# PALIMPSEST — Build Spec & Agent Context

**Hack Hydra 2026 · Track 03: Memory + Context Retrieval**

> A write-time reconciliation and abstention layer built on HydraDB.
> Facts are never deleted — they are superseded, and the chain stays readable.

---

## 0. How to use this document

This file is the single source of truth for the build. Hand it to your coding agent
(Claude Code / Cursor / Codex) as context at the start of every session. It contains:

- what we are building and **why** (Section 1–3)
- the exact HydraDB API surface, verified against SDK v2.1.2 (Section 5)
- the data model and algorithms (Section 6–8)
- repo layout, milestones, and hour budgets (Section 9–11)
- the submission checklist that decides whether we get judged at all (Section 13)

**Agent instructions:** Do not invent HydraDB API parameters. Everything in Section 5
was verified from the published SDK reference. If something is missing, check
`https://docs.hydradb.com/llms.txt` for the page index and read the real doc — do not guess.

---

## 1. Hard constraints

| Item | Value |
|---|---|
| Submission deadline | **Aug 20, 2026, 11:59 PM PT** = **Aug 21, 12:29 PM IST** |
| Earliest allowed commit | Aug 12, 2026 (we start clean — no problem) |
| Team | Solo |
| Time available | ~90 hours from Aug 17 |
| Track | 03 — Memory + Context Retrieval |
| Benchmark | **BEAM-100K** (not LongMemEval-S — see §3) |

Three deliverables, all due together: **Google Form** (`forms.gle/GrMYKxLj9zPQcqqc8`),
**public licensed GitHub repo**, **demo video ≤ 3 minutes**.

---

## 2. The thesis (memorize this — it goes in the README, the video, and the form)

HydraDB ships an append-only, Git-style temporal graph with versioned edges. But a
`SUPERSEDES` edge is *just a label*. Nothing in the store makes the old fact behave as
historical — application code must enforce that on every single read. HydraDB says this
explicitly: the graph, the memory primitives, and the retrieval pipeline are yours to compose.

**PALIMPSEST is the reconciliation and abstention layer HydraDB deliberately does not ship.**

Two claims, both measurable:

1. **Supersession is resolved at write time, not read time.** When a new fact contradicts
   an old one, we write the `SUPERSEDES` edge *and* flip the old fact's metadata to
   `status="historical"`. "What is true now" becomes a hard metadata filter on HydraDB's
   query path — deterministic, not re-derived per query.

2. **Abstention is a graph property, not a model judgment.** Before generating anything we
   decompose the question into required `(entity, predicate)` slots and check coverage in
   the graph. Zero edges on a required slot → we abstain and name the missing slot. A
   vector store cannot do this: it always returns top-k, so its floor is "least-bad match",
   never "absent". We can prove absence.

---

## 3. Why BEAM-100K and not LongMemEval-S

| Dataset | Size | Best published | Verdict |
|---|---|---|---|
| LongMemEval-S | 500 Q | **HydraDB 90.79%** | ❌ vendor already saturated it |
| **BEAM-100K** | 20 dialogues, 400 Q | ~73% | ✅ **use this** |
| BEAM-10M | 100 conv, 2000 Q | ~64% | ❌ infeasible in 3 days |
| LongMemEval-V2 | 451 Q, up to 115M tokens | 72.5% | ❌ ingestion cost kills us |

Reference points on LongMemEval-S: HydraDB 90.79%, Supermemory 85.20%, Zep 71.2%, Mem0 29.07%.
Entering with an 84% there means shipping something *worse than the thing we built it on*,
in front of judges who work there.

BEAM-100K is right because:
- ~100K tokens/conversation matches the brief's stated "115,000 tokens per question"
- it scores **Abstention, Contradiction Resolution, Event Ordering, Knowledge Update,
  Temporal Reasoning** as *named separate categories* — that is our architecture, itemized
- it ships an official rubric judge prompt (1.0 / 0.5 / 0.0 scoring) so we don't invent a metric
- most teams will default to LongMemEval-S; choosing BEAM is itself a signal of judgment

Repo: `github.com/mohammadtavakoli78/BEAM` (ICLR 2026, "Beyond a Million Tokens", Tavakoli et al.)

---

