# S58 ENTRY NOTES — Piece 1 round-by-round record (2026-07-03)

The durable log of the entry piece. RULE (Greg, this session): we work ONLY on the entry until
it is as good as we can get it; old kills are NOT verdicts (S56 grades were rebate-regime +
fixed-25bp-confirm; mid-band at real fees is a new question); every refinement shows its cost
in MISSED TRADES (the old mid-band ceiling), not just per-leg lift. Update this file EVERY
round — chat is not a record.

Scoring frame (all rounds): always-in-market flip machine, mid fills at confirms, $5k flat,
maker-both-sides fee columns cb_entry 40 / cb_early 10 / cb_real 8 / cb_scale 3 / cb_top 0.
Tapes: 30d x 5-coin Binance spot bins (the INSTRUMENT; ~720h each) + Coinbase books (the
DEPLOY-VENUE check; 64-196h, thin at mid-band cadence — never grade off books alone).
Controls: reversed, shuffle, per-week, truncation-invariance leakage check.

## MISTAKES CAUGHT (append-only — read this list before building anything)

1. **R1 look-ahead in the baseline (caught by impossibility, fixed same round):** the S57
   `coarse_zigzag` returns (pivot, confirm, side); `score()` expected (confirm, pivot, side).
   Baseline was entering AT the pivot -> 100% win, +126..210bp/leg. Any flip machine printing
   ~100% win or per-leg gross ~= the full swing IS a tuple-order/look-ahead bug. Normalize
   flip tuple order at every boundary between zigzag variants.
2. **S56 mode-0 bootstrap deadlock resurfaced (round 2, BTC + books "(no legs)"):** v2's
   trailing fallback only ran in mode +-1; a veto that rejects the first-ever confirm strands
   the machine forever. S56 called it moot — it is not moot once any filter is in the loop.
   FIXED round 3: fallback also fires in mode 0. Any "(no legs)" cell = suspect this first.
3. **Books windows are too thin to grade mid-band** (5-20 legs/cell at theta 100): one-window,
   n-tiny — venue SHAPE check only. Do not read books cells as results.
4. **pkill -f with the script name kills the wrapper shell of the new run too** (exit 144
   twice). Use pgrep + explicit PIDs.

## ROUND 1 — armed fine-confirm vs theta-confirm baseline (grid: theta 60/80/100 x c 12.5/25/50%)

Script `scripts/_s58_piece1_entry.py`. Machines: base = plain theta zigzag; armed =
`armed_fine_zigzag_v2` (extreme-anchored arm, c*theta fine confirm, trailing-ARM fallback);
armedV = + R4 `continue`-class veto at the pivot candidate.

**Result (bins):** the v1-era missed-trades problem is GONE — armed fires 24-90 legs/day (at
or above Greg's pencil-scale oracle 7-42/day). But entries are ~coin-flip: win 43-51%, gross
-3..+4bp/leg; total gross bp/HR ~= the baseline's (e.g. sol theta100: base 0.65 legs/h x
4.7bp = 3.0bp/h vs armed c50 1.39 x 2.1 = 2.9bp/h) -> the armed machine slices the SAME
capture into ~3x the legs = pure extra fee toll. Nothing cb_real-positive.
**Verdict:** the bottleneck moved from COVERAGE (v1) to PRECISION (which dip to trust).
The R14 prize (+106..122bp/leg at theta100) is an oracle-entry number; the false-fire cost
currently eats all of it.

**Books (deploy venue, PROVISIONAL one-window):** SOL armed no-veto theta 80-100 showed
+12..+22bp/leg gross, win 50-58%, first cb_real-POSITIVE cells anywhere (+$1.5-1.8/hr);
CAP% 15-19 vs 2-4 on bins. ETH mixed; BTC unusable (collector gap).

## ROUND 2 — veto-strength curve + the MISS LEDGER (none -> continue -> opposing -> reversal)

Script `scripts/_s58_piece1_veto_curve.py`. Added: oracle-leg accounting (orcl/h, PART% =
oracle legs held right-direction, CAP% = gross taken / oracle bp available), dive-depth
quartile grading, worst-10/smallest-10 renders (docs/renders/s58/).

