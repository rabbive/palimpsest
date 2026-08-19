# PALIMPSEST — main results

BEAM-100K rubric judge score (1.0/0.5/0.0 per rubric item, averaged), by category x arm.
B vs C is the load-bearing comparison: it isolates what PALIMPSEST adds over HydraDB's
own auto-extraction rather than over no memory system at all.

Coverage: 20 questions across 2 dialogue(s) (7, 8), 120 arm-runs total.

| category | A: full-context stuffing | B: HydraDB default (infer=True) | C: PALIMPSEST |
|---|---|---|---|
| abstention | 0.00 (n=4) | 0.88 (n=4) | 0.75 (n=4) |
| contradiction_resolution | 0.56 (n=4) | 0.19 (n=4) | 0.16 (n=4) |
| event_ordering | 0.50 (n=4) | 0.40 (n=4) | 0.12 (n=4) |
| knowledge_update | 1.00 (n=4) | 0.00 (n=4) | 0.50 (n=4) |
| temporal_reasoning | 0.25 (n=4) | 0.25 (n=4) | 0.00 (n=4) |
| **overall** | **0.46 (n=20)** | **0.34 (n=20)** | **0.31 (n=20)** |

## Abstention behaviour

| arm | abstained on abstention questions | abstained on answerable questions |
|---|---|---|
| A: full-context stuffing | 0% (n=4) | 0% (n=16) |
| B: HydraDB default (infer=True) | 0% (n=4) | 0% (n=16) |
| C: PALIMPSEST | 75% (n=4) | 56% (n=16) |
| C − materialized current view | 75% (n=4) | 56% (n=16) |
| C − graph-property abstention | 0% (n=4) | 0% (n=16) |
| C − both | 0% (n=4) | 0% (n=16) |