## 4. Prerequisites — complete ALL of these before writing any code

### 4.1 Accounts and keys

- [ ] **HydraDB API key** — sign up at `app.hydradb.com`. Do this first; provisioning is async.
- [ ] **LLM provider key** with credit loaded. Budget **~$40–60 USD**. Use one provider.
      Recommended: OpenAI (`gpt-4.1-mini` for extraction/reconciliation, `gpt-4.1` for QA + judge).
- [ ] **Join the Hack Hydra Discord** — `discord.gg/D8cGSa9H9`. The repo is days old; the team
      runs office hours. Ask early rather than burning four hours.
- [ ] **Register on Luma** — `luma.com/h038glzk`
- [ ] **GitHub repo created, public, MIT LICENSE in the first commit.** Not later. First commit.

### 4.2 Local environment

- [ ] Python **3.10+** (3.11 recommended — the SDK requires ≥3.10)
- [ ] `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] `git` configured with your GitHub identity (`rabbive`)
- [ ] ~5 GB free disk (BEAM conversations + LLM response cache)
- [ ] Screen recorder for the demo (OBS, or QuickTime/macOS, or `ffmpeg`)

### 4.3 Data

- [ ] `git clone https://github.com/mohammadtavakoli78/BEAM` into `data/BEAM/`
- [ ] Locate the **100K bucket** conversations and the **official judge prompt**. Read their
      eval script before writing ours — match their protocol exactly or the numbers are worthless.
- [ ] Confirm which question categories carry ground-truth abstention labels.

### 4.4 ⚠️ The spike that must happen in hour one

Before designing anything, **measure ingestion throughput**:

```
1. Create a throwaway database. Poll databases.status until provisioned.
2. Ingest 10 memories in one call. Poll context.status until indexed.
3. Time it. Record: seconds per memory, seconds per batch call.
4. Run one query with graph_context=True. Confirm the graph comes back populated.
5. Ingest with a graph_payload. Confirm the triplet returns tagged origin: "byog".
```

**Everything downstream depends on this number.** If ingestion is 30s per source, our
dialogue count is decided for us. Do not plan the eval set before you know it.

---

## 5. HydraDB API reference (verified — do not deviate)

**Base URL:** `https://api.hydradb.com` · **Auth:** `Authorization: Bearer <key>` ·
**Header:** `API-Version: 2` · **Package:** `pip install hydradb-sdk` · **Import:** `hydra_db`

### 5.1 Client

```python
from hydra_db import HydraDB
client = HydraDB(token=os.environ["HYDRADB_API_KEY"], api_version="2", timeout=60.0)
```

Async twin: `AsyncHydraDB`, identical surface, `await` each call.
All responses are Pydantic envelopes — payload on `.data`, request metadata on `.meta`.

### 5.2 ⚠️ Database creation — THE critical gotcha

`metadata_filters` only works on fields **declared in the schema at creation time**.
We cannot add `status` later and filter on it. Declare it now:

```python
from hydra_db import TenantsCustomPropertyDefinition

client.databases.create(
    database="palimpsest",
    embeddings_dimension=1536,
    database_metadata_schema=[
        TenantsCustomPropertyDefinition(
            name="status", data_type="VARCHAR", max_length=16, enable_match=True),   # current | historical
        TenantsCustomPropertyDefinition(
            name="predicate", data_type="VARCHAR", max_length=128, enable_match=True),
        TenantsCustomPropertyDefinition(
            name="subject", data_type="VARCHAR", max_length=128, enable_match=True),
        TenantsCustomPropertyDefinition(
            name="session_idx", data_type="INT32"),
        TenantsCustomPropertyDefinition(
            name="dialogue_id", data_type="VARCHAR", max_length=64, enable_match=True),
    ],
)
```

Creation is **asynchronous** — poll `client.databases.status(database=...)` until provisioned
before ingesting. `data_type` options: `BOOL | INT8..INT64 | FLOAT | DOUBLE | VARCHAR | JSON | ARRAY`.

### 5.3 Ingest

