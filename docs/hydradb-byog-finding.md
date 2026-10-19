# HydraDB: graph_payload on infer=False memory ingests

## Summary

PALIMPSEST sends a `graph_payload` with each `type=memory`, `infer=False` ingest. HydraDB accepts it without error. Afterwards `context.relations()` returned no relations for those sources, while sources ingested with `infer=True` returned 21 and 16 relations. We checked our payload against HydraDB's documented shape and it matches. We do not yet know whether the edges are missing or only missing from `context.relations()`, because we had not read them back through `/query` `graph_context`, where the docs say BYOG edges appear with `origin: "byog"`. The repro below does both reads. It has not been run yet. This is a request for clarification, not a bug claim.

Environment: `hydradb-sdk 2.1.2`, API version 2, written 2026-10-19.

**Question for HydraDB: is `graph_payload` supported on `infer=False` memory ingests, and if so, what shape does it expect and where should the edges be readable?**

## Payload shape check

Question: is our `graph_payload` wrong, or does HydraDB drop a correct one? Checked before reporting anything to HydraDB.

Result: our shape matches HydraDB's documented shape field for field. No code change was needed.

Sources:

- BYOG guide, section "Using BYOG without Cypher": https://docs.hydradb.com/essentials/v2/bring-your-own-graph.md
- Ingest endpoint, accordion "Bring your own graph" and its field table: https://docs.hydradb.com/api-reference/v2/endpoint/ingest-context.md
- OpenAPI spec, `POST /context/ingest` and `ingestion.V2IngestResultItem`: https://docs.hydradb.com/api-reference/v2/openapi.json
- Installed SDK `hydradb-sdk` 2.1.2: `hydra_db/context/client.py` (`ingest`), `hydra_db/types/ingestion_v2source_upload_result_item.py`. The SDK types `graph_payload` as a plain `str` and says nothing more. Its docstring for `relations_created` ("Number of graph relations extracted from this file") also omits the OpenAPI caveat "type=knowledge only", which is a likely source of our earlier misreading.

Our payload is built by `write_path._byog_payload` and sent by `hydra.ingest_facts` as `context.ingest(type="memory", upsert="true", memories=json.dumps(...), graph_payload=json.dumps(...))`. Printed offline by `build_payloads()` in `scripts/repro_byog_infer_false.py`, for a synthetic pair: "user lives in chennai." (`mem-a`) superseded by "user lives in bangalore." (`mem-b`). No network calls:

```json
{
  "mem-a": {
    "entities": {
      "subject": {
        "name": "user",
        "type": "ENTITY",
        "namespace": "palimpsest"
      },
      "object": {
        "name": "chennai",
        "type": "ENTITY",
        "namespace": "palimpsest"
      }
    },
    "relations": [
      {
        "source": "subject",
        "target": "object",
        "predicate": "LIVES_IN",
        "context": "user lives in chennai.",
        "temporal_details": "dialogue repro, session 0"
      }
    ]
  },
  "mem-b": {
    "entities": {
      "subject": {
        "name": "user",
        "type": "ENTITY",
        "namespace": "palimpsest"
      },
      "object": {
        "name": "bangalore",
        "type": "ENTITY",
        "namespace": "palimpsest"
      },
      "prior_object": {
        "name": "chennai",
        "type": "ENTITY",
        "namespace": "palimpsest"
      }
    },
    "relations": [
      {
        "source": "subject",
        "target": "object",
        "predicate": "LIVES_IN",
        "context": "user lives in bangalore.",
        "temporal_details": "dialogue repro, session 0"
      },
      {
        "source": "object",
        "target": "prior_object",
        "predicate": "SUPERSEDES",
        "context": "supersedes fact mem-a at session 0",
        "temporal_details": "supersedes mem-a at session 0"
      }
    ]
  }
}
```

