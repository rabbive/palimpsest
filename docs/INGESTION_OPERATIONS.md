# Ingestion operations and HydraDB queue recovery

## Symptoms observed

HydraDB can return an accepted ingestion while individual source IDs remain `queued`. In the dialogue-7 incident, most sources completed but a subset stayed queued for more than ten minutes. `context.status` continued to return `queued`; this was not a local CPU or LLM deadlock.

Root-cause probe: re-upserting an original queued ID was accepted but did not reset its queue state. Fresh diagnostic IDs with the same text and BYOG payload completed. Therefore the fact payload is valid and the persistent failure is stale HydraDB queue state keyed by the original IDs. Also, `graph_creation` is an intermediate status and must not be treated as terminal success.

A source that remains queued is not safe to expose through the materialized current view. Its local fact may exist in SQLite, but HydraDB metadata is not considered complete until indexing succeeds.

## Current safeguards

The write path now:

1. Extracts/reconciles and commits facts plus `hydra_pending` rows locally.
2. Ingests HydraDB in batches (`8` by default).
3. Polls each batch with a bounded timeout (`20s` by default).
4. Moves on when a batch is queued instead of blocking later batches.
5. Re-ingests only queued IDs with `upsert=true`, using bounded request timeouts and exponential backoff.
6. Applies `status=current` or `status=historical` only to known-indexed sources.
7. Clears completed IDs from `hydra_pending`; retains persistent stragglers for the next run.

Relevant implementation: `src/palimpsest/hydra.py`, `src/palimpsest/ledger.py`, `src/palimpsest/write_path.py`.

## Safe status checks

Check local state without modifying it:

```bash
./.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("file:results/ledger.sqlite3?mode=ro", uri=True)
print("facts:", c.execute(
    "select dialogue_id,count(*) from facts group by dialogue_id order by dialogue_id"
).fetchall())
print("pending:", c.execute(
    "select dialogue_id,count(*),max(attempts) from hydra_pending group by dialogue_id"
).fetchall())
PY
```

Check HydraDB collection totals:

```bash
./.venv/bin/python - <<'PY'
import asyncio
from hydra_db import AsyncHydraDB
from palimpsest import config

async def main():
    client = AsyncHydraDB(
        token=config.HYDRADB_API_KEY,
        api_version="2",
        timeout=config.HYDRA_REQUEST_TIMEOUT_SECONDS,
    )
    for collection in ("7", "8"):
        result = await client.context.list(
            database=config.HYDRADB_DATABASE,
            collection=collection,
            type="memory",
            page=1,
            page_size=1,
        )
        print(collection, result.data.total)

asyncio.run(main())
PY
```

For pending IDs, use `context.status(database=..., collection=..., ids=[...])`. Never print the API key or presigned URLs into a log.

## Retry procedure

Retry the outbox only; do not immediately rerun every dialogue:

```bash
PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=10 \
PALIMPSEST_HYDRA_BATCH_TIMEOUT_SECONDS=5 \
PALIMPSEST_HYDRA_QUEUE_RETRIES=1 \
PALIMPSEST_HYDRA_QUEUE_RETRY_BACKOFF_SECONDS=1 \
./.venv/bin/python - <<'PY'
import asyncio
from palimpsest.write_path import _retry_pending

stats = {}
asyncio.run(_retry_pending("7", stats))
print(stats)
PY
```

If the same IDs remain queued after one or two bounded retries, do not spend another ten minutes polling them. Dialogue 7 demonstrated that even approved deletion plus same-ID re-ingestion may preserve stale HydraDB queue state. Its 16 affected facts use deterministic `r1_<canonical_id>` recovery aliases stored in `hydra_source_aliases`. Any future alias recovery must preserve a permanent canonical-to-source mapping and requires explicit review; do not generate random IDs.

After recovery, verify:

- `hydra_pending` count decreases;
- each recovered ID reports `completed`/`indexed`;
- `metadata_filters={"status":"current"}` returns expected current facts;
- superseded facts have `status=historical`.

## Running the next dialogue

Run dialogue 8 separately so a queue problem in dialogue 7 cannot hide its progress:

```bash
./.venv/bin/palimpsest ingest 8
```

Dialogue 8 is LLM-heavy and was previously stopped during extraction/reconciliation. The LLM wrapper now has a provider timeout. Keep the disk cache intact; reruns reuse completed extraction/classification calls.

Only after 7/8 are independently checked should the full evaluation run:

```bash
make eval
make report
```

## Do not do

- Do not delete queued remote sources as a first response or without explicit approval.
- Do not manually delete `results/ledger.sqlite3-journal` while a worker may be alive.
- Do not mark queued facts `current` in HydraDB.
- Do not use a large all-dialogue ingest batch to "unstick" the queue.
- Do not treat a local SQLite commit as proof that HydraDB indexing finished.

## Evaluation runs

An evaluation is a read-heavy workload against the same database, and it failed twice
for harness reasons before it ever failed for data reasons. What changed:

- `eval/run_eval.py` appends each result to `results/raw_eval.jsonl` as it is produced.
  An interrupted run keeps everything it finished.
- Re-running skips rows already checkpointed and retries only rows that recorded an
  error, so a HydraDB `ReadTimeout` costs one question rather than a whole run.
- Each question is bounded by `PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS`.
- Read queries retry twice, not six times. The read path issues one query per coverage
  slot plus one for the answer; the write-side retry budget multiplied a single
  unresponsive endpoint into minutes per question.
- Ingestion is opt-in (`--ingest`, off by default), so evaluating an already-ingested
  dialogue cannot re-enter HydraDB's ingestion queue.

Safe sequence:

```bash
# smallest possible live check
uv run python -m eval.run_eval --dialogues 8 --limit-per-category 1 --arms C
# one question per category, across the three main arms
make eval-smoke
make report
# full sweep; safe to interrupt and rerun
uv run python -m eval.run_eval --dialogues 7,8
```

Watch `results/raw_eval.jsonl` grow while the run is live:

```bash
wc -l results/raw_eval.jsonl
grep -c '"error": null' results/raw_eval.jsonl
```

If errored rows outnumber scored ones, stop and check HydraDB health rather than
spending more budget. `eval/report.py` reads the JSONL checkpoint when
`results/raw_eval.json` is missing, so a stopped run still produces tables — each one
prints its own coverage line, including how many arm-runs errored.

### Do not

- Do not delete `results/raw_eval.jsonl` to "start clean": it is the checkpoint, and
  deleting it re-buys every completed question.
- Do not pass `--ingest` for dialogues 7 or 8. They are ingested, and two dialogue-8
  facts remain in `hydra_pending` pending explicit review.
