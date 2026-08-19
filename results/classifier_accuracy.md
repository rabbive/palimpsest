# Reconciliation classifier accuracy

**88%** over 17 hand-labelled pairs that actually reach the
classifier, and 90% over all 20 pairs including the 3 that `reconcile_fact` resolves deterministically
before any model call. The headline number is the former: counting the
short-circuited pairs as classifier wins would inflate it.

On the 4 pairs deliberately marked *hard* — almost all of them on the
SUPERSESSION / CONTRADICTION boundary — accuracy is 75%. Those pairs are in
the set on purpose; removing them to raise the score would be the wrong move.

The pairs are synthetic and hand-labelled by the author, not drawn from BEAM
ground truth, so this measures whether the classifier applies our taxonomy as we
defined it — not whether the taxonomy is correct.

| expected | predicted | pair | note |
|---|---|---|---|
| REFINEMENT | REFINEMENT | LIVES_IN 'india' -> 'coimbatore, india' |  |
| REFINEMENT | REFINEMENT | REPORTS_TO 'a manager' -> 'priya raghavan' | unnamed -> named, same referent |
| REFINEMENT | REFINEMENT | HAS_DEADLINE 'sometime in march' -> 'march 15 2024' |  |
| REFINEMENT | SUPERSESSION ⟵ miss | USES_TOOL 'a python linter' -> 'ruff' |  |
| SUPERSESSION | SUPERSESSION | REPORTS_TO 'marcus webb' -> 'priya raghavan' |  |
| SUPERSESSION | SUPERSESSION | WORKS_AT 'acme corp' -> 'globex inc' |  |
| SUPERSESSION | SUPERSESSION | HAS_DEADLINE 'march 15 2024' -> 'march 22 2024' |  |
| SUPERSESSION | SUPERSESSION | LIVES_IN 'chennai' -> 'bangalore' |  |
| SUPERSESSION | SUPERSESSION | USES_TOOL 'jenkins' -> 'github actions' |  |
| SUPERSESSION | SUPERSESSION | OWNS 'a honda civic' -> 'a toyota prius' |  |
| SUPERSESSION | SUPERSESSION | SCHEDULED_FOR 'monday standup' -> 'wednesday standup' |  |
| DUPLICATE | DUPLICATE | LIVES_IN 'chennai' -> 'chennai' | identical object; reconcile_fact resolves this without an LLM call |
| DUPLICATE | DUPLICATE | WORKS_AT 'acme corp' -> 'acme corporation' | paraphrase of the same value — does reach the classifier |
| DUPLICATE | DUPLICATE | PREFERS 'dark mode' -> 'dark theme' |  |
| CONTRADICTION | CONTRADICTION | PREFERS 'tea' -> 'coffee' | "always have" denies that the old value was ever true |
| CONTRADICTION | SUPERSESSION ⟵ miss | LIVES_IN 'berlin' -> 'munich' | no move mentioned, no temporal signal either way |
| CONTRADICTION | CONTRADICTION | DISLIKES 'remote work' -> 'the office' | both stated as durable dispositions, mutually implausible |
| CONTRADICTION | CONTRADICTION | ATTENDED 'the berlin conference' -> 'the tokyo conference' | same slot, but attending two events is not actually exclusive — a known weakness of a single-value-per-slot model |
| DUPLICATE | DUPLICATE | HAS_DEADLINE 'march 15 2024' -> 'march 15 2024' | restatement, same date |
| DUPLICATE | DUPLICATE | REPORTS_TO 'priya raghavan' -> 'priya raghavan' | "still" explicitly reaffirms rather than replaces |

## Where it errs

| expected | predicted | count |
|---|---|---|
| REFINEMENT | SUPERSESSION | 1 |
| CONTRADICTION | SUPERSESSION | 1 |
