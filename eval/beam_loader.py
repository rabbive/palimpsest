"""Parse BEAM-100K dialogues and probing questions. Subset frozen here."""

import json
from pathlib import Path

from palimpsest import config

# Frozen eval subset: 100K bucket, weighted toward the categories our architecture
# targets (Abstention, Contradiction Resolution, Knowledge Update, Temporal
# Reasoning, Event Ordering). Dialogue ids are directory names under chats/100K/.
FROZEN_SUBSET = ["1", "2", "3", "4", "5", "6", "7", "8"]

PRIORITY_CATEGORIES = [
    "abstention",
    "contradiction_resolution",
    "knowledge_update",
    "temporal_reasoning",
    "event_ordering",
]


def dialogue_dir(dialogue_id: str) -> Path:
    return config.BEAM_CHATS_100K / dialogue_id


def load_chat(dialogue_id: str) -> list[dict]:
    with open(dialogue_dir(dialogue_id) / "chat.json") as f:
        return json.load(f)


def load_probing_questions(dialogue_id: str) -> dict:
    with open(dialogue_dir(dialogue_id) / "probing_questions" / "probing_questions.json") as f:
        return json.load(f)


def iter_sessions(dialogue_id: str):
    """Yields (session_idx, session_ts, session_text) in chronological order.

    BEAM chat.json is a list of batches, each with a "turns" list of
    [user_msg, assistant_msg, ...] pairs. We treat each batch as one session.
    """
    from palimpsest.extract import session_to_text

    batches = load_chat(dialogue_id)
    for session_idx, batch in enumerate(batches):
        turns = batch.get("turns", [])
        ts = ""
        for turn in turns:
            for msg in turn:
                if msg.get("time_anchor"):
                    ts = msg["time_anchor"]
                    break
            if ts:
                break
        yield session_idx, ts, session_to_text(turns)


def iter_questions(dialogue_id: str, categories: list[str] | None = None):
    """Yields (category, index, question_dict) for a dialogue's probing questions."""
    data = load_probing_questions(dialogue_id)
    for category, questions in data.items():
        if categories and category not in categories:
            continue
        for index, q in enumerate(questions):
            yield category, index, q
