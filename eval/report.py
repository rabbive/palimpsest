"""Turn eval/run_eval.py's raw output into the three tables the README promises:

    results/main_table.md    arms A/B/C x BEAM category
    results/ablation.md      arm C against its read-path ablations
    results/cost_latency.md  cost and latency per arm, next to accuracy

Reads results/raw_eval.json when it exists, and otherwise falls back to the
append-only checkpoint results/raw_eval.jsonl — so a run that was interrupted
still reports the questions it did finish, with the coverage stated in the
table rather than implied.
"""

import json
import os
from collections import defaultdict

import typer

from palimpsest import config

app = typer.Typer()

MAIN_ARMS = ["A", "B", "C"]
ABLATION_ARMS = ["C", "C_no_status_filter", "C_no_coverage", "C_neither"]
ARM_LABELS = {
    "A": "A: full-context stuffing",
    "B": "B: HydraDB default (infer=True)",
    "C": "C: PALIMPSEST",
    "C_no_status_filter": "C − materialized current view",
    "C_no_coverage": "C − graph-property abstention",
    "C_neither": "C − both",
}


def load_results(raw: str, checkpoint: str) -> list[dict]:
    if os.path.exists(raw):
        with open(raw) as f:
            return json.load(f)
    if not os.path.exists(checkpoint):
        raise typer.BadParameter(f"neither {raw} nor {checkpoint} exists; run `make eval` first")

    # Later rows win: a rerun that fixed an errored question appends a new line
    # rather than rewriting the old one.
    rows: dict[str, dict] = {}
    with open(checkpoint) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[f"{row['dialogue_id']}|{row['category']}|{row['arm']}|{row['question']}"] = row
    return list(rows.values())


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cell(value: float | None, n: int, fmt: str = "{:.2f}") -> str:
    return f"{fmt.format(value)} (n={n})" if value is not None else "n/a"


def _scored(results: list[dict]) -> list[dict]:
    """Rows that actually produced a judge score. Errors are excluded from
    accuracy and counted separately, so a timeout never reads as a zero."""
    return [r for r in results if r.get("llm_judge_score") is not None and not r.get("error")]


