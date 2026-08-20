# Next steps — the finish runbook

**Deadline:** Aug 20, 2026, 11:59 PM PT = **Aug 21, 12:29 PM IST**.
Three deliverables, all due together: Google Form, public licensed repo, demo video ≤ 3:00.

**Feature freeze is in effect.** Everything below is running, measuring, and shipping.
No new code. If something is broken, fix it; do not extend it.

Work top to bottom. Each step says what to check and what to do when it fails.

---

## STATUS — Steps 0-8 executed 2026-08-19

**Steps 0 through 6 are done and pushed** (commit `15b8df5`). Step 7 was declined
deliberately. What remains is the video and the Google Form.

- **Step 0** — clean tree, `uv sync`, tests pass.
- **Step 1** — `status` clean, the 2 known `hydra_pending` rows untouched.
  `verify 8` proves the current-view contract. **Its BYOG line now prints empty** —
  see the finding below; this is expected, not a new failure.
- **Step 2** — arm B provisioned, 5 sources each for dialogues 7 and 8. **It needed a
  workaround**, see below.
- **Steps 3-4** — smoke clean, then the full sweep: 120 arm-runs, **0 errored**, $6.69.
- **Step 5** — all four tables generated, committed, pushed.
- **Step 6** — classifier at 88% over the 17 pairs that reach it, 90% of 20.
- **Step 7** — **declined.** Dialogues 1-6 are already ingested (the step below is
  stale on that point); extending would cost ~$27 in arm-A input alone the day before
  the deadline, and would not change the conclusion, which is structural rather than a
  sampling artefact.
- **Step 8** — clean clone verified: 46 passed, 20 skipped. Video and Form outstanding.

Total spend ~$11 of the $45 cap.

### The headline result goes against the thesis

A (stuffing) **0.46**, B (HydraDB default) **0.34**, C (PALIMPSEST) **0.31**. C's
deficit is over-abstention, not wrong answers: it abstains on 56% of answerable
questions, scoring 0.41 when it answers and 0.03 when it abstains. The ablations agree
— switching the abstention gate off scores *higher* than leaving it on. Full reading
in the README under "What the results actually show". This is reported as measured;
do not retune an arm now and re-run.

### Two findings that changed the docs

**BYOG edges cannot be read back.** `context.relations()` returns zero relations for
every arm-C source, on every read shape tried, while the same call against the
`infer=True` arm-B database returns 21 and 16. The ingest reports neither a relation
count nor an error, so `graph_payload` is silently ignored on `infer=False` ingests.
Reproduced on a throwaway collection, so it is not corpus damage. **Not fixed** — the
fix is a re-ingest, which freeze and the queue-exposure rule both forbid. Claim 1 is
unaffected: it rests on `status` metadata filtering, which works, and `verify` still
proves it.

**Arm B provisioning fails silently at the default batch size.** `setup-arm-b` sends
all 5 sessions in one request; that exceeds the 30s request timeout for an
`infer=True` ingest, and the timeout is recorded as "queued" even though the sources
were never created (`context.status` returns `FILE_NOT_FOUND`). If you ever re-run it,
use env vars only — no code change:

```bash
PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120 \
  uv run palimpsest setup-arm-b <ids>
```

Verify with a source count, never with the command's own "queued" line.

---

## Step 0 — get this code onto your machine

```bash
cd /path/to/palimpsest
git status                 # commit or stash anything local first
git pull origin master
uv sync
uv run pytest -q           # expect: 46 passed, 20 skipped
```

The 20 skips are the hand-labelled classifier pairs; they need `LLM_API_KEY` and are
scored in Step 6, not here.

**If `git pull` conflicts:** your local `master` has commits that were never pushed.
`git stash`, pull, then `git stash pop` and resolve. Do not force anything.

---

## Step 1 — preflight, costs nothing

```bash
uv run palimpsest status
```

Expect dialogues 7 and 8 with their current/historical counts and **no rows in
`hydra_pending`**. The two dialogue-8 facts that were previously queued were resumed
from the outbox and now report `completed`; no recovery aliases were needed.

```bash
uv run palimpsest verify 8
```

Re-proves the current-view contract live: superseded fact absent under
`metadata_filters={"status":"current"}`, replacement present, BYOG edge printed. This is
the §15 exit gate and the centrepiece of the demo.

**If `verify` fails:** HydraDB is unhealthy or the metadata flip regressed. Stop and
diagnose before spending anything — every arm-C number depends on this holding.

---

## Step 2 — provision arm B (required, one time)

Arm B is HydraDB's own auto-extraction (`infer=True`) with no reconciliation. **B vs C is
the load-bearing comparison** — it isolates what PALIMPSEST adds over the vendor default
rather than over no memory system at all. Without it the main table proves much less.

