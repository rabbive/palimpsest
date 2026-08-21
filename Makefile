.PHONY: setup spike create-db ingest setup-arm-b eval eval-smoke report demo test clean clean-cache clean-eval-state

setup:
	uv sync
	test -d data/BEAM || git clone --depth 1 https://github.com/mohammadtavakoli78/BEAM data/BEAM

spike:
	uv run palimpsest spike

create-db:
	uv run palimpsest create-db

ingest:
	uv run palimpsest ingest-all

# Arm B needs its own database and a one-time infer=True ingest per dialogue.
# Run this before any evaluation that includes arm B.
setup-arm-b:
	uv run palimpsest setup-arm-b

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
	uv run palimpsest classifier-accuracy

# The demo path: the reconciliation timeline, then the current-view contract
# proved against the live database.
demo:
	uv run palimpsest status
	uv run palimpsest timeline 8
	uv run palimpsest verify 8

test:
	uv run pytest -q

# Removes only what costs nothing to regenerate. It deliberately leaves the LLM
# disk cache, the SQLite ledger, and the evaluation checkpoint alone -- each of
# those costs real money or unrecoverable state to rebuild. See the two targets
# below, which are named so you cannot destroy them by reaching for "clean".
clean:
	rm -rf .pytest_cache site/dist
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

# Drops the LLM response cache. Every extraction, reconciliation, and judge call
# it was holding gets re-bought on the next run. Deliberate, never routine.
clean-cache:
	rm -rf .cache

# Destroys the reconciliation record and the evaluation checkpoint: the ledger
# holds the supersession chains and the recovery aliases, and raw_eval.jsonl is
# what makes a run resumable. Rebuilding either means re-ingesting and re-paying.
clean-eval-state:
	rm -rf results/*.sqlite3 results/*.sqlite3-* results/raw_eval.json results/raw_eval.jsonl
