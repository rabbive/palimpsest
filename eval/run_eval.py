"""Three eval arms + read-path ablations, over the frozen BEAM-100K subset.

Arm A — full-context stuffing: dump the whole dialogue transcript into the prompt,
        no HydraDB at all. The floor a vector store beats.
Arm B — HydraDB default auto-extraction (infer=True), no reconciliation, no
        coverage check. Isolates what PALIMPSEST adds on top of the vendor default.
Arm C — PALIMPSEST: write-time reconciliation + status filtering + coverage/abstention.

B vs C is the load-bearing comparison: it isolates what we engineered.

Three ablations run on the same ingested corpus as arm C, switching off one read
path mechanism each — no second write pass, so they cost queries and nothing else:

    C_no_status_filter  materialized current view off
    C_no_coverage       graph-property abstention off
    C_neither           both off

Operationally this harness is built around one lesson: the first full run was a
single sequential pass that wrote its output only at the end, and a 30-minute
timeout destroyed all of it. Every result is now appended to a JSONL checkpoint
the moment it is produced, a rerun skips what already succeeded, each question is
bounded by its own timeout, and a failure is recorded as a row rather than
killing the run.
"""

import asyncio
import json
import os
import time
from pathlib import Path

import typer

from eval.beam_loader import FROZEN_SUBSET, PRIORITY_CATEGORIES, iter_questions, iter_sessions
from eval.judge import judge_question
from palimpsest import config, hydra, llm
from palimpsest.models import EvalResult
from palimpsest.read_path import answer_question
from palimpsest.write_path import process_dialogue

app = typer.Typer()

ARM_B_DATABASE = f"{config.HYDRADB_DATABASE}_arm_b"

# arm -> (use_status_filter, use_coverage). Arm C's ablations differ only here.
ARM_C_VARIANTS = {
    "C": (True, True),
    "C_no_status_filter": (False, True),
    "C_no_coverage": (True, False),
    "C_neither": (False, False),
}
ALL_ARMS = ["A", "B", *ARM_C_VARIANTS]


def _full_transcript(dialogue_id: str) -> str:
    return "\n\n".join(text for _idx, _ts, text in iter_sessions(dialogue_id))


async def run_arm_a(dialogue_id: str, question: str, model: str = config.STRONG_MODEL) -> str:
    transcript = _full_transcript(dialogue_id)
    prompt = f"Full conversation transcript:\n{transcript}\n\nQUESTION: {question}"
    return llm.complete(prompt=prompt, model=model)


async def setup_arm_b(dialogue_id: str) -> None:
    """Ingest raw sessions into HydraDB with infer=True (vendor default), no reconciliation."""
    sessions = list(iter_sessions(dialogue_id))
    memories = [
        {"id": f"b_{dialogue_id}_{idx}", "text": text[:2000], "infer": True}
        for idx, (_i, _ts, text) in enumerate(sessions)
        if text.strip()
    ]
    if not memories:
        return
    await hydra.ingest_facts_batched(collection=dialogue_id, memories=memories, database=ARM_B_DATABASE, upsert=True)
    await hydra.wait_for_indexed([m["id"] for m in memories], collection=dialogue_id, database=ARM_B_DATABASE)


async def run_arm_b(dialogue_id: str, question: str, model: str = config.STRONG_MODEL) -> str:
    result = await hydra.query(q=question, collection=dialogue_id, database=ARM_B_DATABASE, graph_context=True)
    chunks = "\n".join(c.chunk_content for c in (result.data.chunks or []) if getattr(c, "chunk_content", None))
    prompt = f"CONTEXT:\n{chunks}\n\nQUESTION: {question}"
    return llm.complete(prompt=prompt, model=model)


async def run_arm_c(dialogue_id: str, question: str, arm: str = "C") -> tuple[str, bool]:
    use_status_filter, use_coverage = ARM_C_VARIANTS[arm]
    answer = await answer_question(
        dialogue_id,
        question,
        use_status_filter=use_status_filter,
        use_coverage=use_coverage,
    )
    return answer.text, answer.abstention is not None


