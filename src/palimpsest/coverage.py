"""Slot decomposition + premise/coverage check.

Decompose the question into required (entity, predicate) slots, then check whether
the store holds ANY fact about each slot. Stored facts all have subject "user" and a
coarse predicate, so the check retrieves the top 5 from HydraDB with no metadata
filter and a cheap model verifies whether any of them is about the slot. If none is,
the system abstains and names the missing slot. A plain top-k retriever has no
"absent" signal of its own; this check supplies one.
"""

import logging
import threading

from palimpsest import config, hydra, llm
from palimpsest.models import Abstention
from palimpsest.vocab import PREDICATES

log = logging.getLogger(__name__)

# Times the verifier failed open. Eval runs items in threads (one event loop each), so
# this is a threading.Lock, not asyncio.
FAIL_OPEN_COUNT = 0
_fail_open_lock = threading.Lock()


def _record_fail_open(reason: str) -> None:
    global FAIL_OPEN_COUNT
    with _fail_open_lock:
        FAIL_OPEN_COUNT += 1
    log.warning("coverage verifier failed open: %s", reason)


DECOMPOSE_SYSTEM = """Decompose the QUESTION into the minimal set of (entity, predicate) \
memory slots that MUST be filled for the question to be answerable at all. `entity` is \
the specific thing the question is about: a person, event, project, place or object. Use \
'user' only when the question is about the user in general. `predicate` \
must be chosen from the closed vocabulary below, or "OTHER" if nothing fits closely.

Closed predicate vocabulary: """ + ", ".join(PREDICATES) + """

Return ONLY a JSON object: {"slots": [{"entity": "...", "predicate": "..."}, ...]}.
Usually 1-3 slots. If the question is pure small talk with no memory dependency,
return {"slots": []}.
"""

COVERAGE_SYSTEM = """You decide whether a memory store holds ANY fact about a slot. \
ENTITY is the thing the question is about; PREDICATE is the kind of information needed. \
FACTS are the closest facts in the store. Answer covered=true if at least one fact is about \
the same entity and the same kind of information, even if worded differently or if its \
value later changed. Answer covered=false only if no fact is about that entity and kind of \
information. Return ONLY {"covered": true} or {"covered": false}."""


def _normalize_entity(entity: str) -> str:
    normalized = entity.strip().lower()
    if normalized in {"i", "me", "my", "myself", "the user"}:
        return "user"
    return normalized


def decompose_question(question: str, model: str = config.CHEAP_MODEL) -> list[dict]:
    data = llm.complete_json(prompt=f"QUESTION: {question}", system=DECOMPOSE_SYSTEM, model=model)
    slots = data.get("slots", []) if isinstance(data, dict) else []
    return [
        {"entity": _normalize_entity(str(slot["entity"])), "predicate": slot["predicate"]}
        for slot in slots
        if slot.get("entity") and slot.get("predicate")
    ]


def _evidence_covers_slot(entity: str, predicate: str, evidence: list[str], model: str) -> bool:
    """Fail open: anything but an explicit covered=false counts as covered, so a verifier
    glitch answers the question instead of abstaining."""
    facts = "\n".join(f"- {fact}" for fact in evidence)
    try:
        data = llm.complete_json(
            prompt=f"ENTITY: {entity}\nPREDICATE: {predicate}\nFACTS:\n{facts}",
            system=COVERAGE_SYSTEM,
            model=model,
        )
    except ValueError:  # JSONDecodeError on empty/prose reply; timeouts and budget errors still propagate
        _record_fail_open("unparseable verifier reply")
        return True
    if not isinstance(data, dict):
        _record_fail_open(f"non-dict verifier reply ({type(data).__name__})")
        return True
    return data.get("covered") is not False


async def slot_has_coverage(
    dialogue_id: str, entity: str, predicate: str, model: str = config.CHEAP_MODEL
) -> tuple[bool, list[str]]:
    """Retrieve the nearest facts (any status, no subject/predicate filter - existence, not
    truth) and ask a verifier whether any is about this slot."""
    words = "" if predicate == "OTHER" else " " + predicate.lower().replace("_", " ")
    result = await hydra.query(
        q=f"{entity}{words}",
        collection=dialogue_id,
        max_results=5,
        graph_context=True,
        metadata_filters=None,
    )
    chunks = result.data.chunks or []
    evidence = [c.chunk_content for c in chunks if getattr(c, "chunk_content", None)]
    if not evidence:
        return (False, [])
    return (_evidence_covers_slot(entity, predicate, evidence, model), evidence)


async def check_premise(dialogue_id: str, question: str, model: str = config.CHEAP_MODEL) -> Abstention | None:
    """Returns an Abstention if any required slot has zero coverage, else None."""
    slots = decompose_question(question, model=model)
    if not slots:
        return None

    missing = []
    partial = []
    for slot in slots:
        covered, evidence = await slot_has_coverage(dialogue_id, slot["entity"], slot["predicate"], model)
        if not covered:
            missing.append(f"{slot['entity']} / {slot['predicate']}")
        else:
            partial.extend(evidence)

    if missing:
        return Abstention(
            missing_slots=missing,
            reason=f"No fact in memory covers: {', '.join(missing)}",
            partial_matches=partial,
        )
    return None
