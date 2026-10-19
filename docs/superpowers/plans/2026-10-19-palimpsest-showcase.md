# PALIMPSEST Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PALIMPSEST something to show HydraDB's team as "this fixes a real gap in HydraDB". That means three things: an honest benchmark win over HydraDB's own extraction, a library someone can use in ten lines, and a reproducible bug report on the dropped BYOG edges.

**Architecture:** There are three phases, done in order.
- **Phase 1** fixes the read path's over-abstention on dev dialogues 7–8. It freezes the code, then measures once on held-out dialogues 1–6.
- **Phase 2** wraps the existing `process_dialogue` / `answer_question` in a small `Memory` facade.
- **Phase 3** turns the `graph_payload`-ignored finding into a standalone repro and write-up.

**Tech Stack:** Python 3.11, `hydradb-sdk` 2.1.2, litellm through the configured OpenAI-compatible proxy, SQLite, pytest, uv.

**Spec:** this plan has no separate spec. The requirements come from the 2026-10-19 brainstorm and are restated here:
- **Audience:** people at HydraDB. Nothing has a hackathon deadline any more, and code can change.
- **Message:** PALIMPSEST fixes a real gap in HydraDB. HydraDB stores supersession as a label but doesn't enforce it, and it can't tell you a fact is missing.
- **Success:**
  1. The score is fixed.
  2. PALIMPSEST ships as a library or API on top of HydraDB.
  3. The BYOG finding is written up for HydraDB.
- **Anti-goal:** retuning until the numbers look good.
- **Budget:** about $50 of LLM credits. HydraDB is usable at no cost, and nothing else can be spent.

## Diagnosis this plan rests on

This was checked on 2026-10-19 against `../../../results/ledger.sqlite3` and `results/raw_eval.jsonl`.

- **Every stored fact has subject `user`.** That holds for all 972 facts across dialogues 1–8.
- **The coverage check filters on the wrong field.** `coverage.slot_has_coverage` filters HydraDB on `{"subject": entity, "predicate": predicate}`.
- **All 12 of arm C's abstentions on 7–8 named an entity other than `user`.** Examples are `michele / ATTENDED` and `my zoom call with the creative director / SCHEDULED_FOR`. No stored fact can ever match those slots. The thing the question is about is usually stored in the fact's *object*.
- **Predicates disagree between the two sides.** 309 of 972 facts are `OTHER`. For example, the zoom call is stored as `OTHER "30-minute zoom call between april 15-20"`, while the question decomposes to `SCHEDULED_FOR`. A predicate filter would miss it too.
- **Facts lose their place in time.** Memory text is `"user has deadline april 5."` with no session position, and C scored 0.12 on event_ordering and 0.00 on temporal_reasoning on 7–8.

This is one structural mismatch between write-side and read-side slot schemas, plus one piece of missing information. Neither is a threshold. The fixes below target those two mechanisms and nothing else.

## Global Constraints

- **Expected spend is about $24 if everything goes to plan:** dev about $4 (plus about $4 if a second dev round is needed), held-out smoke under $1, held-out sweep about $14, quickstart under $0.50. Re-extracting 1–6 costs nothing because the ledger already holds them, and arm B setup uses HydraDB's extraction, not ours.
- **Total LLM spend across the whole plan is ≤ $50.** The in-process cap resets per process, so record every run's `LLM usage:` line in `results/SPEND.md`. Before each live run, set `PALIMPSEST_MAX_SPEND_USD` to the remaining budget.
- Never put secrets in source, markdown, logs, or commits. `.env` stays local.
- Keep `infer=False` for arm C. Use deterministic fact IDs and `upsert=true` for any recovery.
- Never delete remote HydraDB memories without the user's explicit approval.
- Never pass `--ingest` to `eval.run_eval`. Never delete `results/raw_eval.jsonl`.
- **Every new evaluation run uses its own `--checkpoint` and `--out` file.** `load_checkpoint` skips keys that already completed, so rerunning arm C against `results/raw_eval.jsonl` would silently return the old answers.
- Add dialogues to HydraDB only through `palimpsest ingest-all`, at most two ids per call.
- Run `uv run pytest -q` after every code change. It must pass before each commit.
- Dev dialogues are `7,8`. Held-out dialogues are `1,2,3,4,5,6`. Never change code after looking at a held-out result (see `docs/EVAL_PROTOCOL.md`, Task 1).

