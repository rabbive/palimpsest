"""All HydraDB calls live here. One wrapper. No exceptions elsewhere in the codebase."""

import asyncio
import json

from hydra_db import AsyncHydraDB, ContentTooLargeError, TenantsCustomPropertyDefinition
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from palimpsest import config

RETRYABLE = retry_if_exception_type(Exception)


def _client(timeout: float | None = None) -> AsyncHydraDB:
    return AsyncHydraDB(
        token=config.HYDRADB_API_KEY,
        api_version="2",
        timeout=timeout if timeout is not None else config.HYDRA_REQUEST_TIMEOUT_SECONDS,
    )


def _retry():
    return retry(
        retry=RETRYABLE,
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        reraise=True,
    )


def _query_retry():
    """Reads get a much smaller retry budget than writes.

    A dropped write costs an extraction call to redo, so six attempts are worth
    it. A dropped read costs one question. The read path issues one query per
    coverage slot plus one for the answer, so the write-side budget multiplied a
    single unresponsive endpoint into minutes of wall clock per question -- the
    failure mode that stalled the first full evaluation.
    """
    return retry(
        retry=RETRYABLE,
        stop=stop_after_attempt(max(1, config.HYDRA_QUERY_ATTEMPTS)),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )


SCHEMA = [
    TenantsCustomPropertyDefinition(name="status", data_type="VARCHAR", max_length=16, enable_match=True),
    TenantsCustomPropertyDefinition(name="predicate", data_type="VARCHAR", max_length=128, enable_match=True),
    TenantsCustomPropertyDefinition(name="subject", data_type="VARCHAR", max_length=128, enable_match=True),
    TenantsCustomPropertyDefinition(name="session_idx", data_type="INT32"),
    TenantsCustomPropertyDefinition(name="dialogue_id", data_type="VARCHAR", max_length=64, enable_match=True),
]


async def create_database(database: str = config.HYDRADB_DATABASE):
    client = _client()
    return await client.databases.create(
        database=database,
        embeddings_dimension=config.EMBEDDINGS_DIMENSION,
        database_metadata_schema=SCHEMA,
    )


async def wait_for_database(database: str = config.HYDRADB_DATABASE, poll_seconds: float = 3.0, timeout_seconds: float = 300.0):
    client = _client()
    elapsed = 0.0
    while elapsed < timeout_seconds:
        resp = await client.databases.status(database=database)
        infra = resp.data.infra
        if infra and infra.ready_for_ingestion:
            return resp
        await asyncio.sleep(poll_seconds)
        elapsed += poll_seconds
    raise TimeoutError(f"database {database!r} not ready after {timeout_seconds}s")


@_retry()
async def ingest_facts(
    collection: str,
    memories: list[dict],
    graph_payload: dict | None = None,
    database: str = config.HYDRADB_DATABASE,
    upsert: bool = True,
):
    """memories: list of {"id", "text", "infer": False}. One HydraDB memory per Fact."""
    client = _client()
    kwargs = dict(
        database=database,
        collection=collection,
        type="memory",
        memories=json.dumps(memories),
        upsert="true" if upsert else "false",
    )
    if graph_payload:
        kwargs["graph_payload"] = json.dumps(graph_payload)
    return await client.context.ingest(**kwargs)


def _sub_payload(graph_payload: dict | None, ids: set) -> dict | None:
    if not graph_payload:
        return None
    sub = {k: v for k, v in graph_payload.items() if k in ids}
    return sub or None


async def _ingest_with_split(
    collection: str,
    memories: list[dict],
    graph_payload: dict | None,
    database: str,
    upsert: bool,
) -> list:
    """Ingest, halving the batch on HydraDB's 413 per-request token budget error
    (observed: 'combined cost N exceeds the per-request per_sec budget of 1000')."""
    try:
        resp = await ingest_facts(collection=collection, memories=memories, graph_payload=graph_payload, database=database, upsert=upsert)
        return [resp]
    except ContentTooLargeError:
        if len(memories) <= 1:
            raise
        mid = len(memories) // 2
        left, right = memories[:mid], memories[mid:]
        left_payload = _sub_payload(graph_payload, {m["id"] for m in left})
        right_payload = _sub_payload(graph_payload, {m["id"] for m in right})
        left_results = await _ingest_with_split(collection, left, left_payload, database, upsert)
        right_results = await _ingest_with_split(collection, right, right_payload, database, upsert)
        return left_results + right_results


async def ingest_facts_batched(
    collection: str,
    memories: list[dict],
    graph_payload: dict | None = None,
    database: str = config.HYDRADB_DATABASE,
    upsert: bool = True,
    batch_size: int = 15,
) -> list:
    """Batch-ingest, adaptively splitting any batch that trips the per-request
    token budget. Returns the list of ingest responses (one per HydraDB call)."""
    responses = []
    for i in range(0, len(memories), batch_size):
        chunk = memories[i : i + batch_size]
        chunk_payload = _sub_payload(graph_payload, {m["id"] for m in chunk})
        responses.extend(await _ingest_with_split(collection, chunk, chunk_payload, database, upsert))
    return responses


