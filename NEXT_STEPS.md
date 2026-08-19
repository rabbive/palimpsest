# Next steps

Deadline: **Aug 20, 2026, 11:59 PM PT** (Aug 21, 12:29 PM IST). Three deliverables due
together: Google Form, public licensed repo, demo video ≤ 3:00.

## P0 — stabilize the live state — complete

- [x] Confirm no ingestion worker is running.
- [x] Diagnose dialogue-7's persistent queue state.
- [x] Recover 16 affected facts with deterministic source aliases after approved same-ID reset failed.
- [x] Verify 210 completed sources, 144 current / 66 historical, complete schema metadata, BYOG relations, and an end-to-end answer.

## P1 — ingest dialogue 8 independently — complete

- [x] Run `./.venv/bin/palimpsest ingest 8`, not `ingest-all 7 8`.
- [x] Keep `.cache/` so completed LLM calls are reused.
- [x] Watch both LLM request timeout behavior and the HydraDB queue counters.
- [x] If a few sources queue, allow the process to checkpoint and continue; do not discard the local ledger.

## P2 — validate the write/read contract — complete

- [x] Check local facts and `hydra_pending` counts.
- [x] Query HydraDB with `metadata_filters={"status":"current"}`.
- [x] Verify a superseded fact is absent from the current view and the replacement is present.
- [x] Verify `context.relations()` returns the expected BYOG replacement edge.
- [x] Verify one deliberate missing-slot question returns a structured abstention.

All three checks are now a single command: `uv run palimpsest verify 8`.

## P3a — grow the ingested subset from 2 dialogues to 8

`FROZEN_SUBSET` in `eval/beam_loader.py` names dialogues 1–8, but only **7 and 8 are
actually ingested**. Until 1–6 are in, the README's "8 of 20 dialogues" describes the
frozen subset rather than the evaluated one. Ingesting them makes the claim true and
roughly quadruples the evidence behind every table.

`ingest-all` now enforces the stop conditions below in code instead of describing them,
so this is safe to run unattended-ish. It halts and reports if:

- one dialogue leaves more than `--max-stragglers` (default 5) sources queued;
- a **second** dialogue queues anything at all — sources queuing across independent
  dialogues means the queue is unhealthy, not that one dialogue was unlucky;
- a dialogue raises;
- the spend cap is hit.

On a halt, everything already reconciled stays committed locally and queued IDs stay in
the outbox, so rerunning resumes rather than restarting.

- [ ] `uv run palimpsest ingest-all 1 2 3 4 5 6 --dry-run` — session counts, what is
      already ingested, what is already stuck. Costs nothing.
- [ ] `uv run palimpsest status` — confirm `hydra_pending` is what you expect first.
- [ ] Ingest in **pairs, not all six**: `uv run palimpsest ingest-all 1 2`, check, then
      `3 4`, then `5 6`. A halt then costs one pair, and you can evaluate after each.
- [ ] After each pair: `uv run palimpsest verify <id>` and `uv run palimpsest timeline <id>`
      to confirm supersession actually happened in that dialogue.
- [ ] Re-run `make eval` after each pair — it resumes, so new dialogues just add rows.

**Budget reality.** Dialogue 8 alone produced 190 facts from its sessions, and every
session is one extraction call plus one reconciliation call per candidate landing on an
occupied slot. Six dialogues is not a rounding error against the $45 cap. `ingest-all`
prints running spend and halts at the cap. If you run out of budget or clock, **stop and
evaluate what you have** — the spec's own risk register says partial with an explicit
"N of M dialogues" note beats nothing, and every generated table already prints its
coverage line.

**Order matters.** Ingest, then evaluate, then ingest more. Do not ingest all six and
then discover the eval harness has a problem with 4× the questions.

## P3b — evaluate — unblocked, not yet run

The first `make eval` was stopped at the 30-minute timeout without producing
`results/raw_eval.json`; a dialogue-8-only retry then hit repeated HydraDB query
`ReadTimeout`s before writing anything. Both failures were harness problems, and both
are fixed:

- results are appended to `results/raw_eval.jsonl` as each one lands, so an interrupted
  run keeps everything it finished;
