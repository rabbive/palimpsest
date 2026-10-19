# SDD ledger — plan: docs/superpowers/plans/2026-10-19-palimpsest-showcase.md

Branch: claude/project-overview-explanation-27975f. Merge base: 8844d75. Plan commit: 61a292e.
Spec: none separate; requirements are in the plan's header (from the 2026-10-19 brainstorm). Rulings made without a separate spec are provisional.

## Preflight scan

| tasks | shared file / interface | finding |
|---|---|---|
| T0 ↔ T4,T5,T8 | results/SPEND.md (T0 creates, others append rows) | consistent |
| T1 ↔ T3,T4 | docs/EVAL_PROTOCOL.md (T3 skip-case and T4 fix-slot-3 append to it) | consistent; appends only before freeze |
| T2 ↔ T4,T5 | coverage.slot_has_coverage signature (+model); check_premise unchanged externally | consistent |
| T3 ↔ T4 | read_path._chunk_line; test fixture gains `prompts` | consistent |
| T5 ↔ T0 | resync conditional on T0 Step 4 counts | consistent |
| T6 ↔ T8 ↔ T10 | README.md: different sections (results / library / BYOG limitation) | consistent, sequential |
| T7 ↔ T0 | config.LEDGER_PATH env override vs T0 symlink at default path | consistent: default unchanged |
| T9 ↔ T10 | write_path._byog_payload (T9 may fix, T10 uses) | consistent |
| T0 self | symlinks .cache/data are files to git; plan adds no-slash ignore patterns | consistent |
| T2 self | tests name `spy` keys (queries, chunks, verdict, verifier_calls, raise) — fixture defined by implementer | consistent |
| T3 self | tests need fixture `prompts` capture + teardown reset of `_Chunk.metadata` | stated in plan |
| T4 self | grep pattern matches json.dumps default `"arm": "A"`; 20 q × 2 arms = 40 | consistent |
| T5 self | report CLI flags --raw/--checkpoint/--out-dir exist (eval/report.py:198) | consistent |
| T6 self | `npm run build` needs site/node_modules (absent) | Ruling below |
| T10 self | Step 5 PR is outward-facing | stop for user go-ahead |

Ruling: Task 0 Step 3 — treat the configured LLM_API_BASE proxy in .env as the account holding the $50 unless the models endpoint fails — the user named no other provider — if wrong, the spend meter and SPEND.md track the wrong account.
Ruling: Task 6 Step 2 — run `npm ci` in site/ before `npm run build` (lockfile exists; local install only, no new deps) — if wrong, costs one install.
Ruling: Live runs (Tasks 0, 3 step 1, 4, 5, 8, 10) are executed by the implementer subagent for that task; the plan's dev gate (Task 4 Step 4) and the PR (Task 10 Step 5) stop for the user — those stops are plan-mandated — cost if wrong: a pause.

