# PALIMPSEST — cost and latency

Coverage: 20 questions across 2 dialogue(s) (7, 8), 120 arm-runs total.

| arm | judge score | mean latency | p90 latency | mean cost/question | total cost | errors |
|---|---|---|---|---|---|---|
| A: full-context stuffing | 0.46 (n=20) | 32.9s | 46.3s | $0.3107 | $6.21 | 0 |
| B: HydraDB default (infer=True) | 0.34 (n=20) | 38.8s | 62.5s | $0.0596 | $1.19 | 0 |
| C: PALIMPSEST | 0.31 (n=20) | 34.2s | 70.2s | $0.0449 | $0.90 | 0 |
| C − materialized current view | 0.29 (n=20) | 25.1s | 61.0s | $0.0307 | $0.61 | 0 |
| C − graph-property abstention | 0.34 (n=20) | 38.9s | 93.7s | $0.0490 | $0.98 | 0 |
| C − both | 0.21 (n=20) | 27.4s | 43.5s | $0.0488 | $0.98 | 0 |

Cost counts money actually spent: a disk-cache hit is billed at zero, so a reported total reflects the run that populated the cache, not a re-run of it.
