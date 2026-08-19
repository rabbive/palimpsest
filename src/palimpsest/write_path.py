"""Orchestration: extract -> reconcile -> ingest -> flip.

Processes one dialogue's sessions in strict chronological order. Every accepted
fact becomes exactly one HydraDB memory (per-fact granularity is required for
per-source ``status`` flipping to mean anything).
"""

import asyncio

from palimpsest import config, hydra
from palimpsest.extract import extract_session_facts
from palimpsest.ledger import (
    all_facts,
    bump_pending_attempts,
    clear_pending,
    connect,
    fact_exists,
    facts_for_slot,
    insert_fact,
    mark_historical,
    pending_ids,
    record_pending,
    source_ids,
)
from palimpsest.models import Fact
from palimpsest.reconcile import classify_pair, reconcile_fact

EDGE_FOR_LABEL = {
    "REFINEMENT": "REFINES",
    "SUPERSESSION": "SUPERSEDES",
    "CONTRADICTION": "CONTRADICTS",
}


def _byog_payload(
    fact: Fact,
    prior: Fact | None,
    edge_predicate: str | None,
    source_id: str | None = None,
) -> dict:
    entities = {
        "subject": {"name": fact.subject, "type": "ENTITY", "namespace": "palimpsest"},
        "object": {"name": fact.object, "type": "ENTITY", "namespace": "palimpsest"},
    }
    relations = [
        {
            "source": "subject",
            "target": "object",
            "predicate": fact.predicate,
            "context": fact.source_span[:2000],
            "temporal_details": f"dialogue {fact.dialogue_id}, session {fact.session_idx}"
            + (f", {fact.session_ts}" if fact.session_ts else ""),
        }
    ]
    if prior and edge_predicate:
        entities["prior_object"] = {"name": prior.object, "type": "ENTITY", "namespace": "palimpsest"}
        relations.append(
            {
                "source": "object",
                "target": "prior_object",
                "predicate": edge_predicate,
                "context": f"{edge_predicate.lower()} fact {prior.id} at session {fact.session_idx}",
                "temporal_details": f"supersedes {prior.id} at session {fact.session_idx}",
            }
        )
    return {source_id or fact.id: {"entities": entities, "relations": relations}}


async def _set_remote_statuses(
    collection: str,
    facts: list[Fact],
    not_indexed: set[str] | None = None,
) -> None:
    """Materialize metadata only for sources known to be indexed."""
    not_indexed = not_indexed or set()
    fact_ids = {fact.id for fact in facts}
    predecessor_ids = {
        fact.supersedes
        for fact in facts
        if fact.supersedes
        and fact.supersedes not in not_indexed
        and fact.supersedes not in fact_ids
    }
    canonical_ids = sorted(fact_ids | predecessor_ids)
    with connect() as conn:
        remote_ids = source_ids(conn, canonical_ids)

    flip_sem = asyncio.Semaphore(max(1, config.INGEST_CONCURRENCY * 4))

    async def _bounded_fact(fact: Fact) -> None:
        async with flip_sem:
            await hydra.set_fact_metadata(
                fact,
                collection,
                source_id=remote_ids[fact.id],
            )

    async def _bounded_historical(fact_id: str) -> None:
        async with flip_sem:
            await hydra.set_status(remote_ids[fact_id], collection, "historical")

    # Materialize all schema fields used by coverage queries, not only status.
    # Then hide predecessors that were indexed in an earlier batch.
    await asyncio.gather(*[_bounded_fact(fact) for fact in facts])
    await asyncio.gather(*[_bounded_historical(fact_id) for fact_id in predecessor_ids])


async def _retry_pending(dialogue_id: str, stats: dict) -> None:
    """Resume facts checkpointed before a previous run timed out or crashed."""
    with connect() as conn:
        ids = pending_ids(conn, dialogue_id)
        facts_by_id = {fact.id: fact for fact in all_facts(conn, dialogue_id)}
        facts = [facts_by_id[fact_id] for fact_id in ids if fact_id in facts_by_id]
        remote_ids = source_ids(conn, ids)

    if not facts:
        return

    memories = [
        {
            "id": remote_ids[fact.id],
            "text": f"{fact.subject} {fact.predicate.lower().replace('_', ' ')} {fact.object}.",
            "infer": False,
        }
        for fact in facts
    ]
    graph_payload = {}
    for fact in facts:
        prior = facts_by_id.get(fact.supersedes)
        edge = None
        if prior:
            label, _reason = classify_pair(prior, fact)
            edge = EDGE_FOR_LABEL.get(label, "SUPERSEDES")
        graph_payload.update(
            _byog_payload(
                fact,
                prior,
                edge,
                source_id=remote_ids[fact.id],
            )
        )

    straggler_sources = await hydra.ingest_facts_with_backpressure(
        collection=dialogue_id,
        memories=memories,
        graph_payload=graph_payload,
    )
    fact_by_source = {source_id: fact_id for fact_id, source_id in remote_ids.items()}
    stragglers = {fact_by_source[source_id] for source_id in straggler_sources}
    indexed_facts = [fact for fact in facts if fact.id not in stragglers]
    if indexed_facts:
        await _set_remote_statuses(dialogue_id, indexed_facts, not_indexed=stragglers)

    with connect() as conn:
        clear_pending(conn, [fact.id for fact in indexed_facts])
        bump_pending_attempts(conn, sorted(stragglers), "still queued after retry")

    if stragglers:
        stats["stragglers"] = sorted(set(stats.get("stragglers", [])) | stragglers)


