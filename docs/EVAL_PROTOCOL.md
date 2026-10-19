# Evaluation protocol (pre-registered)

This file is written before any fix is measured. It fixes what counts as dev, what
counts as held-out, which fixes are allowed, and how the result is reported. It
exists so the final number cannot be tuned.

This file is append-only after the commit that introduces this version. Git history is
the record. Amendments are new commits that add text. Nothing already written here is
edited or removed.

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
  here. Fixes may be measured on dev as often as needed, within budget and within the
  fix budget below.
- **Held-out set:** every question in the five priority categories (abstention,
  contradiction_resolution, knowledge_update, temporal_reasoning, event_ordering) of
  dialogues 1-6. BEAM has exactly 2 questions per category per dialogue, so this is 60
  questions. There is no sampling and no choice of which questions to include.
- **Scope of the result:** held-out covers only those five categories. The README must
  say so, so that "overall" is not read as a score on the whole benchmark.

## What was and was not seen (disclosure)

The held-out set is not untouched. Plainly:

- The diagnosis used aggregate ledger statistics across dialogues 1-8, such as the
  subject distribution and the share of `OTHER` predicates. It used no held-out
  questions and no held-out answers.
- `vocab.py` (the closed predicate vocabulary) was derived in the original build from
  skimming dialogues 1 and 2. The coverage fix aligns read-side slots with that
  write-side vocabulary, so it is partly shaped by dialogues 1 and 2. This is a
  limitation and is reported as one.

## Access to held-out

Nobody reads held-out questions, answers or scores before the freeze tag exists. No
held-out question is run before the tag.

The smoke run (`--limit-per-category 1`, its own checkpoint) happens only after the
tag, and only its error count is read. Its rows are never used for scoring.

## Fixes allowed

1. Coverage slot schema alignment: make the read-side coverage check match the
   write-side schema (subject is `user`, the thing asked about lives in the object,
   predicates fall back to `OTHER`).
2. Session-position context in answers: give the answerer each fact's session position
   so it can order and date facts.
3. At most one further fix, if dev shows a new *structural* cause. Its diagnosis must be
   committed to this file before the commit that contains the code.

The fix budget is these three slots. A slot is used by any change to read-path code,
prompts or thresholds that is measured on dev, whether or not it is listed above.
Prompt-wording or threshold changes made to move a dev number are not allowed.

## Models

All new runs use `gpt-5.6` as both the cheap model and the strong model, by user
instruction. The judge is the cheap model, so every new row shares one judge.

Limitation: the judge is the same model as the answerer (gpt-5.6). That carries a
self-preference risk. It applies equally to every arm, so it does not favor one arm
over another, but it is a limit on how far the absolute scores can be trusted.

Consequences:

- The old dev rows for arms A and B used different models and are not comparable with
  new runs.
- On dev, arm B is re-run with gpt-5.6 alongside the C variants. New dev comparisons
  are B vs C variants, both on gpt-5.6.
- Arm A is excluded from new comparisons. Its old dev score, 0.46, is quoted only with
  the caveat that it was measured with different models.

## Freeze

Tag `eval-freeze-v2` goes on the commit that will be measured on held-out. It is an
annotated tag. It is never moved or recreated. It is created immediately before the
held-out run, not earlier.

The tag freezes everything that can change a held-out score:

- all code and prompts under `src/` and `eval/`,
- model ids and judge settings in `.env`,
- the scorer and report logic,
- this protocol file.

After the tag, the corpus may change only by resync or recovery of facts already in the
ledger, and by arm B provisioning. No other change is allowed between the tag and the
held-out report. The tag SHA and the effective model settings are recorded in the
held-out run output.

## Held-out arms

B, C, C_no_coverage, C_no_status_filter.

Arm A is excluded for budget (about $0.31 per question).

## One run

Each held-out arm runs exactly once, at the tagged commit.

- Retrying errored rows at the same commit through the checkpoint is allowed.
- Re-running scored rows, partial reruns and per-arm reruns are not allowed.
- The raw checkpoint, `results/heldout.jsonl`, is committed as-is.

## Success criterion

"Overall" is the micro-mean over every scored held-out question for each arm. This is
what `eval/report.py` computes in its overall row.

C wins only if all of these hold:

- C overall > B overall,
- the margin is at least 0.05,
- there are 0 errored rows.

A margin under 0.05 is reported as "no clear difference", not as a win.

Both abstention directions are reported: false abstentions on answerable questions, and
correct refusals on unanswerable ones. A reader must be able to see whether a win comes
from answering questions that C used to refuse or from refusing correctly.

## Reporting rule

The held-out result is published as measured, whatever it is. If C does not beat B, the
README says so. There is no second held-out run after a code change.

## Status

Live runs are currently blocked by HydraDB (HTTP 402, free plan deprecated). This
protocol takes effect whenever runs resume. The freeze tag is created only immediately
before the held-out run.

Amendment (fixes): the session-position fix (fix 2) also applies to ORDERING context, which is now the `query_paths` lines followed by the session-prefixed chunk lines; decided before any dev measurement.

Amendment (success criterion): "0 errored rows" applies to every held-out arm that is compared (B, C, C_no_coverage, C_no_status_filter).
