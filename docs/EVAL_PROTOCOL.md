# Evaluation protocol (pre-registered)

This file is written before any fix is measured. It fixes what counts as dev, what
counts as held-out, which fixes are allowed, and how the result is reported. It
exists so the final number cannot be tuned.

## Why a fix is being made

Arm C scored below arm B (0.31 vs 0.34) on dialogues 7 and 8, and the cause was
diagnosed on those dialogues: over-abstention. Arm C abstained on 56% of answerable
questions. The two structural causes found in the ledger and checkpoint:

- **Slot schema mismatch.** The coverage check filters HydraDB on
  `{"subject": entity, "predicate": predicate}`. Every stored fact has subject `user`
  (all 972 facts across dialogues 1-8). All 12 of arm C's abstentions on 7-8 named some
  other entity, so no stored fact could match. Predicates also disagree: 309 of 972
  facts are `OTHER`.
- **Missing time context.** Memory text has no session position, and arm C scored 0.12
  on event_ordering and 0.00 on temporal_reasoning on 7-8.

## Sets

- **Dev set:** dialogues 7 and 8. Arm C failed here and the failure was diagnosed
  here. Fixes may be measured on dev as often as needed, within budget.
- **Held-out set:** dialogues 1-6, priority categories only (abstention,
  contradiction_resolution, knowledge_update, temporal_reasoning, event_ordering),
  60 questions. Nobody has looked at their questions or answers.
- **Disclosure:** dialogues 1 and 2 were skimmed in the original build to derive
  `vocab.py`. That informed the write path's predicate vocabulary. It did not inform
  this read-path fix.

## Fixes allowed

1. The coverage schema alignment (Task 2).
2. Session-position context in answers (Task 3).
3. At most one further fix, if dev shows a new *structural* cause. It must be written
   into this file, with its diagnosis, before it is coded.

Prompt-wording or threshold changes made only to move a dev number are not allowed.

## Models

The proxy no longer serves gpt-5.4-mini or gpt-5.5. All new runs use `gpt-5.6` as both
the cheap model and the strong model. The judge is the cheap model, so every new row
shares one judge.

Consequences:

- The old dev rows for arms A and B are not comparable with new runs.
- On dev, arm B is re-run with gpt-5.6 alongside the C variants. New dev comparisons
  are B vs C variants, both on gpt-5.6.
- Arm A is excluded from new comparisons. Its old dev score, 0.46, is quoted only with
  the caveat that it was measured with different models and an earlier judge setup.

## Freeze

Tag `eval-freeze-v2` goes on the commit that will be measured on held-out. No code
changes are allowed between the tag and the held-out report. The tag is created
immediately before the held-out run, not earlier.

## Held-out arms

B, C, C_no_coverage, C_no_status_filter.

Arm A is excluded for budget (about $0.31 per question).

## Success criterion

On held-out, C overall > B overall.

Both abstention directions are reported: false abstentions on answerable questions, and
correct refusals on unanswerable ones. A reader must be able to see whether a win comes
from answering questions that C used to refuse or from refusing correctly.

## Reporting rule

The held-out result is published as measured, whatever it is. If C does not beat B, the
README says so. There is no second held-out run after a code change.

## Status

Live runs are currently blocked by HydraDB (HTTP 402, free plan deprecated). This
protocol takes effect whenever runs resume. Dev measurements may happen before then
only if a working HydraDB account is available. The freeze tag is created only
immediately before the held-out run.
