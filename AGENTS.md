# PALIMPSEST agent instructions

## Read first

1. `PALIMPSEST_BUILD_SPEC.md` — product thesis, HydraDB API contract, benchmark, and submission checklist.
2. `README.md` — architecture and project limitations.
3. `PROJECT_STATUS.md` — latest known runtime state; this is a snapshot, so refresh HydraDB status before acting.
4. `docs/INGESTION_OPERATIONS.md` — queue recovery and safe ingestion procedure.
5. `NEXT_STEPS.md` — ordered execution plan.

## Project mission

PALIMPSEST is a write-time reconciliation and abstention layer for HydraDB memory:

- Extract atomic user facts from BEAM sessions.
- Reconcile each fact as `NEW`, `DUPLICATE`, `REFINEMENT`, `SUPERSESSION`, or `CONTRADICTION`.
- Persist one HydraDB memory per fact with BYOG graph edges.
- Materialize `status=current|historical` metadata so current reads use HydraDB's hard metadata filter.
- Check graph coverage before answering and return structured abstentions when a required slot is absent.

Every answer path must use HydraDB retrieval; SQLite is only the write-time ledger/inspector mirror.

## Non-negotiable rules

- Never put secrets in source, markdown, logs, or commits. `.env` is local only.
- Do not invent HydraDB API parameters. Follow `PALIMPSEST_BUILD_SPEC.md` and the installed SDK.
- Do not delete remote memories to recover from an indexing incident without explicit approval.
- Use deterministic fact IDs and `upsert=true` for recovery.
- Do not rerun a whole dialogue blindly when `hydra_pending` contains queued facts. Retry the pending IDs first.
- Add dialogues through `palimpsest ingest-all`, a pair at a time. It enforces the stop conditions; `--force` disables them and is for supervised recovery only.
- Do not run the evaluation with `--ingest` against a dialogue that is already ingested. Evaluating must not re-enter HydraDB's ingestion queue.
- Do not delete `results/raw_eval.jsonl` to "start clean". It is the checkpoint; deleting it re-buys every completed question.
- Keep `infer=False`; extraction and reconciliation are ours.
- Run `./.venv/bin/pytest -q` after code changes.
- Before a long live run, check processes, local pending rows, HydraDB source counts, and the LLM cache.

## Write-path reliability

`src/palimpsest/hydra.py` now uses small-batch backpressure, bounded request timeouts, and retries only sources that remain queued. `src/palimpsest/ledger.py` stores an `hydra_pending` outbox. `src/palimpsest/write_path.py` checkpoints facts before remote calls and resumes pending IDs on the next run.

Reads are bounded separately from writes: a dropped write costs an extraction to redo, a dropped read costs one question, and the read path issues one query per coverage slot plus one for the answer. Six write-grade retry attempts on a read turned one unresponsive endpoint into minutes per question.

## Evaluation reliability

`eval/run_eval.py` appends each result to `results/raw_eval.jsonl` as it lands, resumes by skipping completed rows and retrying errored ones, bounds each question with its own timeout, and records a failure as a row rather than ending the run. `eval/report.py` reads that checkpoint when the final JSON is missing, so an interrupted run still reports what it finished.

Arm C's three ablations (`C_no_status_filter`, `C_no_coverage`, `C_neither`) are read-path switches over the corpus arm C already ingested — they cost queries, never a second write pass.

Important config knobs:

- `PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=30`
- `PALIMPSEST_HYDRA_BATCH_SIZE=8`
- `PALIMPSEST_HYDRA_BATCH_TIMEOUT_SECONDS=20`
- `PALIMPSEST_HYDRA_QUEUE_RETRIES=2`
- `PALIMPSEST_HYDRA_QUEUE_RETRY_BACKOFF_SECONDS=3`
- `PALIMPSEST_LLM_TIMEOUT_SECONDS=60`
- `PALIMPSEST_HYDRA_QUERY_ATTEMPTS=2`
- `PALIMPSEST_HYDRA_QUERY_TIMEOUT_SECONDS=20`
- `PALIMPSEST_EVAL_CONCURRENCY=4`
- `PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS=120`

Tune these through environment variables; do not hard-code provider-specific behavior.

## Useful commands

```bash
./.venv/bin/pytest -q
./.venv/bin/palimpsest status            # ledger counts + outbox, no network
./.venv/bin/palimpsest timeline 8        # inspector: superseded facts struck through
./.venv/bin/palimpsest verify 8          # re-prove the current-view contract live
./.venv/bin/palimpsest ingest 8
./.venv/bin/palimpsest ingest-all 1 2 --dry-run  # counts + current state, free
./.venv/bin/palimpsest ingest-all 1 2            # halts on the documented stop conditions
make eval-smoke                          # one question per category
make eval                                # resumable; safe to interrupt
make report
```

Use the recovery/status procedures in `docs/INGESTION_OPERATIONS.md` before `ingest-all`.
