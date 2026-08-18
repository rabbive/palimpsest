# Next steps

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

## P3 — evaluate

- [x] Run the frozen-subset preflight after dialogue 7/8 state was understood.
- [ ] Run `make eval` and preserve `results/raw_eval.json`.
- [ ] Run `make report` and inspect `results/main_table.md`, `results/ablation.md`, and `results/cost_latency.md`.
- [x] Record dialogue-7/8 indexed-source counts and persistent straggler count honestly.

**Evaluation status:** `make eval` was stopped at the 30-minute timeout without producing
`results/raw_eval.json`. A dialogue-8-only retry later hit repeated HydraDB query
`ReadTimeout`s before writing its output. That partial run also checkpointed two new
dialogue-8 facts (`f_8_0001_000`, `f_8_0003_022`) that remain queued after two bounded
retries. Leave them in `hydra_pending`; do not delete or alias them without explicit
review. Do not rerun the full eval blindly; it needs checkpointed progress and narrower
retry budgets first.

## P4 — ship hygiene

- [ ] Add/commit the reliability changes and these context documents.
- [ ] Ensure runtime DB/cache/log artifacts are ignored and no secrets are tracked.
- [ ] Run `./.venv/bin/pytest -q` from a clean environment.
- [ ] Update README limitations with the observed HydraDB queued-source behavior and the outbox mitigation.
- [ ] Complete the demo and submission checklist in `PALIMPSEST_BUILD_SPEC.md`.

## Stop conditions

Stop a live run and reassess if:

- a single HTTP call exceeds the configured timeout;
- the same source IDs remain queued after two bounded retry rounds;
- `hydra_pending` grows across independent dialogues;
- a process is gone but a SQLite journal remains — first open the DB through `ledger.connect()` to let SQLite recover it;
- a full evaluation would spend budget without producing new cached results.
