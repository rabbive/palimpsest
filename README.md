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

## Live demo

[Open the interactive GitHub Pages demo](https://rabbive.github.io/palimpsest/)

The demo is a deterministic browser replay of verified PALIMPSEST outputs. It contains no API keys and does not make live HydraDB requests from the browser; the production write/read path remains in this repository.

## Results

`make eval && make report` writes four tables into `results/`, against a provisioned
HydraDB database and a live LLM key:

| File | Contents |
|---|---|
| `main_table.md` | arms A / B / C x BEAM category, plus abstention rate measured in both directions |
| `ablation.md` | arm C against its three read-path ablations |
| `cost_latency.md` | judge score, mean and p90 latency, cost per question, and errored runs per arm |
| `classifier_accuracy.md` | the 5-way classifier scored against 20 hand-labelled pairs |

**The arms.** A is full-context stuffing with no HydraDB at all. B is HydraDB's own
auto-extraction (`infer=True`) with no reconciliation and no coverage check. C is
PALIMPSEST. **B vs C is the load-bearing comparison** — it isolates what we engineered
rather than what the vendor's API already does.

**The ablations** switch off exactly one read-path mechanism each, against the *same*
ingested corpus as arm C, so a difference is attributable to the mechanism rather than
to a different write pass:

- `C_no_status_filter` — the materialized current view off. The `SUPERSEDES` edges are
  still sent and the metadata is still flipped; the reader just stops enforcing it.
  This is precisely the read-time reconciliation this project argues against, so it is
  the number that tests claim 1. (What the arm actually varies is the metadata filter,
  which is just as well given the edges turn out not to be readable — see the BYOG
  limitation below.)
- `C_no_coverage` — graph-property abstention off, testing claim 2.
- `C_neither` — both off.

**Abstention is reported in both directions.** Abstaining on BEAM's abstention questions
is correct; the same behaviour on an answerable question is a false abstention. A system
that abstained on everything would look perfect on the first number and useless on the
second, so both are printed side by side.

**Running an evaluation is resumable.** Every result is appended to
`results/raw_eval.jsonl` the moment it lands, each question is bounded by its own
timeout, and a failure is recorded as a row rather than killing the run. Re-running
skips what already succeeded and retries only what errored. This is not incidental
polish: the first full evaluation attempt was a single sequential pass that wrote its
output only at the end, and a 30-minute timeout destroyed all of it.

**Honest note on subset size:** the frozen eval subset is 8 of 20 BEAM-100K
dialogues (`eval/beam_loader.py::FROZEN_SUBSET`), weighted toward the categories our
architecture targets (Abstention, Contradiction Resolution, Knowledge Update,
Temporal Reasoning, Event Ordering) rather than the full 20-dialogue set, to fit the
time and API-cost budget of a solo 90-hour build.

The frozen subset is what we *intended* to evaluate; the tables report what we
*did*. Every generated table prints its own coverage line — how many questions, which
dialogue ids, how many arm-runs errored — so a run over fewer dialogues than the
frozen subset reports as exactly that. Check `results/main_table.md` for the dialogues
behind any number quoted here, and `uv run palimpsest status` for what is ingested
locally.

### What the results actually show

**Arm C does not win.** Over 20 questions on dialogues 7 and 8, all 120 arm-runs
scoring without error: A (full-context stuffing) **0.46**, B (HydraDB `infer=True`)
**0.34**, C (PALIMPSEST) **0.31**. The B-vs-C comparison this project called
load-bearing goes against the thesis at this sample size.

The cause is legible in the rows rather than mysterious. Arm C abstains on **56% of
answerable questions**. Split C's non-abstention questions by what it did: when C
answers, it averages **0.41**; when it abstains on an answerable question, it averages
**0.03**. So C's deficit is almost entirely over-abstention, not wrong answers.

The abstentions are slot-matching failures, not retrieval failures. The read path
decomposes a question into `(entity, predicate)` slots and abstains when a slot is
uncovered, and BEAM's derived questions do not decompose cleanly — "How many days
between finishing my first draft and my goal to improve my essay grades?" becomes
`my first draft / COMPLETED_PROJECT` + `my goal to improve my essay grades / HAS_GOAL`
and abstains, as does "When is my Zoom call with the creative director scheduled?" on
`my zoom call with the creative director / SCHEDULED_FOR`. The mechanism does what it
was designed to do; the design demands an exact slot hit for question shapes that are
multi-hop or phrased away from the closed predicate vocabulary. That is the same
slot-matching precision limitation listed below, and this is what it costs.

The ablations agree. Turning the abstention mechanism **off** (`C_no_coverage`, 0.34)
scores *higher* than full C (0.31) — claim 2's mechanism is net-negative as tuned.
Turning both mechanisms off (0.21) is worst, so the machinery is not worthless; the
abstention gate is simply mistuned for these question shapes. Arm C is also the
cheapest arm by a wide margin: $0.0449 per question against arm A's $0.3107, roughly
7× less for the transcript-stuffing baseline that beats it.

These numbers come from 20 questions on 2 dialogues, n=4 per category cell — small
enough that per-category figures are noisy and should not be read as rankings. The
overall column and the abstention split are the parts with enough rows to lean on.
The result is reported as measured; no arm was retuned after seeing it.

## How we use HydraDB

- Memories corpus, **one memory per Fact**, `infer=False` — we do our own extraction
  and reconciliation, so we don't want the server reinterpreting facts we already
  resolved.
- BYOG `graph_payload`: every fact is sent with its own subject/object entities and a
  `REFINES` / `SUPERSEDES` / `CONTRADICTS` edge back to the fact it replaces, with
  `temporal_details` naming the session it happened at. **These edges are not
  readable back out** — see the BYOG limitation below.
- Schema-declared `status` metadata (declared at `databases.create` time, per the
  SDK's hard constraint that `metadata_filters` only works on schema-declared
  fields) → deterministic current-view filtering on every read.
- Hybrid query (`query_by="hybrid"`) + `graph_context=True` for retrieval and
  provenance (`query_paths` becomes the answer's citation trail).
- **What this project would lose without HydraDB:** the schema-declared metadata
  filter above all — without it we'd be re-deriving "what's current" from the SQLite
  ledger on every read, which is exactly the read-time reconciliation this project
  argues against. The persisted graph was meant to carry the same weight, but on the
  evidence below we never got our own edges back out of it.

## Architecture

```
write path:  session -> extract.py (LLM) -> reconcile.py (5-way classifier)
             -> ledger.py (SQLite record) -> hydra.py (ingest + BYOG + flip)

read path:   question -> read_path.py (intent) -> coverage.py (premise check)
             -> hydra.query() -> answer, or a structured Abstention
```

### Inspecting it

```bash
uv run palimpsest status          # local fact counts and the HydraDB outbox, no network
uv run palimpsest timeline 8      # every fact in session order, superseded ones struck through
uv run palimpsest verify 8        # prove the current-view contract against the live database
uv run palimpsest ask 8 "What is my current manager?"
```

`verify` is the Day-1 exit gate kept runnable: it picks a fact that was actually
superseded, shows that it is absent under `metadata_filters={"status": "current"}`,
and that its replacement is present. It also prints whatever `context.relations()`
returns for the replacement, which is currently empty — see the BYOG limitation
below. Asserted contracts rot; a command that re-proves one does not.

SQLite (`ledger.py`) is the write-time reconciliation *record* — supersession-chain
walking, ablation switches, and inspector reads all hit it because HydraDB has no
traversal query language. **Every answer path goes through `hydra.query()`; we never
answer from SQLite.**

## Setup

```bash
uv sync
cp .env.example .env    # fill in HYDRADB_API_KEY, LLM_API_KEY
make setup              # clones BEAM into data/BEAM/ if not already present
uv run palimpsest spike       # §4.4 ingestion throughput spike
uv run palimpsest create-db   # provision the palimpsest database
make ingest             # write path over the frozen eval subset
make setup-arm-b        # one-time: provision arm B's separate database and corpus
make eval-smoke         # one question per category — proves the harness before spending
make eval               # arms A/B/C + the three ablations, resumable
make report             # results/*.md
make test               # pytest
```

`make eval` does **not** re-run the write path by default. Re-ingesting an
already-ingested dialogue re-enters HydraDB's asynchronous queue for no benefit, and a
queue incident during evaluation is exactly how the first run lost its output. Pass
`--ingest` when the database is genuinely empty.

**Arm B needs a one-time setup.** It lives in its own database (`<database>_arm_b`)
because it ingests raw sessions with `infer=True` — letting HydraDB do its own
extraction. Mixing that into arm C's database would contaminate the corpus being
measured. Run `make setup-arm-b` (or `palimpsest setup-arm-b 7 8`) once per dialogue.
An evaluation that includes arm B refuses to start when that corpus is missing, rather
than spending arm A and arm C budget on questions arm B cannot answer.

## Limitations

- Extraction and reconciliation are single LLM calls per session/pair — no
  multi-pass self-consistency, so classifier noise is possible on ambiguous pairs.
  The classifier's measured error rate is in `results/classifier_accuracy.md`,
  regenerated by `uv run palimpsest classifier-accuracy` over the 20 hand-labelled
  pairs in `eval/labelled_pairs.py`. Most of the error sits on the
  SUPERSESSION / CONTRADICTION boundary, which is the genuinely hard call: pairs
  testing it are marked `hard` and kept in the set deliberately. A known error rate
  beats a hidden one.
- **The BYOG graph edges cannot be read back.** The write path sends a
  `graph_payload` with every fact, and HydraDB accepts it — the ingest response
  reports `relations_created=None` and `relations_error=None`, i.e. neither a count
  nor an error. But `context.relations()` returns zero relations for every source in
  the arm-C database, on every read shape tried (`type="memory"` and `"knowledge"`,
  with and without a collection, with and without an `id`). The same call against the
  arm-B database, whose sources were ingested with `infer=True` and went through the
  server's own `graph_creation` stage, returns 21 relations for dialogue 7 and 16 for
  dialogue 8. So the graph machinery works; the supplied `graph_payload` is silently
  ignored on `infer=False` memory ingests. Reproduced on a fresh throwaway collection,
  so it is not corpus damage. **Consequence:** the supersession edge is a claim this
  project makes in its write path and cannot currently demonstrate through HydraDB's
  read path. The current-view contract that `verify` proves does not depend on it — it
  rests on schema-declared `status` metadata filtering, which does work — and neither
  does any answer path, since `query_paths` provenance and the SQLite ledger carry the
  chain. Untangling whether this is a payload-shape mismatch or a server-side gap was
  out of scope under feature freeze.
- Eval subset is 8/20 100K dialogues, not the full bucket (see above).
- No traversal query language in HydraDB means chain-walking and the inspector UI
  read from a local SQLite mirror, not the store itself — stated plainly rather than
  hidden, per the project's own thesis about honest division of labour.
- HydraDB can leave individual asynchronous ingestion sources queued even after the
  request is accepted. The write path uses small batches, bounded polling, retries
  only for queued IDs, and a SQLite `hydra_pending` outbox; persistent stragglers are
  not marked current until indexing completes. Re-upserting a stuck ID does not reset
  its queue state, so recovery goes through deterministic `r1_<canonical_id>` source
  aliases held in the ledger — see `docs/INGESTION_OPERATIONS.md`.
- HydraDB query reads can also time out. The read path issues one query per coverage
  slot plus one for the answer, so reads deliberately get a much smaller retry budget
  than writes (`PALIMPSEST_HYDRA_QUERY_ATTEMPTS=2`): a dropped write costs an
  extraction to redo, a dropped read costs one question.
- Reported cost counts money actually spent. A disk-cache hit is billed at zero, so a
  cost column reflects the run that populated the cache rather than a re-run of it.
- Closed predicate vocabulary (`src/palimpsest/vocab.py`) was derived from a skim of
  two BEAM-100K dialogues; it may miss predicates that appear in dialogues outside
  the frozen subset, which would fall through to `OTHER` and reduce slot-matching
  precision for those facts.

## Attribution

- BEAM benchmark: Tavakoli et al., *"Beyond a Million Tokens"*, ICLR 2026.
  `github.com/mohammadtavakoli78/BEAM`. The rubric judge prompt in `eval/judge.py`
  is copied verbatim from BEAM's `src/prompts.py::unified_llm_judge_base_prompt`.
- HydraDB: `hydradb-sdk` 2.1.2, `docs.hydradb.com`.
