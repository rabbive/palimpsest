"""Arm B is the load-bearing comparison, and it had never been provisioned.

Its corpus lives in a separate database because it ingests raw sessions with
infer=True; letting HydraDB extract into arm C's database would contaminate the
thing being measured. Nothing created that database, and the only code path that
populated it also re-ingested arm C — which the ingestion runbook forbids for the
dialogues already in flight. So an evaluation including arm B would error on
every arm-B question while still paying for arms A and C on the same questions.
"""

import asyncio

import pytest

import eval.run_eval as run_eval


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_eval,
        "iter_questions",
        lambda dialogue_id, categories: [("abstention", 0, {"question": "q0", "rubric": ["r"]})],
    )
    monkeypatch.setattr(run_eval, "judge_question", lambda rubric, response: {"llm_judge_score": 1.0})

    async def dispatch(dialogue_id, question, arm):
        return f"answer from {arm}", False

    monkeypatch.setattr(run_eval, "_dispatch", dispatch)
    return {"checkpoint": str(tmp_path / "raw_eval.jsonl")}


def _with_counts(monkeypatch, counts: dict[str, int]):
    async def source_count(dialogue_id):
        return counts.get(dialogue_id, 0)

    monkeypatch.setattr(run_eval, "arm_b_source_count", source_count)


def test_arm_b_without_a_corpus_fails_fast(harness, monkeypatch):
    _with_counts(monkeypatch, {})

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            run_eval.run_eval(
                dialogues=["7", "8"],
                categories=["abstention"],
                arms=["A", "B", "C"],
                checkpoint_path=harness["checkpoint"],
            )
        )

    message = str(exc.value)
    assert "7, 8" in message
    assert "setup-arm-b 7 8" in message  # names the exact fix
    assert "--arms A,C" in message  # and the escape hatch


def test_a_partially_ingested_arm_b_names_only_what_is_missing(harness, monkeypatch):
    _with_counts(monkeypatch, {"7": 190})

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            run_eval.run_eval(
                dialogues=["7", "8"],
                arms=["B"],
                categories=["abstention"],
                checkpoint_path=harness["checkpoint"],
            )
        )

    message = str(exc.value)
    assert "dialogue(s) 8" in message
    assert "7, 8" not in message


def test_arm_b_with_a_corpus_runs(harness, monkeypatch):
    _with_counts(monkeypatch, {"7": 190})

    results = asyncio.run(
        run_eval.run_eval(
            dialogues=["7"],
            arms=["A", "B", "C"],
            categories=["abstention"],
            checkpoint_path=harness["checkpoint"],
        )
    )
    assert len(results) == 3


def test_dropping_arm_b_skips_the_check_entirely(harness, monkeypatch):
    """--arms A,C must not require a reachable arm-B database at all."""

    async def explode(dialogue_id):
        raise AssertionError("arm B must not be probed when it is not being run")

    monkeypatch.setattr(run_eval, "arm_b_source_count", explode)

    results = asyncio.run(
        run_eval.run_eval(
            dialogues=["7"],
            arms=["A", "C"],
            categories=["abstention"],
            checkpoint_path=harness["checkpoint"],
        )
    )
    assert len(results) == 2


def test_an_unreachable_arm_b_database_counts_as_missing(monkeypatch):
    async def boom(dialogue_id):
        raise ConnectionError("no such database")

    monkeypatch.setattr(run_eval, "arm_b_source_count", boom)
    assert asyncio.run(run_eval.missing_arm_b_dialogues(["7"])) == ["7"]


def test_arm_b_ingest_tolerates_stragglers(monkeypatch):
    """Aborting arm B's setup over one queued source is the mistake already learned."""
    captured = {}

    monkeypatch.setattr(
        run_eval,
        "iter_sessions",
        lambda dialogue_id: [(0, "", "a session"), (1, "", "another session")],
    )

    async def fake_backpressure(**kwargs):
        captured.update(kwargs)
        return {"b_7_1"}

    monkeypatch.setattr(run_eval.hydra, "ingest_facts_with_backpressure", fake_backpressure)

    stragglers = asyncio.run(run_eval.setup_arm_b("7"))
    assert stragglers == {"b_7_1"}
    assert captured["database"] == run_eval.ARM_B_DATABASE
    assert all(m["infer"] is True for m in captured["memories"])


def test_the_spend_cap_stops_the_run_instead_of_becoming_a_row(harness, monkeypatch):
    """BudgetExceeded is a RuntimeError, so the generic handler would have turned
    hitting the cap into an error row and kept going — quietly producing an error
    row for every remaining question while looking like a completed run."""
    _with_counts(monkeypatch, {"7": 190})

    async def broke(dialogue_id, question, arm):
        raise run_eval.llm.BudgetExceeded("spent $45.00 of the $45.00 cap")

    monkeypatch.setattr(run_eval, "_dispatch", broke)

    with pytest.raises(run_eval.llm.BudgetExceeded):
        asyncio.run(
            run_eval.run_eval(
                dialogues=["7"],
                arms=["A", "C"],
                categories=["abstention"],
                checkpoint_path=harness["checkpoint"],
            )
        )


def test_a_judge_hitting_the_cap_also_stops_the_run(harness, monkeypatch):
    _with_counts(monkeypatch, {"7": 190})

    def broke(rubric, response):
        raise run_eval.llm.BudgetExceeded("cap")

    monkeypatch.setattr(run_eval, "judge_question", broke)

    with pytest.raises(run_eval.llm.BudgetExceeded):
        asyncio.run(
            run_eval.run_eval(
                dialogues=["7"],
                arms=["C"],
                categories=["abstention"],
                checkpoint_path=harness["checkpoint"],
            )
        )


def test_the_estimate_flags_arm_a_as_the_dominant_cost(monkeypatch):
    monkeypatch.setattr(run_eval, "_full_transcript", lambda dialogue_id: "x" * 400_000)

    items = [
        {"dialogue_id": "7", "category": "abstention", "question": "q", "rubric": ["a", "b"], "arm": "A"},
        {"dialogue_id": "7", "category": "abstention", "question": "q", "rubric": ["a", "b"], "arm": "C"},
    ]
    lines = "\n".join(run_eval.estimate_lines(items))
    assert "2 answer calls + 4 judge calls" in lines
    assert "100,000 input tokens" in lines  # 400k chars / 4, arm A only
    assert "cap" in lines


def test_the_estimate_is_silent_with_nothing_to_run():
    assert run_eval.estimate_lines([]) == []