# --- checkpointing -------------------------------------------------------


def load_checkpoint(path: str) -> dict[str, dict]:
    """Read completed rows from a previous run, keyed for resume.

    Rows that recorded an error are deliberately not returned: a rerun should
    retry a HydraDB read timeout, not inherit it.
    """
    done: dict[str, dict] = {}
    if not os.path.exists(path):
        return done
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a run killed mid-write can leave one torn line
            if row.get("error"):
                continue
            key = f"{row['dialogue_id']}|{row['category']}|{row['arm']}|{row['question']}"
            done[key] = row
    return done


def append_checkpoint(path: str, result: EvalResult) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(result.model_dump()) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --- work items ----------------------------------------------------------


async def _dispatch(dialogue_id: str, question: str, arm: str) -> tuple[str, bool]:
    if arm == "A":
        return await run_arm_a(dialogue_id, question), False
    if arm == "B":
        return await run_arm_b(dialogue_id, question), False
    return await run_arm_c(dialogue_id, question, arm=arm)


async def _run_item(item: dict, timeout_seconds: float) -> EvalResult:
    started = time.perf_counter()
    with llm.UsageScope() as usage:
        try:
            response, abstained = await asyncio.wait_for(
                _dispatch(item["dialogue_id"], item["question"], item["arm"]),
                timeout=timeout_seconds,
            )
            error = None
        except asyncio.TimeoutError:
            response, abstained, error = "", False, f"timeout after {timeout_seconds}s"
        except Exception as exc:  # a dead endpoint must not end the run
            response, abstained, error = "", False, f"{type(exc).__name__}: {exc}"

        score = None
        if error is None and item["rubric"]:
            try:
                score = judge_question(item["rubric"], response)["llm_judge_score"]
            except Exception as exc:
                error = f"judge failed: {type(exc).__name__}: {exc}"

    return EvalResult(
        dialogue_id=item["dialogue_id"],
        category=item["category"],
        question=item["question"],
        arm=item["arm"],
        llm_response=response,
        llm_judge_score=score,
        abstained=abstained,
        latency_seconds=time.perf_counter() - started,
        cost_usd=usage.cost_usd,
        error=error,
    )


def _run_item_sync(item: dict, timeout_seconds: float) -> EvalResult:
    """Run one work item on its own event loop, inside a worker thread.

    litellm's completion call is blocking, so questions answered on a single
    shared loop serialize on the LLM regardless of how many are in flight. One
    loop per thread is what actually makes the concurrency setting mean
    something.
    """
    return asyncio.run(_run_item(item, timeout_seconds))


def _work_items(dialogues, categories, arms, limit_per_category: int) -> list[dict]:
    items = []
    for dialogue_id in dialogues:
        for category, index, q in iter_questions(dialogue_id, categories):
            if limit_per_category and index >= limit_per_category:
                continue
            for arm in arms:
                items.append(
                    {
                        "dialogue_id": dialogue_id,
                        "category": category,
                        "question": q["question"],
                        "rubric": q.get("rubric", []),
                        "arm": arm,
                    }
                )
    return items


