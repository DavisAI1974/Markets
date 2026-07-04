# DIPOLE LANE FOLLOW-UPS — S61 (dipole specialist, research-only)

Session 61, 2026-07-04. Successor to `dipole_lane_report_s61.md` (repo root) — this file
executes its two OWED FOLLOW-UP TESTS (Greg-ordered) plus Greg's mid-session JOB C add.
Nothing wired, nothing committed; all scripts/artifacts in this scratchpad.
House rules: circular-shift/permutation null on every claim; per-cell/per-pair, never pooled;
$/hr leads every economic claim (Greg's S61 standing rule); data / interpretation /
deflationary reads kept separate; nulls are deliverables. Kraken untouched.

## EXECUTIVE SUMMARY

- **JOB A (coupling-strength decider): NOT VOL-STATE — the cross-coin coupling is
  DIRECTIONAL and survives every vol control on all 6 pairs — but the MI lens adds NOTHING
  beyond rolling signed correlation** (per-window MI == Gaussian-implied MI of the window's
  Pearson rho, to within a small NEGATIVE residual, day_t −20..−40). The vol-matched
  sign-shuffled surrogate kills 60–70% of the above-floor MI (real−surr day_t +6.9..+9.4);
  the MI~H_a relation survives WITHIN market-vol terciles (17/18 strata positive, day_t up
  to +17.6); pair ranking (sol > xrp > doge) is split-half stable for both majors — but
  tracks bin-coverage/liquidity, so pair-level differences stay confounded. OFFICE SPEC:
  the per-cell regime-conditioner descriptor should be **rolling cross-coin signed corr**
  (identical information, ~1000x cheaper than KSG MI), descriptor tier only.
- **JOB B (queue-level fill toxicity): the honest fill model ATTENUATES the mark and the
  $/hr save is SUB-NOISE on the real-spread cells — NO quoting overlay earned.**
  $/hr first: skipping toxic-decile posts saves sol **+2.3 $/hr** at $5k (floor −9.0±9.5,
  z≈+1.2 — sub-noise), doge +9.7 (z≈+0.9), xrp −0.8 (null), btc +12.6 (z≈+2.3 but the
  tickless-degenerate cell, and its whole posting game bleeds −30 $/hr). The per-fill decile
  map shrinks 25–70% vs the taker-print proxy (sol H10 −0.146bp z −2.0 survives marginally;
  doge/btc drop to |z|<1.6; xrp null as before). The fill-probability confound is REAL and
  now measured: toxic-decile posts fill MORE (+4.5pp) and FASTER (−2s median). Spec: keep
  `bn_nf_pre` as a FREE descriptor column on sol/doge sandbox fills; no quoting change.
- **JOB C (big losses vs the whole dipole family): NOTHING NEW SURVIVES — the cross-venue /
  cross-coin flow channels can tell "leg in trouble" from "winner" (z up to +6.7) but
  CANNOT tell a DEATH from a RECOVERY (D-R z ≤ +2 everywhere, increment-over-own-flow
  z ≤ +0.7), which is the only discrimination that pays.** The mitigation stack graded in
  $/hr is at/below its shuffle floor on every cell. The dipole family's honest answer to the
  big losers remains the already-wired per-cell corrector diagonal + the S35 fingerprint
  tier. Full numbers below; the "death = dip that didn't come back" degeneracy reproduces
  on a fifth independent read.

---

## JOB A — the coupling-strength decider (structure vs shared vol-state)

Scripts: `s61f_jobA_volstate.py` → `s61f_jobA_results.json` (+ add-on
`s61f_jobA_gauss_excess.py` → `s61f_jobA_gauss.json`). Construction identical to the prior
run (Binance 30d 1s bins, 10s-aggregated returns, windows of 40 rows stride 20, Vasicek H,
KSG-1 MI), 6 pairs, never pooled. ~12.9k windows/pair, ~30 days; day-level t-stats
throughout (windows overlap 50%; days are the independent unit).

### Test 3 first (the direct control) — vol-matched surrogate

Sign-shuffled major: |10s returns| preserved EXACTLY (vol clustering intact, window RV
bit-identical), signs iid random (directional pairing destroyed). Strength meter re-run
against the same alt:

| pair | REAL slope / r2 / meanMI | SURR slope / r2 / meanMI | shift floor | real−surr day_t |
|---|---|---|---|---|
| btc→sol | +0.080 / 0.36 / 0.188 | +0.016 / 0.09 / 0.066 | 0.027 | +8.8 |
| btc→doge | +0.057 / 0.28 / 0.130 | +0.012 / 0.07 / 0.051 | 0.022 | +7.4 |
| btc→xrp | +0.068 / 0.33 / 0.163 | +0.013 / 0.07 / 0.060 | 0.024 | +8.4 |
| eth→sol | +0.074 / 0.30 / 0.204 | +0.015 / 0.08 / 0.070 | 0.025 | +9.4 |
| eth→doge | +0.049 / 0.20 / 0.135 | +0.008 / 0.03 / 0.054 | 0.023 | +6.9 |
| eth→xrp | +0.057 / 0.25 / 0.164 | +0.010 / 0.04 / 0.060 | 0.023 | +8.5 |

DATA: the surrogate does NOT reproduce the meter. 60–70% of the above-floor MI is carried
by the SIGNS (directional co-movement); the magnitude/vol channel contributes a real but
minor share (surr−floor ≈ +0.03..+0.05). **The "meter fires on the surrogate at the same
strength" kill did NOT fire → the coupling is not vol-state bookkeeping.**

### Test 1 — vol double-sort (market-wide instrument, not linear residualization)

Market vol state V = mean over the 5 coins of z-scored log window-RV (a third-variable,
market-wide instrument; the S61 methodological rule — double-sort, never linear
residualization — honored). Within V terciles, the MI~H_a read:

- H_a(top tercile)−(bottom) MI difference positive in **17/18 strata**, day-level t +3.1..+17.6
  (sole exception: eth→doge low-vol tercile, −0.005, t −1.1 → the meter is a HIGH-state
  instrument on the least-covered pair).
- Within-stratum slope is strongly CONVEX in V: top-V-tercile slopes 0.21–0.29 vs low-V
  0.003–0.012 — coupling intensity grows superlinearly with the market state.
- The surrogate's within-stratum slopes are ~0 in low/mid V and 3–4x smaller than real in
  top-V — the within-stratum survival is also directional, not magnitude.

DATA verdict: **the MI~H_a relation survives inside market-vol strata on all 6 pairs**
(one low-state stratum excepted). A pure common-vol-factor story would have flattened it.

### Test 2 — cross-pair discrimination

Split-half (≈15d/15d): per-pair slope and matched-state (top-V) meanMI, both halves:

| pair | slope h1/h2 | meanMI_topV h1/h2 |
|---|---|---|
| btc→sol | +0.095/+0.063 | 0.407/0.279 |
| btc→xrp | +0.079/+0.055 | 0.349/0.245 |
| btc→doge | +0.069/+0.042 | 0.305/0.190 |
| eth→sol | +0.083/+0.059 | 0.437/0.305 |
| eth→xrp | +0.064/+0.046 | 0.349/0.242 |
| eth→doge | +0.058/+0.035 | 0.322/0.194 |

DATA: the LEVEL is nonstationary (first half hotter everywhere — a market-state effect),
but the pair ORDERING sol > xrp > doge is stable in both halves for both majors, and
sol's excess over doge (~0.10–0.12 MI at matched state) is large vs the floor sd.
DEFLATIONARY (load-bearing): the ordering exactly tracks per-coin trade-second coverage
(sol 61% > xrp 51% > doge 39%) — sparse bins attenuate KSG MI — so **pair-specific
differences remain coverage-confounded; do not read them as pair-specific law.**

### The add-on that decides what the meter IS — Gaussian-implied-MI excess

Per window: rho = Pearson(major, alt), MI_gauss = −0.5·ln(1−rho²); excess = MI_KSG −
MI_gauss − KSG small-sample bias (measured on rho-matched Gaussian surrogates, n=40,
400 draws × 12 rho bins):

| pair | meanMI | MI_gauss(rho) | excess (day_t) | mean rho by activity tercile |
|---|---|---|---|---|
| btc→sol | 0.188 | 0.272 | −0.054 (−32) | 0.40 / 0.57 / 0.74 |
| btc→doge | 0.130 | 0.205 | −0.057 (−40) | 0.34 / 0.48 / 0.67 |
| btc→xrp | 0.163 | 0.242 | −0.054 (−24) | 0.39 / 0.54 / 0.70 |
| eth→sol | 0.204 | 0.286 | −0.050 (−24) | 0.41 / 0.58 / 0.76 |
| eth→doge | 0.135 | 0.210 | −0.055 (−32) | 0.34 / 0.48 / 0.68 |
| eth→xrp | 0.164 | 0.238 | −0.051 (−21) | 0.38 / 0.54 / 0.70 |

DATA: the per-window dependence carries **zero content beyond the signed linear
correlation** — if anything slightly sub-Gaussian (no tail-dependence at the 10s/400s
scale), uniformly across pairs and states. The whole "coupling strength" object = rolling
signed corr, which rises 0.34→0.76 across activity states (the known corr-with-vol
phenomenon, now measured per pair, per state, shift-nulled).

### JOB A VERDICT (per charter: STRUCTURED / VOL-STATE / UNDECIDED)

**All 6 pairs: NOT VOL-STATE.** The coupling is directional (sign-carried), survives the
market-vol double-sort, and its state-dependence is real. But the honest composite label is
**DIRECTIONAL-LINEAR**: the MI lens is exactly rolling signed correlation in nats — no
beyond-Gaussian structure to justify the heavier estimator, and the M1 null-membership
question (law-like vs generic, INFO-040/041 sense) remains floor-blocked as before.

INTERPRETATION (separate): "majors and alts co-move directionally, more so when the market
is active, with the intensity readable per pair per window" — real, robust, and fully
classical. The dipole program's contribution here is the VALIDATION DISCIPLINE (surrogate +
double-sort + Gaussian-excess), not a new object.