**Result (bins):** the veto curve is REAL and ~monotone on gross/leg, 2-5x lift:
sol th80 c50: -0.09 -> +2.05 -> +5.93 -> +6.72 (none->continue->opposing->reversal);
sol th100 c50: +2.12 -> +5.22; xrp th100 c25: -2.14 -> +5.99. Win% DROPS (51->38) while
gross/leg RISES — the veto declines cheap dips and waits for asymmetric ones (filter earning
its place, not degeneracy). COVERAGE COST ~ZERO: PART% stays 95-100 through the tight vetoes
(the fallback still enters the leg, later) — exceptions: doge th100 c50 reversal (PART 29% =
over-vetoed, past the curve's peak) and the BTC deadlocks (mistake #2).
**CAP% never exceeds ~4 on bins.** Arithmetic: c50/theta100 clean entries on a ~130bp swing
should capture ~+30bp/leg; realized +5-7. The residual bleed = FAKEOUT legs (2x fine cost
each) + FALLBACK legs (theta-giveback, structurally sell troughs, never vetoed by design).
Dive-depth quartiles NON-monotone at coarse pivots (Q2 best) -> not a standalone grader here
(consistent with S55-R9 scale-locality).
**Fees:** best cells cb_real -2..-4 $/hr; zero-fee ceiling only +1.8..+3.7 $/hr/coin. No
adoption candidate; expected this early.

**Books:** SOL inverts the veto — no-veto +22.5bp/leg gross th100 c50 (cb_real +$1.82/hr),
EVERY veto destroys it; tight vetoes deadlock (mistake #2). OPEN QUESTION (named): why does
Coinbase SOL reward the naive armed dip while Binance punishes it — venue microstructure or
one-window luck? Do not resolve by assumption.

## SCRAP-HEAP MINING (two agents, S38-S57 handoffs + full code sweep)

Synthesis: **mid-band is the untested middle** — the archive's descriptors were killed at fine
scale, at coarse scale, as binary gates, or under the dead Bybit-rebate regime; almost nothing
was ever graded at theta 60-100 as a stack member. Standing warnings: (a) GRADED beats GATED —
every hard binary veto eventually lost (freight-train lesson: "content lives in the size
axis"); (b) SCALE-LOCALITY — divergence reversal-class +30/leg at zz150, INVERTED at zz100;
every (band, descriptor) pair revalidates.

Stack candidates (ranked): divergence graded reads (rev_conv/class — round-2-proven at
mid-band); clmx_60 volume climax (S47's only sign-consistent win/lose lever, killed ONLY as a
gate); ER trend-efficiency regime meter (targets the freight-train false-fire class); lean
deceleration `_turn_accel` (the only LEADING read, ~3s pre-vertex, never harvested — needs
causal-trailing adaptation); dive_depth signed (possible INVERTED exhaustion read at coarse
tops). Dead, do not restack: steepness (3x confirmed noise), mi_flow/imb_flow differentials,
confirm-speed, across-trades priors, book-depth as taker entry (sub-fee-floor), the bell.
Reopenable someday: "wrong tail irreducible / causal AUC~0.53" was fine-scale one-window only.

## ROUND 3 — the 4-member AGREEMENT STACK (running)

Script `scripts/_s58_piece1_stack.py`. At every armed dip candidate, four causal reads at the
pivot candidate: B1 opposing (flow vs leg), B2 exhausting (dipole -> 0.5), B3 climax
(vm60/vm600 >= 1.5, untuned S40 anchor), B4 chop (ER <= 0.5, untuned). Confirm when agreement
>= k, k swept 0-4 (k=0 == round-2 none). No fitted weights (nothing to tune off one window).
Includes mode-0 deadlock fix + member-marginal table at th100 c50.
**Question:** does stacking separate entries beyond the best single veto, and what does each
step of conviction cost in PART%/CAP%?
**Result:** (pending — fill in when the sweep lands)

## STANDING NEXT / OPEN

- Fallback refinement: the trailing-ARM fallback legs are the bleed the veto cannot touch
  (structurally sell troughs). Candidate: fallback waits for its own fine flip instead of
  flipping at raw theta-adverse. NOT yet tested.
- Venue-inversion thread (SOL books vs bins) — fan-out agent candidate.
- Gate pass (shuffle + per-week z + leakage) on whatever survives round 3+ — before any talk
  of adoption. Books re-check as windows accrue.
- Piece 2 (exit/lean-collapse) and Piece 3 (staged all-in) DO NOT START until Greg calls the
  entry done.
