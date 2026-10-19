import asyncio

import pytest

from palimpsest import coverage
from palimpsest.coverage import _normalize_entity


def test_normalize_first_person_entities_to_user():
    for entity in ("I", "me", "My", "myself", "the user"):
        assert _normalize_entity(entity) == "user"


def test_normalize_named_entity():
    assert _normalize_entity("  Priya Raghavan ") == "priya raghavan"


class _Chunk:
    def __init__(self, text):
        self.chunk_content = text


class _Data:
    def __init__(self, chunks):
        self.chunks = [_Chunk(t) for t in chunks]


class _Result:
    def __init__(self, chunks):
        self.data = _Data(chunks)


@pytest.fixture
def spy(monkeypatch):
    state = {
        "queries": [],
        "chunks": ["user has pet rex."],
        "verdict": {"covered": True},
        "verifier_calls": 0,
        "raise": None,
    }

    async def fake_query(**kwargs):
        state["queries"].append(kwargs)
        if state["raise"] is not None:
            raise state["raise"]
        return _Result(state["chunks"])

    def fake_complete_json(**kwargs):
        state["verifier_calls"] += 1
        return state["verdict"]

    monkeypatch.setattr(coverage.hydra, "query", fake_query)
    monkeypatch.setattr(coverage.llm, "complete_json", fake_complete_json)
    return state


def test_coverage_query_does_not_filter_on_subject_or_predicate(spy):
    asyncio.run(coverage.slot_has_coverage("8", "my zoom call with the creative director", "SCHEDULED_FOR"))
    assert spy["queries"][0]["metadata_filters"] is None
    assert "zoom call" in spy["queries"][0]["q"]


def test_slot_covered_when_verifier_says_a_fact_is_about_it(spy):
    spy["chunks"] = ["user other 30-minute zoom call between april 15-20."]
    spy["verdict"] = {"covered": True}
    covered, evidence = asyncio.run(
        coverage.slot_has_coverage("8", "my zoom call with the creative director", "SCHEDULED_FOR")
    )
    assert covered and evidence == spy["chunks"]


def test_slot_uncovered_when_verifier_says_no(spy):
    spy["chunks"] = ["user uses tool notion."]
    spy["verdict"] = {"covered": False}
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is False


def test_no_chunks_is_uncovered_without_an_llm_call(spy):
    spy["chunks"] = []
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is False
    assert spy["verifier_calls"] == 0


def test_malformed_verifier_output_fails_open(spy):
    spy["chunks"] = ["user has pet rex."]
    spy["verdict"] = "not json"
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is True


def test_hydra_timeout_propagates_instead_of_abstaining(spy, monkeypatch):
    monkeypatch.setattr(coverage, "decompose_question", lambda q, model=None: [{"entity": "my dog", "predicate": "HAS_PET"}])
    spy["raise"] = asyncio.TimeoutError()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(coverage.check_premise("8", "Do I have a dog?"))


def test_abstention_still_names_the_missing_slot(spy, monkeypatch):
    monkeypatch.setattr(coverage, "decompose_question", lambda q, model=None: [{"entity": "my dog", "predicate": "HAS_PET"}])
    spy["chunks"] = []
    ab = asyncio.run(coverage.check_premise("8", "What is my dog's name?"))
    assert ab.missing_slots == ["my dog / HAS_PET"]
