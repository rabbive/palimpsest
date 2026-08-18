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

LEDGER_PATH = str(ROOT / "results" / "ledger.sqlite3")
CACHE_DIR = str(ROOT / ".cache")

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

MAX_SPEND_USD = float(os.environ.get("PALIMPSEST_MAX_SPEND_USD", "45"))
