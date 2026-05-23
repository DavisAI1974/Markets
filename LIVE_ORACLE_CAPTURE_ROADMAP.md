# Live Oracle Capture Roadmap

Created: 2026-05-21

## Goal

Move from the current live mock result toward the oracle winner ceiling without using future data at entry time.

Current gap source:

- Historical h0-h168 result was a hindsight/winner-selected opportunity set, not a live execution stream.
- Live mock has to learn which present-tense traits predict those winner rows.
- The evolve agent's job is to turn hindsight misses into live-observable rules, test them in shadow/probe accounts, and only promote rules that prove themselves on live data.

## Non-Negotiable Accounting

Always report these separately:

- `actual_live_mock_pnl`: closed PnL from promoted/live route accounts.
- `shadow_probe_pnl`: sidecar/probe results used for learning, not proof of production edge.
- `hindsight_oracle_pnl`: best future-path result after the fact.
- `capture_ratio`: actual live mock PnL divided by hindsight oracle PnL over the same audited window.

Never compare winner-only oracle PnL to actual live PnL without labeling it as a ceiling.

## Agent Loop

Every cycle, the evolve worker should:

1. Run `build_live_hindsight_missed_winner_audit.py`.
2. Read `_hindsight_missed_winner_queue.json`.
3. Promote the highest critical/high miss contexts into `_queue.json`.
4. Force mock-only side/family probes through the sidecar matrix.
5. Score closed probe outcomes by side, family, venue, session, entry traits, and exit profile.
6. Promote only live-positive combinations into routing.
7. Kill or quarantine combinations that lose after enough live samples.
8. Write a status file showing capture ratio, promoted rules, killed rules, and next experiments.

## Promotion Ladder

### Stage 0: Hindsight Candidate

Input: an oracle winner row from the audit.

Requirement:

- Future path was positive after fees.
- Entry was missed or exit leaked.
- Context is grouped with repeated similar misses.

Output:

- Candidate experiment in `_candidate_experiments.json`.
- Queue row in `_queue.json`.

### Stage 1: Shadow Probe

Input: queued candidate.

Requirement:

- Test both sides when side is uncertain.
- Test all active families for `NO_STRATEGY` / `NO_TRADE` misses.
- Do not count these probes as production PnL.

Output:

- Sidecar rows in `live_family_registry_compare`.
- Trait ledger rows grouped by entry and exit characteristics.

### Stage 2: Live Evidence Winner

Requirement before promotion:

- Minimum closed trades per candidate: 10 for warning, 30 for promotion.
- Positive realized PnL after fees.
- Win rate above 45% or positive expectancy with controlled drawdown.
- Not dependent on one outlier trade.
- Exit profile has positive net capture, not just oracle-best future path.

Output:

- Update `_routing.json` with promoted context.
- Mark candidate as `promoted_live_evidence`.

### Stage 3: Main Route Execution

Requirement:

- Only promoted live-evidence routes can affect main `route_evidence` PnL.
- Any side/family/exit profile that becomes live-negative is blocked by the live PnL guard.

Output:

- Main live mock opens only promoted routes.
- Probe/learning remains in sidecar.

## Priority Workstreams

### 1. Entry Capture

Current biggest gap: `no_trade_side` / `NO_STRATEGY`.

First promoted move-shape category:

- `SMALL_MOVE_FADE`: small upward push that does not confirm continuation, traded as a sell fade.
- Current catalog bucket: `small_up_sell_fade`.
- Current evidence snapshot: 317 closed shadow trades, 270 winners, 85.2% win rate, +$254.81 after fees.
- Do not generalize this to every sell fade. `extended_up_sell_fade` is currently negative and should stay separate.

Agent tasks:

- Mine top missed contexts from `_hindsight_missed_winner_queue.json`.
- Compare their present-time traits against losers:
  - asset
  - venue
  - side
  - session
  - pressure direction/state
  - trade stage
  - score band
  - dipole band
  - volume band
  - recent move band
  - spread band
- Build directional recognizers for repeated winner traits.
- Force side probes when live side is missing.

### 2. Exit Capture

Current issue: many opened oracle winners close through stop loss, pressure flip, or score degradation.

Agent tasks:

- Compare actual exit to sidecar exit variants.
- Promote exits that improve realized PnL after fees:
  - pressure-hold gated
  - pressure-hold runner
  - hard TP/SL
  - fixed hold windows
  - runner trail profiles
- Kill exits with repeated negative live evidence.

### 3. Side And Family Kill Rules

Current live evidence shows buy-side main trades are strongly negative.

Agent tasks:

- Maintain side/family/venue/session kill and quarantine rules.
- Keep killed traits in sidecar only until they recover with shadow evidence.
- Never let a known losing side/family continue opening in main route execution.

### 4. Capture Ratio Tracking

Agent tasks:

- Write a rolling capture report:
  - actual live mock PnL
  - oracle PnL over same window
  - missed-entry PnL
  - exit-leak PnL
  - capture ratio
  - top promoted live winners
  - top active blockers

Target milestones:

- Phase A: stop main account bleeding.
- Phase B: capture 10% of oracle.
- Phase C: capture 25% of oracle.
- Phase D: capture 40%+ of oracle with stable live samples.

## Current Immediate Controls

Implemented:

- Sidecar buy/sell matrix probes enabled.
- Main route context probes disabled so exploratory probes stay out of main PnL.
- Hindsight evolve worker promotes oracle misses into `_queue.json`.
- Live PnL guard blocks a side in main route execution when it has enough closed live samples, negative PnL, and poor win rate.

Next required controls:

- Keep main PnL separate from shadow/probe PnL in every report.
- Add a promoted-only route mode for main execution.
- Add an evolve status report that shows exactly which candidates moved from hindsight to shadow to promoted to killed.