| Item | HydraDB documents | We send | Match |
| - | - | - | - |
| Encoding | `graph_payload` is a JSON map in a multipart string field | `json.dumps(dict)` | yes |
| Top-level key | source id; for `type=memory`, the memory `id` in the same request | the memory's `id`; main path and retry path both pass the same id to `memories` and to the payload | yes |
| `entities` | map keyed by a caller-local handle, "not stored" | keys `subject`, `object`, `prior_object` | yes |
| `entities[].name` | required string, at most 256 chars, lowercased server-side | non-empty fact subject, object or prior object | yes |
| `entities[].type`, `.namespace` | optional strings, "stored as supplied" | `"ENTITY"`, `"palimpsest"` | yes |
| `relations[].source`, `.target` | required, entity-map keys (not names, not ids) | `"subject"`, `"object"`, `"prior_object"`, all present in `entities` | yes |
| `relations[].predicate` | required string, any plain string, at most 256 chars | closed-vocabulary predicate, or `SUPERSEDES` / `REFINES` / `CONTRADICTS` | yes |
| `relations[].context` | optional, at most 2,000 chars | `source_span[:2000]` | yes |
| `relations[].temporal_details` | optional string (example "since 2021") | string | yes |
| Limits | 5,000 entities, 10,000 relations, 500 per entity | 2 to 3 entities, 1 to 2 relations per source | yes |
| Unknown key | key matching no source returns 400 | none. Observed separately: HydraDB accepted every call we made | yes (documented behaviour only) |

HydraDB's own docs say `graph_payload` works for `type=memory`, so the request is in a supported mode.

Things we checked that could have been our bug and are not:

- Nesting and key names are identical to the documented example, which is for `type=knowledge`. The memory form differs only in that the key is a memory `id`.
- Relations reference entity-map keys, not entity names. We do the same.
- `temporal_details` is a string in the docs and in ours.
- `relations_created=None` and `relations_error=None` on our ingest responses are not evidence of a drop. The OpenAPI spec says both fields are "type=knowledge only" (`relations_created` only "for items that carried a `relations` payload"). A memory ingest is not expected to populate them.

What HydraDB's docs do not say, which is where the open questions are:

1. Nothing states how `graph_payload` interacts with `infer=False` on a memory. The docs say extraction is skipped for keyed sources, and that `infer=False` stores text verbatim. They never say whether a keyed memory with `infer=False` gets its BYOG graph written.
2. The docs say BYOG relations appear in `/query` `graph_context` tagged `origin: "byog"`. They do not say whether `GET /context/relations` (`client.context.relations()`) lists BYOG edges. Our zero-relation finding comes from `context.relations()`. A `/query` readback of `graph_context` for the same memory has not been tried, and is the first thing to rule out in Task 10.
3. Nothing documents what the memory path does with a graph that it accepted but could not apply, since the 202 response has no per-item graph field for memories.
4. The BYOG guide states relations "link to their best-matching chunk even when the match is weak". It does not say what happens for a memory.
5. Two entities with the same name after lowercasing (our `object` and `prior_object`, if a supersession repeats the object text) are not described. This is an edge case on our side. It cannot explain zero relations, since the first relation never involves `prior_object`.

Conclusion: the shape is not the bug. Treat the missing relations as either an undocumented limit of BYOG on `infer=False` memories, or a readback gap in `context.relations()`. Task 10's repro should read back through both `context.relations()` and `/query` `graph_context`, and ask HydraDB the questions above.

## The exact payload sent

Printed offline by `scripts/repro_byog_infer_false.py::build_payloads()`, which calls `write_path._byog_payload` for a synthetic pair. Memory A is "user lives in chennai." Memory B is "user lives in bangalore." B supersedes A. Each memory is sent as `{"id": ..., "text": ..., "infer": false}` in `memories`, with `type=memory`, `upsert=true`, and this `graph_payload`:

```json
{
  "mem-a": {
    "entities": {
      "subject": {"name": "user", "type": "ENTITY", "namespace": "palimpsest"},
      "object": {"name": "chennai", "type": "ENTITY", "namespace": "palimpsest"}
    },
    "relations": [
      {"source": "subject", "target": "object", "predicate": "LIVES_IN",
       "context": "user lives in chennai.",
       "temporal_details": "dialogue repro, session 0"}
    ]
  },
  "mem-b": {
    "entities": {
      "subject": {"name": "user", "type": "ENTITY", "namespace": "palimpsest"},
      "object": {"name": "bangalore", "type": "ENTITY", "namespace": "palimpsest"},
      "prior_object": {"name": "chennai", "type": "ENTITY", "namespace": "palimpsest"}
    },
    "relations": [
      {"source": "subject", "target": "object", "predicate": "LIVES_IN",
       "context": "user lives in bangalore.",
       "temporal_details": "dialogue repro, session 0"},
      {"source": "object", "target": "prior_object", "predicate": "SUPERSEDES",
       "context": "supersedes fact mem-a at session 0",
       "temporal_details": "supersedes mem-a at session 0"}
    ]
  }
}
```

The control run ingests the same two texts with `infer: true` and no `graph_payload`.

## Expected vs actual

