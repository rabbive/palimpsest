"""Report tables have to be readable off a partial run, since that is the likely
shape of the final numbers: errored arm-runs excluded from accuracy, counted
separately, and the coverage stated rather than implied."""

import json

from eval.report import _abstention_table, _cost_latency_table, _coverage_note, _score_table, load_results


def _row(**overrides) -> dict:
    row = {
        "dialogue_id": "7",
        "category": "knowledge_update",
        "question": "who is my manager?",
        "arm": "C",
        "llm_response": "Priya",
        "llm_judge_score": 1.0,
        "abstained": False,
        "latency_seconds": 2.0,
        "cost_usd": 0.01,
        "error": None,
    }
    row.update(overrides)
    return row


def test_errors_are_excluded_from_scores_not_scored_as_zero():
    rows = [_row(), _row(arm="A", llm_judge_score=None, error="timeout")]
    table = _score_table(rows, ["A", "C"])
    assert "1.00 (n=1)" in table
    assert "A: full-context stuffing" not in table  # no scored rows for A at all


def test_abstention_is_reported_in_both_directions():
    rows = [
        _row(category="abstention", abstained=True),
        _row(category="knowledge_update", abstained=False),
    ]
    table = _abstention_table(rows)
    assert "100% (n=1)" in table  # abstained where it should
    assert "0% (n=1)" in table  # did not abstain where it should not


def test_cost_latency_counts_errors_separately():
    rows = [_row(), _row(llm_judge_score=None, error="ReadTimeout", question="q2")]
    table = _cost_latency_table(rows)
    assert "$0.02" in table  # total cost includes the errored attempt's spend
    assert table.strip().splitlines()[2].endswith("| 1 |")


def test_coverage_note_names_the_dialogues_and_errors():
    note = _coverage_note([_row(), _row(dialogue_id="8", error="timeout")])
    assert "2 dialogue(s) (7, 8)" in note
    assert "1 arm-run(s) errored" in note


def test_report_falls_back_to_the_checkpoint(tmp_path):
    checkpoint = tmp_path / "raw_eval.jsonl"
    with open(checkpoint, "w") as f:
        f.write(json.dumps(_row()) + "\n")
        f.write(json.dumps(_row(llm_judge_score=0.5)) + "\n")  # a rerun of the same key

    rows = load_results(str(tmp_path / "absent.json"), str(checkpoint))
    assert len(rows) == 1
    assert rows[0]["llm_judge_score"] == 0.5  # later row wins
