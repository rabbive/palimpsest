"""Turn eval/run_eval.py's raw JSON into results/main_table.md + results/ablation.md."""

import json
from collections import defaultdict

import typer

app = typer.Typer()


def _score_table(results: list[dict], group_keys: tuple[str, ...] = ("category", "arm")) -> str:
    buckets = defaultdict(list)
    for r in results:
        if r["llm_judge_score"] is None:
            continue
        key = tuple(r[k] for k in group_keys)
        buckets[key].append(r["llm_judge_score"])

    categories = sorted({k[0] for k in buckets})
    arms = sorted({k[1] for k in buckets})

    lines = ["| category | " + " | ".join(arms) + " |", "|---" * (len(arms) + 1) + "|"]
    for cat in categories:
        row = [cat]
        for arm in arms:
            scores = buckets.get((cat, arm), [])
            avg = sum(scores) / len(scores) if scores else float("nan")
            row.append(f"{avg:.2f} (n={len(scores)})" if scores else "n/a")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


@app.command()
def main(raw: str = "results/raw_eval.json", out: str = "results/main_table.md"):
    with open(raw) as f:
        results = json.load(f)

    table = _score_table(results)
    with open(out, "w") as f:
        f.write("# PALIMPSEST — main results\n\n")
        f.write("BEAM-100K rubric judge score (1.0/0.5/0.0 per rubric item, averaged), by category x arm.\n\n")
        f.write(table + "\n")

    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    app()
