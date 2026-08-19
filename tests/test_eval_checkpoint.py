"""The eval harness must survive being killed mid-run.

The first full evaluation was a single sequential pass that wrote its output
only at the end; a 30-minute timeout destroyed all of it. These tests pin the
behaviour that replaced it.
"""

import json

from eval.run_eval import ALL_ARMS, ARM_C_VARIANTS, _work_items, append_checkpoint, load_checkpoint
from palimpsest.models import EvalResult


def _result(**overrides) -> EvalResult:
    fields = {
        "dialogue_id": "7",
        "category": "abstention",
        "question": "who is my manager?",
        "arm": "C",
        "llm_response": "I can't answer this",
        "llm_judge_score": 1.0,
    }
    fields.update(overrides)
    return EvalResult(**fields)


def test_checkpoint_roundtrip_resumes_completed_work(tmp_path):
    path = str(tmp_path / "raw_eval.jsonl")
    append_checkpoint(path, _result())
    append_checkpoint(path, _result(arm="A", llm_response="Priya"))

    done = load_checkpoint(path)
    assert set(done) == {
        "7|abstention|C|who is my manager?",
        "7|abstention|A|who is my manager?",
    }


def test_errored_rows_are_retried_not_resumed(tmp_path):
    path = str(tmp_path / "raw_eval.jsonl")
    append_checkpoint(path, _result(llm_judge_score=None, error="ReadTimeout"))
    assert load_checkpoint(path) == {}


def test_torn_final_line_does_not_break_resume(tmp_path):
    path = str(tmp_path / "raw_eval.jsonl")
    append_checkpoint(path, _result())
    with open(path, "a") as f:
        f.write('{"dialogue_id": "7", "cat')  # killed mid-write

    assert len(load_checkpoint(path)) == 1


def test_missing_checkpoint_is_an_empty_resume(tmp_path):
    assert load_checkpoint(str(tmp_path / "nope.jsonl")) == {}


def test_result_key_matches_checkpoint_key(tmp_path):
    path = str(tmp_path / "raw_eval.jsonl")
    result = _result()
    append_checkpoint(path, result)
    assert result.key in load_checkpoint(path)


def test_every_arm_is_dispatchable():
    assert ALL_ARMS == ["A", "B", *ARM_C_VARIANTS]
    # Each ablation must switch off something arm C has on, or it is not an ablation.
    assert ARM_C_VARIANTS["C"] == (True, True)
    for arm, flags in ARM_C_VARIANTS.items():
        if arm != "C":
            assert flags != (True, True)


def test_work_items_fan_out_over_arms(monkeypatch):
    import eval.run_eval as run_eval

    monkeypatch.setattr(
        run_eval,
        "iter_questions",
        lambda dialogue_id, categories: [
            ("abstention", 0, {"question": "q0", "rubric": ["r"]}),
            ("abstention", 1, {"question": "q1", "rubric": ["r"]}),
        ],
    )

    items = _work_items(["7"], ["abstention"], ["A", "C"], limit_per_category=0)
    assert len(items) == 4
    assert {i["arm"] for i in items} == {"A", "C"}

    capped = _work_items(["7"], ["abstention"], ["A", "C"], limit_per_category=1)
    assert {i["question"] for i in capped} == {"q0"}


def test_run_eval_checkpoints_each_result_and_resumes_after_a_kill(tmp_path, monkeypatch):
    """The end-to-end guarantee: whatever finished before the run died is on disk,
    and a rerun only pays for what did not."""
    import asyncio

    import eval.run_eval as run_eval

    checkpoint = str(tmp_path / "raw_eval.jsonl")
    monkeypatch.setattr(
        run_eval,
        "iter_questions",
        lambda dialogue_id, categories: [("abstention", 0, {"question": "q0", "rubric": ["r"]})],
    )
    monkeypatch.setattr(run_eval, "judge_question", lambda rubric, response: {"llm_judge_score": 1.0})

    # Arm B is provisioned here; this test is about a flaky *query*, not a
    # missing corpus. Without the stub the arm-B preflight refuses the run --
    # which is its job, and is covered in tests/test_arm_b.py.
    async def arm_b_ready(dialogue_id):
        return 190

    monkeypatch.setattr(run_eval, "arm_b_source_count", arm_b_ready)

    attempts: list[str] = []

    async def flaky_dispatch(dialogue_id, question, arm):
        attempts.append(arm)
        if arm == "B":
            raise RuntimeError("ReadTimeout")
        return f"answer from {arm}", False

    monkeypatch.setattr(run_eval, "_dispatch", flaky_dispatch)

    kwargs = dict(
        dialogues=["7"],
        categories=["abstention"],
        arms=["A", "B", "C"],
        checkpoint_path=checkpoint,
        concurrency=2,
    )
    first = asyncio.run(run_eval.run_eval(**kwargs))
    assert len(first) == 3
    assert sorted(attempts) == ["A", "B", "C"]

    # Second pass: A and C are already banked, only the errored B is retried.
    attempts.clear()
    second = asyncio.run(run_eval.run_eval(**kwargs))
    assert attempts == ["B"]
    assert len(second) == 3
