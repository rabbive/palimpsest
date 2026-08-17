"""Session -> list[Fact]. One LLM call per session, closed-vocabulary predicates,
verbatim source spans (never paraphrase — this is our provenance).
"""

import json

from palimpsest import config, llm
from palimpsest.models import Fact
from palimpsest.vocab import PREDICATES

EXTRACTION_SYSTEM = """You extract atomic (subject, predicate, object) facts about the \
USER from one session of a conversation. You are building a long-term memory graph.

Rules:
- predicate MUST be exactly one string from the closed vocabulary list given below,
  or the literal string "OTHER" if nothing fits.
- subject and object are short noun phrases, lowercase-normalized where they name
  an entity (e.g. "user", "priya raghavan", "coimbatore").
- source_span MUST be a verbatim substring copied from the session text — never
  paraphrase. This is the only provenance we keep.
- polarity is "negate" only if the fact explicitly reverses/denies something
  (e.g. "I no longer live in Chennai" -> negate LIVES_IN chennai). Otherwise "affirm".
- Only extract facts stated or clearly implied about the user (not hypotheticals,
  not facts about third parties unless they are relationally tied to the user,
  e.g. "reports to").
- Skip small talk, opinions with no durable content, and anything already generic.
- confidence in [0,1]: 1.0 for explicit statements, lower for inference.

Return ONLY a JSON object: {"facts": [{"subject":..., "predicate":..., "object":...,
"polarity":..., "source_span":..., "confidence":...}, ...]}. Empty list if nothing
extractable.
"""


def _predicate_list_block() -> str:
    return "Closed predicate vocabulary:\n" + ", ".join(PREDICATES)


def extract_session_facts(
    dialogue_id: str,
    session_idx: int,
    session_text: str,
    session_ts: str = "",
    model: str = config.CHEAP_MODEL,
) -> list[Fact]:
    prompt = (
        f"{_predicate_list_block()}\n\n"
        f"SESSION (dialogue={dialogue_id}, session_idx={session_idx}, time_anchor={session_ts}):\n"
        f"{session_text}\n"
    )
    data = llm.complete_json(prompt=prompt, system=EXTRACTION_SYSTEM, model=model)
    raw_facts = data.get("facts", []) if isinstance(data, dict) else []

    facts: list[Fact] = []
    for i, rf in enumerate(raw_facts):
        predicate = rf.get("predicate", "OTHER")
        if predicate not in PREDICATES:
            predicate = "OTHER"
        fact = Fact(
            id=f"f_{dialogue_id}_{session_idx:04d}_{i:03d}",
            dialogue_id=dialogue_id,
            session_idx=session_idx,
            session_ts=session_ts,
            subject=str(rf.get("subject", "user")).strip().lower(),
            predicate=predicate,
            object=str(rf.get("object", "")).strip().lower(),
            polarity=rf.get("polarity", "affirm") if rf.get("polarity") in ("affirm", "negate") else "affirm",
            source_span=str(rf.get("source_span", "")).strip(),
            confidence=float(rf.get("confidence", 1.0)),
        )
        if fact.object:
            facts.append(fact)
    return facts


def session_to_text(turns: list[list[dict]]) -> str:
    """Flatten one BEAM `turns` list (list of [user_msg, assistant_msg, ...]) into text."""
    lines = []
    for turn in turns:
        for msg in turn:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")
    return "\n".join(lines)
