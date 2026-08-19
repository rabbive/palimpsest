"""The ablation arms are read-path switches, so they must actually change the
request that goes to HydraDB — otherwise the ablation table measures nothing."""

import asyncio

import pytest

from palimpsest import read_path
from palimpsest.models import Abstention


class _Chunk:
    chunk_content = "user reports to priya raghavan."


class _Data:
    chunks = [_Chunk()]
    graph_context = None


class _Result:
    data = _Data()


@pytest.fixture
def spy(monkeypatch):
    calls = {"queries": [], "premise_checks": 0}

    async def fake_query(**kwargs):
        calls["queries"].append(kwargs)
        return _Result()

    async def fake_check_premise(dialogue_id, question, model=None):
        calls["premise_checks"] += 1
        return Abstention(missing_slots=["user / REPORTS_TO"], reason="nothing covers it")

    monkeypatch.setattr(read_path.hydra, "query", fake_query)
    monkeypatch.setattr(read_path, "check_premise", fake_check_premise)
    monkeypatch.setattr(read_path, "classify_intent", lambda question, model=None: "CURRENT")
    monkeypatch.setattr(read_path.llm, "complete", lambda **kwargs: "an answer")
    return calls


def test_full_arm_abstains_via_the_premise_check(spy):
    answer = asyncio.run(read_path.answer_question("7", "who is my manager?"))
    assert answer.abstention is not None
    assert spy["premise_checks"] == 1
    assert spy["queries"] == []  # abstained before retrieving


def test_coverage_off_skips_the_premise_check_and_answers(spy):
    answer = asyncio.run(read_path.answer_question("7", "who is my manager?", use_coverage=False))
    assert answer.abstention is None
    assert spy["premise_checks"] == 0
    assert answer.text == "an answer"


def test_status_filter_off_drops_the_current_view_filter(spy):
    asyncio.run(read_path.answer_question("7", "who is my manager?", use_coverage=False))
    assert spy["queries"][0]["metadata_filters"] == {"status": "current"}

    spy["queries"].clear()
    asyncio.run(
        read_path.answer_question("7", "who is my manager?", use_coverage=False, use_status_filter=False)
    )
    assert spy["queries"][0]["metadata_filters"] is None


def test_answers_carry_latency_and_cost(spy):
    answer = asyncio.run(read_path.answer_question("7", "who is my manager?", use_coverage=False))
    assert answer.latency_seconds > 0
    assert answer.cost_usd == 0.0  # the stubbed LLM spends nothing