- a rerun skips completed work and retries only errored rows;
- each question is bounded by `PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS` (120s);
- a failed question is recorded as a row with its error instead of killing the run;
- read queries retry twice rather than six times, so one dead endpoint costs seconds
  per question rather than minutes;
- questions run concurrently, each on its own event loop, because the LLM client is
  blocking and a shared loop serialized them regardless of the concurrency setting;
- `make eval` no longer re-runs the write path, so evaluating cannot re-enter HydraDB's
  ingestion queue.

**Arm B has never been provisioned.** It lives in its own database
(`palimpsest_arm_b`) because it ingests raw sessions with `infer=True`, and nothing had
ever created it — the only code path that populated it also re-ingested arm C, which the
runbook forbids for dialogues 7 and 8. That is now a standalone step, and an evaluation
including arm B refuses to start without it rather than burning arm A and arm C budget
on questions arm B cannot answer. Since B vs C is the load-bearing comparison, this is
not optional.

Run it in this order:

- [ ] `uv run palimpsest setup-arm-b 7 8` — creates the arm-B database and ingests its
      corpus. One time per dialogue; does not touch arm C.
- [ ] `uv run python -m eval.run_eval --dialogues 7,8 --limit-per-category 1 --arms C`
      — smallest possible live check that the harness produces rows.
- [ ] `make eval-smoke` — one question per category across A/B/C. Confirm
      `results/raw_eval.jsonl` grows during the run, not at the end.
- [ ] `make report` and read `results/main_table.md`. If the numbers are sane, continue.
- [ ] `uv run python -m eval.run_eval --dialogues 7,8` — the full sweep across all six
      arms. Safe to interrupt and rerun; it resumes.
- [ ] `make report`, then commit `results/*.md` and `results/raw_eval.jsonl` so the
      tables exist in the repo a judge clones.

The run prints a spend forecast before starting. Arm A stuffs the whole transcript into
every question, so it dominates the bill — check that line against your remaining budget
before committing to the full sweep. Hitting `PALIMPSEST_MAX_SPEND_USD` stops the run
cleanly and keeps every checkpointed result.

If HydraDB is unhealthy, run arms A and C only — A needs no HydraDB at all, and arm C's
ablations reuse the corpus already ingested. Partial and honest beats nothing; every
table prints its own coverage line.

**Do not** run the evaluation with `--ingest` against dialogues 7 or 8. They are already
ingested, and two dialogue-8 facts (`f_8_0001_000`, `f_8_0003_022`) remain in
`hydra_pending` after two bounded retries. Leave them; do not delete or alias them
without explicit review. Ingestion for new dialogues goes through `palimpsest ingest-all`,
which has the stop conditions; the evaluation's `--ingest` flag does not.

## P4 — ship hygiene

- [ ] Run `uv run pytest -q` from a clean environment.
- [ ] Clean-clone test: fresh directory, follow the README's own setup steps, confirm
      they work. `results/` is created lazily now, so a clone no longer fails on the
      ledger — verify that end to end anyway, since it is a §13.1 disqualifier.
- [ ] Commit `results/*.md` once real numbers exist. An empty results directory reads
      as an unfinished project.
- [ ] Complete the demo and submission checklist in `PALIMPSEST_BUILD_SPEC.md` §13.
- [ ] Record the video (§13.3 order, ≤ 3:00). The demo sequence is `make demo`:
      `status` → `timeline 8` (superseded facts struck through) → `verify 8` (the
      superseded fact absent from the current view, the replacement present, the BYOG
      edge printed) → `ask 8` on a missing slot for the structured abstention → the
      results tables.
- [ ] Verify the video link opens in a logged-out incognito window.
- [ ] Submit the form well before the buzzer.

## Stop conditions

Stop a live run and reassess if:

- a single HTTP call exceeds the configured timeout;
- the same source IDs remain queued after two bounded retry rounds;
- `hydra_pending` grows across independent dialogues;
- a process is gone but a SQLite journal remains — first open the DB through `ledger.connect()` to let SQLite recover it;
- an evaluation is producing errored rows faster than scored ones — check HydraDB
  health before spending more of the budget.
