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

CHEAP_MODEL = os.environ.get("PALIMPSEST_CHEAP_MODEL", "gpt-5.4-mini")
STRONG_MODEL = os.environ.get("PALIMPSEST_STRONG_MODEL", "gpt-5.5")

EMBEDDINGS_DIMENSION = 1536

LEDGER_PATH = str(ROOT / "results" / "ledger.sqlite3")
CACHE_DIR = str(ROOT / ".cache")

BEAM_ROOT = ROOT / "data" / "BEAM"
BEAM_CHATS_100K = BEAM_ROOT / "chats" / "100K"

INGEST_CONCURRENCY = int(os.environ.get("PALIMPSEST_INGEST_CONCURRENCY", "5"))

MAX_SPEND_USD = float(os.environ.get("PALIMPSEST_MAX_SPEND_USD", "45"))