## Review Focus

1. **`Memory.add_session` is called twice concurrently on one instance.** Session indexes must still be distinct, because fact IDs are `f_<collection>_<session:04d>_<i:03d>` and a collision would silently skip the second session's facts. Tested in Task 7.
2. **The coverage verifier returns malformed or non-JSON output.** The slot must count as covered and the question gets answered. A parse failure must never turn into an abstention. Tested in Task 2.
3. **A HydraDB timeout happens inside the coverage check.** The exception must propagate, so the eval records an error row. It must not come back as an `Abstention` that would be scored as a correct refusal. Tested in Task 2.
4. **A retrieved chunk has no `metadata`, or no `session_idx` key in it.** The chunk must appear in the answer context unprefixed, with no crash. Tested in Task 3.
5. **The library is installed outside the repo,** where `config.ROOT` points into site-packages. The ledger and cache paths must be settable by environment variable. Tested in Task 7.

---

## Phase 0: Workspace

### Task 0: Make the worktree runnable and record the starting state

This task has no product code. The worktree has no `.env`, no `.cache/`, no `data/BEAM`, and no ledger. Those live in the main checkout at `../../..`.

**Files:**
- Modify: `.gitignore`. Add `.cache` and `data` without trailing slashes, so the symlinks are ignored too.
- Create: `results/SPEND.md`

- [ ] **Step 1: Link the shared state into the worktree.**

```bash
ln -s ../../../.env .env
ln -s ../../../.cache .cache
ln -s ../../../data data
ln -s ../../../../results/ledger.sqlite3 results/ledger.sqlite3
```

There is a single ledger and a single LLM cache, and the main checkout and the worktree must share them. Copies would fork the reconciliation record.

- [ ] **Step 2: Install and run the tests.**

Run `uv sync && uv run pytest -q`. Expect 0 failures. Some tests are skipped when live keys are absent; the last recorded run was `46 passed, 20 skipped`.

- [ ] **Step 3: Confirm the models are reachable on the account that holds the $50.**

Run `uv run python -c "import litellm, os; from palimpsest import config; print(config.CHEAP_MODEL, config.STRONG_MODEL, config.LLM_API_BASE)"`. Then fetch `$LLM_API_BASE/models` with the key from `.env`, without printing the key. Both model ids must be listed.

If the $50 is on a different provider or base URL, stop and ask the user before going further. Then set `PALIMPSEST_CHEAP_PRICE_*` / `PALIMPSEST_STRONG_PRICE_*` in `.env` to that provider's price sheet, so the meter matches real spend.

- [ ] **Step 4: Record what is in HydraDB for every dialogue.**

```bash
uv run python -c "
import asyncio
from palimpsest import hydra
async def main():
    for db in ('palimpsest', 'palimpsest_arm_b'):
        for d in '12345678':
            try:
                r = await hydra.list_facts(database=db, collection=d, page=1, page_size=1)
                print(db, d, getattr(r.data, 'total', None))
            except Exception as e:
                print(db, d, type(e).__name__)
asyncio.run(main())"
uv run palimpsest status
```

Write both outputs into `results/SPEND.md` under a heading `## Starting state 2026-10-19`.
- Expected for `palimpsest` 7 and 8: 210 and 190 sources.
- Expected for `palimpsest_arm_b` 7 and 8: 5 each.
- If any of `palimpsest` 1–6 has fewer sources than the ledger shows (1: 92, 2: 98, 3: 89, 4: 51, 5: 65, 6: 177), Task 5 runs its resync step.

- [ ] **Step 5: Start the spend log.**

`results/SPEND.md` gets a table with the columns `| date | run | LLM usage line | remaining |`. Its first row is `| 2026-10-19 | start | — | $50.00 |`.

- [ ] **Step 6: Commit.**

```bash
git add .gitignore results/SPEND.md
git commit -m "chore: share ledger and cache with the worktree, record starting state"
```

