# HydraDB: graph_payload on infer=False memory ingests

## Payload shape check

Question: is our `graph_payload` wrong, or does HydraDB drop a correct one? Checked before reporting anything to HydraDB.

Result: our shape matches HydraDB's documented shape field for field. No code change was needed.

Sources:

- BYOG guide, section "Using BYOG without Cypher": https://docs.hydradb.com/essentials/v2/bring-your-own-graph.md
- Ingest endpoint, accordion "Bring your own graph" and its field table: https://docs.hydradb.com/api-reference/v2/endpoint/ingest-context.md
- OpenAPI spec, `POST /context/ingest` and `ingestion.V2IngestResultItem`: https://docs.hydradb.com/api-reference/v2/openapi.json
- Installed SDK `hydradb-sdk` 2.1.2: `hydra_db/context/client.py` (`ingest`), `hydra_db/types/ingestion_v2source_upload_result_item.py`. The SDK types `graph_payload` as a plain `str` and says nothing more.

Our payload is built by `write_path._byog_payload` and sent by `hydra.ingest_facts` as `context.ingest(type="memory", upsert="true", memories=json.dumps(...), graph_payload=json.dumps(...))`. Printed from the ledger for fact `f_8_0001_007`, a supersession of `f_8_0000_003` (no network calls):

```json
{
  "f_8_0001_007": {
    "entities": {
      "subject":      {"name": "user", "type": "ENTITY", "namespace": "palimpsest"},
      "object":       {"name": "$120 on grammarly premium", "type": "ENTITY", "namespace": "palimpsest"},
      "prior_object": {"name": "$75,000 annually", "type": "ENTITY", "namespace": "palimpsest"}
    },
    "relations": [
      {"source": "subject", "target": "object", "predicate": "SPENT_AMOUNT",
       "context": "I spent on Grammarly Premium on April 7",
       "temporal_details": "dialogue 8, session 1, April-12-2024"},
      {"source": "object", "target": "prior_object", "predicate": "SUPERSEDES",
       "context": "supersedes fact f_8_0000_003 at session 1",
       "temporal_details": "supersedes f_8_0000_003 at session 1"}
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
| Unknown key | key matching no source returns 400 | none; HydraDB accepted every call | yes |

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
