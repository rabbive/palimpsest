"""Single entry point for LLM calls. Disk-cached, retried, JSON-parsing aware.

Uses litellm so the provider can be swapped without touching call sites. Points
at a custom OpenAI-compatible base URL (config.LLM_API_BASE) rather than the
public OpenAI endpoint.

Every call is metered. Two numbers come out of that: a global running spend,
which enforces the ``PALIMPSEST_MAX_SPEND_USD`` budget cap, and a per-scope
total, which lets the eval harness report cost next to accuracy for one
question. Cache hits are free and are counted as such -- the reported cost is
money actually spent, not money that would have been spent without the cache.
"""

import contextvars
import hashlib
import json
import threading
import time

import litellm
from diskcache import Cache
from json_repair import repair_json
from tenacity import retry, stop_after_attempt, wait_exponential

from palimpsest import config

_cache = Cache(config.CACHE_DIR)

_spend_lock = threading.Lock()
_total_spend_usd = 0.0
_total_calls = 0
_cache_hits = 0

# Per-scope accounting. A ContextVar rather than a global because the eval
# harness answers several questions concurrently and each needs its own total.
# The value is a stack: a call is billed to every open scope, so wrapping the
# read path in one scope and the whole eval question in another gives the outer
# scope the read path's cost plus the judge's, not zero.
_scope_stack: contextvars.ContextVar[tuple] = contextvars.ContextVar("palimpsest_llm_scopes", default=())


class BudgetExceeded(RuntimeError):
    """Raised instead of spending past config.MAX_SPEND_USD."""


class UsageScope:
    """Context manager accumulating cost and token counts for the calls inside it.

    Scopes nest, and a call is billed to all of them. Also usable as an async
    context manager so a coroutine can hold one across awaits.
    """

    def __init__(self) -> None:
        self.cost_usd = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self._totals: dict = {}
        self._token = None

    def __enter__(self) -> "UsageScope":
        self._totals = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
        self._token = _scope_stack.set(_scope_stack.get() + (self._totals,))
        return self

    def __exit__(self, *exc) -> None:
        self.cost_usd = self._totals.get("cost_usd", 0.0)
        self.input_tokens = self._totals.get("input_tokens", 0)
        self.output_tokens = self._totals.get("output_tokens", 0)
        self.calls = self._totals.get("calls", 0)
        if self._token is not None:
            _scope_stack.reset(self._token)

    async def __aenter__(self) -> "UsageScope":
        return self.__enter__()

    async def __aexit__(self, *exc) -> None:
        self.__exit__(*exc)


def price_of(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call. Unknown models fall back to the cheap tier's rates."""
    in_rate = config.PRICE_PER_1K_INPUT.get(model, config.PRICE_PER_1K_INPUT.get(config.CHEAP_MODEL, 0.0))
    out_rate = config.PRICE_PER_1K_OUTPUT.get(model, config.PRICE_PER_1K_OUTPUT.get(config.CHEAP_MODEL, 0.0))
    return (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate


def spend_usd() -> float:
    return _total_spend_usd


def usage_summary() -> dict:
    return {"spend_usd": _total_spend_usd, "calls": _total_calls, "cache_hits": _cache_hits}


def reset_usage() -> None:
    global _total_spend_usd, _total_calls, _cache_hits
    with _spend_lock:
        _total_spend_usd = 0.0
        _total_calls = 0
        _cache_hits = 0


def _record(model: str, input_tokens: int, output_tokens: int) -> float:
    global _total_spend_usd, _total_calls
    cost = price_of(model, input_tokens, output_tokens)
    with _spend_lock:
        _total_spend_usd += cost
        _total_calls += 1
    for scope in _scope_stack.get():
        scope["cost_usd"] += cost
        scope["input_tokens"] += input_tokens
        scope["output_tokens"] += output_tokens
        scope["calls"] += 1
    return cost


def _check_budget() -> None:
    if config.MAX_SPEND_USD > 0 and _total_spend_usd >= config.MAX_SPEND_USD:
        raise BudgetExceeded(
            f"spent ${_total_spend_usd:.2f} of the ${config.MAX_SPEND_USD:.2f} cap; "
            "raise PALIMPSEST_MAX_SPEND_USD or cut dialogues"
        )


def _cache_key(model: str, prompt: str, system: str, params: dict) -> str:
    blob = json.dumps({"model": model, "prompt": prompt, "system": system, "params": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
def _call(model: str, messages: list[dict], temperature: float) -> tuple[str, int, int]:
    resp = litellm.completion(
        model=f"openai/{model}",
        messages=messages,
        temperature=temperature,
        api_key=config.LLM_API_KEY,
        api_base=config.LLM_API_BASE,
        timeout=config.LLM_TIMEOUT_SECONDS,
    )
    usage = getattr(resp, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    return resp.choices[0].message.content, input_tokens, output_tokens


def _cached_content(entry) -> tuple[str, int, int] | None:
    """Read a cache entry written by either the current or the pre-metering format.

    Entries written before token accounting existed are bare strings. Rejecting
    them would silently re-buy every extraction and reconciliation call already
    paid for, so both shapes are accepted.
    """
    if isinstance(entry, str):
        return entry, 0, 0
    if isinstance(entry, dict) and "content" in entry:
        return entry["content"], int(entry.get("input_tokens", 0)), int(entry.get("output_tokens", 0))
    return None


def complete(
    prompt: str,
    system: str = "",
    model: str = config.CHEAP_MODEL,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> str:
    global _cache_hits
    params = {"temperature": temperature}
    key = _cache_key(model, prompt, system, params)
    if use_cache and key in _cache:
        cached = _cached_content(_cache[key])
        if cached is not None:
            with _spend_lock:
                _cache_hits += 1
            return cached[0]

    _check_budget()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    content, input_tokens, output_tokens = _call(model, messages, temperature)
    _record(model, input_tokens, output_tokens)
    if use_cache:
        _cache[key] = {"content": content, "input_tokens": input_tokens, "output_tokens": output_tokens}
    return content


def complete_json(
    prompt: str,
    system: str = "",
    model: str = config.CHEAP_MODEL,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> dict | list:
    raw = complete(prompt=prompt, system=system, model=model, temperature=temperature, use_cache=use_cache)
    return _parse_json(raw)


def timed(fn, *args, **kwargs) -> tuple:
    """Run fn and return (result, elapsed_seconds)."""
    started = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - started


def _parse_json(raw: str):
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(repair_json(text))