---

## Phase 1: Fix the score honestly

### Task 1: Pre-register the evaluation protocol

This task writes the rules down before any fix is measured. That is what the anti-goal requires.

**Files:**
- Create: `docs/EVAL_PROTOCOL.md`

- [ ] **Step 1: Write `docs/EVAL_PROTOCOL.md` with exactly these decisions.**

  - **Dev set:** dialogues 7, 8. Arm C failed here, and that failure was diagnosed here. Fixes may be measured on dev as often as needed, within budget.
  - **Held-out set:** dialogues 1–6, priority categories only, 60 questions. Nobody has looked at their questions or answers. Disclose that dialogues 1–2 were skimmed to build `vocab.py` in the original build. They informed the write path's vocabulary, not this read-path fix.
  - **Fixes allowed:**
    1. The coverage schema alignment (Task 2).
    2. Session-position context in answers (Task 3).
    3. At most one further fix, if dev shows a new *structural* cause. It must be written into this file, with its diagnosis, before it is coded.

    Prompt-wording or threshold changes made only to move a dev number are not allowed.
  - **Freeze:** tag `eval-freeze-v2` on the commit that will be measured on held-out. No code changes are allowed between the tag and the held-out report.
  - **Held-out arms:** B, C, C_no_coverage, C_no_status_filter. Arm A is excluded for budget (about $0.31 per question). Its dev score, 0.46, is quoted with that caveat.
  - **Success:** on held-out, C overall > B overall. Both abstention directions are reported. A reader should be able to see whether a win comes from false abstentions on answerable questions or from refusing correctly.
  - **Reporting rule:** the held-out result is published as measured, whatever it is. If C does not beat B, the README says so. There is no second held-out run after a code change.

- [ ] **Step 2: Commit.**

```bash
git add docs/EVAL_PROTOCOL.md
git commit -m "docs: pre-register the dev/held-out evaluation protocol"
```

### Task 2: Align coverage slots with what the write path stores

**Files:**
- Modify: `src/palimpsest/coverage.py`, which holds `DECOMPOSE_SYSTEM`, `slot_has_coverage`, `check_premise`, and a new `_evidence_covers_slot`
- Test: `tests/test_coverage.py`

**Interfaces:**
- Produces: `async def slot_has_coverage(dialogue_id: str, entity: str, predicate: str, model: str = config.CHEAP_MODEL) -> tuple[bool, list[str]]`. The signature is the same as today plus `model`. `check_premise` passes its `model` through.
- Produces: `def _evidence_covers_slot(entity: str, predicate: str, evidence: list[str], model: str) -> bool`
- `Abstention.missing_slots` keeps its `"entity / PREDICATE"` format. `read_path` and the eval harness are unchanged.

- [ ] **Step 1: Write the failing tests.**

Use a `spy` fixture the way `tests/test_read_path_ablations.py` does: monkeypatch `coverage.hydra.query` to record kwargs and return chunks, and monkeypatch `coverage.llm.complete_json`.

```python
def test_coverage_query_does_not_filter_on_subject_or_predicate(spy):
    asyncio.run(coverage.slot_has_coverage("8", "my zoom call with the creative director", "SCHEDULED_FOR"))
    assert spy["queries"][0]["metadata_filters"] is None
    assert "zoom call" in spy["queries"][0]["q"]

def test_slot_covered_when_verifier_says_a_fact_is_about_it(spy):
    spy["chunks"] = ["user other 30-minute zoom call between april 15-20."]
    spy["verdict"] = {"covered": True}
    covered, evidence = asyncio.run(coverage.slot_has_coverage("8", "my zoom call with the creative director", "SCHEDULED_FOR"))
    assert covered and evidence == spy["chunks"]

def test_slot_uncovered_when_verifier_says_no(spy):
    spy["chunks"] = ["user uses tool notion."]
    spy["verdict"] = {"covered": False}
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is False

def test_no_chunks_is_uncovered_without_an_llm_call(spy):
    spy["chunks"] = []
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is False
    assert spy["verifier_calls"] == 0

def test_malformed_verifier_output_fails_open(spy):           # Review Focus 2
    spy["chunks"] = ["user has pet rex."]
    spy["verdict"] = "not json"
    assert asyncio.run(coverage.slot_has_coverage("8", "my dog", "HAS_PET"))[0] is True

def test_hydra_timeout_propagates_instead_of_abstaining(spy):  # Review Focus 3
    spy["raise"] = asyncio.TimeoutError()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(coverage.check_premise("8", "Do I have a dog?"))

def test_abstention_still_names_the_missing_slot(spy, monkeypatch):
    monkeypatch.setattr(coverage, "decompose_question", lambda q, model=None: [{"entity": "my dog", "predicate": "HAS_PET"}])
    spy["chunks"] = []
    ab = asyncio.run(coverage.check_premise("8", "What is my dog's name?"))
    assert ab.missing_slots == ["my dog / HAS_PET"]
```