It lives in a **separate database** (`palimpsest_arm_b`) so the server's own extraction
cannot contaminate arm C's corpus. **Done on 2026-08-19** — the database exists and
holds 5 sources for each of dialogues 7 and 8. Re-run this only for a new dialogue.

```bash
PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120 \
  uv run palimpsest setup-arm-b 7 8
```

The env vars are not optional. At the default batch size all 5 sessions go in one
request, which exceeds the 30s request timeout for an `infer=True` ingest; the timeout
is caught and the IDs are reported as "queued" even though **the sources were never
created at all**. Sent one at a time they are accepted immediately.

Expect: database ready, then per dialogue a source count. **Trust the source count, not
the queued line** — a run that prints "5 sources still queued / 0 sources in arm B"
created nothing, whatever the wording suggests. Confirm independently:

```bash
uv run python -c "
import asyncio; from eval.run_eval import missing_arm_b_dialogues
print('missing:', asyncio.run(missing_arm_b_dialogues(['7','8'])))"
```

**If many sources queue:** this is a fresh `infer=True` ingest and carries the same queue
exposure as any ingest. Stop after dialogue 7, check, then do 8 separately.

**If HydraDB refuses to create the database:** you can still run everything else with
`--arms A,C` plus the ablations. Say so in the README rather than shipping a silently
empty arm B.

---

## Step 3 — smoke the harness before spending

```bash
uv run python -m eval.run_eval --dialogues 7,8 --limit-per-category 1 --arms C
```

Smallest possible live check. Watch for rows appearing **during** the run:

```bash
wc -l results/raw_eval.jsonl      # in a second terminal; should grow steadily
```

Then widen slightly:

```bash
make eval-smoke                   # one question per category, arms A/B/C
make report
cat results/main_table.md
```

The run prints a spend forecast before starting. **Read the arm-A line** — arm A stuffs
the whole transcript into every question and dominates the bill. Check it against your
remaining budget before Step 4.

**If arm B errors on every question:** Step 2 did not take. Re-run it, or drop to
`--arms A,C`.

**If more rows error than score:** stop. HydraDB is unhealthy; do not spend more.

---

## Step 4 — the full sweep

```bash
uv run python -m eval.run_eval --dialogues 7,8
```

All six arms: A, B, C, and C's three ablations. Safe to interrupt with Ctrl-C and
re-run — it resumes, skipping what succeeded and retrying only what errored.

Useful variations:

```bash
# HydraDB flaky? A needs no HydraDB, and C's ablations reuse the ingested corpus.
uv run python -m eval.run_eval --dialogues 7,8 --arms A,C,C_no_status_filter,C_no_coverage,C_neither

# Reads timing out? Tighten the per-question bound so failures are cheap.
PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS=60 uv run python -m eval.run_eval --dialogues 7,8

# Rate limited? Lower concurrency.
PALIMPSEST_EVAL_CONCURRENCY=2 uv run python -m eval.run_eval --dialogues 7,8
```

**If the spend cap trips:** the run stops cleanly and keeps every checkpointed result. Go
to Step 5 with what you have, or raise `PALIMPSEST_MAX_SPEND_USD` and re-run to resume.

---

## Step 5 — generate and commit the tables ⭐

This is the step that turns work into a submission. Do not skip it or leave it for later.

```bash
make report
```

Writes `results/main_table.md`, `results/ablation.md`, `results/cost_latency.md`, and
`results/classifier_accuracy.md`. Every table prints its own coverage line, so a partial
run reports as partial.

```bash
git add results NEXT_STEPS.md
git commit -m "Add evaluation results over dialogues 7-8"
git push origin master
```

**An empty `results/` directory reads as an unfinished project.** Commit whatever you
have, even a smoke run. Partial and honest beats nothing — the build spec's own risk
register says so.

---

## Step 6 — the classifier's error rate (15 minutes, high credibility)

```bash
uv run palimpsest classifier-accuracy
cat results/classifier_accuracy.md
```

Scores the 5-way classifier over the 20 hand-labelled pairs in
`eval/labelled_pairs.py`. §14 of the build spec asks for this explicitly: a known error
rate beats a hidden one. `make report` runs it too, so Step 5 may already have.

Read the output before shipping it. If accuracy is poor on the
SUPERSESSION/CONTRADICTION pairs, **say that in the README** — do not relabel the pairs
to raise the number.

---

## Step 7 — optional: grow the ingested subset — DECLINED, and stale as written

**Superseded by what was found on 2026-08-19: dialogues 1–6 are already ingested.**
`palimpsest status` reports current/historical counts for all eight (d1 72/20, d2
72/26, d3 63/26, d4 31/20, d5 36/29, d6 116/61, d7 144/66, d8 135/55). What 1–6
actually lack is an arm-B corpus and eval coverage, not ingestion — so the
`ingest-all` sequence below is not the work that was left.

