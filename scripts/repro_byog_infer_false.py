"""Minimal repro: does HydraDB apply a BYOG graph_payload on infer=False memories?

Ingests a synthetic supersession pair (B supersedes A) twice, into two fresh
collections of the existing database:
  byog-repro-<t>        infer=False + graph_payload (what PALIMPSEST does)
  byog-repro-<t>-infer  infer=True, no payload (control)
Then reads back through context.relations() and /query graph_context.
Makes no LLM calls and deletes nothing. Exits 1 on any HydraDB error.

    uv run python scripts/repro_byog_infer_false.py
"""

import asyncio
import json
import sys
import time

from palimpsest import config, hydra
from palimpsest.models import Fact
from palimpsest.write_path import _byog_payload

QUESTION = "where does the user live"
ID_A, ID_B = "mem-a", "mem-b"


def build_payloads() -> tuple[list[dict], dict]:
    """Return (memories, graph_payload) for the pair. Pure, no network."""
    common = dict(dialogue_id="repro", session_idx=0, subject="user", predicate="LIVES_IN")
    a = Fact(id=ID_A, object="chennai", source_span="user lives in chennai.", **common)
    b = Fact(id=ID_B, object="bangalore", source_span="user lives in bangalore.", supersedes=ID_A, **common)
    memories = [{"id": ID_A, "text": a.source_span}, {"id": ID_B, "text": b.source_span}]
    graph = {**_byog_payload(a, None, None, source_id=ID_A), **_byog_payload(b, a, "SUPERSEDES", source_id=ID_B)}
    return memories, graph


def _has_byog(node) -> bool:
    if isinstance(node, dict):
        return node.get("origin") == "byog" or any(_has_byog(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_byog(v) for v in node)
    return False


def _dump(obj):
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj


async def run_one(collection: str, infer: bool, graph: dict | None, memories: list[dict]) -> None:
    print(f"\n=== {collection}  infer={infer}  graph_payload={'yes' if graph else 'no'} ===")
    sent = [{**m, "infer": infer} for m in memories]
    resp = await hydra.ingest_facts(collection=collection, memories=sent, graph_payload=graph)
    print("ingest response (as returned):")
    print(json.dumps(_dump(resp), indent=2, default=str))
    print("Note: relations_created / relations_error are documented as type=knowledge only.")
    # wait_for_indexed also returns early with the unfinished ids on a status-call
    # timeout, so check the result explicitly. Never read back unindexed sources.
    stragglers = await hydra.wait_for_indexed([ID_A, ID_B], collection, max_stragglers=0)
    if stragglers:
        raise RuntimeError(f"not indexed in {collection}: {sorted(stragglers)}; no read-back done")
    print("indexed: both memories")

    # Print the whole response (success, data, ...) so `data: null` is visible and is
    # not read as "0 relations".
    rel = _dump(await hydra.relations(collection=collection))
    print("context.relations() full response:")
    print(json.dumps(rel, indent=2, default=str))
    rows = (rel.get("data") or {}).get("relations") or []
    print(f"context.relations(): {len(rows)} relations")

    q = _dump(await hydra.query(q=QUESTION, collection=collection, graph_context=True))
    print("query graph_context (null here means absent from the response):")
    gc = (q.get("data") or {}).get("graph_context")
    print(json.dumps(gc, indent=2, default=str))
    print("query response success:", q.get("success"), "| data is null:", q.get("data") is None)
    print("any element with origin == 'byog':", _has_byog(gc))


async def main() -> int:
    stamp = int(time.time())
    memories, graph = build_payloads()
    print("hydradb-sdk database:", config.HYDRADB_DATABASE)
    print("graph_payload sent on the infer=False run:")
    print(json.dumps(graph, indent=2))
    await run_one(f"byog-repro-{stamp}", False, graph, memories)
    await run_one(f"byog-repro-{stamp}-infer", True, None, memories)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:  # HydraDB errors, e.g. HTTP 402. Never prints the key.
        print(f"repro failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
