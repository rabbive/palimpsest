.PHONY: setup spike create-db ingest eval eval-smoke report demo test clean

setup:
	uv sync
	test -d data/BEAM || git clone --depth 1 https://github.com/mohammadtavakoli78/BEAM data/BEAM

spike:
	uv run palimpsest spike

create-db:
	uv run palimpsest create-db

ingest:
	uv run palimpsest ingest-all

# Resumable: results are appended to results/raw_eval.jsonl as they land, so an
# interrupted run loses at most the questions in flight. Re-running skips what
# already succeeded and retries only what errored.
eval:
	uv run python -m eval.run_eval

# One question per category per dialogue -- enough to prove the harness end to
# end before committing budget to the full sweep.
eval-smoke:
	uv run python -m eval.run_eval --limit-per-category 1 --arms A,B,C

report:
	uv run python -m eval.report

# The demo path: the reconciliation timeline, then the current-view contract
# proved against the live database.
demo:
	uv run palimpsest status
	uv run palimpsest timeline 8
	uv run palimpsest verify 8

test:
	uv run pytest -q

clean:
	rm -rf .cache results/*.sqlite3 results/raw_eval.json results/raw_eval.jsonl