- [ ] **Step 2: Run the tests and confirm they fail.**

Run `uv run pytest tests/test_coverage.py -v`. Expect failures on the `metadata_filters` assertion and on the missing `_evidence_covers_slot` behavior.

- [ ] **Step 3: Implement.**

`slot_has_coverage`:
- Query HydraDB with `q=f"{entity} {predicate words}"`. Leave out the predicate words when the predicate is `OTHER`.
- Use `metadata_filters=None`, `max_results=5`, and keep `graph_context=True`. No status filter, since this checks existence, not truth.
- If there is no evidence, return `(False, [])` without an LLM call.
- Otherwise return `(_evidence_covers_slot(...), evidence)`.

`_evidence_covers_slot` makes one `llm.complete_json` call with the system prompt below and the user prompt `ENTITY: …\nPREDICATE: …\nFACTS:\n- …`. It returns `data.get("covered") is not False` when `data` is a dict, and `True` otherwise. That is fail-open: any parse failure counts as covered.

```python
COVERAGE_SYSTEM = """You decide whether a memory store holds ANY fact about a slot. \
ENTITY is the thing the question is about; PREDICATE is the kind of information needed. \
FACTS are the closest facts in the store. Answer covered=true if at least one fact is about \
the same entity and the same kind of information, even if worded differently or if its \
value later changed. Answer covered=false only if no fact is about that entity and kind of \
information. Return ONLY {"covered": true} or {"covered": false}."""
```

In `DECOMPOSE_SYSTEM`, change only the description of `entity` to: "the specific thing the question is about: a person, event, project, place or object. Use 'user' only when the question is about the user in general." The JSON shape and the closed vocabulary sentence stay as they are.

- [ ] **Step 4: Run the tests and confirm they pass.**

Run `uv run pytest -q`. Expect everything to pass, including the existing `_normalize_entity` tests.

- [ ] **Step 5: Commit.**

```bash
git add src/palimpsest/coverage.py tests/test_coverage.py
git commit -m "fix(coverage): match slots against what the write path stores

Every stored fact has subject 'user', so filtering coverage on
subject=<entity> could never match a named entity. All 12 arm-C
abstentions on dialogues 7-8 had this cause."
```

### Task 3: Give the answer model each fact's place in time

**Files:**
- Modify: `src/palimpsest/read_path.py`, the context assembly in `_answer`
- Test: `tests/test_read_path_ablations.py`, extending its `_Chunk` fake

**Interfaces:**
- Produces: `def _chunk_line(chunk) -> str`. It returns `f"(session {idx}) {content}"` when `chunk.metadata` is a dict containing `session_idx`, and `content` otherwise.

- [ ] **Step 1: Confirm live that chunks carry our schema metadata.** This costs nothing, since it is a HydraDB read only.

```bash
uv run python -c "
import asyncio
from palimpsest import hydra
r = asyncio.run(hydra.query(q='deadline', collection='8', max_results=2))
print([(c.metadata, c.additional_metadata) for c in r.data.chunks])"
```

- **`session_idx` appears in `metadata`:** continue.
- **It only appears in `additional_metadata`:** read from there instead, and say so in `_chunk_line`'s docstring.
- **It appears in neither:** skip this task. Record that in `docs/EVAL_PROTOCOL.md` under fixes, and go to Task 4.

