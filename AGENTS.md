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
- Keep `infer=False`; extraction and reconciliation are ours.
- Run `./.venv/bin/pytest -q` after code changes.
- Before a long live run, check processes, local pending rows, HydraDB source counts, and the LLM cache.

## Write-path reliability

`src/palimpsest/hydra.py` now uses small-batch backpressure, bounded request timeouts, and retries only sources that remain queued. `src/palimpsest/ledger.py` stores an `hydra_pending` outbox. `src/palimpsest/write_path.py` checkpoints facts before remote calls and resumes pending IDs on the next run.

Important config knobs:

- `PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=30`
- `PALIMPSEST_HYDRA_BATCH_SIZE=8`
- `PALIMPSEST_HYDRA_BATCH_TIMEOUT_SECONDS=20`
- `PALIMPSEST_HYDRA_QUEUE_RETRIES=2`
- `PALIMPSEST_HYDRA_QUEUE_RETRY_BACKOFF_SECONDS=3`
- `PALIMPSEST_LLM_TIMEOUT_SECONDS=60`

Tune these through environment variables; do not hard-code provider-specific behavior.

## Useful commands

```bash
./.venv/bin/pytest -q
./.venv/bin/palimpsest ingest 8
./.venv/bin/palimpsest ingest-all 7 8
make eval
make report
```

Use the recovery/status procedures in `docs/INGESTION_OPERATIONS.md` before `ingest-all`.
