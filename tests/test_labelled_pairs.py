"""The labelled set and the reported accuracy over it.

§14 of the build spec asks for 20 hand-labelled pairs and a reported error rate.
These tests pin the set's shape and the honesty properties of the report — not
the classifier's score, which needs a live key and is what the report measures.
"""

from collections import Counter

import pytest
from typer.testing import CliRunner

from eval.labelled_pairs import PAIRS
from palimpsest import reconcile
from palimpsest.cli import app

runner = CliRunner()


def test_the_set_meets_the_specs_size():
    assert len(PAIRS) >= 20


def test_every_label_is_in_the_taxonomy():
    valid = {"NEW", "DUPLICATE", "REFINEMENT", "SUPERSESSION", "CONTRADICTION"}
    assert {p.expected for p in PAIRS} <= valid


def test_all_five_outcomes_that_can_occur_are_represented():
    """NEW is excluded on purpose: reconcile_fact returns it when no prior fact
    occupies the slot, so a *pair* can never legitimately be labelled NEW."""
    counts = Counter(p.expected for p in PAIRS)
    for label in ("DUPLICATE", "REFINEMENT", "SUPERSESSION", "CONTRADICTION"):
        assert counts[label] >= 3, f"{label} is thinly covered: {counts[label]}"


def test_deterministic_pairs_are_exactly_the_identical_value_ones():
    """reconcile_fact short-circuits on an identical object value. Any pair marked
    deterministic must genuinely be one of those, or the headline accuracy would
    exclude pairs that really do reach the classifier."""
    for pair in PAIRS:
        if pair.deterministic:
            assert pair.prior.object == pair.candidate.object
            assert pair.expected == "DUPLICATE"


def test_hard_pairs_exist_and_are_annotated():
    hard = [p for p in PAIRS if p.hard]
    assert len(hard) >= 3
    assert all(p.note for p in hard), "a pair marked hard should say why"


def test_report_excludes_deterministic_pairs_from_the_headline(tmp_path, monkeypatch):
    """A perfect classifier on a set containing short-circuited pairs must still
    report the two numbers separately, so the figure cannot be inflated by pairs
    the model never sees."""
    monkeypatch.setattr(reconcile, "classify_pair", lambda prior, candidate, **kw: (
        next(p.expected for p in PAIRS if p.prior.object == prior.object and p.candidate.object == candidate.object),
        "stub",
    ))

    out = tmp_path / "classifier_accuracy.md"
    result = runner.invoke(app, ["classifier-accuracy", "--out", str(out)])
    assert result.exit_code == 0, result.output

    body = out.read_text()
    judged = [p for p in PAIRS if not p.deterministic]
    assert "100%" in body
    assert f"over {len(judged)} hand-labelled pairs" in body
    assert f"all {len(PAIRS)} pairs" in body


def test_report_records_misses_in_a_confusion_table(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reconcile, "classify_pair", lambda prior, candidate, **kw: ("CONTRADICTION", "stub")
    )

    out = tmp_path / "classifier_accuracy.md"
    result = runner.invoke(app, ["classifier-accuracy", "--out", str(out)])
    assert result.exit_code == 0, result.output

    body = out.read_text()
    assert "Where it errs" in body
    assert "⟵ miss" in body
