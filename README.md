# PALIMPSEST

The write-time reconciliation and abstention layer for HydraDB memory.

## The problem

HydraDB ships an append-only, Git-style temporal graph with versioned edges. A
`SUPERSEDES` edge is just a label — nothing in the store makes the old fact behave
as historical. Application code has to enforce that on every single read, or a
"what is my manager's name" query can return a fact that stopped being true three
sessions ago. Vector-store memory has a second, sharper problem: it always returns
top-k, so its floor is "least-bad match", never "absent" — it cannot say it doesn't
know something.

PALIMPSEST is the layer HydraDB deliberately does not ship: supersession resolved
at write time (not re-derived per query), and abstention as a graph property (not a
model's judgment call).

## What we built

- **Write-time reconciliation** — a 5-way classifier (NEW / DUPLICATE / REFINEMENT /
  SUPERSESSION / CONTRADICTION) that runs on every candidate fact before it's
  written, and flips superseded facts' `status` metadata to `historical` immediately.
- **Materialized current view** — `metadata_filters={"status": "current"}` is a hard,
  deterministic filter on HydraDB's own query path. No re-ranking, no re-deriving.
- **Graph-property abstention** — decompose a question into required
  `(entity, predicate)` slots, check coverage against the graph, and abstain with a
  named missing slot when coverage is zero. We can prove absence; a vector store can't.

## Results

See `results/main_table.md` (arms A/B/C x BEAM category), `results/ablation.md`, and
`results/cost_latency.md` once `make eval && make report` has been run against a
provisioned HydraDB database and a live LLM key.

**Honest note on subset size:** the frozen eval subset is 8 of 20 BEAM-100K
dialogues (`eval/beam_loader.py::FROZEN_SUBSET`), weighted toward the categories our
architecture targets (Abstention, Contradiction Resolution, Knowledge Update,
Temporal Reasoning, Event Ordering) rather than the full 20-dialogue set, to fit the
time and API-cost budget of a solo 90-hour build.

## How we use HydraDB

- Memories corpus, **one memory per Fact**, `infer=False` — we do our own extraction
  and reconciliation, so we don't want the server reinterpreting facts we already
  resolved.
- BYOG `graph_payload`: every fact carries its own subject/object entities and a
  `REFINES` / `SUPERSEDES` / `CONTRADICTS` edge back to the fact it replaces, with
  `temporal_details` naming the session it happened at.
- Schema-declared `status` metadata (declared at `databases.create` time, per the
  SDK's hard constraint that `metadata_filters` only works on schema-declared
  fields) → deterministic current-view filtering on every read.
- Hybrid query (`query_by="hybrid"`) + `graph_context=True` for retrieval and
  provenance (`query_paths` becomes the answer's citation trail).
- **What this project would lose without HydraDB:** the persisted, queryable graph
  and the schema-declared metadata filter. Without them we'd be re-deriving "what's
  current" from the SQLite ledger on every read — which is exactly the read-time
  reconciliation this project argues against.

## Architecture

```
write path:  session -> extract.py (LLM) -> reconcile.py (5-way classifier)
             -> ledger.py (SQLite record) -> hydra.py (ingest + BYOG + flip)

read path:   question -> read_path.py (intent) -> coverage.py (premise check)
             -> hydra.query() -> answer, or a structured Abstention
```

SQLite (`ledger.py`) is the write-time reconciliation *record* — supersession-chain
walking, ablation switches, and inspector reads all hit it because HydraDB has no
traversal query language. **Every answer path goes through `hydra.query()`; we never
answer from SQLite.**

## Setup

```bash
uv sync
cp .env.example .env   # fill in HYDRADB_API_KEY, LLM_API_KEY
make setup              # clones BEAM into data/BEAM/ if not already present
uv run palimpsest spike       # §4.4 ingestion throughput spike
uv run palimpsest create-db   # provision the palimpsest database
make ingest              # write path over the frozen eval subset
make eval                # arms A/B/C + ablations
make report              # results/*.md
```

## Limitations

- Extraction and reconciliation are single LLM calls per session/pair — no
  multi-pass self-consistency, so classifier noise is possible on ambiguous pairs
  (see `tests/test_reconcile.py` for the hand-labelled accuracy check).
- Eval subset is 8/20 100K dialogues, not the full bucket (see above).
- No traversal query language in HydraDB means chain-walking and the inspector UI
  read from a local SQLite mirror, not the store itself — stated plainly rather than
  hidden, per the project's own thesis about honest division of labour.
- Closed predicate vocabulary (`src/palimpsest/vocab.py`) was derived from a skim of
  two BEAM-100K dialogues; it may miss predicates that appear in dialogues outside
  the frozen subset, which would fall through to `OTHER` and reduce slot-matching
  precision for those facts.

## Attribution

- BEAM benchmark: Tavakoli et al., *"Beyond a Million Tokens"*, ICLR 2026.
  `github.com/mohammadtavakoli78/BEAM`. The rubric judge prompt in `eval/judge.py`
  is copied verbatim from BEAM's `src/prompts.py::unified_llm_judge_base_prompt`.
- HydraDB: `hydradb-sdk` 2.1.2, `docs.hydradb.com`.