- [ ] **Step 2: Write the failing tests.**

```python
def test_context_lines_carry_session_position(spy):
    _Chunk.metadata = {"session_idx": 3, "status": "current"}
    asyncio.run(read_path.answer_question("7", "who is my manager?", use_coverage=False))
    assert "(session 3) user reports to priya raghavan." in spy["prompts"][0]

def test_chunk_without_metadata_is_unprefixed(spy):            # Review Focus 4
    _Chunk.metadata = None
    asyncio.run(read_path.answer_question("7", "who is my manager?", use_coverage=False))
    assert "\nuser reports to priya raghavan." in spy["prompts"][0]
```

These tests need the fixture's `llm.complete` fake to record `kwargs["prompt"]` into `calls["prompts"]`. Reset `_Chunk.metadata` in the fixture teardown.

- [ ] **Step 3: Implement `_chunk_line` and use it when building `chunk_texts`.** Add one line to `ANSWER_SYSTEM`: "Lines prefixed (session N) come from the Nth conversation session; higher N is later."

- [ ] **Step 4: Run `uv run pytest -q`.** Expect a pass.

- [ ] **Step 5: Commit.**

```bash
git add src/palimpsest/read_path.py tests/test_read_path_ablations.py
git commit -m "feat(read): give the answer model each fact's session position"
```

### Task 4: Measure on dev (7–8)

**Files:**
- Create: `results/dev_v2.jsonl`, `results/dev_v2.json`, `results/dev_v2/*.md`
- Modify: `results/SPEND.md`

- [ ] **Step 1: Seed the new checkpoint with the unchanged arms.** Neither A nor B calls `read_path` or `coverage`, so their rows from `results/raw_eval.jsonl` are still valid.

```bash
grep -E '"arm": "(A|B)"' results/raw_eval.jsonl > results/dev_v2.jsonl
wc -l results/dev_v2.jsonl   # expect 40
```

- [ ] **Step 2: Run the four arm-C variants on dev.** Expect about $4. The last run cost $3.48 for these 80 arm-runs.

```bash
PALIMPSEST_MAX_SPEND_USD=<remaining> uv run python -m eval.run_eval \
  --dialogues 7,8 --arms C,C_no_status_filter,C_no_coverage,C_neither \
  --checkpoint results/dev_v2.jsonl --out results/dev_v2.json
mkdir -p results/dev_v2
uv run python -m eval.report --raw results/dev_v2.json --checkpoint results/dev_v2.jsonl --out-dir results/dev_v2
```

The run should end with `wrote 120 eval results to results/dev_v2.json (0 errored)`. If any rows errored, rerun the same command; it resumes and retries only the errored rows.

- [ ] **Step 3: Log spend.** Append the run's `LLM usage:` line to `results/SPEND.md`.