def _score_table(results: list[dict], arms: list[str]) -> str:
    buckets = defaultdict(list)
    for r in _scored(results):
        if r["arm"] in arms:
            buckets[(r["category"], r["arm"])].append(r["llm_judge_score"])

    present = [a for a in arms if any(k[1] == a for k in buckets)]
    if not present:
        return "_no scored results for these arms yet_"

    lines = [
        "| category | " + " | ".join(ARM_LABELS.get(a, a) for a in present) + " |",
        "|---" * (len(present) + 1) + "|",
    ]
    for category in sorted({k[0] for k in buckets}):
        row = [category]
        for arm in present:
            scores = buckets.get((category, arm), [])
            row.append(_cell(_mean(scores), len(scores)))
        lines.append("| " + " | ".join(row) + " |")

    row = ["**overall**"]
    for arm in present:
        scores = [s for (_c, a), v in buckets.items() if a == arm for s in v]
        row.append(f"**{_cell(_mean(scores), len(scores))}**")
    lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _abstention_table(results: list[dict]) -> str:
    """Abstention is the headline claim, so it gets measured in both directions.

    On BEAM's abstention questions, abstaining is the correct behavior. On every
    other category the same behavior is a false abstention — a refusal to answer
    something the memory does cover. A system that abstains on everything would
    look perfect in the first column and terrible in the second.
    """
    correct = defaultdict(list)
    false_positive = defaultdict(list)
    for r in results:
        if r.get("error"):
            continue
        target = correct if r["category"] == "abstention" else false_positive
        target[r["arm"]].append(1.0 if r.get("abstained") else 0.0)

    arms = [a for a in ARM_LABELS if a in set(correct) | set(false_positive)]
    if not arms:
        return "_no abstention data yet_"

    lines = [
        "| arm | abstained on abstention questions | abstained on answerable questions |",
        "|---|---|---|",
    ]
    for arm in arms:
        lines.append(
            "| "
            + " | ".join(
                [
                    ARM_LABELS.get(arm, arm),
                    _cell(_mean(correct.get(arm, [])), len(correct.get(arm, [])), "{:.0%}"),
                    _cell(_mean(false_positive.get(arm, [])), len(false_positive.get(arm, [])), "{:.0%}"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _cost_latency_table(results: list[dict]) -> str:
    by_arm = defaultdict(list)
    for r in results:
        by_arm[r["arm"]].append(r)

    lines = [
        "| arm | judge score | mean latency | p90 latency | mean cost/question | total cost | errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in [a for a in ARM_LABELS if a in by_arm]:
        rows = by_arm[arm]
        scored = _scored(rows)
        latencies = sorted(r.get("latency_seconds", 0.0) for r in rows if not r.get("error"))
        costs = [r.get("cost_usd", 0.0) for r in rows]
        p90 = latencies[min(len(latencies) - 1, int(0.9 * len(latencies)))] if latencies else None
        errors = sum(1 for r in rows if r.get("error"))
        lines.append(
            "| "
            + " | ".join(
                [
                    ARM_LABELS.get(arm, arm),
                    _cell(_mean([r["llm_judge_score"] for r in scored]), len(scored)),
                    f"{_mean(latencies):.1f}s" if latencies else "n/a",
                    f"{p90:.1f}s" if p90 is not None else "n/a",
                    f"${_mean(costs):.4f}" if costs else "n/a",
                    f"${sum(costs):.2f}",
                    str(errors),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append(
        "Cost counts money actually spent: a disk-cache hit is billed at zero, so a "
        "reported total reflects the run that populated the cache, not a re-run of it."
    )
    return "\n".join(lines)


def _coverage_note(results: list[dict]) -> str:
    dialogues = sorted({r["dialogue_id"] for r in results})
    questions = len({(r["dialogue_id"], r["category"], r["question"]) for r in results})
    errors = sum(1 for r in results if r.get("error"))
    note = (
        f"Coverage: {questions} questions across {len(dialogues)} dialogue(s) "
        f"({', '.join(dialogues)}), {len(results)} arm-runs total."
    )
    if errors:
        note += (
            f" {errors} arm-run(s) errored (mostly HydraDB read timeouts) and are excluded "
            "from the score columns rather than scored as zero; they are counted in the "
            "errors column of `cost_latency.md`."
        )
    return note


@app.command()
def main(
    raw: str = config.EVAL_RAW_PATH,
    checkpoint: str = config.EVAL_CHECKPOINT_PATH,
    out_dir: str = str(config.RESULTS_DIR),
):
    config.ensure_dirs()
    results = load_results(raw, checkpoint)
    note = _coverage_note(results)

    files = {
        "main_table.md": (
            "# PALIMPSEST — main results\n\n"
            "BEAM-100K rubric judge score (1.0/0.5/0.0 per rubric item, averaged), by category x arm.\n"
            "B vs C is the load-bearing comparison: it isolates what PALIMPSEST adds over HydraDB's\n"
            "own auto-extraction rather than over no memory system at all.\n\n"
            f"{note}\n\n"
            f"{_score_table(results, MAIN_ARMS)}\n\n"
            "## Abstention behaviour\n\n"
            f"{_abstention_table(results)}\n"
        ),
        "ablation.md": (
            "# PALIMPSEST — ablations\n\n"
            "Each ablation switches off exactly one read-path mechanism against the same ingested\n"
            "corpus as arm C, so the difference is attributable to the mechanism and not to a\n"
            "different write pass.\n\n"
            f"{note}\n\n"
            f"{_score_table(results, ABLATION_ARMS)}\n"
        ),
        "cost_latency.md": (
            "# PALIMPSEST — cost and latency\n\n"
            f"{note}\n\n"
            f"{_cost_latency_table(results)}\n"
        ),
    }

    for name, body in files.items():
        path = os.path.join(out_dir, name)
        with open(path, "w") as f:
            f.write(body)
        typer.echo(f"wrote {path}")


if __name__ == "__main__":
    app()
