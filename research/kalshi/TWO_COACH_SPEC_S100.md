# THE TWO-COACH SPEC (Tier 3 item 6; S100, written off feed M's MEASURED numbers)

Gate 0c fixed the architecture: ONE shared signal core, TWO coaches (Kalshi initial primary,
NYMEX dailies next), ledgers never pooled. This spec fixes the BOUNDARIES, now grounded in the
lag execution map (`KALSHI_ECHO_MAP_S100.md`) instead of assumption. PRINTED to Greg before
merge per protocol. The dashboard ("Mission Control") renders exactly these interfaces.

## 1. WHAT THE SIGNAL CORE EMITS (one voice per target - the S100 simplification doctrine)

Per session, ONE call per target, each with a NAMED OWNING PLAY; all other plays that touched the
event log as CONTEXT or WATCH, never as competing calls (doctrine_tier3.supersession):

- `block_regime_state`: polarity + conviction (a DESCRIPTOR - demoted per scoring_split)
- `day_side`: direction + owning play + requires-class (open_time vs needs-day-N-1-tape)
- `day_type`: archetype/chain-phase class + owning play
- `magnitude_band`: condition-class band (vol-regime scaled; VOID inside squeeze_watch)
- `timing_notes`: catalyst clock (information_clock + flow_calendar); gap-vs-session ownership
- `watch_list`: retired-rule reminders + checklist reads (flip driver checklist output)

The emit is VEHICLE-AGNOSTIC. Each coach translates it; neither edits it.

## 2. THE NYMEX COACH (full depth)

- Consumes: everything (all 23 decision_state blocks + brain).
- Product: the DAY-BOOK (per-day nets, session cell, settle-excluded) - the primary scored
  product per scoring_split; block lean recorded as regime-state descriptor only.
- Execution: futures fees $5 maker / $25 taker per COACH_REPLAY_S97 - immaterial at our scale;
  DIRECTION is the binding constraint on this leg.
- Ledger: NYMEX coach ledger. Never pooled with any other.

## 3. THE KALSHI COACH (deliberately shallow, measured-subset)

- Consumes: the signal core's emit + the LAG MECHANICS + Kalshi microstructure ONLY. It does not
  re-read the deep stack (build-deep-subset-down; the subset is MEASURED by feed M, not guessed).
- Entry trigger: the NYMEX move (the established lag). MEASURED execution reality on the life:
  minutes of runway on thin brackets (median first-trade delays 110-215s; response rates ATM
  ~42% / NEAR ~30% / FAR ~7.5%), seconds-scale only at the liquid margin.
- ENTRY DESIGN, from the fill/fee wall: MAKER-FIRST. Taker economics (fees ~3.4c RT + spread
  4-15c) do NOT clear the median echo event in this regime; the >=4c fast-tail class on
  tight-spread days is taker's only near-viable cell. Default: rest orders AT the lag (0 fee,
  spread earned), sized top-of-book conservative; taker reserved for the >=4c class.
- Fill evidence: resting-fill probability is a LIVE question (collector books 2026-07-12+;
  paper-trade on Kalshi demo per provisional-until-live). No historical fill claim exists.
- Exit: before the bracket's own settle mechanics dominate (>=16:30 ET flagged; 17:00 EDT
  settle = Pyth per-contract NGD close; 5bd-forward underlying roll respected near LTD).
- Ledger: the ECHO BOOK - scored per-event, net-of-fee maker AND taker framings, never pooled
  with the NYMEX day-book.
- Skill test: NOT the walk. Echo replay of walk calls happens chronologically at G14+ when the
  walk reaches the market's life; until then the coach's scoreboard is live-forward paper.

## 4. THE POLYMARKET LANE (queued, NOT built - Greg's dashboard concept 2026-07-20)

A third venue = a third ledger + its own microstructure/fee/fill feed work before anything
trades. Recorded so it is not lost; enters as CONTEXT-ONLY until its own feed M exists
(doctrine: new inputs default to context, never voice).

## 5. STANDING RULES BOUND INTO THE SPEC

- Ledgers NEVER pooled; per-event scoring everywhere; drift = descriptor.
- The lag is telemetry-watched live (decay watch per fire), never retested.
- Live loop: LLM never in the hot path; playbook pre-set; deterministic executor fires;
  sub-second suffices (7.7ms measured transit vs minutes-scale bracket response = the binding
  clock is the BRACKET, not the wire).
- Winter re-measure: the map's cells are regime-stamped; first cold reprices everything - the
  live collector re-runs the map continuously at go-live.
