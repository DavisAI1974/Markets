# FORECASTER RUNBOOK — verbose instructions for S93 (Greg S92)

Everything is BUILT and ready to run. This is the explicit "what we want to do, why, and exactly how" for the
next session. Read `SESSION_HANDOFF_2026-07-14_S92.md` first for the state; this is the operating manual.

---

## 0. THE VISION (why we're doing this)
Hand-coded entrance/exit/hold rules are RIGID — a coded threshold ("ride if move > $350") is a POOLED decision
applied to every situation blindly, so it clips winners and eats losers whenever the moment isn't average. We
are replacing that with a **coach**: an agent that has learned WHY natural gas moves (a "brain" of general
patterns + mechanisms) and reads THIS instant's fingerprint to call the play for THAT moment — per-event
judgment, not a pooled rule. The coach calls: when to enter, hang back, ride, let go, buy/sell. A second agent
watches the live tape and suggests adjustments. We follow the coach.

The coach is built by a **self-growing loop**: forecast days BLIND from the brain, score vs actual, distill the
lessons back into the brain, refine, repeat over the whole year until the forecasts are near-perfect BLIND —
then that brain IS the coach.

## 1. WHERE WE ARE (the plays discovered — the brain v1)
`research/kalshi/knowledge/ng_brain.json` holds the current PLAYS (run `python research/kalshi/forecast_harness.py brain-show`):
- **direction.flow_nowcast [the breakthrough]** — `dip_imb_level` (pre-entry order-flow imbalance) calls a
  leg's SIDE: 7%/93% terciles, OOS-validated 100% on strong flow (34/34, 3 unseen days). A NOWCAST (flow as the
  leg is born) — perfect for the Kalshi lag: know NG's way, fire before Kalshi reprices.
- **ride.magnitude_staircase** — the $350 crossing = a 92% "keep riding" event; $500 = 100%. Real-time.
- **exit.recruitment_reversal** — a leg lives while the far-side book RECRUITS liquidity ahead of it; it tops
  when the far side stops/gets eaten (turn_far_thinning flips positive) + support collapses.
- **shape.grind_vs_spike** — grind holds, front-loaded spike round-trips.
- **daytype.*** — weekday archetype + storage-surprise-magnitude (weak day-level trend-vs-range priors).
All warm-season (12 days), per-event, exemplar-cited. NOT yet winter-tested.

## 2. THE MACHINERY (built this session — ready to run)
- `research/kalshi/month_characterize.py` — `characterize_day("NG", day, source="s3")` returns every leg with the
  FULL fingerprint (flow/dipole, exhaustion suite, turning-point turn_*, surprise, curve, weather, outcomes).
  This is the tape reader the whole program runs on.
- `research/kalshi/knowledge/ng_brain.json` (+ README) — the machine brain. Plays are numeric + status-tagged.
- `research/kalshi/coach_replay.py` — **the executable playbook backtest** (the rigid baseline the adaptive coach
  must beat). Applies the plays per leg net-of-fee, per-event, no pooling. `--selftest` PASS. Canary-side +
  INDICATIVE capture proxy for now (real fill model = a JOB below).
- `research/kalshi/forecast_harness.py` — turn-key loop helpers: `decision-state` (blind-safe state for a group),
  `overlay` (guess-vs-actual render), `brain-show`. `--selftest` PASS.
- `scratchpad/ng_group2_decision_state.json` — the next 12 blind days' decision-state, staged.

## 3. THE LOOP — exactly how to run it (JOB 1, Greg's #1)
Repeat this cycle, walking forward through the year; each pass the brain grows:

**(a) Pick a new group** of ~12 NG days never used in any prior pass (learn=12, blind1=12, group2 staged).
   `python research/kalshi/forecast_harness.py decision-state --days D1,D2,... --out scratchpad/grpN_state.json`

**(b) BLIND FORECAST (the agent step).** Spawn an agent; give it `knowledge/ng_brain.json` + the group's
   decision-state JSON. It applies the brain to guess each day's curve (archetype + cumulative-move trajectory),
   writing `scratchpad/grpN_forecasts.json`. **HARD RULE: it must NOT load the tape / characterize_day for these
   days — decision-time state ONLY.** (This is the blind wall; peeking invalidates the test.)

**(c) SCORE.** `python research/kalshi/forecast_harness.py overlay --forecasts scratchpad/grpN_forecasts.json --out research/kalshi/renders/ng_learn_s92/grpN_overlay.png`
   Greg looks at the overlays (per-day, no pooling). Mark days "DONE" (nailed) so future passes skip them.

**(d) MERGE.** The agent distills what it learned (new/refined plays, exemplars, confidence) and MERGES into
   `ng_brain.json` (bump `meta.version`, append to `NG_BEHAVIOR_KNOWLEDGE.md` growth log). Commit.