async def ingest_facts_with_backpressure(
    collection: str,
    memories: list[dict],
    graph_payload: dict | None = None,
    database: str = config.HYDRADB_DATABASE,
    upsert: bool = True,
    batch_size: int = config.HYDRA_BATCH_SIZE,
    batch_timeout_seconds: float = config.HYDRA_BATCH_TIMEOUT_SECONDS,
    queue_retries: int = config.HYDRA_QUEUE_RETRIES,
    retry_backoff_seconds: float = config.HYDRA_QUEUE_RETRY_BACKOFF_SECONDS,
) -> set[str]:
    """Ingest with bounded queue pressure and retry only queued sources.

    HydraDB accepts ingestion asynchronously. Sending an entire dialogue and then
    waiting for every source can leave a subset permanently queued while siblings
    finish. This helper waits after each small batch, re-upserts only the sources
    still queued, and returns persistent stragglers so callers can checkpoint them
    instead of losing the whole dialogue.
    """
    pending: set[str] = set()

    # First pass: keep only a small number of sources in flight and move on
    # after the batch timeout. A queued batch must not block all later batches.
    for i in range(0, len(memories), batch_size):
        chunk = memories[i : i + batch_size]
        ids = {memory["id"] for memory in chunk}
        payload = _sub_payload(graph_payload, ids)
        try:
            await asyncio.wait_for(
                _ingest_with_split(collection, chunk, payload, database, upsert),
                timeout=config.HYDRA_REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            pending.update(ids)
            continue
        pending.update(
            await wait_for_indexed(
                list(ids),
                collection=collection,
                database=database,
                max_stragglers=len(ids),
                timeout_seconds=batch_timeout_seconds,
            )
        )

    # Retry only the IDs that remained queued, in the same bounded batch size.
    # Re-upserting completed IDs is unnecessary and can add queue pressure.
    for attempt in range(queue_retries):
        if not pending:
            break
        await asyncio.sleep(retry_backoff_seconds * (2**attempt))
        next_pending: set[str] = set()
        pending_memories = [memory for memory in memories if memory["id"] in pending]
        for i in range(0, len(pending_memories), batch_size):
            chunk = pending_memories[i : i + batch_size]
            ids = {memory["id"] for memory in chunk}
            payload = _sub_payload(graph_payload, ids)
            try:
                await asyncio.wait_for(
                    _ingest_with_split(collection, chunk, payload, database, upsert),
                    timeout=config.HYDRA_REQUEST_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                next_pending.update(ids)
                continue
            next_pending.update(
                await wait_for_indexed(
                    list(ids),
                    collection=collection,
                    database=database,
                    max_stragglers=len(ids),
                    timeout_seconds=batch_timeout_seconds,
                )
            )
        pending = next_pending

    return pending


# `graph_creation` is an in-progress stage, not terminal. A diagnostic source
# transitioned graph_creation -> completed a few seconds later; treating it as
# success can race metadata updates and reads against unfinished graph work.
TERMINAL_SUCCESS = ("indexed", "completed", "success", "ready")
TERMINAL_FAILURE = ("errored", "failed")


async def wait_for_indexed(
    ids: list[str],
    collection: str,
    database: str = config.HYDRADB_DATABASE,
    poll_seconds: float = 2.0,
    timeout_seconds: float = 120.0,
    max_stragglers: int = 0,
) -> set[str]:
    """collection MUST match the collection used at ingest time or the status
    poll returns FILE_NOT_FOUND for every id (a scope mismatch, not a missing file).

    Returns the set of ids still not indexed (stragglers) if that set's size is
    <= max_stragglers; raises otherwise. Observed in practice: an occasional
    single memory gets permanently wedged in "queued" for an entire dialogue
    batch while 200+ siblings index normally within seconds -- treating that as
    a hard failure would throw away an otherwise-successful ingest. Not
    decorated with @_retry(): it already polls internally, so retrying the
    whole function would multiply the timeout.
    """
    client = _client()
    elapsed = 0.0
    remaining = set(ids)
    failures: dict[str, str] = {}
    while remaining and elapsed < timeout_seconds:
        try:
            resp = await asyncio.wait_for(
                client.context.status(database=database, collection=collection, ids=list(remaining)),
                timeout=config.HYDRA_REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Let the outer batch retry decide whether this is transient. Do not
            # spend the entire dialogue timeout waiting on one dead HTTP call.
            return remaining
        for s in resp.data.statuses:
            if s.indexing_status in TERMINAL_SUCCESS:
                remaining.discard(s.id)
            elif s.indexing_status in TERMINAL_FAILURE:
                remaining.discard(s.id)
                failures[s.id] = f"{s.error_code}: {s.error_message}"
        if not remaining:
            break
        await asyncio.sleep(poll_seconds)
        elapsed += poll_seconds
    if failures:
        raise RuntimeError(f"{len(failures)} memories failed indexing: {failures}")
    if remaining and len(remaining) > max_stragglers:
        raise TimeoutError(f"{len(remaining)} memories not indexed after {timeout_seconds}s: {remaining}")
    return remaining


@_query_retry()
async def query(
    q: str,
    database: str = config.HYDRADB_DATABASE,
    collection: str | None = None,
    type_: str = "memory",
    query_by: str = "hybrid",
    mode: str = "thinking",
    operator: str = "or",
    max_results: int = 20,
    num_related_chunks: int = 3,
    graph_context: bool = True,
    recency_bias: float = 0.2,
    metadata_filters: dict | None = None,
    ids: list[str] | None = None,
    timeout_seconds: float | None = None,
):
    timeout = timeout_seconds if timeout_seconds is not None else config.HYDRA_QUERY_TIMEOUT_SECONDS
    client = _client(timeout=timeout)
    kwargs = dict(
        query=q,
        database=database,
        type=type_,
        query_by=query_by,
        mode=mode,
        operator=operator,
        max_results=max_results,
        num_related_chunks=num_related_chunks,
        graph_context=graph_context,
        recency_bias=recency_bias,
    )
    if collection:
        kwargs["collection"] = collection
    if metadata_filters:
        kwargs["metadata_filters"] = metadata_filters
    if ids:
        kwargs["ids"] = ids
    # The SDK's own timeout has been observed to hang past its deadline on a
    # stalled read; wait_for is the outer guarantee that one query cannot eat
    # an unbounded slice of the evaluation.
    return await asyncio.wait_for(client.query(**kwargs), timeout=timeout)


@_retry()
async def relations(
    collection: str,
    database: str = config.HYDRADB_DATABASE,
    id: str | None = None,
    limit: int = 100,
    cursor: float | None = None,
):
    client = _client()
    kwargs = dict(database=database, collection=collection, type="memory", limit=limit)
    if id:
        kwargs["id"] = id
    # The API treats cursor=0 as "after timestamp zero" and returns no rows;
    # omit it for the initial page. Pass a cursor only when continuing pagination.
    if cursor is not None:
        kwargs["cursor"] = cursor
    return await client.context.relations(**kwargs)


@_retry()
async def set_metadata(
    fact_id: str,
    collection: str,
    metadata: dict,
    database: str = config.HYDRADB_DATABASE,
):
    """Merge schema-declared database metadata onto one indexed source."""
    client = _client()
    return await client.context.update_source_metadata(
        fact_id,
        database=database,
        collection=collection,
        database_metadata=metadata,
    )


async def set_status(fact_id: str, collection: str, status: str, database: str = config.HYDRADB_DATABASE):
    """Set the schema-declared `status` field on one source.

    Gotcha: context.ingest() has no field to set schema-declared metadata per
    memory. A freshly-ingested fact's `status` is unset, and
    metadata_filters={"status": "current"} excludes unset rows (it is not a
    default value, it's a hard match).
    """
    return await set_metadata(fact_id, collection, {"status": status}, database=database)


async def set_fact_metadata(
    fact,
    collection: str,
    database: str = config.HYDRADB_DATABASE,
    source_id: str | None = None,
):
    """Materialize every schema field used by current-view and coverage reads."""
    return await set_metadata(
        source_id or fact.id,
        collection,
        {
            "status": fact.status,
            "predicate": fact.predicate,
            "subject": fact.subject,
            "session_idx": fact.session_idx,
            "dialogue_id": fact.dialogue_id,
        },
        database=database,
    )


async def flip_to_historical(fact_id: str, collection: str, database: str = config.HYDRADB_DATABASE):
    return await set_status(fact_id, collection, "historical", database=database)


async def flip_to_current(fact_id: str, collection: str, database: str = config.HYDRADB_DATABASE):
    return await set_status(fact_id, collection, "current", database=database)


@_retry()
async def list_facts(database: str = config.HYDRADB_DATABASE, collection: str | None = None, page: int = 1, page_size: int = 100):
    client = _client()
    kwargs = dict(database=database, type="memory", page=page, page_size=page_size)
    if collection:
        kwargs["collection"] = collection
    return await client.context.list(**kwargs)


@_retry()
async def delete_facts(ids: list[str], database: str = config.HYDRADB_DATABASE, collection: str | None = None):
    client = _client()
    kwargs = dict(database=database, type="memory", ids=ids)
    if collection:
        kwargs["collection"] = collection
    return await client.context.delete(**kwargs)
