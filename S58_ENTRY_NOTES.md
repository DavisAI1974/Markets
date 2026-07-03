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
**Result (bins, 30d x 5):**
- CHOP (ER<=0.5) is a NON-FILTER as anchored — k>=0 == k>=1 rows identical everywhere, and
  the chop marginal == the unfiltered machine on 3/5 coins. Effective stack = 3 members.
  Fix or drop before reading k literally (it inflates agreement counts by ~1).
- The agreement curve IS the round-2 story made robust: k>=3/k>=4 lifts gross/leg to +2..+7
  across most cells (sol th80c50: +0.07 -> k3 +4.27 -> k4 +5.85; xrp th100c25: -2.25 -> k4
  +6.88; btc th100c25: -2.84 -> k4 +5.42 — BTC now measurable thanks to the mode-0 fix) with
  PART% 97-99 (coverage still ~free) and CAP% 3-6.
- Stack ~= round-2's tight reversal veto in magnitude (not clearly better on gross/leg), but
  from agreement of DISTINCT reads rather than one class — and it produced measurements where
  the single tight veto deadlocked.
- MEMBER MARGINALS (th100 c50): opposing = strongest single on 4/5 coins (+1.7..+4.7);
  exhausting mixed (xrp +4.6 best, btc/doge negative); climax weak alone (doge +3.0 only);
  chop non-filter. DOGE INVERTS opposing (-1.9) — per-cell heterogeneity again; the eventual
  deploy is a PER-CELL member map, never pooled.
- FEES: best cells now cb_real -1.5..-2.5 $/hr (was -4..-7 unfiltered). Breakeven at cb_real
  needs gross/leg ~= 16bp at these cadences; best entry-only stack cells sit at +5..+7. The
  known remaining bleeds: FALLBACK legs (theta-giveback, sell the trough) and the exit side
  (parked — Piece 2). Entry-only may not reach cb_real+ alone; that is not failure, it is the
  budget the exit piece inherits.

**Result (books — the INVERSION sharpens):** on SOL Coinbase books the stack INVERTS: k>=2
stays healthy (+17..21bp/leg gross, cb_real +$0.6..+1.4/hr — barely filtered) but k>=3/k>=4
DESTROY it (-9..-41bp/leg); member marginals flip sign vs bins (opposing -12.8bp/leg on books
vs best-single on bins; chop/pass-all +23.2). The dips the flow reads call best on Binance
are the WORST on the Coinbase SOL window. CONFOUND NOT YET SPLIT: venue microstructure vs
regime/window (books = one ~4-day window; bins = 30d multi-regime). Resolution queued: run
the bins stack restricted to the books' calendar window — if bins-last-4-days also inverts,
it is regime not venue. Plus per-week z on the bins k>=3 lift (if the lift is week-unstable
on bins, the books inversion is just one bad week showing up honestly).

## ROUND 3 CONTROLS (gate + window-match) — THE STACK IS CONDITIONAL, NOT UNIVERSAL

`scripts/_s58_piece1_stack_gate.py`. Three findings, each load-bearing:

1. **Shuffle gate: the k>=3 lift clears the structure-free floor ONLY on SOL** (fwd -7.48 vs
   shuffle -11.93 at th80c50; -5.72 vs -9.21 at th100c50 — a real +3.5-4.4 $/hr structure
   premium). ETH/BTC/DOGE th100 sit AT their shuffle floor (no separation); XRP th80 is BELOW
   it. Leakage PASS everywhere. Per-week: 0/5 positive weeks on every cell at cb_real (fees
   dominate every week; the stack never flips a week positive — entry-alone confirmed unable
   to reach cb_real+).
2. **Window-match splits the SOL inversion: it is VENUE, not regime.** On the SAME recent
   ~4-day window, Binance SOL holds (k0 +2.42 -> k3 +5.18bp/leg) while Coinbase SOL books
   invert — so the flow reads mean different things on the two venues (channel construction
   and/or participant mix). Do NOT port flow-read grades across venues without per-venue
   validation.
