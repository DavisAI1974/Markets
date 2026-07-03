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

## Round 4 — "have we wired this in anywhere?" -> the MULTI-ROLE decision (Greg)
Wiring map (verified by grep, not memory):
- Dive as flip TIMING/confirmer: wired NOWHERE (S53 C1 flag stands; no dive trigger in any executor).
- Divergence as ENTRY GATE: available in `swing_maker(entry_gate=...)` but DEFAULT OFF; wired live
  only in the `swing_accum` research thread (S52 SOL miniature).
- Dive as DESCRIPTOR: DEPLOYED — `size_legs` SIZE axis includes z(dive_depth) (S47->S49 OOS,
  sign-consistent all 5 cells). The one role that survived contact with the deployed executor.
GREG DECISION (this round): the dipole dive is a MULTI-ROLE instrument — use it in multiple places
in multiple roles; it is NOT a standalone signal. Role registry (each earns its place separately):
  R1 DESCRIPTOR of trades: dipole read columns on every leg table (expect/aligned_flow/exhausting/
     reversal_conviction at the opening flip). Status: PROPOSED, test defined below.
  R2 DESCRIPTOR of graphs: dipole strip under every leg render panel. Status: PROPOSED.
  R3 SIZING feature: z(dive_depth) in the SIZE axis. Status: DEPLOYED (S49 OOS).
  R4 FLIP CONFIRMER (armed by coarse structure, replaces theta-confirm): JOB 1a. Status: SPEC ONLY.
  R5 ENTRY GATE (divergence exhaustion): swing_accum thread. Status: R&D, SOL-only miniature.
PACE RULE (Greg, this round): test each round before moving on — "we get too far ahead and forget
things." One round = one defined test, run, read, THEN next.
ROUND-4 TEST (defined, not yet run): label every zz100/zz150 leg in the existing 30d tables with
the S36 `divergence()` read at its OPENING flip (causal window [pivot-DIVW, pivot]); report
n/win%/gross/net per expect-class (reversal/flip_risk/weakening/continue), per theta, pooled +
per coin. Descriptor only — NO gate, NO engine change. Pass = the classes separate outcomes
(reversal-class legs beat continue-class); fail = flat across classes.

## Round 4 RESULT (descriptor test, 30d x 5 Bybit)
zz150: PROVISIONAL PASS — reversal-class = the ONLY positive class (+30.2 net/leg, win 52.5%, 8% of
legs) vs continue-class −9.6; positive 4/5 coins (XRP −36 = outlier cell); BUT shuffle z=1.82,
p=0.043 on n=61 — below the z>>2-3 adoption bar. zz100: FAIL/INVERTED (reversal-class worst).
The S36 read is SCALE-DEPENDENT: describes zz150 flips, not zz100, on this tape. Round completes
with a second venue (Binance spot) — QUEUED, not yet run.

## Round 5 RESULT (the lag cut, Greg's dive-graph question)
Measured on all 765 zz150 turns: theta-confirm enters 151bp / 54min (median) from the true pivot;
a fine 25bp price-reversal confirm enters 26bp / ~1min — SAVES 125bp/side, available again at exit.
Catches: (1) fine confirm is equally fast on fakeouts — speed does not discriminate; dipole read at
that moment lifts P(real) only 0.36->0.48. (2) measurement was HINDSIGHT-ARMED (evaluated only
inside real zz150 flip windows) — the causal ARMING RULE is the un-built piece.

## Rounds 6-7 RESULT (Greg: clone the zigzag bounded-loss into the fine machine)
v0 (fine zz25 executes, exit on ANY fine flip against, coarse zz150 side): FAIL −80/hr total.
The CLONE WORKED (worst leg −73 vs −168) but free-running fine exits churned 45-103 tr/day at
~-fees/leg. v1 (fine-25 entry, trailing-X stop, re-enter on agreeing fine confirm): FAIL at X=40/
60/80 (−47/−22/−13/hr), monotone toward zz150 (−2.9/hr) as X grows; forward beats REVERSED by
+13-18/hr at every X (coarse side carries real signal) but churn fees dominate.
JOINT LESSON (three rounds converge): the fine entry saves 125bp ONCE per leg; unlimited
re-entries pay 11bp+ dozens of times. The machine must trade at COARSE CADENCE (~5 legs/coin/day)
with fine EXECUTION — one-shot entry per coarse leg, stop-once-then-wait, armed exits. Every dead
end this session points at the same missing part: the causal ARMING rule (when to listen to the
fine machinery), entries AND exits.

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

## Round 8 RESULT (Greg: "invert that graph" — dive as EXIT fine-tuner)
`inverted_exit_anatomy.png`: 765 zz150 legs aligned to the EXIT turn, flow signed WITH the ride.
Flow lean CLIMAXES at the exact top (+0.40 at x=0 — the strongest with-ride lean in the +/-600s
window = the S45 "can't refuse" maker-exit moment), then COLLAPSES through zero to -0.17 within
60s, while price has given back only ~28bp (vs 151bp at the theta-exit). Dive min -0.267 at +60s
— more violent than the entry-side dive. Exit-confirm saving ~123bp/side, mirroring round 5's
125bp at entry (~250bp/leg total = the S54 giveback ledger prize, both sides now MEASURED).
Asymmetry: entry dive fires AT x=0 (S40); exit collapse completes +30..+60s AFTER the top.
Caveats: mean-of-765 (per-leg noisier); hindsight-aligned (arming still the un-built piece);
post-top sell-lean partly price-correlated (but a full sign flip on 28bp giveback exceeds that).
ROUND 9 (defined, not run): per-leg CAUSAL exit test — armed by leg extension, exit on lean
zero-cross/dive threshold, vs theta-exit baseline, NO-GATES scoring + full controls.

## Round 9 RESULT (Greg: wire the dive depth/steepness DESCRIPTION into the leg tables)
Prior record located: S40 "steepness is noise; DEPTH is the signal" (depth->|move|, Greg's
big-vs-small correction) -> S47 reproduced stronger (+0.07..+0.165 sign-consistent all 5, fine
lean-pivot scale) -> DEPLOYED in the swing_maker SIZE axis. R1 WIRED: `_s55_dump_legs_dipole.py`
-> `_s55_legs_zigzag_bybit30d_dipole.csv` (2,433 legs x dive_depth/lean_pivot_signed/steepness/
dipole_class/rev_conv, all causal at the opening pivot).
VALIDATION AT COARSE SCALE: does NOT reproduce — corr(depth,|move|) at zz150 sign-INCONSISTENT
(sol −0.145, eth −0.160, doge −0.138, btc +0.196, xrp +0.059); steepness ~noise (S40 re-confirmed).
Fine-scale deployed usage UNTOUCHED (different object: lean@lean-pivot at theta~23bp). Readings
kept open: (a) scale-locality of dipole descriptions (matches round 4's zz150-vs-zz100 flip);
(b) proxy mismatch (60s lean @ price-pivot vs deployed lean-pivot; coarse analogue may need a
leg-scale lean window). Wrinkle (one data point): NEGATIVE depth corr at coarse tops fits round
8's climax-burnout picture — deep coarse-pivot lean may mark exhaustion, not fuel.
STANDING: every (scale, descriptor) pair earns its own validation before it feeds sizing/arming.
