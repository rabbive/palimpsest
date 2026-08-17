"""Intent classification -> retrieve (status-filtered) -> premise/coverage check -> answer.

Every answer path goes through hydra.query(). We never answer from SQLite.
"""

from palimpsest import config, hydra, llm
from palimpsest.coverage import check_premise
from palimpsest.models import Answer

INTENT_SYSTEM = """Classify the QUESTION into exactly one intent:
- CURRENT: asks what is true now / currently.
- AS_OF: asks what was true at a specific past point in time ("what did I say in March").
- ORDERING: asks about the sequence/order of events.
- AGGREGATE: asks for a synthesis across multiple facts/sessions, no single current answer.

Return ONLY {"intent": "CURRENT"|"AS_OF"|"ORDERING"|"AGGREGATE"}.
"""

ANSWER_SYSTEM = """Answer the QUESTION using ONLY the provided CONTEXT (retrieved memory \
chunks and graph traversal paths). If the context is insufficient, say so plainly. Cite \
which fact(s) you used implicitly by staying close to their wording. Be concise."""


def classify_intent(question: str, model: str = config.CHEAP_MODEL) -> str:
    data = llm.complete_json(prompt=f"QUESTION: {question}", system=INTENT_SYSTEM, model=model)
    intent = data.get("intent", "CURRENT") if isinstance(data, dict) else "CURRENT"
    return intent if intent in ("CURRENT", "AS_OF", "ORDERING", "AGGREGATE") else "CURRENT"


def _metadata_filters_for_intent(intent: str) -> dict | None:
    if intent == "CURRENT":
        return {"status": "current"}
    # AS_OF / ORDERING / AGGREGATE need the full chain, not just the live view.
    return None


async def answer_question(dialogue_id: str, question: str, model: str = config.CHEAP_MODEL, strong_model: str = config.STRONG_MODEL) -> Answer:
    intent = classify_intent(question, model=model)

    abstention = await check_premise(dialogue_id, question, model=model)
    if abstention is not None:
        return Answer(
            text=f"I can't answer this — {abstention.reason}.",
            abstention=abstention,
            provenance=abstention.partial_matches,
            intent=intent,
        )

    result = await hydra.query(
        q=question,
        collection=dialogue_id,
        max_results=20,
        num_related_chunks=3,
        graph_context=True,
        recency_bias=0.2 if intent != "AS_OF" else 0.0,
        metadata_filters=_metadata_filters_for_intent(intent),
    )

    chunks = result.data.chunks or []
    chunk_texts = [c.chunk_content for c in chunks if getattr(c, "chunk_content", None)]

    query_paths = []
    if result.data.graph_context and result.data.graph_context.query_paths:
        query_paths = [str(p) for p in result.data.graph_context.query_paths]

    if intent == "ORDERING":
        context_block = "\n".join(f"- {p}" for p in query_paths) or "\n".join(chunk_texts)
    else:
        context_block = "\n".join(chunk_texts)

    if not context_block.strip():
        ab = Abstention(missing_slots=["<no matching context>"], reason="Retrieval returned no chunks for this question")
        return Answer(text="I don't have this in memory.", abstention=ab, intent=intent)

    prompt = f"QUESTION: {question}\n\nCONTEXT:\n{context_block}"
    text = llm.complete(prompt=prompt, system=ANSWER_SYSTEM, model=strong_model)

    return Answer(text=text, abstention=None, provenance=chunk_texts + query_paths, intent=intent)
