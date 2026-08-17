"""The 5-way reconciliation classifier. Highest-leverage component in the project.

For each candidate fact, compare against prior facts on the same (subject, predicate)
slot (from the SQLite ledger) and classify into exactly one bucket: NEW, DUPLICATE,
REFINEMENT, SUPERSESSION, CONTRADICTION.
"""

import sqlite3

from palimpsest import config, llm
from palimpsest.ledger import facts_for_slot
from palimpsest.models import Fact, ReconcileDecision

RECONCILE_SYSTEM = """You classify how a NEW candidate fact relates to a PRIOR fact that \
occupies the same (subject, predicate) memory slot. Choose exactly one label:

- DUPLICATE: same value as the prior fact (allowing paraphrase/case/whitespace differences).
- REFINEMENT: the new value is strictly MORE SPECIFIC than the prior value, and does not
  contradict it (e.g. "India" -> "Coimbatore, India"; "a manager" -> "Priya Raghavan").
- SUPERSESSION: the new value is DIFFERENT from the prior value, and there is a clear
  temporal signal (explicit or implied by chronological order + subject matter) that the
  new value replaces the old one (e.g. new job, new manager, moved city, changed tool).
- CONTRADICTION: the new value is incompatible with the prior value but there is NO clear
  signal that one supersedes the other in time — they read like a genuine conflict.
- NEW: use this only if you conclude the two facts do NOT actually share a slot (should be
  rare since both are pre-filtered to the same subject+predicate).

Return ONLY a JSON object: {"label": "...", "reason": "<one sentence>"}.
"""


def _prompt(prior: Fact, candidate: Fact) -> str:
    return (
        f"PRIOR fact (session {prior.session_idx}, ts={prior.session_ts}): "
        f"{prior.subject} {prior.predicate} {prior.object!r} "
        f"(source: {prior.source_span!r})\n\n"
        f"NEW candidate (session {candidate.session_idx}, ts={candidate.session_ts}): "
        f"{candidate.subject} {candidate.predicate} {candidate.object!r} "
        f"(source: {candidate.source_span!r})\n"
    )


def classify_pair(prior: Fact, candidate: Fact, model: str = config.CHEAP_MODEL) -> tuple[str, str]:
    data = llm.complete_json(prompt=_prompt(prior, candidate), system=RECONCILE_SYSTEM, model=model)
    label = data.get("label", "CONTRADICTION")
    valid = {"NEW", "DUPLICATE", "REFINEMENT", "SUPERSESSION", "CONTRADICTION"}
    if label not in valid:
        label = "CONTRADICTION"
    return label, data.get("reason", "")


def reconcile_fact(conn: sqlite3.Connection, candidate: Fact) -> ReconcileDecision:
    """Compare candidate against the most recent current fact on the same slot."""
    priors = facts_for_slot(conn, candidate.dialogue_id, candidate.subject, candidate.predicate, status="current")
    if not priors:
        return ReconcileDecision(label="NEW", candidate=candidate, prior_fact_id=None, reason="no prior fact on this slot")

    prior = priors[-1]  # most recent current fact
    if prior.object == candidate.object:
        return ReconcileDecision(label="DUPLICATE", candidate=candidate, prior_fact_id=prior.id, reason="identical object value")

    label, reason = classify_pair(prior, candidate)
    if label == "NEW":
        return ReconcileDecision(label="NEW", candidate=candidate, prior_fact_id=None, reason=reason)
    return ReconcileDecision(label=label, candidate=candidate, prior_fact_id=prior.id, reason=reason)