| | Expected | Actual (earlier observation, `PROJECT_STATUS.md`) |
| - | - | - |
| `infer=False` memories with `graph_payload` | BYOG edges are stored and readable, per the BYOG guide | `context.relations()` returned 0 relations for every arm-C source. Checked with `type="memory"` and `"knowledge"`, with and without a collection, with and without an `id`. A throwaway collection with a synthetic supersession pair gave the same result |
| `infer=True` memories, no payload | HydraDB's own extraction creates relations | `context.relations()` returned 21 relations for dialogue 7 and 16 for dialogue 8 in the arm-B database |
| Ingest response on the `infer=False` run | `relations_created` and `relations_error` are "type=knowledge only", so `None` is expected on a memory ingest | `None` and `None`. This is not evidence of a drop |

What this does and does not show. The zero-relation result comes from `context.relations()` only. It has not been checked through `/query` `graph_context`. So the finding could turn out to be any of these:

1. The edges were stored and appear in `graph_context` with `origin: "byog"`, and `context.relations()` simply does not list them. Then nothing is wrong except a documentation gap.
2. HydraDB ignores `graph_payload` when `infer=False`. Then that needs documenting, or fixing.
3. HydraDB drops a graph it cannot attach to a memory chunk, with no signal in the response.

The repro distinguishes outcome 1 from outcomes 2 and 3: whether the edges are readable through `/query` `graph_context`. It does not tell outcome 2 from outcome 3. That needs HydraDB.

## Repro command

```bash
uv run python scripts/repro_byog_infer_false.py
```

It needs `HYDRADB_API_KEY` in the environment or `.env`, and uses the database in `HYDRADB_DATABASE` (default `palimpsest`). It makes no LLM calls and deletes nothing. For each of two fresh collections (`byog-repro-<unix time>` with `infer=False` and the payload, `byog-repro-<unix time>-infer` with `infer=True` and no payload) it:

- prints the ingest response as returned;
- waits for both memories to index;
- prints the full `context.relations()` response, including `success` and `data`, so `data: null` is not mistaken for 0 relations, and the row count;
- runs `/query` ("where does the user live", `graph_context=True`), prints the `graph_context` (and whether the response is `success` with non-null `data`), and says whether any element has `origin == "byog"`.

Read the printed `graph_context` yourself. The `origin == "byog"` check only flags edges that carry an `origin` key, so edges without one are not flagged.

Rerun rule: the readback happens once, right after indexing. If the `infer=True` control also shows 0 relations, rerun the readback after a minute before concluding anything, because graph work can lag the "completed" status.

It exits with status 1 and a message on any HydraDB error, for example HTTP 402. It never prints the API key.

## Repro output

Pending: HydraDB access (HTTP 402 on 2026-10-19). Run the command above and paste its output here.

## What PALIMPSEST does instead

The BYOG edges are best-effort in this project. Current-view correctness does not depend on them:

- The current view comes from a schema-declared `status` metadata field (`current` or `historical`). The write path flips it when a fact is superseded, and reads use HydraDB's hard `metadata_filters={"status": "current"}`. `palimpsest verify` proves this against the live store.
- The supersession chain lives in the local SQLite ledger (`results/ledger.sqlite3`). The timeline inspector and chain walking read from it.
- ORDERING answers read `graph_context.query_paths`, which is where BYOG edges would appear if HydraDB returned them. So ORDERING would use them if present. Other answers, and current-view correctness, do not use them. Provenance also comes from the ledger.

If `graph_payload` does work on `infer=False` memories, the edges would also show up in `query_paths`, and ORDERING answers would pick them up.

## Open questions for HydraDB

1. Is `graph_payload` supported on `infer=False` memory ingests, and if so, what shape does it expect? The docs say it works for `type=memory` and that extraction is skipped for keyed sources. They never say what happens when `infer=False` is also set.
2. Does `GET /context/relations` (`client.context.relations()`) list BYOG edges? The OpenAPI description says "knowledge-graph relations for a tenant or a single source" and never mentions BYOG. The BYOG guide says edges appear in `/query` `graph_context` with `origin: "byog"`. Which read is the supported way to see them?
3. What happens to a graph that a memory ingest accepts but cannot apply? The 202 response has no per-item graph field for memories, and `relations_created` and `relations_error` are knowledge-only. How would a caller find out?
4. How does a relation attach to a chunk for a memory? The guide says relations "link to their best-matching chunk even when the match is weak". Does that hold for a memory, which has one verbatim text?
5. The SDK docstring for `relations_created` omits "type=knowledge only". Can it be added?
