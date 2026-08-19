"""Multi-dialogue ingestion must stop when HydraDB's queue starts wedging.

The original `ingest-all 7 8` incident: dialogue 7 left 54 sources queued and
dialogue 8 was submitted into the same queue regardless, because the loop had no
notion of "this is going wrong". These are those stop conditions as code.
"""

from palimpsest.write_path import halt_reason


def _run(dialogue_id: str, stragglers: int = 0, error: str | None = None) -> dict:
    return {
        "dialogue_id": dialogue_id,
        "stats": {"stragglers": [f"f_{dialogue_id}_{i}" for i in range(stragglers)]} if stragglers else {},
        "error": error,
    }


def test_a_clean_run_continues():
    assert halt_reason([], 5) is None
    assert halt_reason([_run("1"), _run("2")], 5) is None


def test_a_few_stragglers_on_one_dialogue_do_not_halt():
    # Dialogue 8 finished with 2 queued out of 190 and that was worth continuing
    # from; a handful is a known HydraDB behaviour, not an incident.
    assert halt_reason([_run("8", stragglers=2)], 5) is None


def test_one_dialogue_queuing_heavily_halts():
    reason = halt_reason([_run("7", stragglers=54)], 5)
    assert reason is not None
    assert "54 sources queued" in reason


def test_stragglers_across_independent_dialogues_halt():
    reason = halt_reason([_run("1", stragglers=1), _run("2", stragglers=1)], 5)
    assert reason is not None
    assert "independent dialogues" in reason
    assert "1, 2" in reason


def test_a_failed_dialogue_halts_immediately():
    reason = halt_reason([_run("1"), _run("2", error="TimeoutError: boom")], 5)
    assert reason is not None
    assert "dialogue 2 failed" in reason


def test_the_halt_names_the_most_recent_problem_first():
    """A dialogue that just blew the per-dialogue limit should be reported as
    that, not as the vaguer cross-dialogue condition."""
    runs = [_run("1", stragglers=1), _run("2", stragglers=99)]
    assert "99 sources queued" in halt_reason(runs, 5)
