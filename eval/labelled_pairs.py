"""Hand-labelled reconciliation pairs — the classifier's known error rate.

§14 of the build spec: "Hand-label 20 pairs. Report classifier accuracy in the
README — a known error rate beats a hidden one." This is that set, kept in one
place so the test suite and the reported number cannot drift apart.

Honesty notes, because they change how the number should be read:

- These pairs are synthetic and hand-labelled by the author, not drawn from BEAM
  ground truth. They measure whether the classifier applies *our* taxonomy the
  way we defined it, not whether the taxonomy is right.
- Some pairs are marked ``deterministic``: production never sends them to the
  LLM at all, because ``reconcile_fact`` short-circuits an identical object value
  to DUPLICATE before any model call. Counting them as classifier wins would
  inflate the number, so the report gives accuracy both with and without them.
- The SUPERSESSION / CONTRADICTION boundary is the genuinely hard one and is
  where we expect most of the error. Pairs marked ``hard`` are there on purpose;
  removing them to raise the score would be the wrong move.
"""

from dataclasses import dataclass, field

from palimpsest.models import Fact


def _fact(session_idx: int, subject: str, predicate: str, obj: str, span: str, ts: str = "") -> Fact:
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


@dataclass(frozen=True)
class LabelledPair:
    prior: Fact
    candidate: Fact
    expected: str
    note: str = ""
    deterministic: bool = False
    hard: bool = field(default=False)

    @property
    def label(self) -> str:
        return f"{self.prior.predicate} {self.prior.object!r} -> {self.candidate.object!r}"


PAIRS: list[LabelledPair] = [
    # --- REFINEMENT: strictly more specific, not contradictory -------------
    LabelledPair(
        _fact(1, "user", "LIVES_IN", "india", "I live in India"),
        _fact(2, "user", "LIVES_IN", "coimbatore, india", "I live in Coimbatore, India"),
        "REFINEMENT",
    ),
    LabelledPair(
        _fact(1, "user", "REPORTS_TO", "a manager", "I report to a manager on the platform team"),
        _fact(4, "user", "REPORTS_TO", "priya raghavan", "My manager is Priya Raghavan"),
        "REFINEMENT",
        note="unnamed -> named, same referent",
    ),
    LabelledPair(
        _fact(1, "user", "HAS_DEADLINE", "sometime in march", "the deadline is sometime in March"),
        _fact(2, "user", "HAS_DEADLINE", "march 15 2024", "the deadline is March 15, 2024"),
        "REFINEMENT",
    ),
    LabelledPair(
        _fact(1, "user", "USES_TOOL", "a python linter", "I use a Python linter"),
        _fact(3, "user", "USES_TOOL", "ruff", "I use Ruff for linting"),
        "REFINEMENT",
    ),
    # --- SUPERSESSION: different value, clear temporal replacement ---------
    LabelledPair(
        _fact(1, "user", "REPORTS_TO", "marcus webb", "My manager is Marcus Webb"),
        _fact(5, "user", "REPORTS_TO", "priya raghavan", "My new manager is Priya Raghavan now"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(1, "user", "WORKS_AT", "acme corp", "I work at Acme Corp"),
        _fact(9, "user", "WORKS_AT", "globex inc", "I just started a new job at Globex Inc"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(1, "user", "HAS_DEADLINE", "march 15 2024", "my deadline is March 15, 2024"),
        _fact(3, "user", "HAS_DEADLINE", "march 22 2024", "the deadline got pushed to March 22, 2024"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(2, "user", "LIVES_IN", "chennai", "I live in Chennai"),
        _fact(8, "user", "LIVES_IN", "bangalore", "I moved to Bangalore last month"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(1, "user", "USES_TOOL", "jenkins", "our CI runs on Jenkins"),
        _fact(6, "user", "USES_TOOL", "github actions", "we migrated CI to GitHub Actions"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(1, "user", "OWNS", "a honda civic", "I drive a Honda Civic"),
        _fact(7, "user", "OWNS", "a toyota prius", "I sold the Civic and bought a Prius"),
        "SUPERSESSION",
    ),
    LabelledPair(
        _fact(1, "user", "SCHEDULED_FOR", "monday standup", "standup is Monday"),
        _fact(4, "user", "SCHEDULED_FOR", "wednesday standup", "we've shifted standup to Wednesdays"),
        "SUPERSESSION",
    ),
    # --- DUPLICATE ---------------------------------------------------------
    LabelledPair(
        _fact(1, "user", "LIVES_IN", "chennai", "I live in Chennai"),
        _fact(2, "user", "LIVES_IN", "chennai", "I live in Chennai"),
        "DUPLICATE",
        note="identical object; reconcile_fact resolves this without an LLM call",
        deterministic=True,
    ),
    LabelledPair(
        _fact(1, "user", "WORKS_AT", "acme corp", "I work at Acme Corp"),
        _fact(3, "user", "WORKS_AT", "acme corporation", "I'm at Acme Corporation"),
        "DUPLICATE",
        note="paraphrase of the same value — does reach the classifier",
    ),
    LabelledPair(
        _fact(1, "user", "PREFERS", "dark mode", "I prefer dark mode"),
        _fact(5, "user", "PREFERS", "dark theme", "I like dark theme in every editor"),
        "DUPLICATE",
    ),
    # --- CONTRADICTION: incompatible, no clear temporal ordering -----------
    LabelledPair(
        _fact(1, "user", "PREFERS", "tea", "I prefer tea over coffee"),
        _fact(2, "user", "PREFERS", "coffee", "Actually I prefer coffee, always have"),
        "CONTRADICTION",
        note='"always have" denies that the old value was ever true',
        hard=True,
    ),
    LabelledPair(
        _fact(1, "user", "LIVES_IN", "berlin", "I live in Berlin"),
        _fact(2, "user", "LIVES_IN", "munich", "I live in Munich"),
        "CONTRADICTION",
        note="no move mentioned, no temporal signal either way",
        hard=True,
    ),
    LabelledPair(
        _fact(1, "user", "DISLIKES", "remote work", "I don't like working remotely"),
        _fact(3, "user", "DISLIKES", "the office", "I can't stand being in the office"),
        "CONTRADICTION",
        note="both stated as durable dispositions, mutually implausible",
        hard=True,
    ),
    LabelledPair(
        _fact(1, "user", "ATTENDED", "the berlin conference", "I was at the Berlin conference"),
        _fact(2, "user", "ATTENDED", "the tokyo conference", "I was at the Tokyo conference"),
        "CONTRADICTION",
        note="same slot, but attending two events is not actually exclusive — a known "
        "weakness of a single-value-per-slot model",
        hard=True,
    ),
    # --- Cases that should NOT be treated as replacements ------------------
    LabelledPair(
        _fact(1, "user", "HAS_DEADLINE", "march 15 2024", "the Q1 deadline is March 15"),
        _fact(2, "user", "HAS_DEADLINE", "march 15 2024", "March 15 is when Q1 is due"),
        "DUPLICATE",
        note="restatement, same date",
        deterministic=True,
    ),
    LabelledPair(
        _fact(1, "user", "REPORTS_TO", "priya raghavan", "Priya is my manager"),
        _fact(6, "user", "REPORTS_TO", "priya raghavan", "I still report to Priya"),
        "DUPLICATE",
        note='"still" explicitly reaffirms rather than replaces',
        deterministic=True,
    ),
]