- [ ] **Step 4: Gate.** Read `results/dev_v2/main_table.md`.
  - **C overall > 0.34 (B's dev score):** go to Task 5.
  - **Otherwise:** list C's lowest-scoring rows, give each a cause, and bring that list to the user. Only a structural cause that gets written into `docs/EVAL_PROTOCOL.md` (fix slot 3) may be coded, and that happens once. Repeat Steps 1–4 with `dev_v3`. If C still does not beat B, stop and report to the user. Do not go on to held-out.

- [ ] **Step 5: Commit.**

```bash
git add results/dev_v2.jsonl results/dev_v2.json results/dev_v2 results/SPEND.md
git commit -m "eval: dev results after coverage and session-position fixes"
```

### Task 5: Freeze, then measure once on held-out (1–6)

**Files:**
- Modify only if the Task 0 Step 4 counts showed gaps: `src/palimpsest/cli.py` (new `resync` command), `src/palimpsest/hydra.py` (new `remote_source_ids`), `tests/test_hydra.py`
- Create: `results/heldout.jsonl`, `results/heldout.json`, `results/heldout/*.md`

**Interfaces (resync only):**
- Produces: `async def remote_source_ids(collection: str, database: str = config.HYDRADB_DATABASE) -> set[str]`. It pages through `list_facts` with `page_size=100` until a page comes back short.
- Produces: the CLI command `palimpsest resync <dialogue_id>`. It computes `missing = ledger source ids (via ledger.source_ids) − remote_source_ids`. It calls `ledger.record_pending(conn, missing, dialogue_id)`, then `await write_path._retry_pending(dialogue_id, stats)`, and prints the stats. It never re-sends IDs that are already remote.

- [ ] **Step 1 (only if needed): Write and run the resync with TDD.**
  1. Write the test `test_remote_source_ids_pages_until_short_page` using a fake `list_facts`. Run it and confirm it fails.
  2. Implement `remote_source_ids` and the `resync` command, and run `uv run pytest -q`.
  3. Commit with `feat(cli): resync ledger facts missing from HydraDB`.
  4. Run `palimpsest resync <id>` for each gapped dialogue, one at a time. Confirm `palimpsest status` shows an empty outbox.

- [ ] **Step 2: Freeze.**

```bash
uv run pytest -q
git tag eval-freeze-v2
```

- [ ] **Step 3: Provision arm B for 1–6.** This makes no LLM calls; HydraDB does the extraction. The env values are the workaround recorded in `PROJECT_STATUS.md`.

```bash
PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120 uv run palimpsest setup-arm-b 1 2
PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120 uv run palimpsest setup-arm-b 3 4
PALIMPSEST_HYDRA_BATCH_SIZE=1 PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS=120 uv run palimpsest setup-arm-b 5 6
```

Expect every dialogue to report its sources, and the Task 0 Step 4 snippet to show `palimpsest_arm_b` counts > 0 for 1–6.

- [ ] **Step 4: Smoke test.** Expect under $1.

```bash
PALIMPSEST_MAX_SPEND_USD=<remaining> uv run python -m eval.run_eval --dialogues 1,2,3,4,5,6 \
  --arms B,C --limit-per-category 1 --checkpoint results/heldout_smoke.jsonl --out results/heldout_smoke.json
```

Expect 0 errored.

- [ ] **Step 5: Run the held-out sweep.** Expect about $14: 60 questions × 4 arms, judge included.

```bash
PALIMPSEST_MAX_SPEND_USD=<remaining> uv run python -m eval.run_eval --dialogues 1,2,3,4,5,6 \
  --arms B,C,C_no_coverage,C_no_status_filter --checkpoint results/heldout.jsonl --out results/heldout.json
mkdir -p results/heldout
uv run python -m eval.report --raw results/heldout.json --checkpoint results/heldout.jsonl --out-dir results/heldout
```

Expect `wrote 240 eval results … (0 errored)`. If rows errored, rerun the same command (it resumes). Errored rows are not a code change.

- [ ] **Step 6: Log spend and commit, with no code changes.**

```bash
git add results/heldout* results/SPEND.md
git commit -m "eval: held-out results on dialogues 1-6 at eval-freeze-v2"
```

### Task 6: Publish the numbers as measured

**Files:**
- Modify: `README.md` ("Results" and "What the results actually show"), `site/src/App.tsx` (the hard-coded score figures), `PROJECT_STATUS.md`
- Replace: `NEXT_STEPS.md`. Its hackathon runbook is stale. Replace it with a pointer to this plan's remaining phases.

- [ ] **Step 1: Rewrite the README results section.** Keep the old 7–8 numbers, labeled "before". Then show:
  - dev after the fixes;
  - held-out at `eval-freeze-v2`, with its coverage line, n per cell, and both abstention directions;
  - the protocol link.

  Name the diagnosis in one paragraph: the subject mismatch and the 12/12 abstentions. If held-out C ≤ B, say that plainly in the first sentence of the section.

- [ ] **Step 2: Update the numbers the site replays** in `site/src/App.tsx`. Run `cd site && npm run build`. Expect a successful build.

- [ ] **Step 3: Run `uv run pytest -q` and commit.**

```bash
git add README.md site/src/App.tsx PROJECT_STATUS.md NEXT_STEPS.md
git commit -m "docs: report dev and held-out results after the coverage fix"
```

---

## Phase 2: Library on top of HydraDB

### Task 7: `Memory` facade

**Files:**
- Create: `src/palimpsest/memory.py`
- Modify: `src/palimpsest/__init__.py` (export `Memory`), `src/palimpsest/config.py` (`LEDGER_PATH` and `CACHE_DIR` read `PALIMPSEST_LEDGER_PATH` / `PALIMPSEST_CACHE_DIR` and fall back to today's values), `src/palimpsest/ledger.py` (new `next_session_idx`), `pyproject.toml` (real `description`)
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `write_path.process_dialogue(dialogue_id: str, sessions: list[tuple[int, str, str]], model=...) -> dict` and `read_path.answer_question(dialogue_id, question, ...) -> Answer`, both unchanged.
- Produces: `def ledger.next_session_idx(conn, dialogue_id: str) -> int`, which returns `MAX(session_idx)+1`, or `0` when the dialogue has no facts.
- Produces:

```python
class Memory:
    def __init__(self, collection: str): ...
    async def add_session(self, text: str, timestamp: str = "") -> dict: ...   # process_dialogue stats
    async def ask(self, question: str) -> Answer: ...
    def history(self) -> list[Fact]: ...   # ledger.all_facts, for inspection only; never used to answer
```

`collection` is one end user's memory. It maps to HydraDB's collection and to the ledger's `dialogue_id`. The database still comes from `HYDRADB_DATABASE`, and its schema is created once with `palimpsest create-db`.

- [ ] **Step 1: Write the failing tests.** Monkeypatch `memory.process_dialogue` and `memory.answer_question`, and use a temporary ledger via `PALIMPSEST_LEDGER_PATH` and `importlib.reload(config)`, or by monkeypatching `config.LEDGER_PATH`.

```python
def test_add_session_uses_next_session_index(fake_write, mem):
    asyncio.run(mem.add_session("I live in Chennai."))
    asyncio.run(mem.add_session("I moved to Bangalore."))
    assert [s[0][0] for s in fake_write["sessions"]] == [0, 1]

def test_concurrent_add_session_gets_distinct_indexes(fake_write, mem):   # Review Focus 1
    async def both():
        await asyncio.gather(mem.add_session("a"), mem.add_session("b"))
    asyncio.run(both())
    assert sorted(s[0][0] for s in fake_write["sessions"]) == [0, 1]

def test_ask_routes_to_the_collection(fake_read, mem):
    asyncio.run(mem.ask("Where do I live?"))
    assert fake_read["dialogue_id"] == mem.collection

def test_ledger_path_is_env_overridable(monkeypatch, tmp_path):          # Review Focus 5
    monkeypatch.setenv("PALIMPSEST_LEDGER_PATH", str(tmp_path / "l.sqlite3"))
    import importlib, palimpsest.config as c
    assert importlib.reload(c).LEDGER_PATH == str(tmp_path / "l.sqlite3")
```

The fake `process_dialogue` must `await asyncio.sleep(0)` before it inserts one ledger fact per session at the given `session_idx`. Without that yield, the concurrency test passes even without the lock. With it, `next_session_idx` advances the way the real thing does.

- [ ] **Step 2: Run `uv run pytest tests/test_memory.py -v`.** Expect a failure, because `palimpsest.memory` doesn't exist yet.

- [ ] **Step 3: Implement.**

`add_session` holds an `asyncio.Lock` owned by the instance from reading `next_session_idx` until `process_dialogue` returns. That lock is what makes the concurrency test pass. The docstring states that it does not protect against two processes writing to one collection.

- [ ] **Step 4: Run `uv run pytest -q`.** Expect a pass.

- [ ] **Step 5: Commit.**

```bash
git add src/palimpsest/memory.py src/palimpsest/__init__.py src/palimpsest/config.py src/palimpsest/ledger.py pyproject.toml tests/test_memory.py
git commit -m "feat: Memory facade for using PALIMPSEST as a library"
```

### Task 8: Quickstart example that shows the gap

**Files:**
- Create: `examples/quickstart.py`
- Modify: `README.md` (new "Use it as a library" section near the top)

- [ ] **Step 1: Write `examples/quickstart.py`.**
  - It uses collection `quickstart-<unix time>`, so reruns never collide.
  - It adds three sessions: "I live in Chennai and work at Zoho.", "I moved to Bangalore last month.", and "My manager is Priya."
  - It then prints `ask()` for:
    1. "Where do I live now?" Expect Bangalore, with Chennai not in the answer context.
    2. "Who is my manager?" Expect Priya.
    3. "What is my dog's name?" Expect an `Abstention` naming the slot.
  - It prints `history()` with historical facts marked.

- [ ] **Step 2: Run it live.** Expect under $0.50.

```bash
PALIMPSEST_MAX_SPEND_USD=<remaining> uv run python examples/quickstart.py
```

The three answers should be as listed in Step 1. If HydraDB leaves a source queued, the script prints the `stragglers` stat. Rerun once after 30 seconds, and the outbox retries it.

- [ ] **Step 3: Paste the real output into the README section** as a fenced block, with the four-line usage snippet above it. Log the spend.

- [ ] **Step 4: Commit.**

```bash
git add examples/quickstart.py README.md results/SPEND.md
git commit -m "docs: library quickstart with a supersession and an abstention"
```

---

## Phase 3: The BYOG finding for HydraDB

### Task 9: Rule out our own payload shape first

**Files:**
- Modify (only if the shape is wrong): `src/palimpsest/write_path.py` (`_byog_payload`) and the matching test

- [ ] **Step 1: Read HydraDB's BYOG / `graph_payload` docs** (docs.hydradb.com) and the SDK's ingest types in `.venv/lib/python3.11/site-packages/hydra_db/types/`. Compare field by field with the output of `_byog_payload` for one real fact. Print it with `uv run python -c` from the ledger.

- [ ] **Step 2: Decide.**
  - **The shape matches the docs:** go to Task 10, and record the comparison in its write-up.
  - **It doesn't match:** fix `_byog_payload` test-first, then commit with `fix(write): match HydraDB's documented graph_payload shape`. Task 10's repro then tests the corrected shape. If relations now come back, the write-up becomes "our bug, fixed", and the README limitation is corrected to match.

### Task 10: Minimal repro and write-up

**Files:**
- Create: `scripts/repro_byog_infer_false.py`, `docs/hydradb-byog-finding.md`

- [ ] **Step 1: Write the repro.**
  - It uses a fresh collection `byog-repro-<unix time>` in the existing `palimpsest` database.
  - It ingests two memories with `infer=False` and a `graph_payload` holding one relation between them, built with `_byog_payload`. Then it waits with `wait_for_indexed`.
  - It ingests the same two texts with `infer=True` and no payload into the same database, under a second fresh collection, as the control.
  - It prints, for each collection, the ingest response's `relations_created` / `relations_error` and `len(relations(...))`.
  - It deletes nothing.

- [ ] **Step 2: Run it.** This makes no LLM calls.

Run `uv run python scripts/repro_byog_infer_false.py`. The recorded finding predicts:
- the `infer=False` collection shows `relations_created=None relations_error=None` and 0 relations;
- the `infer=True` collection shows more than 0 relations.

Whatever it prints is the result.

- [ ] **Step 3: Write `docs/hydradb-byog-finding.md`** for HydraDB engineers:
  - one-paragraph summary;
  - SDK version `hydradb-sdk 2.1.2` and the date;
  - the exact payload sent;
  - expected vs actual;
  - the repro command and its real output;
  - the Task 9 doc comparison;
  - what PALIMPSEST does instead: the status-metadata filter plus the SQLite chain;
  - one question for them: "Is `graph_payload` supported on `infer=False` memory ingests, and if so, what shape does it expect?"

  No secrets or API keys go into this file.

- [ ] **Step 4: Link it** from the README's BYOG limitation. Run `uv run pytest -q`, then commit.

```bash
git add scripts/repro_byog_infer_false.py docs/hydradb-byog-finding.md README.md
git commit -m "docs: reproducible report of graph_payload ignored on infer=False ingests"
```

- [ ] **Step 5: Hand off.** Sending the report to HydraDB is the user's action. Give them the file path and the one question. Then open the PR for the branch, with the user's go-ahead.