```python
client.context.ingest(
    database="palimpsest",
    collection=dialogue_id,          # one collection per BEAM dialogue
    type="memory",
    memories=json.dumps([            # JSON array STRING, not a list
        {"id": "f_00123", "text": "User's manager is Priya Raghavan.", "infer": False}
    ]),
    graph_payload=json.dumps({...}), # keyed by the memory's id — see §6.2
    upsert="true",                   # form field is a STRING, not a bool
)
```

**Rules:**
- `memories` / `document_metadata` / `app_knowledge` / `graph_payload` are **JSON string** form fields.
- A memory **must carry an explicit `id`** to receive a graph payload. No id → server-generated → untargetable.
- The form field stays plural (`memories`) even when `type="memory"`.
- Use `infer: False`. We do our own extraction and reconciliation; we do not want the
  server reinterpreting facts we already resolved.
- **Batch aggressively** — many memories per call. This is our main throughput lever.

### 5.4 Query

```python
result = client.query(
    query=question,
    database="palimpsest",
    collection=dialogue_id,
    type="memory",                   # "knowledge" | "memory" | "all"
    query_by="hybrid",               # "hybrid" | "text"
    mode="thinking",                 # "fast" | "thinking" | "auto"
    operator="or",                   # "or" | "and" | "phrase"
    max_results=20,
    num_related_chunks=3,
    graph_context=True,
    recency_bias=0.2,
    metadata_filters={"status": "current"},
)
# result.data.chunks[*].chunk_content  -> feed to LLM
# result.data.graph_context.query_paths -> triplets, provenance
```

Also available: `ids=[...]` for a hard `source_id in [...]` pre-filter (returns empty rather
than widening — useful for slot checks), and `collections={"a": 1.0, "b": 0.5}` for weighted
multi-collection ranking.

### 5.5 Other endpoints we need

| Call | Purpose |
|---|---|
| `client.context.status(database=, ids=[...])` | Poll until indexed. **Required before querying.** |
| `client.context.relations(database=, collection=, id=, type="memory", limit=100, cursor=0)` | Read back graph triplets — powers the inspector UI |
| `client.context.update_source_metadata(id=, database=, collection=, tenant_metadata={"status":"historical"})` | Flip a superseded fact. `collection` is **required** by the server. Schema-declared fields go in `tenant_metadata`; free-form in `additional_metadata`. This endpoint **rejects** `document_metadata` (400). |
| `client.context.list(database=, type="memory", page=, page_size=)` | Enumerate facts |
| `client.context.delete(database=, ids=[...])` | Teardown between runs |

### 5.6 BYOG limits (per source)

| Limit | Value |
|---|---|
| Entities | ≤ 5,000 |
| Relations | ≤ 10,000 |
| Relations per entity (degree) | ≤ 500 |
| `context` length | ≤ 2,000 chars |
| `name` / `predicate` length | ≤ 256 chars |

Since we use **one memory per fact**, each payload holds 2–4 entities and 1–2 relations.
We are nowhere near these caps. Entity names are lowercase-normalized server-side.
BYOG is **replace mode, bulk only** — no per-triple update. Graphs persist across re-ingest.

### 5.7 Errors

`ApiError` subclasses: `BadRequestError` 400, `ForbiddenError` 403, `NotFoundError` 404,
`ConflictError` 409, `UnprocessableEntityError` 422, `InternalServerError` 500.
Each carries `.status_code` and `.body`. Per-call override:
`request_options={"timeout_in_seconds": 30, "max_retries": 3}`.

---

## 6. Data model

### 6.1 The Fact (Pydantic, and the SQLite ledger schema)

```python
class Fact(BaseModel):
    id: str                    # "f_{dialogue}_{seq}"
    dialogue_id: str
    session_idx: int           # ordinal position in the conversation
    session_ts: str            # ISO8601 from the dialogue, if present
    subject: str               # normalized lowercase
    predicate: str             # from a CLOSED vocabulary — see §6.3
    object: str
    polarity: Literal["affirm", "negate"]
    source_span: str           # verbatim quote — provenance, never paraphrase
    status: Literal["current", "historical"] = "current"
    superseded_by: str | None = None
    supersedes: str | None = None
    confidence: float
```

**One HydraDB memory per Fact.** This is deliberate: `update_source_metadata` is per-source,
so per-fact granularity is the only way `status` filtering works. Session-level sources
would make status meaningless (a session holds both live and dead facts).

