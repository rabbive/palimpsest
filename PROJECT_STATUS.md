# PALIMPSEST runtime status

_Last checked: 2026-08-19 while executing the `NEXT_STEPS.md` runbook. Refresh before relying on counts._
_Code updated 2026-08-19: the evaluation harness is resumable, the read path is bounded,
arm B is provisionable, and a clean clone was verified end to end (see below)._

## Ingested coverage

**Arm B is now provisioned** for dialogues 7 and 8 — 5 sources each in
`palimpsest_arm_b`, verified by `arm_b_source_count`, so the arm-B guard passes.
Dialogues 1–6 have no arm-B corpus and would need `setup-arm-b` per dialogue before
they could be evaluated on that arm.

Provisioning needed one workaround. `setup-arm-b` batches sessions
(`PALIMPSEST_HYDRA_BATCH_SIZE=8`, so all 5 sessions go in one request), and that
request exceeds the 30s `PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS` for an
`infer=True` ingest. The timeout is caught and the IDs are recorded as "queued", but
the sources were never created at all — `context.status` returned `FILE_NOT_FOUND`
for every one. Sent one at a time they are accepted immediately. Use
`PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120` when
provisioning arm B; both are env-tunable, so no code change was made under freeze.

`FROZEN_SUBSET` names dialogues 1–8. **All 8 are ingested in the local ledger** —
`palimpsest status` reports current/historical counts for every one (dialogue 1: 72/20,
2: 72/26, 3: 63/26, 4: 31/20, 5: 36/29, 6: 116/61, 7: 144/66, 8: 135/55). The earlier
claim that only 7 and 8 were ingested is stale, as is `NEXT_STEPS.md` Step 7, which
proposes ingesting 1–6 as optional remaining work. What dialogues 1–6 still lack is an
arm-B corpus and any evaluation coverage; the committed results tables cover 7 and 8
and disclose that in their own coverage lines.

## Current runtime

- No `palimpsest ingest` process is running.
- The previous long-running command was aborted; it is not still active.
- HydraDB collection `7`: **210 completed/listed sources**.
- Dialogue 7 metadata: **144 current**, **66 historical**; all 210 have `predicate`, `subject`, `session_idx`, and `dialogue_id` populated.
- Local SQLite ledger: dialogue 7 has **210 facts** and `hydra_pending` is empty.
- Sixteen canonical HydraDB IDs retained stale queue state even after approved deletion/re-ingestion. They were recovered under deterministic `r1_<canonical_id>` source aliases, persisted in SQLite table `hydra_source_aliases`.
- All 16 recovery aliases report `completed`; graph relations are present.
- End-to-end output verified: `palimpsest ask 7 "What date format do I prefer?"` returns `You prefer the month day, year format.`
- HydraDB collection `8`: **190 listed sources**, all **completed**.
- Local SQLite ledger: dialogue 8 has **190 facts**, **135 current**, **55 historical**, and `hydra_pending` is empty.
- The current-view contract is verified for the full corpus: a historical source returns no chunk with `metadata_filters={"status":"current"}`, while its replacement does.
- `context.relations()` **returns zero relations** for every arm-C source, so the
  earlier claim that it returns the expected `SUPERSEDES` edge no longer holds. The
  `cursor=0` wrapper fix is still in place and is not the cause. Checked across both
  dialogues, `type="memory"` and `"knowledge"`, with and without a collection, and
  with and without an `id`; the whole `palimpsest` database has no relations. Ingest
  responses report `relations_created=None` and `relations_error=None` — neither a
  count nor an error. The same call against `palimpsest_arm_b`, ingested with
  `infer=True`, returns 21 relations for dialogue 7 and 16 for dialogue 8, so the
  server's graph works and the supplied BYOG `graph_payload` is being silently ignored
  on `infer=False` ingests. Reproduced on a throwaway collection with a synthetic
  supersession pair, so this is not damage to the real corpus. Not fixed: the fix
  would be a re-ingest of both dialogues, which feature freeze and the queue-exposure
  rule both rule out. Documented in the README limitations instead.
- `palimpsest ask 8 "What is my current manager?"` returns a structured abstention naming `user / MANAGES`.

## What happened

The original `ingest-all 7 8` run submitted dialogue 7, then waited 630 seconds for indexing. HydraDB completed 156 sources but left 54 queued. The old all-or-nothing transaction rolled dialogue 7 back locally, and dialogue 8 never started.

After the reliability changes, a rerun persisted all 210 dialogue-7 facts locally and reduced the remote queue to 16. The pipeline no longer rolls back the entire dialogue when a subset remains queued.

Dialogue 8 was first ingested independently with the disk cache intact. It reconciled 192 extracted candidates as `55 NEW`, `4 DUPLICATE`, `13 REFINEMENT`, `41 SUPERSESSION`, and `79 CONTRADICTION`; 188 accepted facts indexed cleanly. A later partial eval run extracted two new deterministic facts and left both queued after two bounded retries. They were subsequently resumed from the outbox; both now report `completed`, and no recovery aliases were needed.

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
  - `status`, `timeline`, and `verify` — the inspector and the demo path;
  - `setup-arm-b` provisions arm B independently of arm C;
  - `classifier-accuracy` reports the classifier's error rate over 20 labelled pairs.
- `conftest.py`
  - project root on `sys.path`, so each test file passes standalone and not only
    as part of a full-suite collection order.
- `src/palimpsest/config.py`, `ledger.py`
  - `results/` created lazily, so a clean clone no longer fails on the ledger.
- `src/palimpsest/write_path.py`, `cli.py`
  - `halt_reason()` encodes the documented stop conditions, and `ingest-all` enforces
    them: a preflight showing what is ingested and what is stuck, a `--dry-run`, running
    spend, and a halt when one dialogue queues heavily or a second dialogue queues at all.
    This is the guard the original `ingest-all 7 8` run did not have.

## Validation

```text
uv run pytest -q  -> 46 passed, 20 skipped
```

The 20 skips are the hand-labelled reconciliation pairs, which need a live LLM key;
`palimpsest classifier-accuracy` scores them and writes the error rate.
The 46 passing tests include the arm-B preflight, the multi-dialogue ingestion stop conditions, the evaluation harness's checkpoint/resume loop, the
read-path ablation switches, the report tables, and the cost metering — all runnable
offline, which is the point: the harness can be trusted before spending budget on it.

## Important interpretation

Dialogue 7 is complete through the 16 deterministic recovery aliases. Dialogue 8's full 190-source ingest is complete and `hydra_pending` is empty after bounded outbox recovery. Approved deletion and same-ID re-ingestion did not reset HydraDB's stale per-ID queue state for dialogue 7, so future status/metadata operations must resolve `hydra_source_aliases`.