async def run_eval(
    dialogues: list[str] | None = None,
    categories: list[str] | None = None,
    arms: list[str] | None = None,
    checkpoint_path: str = config.EVAL_CHECKPOINT_PATH,
    resume: bool = True,
    ingest: bool = False,
    concurrency: int = config.EVAL_CONCURRENCY,
    question_timeout: float = config.EVAL_QUESTION_TIMEOUT_SECONDS,
    limit_per_category: int = 0,
) -> list[dict]:
    config.ensure_dirs()
    dialogues = dialogues or FROZEN_SUBSET
    categories = categories or PRIORITY_CATEGORIES
    arms = arms or ALL_ARMS

    done = load_checkpoint(checkpoint_path) if resume else {}
    if done:
        typer.echo(f"resuming: {len(done)} results already checkpointed in {checkpoint_path}")

    # Ingestion is opt-in. Re-running the write path over an already-ingested
    # dialogue re-enters HydraDB's asynchronous queue for no benefit, and a
    # queue incident during evaluation is how the previous run lost its output.
    if ingest:
        for dialogue_id in dialogues:
            if any(arm in ARM_C_VARIANTS for arm in arms):
                stats = await process_dialogue(dialogue_id, list(iter_sessions(dialogue_id)))
                typer.echo(f"dialogue {dialogue_id} write path: {stats}")
            if "B" in arms:
                await setup_arm_b(dialogue_id)

    items = _work_items(dialogues, categories, arms, limit_per_category)
    pending = [
        item
        for item in items
        if f"{item['dialogue_id']}|{item['category']}|{item['arm']}|{item['question']}" not in done
    ]
    typer.echo(f"{len(items)} work items, {len(pending)} to run, concurrency={concurrency}")

    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    lock = asyncio.Lock()

    async def _bounded(item: dict) -> dict:
        nonlocal completed
        async with semaphore:
            result = await asyncio.to_thread(_run_item_sync, item, question_timeout)
        async with lock:
            append_checkpoint(checkpoint_path, result)
            completed += 1
            flag = f" [{result.error}]" if result.error else ""
            typer.echo(
                f"  {completed}/{len(pending)} {result.dialogue_id}/{result.category}/{result.arm} "
                f"{result.latency_seconds:.1f}s ${llm.spend_usd():.2f} total{flag}"
            )
        return result.model_dump()

    fresh = await asyncio.gather(*[_bounded(item) for item in pending])
    return list(done.values()) + list(fresh)


@app.command()
def main(
    dialogues: str = typer.Option("", help="comma-separated dialogue ids; defaults to the frozen subset"),
    categories: str = typer.Option("", help="comma-separated BEAM categories; defaults to the priority 5"),
    arms: str = typer.Option(",".join(ALL_ARMS), help=f"comma-separated arms from: {', '.join(ALL_ARMS)}"),
    out: str = typer.Option(config.EVAL_RAW_PATH),
    checkpoint: str = typer.Option(config.EVAL_CHECKPOINT_PATH, help="append-only JSONL written as results arrive"),
    resume: bool = typer.Option(True, help="skip work already present in the checkpoint"),
    ingest: bool = typer.Option(False, help="run the write path before evaluating (off by default: reruns re-enter HydraDB's queue)"),
    concurrency: int = typer.Option(config.EVAL_CONCURRENCY),
    question_timeout: float = typer.Option(config.EVAL_QUESTION_TIMEOUT_SECONDS),
    limit_per_category: int = typer.Option(0, help="cap questions per category, for a cheap smoke run"),
):
    arm_list = [a.strip() for a in arms.split(",") if a.strip()]
    unknown = [a for a in arm_list if a not in ALL_ARMS]
    if unknown:
        raise typer.BadParameter(f"unknown arms {unknown}; choose from {ALL_ARMS}")

    results = asyncio.run(
        run_eval(
            dialogues=[d.strip() for d in dialogues.split(",") if d.strip()] or None,
            categories=[c.strip() for c in categories.split(",") if c.strip()] or None,
            arms=arm_list,
            checkpoint_path=checkpoint,
            resume=resume,
            ingest=ingest,
            concurrency=concurrency,
            question_timeout=question_timeout,
            limit_per_category=limit_per_category,
        )
    )

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(results, f, indent=2)

    errors = sum(1 for r in results if r.get("error"))
    typer.echo(f"wrote {len(results)} eval results to {out} ({errors} errored)")
    typer.echo(f"LLM usage: {llm.usage_summary()}")


if __name__ == "__main__":
    app()