## Tasks
Task 0: dispatched (base 61a292e, implementer sonnet)
Task 0: NEEDS_CONTEXT — (1) configured models gpt-5.4-mini / gpt-5.5 absent from pincc /models (available: gpt-5.6*, gpt-6*, gpt-6.1-sol, ...); (2) sandbox denies writes to main checkout .cache and results/ via symlinks; (3) uv needed UV_CACHE_DIR=$TMPDIR/uvcache + pypi hosts. Symlinks + .gitignore edit left uncommitted. Waiting on user for models/prices and sandbox route.
User answers 2026-10-19: cheap=gpt-6-luna, strong="opus 5.5", prices later ("proceed with rest"), sandbox=copy into worktree.
Probe: gpt-6-luna -> "Upstream gateway error" x2; claude-opus-5-5 -> model_not_found on pincc; gpt-5.6 works. Proxy adds ~4.4K cached prompt tokens per call.
Ruling: Proceed with tasks that make no LLM calls (0,1,2,3,7 code, 9) while the strong model's provider is pending; hold live LLM runs (Tasks 4,5,8) until the user names where Opus 5.5 is served — guessing a provider could spend the wrong account — cost if wrong: a pause before Task 4.
Ruling: Copy .env into the worktree too (gitignored) so model settings can change without touching the main checkout — cost if wrong: two .env copies to reconcile.
Task 0: resumed with rulings
User 2026-10-19: use gpt-5.6 for both cheap and strong on pincc for now; Opus later.
Ruling: Set PALIMPSEST_CHEAP_MODEL=PALIMPSEST_STRONG_MODEL=gpt-5.6 in the worktree .env at the start of Task 4 — user's instruction — cost if wrong: none.
Ruling: Task 4 Step 1 changes — do NOT seed dev_v2 with old A/B rows; old rows were answered and judged by gpt-5.4-mini/gpt-5.5. Re-run B on dev with gpt-5.6 alongside the four C variants; quote old A (0.46) with a "different models" caveat; A excluded from new comparisons — keeps B vs C judged by the same model — cost if wrong: ~$1-2 extra for B.
Ruling: With cheap==strong the PRICE dicts collapse to one key and the strong default price ($0.0025/$0.01 per 1K) applies to every call — conservative overcount until the user supplies prices — cost if wrong: SPEND.md overstates spend.
Task 0: implementer DONE_WITH_CONCERNS (commit 0c6b2fb). HydraDB returns HTTP 402 FREE_PLAN_DEPRECATED on every read — all live HydraDB steps blocked (Tasks 3 step1, 4, 5, 8, 10). Ledger totals match brief; hydra_pending empty. pytest with copied .env: 64 passed, 2 failed (cached classifier tests: USES_TOOL ruff, LIVES_IN berlin->munich), previously skipped without key.
Ruling: Commit gate for the rest of the plan = "no failures beyond the 2 pre-existing cached classifier misses" — they are documented misses in results/classifier_accuracy.md and appear only because a key is now present — cost if wrong: a real regression in those two tests would be masked.
Ruling: Continue no-network tasks (1, 2, 3 code, 7, 9 doc read) while HydraDB access is surfaced to the user; live steps wait — cost if wrong: none.
Task 0: minor (deferred): SPEND.md Models omits "gpt-5.6 for both going forward"; resync decision pending on 402 not stated; record the 2 baseline failing test ids.
Task 0: minor (deferred): ledger/cache forked from main checkout — canonical copy is now the worktree's; copy back at finish.
Task 0: parked — reviewer says trailer should name Sonnet 5.5 — Ruling: the session's attribution reminder specifies "Claude Opus 5.5"; trailer stands — cost if wrong: one wrong trailer line.
Task 0: complete (commits 61a292e..0c6b2fb, review clean)
Task 1: dispatched (base 0c6b2fb, implementer sonnet)
Task 1: implementer DONE (e101515). 60-question figure verified by controller: 2 per category x 5 priority categories x 6 dialogues.
Task 1: review — spec compliant, quality needs fixes (7 Important doc loopholes).
Ruling: Held-out smoke (plan Task 5 Step 4) stays — it runs only after the freeze tag, and only its error count is read; its rows are not used for scoring — plan-mandated and harmless after freeze — cost if wrong: smoke rows peeked.
Ruling: Retrying errored rows at the same commit is allowed (plan Task 5 Step 5); re-running scored rows, partial or per-arm reruns are not — cost if wrong: none.
Ruling: "Overall" = micro-mean over every scored held-out question per arm, as eval/report.py computes; win requires C > B with 0 errored rows; a margin under 0.05 is reported as "no clear difference" rather than a win — avoids new stats code at n=60 — cost if wrong: a real small win reported as a draw.
Ruling: Question selection = all questions in the 5 priority categories (BEAM has exactly 2 per category per dialogue), no sampling.
Task 1: fix round 1/5 dispatched (commits e101515..3a62207); re-review running
Task 1: fix round 1/5 (12 addressed, 0 open; commits e101515..3a62207)
Task 1: minor (deferred): freeze covers protocol file vs append-only (post-tag amendment breaches freeze — intended); "0 errored rows" arm scope unstated (means B and C variants); smoke arms/checkpoint unstated (plan Task 5 Step 4 specifies B,C + results/heldout_smoke.jsonl).
Task 1: parked — re-reviewer says eval/ lacks output-path options — Ruling: wrong; eval/run_eval.py already has --checkpoint/--out and eval/report.py has --raw/--checkpoint/--out-dir — cost if wrong: none.
Task 1: note — 12-of-12 abstention figure was verified by the controller from results/raw_eval.jsonl on 2026-10-19; 0.31/0.34/56% come from results/main_table.md generated from the same file.
Task 1: complete (commits 0c6b2fb..3a62207, review clean after 1 fix round)
Task 2: dispatched (base 3a62207, implementer sonnet)
Task 2: implementer DONE_WITH_CONCERNS (363eee8). Deviation: timeout test also monkeypatches decompose_question (as written it could never reach hydra.query).
Ruling: Accept the timeout-test deviation — the brief's test was unreachable as written; adding the one-slot decompose patch keeps its intent — cost if wrong: none.
Task 2: review — spec ❌ (Focus 2: real complete_json raises JSONDecodeError on empty/prose; no catch). Important x1.
Task 2: minor (deferred): no test that OTHER drops predicate words; no assert verifier prompt contains entity/predicate/facts; query test doesn't assert max_results/graph_context.
Task 2: fix round 1/5 dispatched (363eee8..6e1df16); re-review running
Ruling: Task 3 Step 1 (live check of chunk metadata) is blocked by HydraDB 402 — implement _chunk_line to read session_idx from chunk.metadata, falling back to chunk.additional_metadata, unprefixed if absent in both; the live check moves to the first live step after access returns (before any dev run) and its result is recorded in docs/EVAL_PROTOCOL.md — if neither field carries it, the fix is inert rather than wrong — cost if wrong: fix 2 has no effect and dev measures fix 1 alone.
Task 2: fix round 1/5 (1 addressed, 0 open; commits 363eee8..6e1df16)
Task 2: minor (deferred): `except ValueError` broader than JSONDecodeError (low risk).
Task 2: complete (commits 3a62207..6e1df16, review clean after 1 fix round)
Task 3: dispatched (base 6e1df16, implementer sonnet)
Task 3: implementer DONE_WITH_CONCERNS (7728008); live check deferred per ruling
Ruling: While HydraDB is 402, execute out of order: after Task 3 go to Task 7 (library, offline), Task 9 (payload-shape comparison: SDK types + public docs, no HydraDB calls), Task 10 Steps 1 and 3 drafted without the live run (script written, write-up marked "repro output pending"). Tasks 4, 5, 6, 8 and Task 10 Step 2 wait for access — none of the skipped-ahead tasks depend on their results — cost if wrong: Task 6 README edits may need a merge with Task 8's README section.
Task 3: minor (deferred): no test for metadata dict lacking session_idx; session_idx=None renders "(session None)"; ORDERING chunk-line fallback untested.
Task 3: ⚠️ live field unverified — resolved by earlier ruling: first live step after access returns checks it before any dev run.
Task 3: complete (commits 6e1df16..7728008, review clean)
Task 7: dispatched (base 7728008, implementer sonnet)
Task 7: implementer DONE (f5635df); uv run needs --no-sync in sandbox after pyproject edit
Task 7: review — spec compliant, quality needs fixes: (I1) ledger split — connect() default bound at import vs Memory reading config at call time; (I2) ensure_dirs creates ROOT/results even with PALIMPSEST_LEDGER_PATH set, never creates custom ledger parent.
Task 7: minor (deferred): asyncio.Lock bound to one loop / docstring should say per-instance; ask test partly echoes mock. (2 test_reconcile failures confirmed pre-existing at Task 0 baseline.)
Task 7: fix round 1/5 dispatched (f5635df..484239f); re-review running
Task 7: fix round 1/5 (2 addressed, 0 open; commits f5635df..484239f)
Task 7: complete (commits 7728008..484239f, review clean after 1 fix round)
Task 9: dispatched (base 484239f, implementer sonnet)
Task 9: implementer DONE (388d77b), decision (a) shape matches docs. Key: relations_created/relations_error documented as "type=knowledge only" (None on memory ingest is expected, README overclaims); BYOG edges documented to surface in /query graph_context origin "byog" — repro must read both relations() and query graph_context.
Task 9: minor (deferred): "Unknown key" row mixes observed vs documented; add line that SDK docstring lacks "knowledge only" caveat; example pair odd.
Task 9: complete (commits 484239f..388d77b, review clean)
Ruling: Task 10 repro reads back through BOTH context.relations() and query(graph_context=True) looking for origin "byog", and uses a synthetic clean supersession pair (user lives in chennai -> bangalore), not a ledger fact — Task 9 showed relations() alone is not documented to list BYOG edges — cost if wrong: none.
Ruling: Task 10 now runs Steps 1, 3 (write-up with "Repro output: pending HydraDB access"), and 4 (README limitation corrected: relations_created=None is documented as knowledge-only, so it is not evidence; link the finding). Step 2 waits for access; Step 5 waits for the user.
Task 10: dispatched partial (base 388d77b, implementer sonnet)
Task 10: implementer DONE partial (46bae07); repro unrun (402)
Task 10: review — spec compliant; quality needs fixes: (I1) max_stragglers=2 of 2 ids means unindexed memories read back as "0 relations"; (I2, plan-mandated) README:61 and :134 still state "not readable" as fact, contradicting corrected limitation.
Ruling: Override my earlier "change nothing else in README" for README:61 and :134 only — qualify both with "through context.relations()" — a self-contradicting README is worse than the scope rule it protects — cost if wrong: two extra README lines changed.
Task 10: minor (deferred, triage at final review — audience-facing doc): data:null hidden as 0 relations; single readback (0 on control => rerun); "The repro separates these" overclaims; commit subject states hypothesis; @_retry makes 402 exit ~30s; _has_byog misses edges without origin key.
Task 10: fix round 1/5 dispatched (46bae07..7abedf6); re-review running
Task 10: fix round 1/5 (2 addressed, 0 open; commits 46bae07..7abedf6)
Task 10: minor (deferred): README "What this project would lose without HydraDB" bullet (~138-143) still says "we never got our own edges back out of it" unqualified.
Task 10: partial complete (offline Steps 1,3,4; commits 388d77b..7abedf6, review clean). Step 2 (live run) and Step 5 (hand-off/PR) pending.
Ruling: Run the whole-branch review now over 8844d75..HEAD rather than after the blocked live tasks — code that dev will measure should be clean before any dev run, and the deferred minors on audience-facing docs need triage — the workspace is kept (plan not finished) — cost if wrong: a second, smaller final review later over the live-task commits.
Final (interim) review: ready with fixes; 4 Important (I1 ORDERING drops session lines; I2 silent verifier fail-open; I3 stale "graph property / vector store can't" claims; I4 "no answer path depends on edges" vs ORDERING query_paths); 29 minors: 10 fix-now, 19 can wait (see final-review.md).
Ruling: I1 — ORDERING context = query_paths (if any) followed by the session-prefixed chunk lines, so fix 2 reaches event_ordering; it is within fix 2's scope and lands before any dev measurement; append one line to docs/EVAL_PROTOCOL.md saying so — cost if wrong: longer ORDERING prompts.
Ruling: I2 — log a warning and count fail-opens in a module-level counter; run_eval prints the count at the end of a run — minimal observability so dev can tell fix 1 from a broken verifier — cost if wrong: none.
Ruling: Fix-now minors that need live HydraDB (source counts for resync; live session_idx field check; live query_paths check) are moved into the first live step, before any dev run; they are not in this fix wave.
User 2026-10-19: will ask HydraDB team for a showcase/partner workspace; keep going on code-only; hold live runs until new key.
Final fix wave: DONE (7abedf6..721bbaf: cb59379 code, 721bbaf docs); 87 passed + 2 pre-existing. Re-review running.
Final fix wave: re-review — all 10 ADDRESSED, no new breakage.
Parked — site/src/App.tsx, site/index.html, PALIMPSEST_BUILD_SPEC.md still say "graph-property abstention" — Ruling: fold into Task 6 (which already edits the site) before the demo is shared; the build spec is historical and stays — cost if wrong: stale wording on the demo until Task 6.
Parked — byog doc "Task 10" mentions and unrecorded throwaway-collection claim (M1/M2) — Ruling: fix in Task 10 Step 2 when the live repro output is pasted, before the doc goes to HydraDB — cost if wrong: two stale sentences until then.
OFFLINE PHASE COMPLETE at 721bbaf. Waiting for new HydraDB key (user is asking HydraDB for a showcase workspace). Workspace kept.
First live step when the key arrives: (1) HydraDB source counts per dialogue (resync decision); (2) live check of which chunk field carries session_idx and whether ORDERING query_paths is non-empty; record both in EVAL_PROTOCOL (append) before any dev run; then Task 4.
