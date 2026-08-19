"""Cost has to be reported next to accuracy, and the budget cap has to bite."""

import pytest

from palimpsest import config, llm


@pytest.fixture(autouse=True)
def _clean_usage():
    llm.reset_usage()
    yield
    llm.reset_usage()


def test_scopes_nest_and_bill_every_open_scope():
    with llm.UsageScope() as outer:
        llm._record(config.STRONG_MODEL, 1000, 0)
        with llm.UsageScope() as inner:
            llm._record(config.STRONG_MODEL, 1000, 0)

    assert inner.cost_usd == pytest.approx(llm.price_of(config.STRONG_MODEL, 1000, 0))
    assert outer.cost_usd == pytest.approx(2 * inner.cost_usd)
    assert outer.calls == 2


def test_budget_cap_blocks_a_call_instead_of_overspending(monkeypatch):
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.001)
    llm._record(config.STRONG_MODEL, 10_000, 0)

    with pytest.raises(llm.BudgetExceeded):
        llm.complete(prompt="anything", use_cache=False)


def test_pre_metering_cache_entries_still_hit():
    """The disk cache holds hundreds of already-paid-for calls written before
    token accounting existed. Those entries are bare strings; rejecting them
    would silently re-buy every extraction."""
    assert llm._cached_content("plain string") == ("plain string", 0, 0)
    assert llm._cached_content({"content": "x", "input_tokens": 3, "output_tokens": 4}) == ("x", 3, 4)
    assert llm._cached_content({"unexpected": 1}) is None
