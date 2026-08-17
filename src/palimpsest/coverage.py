"""Slot decomposition + premise/coverage check.

Abstention is a graph property: decompose the question into required
(entity, predicate) slots, check whether the graph has ANY edge on each slot.
Zero edges on a required slot -> abstain and name it. This is the thing a
vector store cannot do (it always returns top-k, never "absent").
"""

from palimpsest import config, hydra, llm
from palimpsest.models import Abstention
from palimpsest.vocab import PREDICATES

DECOMPOSE_SYSTEM = """Decompose the QUESTION into the minimal set of (entity, predicate) \
memory slots that MUST be filled for the question to be answerable at all. `predicate` \
must be chosen from the closed vocabulary below, or "OTHER" if nothing fits closely.

Closed predicate vocabulary: """ + ", ".join(PREDICATES) + """

Return ONLY a JSON object: {"slots": [{"entity": "...", "predicate": "..."}, ...]}.
Usually 1-3 slots. If the question is pure small talk with no memory dependency,
return {"slots": []}.
"""


def decompose_question(question: str, model: str = config.CHEAP_MODEL) -> list[dict]:
    data = llm.complete_json(prompt=f"QUESTION: {question}", system=DECOMPOSE_SYSTEM, model=model)
    slots = data.get("slots", []) if isinstance(data, dict) else []
    return [s for s in slots if s.get("entity") and s.get("predicate")]


async def slot_has_coverage(dialogue_id: str, entity: str, predicate: str) -> tuple[bool, list[str]]:
    """Query HydraDB for any edge on this slot (current or historical - existence, not truth)."""
    result = await hydra.query(
        q=f"{entity} {predicate.lower().replace('_', ' ')}",
        collection=dialogue_id,
        max_results=5,
        graph_context=True,
        metadata_filters={"subject": entity, "predicate": predicate} if predicate != "OTHER" else None,
    )
    chunks = result.data.chunks or []
    evidence = [c.chunk_content for c in chunks if getattr(c, "chunk_content", None)]
    return (len(evidence) > 0, evidence)


async def check_premise(dialogue_id: str, question: str, model: str = config.CHEAP_MODEL) -> Abstention | None:
    """Returns an Abstention if any required slot has zero coverage, else None."""
    slots = decompose_question(question, model=model)
    if not slots:
        return None

    missing = []
    partial = []
    for slot in slots:
        covered, evidence = await slot_has_coverage(dialogue_id, slot["entity"], slot["predicate"])
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