OFFICE (spec only, nothing wired): per-cell regime conditioner, DESCRIPTOR tier —
**rolling cross-coin signed corr** (e.g. 400s window vs BTC), NOT KSG MI (identical
information at ~1/1000 the compute; the Gaussian-excess table is the license). Falsifiable
next test unchanged from the prior report: does per-cell entry quality / corrector
performance differ between high- and low-corr states beyond a vol control (double-sort,
per cell, shift-nulled)?

DEFLATIONARY READS (visible): (i) pair-level differences are coverage-confounded (above);
(ii) corr-with-vol is a known market phenomenon — the finding disciplines the office spec,
it does not create an edge; (iii) 10s aggregation hides sub-10s structure by construction.

---

## JOB B — fill toxicity at the QUEUE level (the honest-fill test owed)

Scripts: `s61f_cbq_cache.py` (per-second best-level sizes + spread from the raw books;
doge's binned level offsets round to 0 so limit prices come from the record's `spread`
field on all cells) and `s61f_jobB_queue_toxicity.py` → `s61f_jobB_results.json`.
SELFTEST: the vectorized fill rule reproduces `odcore.swing_maker._queue_fill_index`
exactly on 200 random posts (PASS). Design: every era-interior second = a candidate post on
BOTH sides at the top-of-book price with queue_ahead = best-level displayed size; timeout
60s (unfilled = free cancel); conditioner x = s_taker × Binance netflow[t−1] (causal,
cross-venue, <1s skew bound); ADV markout mid[j]→mid[j+H] and FULL P&L limit→mid[j+H]
measured POST-FILL; 200-shift circular null (decile edges recomputed per shift); collector
gaps era-split, never forward-filled across.

