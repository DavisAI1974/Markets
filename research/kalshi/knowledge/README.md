# knowledge/ — the agents' "brain" (Greg S92)

Machine-readable knowledge the forecast/coach agents LOAD as context and APPLY. The human-readable view is
`../NG_BEHAVIOR_KNOWLEDGE.md`; this folder is the queryable brain.

- **`ng_brain.json`** — versioned plays + mechanisms + open frontier + ruled-out, per target
  (direction / sustain / turn / daytype). Each play = a callable decision the coach applies live.

## The self-growing loop (how the brain compounds)
1. An agent LOADS `ng_brain.json`.
2. It builds 12 BLIND forecasts for a new group of days (never peeking at actuals).
3. Scored vs actual (human sees the overlays); the agent DISTILLS what it learned.
4. New/refined plays MERGE back into `ng_brain.json` (refine confidence + n, add plays) -> version bumps.
5. Next group. Year built -> loop back, refine the earliest/worst -> converge.
6. Days that get nailed are marked "done" (skip). Endpoint: the brain explains every rise/fall and drives
   the COACH that calls plays live (enter/hang-back/ride/exit/buy-sell), with a live-adjuster agent.

## The guard (non-negotiable)
GENERAL rules with mechanism + n, never memorized days. Skill is judged on days NEVER touched in any pass
(true HOLDOUT) + forward-live - not on the training year. Every play is provisional-until-live: clears the
size-vs-fee wall + paper-trades on Kalshi demo before real orders. The coach adapts WITHIN bounded risk.
