# S55 WALKTHROUGH NOTES (2026-07-03, live with Greg) — JOB 0 leg walkthrough -> JOB 1 spec rounds

Running record of the render walkthrough + Greg's markups (the spec pipeline). Renders:
`docs/renders/s55/legs/` (regenerate `scripts/_s55_render_legs.py`; PNGs gitignored).

## Round 1 — "the losers look side-flipped" (Greg, on the worst-12 sheets)
Observation: worst legs trade at the worst possible points; reversed they'd be great trades.
Suspected code issue. CHECKED, verdict = NOT an inversion:
- Side semantics verified in `_price_zigzag` (+1 = valley confirmed -> LONG, entry at CONFIRM
  index) and P&L math verified against raw prices per side. LONG/SHORT symmetric per cell
  (SHORTs slightly better everywhere).
- FLIP TEST (all sides reversed): zigzag −7.8→−14.2 (zz100), −5.4→−16.6 (zz150) — flipped wins
  58% of legs but wins are bounded ~θ while the 20h monster rides become −1,000bp losses.
  Coinbase bigline +2.0→−22.3. Matches the S54 REVERSED controls (negative everywhere).
- The real mechanism (anatomy render `anatomy_worst_leg.png`): on a FAKEOUT the θ-move that
  TRIGGERS the flip is the entire ripple, so the confirm lands at the ripple's extreme on the
  wrong side BY CONSTRUCTION. Worst-N sheets are hindsight-sorted collections of exactly those.
- One real catch from Greg's eye: bigline on Bybit 30d wins only 21-25% of legs and flipping
  IMPROVES net/leg (−12.6→−9.4, both still lose) — the HH+HL alignment entry is mildly
  ANTI-predictive on that tape (fires at exhaustion; same family as the S54 bell verdict:
  LATE, not wrong).

## Round 2 — Greg's pencil on the anatomy window (XRP 06-05 19:08-20:49)
Greg marked ~5 legs on the worst-leg render ("why did it miss all of those?"). Measured
(`greg_window_overlay.png`): his marks = the oracle θ60 turn sequence — 11 legs, avg ~116bp,
+1,277bp gross available (+1,156 net at perfect turns, taker rt11). The true sequence
alternates perfectly — no direction errors at his scale.
- zz150 in-window: 3 flips net −87bp. 8/11 legs INVISIBLE (<θ); the 3 seen entered 150-176bp
  late (a +169bp leg became the −157 short-at-the-bottom).
- zz60: sees ALL 11 turns (cadence matches the pencil exactly) but pays ~61bp/side ->
  62-91bp legs negative by arithmetic; net −89bp despite perfect sequence match.
- zz100: +147bp this window (window personality — loses −8.1/leg over 30d; never tune off one).
- LAW: θ-confirm capture = swing − 2θ − fees. No θ both sees Greg-scale legs and keeps their
  profit. The pencil-vs-machine gap is ENTIRELY confirm cost, not direction.

## Round 3 — Greg re-attaches the S40 dive anatomy: "maybe not the best trade signal but
## definitely the best flip confirmer"
AGREED and it matches the measured record exactly (tools-are-complementary):
- The S40 2000-winner alignment proves the dive fires AT x=0 with seconds precision = the
  WHEN instrument. S36b: ~5-6bp-from-turn at 1s; deployed fine detector 0.69bp forward.
- Standalone WHICH job is dead (S54 bell P(real)≈0.50; fine lean rings 83/hr) -> the dive must
  be ARMED by coarse structure, never free-running.
- Giveback math on Greg's window with dive-confirm (~12bp round) instead of θ-confirm:
  11 legs × (116 − 12 − 11) ≈ +1,000bp vs −87 (zz150) / −89 (zz60).

## JOB 1a SPEC (sharpened by this walkthrough)
Two-scale machine, roles now precise:
1. COARSE zigzag/leg-state = SCALE + SIDE ("extended ~θ into a leg; next opposing turn is
   worth taking") — arms a narrow window.
2. FINE dipole DIVE + micro price-reversal = the FLIP CONFIRMER at the extreme (replaces
   θ-confirm; pays bps not θ). 30d bins carry buy/sell flow -> dipole computes on them.
3. Baseline = plain θ-confirm zigzag (the S54 tables). Falsifiable claim: dive-confirm
   recovers most of the 2θ giveback on θ100-150-class legs WITHOUT raising the fakeout rate.
   Failure mode to watch: armed windows too wide -> 83/hr ringing re-derived.
4. NO-GATES scoring (net $/hr AND legs/hr); controls mandatory: shuffle, reversed, leakage
   gate, per-week splits × 5 coins.
