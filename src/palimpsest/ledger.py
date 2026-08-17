"""Local SQLite mirror of the fact ledger.

Powers cheap reads: supersession-chain walking, ablation switches, the inspector UI.
Every answer path still goes through hydra.query() — this file is never read on the
answer path, only on the write path and by tooling.
"""

import sqlite3
from contextlib import contextmanager

from palimpsest import config
from palimpsest.models import Fact

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    dialogue_id TEXT NOT NULL,
    session_idx INTEGER NOT NULL,
    session_ts TEXT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    polarity TEXT NOT NULL,
    source_span TEXT NOT NULL,
    status TEXT NOT NULL,
    superseded_by TEXT,
    supersedes TEXT,
    confidence REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_slot ON facts (dialogue_id, subject, predicate);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts (dialogue_id, status);
"""


@contextmanager
def connect(path: str = config.LEDGER_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_fact(conn: sqlite3.Connection, fact: Fact) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO facts
        (id, dialogue_id, session_idx, session_ts, subject, predicate, object,
         polarity, source_span, status, superseded_by, supersedes, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            fact.id, fact.dialogue_id, fact.session_idx, fact.session_ts,
            fact.subject, fact.predicate, fact.object, fact.polarity,
            fact.source_span, fact.status, fact.superseded_by, fact.supersedes,
            fact.confidence,
        ),
    )


def mark_historical(conn: sqlite3.Connection, fact_id: str, superseded_by: str) -> None:
    conn.execute(
        "UPDATE facts SET status = 'historical', superseded_by = ? WHERE id = ?",
        (superseded_by, fact_id),
    )


def facts_for_slot(conn: sqlite3.Connection, dialogue_id: str, subject: str, predicate: str, status: str | None = "current") -> list[Fact]:
    q = "SELECT * FROM facts WHERE dialogue_id = ? AND subject = ? AND predicate = ?"
    params = [dialogue_id, subject, predicate]
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY session_idx ASC"
    rows = conn.execute(q, params).fetchall()
    return [_row_to_fact(r) for r in rows]


def supersession_chain(conn: sqlite3.Connection, fact_id: str) -> list[Fact]:
    """Walk backward from fact_id through `supersedes` links to the origin fact."""
    chain = []
    current = fact_id
    seen = set()
    while current and current not in seen:
        seen.add(current)
        row = conn.execute("SELECT * FROM facts WHERE id = ?", (current,)).fetchone()
        if not row:
            break
        fact = _row_to_fact(row)
        chain.append(fact)
        current = fact.supersedes
    return chain


def all_facts(conn: sqlite3.Connection, dialogue_id: str) -> list[Fact]:
    rows = conn.execute(
        "SELECT * FROM facts WHERE dialogue_id = ? ORDER BY session_idx ASC", (dialogue_id,)
    ).fetchall()
    return [_row_to_fact(r) for r in rows]


def _row_to_fact(row: sqlite3.Row) -> Fact:
    return Fact(
        id=row["id"], dialogue_id=row["dialogue_id"], session_idx=row["session_idx"],
        session_ts=row["session_ts"] or "", subject=row["subject"], predicate=row["predicate"],
        object=row["object"], polarity=row["polarity"], source_span=row["source_span"],
        status=row["status"], superseded_by=row["superseded_by"], supersedes=row["supersedes"],
        confidence=row["confidence"],
    )