### $/hr FIRST (Greg's scoreboard; $5k clips, 10s posting grid per side, hold H=60s, gross of fees)

| cell | usable h | fills/hr | base $/hr | save skip-dec10 | 50-shift floor | z | verdict |
|---|---|---|---|---|---|---|---|
| **sol** | 40.8 | 511 | +45.7 | **+2.3** | −9.0 ± 9.5 | +1.2 | SUB-NOISE |
| doge | 40.8 | 377 | −40.8 | +9.7 | +3.8 ± 6.3 | +0.9 | sub-noise |
| xrp | 29.2 | 541 | +57.2 | −0.8 | −6.6 ± 8.1 | +0.7 | null |
| btc | 40.8 | 656 | −30.4 | +12.6 | +3.4 ± 4.0 | +2.3 | degenerate cell* |

(*) btc is the tickless cell (spread ≈ 0.002bp): the posting game itself bleeds −30 $/hr
gross there and the "save" is mostly "do less of a losing thing"; not a real-spread result.
Skipping the top TWO deciles: sol −6.9 $/hr (worse — foregone spread capture exceeds
avoided toxicity), doge +56.0 vs floor +35.0±9.6 (z +2.2, same do-less-of-a-losing-thing
shape as btc: doge's base is negative). Fee reality: at cb_real (8bp maker/leg) the whole
second-scale posting game is fee-dead on every cell regardless of toxicity skipping (the
+0.09bp/fill sol gross edge vs an 8bp fee is the S60 fee wall, reproduced — the "net16"
columns in the JSON are that wall, not signal).

### The per-fill decile map under honest fills (kill condition #1 check)

dec10−dec1 maker ADV markout (bp), honest fill moments, vs the taker-print proxy:

| cell | H=10s queue (z) | proxy (S61 prior) | H=60s (z) | H=300s (z) | fill-rate dec1→dec10 | ttf dec1→dec10 |
|---|---|---|---|---|---|---|
| sol | **−0.146 (−2.0)** | −0.19 (−2.2) | −0.16 (−0.9) | −0.26 (−0.6) | 79.4%→83.9% | 11s→9s |
| doge | −0.103 (−1.3) | −0.30 (−3.2) | −0.18 (−0.8) | −0.37 (−0.7) | 59.1%→68.4% | 17s→13s |
| btc | −0.062 (−1.6) | −0.20 (−6.6) | −0.11 (−0.6) | −0.39 (−0.7) | 91.8%→96.3% | 6s→5s |
| xrp | +0.066 (+1.4) | −0.04 (−0.5) | +0.02 (+0.2) | −0.58 (−1.2) | 80.6%→84.9% | 13s→10s |

DATA: (1) the separation SHRINKS 25–70% under honest fills and keeps |z|≥2 only on sol at
H=10s; (2) the fill-probability confound the prior run flagged is REAL and now measured —
toxic-decile posts fill more (+4.5 to +9.3pp) and faster; part of the proxy's markout
separation was fill-timing selection; (3) signs stay consistent with the proxy on
sol/doge/btc (same direction, smaller), xrp stays the null cell.

### JOB B VERDICT

Kill condition #2 FIRES: the $/hr save is sub-noise on the real-spread cells. Kill
condition #1 PARTIALLY fires: the mark survives honest fills only on sol at the 10s
horizon, marginally (−0.15bp, z −2.0), and dies at longer horizons. **No quoting overlay
is earned.** The prior-second Binance net flow remains real per-fill toxicity INFORMATION
(sign-consistent across proxy and queue reads on 3/4 cells, vol-robust in the proxy tier)
but it does not carry money at the queue level on these tapes.

SANDBOX LEDGER SPEC (descriptor tier, spec only — no wiring): add `bn_nf_pre` (prior-second
same-coin Binance net flow, signed by fill side) as a FREE descriptor column on sol and
doge sandbox fill rows. Cost: one 1s cross-venue join at ledger-write time. Consumers:
none (descriptor only). Promotion bar: it must show a per-fill markout split on the
FORWARD sandbox record (the machine's own fills, not per-second posts) before any quote
width/size consumption is even proposed. xrp: no column (double-null). btc: no column
(degenerate economics).

DEFLATIONARY READS (visible): the queue rule is price-blind (volume anywhere fills the
level — the S61 build (a) convention; price-eligibility would push fills LATER and likely
weaken the 10s mark further — the named next increment of the fill model); posting at
EVERY second creates overlapping forward paths (handled by the shift null, which preserves
that structure); 41h tapes — the H=300 shift-null variance swamps everything at that horizon.

---

## JOB C — the BIG LOSSES vs the whole dipole family (Greg, mid-session)

Script: `s61f_jobC_bigloss.py` → `s61f_jobC_results.json`. Population: registry-theta legs
of the promoted mid-band machine from the S60 dumps, per cell, both tapes. Classes:
DEATH (gross ≤ −0.6θ), RECOVERY (went ≥0.3θ underwater, finished > −0.2θ), WINNER
(gross > 0). Counts (bins tape): sol 237/210/333, doge 172/139/246, xrp 255/214/362,
btc 177/115/236 — well-powered; books cells are n=22–56 (stated, underpowered).
Priors respected and NOT re-derived: armed-before (SOL-only, failed as stop), naked
depth-stops/flips (killed both tapes), DOGE cascflip (wired), winners-invisible law,
kill ledger (graded, never gated; no divergence entry gates). New angles only:
(a) cross-venue/cross-coin flow at the leg, (b) D6 coupling INSIDE the leg,
(c) the stack, graded in $/hr. All reads label-permutation-nulled (2000 perms);
mitigation vs a 50-shift circular floor of the cross tape.

### (a) Was the other tape's flow already leaning against the death legs?

Oppose-ratio x = −side·(B−S)/(B+S) on the CROSS channel (bins legs: BTC Binance flow for
alts, ETH for btc; books legs: same-coin Binance = true cross-venue), windows PRE
[−300,0), E60, E300 after entry. The decisive contrast is DEATH vs RECOVERY (a read that
only separates deaths from winners is depth restated):

| cell (bins) | PRE D−R (z) | E60 D−R (z) | E300 D−R (z) | E300 D−W (z) |
|---|---|---|---|---|
| sol | +0.054 (+2.0) | +0.046 (+1.3) | +0.015 (+0.6) | +0.159 (**+6.7**) |
| doge | +0.034 (+1.0) | −0.019 (−0.5) | +0.014 (+0.5) | +0.174 (**+6.6**) |
| xrp | −0.009 (−0.4) | +0.013 (+0.4) | +0.049 (+1.9) | +0.161 (**+6.8**) |
| btc | +0.057 (+2.0) | −0.019 (−0.5) | −0.002 (−0.1) | +0.117 (**+5.0**) |

DATA: the cross channel separates troubled legs from WINNERS loudly (z +5..+7) but
CANNOT tell a DEATH from a RECOVERY (all |z| ≤ 2.0; and ~128 feature×cell×contrast tests
were run this battery, so isolated z≈2 prints are within multiple-comparison expectation).
The INCREMENT test (cross flow within terciles of the leg's OWN oppose-flow) is null
everywhere (z −0.8..+1.9, sign-inconsistent across strata and cells). Books cells
(true cross-venue, n tiny): sign-INCONSISTENT (sol PRE −1.3; xrp E300 −2.4 i.e. inverted;
btc D-R unreadable n=8/2) — no consistent cross-venue read, honestly underpowered.

### (b) D6 inside the leg — does the death leg's early flow-price coupling differ?

Per leg, first 300s: corr(nf,ret) lag0, corr(nf,ret+1s), sign-flow/ret corr, own tape.
D−R: |z| ≤ 1.7 on every cell (16 reads). NULL — a dying leg's own microstructure coupling
in the first minutes underwater is indistinguishable from a dip that will recover.

### (c) Lead time exists; discrimination does not — and the stack grades negative

Lead-time accounting: at t_e+300s, deaths sit only −12..−22bp underwater with
**−52..−77bp still to come** (e.g. sol bins: depth −16.1bp, remaining −68.6bp). The money
IS still on the table at read time — the missing piece is purely the D-vs-R discriminator.
The stacked read (own-oppose tercile × cross-oppose tercile) does grade death RATE
monotonically (sol: 15% in the calm corner → 47% in the double-hot corner) but that
gradient is the leg's own state restated; the graded mitigation (flatten at +300s when
double-hot, 10bp taker penalty), in Greg's units:

| cell (bins) | fires | mitigation $/hr @$5k | 50-shift floor | z |
|---|---|---|---|---|
| sol | 111 | −0.92 | −1.06 ± 0.37 | +0.4 |
| doge | 70 | −1.08 | −0.49 ± 0.28 | **−2.1** |
| xrp | 105 | −0.40 | −0.60 ± 0.20 | +1.0 |
| btc | 76 | −0.25 | −0.30 ± 0.21 | +0.3 |

**Negative $/hr on every cell, at or below the shuffle floor.** The double-hot corner
still contains ~53–60% non-deaths whose recoveries the flatten forfeits — the same
wealth-transfer arithmetic that killed every stop family.

### JOB C VERDICT

**Nothing new survives.** Across the whole dipole family — D4 own-flow states (own300,
in-dump dive/slmax reads), D5-flavor early-leg exhaustion via flow ratios, D6 cross-venue
and cross-coin flow (the Job-1 survivor channel, tested per-leg for the first time),
D6 lag/coupling structure inside the leg, D7-style oppose ratios, and the stack — every
read that fires is a restatement of "this leg is underwater with flow against it," which
recoveries share. The program's fifth independent demonstration that **death vs dip is not
carried by any causal flow/depth read at actionable lead time**. The dipole family's
answer to the big losers therefore REMAINS: the per-cell corrector diagonal already wired
(doge cascflip — the one flow-conditioned flip that earned; btc plainstop rider) plus the
S35 fingerprint tier for false-confirm recognition at entry. That is a full deliverable,
not a failure (nulls are deliverables).

Watch item (explicitly NOT a claim): PRE-ENTRY cross-major oppose prints z≈+2.0 (D−R) on
sol and btc bins — within multiple-comparison expectation here, but it is a pre-entry
feature, so if the S35 fingerprint tier gets built, `cross_major_nf_pre300` is a free
candidate column for that encoder (cost: one join; grading: the fingerprint tier's own
harness).

---

## Standing-constraint compliance

- Kraken untouched; Coinbase books + Binance instrument only. MPLBACKEND=Agg (no plots drawn).
- Circular-shift/permutation null on every read; decile edges and stack thresholds
  recomputed under each shift; label-permutation for class contrasts.
- Per-cell / per-pair everywhere; no pooled fits; no gates proposed — descriptor/grade tier only.
- $/hr leads every economic claim (Greg's S61 standing rule); per-event bp kept as diagnostics.
- Research only: no repo file touched; all scripts + JSONs in this scratchpad.

## Artifacts (this scratchpad)

- `s61f_jobA_volstate.py` → `s61f_jobA_results.json`, `s61f_jobA.log`
- `s61f_jobA_gauss_excess.py` → `s61f_jobA_gauss.json`, `s61f_jobA_gauss.log`
- `s61f_cbq_cache.py` → `cbq_{sol,doge,xrp,btc}.npz` (per-second best-level sizes + spread)
- `s61f_jobB_queue_toxicity.py` → `s61f_jobB_results.json`, `s61f_jobB.log` (selftest vs
  `odcore.swing_maker._queue_fill_index`: PASS)
- `s61f_jobC_bigloss.py` → `s61f_jobC_results.json`, `s61f_jobC.log`