### 6.2 The BYOG payload for one fact

```json
{
  "f_d01_0042": {
    "entities": {
      "user":     {"name": "User",            "type": "PERSON",  "namespace": "people"},
      "priya":    {"name": "Priya Raghavan",  "type": "PERSON",  "namespace": "people"},
      "prior":    {"name": "Marcus Webb",     "type": "PERSON",  "namespace": "people"}
    },
    "relations": [
      {"source": "user", "target": "priya", "predicate": "REPORTS_TO",
       "context": "User mentioned Priya Raghavan is now their manager.",
       "temporal_details": "session 12, 2024-07-03"},
      {"source": "priya", "target": "prior", "predicate": "SUPERSEDES",
       "context": "Replaces the earlier manager fact from session 4.",
       "temporal_details": "supersedes f_d01_0009 at session 12"}
    ]
  }
}
```

### 6.3 Closed predicate vocabulary

Free-form predicates destroy slot matching. Fix a vocabulary of ~25–40 predicates up front,
derived from a skim of 2 BEAM dialogues. Force the extractor to choose from the list or emit
`OTHER`. Examples: `LIVES_IN`, `WORKS_AT`, `REPORTS_TO`, `OWNS`, `PREFERS`, `DISLIKES`,
`SCHEDULED_FOR`, `USES_TOOL`, `HAS_DEADLINE`, `ATTENDED`, `DECIDED`, `RECOMMENDED`.

Store it in `src/palimpsest/vocab.py`. This file is load-bearing for the abstention logic.

### 6.4 Local SQLite ledger — be honest about this in the README

HydraDB has no traversal query language. Supersession chain walking, the ablation switches,
and the inspector UI all need cheap local reads. So we mirror the fact ledger in SQLite.

**The honest framing (write this in the README):** HydraDB is the retrieval substrate —
hybrid search, graph context, metadata-scoped recall, and the persisted context graph. The
SQLite ledger is the write-time reconciliation *record* that produces the supersession edges
we push into HydraDB. **Every answer path goes through `client.query()`.** We never answer
from SQLite. Judges respect a clear division of labour more than an overclaim, and
"HydraDB not used meaningfully" is an explicit disqualifier.

---

## 7. Write path

Process sessions in **strict chronological order**. For each session:

**Step 1 — Extract.** One LLM call per session. Structured output → `list[Fact]`.
Predicate must come from the closed vocabulary. `source_span` must be verbatim.

**Step 2 — Reconcile.** For each candidate fact, query HydraDB for existing facts on the
same `(subject, predicate)` slot, plus the SQLite ledger. Classify into exactly one bucket:

| Label | Condition | Action |
|---|---|---|
| `NEW` | no prior fact on this slot | write it |
| `DUPLICATE` | same value | drop — this is our defense against duplicate memory records |
| `REFINEMENT` | strictly more specific ("India" → "Coimbatore") | write new, mark old `historical`, edge `REFINES` |
| `SUPERSESSION` | same slot, different value, later timestamp | write new, mark old `historical`, edge `SUPERSEDES` |
| `CONTRADICTION` | incompatible, no clear temporal ordering | write new, keep **both** `current`, edge `CONTRADICTS`, flag for read-path handling |

The classifier is the highest-leverage component in the project. Build it and test it first
on hand-labelled pairs before wiring the rest.

**Step 3 — Write.** Batch-ingest new facts with `infer: False` and their BYOG payloads.

**Step 4 — Flip.** `update_source_metadata` on every superseded fact → `status: "historical"`.
Never delete. The palimpsest stays readable.

---

## 8. Read path

**Step 1 — Classify intent** (one cheap LLM call, or rules where possible):

| Intent | Retrieval strategy |
|---|---|
| `CURRENT` | `metadata_filters={"status": "current"}` |
| `AS_OF` ("what did I say in March") | temporal window + walk supersession chains backward |
| `ORDERING` | return the chain itself — the chain **is** the event ordering |
| `AGGREGATE` | multi-slot query, no status filter, synthesize |

**Step 2 — Premise / coverage check.** Decompose the question into required
`(entity, predicate)` slots. Query each against the graph.

