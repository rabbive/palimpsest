"""Orchestration: extract -> reconcile -> ingest -> flip.

Processes one dialogue's sessions in strict chronological order. Every accepted
fact becomes exactly one HydraDB memory (per-fact granularity is required for
per-source `status` flipping to mean anything).
"""

import asyncio

from palimpsest import config, hydra
from palimpsest.extract import extract_session_facts, session_to_text
from palimpsest.ledger import connect, facts_for_slot, insert_fact, mark_historical
from palimpsest.models import Fact
from palimpsest.reconcile import reconcile_fact

EDGE_FOR_LABEL = {
    "REFINEMENT": "REFINES",
    "SUPERSESSION": "SUPERSEDES",
    "CONTRADICTION": "CONTRADICTS",
}


def _byog_payload(fact: Fact, prior: Fact | None, edge_predicate: str | None) -> dict:
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
    return {fact.id: {"entities": entities, "relations": relations}}


async def process_dialogue(dialogue_id: str, sessions: list[tuple[int, str, str]], model: str = config.CHEAP_MODEL):
    """sessions: list of (session_idx, session_ts, session_text), already chronological."""
    new_memories: list[dict] = []
    graph_payload: dict = {}
    to_flip: list[tuple[str, str]] = []  # (fact_id, collection)
    stats = {"NEW": 0, "DUPLICATE": 0, "REFINEMENT": 0, "SUPERSESSION": 0, "CONTRADICTION": 0}

    with connect() as conn:
        for session_idx, session_ts, session_text in sessions:
            candidates = extract_session_facts(dialogue_id, session_idx, session_text, session_ts, model=model)

            for candidate in candidates:
                decision = reconcile_fact(conn, candidate)
                stats[decision.label] += 1

                if decision.label == "DUPLICATE":
                    continue

                fact = decision.candidate
                prior = None
                if decision.prior_fact_id:
                    priors = facts_for_slot(conn, fact.dialogue_id, fact.subject, fact.predicate, status=None)
                    prior = next((p for p in priors if p.id == decision.prior_fact_id), None)

                if decision.label in ("REFINEMENT", "SUPERSESSION"):
                    fact.supersedes = decision.prior_fact_id
                    if prior:
                        mark_historical(conn, prior.id, fact.id)
                        to_flip.append((prior.id, dialogue_id))

                insert_fact(conn, fact)
                new_memories.append({"id": fact.id, "text": f"{fact.subject} {fact.predicate.lower().replace('_', ' ')} {fact.object}.", "infer": False})
                graph_payload.update(
                    _byog_payload(fact, prior, EDGE_FOR_LABEL.get(decision.label))
                )

    if new_memories:
        await hydra.ingest_facts(collection=dialogue_id, memories=new_memories, graph_payload=graph_payload)
        await hydra.wait_for_indexed([m["id"] for m in new_memories], collection=dialogue_id)
        # ingest() cannot set schema-declared metadata per memory -- every new
        # fact starts with `status` unset, which metadata_filters={"status":
        # "current"} treats as a non-match, not a default. Must flip explicitly.
        await asyncio.gather(*[hydra.flip_to_current(m["id"], collection=dialogue_id) for m in new_memories])

    for fact_id, collection in to_flip:
        await hydra.flip_to_historical(fact_id, collection=collection)

    return stats


async def process_dialogues(dialogues: dict[str, list[tuple[int, str, str]]], model: str = config.CHEAP_MODEL, concurrency: int = config.INGEST_CONCURRENCY):
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(dialogue_id, sessions):
        async with sem:
            return dialogue_id, await process_dialogue(dialogue_id, sessions, model=model)

    results = await asyncio.gather(*[_bounded(d, s) for d, s in dialogues.items()])
    return dict(results)
