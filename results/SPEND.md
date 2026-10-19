# Spend log

| date | run | LLM usage line | remaining |
|---|---|---|---|
| 2026-10-19 | start | — | $50.00 |

## Models

- The proxy (`LLM_API_BASE`) no longer lists `gpt-5.4-mini` or `gpt-5.5`, the ids currently set in `.env`. Model settings are unchanged for now.
- Cheap model: the user picked `gpt-6-luna`. A test call to it returned "Upstream gateway error" twice. `gpt-5.6` does answer.
- Strong model: the user picked Opus 5.5. `claude-opus-5-5` returns `model_not_found` on this proxy, so the strong model is pending the user.
- Prices are pending the user. The meter uses the old defaults, so reported spend is approximate.
- Each proxy call carries about 4.4K mostly-cached prompt tokens of proxy overhead.

## Starting state 2026-10-19

HydraDB source counts: not obtained. Every read call (`list_facts`, `palimpsest` / collection 7) returns HTTP 402 from api.hydradb.com:
`FREE_PLAN_DEPRECATED: This workspace is on the Free plan, which has been deprecated. Upgrade to a paid plan to continue.`
No write calls were made.

`uv run palimpsest status` (local ledger, no network):

```
dialogue 1: 72 current
dialogue 1: 20 historical
dialogue 2: 72 current
dialogue 2: 26 historical
dialogue 3: 63 current
dialogue 3: 26 historical
dialogue 4: 31 current
dialogue 4: 20 historical
dialogue 5: 36 current
dialogue 5: 29 historical
dialogue 6: 116 current
dialogue 6: 61 historical
dialogue 7: 144 current
dialogue 7: 66 historical
dialogue 8: 135 current
dialogue 8: 55 historical
hydra_pending is empty
recovery aliases: 16
```
