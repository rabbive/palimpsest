import asyncio
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.progress import track

from palimpsest import config, hydra
from palimpsest.read_path import answer_question
from palimpsest.write_path import process_dialogue

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

app = typer.Typer(help="PALIMPSEST — write-time reconciliation and abstention layer for HydraDB")


@app.command()
def spike():
    """§4.4 ingestion spike + §14 Day-0 risk check: create throwaway DB, ingest 10
    memories, time it, confirm graph + BYOG, and confirm status filtering actually
    filters (the Day 1 exit gate)."""
    import json
    import time

    async def _run():
        db = "palimpsest_spike"
        rprint(f"[bold]Creating database[/bold] {db}")
        try:
            await hydra.create_database(database=db)
        except Exception as e:
            rprint(f"[yellow]create_database: {e} (continuing, database may already exist)[/yellow]")
        await hydra.wait_for_database(database=db)
        rprint("[green]database ready[/green]")

        memories = [{"id": f"spike_{i}", "text": f"Spike memory number {i} about test topic {i}.", "infer": False} for i in range(10)]
        graph_payload = {
            "spike_0": {
                "entities": {"a": {"name": "Test Subject", "type": "ENTITY"}, "b": {"name": "Test Object", "type": "ENTITY"}},
                "relations": [{"source": "a", "target": "b", "predicate": "TEST_RELATION", "context": "spike test"}],
            }
        }

        t0 = time.time()
        await hydra.ingest_facts(collection="spike", memories=memories, graph_payload=graph_payload, database=db)
        t1 = time.time()
        rprint(f"[bold]ingest call[/bold]: {t1 - t0:.2f}s for 10 memories ({(t1 - t0) / 10:.2f}s/memory)")

        await hydra.wait_for_indexed([m["id"] for m in memories], collection="spike", database=db)
        t2 = time.time()
        rprint(f"[bold]indexed after[/bold]: {t2 - t1:.2f}s")

        result = await hydra.query(q="test topic", collection="spike", database=db, graph_context=True)
        rprint("[bold]graph_context present:[/bold]", bool(result.data.graph_context))
        rprint(f"[bold]chunks returned:[/bold] {len(result.data.chunks or [])}")

        # §14 risk check: does metadata_filters={"status": "current"} actually filter?
        rprint("\n[bold]status-filter check[/bold] (Day 1 exit gate)")
        coll = "status_check"
        sf_memories = [
            {"id": "sf_old", "text": "The users manager is Marcus Webb.", "infer": False},
            {"id": "sf_new", "text": "The users manager is Priya Raghavan.", "infer": False},
        ]
        await hydra.ingest_facts(collection=coll, memories=sf_memories, database=db)
        await hydra.wait_for_indexed(["sf_old", "sf_new"], collection=coll, database=db)
        # ingest() cannot set schema-declared metadata per memory -- must flip explicitly.
        await hydra.flip_to_current("sf_new", collection=coll, database=db)
        await hydra.flip_to_historical("sf_old", collection=coll, database=db)

        filtered = await hydra.query(q="who is the users manager", collection=coll, database=db, metadata_filters={"status": "current"})
        ids = [c.id for c in (filtered.data.chunks or [])]
        ok = ids == ["sf_new"]
        color = "green" if ok else "red"
        rprint(f"[{color}]status=current returned {ids} (expect only ['sf_new']): {'PASS' if ok else 'FAIL'}[/{color}]")

    asyncio.run(_run())


@app.command()
def create_db(database: str = config.HYDRADB_DATABASE):
    """Create the palimpsest database with the schema declared in hydra.py, then poll until ready."""
    async def _run():
        await hydra.create_database(database=database)
        await hydra.wait_for_database(database=database)
        rprint(f"[green]database {database!r} ready[/green]")

    asyncio.run(_run())


@app.command()
def ingest(dialogue_id: str = typer.Argument(..., help="BEAM 100K dialogue directory name, e.g. '1'")):
    """Run the write path (extract -> reconcile -> ingest -> flip) over one dialogue."""
    from eval.beam_loader import iter_sessions

    async def _run():
        sessions = list(iter_sessions(dialogue_id))
        stats = await process_dialogue(dialogue_id, sessions)
        rprint(f"[bold]dialogue {dialogue_id}[/bold] reconciliation stats: {stats}")

    asyncio.run(_run())


@app.command()
def ingest_all(dialogues: list[str] = typer.Argument(None)):
    """Ingest the frozen eval subset (or the given dialogue ids) sequentially, reporting stats."""
    from eval.beam_loader import FROZEN_SUBSET, iter_sessions

    ids = dialogues or FROZEN_SUBSET

    async def _run():
        for dialogue_id in track(ids, description="ingesting"):
            sessions = list(iter_sessions(dialogue_id))
            stats = await process_dialogue(dialogue_id, sessions)
            rprint(f"dialogue {dialogue_id}: {stats}")

    asyncio.run(_run())


@app.command()
def ask(dialogue_id: str, question: str):
    """Ask a question against one dialogue's memory via the read path."""
    async def _run():
        answer = await answer_question(dialogue_id, question)
        rprint(f"[bold]intent:[/bold] {answer.intent}")
        if answer.abstention:
            rprint("[yellow]ABSTAINED[/yellow]")
            rprint(answer.abstention.model_dump())
        rprint(f"[bold]answer:[/bold] {answer.text}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
