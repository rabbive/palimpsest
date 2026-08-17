"""Hand-labelled pairs for the reconciliation classifier.

Requires LLM_API_KEY / LLM_API_BASE configured (uses the real classify_pair call,
disk-cached after the first run). Skipped automatically if no key is set.
"""

import os

import pytest

from palimpsest.models import Fact
from palimpsest.reconcile import classify_pair

pytestmark = pytest.mark.skipif(
    not os.environ.get("LLM_API_KEY"),
    reason="LLM_API_KEY not set; reconciliation classifier needs a live LLM call",
)


def _fact(session_idx, subject, predicate, obj, span, ts=""):
    return Fact(
        id=f"f_test_{session_idx}",
        dialogue_id="test",
        session_idx=session_idx,
        session_ts=ts,
        subject=subject,
        predicate=predicate,
        object=obj,
        source_span=span,
    )


CASES = [
    (
        _fact(1, "user", "LIVES_IN", "india", "I live in India"),
        _fact(2, "user", "LIVES_IN", "coimbatore, india", "I live in Coimbatore, India"),
        "REFINEMENT",
    ),
    (
        _fact(1, "user", "REPORTS_TO", "marcus webb", "My manager is Marcus Webb"),
        _fact(5, "user", "REPORTS_TO", "priya raghavan", "My new manager is Priya Raghavan now"),
        "SUPERSESSION",
    ),
    (
        _fact(1, "user", "LIVES_IN", "chennai", "I live in Chennai"),
        _fact(2, "user", "LIVES_IN", "chennai", "I live in Chennai"),
        "DUPLICATE",
    ),
    (
        _fact(1, "user", "PREFERS", "tea", "I prefer tea over coffee"),
        _fact(2, "user", "PREFERS", "coffee", "Actually I prefer coffee, always have"),
        "CONTRADICTION",
    ),
    (
        _fact(1, "user", "WORKS_AT", "acme corp", "I work at Acme Corp"),
        _fact(9, "user", "WORKS_AT", "globex inc", "I just started a new job at Globex Inc"),
        "SUPERSESSION",
    ),
    (
        _fact(1, "user", "HAS_DEADLINE", "march 15 2024", "my deadline is March 15, 2024"),
        _fact(3, "user", "HAS_DEADLINE", "march 22 2024", "the deadline got pushed to March 22, 2024"),
        "SUPERSESSION",
    ),
]


@pytest.mark.parametrize("prior,candidate,expected", CASES)
def test_classify_pair(prior, candidate, expected):
    label, _reason = classify_pair(prior, candidate)
    assert label == expected
