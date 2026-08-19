import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

HYDRADB_API_KEY = os.environ.get("HYDRADB_API_KEY", "")
HYDRADB_DATABASE = os.environ.get("HYDRADB_DATABASE", "palimpsest")

# litellm-compatible OpenAI provider, pointed at a custom base URL (pincc.ai proxy).
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://v2.pincc.ai/v1")
LLM_TIMEOUT_SECONDS = float(os.environ.get("PALIMPSEST_LLM_TIMEOUT_SECONDS", "60"))

CHEAP_MODEL = os.environ.get("PALIMPSEST_CHEAP_MODEL", "gpt-5.4-mini")
STRONG_MODEL = os.environ.get("PALIMPSEST_STRONG_MODEL", "gpt-5.5")

EMBEDDINGS_DIMENSION = 1536

RESULTS_DIR = ROOT / "results"
LEDGER_PATH = str(RESULTS_DIR / "ledger.sqlite3")
CACHE_DIR = str(ROOT / ".cache")


def ensure_dirs() -> None:
    """Create the runtime directories a clean clone does not ship.

    `results/` holds the SQLite ledger and the eval outputs, and it is
    gitignored, so a fresh clone has neither. Creating it lazily keeps the
    documented setup steps working without committing an empty directory.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)


BEAM_ROOT = ROOT / "data" / "BEAM"
BEAM_CHATS_100K = BEAM_ROOT / "chats" / "100K"

INGEST_CONCURRENCY = int(os.environ.get("PALIMPSEST_INGEST_CONCURRENCY", "5"))
# HydraDB ingestion is asynchronous and can leave a subset of sources queued.
# Keep write-side backpressure conservative rather than flooding that queue.
HYDRA_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("PALIMPSEST_HYDRA_REQUEST_TIMEOUT_SECONDS", "30"))
HYDRA_BATCH_SIZE = int(os.environ.get("PALIMPSEST_HYDRA_BATCH_SIZE", "8"))
HYDRA_BATCH_TIMEOUT_SECONDS = float(os.environ.get("PALIMPSEST_HYDRA_BATCH_TIMEOUT_SECONDS", "20"))
HYDRA_QUEUE_RETRIES = int(os.environ.get("PALIMPSEST_HYDRA_QUEUE_RETRIES", "2"))
HYDRA_QUEUE_RETRY_BACKOFF_SECONDS = float(os.environ.get("PALIMPSEST_HYDRA_QUEUE_RETRY_BACKOFF_SECONDS", "3"))
# Read-path queries are retried far less aggressively than writes. A write is
# worth six attempts because losing it costs an extraction; a query is not,
# and the read path issues one query per coverage slot plus one for the answer.
# Six attempts with exponential backoff turned a single dead endpoint into
# minutes per question, which is what stalled the first full evaluation.
HYDRA_QUERY_ATTEMPTS = int(os.environ.get("PALIMPSEST_HYDRA_QUERY_ATTEMPTS", "2"))
HYDRA_QUERY_TIMEOUT_SECONDS = float(os.environ.get("PALIMPSEST_HYDRA_QUERY_TIMEOUT_SECONDS", "20"))

MAX_SPEND_USD = float(os.environ.get("PALIMPSEST_MAX_SPEND_USD", "45"))

# Evaluation controls. The first full run was a single sequential pass that
# wrote its output only at the end, so a timeout destroyed 30 minutes of work.
EVAL_CONCURRENCY = int(os.environ.get("PALIMPSEST_EVAL_CONCURRENCY", "4"))
EVAL_QUESTION_TIMEOUT_SECONDS = float(os.environ.get("PALIMPSEST_EVAL_QUESTION_TIMEOUT_SECONDS", "120"))
EVAL_RAW_PATH = str(RESULTS_DIR / "raw_eval.json")
EVAL_CHECKPOINT_PATH = str(RESULTS_DIR / "raw_eval.jsonl")

# USD per 1K tokens, used only for the reported cost column. Override to match
# your provider's price sheet; unknown models fall back to the cheap tier.
PRICE_PER_1K_INPUT = {
    CHEAP_MODEL: float(os.environ.get("PALIMPSEST_CHEAP_PRICE_INPUT", "0.00015")),
    STRONG_MODEL: float(os.environ.get("PALIMPSEST_STRONG_PRICE_INPUT", "0.0025")),
}
PRICE_PER_1K_OUTPUT = {
    CHEAP_MODEL: float(os.environ.get("PALIMPSEST_CHEAP_PRICE_OUTPUT", "0.0006")),
    STRONG_MODEL: float(os.environ.get("PALIMPSEST_STRONG_PRICE_OUTPUT", "0.01")),
}