```
required_slots = decompose(question)
coverage = {slot: graph_has_edge(slot) for slot in required_slots}
if any(not covered for covered in coverage.values()):
    return Abstention(
        missing_slots=[s for s, c in coverage.items() if not c],
        reason="No fact in memory covers <slot>",
        evidence=partial_matches,
    )
```

Abstentions are **structured objects with a named missing slot**, not a polite sentence.
That is the demo moment.

**Step 3 — Answer** from `chunks[*].chunk_content` plus `graph_context.query_paths`.
Attach the traversal path as provenance on every answer.

---

## 9. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | SDK requires ≥3.10 |
| Env / deps | `uv` | fast, lockfile, reproducible for judges |
| Memory substrate | `hydradb-sdk` 2.1.2 | the point of the hackathon |
| LLM calls | `litellm` | provider swap without a rewrite if we hit rate limits |
| Schemas | `pydantic` v2 | structured extraction output, typed everywhere |
| Ledger | `sqlite3` (stdlib) | zero deps, judges can open the file |
| LLM cache | `diskcache` | **non-negotiable — see §12** |
| CLI | `typer` | `palimpsest ingest`, `eval`, `ask` |
| Progress | `rich` | you will stare at these bars for 8 hours |
| Config | `python-dotenv` | `.env` + committed `.env.example` |
| Concurrency | `asyncio` + `AsyncHydraDB` | ingestion is I/O-bound; this is the throughput lever |
| Retries | `tenacity` | 429s and 500s will happen |
| Inspector (Day 3, optional) | `fastapi` + one static HTML page | do NOT build a real frontend |
| Tests | `pytest` | ~6 tests on the reconciliation classifier only |

**Do not add:** LangChain, LlamaIndex, a vector DB, Docker, a React app, a database migration
tool. Every one of these costs hours we do not have and adds nothing a judge will score.

---

## 10. Repo layout

```
palimpsest/
├── LICENSE                      # MIT — FIRST COMMIT
├── README.md                    # §13.2 skeleton
├── pyproject.toml
├── uv.lock
├── .env.example                 # HYDRADB_API_KEY=, OPENAI_API_KEY=
├── .gitignore                   # .env, data/, .cache/, results/raw/
├── Makefile                     # make setup / spike / ingest / eval / demo
├── src/palimpsest/
│   ├── config.py                # settings, model names, DB name
│   ├── vocab.py                 # closed predicate vocabulary  ← load-bearing
│   ├── models.py                # Fact, Abstention, Answer, EvalResult
│   ├── hydra.py                 # ALL HydraDB calls live here. One wrapper. No exceptions.
│   ├── ledger.py                # SQLite: facts, chains, current-view
│   ├── extract.py               # session -> list[Fact]
│   ├── reconcile.py             # the 5-way classifier  ← build and test FIRST
│   ├── write_path.py            # orchestration: extract -> reconcile -> ingest -> flip
│   ├── read_path.py             # intent -> retrieve -> coverage check -> answer
│   ├── coverage.py              # slot decomposition + premise check
│   └── cli.py
├── eval/
│   ├── beam_loader.py           # parse BEAM-100K, subset selection
│   ├── judge.py                 # BEAM's OFFICIAL rubric prompt — do not invent one
│   ├── run_eval.py              # arms A / B / C + ablations
│   └── report.py                # markdown tables into results/
├── results/
│   ├── main_table.md
│   ├── ablation.md
│   └── cost_latency.md
├── inspector/                   # Day 3 only, if time survives
│   ├── app.py
│   └── static/index.html
└── tests/
    └── test_reconcile.py        # ~6 hand-labelled pairs
```

---

## 11. Milestones

### Day 0 — Aug 17 (today, remaining hours)

| Hrs | Task | Done when |
|---|---|---|
| 1 | All of §4 prerequisites | key in hand, repo public with LICENSE |
| 1 | **§4.4 ingestion spike** | you can state seconds-per-memory out loud |
| 1 | Create DB with the §5.2 schema, confirm provisioned | `databases.status` returns ready |
| 1 | Clone BEAM, read their eval script + judge prompt | you know their scoring protocol |
| 1 | Skim 2 dialogues → draft `vocab.py` | 25–40 predicates committed |
| 1 | **Freeze the eval subset.** 5–8 dialogues, ~120–160 Q, weighted to Abstention / Contradiction Resolution / Knowledge Update / Temporal Reasoning / Event Ordering | subset ids written into `eval/beam_loader.py` and the README |