Extending the *evaluation* to them was considered and declined: ~$27 in arm-A input
tokens alone against a $45 cap with ~$11 spent, on the eve of the deadline, to sharpen
per-category cells without changing a conclusion that is structural. The tables
disclose their own 2-dialogue coverage. Kept below for reference only.

```bash
uv run palimpsest ingest-all 1 2 3 4 5 6 --dry-run   # session counts + state, free
uv run palimpsest ingest-all 1 2                     # a PAIR at a time, never all six
uv run palimpsest verify 1                           # supersession really happened
uv run palimpsest setup-arm-b 1 2                    # arm B needs each new dialogue too
uv run python -m eval.run_eval --dialogues 7,8,1,2   # resumes; new dialogues add rows
make report && git add results && git commit -m "Extend results to dialogues 1-2" && git push
```

`ingest-all` halts on the documented stop conditions: one dialogue queuing more than
`--max-stragglers` (default 5), a second dialogue queuing anything at all, a raised
error, or the spend cap. On a halt, reconciled facts stay committed and queued IDs stay
in the outbox — re-running resumes.

**Stop growing the moment either budget or clock gets tight.** Dialogue count is a
footnote every table already discloses. A missing video is a disqualifier.

---

## Step 8 — ship

```bash
uv run pytest -q                  # 46 passed, 20 skipped
git status                        # clean; results/ committed
```

Clean-clone check — a §13.1 disqualifier, so do it even though it passed in CI-like
conditions already:

```bash
cd /tmp && rm -rf clone-test
git clone https://github.com/rabbive/palimpsest.git clone-test
cd clone-test && uv sync && uv run pytest -q
```

Demo sequence for the video (§13.3 order, ≤ 3:00 — record in the morning, not at night):

```bash
make demo          # status -> timeline 8 -> verify 8
uv run palimpsest ask 8 "What is my current manager?"     # structured abstention
cat results/main_table.md results/ablation.md
```

- `timeline 8` — superseded facts struck through. The palimpsest, visible. Widen the
  terminal first; at 80 columns the object and edge columns truncate.
- `verify 8` — superseded fact absent from the current view, replacement present.
  Claim 1, proved on camera. **The BYOG relations line prints empty** — say so out
  loud and name it as a measured finding rather than editing around it; the README
  documents why it is server-side. A defect you found and diagnosed reads as rigour.
- `ask` on a missing slot — a structured abstention naming the slot. Claim 2.
  Verified working: returns `missing_slots: ['user / MANAGES']`.
- Consider showing `cost_latency.md` too: arm C answers at $0.0449 a question against
  arm A's $0.3107. It is the one column where C wins outright.

Final checklist:

- [ ] Video ≤ 3:00, uploaded, link opens in a logged-out incognito window
- [x] `results/*.md` committed and pushed — commit `15b8df5`
- [x] README limitations match what actually happened — dialogue count, queued facts,
      classifier error rate, the BYOG edge, and the headline result all updated
- [ ] Google Form submitted — **mid-morning IST, not at the buzzer**

---

## Troubleshooting

| Symptom | Action |
|---|---|
| Arm B errors on every question | Step 2 did not take. Re-run `setup-arm-b`, or use `--arms A,C,...` |
| Eval produces mostly errored rows | HydraDB unhealthy. Stop, check `verify`, do not keep spending |
| Read timeouts | Lower `PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS`; failures get cheap, run continues |
| Rate limits / 429s | `PALIMPSEST_EVAL_CONCURRENCY=2` |
| Spend cap tripped | Results are kept. Report on them, or raise the cap and re-run to resume |
| A dialogue leaves many sources queued | `ingest-all` already halted. See `docs/INGESTION_OPERATIONS.md`; do not force |
| `results/raw_eval.jsonl` looks wrong | Never delete it — it is the checkpoint, and deleting re-buys every completed question |
| Interrupted run | Just re-run the same command. It resumes |

## Hard rules

- Never delete `results/raw_eval.jsonl` to "start clean".
- Never pass `--ingest` to the evaluation for dialogues 7 or 8; they are already ingested.
- Never delete or alias `f_8_0001_000` / `f_8_0003_022` without explicit review.
- Never delete remote memories to recover from an indexing incident.
- Add dialogues in pairs through `ingest-all`, never all at once.

## Already done

- **P0** live state stabilized: 210 dialogue-7 facts, 16 recovered under deterministic aliases.
- **P1** dialogue 8 ingested independently: 190 facts, 188 indexed, 2 queued and reviewed.
- **P2** write/read contract validated — now re-runnable as `palimpsest verify`.
- **Harness** made resumable and bounded; ablation arms, cost/latency, and the three
  report tables added; arm B made provisionable; ingestion stop conditions enforced in
  code; clean clone verified. See `PROJECT_STATUS.md` for the full change list.
