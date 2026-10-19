import asyncio
import importlib

import pytest

from palimpsest import config, ledger, memory
from palimpsest.models import Answer, Fact


@pytest.fixture
def mem(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LEDGER_PATH", str(tmp_path / "ledger.sqlite3"))
    return memory.Memory("alice")


@pytest.fixture
def fake_write(monkeypatch, mem):
    seen = {"sessions": []}

    async def fake_process_dialogue(dialogue_id, sessions, model=None):
        # Yield first so a concurrent caller can run before this one inserts;
        # without the lock both would read the same next_session_idx.
        await asyncio.sleep(0)
        seen["sessions"].append(sessions)
        with ledger.connect() as conn:
            for idx, ts, text in sessions:
                ledger.insert_fact(conn, Fact(
                    id=f"f_{dialogue_id}_{idx:04d}_000", dialogue_id=dialogue_id,
                    session_idx=idx, session_ts=ts, subject="user", predicate="said",
                    object=text, source_span=text,
                ))
        return {"NEW": len(sessions)}

    monkeypatch.setattr(memory, "process_dialogue", fake_process_dialogue)
    return seen


@pytest.fixture
def fake_read(monkeypatch):
    seen = {}

    async def fake_answer_question(dialogue_id, question, **kwargs):
        seen["dialogue_id"] = dialogue_id
        seen["question"] = question
        return Answer(text="Bangalore")

    monkeypatch.setattr(memory, "answer_question", fake_answer_question)
    return seen


def test_add_session_uses_next_session_index(fake_write, mem):
    asyncio.run(mem.add_session("I live in Chennai."))
    asyncio.run(mem.add_session("I moved to Bangalore."))
    assert [s[0][0] for s in fake_write["sessions"]] == [0, 1]


def test_concurrent_add_session_gets_distinct_indexes(fake_write, mem):
    async def both():
        await asyncio.gather(mem.add_session("a"), mem.add_session("b"))
    asyncio.run(both())
    assert sorted(s[0][0] for s in fake_write["sessions"]) == [0, 1]


def test_ask_routes_to_the_collection(fake_read, mem):
    assert asyncio.run(mem.ask("Where do I live?")).text == "Bangalore"
    assert fake_read["dialogue_id"] == mem.collection


def test_history_returns_ledger_facts(fake_write, mem):
    asyncio.run(mem.add_session("I live in Chennai.", timestamp="2026-01-01"))
    assert [f.session_ts for f in mem.history()] == ["2026-01-01"]


def test_ledger_path_is_env_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("PALIMPSEST_LEDGER_PATH", str(tmp_path / "l.sqlite3"))
    monkeypatch.setenv("PALIMPSEST_CACHE_DIR", str(tmp_path / "cache"))
    try:
        reloaded = importlib.reload(config)
        assert reloaded.LEDGER_PATH == str(tmp_path / "l.sqlite3")
        assert reloaded.CACHE_DIR == str(tmp_path / "cache")
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_writer_and_memory_share_the_ledger(mem, tmp_path):
    # ledger.connect() is what the real process_dialogue calls with no argument.
    with ledger.connect() as conn:
        ledger.insert_fact(conn, Fact(
            id="f_alice_0000_000", dialogue_id="alice", session_idx=0, subject="user",
            predicate="lives_in", object="Chennai", source_span="x"))
    assert (tmp_path / "ledger.sqlite3").exists()
    assert [f.id for f in mem.history()] == ["f_alice_0000_000"]


def test_connect_creates_only_the_ledger_parent(monkeypatch, tmp_path):
    results = tmp_path / "results"
    monkeypatch.setattr(config, "RESULTS_DIR", results)
    monkeypatch.setattr(config, "LEDGER_PATH", str(tmp_path / "new" / "sub" / "l.sqlite3"))
    with ledger.connect():
        pass
    assert (tmp_path / "new" / "sub" / "l.sqlite3").exists()
    assert not results.exists()