### Day 1 — Aug 18: the write path (hardest day, protect it)

| Hrs | Task |
|---|---|
| 3 | `extract.py` — structured extraction, closed vocab, verbatim spans |
| 4 | **`reconcile.py`** — the 5-way classifier + `tests/test_reconcile.py` |
| 3 | `hydra.py` + `ledger.py` — batched async ingest, BYOG payloads, status flipping |
| 2 | Full write path over **one** dialogue end to end |
| 1 | Verify: `context.relations` returns supersession edges; `status` filter actually filters |

**Day 1 exit gate:** one dialogue fully ingested, and a query with
`metadata_filters={"status":"current"}` returns the *new* manager, not the old one.
If this doesn't work, stop and fix it — nothing downstream matters.

### Day 2 — Aug 19 morning/afternoon: the read path + eval

| Hrs | Task |
|---|---|
| 2 | `read_path.py` — intent classification, three retrieval strategies |
| 3 | `coverage.py` — slot decomposition, premise check, structured `Abstention` |
| 2 | `eval/` — arms A (full-context stuffing), B (HydraDB default auto-extraction), C (PALIMPSEST) |
| 3 | Ingest the remaining dialogues, run the full eval |
| 2 | Ablations: reconciliation off, coverage check off, both off |

**Arm B is the one that matters.** A vs C proves the graph earns its keep. **B vs C isolates
what *we* built** — without it, a judge cannot tell whether we engineered anything or just
called an API competently.

### Day 2 evening — FEATURE FREEZE (non-negotiable)

Their own closing advice: *"Stop adding features before the deadline. Test what you already built."*

| Hrs | Task |
|---|---|
| 2 | Minimal inspector UI — timeline, superseded facts struck through, supersession edge drawn |
| 1 | `results/*.md` tables generated |

### Day 3 — Aug 20: ship

| Hrs | Task |
|---|---|
| 3 | README (§13.2), honest limitations section |
| 1 | **Clean-clone test.** Fresh directory, follow your own setup steps, confirm they work. |
| 2 | Record + edit demo video (§13.3) |
| 1 | Upload video, verify the link opens in a logged-out incognito window |
| 1 | Submit the Google Form |

**Submit by mid-morning IST on Aug 21, not at the buzzer.**

---

## 12. Cost and throughput controls

**Cache every LLM call to disk, keyed by a hash of (model, prompt, params).** You will
re-run the pipeline twenty times. Paying twice for the same extraction is the classic way a
student burns a hackathon budget. Wire `diskcache` in on hour one, before the first LLM call.

- Extraction + reconciliation + intent + slot decomposition → **cheap model** (`gpt-4.1-mini` class)
- Final answer generation + judge → **strong model** (`gpt-4.1` class)
- Batch memories per `ingest` call; run ingestion under `asyncio` with a semaphore (start at 5)
- Track spend in a running log; if you cross **$45**, cut dialogues, not rigor

Estimated total: **$25–50** with caching, **$150+** without.

---

## 13. Submission

### 13.1 Disqualifier checklist — most losses are paperwork, not weak projects

