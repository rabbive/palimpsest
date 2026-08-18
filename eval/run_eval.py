"""Three eval arms + ablations, run over the frozen BEAM-100K subset.

Arm A — full-context stuffing: dump the whole dialogue transcript into the prompt,
        no HydraDB at all. The floor a vector store beats.
Arm B — HydraDB default auto-extraction (infer=True), no reconciliation, no
        coverage check. Isolates what PALIMPSEST adds on top of the vendor default.
Arm C — PALIMPSEST: write-time reconciliation + status filtering + coverage/abstention.

B vs C is the load-bearing comparison: it isolates what we engineered.
"""

import asyncio
import json

import typer

from eval.beam_loader import FROZEN_SUBSET, PRIORITY_CATEGORIES, iter_questions, iter_sessions
from eval.judge import judge_question
from palimpsest import config, hydra, llm
from palimpsest.models import EvalResult
from palimpsest.read_path import answer_question
from palimpsest.write_path import process_dialogue

app = typer.Typer()

ARM_B_DATABASE = f"{config.HYDRADB_DATABASE}_arm_b"


async def _full_transcript(dialogue_id: str) -> str:
    parts = [text for _idx, _ts, text in iter_sessions(dialogue_id)]
    return "\n\n".join(parts)


async def run_arm_a(dialogue_id: str, question: str, model: str = config.STRONG_MODEL) -> str:
    transcript = await _full_transcript(dialogue_id)
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


async def run_arm_c(dialogue_id: str, question: str) -> str:
    answer = await answer_question(dialogue_id, question)
    return answer.text


async def run_eval(dialogues: list[str] | None = None, categories: list[str] | None = None, arms: list[str] | None = None):
    dialogues = dialogues or FROZEN_SUBSET
    categories = categories or PRIORITY_CATEGORIES
    arms = arms or ["A", "B", "C"]
    results: list[EvalResult] = []

    for dialogue_id in dialogues:
        if "C" in arms:
            sessions = list(iter_sessions(dialogue_id))
            await process_dialogue(dialogue_id, sessions)
        if "B" in arms:
            await setup_arm_b(dialogue_id)

        for category, _index, q in iter_questions(dialogue_id, categories):
            question = q["question"]
            rubric = q.get("rubric", [])

            for arm in arms:
                if arm == "A":
                    response = await run_arm_a(dialogue_id, question)
                elif arm == "B":
                    response = await run_arm_b(dialogue_id, question)
                else:
                    response = await run_arm_c(dialogue_id, question)

                judged = judge_question(rubric, response) if rubric else {"llm_judge_score": None}
                results.append(
                    EvalResult(
                        dialogue_id=dialogue_id,
                        category=category,
                        question=question,
                        arm=arm,
                        llm_response=response,
                        llm_judge_score=judged["llm_judge_score"],
                    )
                )

    return results


@app.command()
def main(
    dialogues: str = typer.Option("", help="comma-separated dialogue ids; defaults to the frozen subset"),
    categories: str = typer.Option("", help="comma-separated BEAM categories; defaults to the priority 5"),
    arms: str = typer.Option("A,B,C", help="comma-separated arms to run"),
    out: str = typer.Option("results/raw_eval.json"),
):
    dialogue_list = dialogues.split(",") if dialogues else None
    category_list = categories.split(",") if categories else None
    arm_list = arms.split(",")

    results = asyncio.run(run_eval(dialogue_list, category_list, arm_list))

    with open(out, "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    typer.echo(f"wrote {len(results)} eval results to {out}")


if __name__ == "__main__":
    app()
