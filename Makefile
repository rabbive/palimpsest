.PHONY: setup spike create-db ingest eval report demo test clean

setup:
	uv sync
	test -d data/BEAM || git clone --depth 1 https://github.com/mohammadtavakoli78/BEAM data/BEAM

spike:
	uv run palimpsest spike

create-db:
	uv run palimpsest create-db

ingest:
	uv run palimpsest ingest-all

eval:
	uv run python -m eval.run_eval

report:
	uv run python -m eval.report

test:
	uv run pytest -q

clean:
	rm -rf .cache results/*.sqlite3 results/raw_eval.json