- [ ] Repo public, opens without an access request
- [ ] Open-source LICENSE file present
- [ ] No commits before Aug 12, 2026
- [ ] README explains the project clearly
- [ ] Setup instructions actually work from a clean clone (**test this, don't assume**)
- [ ] HydraDB usage clearly explained — where it's used, what we'd lose without it
- [ ] Demo video ≤ 3:00, link opens logged-out
- [ ] Dependencies and environment documented
- [ ] Attribution: BEAM (Tavakoli et al., ICLR 2026), HydraDB, any borrowed code
- [ ] Form submitted before 11:59 PM PT Aug 20

### 13.2 README skeleton

```
# PALIMPSEST
One-line: the write-time reconciliation and abstention layer for HydraDB memory.

## The problem
Supersession edges are labels. Something has to enforce them. (2 short paras)

## What we built
Write-time reconciliation · materialized current view · graph-property abstention

## Results
Main table: arms A / B / C, per BEAM category
Ablation table
Cost + latency table
Honest note on subset size and why

## How we use HydraDB
- Memories corpus, one memory per fact, infer=False
- BYOG graph_payload: supersession chains with temporal_details
- Schema-declared `status` metadata → deterministic current-view filtering
- Hybrid query + graph_context for retrieval and provenance
- What this project would lose without HydraDB: <specific, honest answer>

## Architecture
Diagram + the SQLite-ledger division of labour, stated plainly

## Setup
Prereqs, .env, uv sync, make ingest, make eval

## Limitations
Say them out loud. Judges trust projects that know their own edges.

## Attribution
```

### 13.3 Demo video — their required order, exactly

| Time | Section | Content |
|---|---|---|
| 0:00–0:30 | **The problem** | Superseded facts. Show a model confidently returning a stale answer. |
| 0:30–1:00 | **The project** | Write-time reconciliation + abstention as a graph property. |
| 1:00–2:15 | **The demo** | Inspector: scrub the timeline, watch a fact get struck through. Then ask an unanswerable question and show the structured abstention naming the missing slot. Then the results table. |
| 2:15–3:00 | **HydraDB** | Where it's used and why it matters. Be specific: BYOG, `status` filtering, `graph_context` provenance. |

Anything after 3:00 may not be reviewed. Record Aug 20 morning, not Aug 20 night.

---

## 14. Risk register

| Risk | Mitigation |
|---|---|
| Ingestion too slow to fit the subset | Measured in hour one (§4.4). Cut dialogues, keep category coverage. |
| `metadata_filters` won't filter on `status` | **Verify Day 0.** Fallback: filter client-side from `context.list` + `ids=[...]` pre-filter on query. Slower, still honest. |
| Reconciliation classifier is noisy | Hand-label 20 pairs Day 1 morning. Report classifier accuracy in the README — a known error rate beats a hidden one. |
| Repo is days old, API has bugs | Discord first, not four hours of solo debugging. |
| Eval doesn't finish | Ship partial results with an explicit "N of M dialogues" note. Partial + honest > nothing. |
| Scope creep | Feature freeze Aug 19 evening. Written down. Obey it. |

---

## 15. Definition of done

We ship when all of these are true:

1. Write path runs end to end over the frozen subset
2. A query with `status="current"` provably returns the live fact, not the superseded one
3. The premise check produces structured abstentions with named missing slots
4. Three eval arms + one ablation table exist in `results/`
5. Cost and latency are reported next to accuracy
6. Every §13.1 box is ticked
7. Setup instructions verified from a clean clone

Not on the list: a polished UI, full BEAM coverage, beating SOTA. **A working, honest,
well-scoped system beats an ambitious broken one** — their judging page says so in as many
words: *"We care about working, thoughtful products, not just benchmark scores."*

---

## Appendix A — Key URLs

| Resource | URL |
|---|---|
| Hackathon site | `hackhydra.hydradb.com` |
| Submission form | `forms.gle/GrMYKxLj9zPQcqqc8` |
| Discord | `discord.gg/D8cGSa9H9` |
| HydraDB docs index (for agents) | `https://docs.hydradb.com/llms.txt` |
| Agent integration guide | `https://docs.hydradb.com/AGENTS.md` |
| OpenAPI spec | `https://docs.hydradb.com/api-reference/v2/openapi.json` |
| BYOG reference | `https://docs.hydradb.com/essentials/v2/bring-your-own-graph.md` |
| Python SDK | `pip install hydradb-sdk` · `https://pypi.org/project/hydradb-sdk/` |
| BEAM dataset | `github.com/mohammadtavakoli78/BEAM` |
| HydraDB benchmarks | `benchmarks.hydradb.com` |

## Appendix B — First five commands

```bash
git init palimpsest && cd palimpsest
curl -o LICENSE https://raw.githubusercontent.com/licenses/license-templates/main/templates/mit.txt
git add LICENSE && git commit -m "MIT license"        # first commit, dated after Aug 12

uv init --python 3.11
uv add hydradb-sdk litellm pydantic typer rich python-dotenv diskcache tenacity
uv add --dev pytest

# then: the §4.4 spike, before anything else
```