async def process_dialogue(
    dialogue_id: str,
    sessions: list[tuple[int, str, str]],
    model: str = config.CHEAP_MODEL,
):
    """Process sessions chronologically with checkpointed HydraDB ingestion."""
    new_memories: list[dict] = []
    graph_payload: dict = {}
    stats = {"NEW": 0, "DUPLICATE": 0, "REFINEMENT": 0, "SUPERSESSION": 0, "CONTRADICTION": 0}

    # A previous run may have committed facts locally before HydraDB finished
    # indexing them. Retry those IDs first; this makes reruns resumable and avoids
    # treating a queued fact as a duplicate that never gets re-submitted.
    await _retry_pending(dialogue_id, stats)

    # Reconciliation and pending-ingest records are committed before remote
    # calls. This is an outbox/checkpoint: a HydraDB timeout no longer rolls back
    # the whole dialogue, and the next run can retry only unfinished sources.
    with connect() as conn:
        for session_idx, session_ts, session_text in sessions:
            candidates = extract_session_facts(
                dialogue_id, session_idx, session_text, session_ts, model=model
            )

            for candidate in candidates:
                # Fact IDs are deterministic. On a resumed run, do not invoke
                # reconciliation again for a fact already checkpointed locally;
                # only the pending-ingest outbox needs remote work.
                if fact_exists(conn, candidate.id):
                    stats["DUPLICATE"] += 1
                    continue
                decision = reconcile_fact(conn, candidate)
                stats[decision.label] += 1

                if decision.label == "DUPLICATE":
                    continue

                fact = decision.candidate
                prior = None
                if decision.prior_fact_id:
                    priors = facts_for_slot(
                        conn, fact.dialogue_id, fact.subject, fact.predicate, status=None
                    )
                    prior = next((p for p in priors if p.id == decision.prior_fact_id), None)

                if decision.label in ("REFINEMENT", "SUPERSESSION"):
                    fact.supersedes = decision.prior_fact_id
                    if prior:
                        mark_historical(conn, prior.id, fact.id)

                insert_fact(conn, fact)
                new_memories.append(
                    {
                        "id": fact.id,
                        "text": f"{fact.subject} {fact.predicate.lower().replace('_', ' ')} {fact.object}.",
                        "infer": False,
                    }
                )
                graph_payload.update(_byog_payload(fact, prior, EDGE_FOR_LABEL.get(decision.label)))

        if new_memories:
            record_pending(conn, [memory["id"] for memory in new_memories], dialogue_id)

    if new_memories:
        all_ids = [memory["id"] for memory in new_memories]
        stragglers = await hydra.ingest_facts_with_backpressure(
            collection=dialogue_id,
            memories=new_memories,
            graph_payload=graph_payload,
        )
        indexed_ids = set(all_ids) - stragglers

        with connect() as conn:
            fact_rows = {fact.id: fact for fact in all_facts(conn, dialogue_id)}
        await _set_remote_statuses(
            dialogue_id,
            [fact_rows[memory["id"]] for memory in new_memories if memory["id"] in indexed_ids],
            not_indexed=stragglers,
        )

        with connect() as conn:
            clear_pending(conn, sorted(indexed_ids))
            bump_pending_attempts(conn, sorted(stragglers), "still queued after retry")

        if stragglers:
            stats["stragglers"] = sorted(stragglers)

    return stats


def halt_reason(runs: list[dict], max_stragglers: int) -> str | None:
    """Decide whether a multi-dialogue ingestion must stop, per NEXT_STEPS.md.

    ``runs`` is the per-dialogue record so far, each entry ``{"dialogue_id",
    "stats", "error"}``. Returns a human-readable reason to halt, or None to
    continue.

    These are the documented stop conditions, enforced rather than described.
    The original `ingest-all 7 8` incident is what they exist for: the loop had
    no notion of "this is going wrong", so a wedged queue on the first dialogue
    was followed by submitting the next one into the same queue.
    """
    if not runs:
        return None

    last = runs[-1]
    if last.get("error"):
        return f"dialogue {last['dialogue_id']} failed: {last['error']}"

    stragglers = last.get("stats", {}).get("stragglers", [])
    if len(stragglers) > max_stragglers:
        return (
            f"dialogue {last['dialogue_id']} left {len(stragglers)} sources queued "
            f"(limit {max_stragglers}); HydraDB indexing is not keeping up"
        )

    # `hydra_pending` growing across independent dialogues is the signal that the
    # queue itself is unhealthy, not that one dialogue is unlucky.
    with_stragglers = [r["dialogue_id"] for r in runs if r.get("stats", {}).get("stragglers")]
    if len(with_stragglers) > 1:
        return (
            "sources are queuing across independent dialogues "
            f"({', '.join(with_stragglers)}); stop and check HydraDB health"
        )

    return None


async def process_dialogues(
    dialogues: dict[str, list[tuple[int, str, str]]],
    model: str = config.CHEAP_MODEL,
    concurrency: int = config.INGEST_CONCURRENCY,
):
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(dialogue_id, sessions):
        async with sem:
            return dialogue_id, await process_dialogue(dialogue_id, sessions, model=model)

    results = await asyncio.gather(*[_bounded(d, s) for d, s in dialogues.items()])
    return dict(results)
