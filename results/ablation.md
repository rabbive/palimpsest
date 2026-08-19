# PALIMPSEST — ablations

Each ablation switches off exactly one read-path mechanism against the same ingested
corpus as arm C, so the difference is attributable to the mechanism and not to a
different write pass.

Coverage: 20 questions across 2 dialogue(s) (7, 8), 120 arm-runs total.

| category | C: PALIMPSEST | C − materialized current view | C − graph-property abstention | C − both |
|---|---|---|---|---|
| abstention | 0.75 (n=4) | 1.00 (n=4) | 0.25 (n=4) | 0.62 (n=4) |
| contradiction_resolution | 0.16 (n=4) | 0.09 (n=4) | 0.16 (n=4) | 0.19 (n=4) |
| event_ordering | 0.12 (n=4) | 0.10 (n=4) | 0.15 (n=4) | 0.07 (n=4) |
| knowledge_update | 0.50 (n=4) | 0.25 (n=4) | 0.75 (n=4) | 0.00 (n=4) |
| temporal_reasoning | 0.00 (n=4) | 0.00 (n=4) | 0.38 (n=4) | 0.19 (n=4) |
| **overall** | **0.31 (n=20)** | **0.29 (n=20)** | **0.34 (n=20)** | **0.21 (n=20)** |
