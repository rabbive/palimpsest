# PALIMPSEST runtime status

_Last checked: 2026-08-18 after dialogue-8 ingestion and contract validation. Refresh before relying on counts._
_Code updated 2026-08-19: the evaluation harness is resumable and the read path is bounded (see below)._

## Current runtime

- No `palimpsest ingest` process is running.
- The previous long-running command was aborted; it is not still active.
- HydraDB collection `7`: **210 completed/listed sources**.
- Dialogue 7 metadata: **144 current**, **66 historical**; all 210 have `predicate`, `subject`, `session_idx`, and `dialogue_id` populated.
- Local SQLite ledger: dialogue 7 has **210 facts** and `hydra_pending` is empty.
- Sixteen canonical HydraDB IDs retained stale queue state even after approved deletion/re-ingestion. They were recovered under deterministic `r1_<canonical_id>` source aliases, persisted in SQLite table `hydra_source_aliases`.
- All 16 recovery aliases report `completed`; graph relations are present.
- End-to-end output verified: `palimpsest ask 7 "What date format do I prefer?"` returns `You prefer the month day, year format.`
- HydraDB collection `8`: **190 listed sources**; **188 completed** and **2 still queued**.
- The first dialogue-8 ingest completed **188 sources** with **134 current / 54 historical** and complete schema metadata. A later partial eval run discovered two additional facts, which are checkpointed but not yet indexed.
- Local SQLite ledger: dialogue 8 has **190 facts**, **135 current**, **55 historical**, and two `hydra_pending` rows (`f_8_0001_000`, `f_8_0003_022`).
- The current-view contract is verified for the completed corpus: a historical source returns no chunk with `metadata_filters={"status":"current"}`, while its replacement does.
- `context.relations()` returns the expected `SUPERSEDES` edge after fixing the initial `cursor=0` wrapper bug.
- `palimpsest ask 8 "What is my current manager?"` returns a structured abstention naming `user / MANAGES`.

## What happened

The original `ingest-all 7 8` run submitted dialogue 7, then waited 630 seconds for indexing. HydraDB completed 156 sources but left 54 queued. The old all-or-nothing transaction rolled dialogue 7 back locally, and dialogue 8 never started.

After the reliability changes, a rerun persisted all 210 dialogue-7 facts locally and reduced the remote queue to 16. The pipeline no longer rolls back the entire dialogue when a subset remains queued.

Dialogue 8 was first ingested independently with the disk cache intact. It reconciled 192 extracted candidates as `55 NEW`, `4 DUPLICATE`, `13 REFINEMENT`, `41 SUPERSESSION`, and `79 CONTRADICTION`; 188 accepted facts indexed cleanly. A later partial eval run extracted two new deterministic facts and left both queued after two bounded retries. They remain in the outbox; do not delete or alias them without explicit review.

The full `make eval` was attempted after the preflight but reached the 30-minute command timeout without writing `results/raw_eval.json`. A dialogue-8-only retry later failed on repeated HydraDB query `ReadTimeout`s. No evaluation results are being claimed yet; do not rerun blindly without checkpointed progress.

## Reliability changes

- `src/palimpsest/hydra.py`
  - small-batch backpressure;
  - bounded HTTP request timeout;
  - status polling timeout;
  - retry only queued IDs with exponential backoff;
  - persistent stragglers returned instead of raising for the whole dialogue.
- `src/palimpsest/ledger.py`
  - `hydra_pending` outbox table;
  - pending fact recording, retry counts, and clearing;
  - permanent canonical-fact to recovery-source alias mapping.
- `src/palimpsest/write_path.py`
  - checkpoint before remote calls;
  - resume pending IDs and resolve recovery aliases;
  - deterministic fact-ID skip on reruns;
  - materialize complete metadata only for known-indexed facts.
- `src/palimpsest/llm.py`
  - explicit provider request timeout.
- `src/palimpsest/hydra.py`
  - `context.relations()` omits the API's invalid initial `cursor=0`; continuation cursors remain supported.
- `.env.example`
  - documents all queue, timeout, evaluation, and pricing controls.

### Evaluation and read-path changes (2026-08-19)

- `eval/run_eval.py`
  - every result appended to `results/raw_eval.jsonl` the moment it is produced;
  - resume skips completed rows and retries errored ones;
  - per-question timeout, and a failure recorded as a row rather than raising;
  - bounded concurrency, one event loop per worker thread (the LLM client is blocking,
    so a single shared loop serialized every question);
  - three read-path ablation arms over the corpus already ingested;
  - ingestion is opt-in, so evaluating cannot re-enter HydraDB's queue.
- `eval/report.py`
  - writes `main_table.md`, `ablation.md`, and `cost_latency.md`;
  - abstention measured in both directions, errored runs excluded from accuracy and
    counted separately, coverage stated in every table;
  - falls back to the JSONL checkpoint when a run never wrote its final JSON.
- `src/palimpsest/hydra.py`
  - reads get a two-attempt retry budget and their own timeout, separate from writes.
- `src/palimpsest/read_path.py`
  - `use_status_filter` / `use_coverage` switches; latency and cost on every answer.
- `src/palimpsest/llm.py`
  - token and cost metering, nestable usage scopes, and an enforced spend cap. Cache
    entries written before metering existed are still honored, so no paid call is re-bought.
- `src/palimpsest/cli.py`
  - `status`, `timeline`, and `verify` — the inspector and the demo path.
- `src/palimpsest/config.py`, `ledger.py`
  - `results/` created lazily, so a clean clone no longer fails on the ledger.

## Validation

```text
uv run pytest -q  -> 23 passed, 6 skipped
```

The 6 skips are the hand-labelled reconciliation pairs, which need a live LLM key.
The 23 passing tests include the evaluation harness's checkpoint/resume loop, the
read-path ablation switches, the report tables, and the cost metering — all runnable
offline, which is the point: the harness can be trusted before spending budget on it.

## Important interpretation

Dialogue 7 is complete through the 16 deterministic recovery aliases. Dialogue 8's initial 188-source ingest is complete, but two later deterministic sources remain queued in `hydra_pending` after bounded retries. Approved deletion and same-ID re-ingestion did not reset HydraDB's stale per-ID queue state for dialogue 7, so future status/metadata operations must resolve `hydra_source_aliases`. Do not delete or alias the two dialogue-8 stragglers without explicit review.
