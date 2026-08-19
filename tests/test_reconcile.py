"""Hand-labelled pairs for the reconciliation classifier.

Requires LLM_API_KEY / LLM_API_BASE configured (uses the real classify_pair call,
disk-cached after the first run). Skipped automatically if no key is set.
"""

import os

import pytest

from eval.labelled_pairs import PAIRS
from palimpsest.reconcile import classify_pair

pytestmark = pytest.mark.skipif(
    not os.environ.get("LLM_API_KEY"),
    reason="LLM_API_KEY not set; reconciliation classifier needs a live LLM call",
)


@pytest.mark.parametrize("pair", PAIRS, ids=[p.label for p in PAIRS])
def test_classify_pair(pair):
    """One assertion per labelled pair.

    The reported accuracy over the same set lives in
    `palimpsest classifier-accuracy`, which writes
    results/classifier_accuracy.md. A pair failing here is a known error, not a
    reason to relabel the pair.
    """
    label, _reason = classify_pair(pair.prior, pair.candidate)
    assert label == pair.expected
