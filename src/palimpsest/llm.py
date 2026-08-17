"""Single entry point for LLM calls. Disk-cached, retried, JSON-parsing aware.

Uses litellm so the provider can be swapped without touching call sites. Points
at a custom OpenAI-compatible base URL (config.LLM_API_BASE) rather than the
public OpenAI endpoint.
"""

import hashlib
import json

import litellm
from diskcache import Cache
from json_repair import repair_json
from tenacity import retry, stop_after_attempt, wait_exponential

from palimpsest import config

_cache = Cache(config.CACHE_DIR)


def _cache_key(model: str, prompt: str, system: str, params: dict) -> str:
    blob = json.dumps({"model": model, "prompt": prompt, "system": system, "params": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True)
def _call(model: str, messages: list[dict], temperature: float) -> str:
    resp = litellm.completion(
        model=f"openai/{model}",
        messages=messages,
        temperature=temperature,
        api_key=config.LLM_API_KEY,
        api_base=config.LLM_API_BASE,
    )
    return resp.choices[0].message.content


def complete(
    prompt: str,
    system: str = "",
    model: str = config.CHEAP_MODEL,
    temperature: float = 0.0,
    use_cache: bool = True,
) -> str:
    params = {"temperature": temperature}
    key = _cache_key(model, prompt, system, params)
    if use_cache and key in _cache:
        return _cache[key]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    content = _call(model, messages, temperature)
    if use_cache:
        _cache[key] = content
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