**(e) Next group.** When the year is built, LOOP BACK to the earliest/worst days and refine with the grown brain
   (early forecasts are worst). Converge until near-perfect BLIND.

**MULTI-AGENT / AWS:** run several agents (one group each), merge at checkpoints (a coordinator folds their
   proposed additions — cleaner than live-write races). To go hands-free (Greg's phone free): a scheduled Routine
   or an EC2 box runs (a)-(d) autonomously — REQUIRES durable creds (the GH secrets / box config), not
   session-pasted.

## 4. JOB 2 — the coach replay / net-of-fee edge (the money test)
`python research/kalshi/coach_replay.py --days D1,D2,...` applies the plays leg-by-leg and reports per-event net.
S93 work: (i) replace the INDICATIVE capture proxy with a real fill/slippage model; (ii) add the venue —
Kalshi echo via the lag (`lag_join.py`) AND/OR NYMEX options (section 6); (iii) net-of-fee at SIZE is the gate.
This tells us whether the coach's plays actually make money before we hand it the wheel.

## 5. THE GUARD (non-negotiable — what keeps the coach honest)
- **General rules, never memorized days.** Blind-refine can slide into memorizing the training days (looks
  perfect, worthless live). The brain must be patterns + mechanism + n. Judge skill on a **TRUE HOLDOUT** (days
  never touched in any pass) + **forward-live** — not the training year.
- **Provisional-until-live.** Every play clears the size-vs-fee wall + paper-trades on Kalshi demo before real
  orders. The coach adapts WITHIN bounded risk caps (the "rules of the game" Greg will hand it).
- **Per-event, never pool-as-verdict.** An extreme rate is a LEAD; individual numbers pinpoint the WHEN.

## 6. NYMEX OPTIONS — the real trading vehicle (Greg's S92 flag: "very soon")
Our edge is KNOWING NG's move (direction nowcast + magnitude + top). The Kalshi echo is one way to monetize it;
**NYMEX options on NG futures are likely the bigger, more liquid, more direct vehicle** — trade the move itself
rather than a lagging binary. S93 scoping:
- We already pull the NG futures tape (Databento GLBX). NYMEX/CME **NG options** (LN / weekly LO, etc.) — pull
  the options chain + greeks from Databento (definitions + a quotes/OPRA-equivalent schema); map our direction/
  magnitude/timing calls onto option structures (long calls/puts for direction+magnitude, spreads for defined
  risk, short premium into exhaustion/range days).
- Why it fits the coach: the plays already speak the option language — direction (which way), magnitude
  ($350/$500 staircase = expected move = strike/expiry selection), timing (US-session concentration = intraday
  expiry / 0DTE-style), exhaustion (when to take profit / flip). The coach calls the option play.
- Execution reality: NYMEX needs an FCM/broker (data-only env can't route orders) — a go-live cost, like Kalshi
  needs a funded account + RSA key. Paper/analog-validate first.
- FIRST STEP (S93): a `nymex_options` survey — what NG option products exist, their liquidity/tick/fees, what
  Databento serves, and how each of our plays maps to an option structure. Then price a few of our best historical
  calls as option trades (was the edge tradeable net-of-premium?).

## 7. HYGIENE (data + infra — do early in S93)
- **Box:** verify the year finished (watch `deploy/box-logs/` -> DONE; span should reach 2026-07). Then
  `python research/kalshi/pull_year_mbp10.py --reconcile-names --start 2025-07 --end 2026-07 --dest s3://bento-568968024170-us-east-2-an/nymex`
  (rename date-only -> dow + write week markers). Then a **FINAL Monday sweep** — `python scratchpad/redownload_mondays.py`
  (or its committed home) — the box minted NEW corrupt Mondays past Sep as it advanced; the runner finds all sub-5KB Mondays.
- **Characterize NG Mondays** (now clean) -> the distinct weekend-gap shape -> add a Monday play to the brain.
- **Greg adds the 3 GH secrets** (DATABENTO_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) -> enable the S3
  workflows (NYMEX-forward AFTER box+reconcile; NWS-hourly anytime). Then git data-branch pushes stop.
- **ROTATE the keys** (standing).

## 8. THE FRONTIER (open problems — where discovery goes)
Direction from-flat FORECAST (vs today's nowcast) · the LIVE running turn-track (far_thinning neg->pos as the
exit) · WINTER/backwardation regime (the decisive OOS test) · direction data (forward news, real consensus,
day-ahead/spot pipeline noms, overnight-lean) · the NYMEX-options vehicle (section 6).

---
**One-line for S93:** run the loop (build the year of blind forecasts, grow the brain), prove the plays net-of-fee
(coach replay), start the NYMEX-options vehicle survey — all under the guard (general rules, true holdout,
provisional-until-live).