3. **The k>=3 lift is REGIME-UNSTABLE on 4/5 coins:** on the recent bins suffixes the naive
   k0 machine beats the stack (eth +0.12 -> -1.87; xrp +8.07 -> -2.11; btc +12.59 -> +6.00;
   doge +5.24 -> +2.47) AND k0 gross is positive on ALL coins in the recent window (the
   recent regime favors naive mid-band dip-entering everywhere). The stack's pooled-30d lift
   is concentrated in other/earlier regimes.

**Verdict:** flow-read confirm-grading is venue-specific AND regime-conditional — per-cell
AND per-regime validation required before it is anything more than a research read. The
venue-portable part of the entry is the PRICE MECHANICS (arming, confirm fraction, fallback).
Priority therefore shifts to the fallback refinement (price-only, the last named entry
bleed), with regime-conditioning of the stack as the follow-on question ("WHEN does the
stack help?" — likely a job for the regime gate thread, per-cell).

## ROUND 5 — THE FALLBACK REFINEMENT (Greg's order: fallback, then machine reruns)

STRUCTURAL FACT (why this round targets k>=3): in the k0 machine the fallback ~never fires —
the first fine dip always confirms before adverse reaches theta ("k0 is all-confirm", XRP
agent). The fallback bleed exists only in VETOED machines (54-63% of k>=3 legs) — and the
member-map reruns will lean on fallbacks harder, so they inherit this fix.
TEST: baseline (flip at raw theta-adverse = sell the trough tick) vs BOUNCE-fallback (once
adverse >= theta with no vetted confirm, flip on the first f_fb recovery off the running
adverse extreme; f_fb in {25%,50%} theta). RISK ACCOUNTING first-class: loss bound loosens
from ~theta to theta+depth-to-first-bounce -> per-leg max-adverse p95/max printed; a blown
tail kills the refinement regardless of P&L.
**Result (bins, 30d x 5): REJECTED as a general fix — and the diagnosis it rested on is
OVERTURNED at mid-band.**
- P&L: bnc25 improves $real on ~6/10 (coin,theta) cells (best: BTC th80 -3.50 -> -2.09 with
  gross +3.1 -> +7.4); bnc50 erratic (ETH/DOGE th80 up, XRP th100 blown: -7.4 gr/leg). No
  uniform winner.
- RISK: the tail price is real and steep — adv p95 78-99 (base) -> 103-140 (bnc25) -> 140-200
  (bnc50); MAX 87-148 -> 154-286 -> 260-539bp. The bounded-loss property is the baseline's
  crown jewel; bnc50 triples the tail.
- COVERAGE: PART% 98-99 -> 84-90 (bnc25) -> 78-82 (bnc50) — bounce-waiting sits wrong-sided
  through 10-20% of oracle legs (Greg's missed-trades axis, directly hit).
- **THE DIAGNOSIS FLIP (the round's real finding): at mid-band the fallback was never the
  bleed.** Base-machine fallbacks OUT-gross confirms on 7/10 cells (XRP th100: FB +5.6 vs
  CONF -1.6; ETH th80: FB +6.4 vs CONF -1.7). The S56 "structurally sells troughs" narrative
  was a FINE-scale/un-vetoed-v2 fact that does NOT transfer to the k>=3 mid-band machine
  (scale-locality strikes again — it applied to the KILL narrative too). The true weak spot
  on the weak coins is VETOED-CONFIRM QUALITY, which is the member-map rerun's business.
**Verdict:** keep the BASELINE fallback (immediate flip, bounded ~theta) as the standard;
carry bnc25 ONLY as a BTC per-cell candidate into the machine reruns (both BTC thetas
improved, tail moderate 166-169 max); the reruns inherit baseline fallback everywhere else.

## ROUND 6 — MEMBER-MAP MACHINE RERUNS (bins; books venue-check separate)

The agent maps re-earned as machines vs their k0/k3 baselines. All maps derived from this
tape — per-week stability is the internal check, OOS waits on books accrual.

- **SOL fade+climax: the round's winner.** gr/leg +5.61/+5.65 at BOTH thetas (vs k3
  +4.27/+2.79), $real -5.91/-4.06, and at th100 the FIRST positive weeks of the whole piece
  (wk+ 2/5). Composition tax visible: leg-slice promised +11.5/+19.8, machine delivers
  ~+5.6 — path effects cost half, as the XRP lesson predicted. Threshold caveat: fade>=27
  is an in-sample quartile anchor — flagged.
- **BTC opposing-mandatory: th80-only, confirmed.** btc_opp th80 +3.86 (vs k3 +3.13);
  btc_opp+bnc25 th80 = the best BTC cell (gr +9.26, $real -1.44, CAP 6%) at the known
  bounce costs (PART 83%). th100 versions negative — th100 stays naive-or-off.
- **DOGE: the map works at th100, NOT th80** (agent had recommended th80 — the machine
  corrects the leg-slice): clmxexh th100 +6.35 ($real -2.49), +cascade-veto +7.24 (-2.20)
  = best DOGE cells; at th80 the map UNDERPERFORMS k3 (+2.74 vs +4.62). zw -8.2/-5.1 =
  weeks uniformly negative at cb_real but tight.
- **XRP death-combo veto: cheap and harmless rider.** Veto barely binds (rare class):
  th100 +2.55 vs k0 +1.51, coverage untouched (PART 100). Keep as a rider on the naive
  machine.
- **Ceiling re-confirmed:** every $real still negative (best -1.44..-4.06/hr) — entry-alone
  cannot cross cb_real; the surviving configs define the per-leg budget handed to Piece 2.

## PER-COIN VERDICTS (coin-specific agents on the leg dumps; Coinbase = deploy frame)

**ETH — DROP from the mid-band deploy round (agent verdict, decisive).** The Coinbase
promise = 2 legs of one tape (top-2 legs = 155% of the cell total; remaining 11 avg -15.8bp;
the same market moves recur across cells via entry_idx — books hold ~6-8 independent swings
total) AND the lucky legs sit in b_climax=0 = the bins fingerprint's false-fire pool. Bins:
k3 confirms -1.66bp/leg while fallbacks +6.4 (the stack selects nothing on ETH); everything
cb_real-negative. RE-ENTRY TEST (named): ~100 accrued Coinbase book confirms in th100 k3
with top-2-excluded mean > +10bp/leg + k3^B3 shuffle-gate pass. ETH false-fire fingerprint
(both-theta): NO-climax + low-ER(<0.075) + slow-fade(<10bpm) + LONG side + hod 18-23 UTC
(win 28-33%, -16..-32bp/leg). ETH winner marks (wire-in item): clmx60>=2.85 (strongest),
er600>=0.18, fade>=28bpm, SHORT side, hod 06-11, dive_depth MID (Q3, not deep). STRUCTURAL:
climax GRADES confirms but ANTI-grades fallbacks (sign flip per kind) — member maps are
per-KIND, never pooled. Honest positive kept: bins k3-confirm improves across 30d thirds
(th100: -16.2 -> +6.5 -> +13.0) but k0 improved too = the regime effect, not an ETH edge.

**SOL — KEEP AS LEAD (agent verdict).** Only coin with a shuffle-cleared k3 bins premium AND
the only net-real-POSITIVE cell in the round: Coinbase books th100 k0 +6.11 net/leg (n=56,
one window, shape only). CORRECTION to the fallback framing: at mid-band SOL fallbacks
OUT-GROSS confirms (+5.5 vs +2.3) — the fallback bleed is a FEE/COUNT bleed (62-63% of stack
legs are fallbacks), not a gross bleed; "refine the fallback" = need it less often. FALSE-FIRE
(both-theta, half-split stable): 3-agreement WITHOUT climax = the false-fire bulk (win 26-27%,
-21/-26 mnet; same sign on books); slow fade (Q1) false-fires, fast fade (>=~27bpm) = only
positive quartile (transfers to books right-signed); DEEP dives passing the stack are fake
(hump: Q2 best, Q4 worst); agree=4 NOT robust (half-split flips). FALLBACK worst = deep-dive
trough-SELL (dive>0.55 & side=-1: win 21-23%, -29 mnet, stable). Books member map: exhausting
HURTS on Coinbase both thetas; opposing softer than the r3 machine-marginal implied. Untuned
combined read fade>=27 & climax=1 = the ONLY net-real-positive confirm region on bins
(+11.5/+19.8 mnet, n=73/54). KNOB REGION (Coinbase): th100 > th80, k0 price mechanics, graded
fade preference, exhausting dropped/negative, dive as size-grade. WINNER SIDE: big winners
nearly INVISIBLE to the 6 causal reads (only climax leans winner) — direct support for the
S35 onset-fingerprint 5th member.

**BTC — KEEP as conditional research cell (agent verdict); NOT adoption; the gating action
is FIXING THE COINBASE BTC BOOK COLLECTOR (155h gap = deploy-venue blind, books n=45).**
Recent-window strength = mostly regime (k0 turns positive in the tail on both thetas) PLUS a
real-looking th80-only stack lift: tail th80 k3 +18.2bp/leg (n=103, t=+2.3; ex-top-3 still
+10.2) — the only cb_real-positive BTC slice (+2.2bp/leg net, TAIL-ONLY, post-selection
caveat). th100: stack does NOT earn (tail k0 +13.1 > k3 +4.1) — th100 naive or off. KNOBS
(bins, pending Coinbase): th80/c0.5/k>=3 with OPPOSING-mandatory (k3^opp: full +7.65 n=55,
tail +31.9 n=17; must re-run as a machine config, leg-slice caveat); agree==4 rare-and-golden
(+67.5 n=8 / +55.7 n=5, same direction both thetas). FALSE-FIRE shape: "MID-EVERYTHING" —
mid fade (13.5-21bpm), mid climax, mid ER, minimal-lag confirms, hod 00-05 UTC; the EXTREMES
are fine (violent fade Q4 +32.2/+12.2, heavy climax Q4 +21.5/+2.1). Fallback worst = SHORT-
DURATION trough-sells (dur Q1: -10.5/-26.6). WINNER SIDE: big winners vs big losers are
NEAR-IDENTICAL on every continuous median (fade 12.6v13.8, clmx 1.84v1.78, er .16v.17) — no
standalone separator; separation lives in bucket/agreement structure = the bucket-
distinctiveness doctrine in the data; third independent argument for the S35 5th member.

**ETH TOP-LEGS AUDIT (Greg: "are those 2 legs our biggest / confident at their start? keep
ETH to fire on just those 2?"):** they ARE the biggest, but the sniper idea fails its own
precondition. The +367/+347 pair = the SAME move in two theta-cells (as is +215/+193) —
~4 independent big moves on the whole books tape. At ENTRY they looked QUIET/ordinary:
climax 0.40 (tape median 1.77, bottom decile), dive 0.17 (median 0.47), fade = median, low
ER. The top-4's only shared trait = quieter-than-average entries — and that exact print on
the 30d tape selects LOSERS (win 28-35%, net -13..-28 across every top-leg-range condition).
Their size came from DURATION (20-48h trend rides), not the entry — unrecognizable at start
by construction. -> No print to snipe on; drop stands (re-entry test unchanged); if ETH's
big riders ever become onset-recognizable it will be via the S35 fingerprint tier, not flow
reads.

**DOGE — KEEP with a REMAPPED stack (agent verdict).** The "inversion" is THETA-LOCAL:
opposing +6.2 at th80 (n=245) but -7.0 at th100 (n=163; negative all 4 sub-windows) —
th100 BUY+opposing = the worst discrete cell in the dataset (n=71, median -25.4bp) = meme
CASCADE-CONTINUATION (persistent opposing flow deep into a 100bp move = still being sold
into), while th80 catches normal absorption. EXHAUSTING = the only member sign-consistent
positive at both thetas (+2.0/+5.3); climax works GRADED at top-quartile clmx60>=3.4 (win
56-57%, +19-26bp), not as the 1.5 bit. Cleanest DOGE number: clmxQ4 & er>=0.14 -> +17.2/+17.0
bp/leg BOTH thetas (z 2.95/2.07, positive 3/4 sub-windows). TOOLING BUG: the ER<=0.5 chop
anchor passes 100% of DOGE legs (er600 range 0.002-0.46) — re-anchor per coin or use
er-quartiles. Map: climax(graded)+exhausting core, opposing = th100-only veto (esp BUY),
low-ER decline mark; th80 c50 the better band. COINBASE CAVEAT: books shape inverts again
(clmxQ4 -29.3 n=28) — the map is a Binance-instrument read; deploy knobs UNSET pending venue
thread. Winner side: lose-print MORE distinctive than win-print on DOGE — match-to-loser
carries the dual-print signal here.

**XRP — DROP THE STACK, KEEP THE NAIVE MACHINE (agent verdict).** The stack lift is a
pooled-window artifact, shown 3 ways: (a) all-legs lift ~0 (CIs straddle zero); (b) week-
concentrated (th100 lift = one early week; dropping w1 flips pooled to -2.3; recent suffix
-16.7); (c) DECISIVE — the stack's own confirms are ANTI-selective: k3 confirm -5.0/-1.6 vs
fallback +1.2/+5.6 (fallback beats confirm 8/10 theta-week cells) — the apparent lift was
COMPOSITION (vetoed confirms replaced by fallback entries). agree=4 does NOT mark winners on
XRP (inverted at th100). DURABLE ANTI-PRINT (the round's single strongest fingerprint):
**opposing+climax WITHOUT exhausting = the death combo** — win 8-21%, -31..-53bp/leg,
replicated 4x (both thetas x both machines, n~75; exhausting=1 legs near-flat). = the
freight-train in member-bit form; matches S36 physics (no dipole collapse = continuation).
Coinbase shape: th80 k0 the only healthy cell (+4.14 gross, 66% win, n=32, n-flagged);
k3 destroys it (SOL-style inversion). Deploy shape: naive k0 th80 c50; death-combo carried
as a graded per-cell veto CANDIDATE; short-side tilt -> sizing axis (Piece 3, parked).
Fallback worst-decile INDISTINGUISHABLE on every descriptor — the fallback bleed is
structural timing, not fingerprintable: supports the price-only fallback refinement.

## THE FIVE-VERDICT BOARD (per-coin round, complete)

| coin | verdict | deploy shape (Coinbase frame) |
|---|---|---|
| SOL  | KEEP — LEAD        | th100 k0 price mechanics; graded fade preference; exhausting negative-weighted |
| BTC  | KEEP — conditional | th80 k>=3 opposing-weighted (bins read); GATED on book-collector fix |
| DOGE | KEEP — remapped    | th80; climax(Q4-graded)+exhausting core; opposing = th100-only veto |
| XRP  | KEEP — naive only  | th80 k0; stack dropped; death-combo anti-print carried |
| ETH  | DROP               | re-entry test: ~100 book confirms, top-2-excluded mean >+10bp + k3^B3 gate |

**THE ROUND'S MASTER FINDING:** on the DEPLOY venue every healthy shape is the NAIVE armed
machine (SOL th100 k0 +6.1 net/leg; XRP th80 k0 +4.1 gross; DOGE/SOL books invert the flow
maps; BTC blind). The flow stack is so far a BINANCE-INSTRUMENT phenomenon. PRICE MECHANICS
PORT; FLOW READS DON'T (r3 controls + 5 independent agents, unanimous). Coinbase flow-read
validation happens only on accrued Coinbase books, per cell.

**NEXT-ROUND QUEUE (entry only, in order):**
1. FALLBACK REFINEMENT (price-only, portable, the shared bleed): fallback waits for its own
   fine dip; also targets SOL's fee/count bleed (fewer fallback legs) + BTC's short-dur
   trough-sells + DOGE/XRP worst tails.
2. MACHINE RE-RUNS of the per-coin member maps (leg-slice reads must be re-earned as machine
   configs: DOGE climax-led map, BTC opposing-mandatory th80, XRP death-combo veto).
3. CHOP RE-ANCHOR per coin (ER<=0.5 passes 100% on DOGE/XRP — bug-class fix).
4. S35 fingerprint wire-in prep (dual-print, micros-first) — the winner side is invisible to
   all six causal reads on every coin (SOL/BTC/DOGE agents independently); the lose-print is
   the more distinctive half on DOGE.
5. Books accrual + venue thread standing: nothing flow-based deploys without per-venue pass.

**CROSS-COIN CONVERGENCES (ETH+SOL+BTC+DOGE+XRP):** (1) CLIMAX = the load-bearing member on both;
(2) fast fade = winner mark / slow fade = false-fire on both; (3) per-kind AND per-venue
member sign flips on both — member maps never pool.

## FINGERPRINTABLE SURFACES (Greg: "is there any other part fingerprintable?" — the map)

Anything recurring with a per-cell distinctive signature at a decision moment. Preconditions
for ALL: causal at the decision cell, assert_no_leakage, per-(cell, band) revalidation,
enough examples per bucket (mid-band cadence 25-90 legs/day/coin fills buckets fast).

ENTRY-SCOPE (this piece):
1. WINNERS at onset — the standing wire-in item (S35 machinery).
2. FALSE-FIRES that pass the stack — the anti-fingerprint (this round's agent question).
   Entry quality = distance-to-winner-print minus distance-to-loser-print.
3. THE DIP ITSELF — grade every candidate dip (real-turn vs mid-leg noise) as a flow/shape
   object; no selection bias, max examples.
4. FALLBACK FIRINGS — the 60-90s window before a trailing-ARM flip; pre-empt the trough-sell.
5. MISSED LEGS — the PART% gaps, fingerprinted from the coverage side.
6. THE REGIME — per-cell "stack-friendly tape" print (r3 controls showed the flow stack is
   regime-conditional; this is the master conditioner for WHICH members to trust WHEN).
   Possibly highest-leverage after winners.

PARKED (other pieces): 7. the TOP/exit (R8 climax-collapse signature half-exists — Piece 2
inherits). 8. MID-TRADE winner state (S35b "in there 2 times" — hold piece). 9. the maker
"can't-refuse" fill moment (S45 dive=fillability — execution layer at deploy).

## PARKED FOR LATER PIECES (Greg: do NOT act on these while entry is open — record only)

Findings about exit/hold/sizing that surfaced during entry work. Append here, never chase.

- **PIECE 2 (exit):** `lean_exit` (R8 lean-collapse) is wired in the executor, INERT at fine
  scale (REV=0.1 retrace IS the collapse exit there), value expected at coarse price-theta
  exits (~28bp vs 151bp giveback). `lean_close` descriptor already recorded per leg. Dive
  S55-R9 wrinkle: NEGATIVE coarse-top depth corr may mark exhaustion — candidate EXIT read.
- **PIECE 3 (hold/size):** the validated 2-axis rank product (clmx_60 quality x size_score
  magnitude) is the deployed sizing stack (S47/S49, leakage PASS all 5 cells) — extend it at
  mid-band rather than invent. dive_depth belongs on the SIZE axis, not the entry veto.
  Trailing-4h-range coarse size axis: sized beat flat 4/5 coins but shuffle beat true 2/5 —
  NOT earned (S55 R11), needs accrued history. Staged-commit spec frozen S57 (starter ->
  $5k all-in, adds maker-posted, confirm threshold scales with band).
- **Fill/execution diagnostics:** taker-share is the cleanest realized net separator (corr
  -0.31, S53) but is measured DURING the leg — diagnose fills with it, never grade entries.
  Book-depth reads are maker/quoting signals (sub-fee-floor as taker entries).

## DEFINITION OF DONE — ENTRY PIECE (Greg, this session)

When the entry is called finished: **PROMOTE the surviving fixes into the platform code and
commit** — the armed mid-band machine + the winning fallback + whatever per-coin member maps
re-earn as machine configs go from `scripts/_s58_*` probes into `odcore/` (platform-composed,
one-version law: paper=live=research through `run_stream`). Standing preconditions carry:
sandbox-first (SANDBOX registry cells, never the baseline), baseline canary bit-identical
(+0 trades, ledger intact), `assert_no_leakage` on every wired read, per-cell registry
entries with the gate record documented. Only after that promotion commit is the entry piece
DONE and Piece 2 (exit) opens.

## STANDING NEXT / OPEN

- **⭐ WIRE THE WINNER FINGERPRINT INTO THE ENTRY (Greg, this session — NEEDS A DEDICATED
  LOOK):** the S35 thread (`bucket-distinctiveness-is-the-goal`) built the per-cell winner
  fingerprint machinery — `odcore/fingerprint.py` (verbatim cheap-micro ports + chunker
  recipe), the 6 micros, the 128-dim OD coeffs + centroid projection (live in
  `_markets_gate_v2.py` heavy tier), and the S35b per-episode ONSET re-anchor (entry
  fingerprint = onset micros + onset coeffs, strictly pre-entry). Greg: predict winners by
  their DISTINCTIVE fingerprint at entry — wire that read into the mid-band entry stack as a
  per-cell member. PRECONDITIONS from the record: (a) the S35b onset canary (encoder must
  reproduce ONSET micros from strictly pre-entry bars) MUST pass before wiring — it was the
  blocking gate then and stays the gate now; (b) mid-band legs are a NEW bucket scale — the
  fingerprint buckets were fine-scale episodes; per-(cell, band) revalidation required
  (scale-locality law); (c) leakage gate (`assert_no_leakage`) on any fingerprint feature at
  the confirm cell. Where it slots: a 5th stack member (graded, per-cell) — "does this dip's
  pre-entry window match this cell's WINNER fingerprint" — complementing the flow reads that
  the r3 controls just demoted to conditional.
  **DUAL-PRINT SPEC (Greg: "didn't losing trades have different coefficients?" — yes):**
  the original centroid dipole was ALWAYS two-projection — H_a=<c,c_win>/||c_win||,
  H_b=<c,c_LOSE>/||c_lose|| (odcore/dipole_predictor.py, verbatim S22/S25 construction, in
  repo). Loser-side data exists (S34 Path-C relabeled losers + ~1,919 cand_sp per-cell
  signatures — archives on Greg's LOCAL E: drive, not this container). S34 nuance:
  de-confounded, the COEFF win/lose separation was weak/null; the MICROS carried it (AUC
  0.72-0.84 on 5 cells), stack added on top. -> Wire the 5th member as match-to-winner
  MINUS match-to-loser, micros-first, coeff tier behind it; the mid-band false-fire
  fingerprint (coin agents, this round) is the new-band LOSE-print being built.

- Fallback refinement: the trailing-ARM fallback legs are the bleed the veto cannot touch
  (structurally sell troughs). Candidate: fallback waits for its own fine flip instead of
  flipping at raw theta-adverse. NOT yet tested.
- Venue-inversion thread (SOL books vs bins) — fan-out agent candidate.
- Gate pass (shuffle + per-week z + leakage) on whatever survives round 3+ — before any talk
  of adoption. Books re-check as windows accrue.
- Piece 2 (exit/lean-collapse) and Piece 3 (staged all-in) DO NOT START until Greg calls the
  entry done.

## ROUND 6b — BOOKS VENUE-CHECK of the machine maps (thin n, shape only)
- SOL fade+climax INVERTS on Coinbase (-22/-36 gr/leg vs k0 +7.8/+22.1) — SOL Coinbase = NAIVE, final for this round.
- **DOGE climax+exhaustion = the ONLY flow map that holds shape on Coinbase** (th100 +15.6 vs k0 +9.3, $real -0.05 ~= breakeven, n~23) — the top per-venue-validation candidate as books accrue.
- BTC opposing-map right-signed on books but n=2-5 (anecdote). XRP death-combo veto never fired in the window (rare class; rider stays).
- PROMOTION SET (entry definition-of-done): odcore gets the armed machine (mode-0 fix + baseline fallback + c-scaled confirm) with a per-cell config registry — Coinbase cells NAIVE (sol th100, xrp th80, doge th100 w/ clmxexh flagged candidate, btc pending collector), bins member maps flagged research-only.

## INFRA (while waiting on books accrual)
- BTC book: the "gap" is BY DESIGN (unified workflow excludes btc: 1-tick control + 100MB-cap risk at 100ms). BUT the superseded book_collector_btc.yml STILL FIRES from the default branch (data/btc-book pushed today; file at 47.2MB and growing toward the S37 cap-stall). SOL/ETH books at ~50MB — the cap will hit ALL book branches. FIX: rotation guardrail + btc grid 1000ms + checkout ref -> canonical.

## ⭐ VENUE FINDING (S58 verification agent, primary sources, 2026-07-03) — KRAKEN PRO US SPOT: 0bp MAKER AT $10M/30d — VERIFIED
- kraken.com/features/fee-schedule + API cross-check: maker ladder 25->0bp; **0.00% maker at
  $10M+ 30d volume** (taker 10bp there). NOT a rebate (the -0.02 floor is stablecoin/FX pairs
  only) — but a lawful, application-free, US-available (Ohio fine; ME/NY excluded) ZERO-maker
  tier at a bar our paper cadence (~$25-30M/mo notional) CLEARS.
- Tier-climb bleed to $10M: **$3,905 one-time** (~1.3-1.6bp effective month 1), then $0 maker
  vs ~$20-24k/mo at Coinbase 8bp. SOL/USD, XRP/USD, XDG(DOGE)/USD online; rate limits trivial
  at our cadence (0.09 events/sec vs Pro 3.75/sec decay). No minimum balance/application.
- ⚠ SCHEDULE CHANGES JULY 9 2026 (6 days): new 17-tier table; $1M+ ladder UNCHANGED (6/4/2/0);
  sub-$50k tiers worsen; adds AoP shortcut ($10M assets-on-platform = instant tier 12).
- **IMPLICATION:** the S57 "cb_top 0/6 ceiling-only" column becomes REACHABLE as kr_mk0
  (0 maker/10 taker at $10M/30d). Every entry table's $top column is suddenly a real venue
  scenario — and the S57 fine-band verdict ("positive ONLY at the 0/6 ceiling") deserves a
  Kraken-priced re-read. CAUTIONS: (a) venue-inversion law — nothing validated on
  Binance/Coinbase ports to Kraken books; we have NO Kraken book collector (bins collector
  exists from S37); building one is the prerequisite for any Kraken cell validation;
  (b) XRP-US relisting implied-not-printed (flagged); (c) intra-month tier-update latency
  assumed per-trade, unverified; (d) queue/fill reality on Kraken books unknown.
- NEXT (queued, not started): kraken book collector (new code, S37 bins collector as base) +
  re-price the S57/S58 tables with a kr_mk0 column (0/10).

## FINE-BAND STATUS CHANGE (Greg: "is the fine grain back in?") — DEAD -> RESEARCH-REOPENED, KRAKEN-GATED
- Live 24h volume snapshot (2026-07-03, both venues' public APIs): Kraken = 35-42% of
  Coinbase on our pairs (SOL $21.5M vs $52.2M; BTC $112M vs $317M; ETH $49M vs $119M; XRP
  $28M vs $67M; DOGE 71% at $5.9M vs $8.3M). Real venue, comparable order of magnitude.
  Depth-at-touch (what fills) unmeasured — book collector required.
- At kr_mk0 (0 maker/$10M/30d) the S57 fine-band toll term vanishes on maker legs: the
  "positive only at the 0/6 ceiling" verdict becomes live because the ceiling is reachable.
  SYNERGY: the fine machine's cadence itself sustains the $10M/30d tier for ALL cells
  (lawful volume-paycheck logic, no rebate needed).
- CONDITIONS before it counts (venue law, proven 2x this session): (1) re-measure the fine
  edge on KRAKEN books (Coinbase-measured +1.9bp/leg does not port); (2) fill-depth reality
  at ~40% Coinbase volume (fine band is fill-capped); (3) taker share ~0 revalidated with
  Kraken cover mechanics; (4) July-9 schedule confirm. -> KRAKEN BOOK COLLECTOR = the next
  infra build (gates fine-band reopen AND Kraken mid-band cells). Entry-piece focus stands.
