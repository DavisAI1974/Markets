# DIPOLE LANE REPORT — S61 (dipole specialist, research-only)

Session 61, 2026-07-04. Successor to the S60 dipole program (paper `docs/DIPOLE_PAPER_S60.md`,
dive chapter §3.5R). Charter: Job 1 = D6 cross-venue lead-lag map; Job 2 = lean-conditioned
maker markout; Job 2b (Greg, mid-session) = cross-coin coupling majors->alts (D6 + M1);
Job 3 = cross-coin dive propagation. Kraken parked; Coinbase + Binance-instrument only.
Nothing wired, nothing committed; all scripts/artifacts in this scratchpad.

House rules honored: circular-shift tautology null on every coupling claim; office named
for every read; per-cell, never pooled; nulls are deliverables; data / interpretation /
frame kept separate.

## EXECUTIVE SUMMARY (per-job verdicts)

- **Job 1 (Binance->Coinbase lead-lag): SYNCHRONY KILL.** Every channel, every 12h segment,
  every coin peaks at lag 0 (PP z +150..+355). Clock skew < 1s and points the wrong way for a
  flow-lead story. ONE small survivor: Binance NET flow -> Coinbase next-second return, +1s,
  13/13 segments, skew-controlled, magnitude ~0.3-0.5bp (t 13-30) = quote-skew tier, sub-fee.
- **Job 2 (lean-conditioned maker markout): KILL as a decile map** (sol underpowered same-sign;
  doge nominal but vol-double-sort kills it; xrp null; btc inverted-tickless). TWO deliverables:
  (a) a METHODOLOGICAL one — lean-vs-vol is inverted-U, so lean-conditioned fill reads REQUIRE
  a double-sort (linear residualization is a non-control); (b) the Job-1 survivor CONSUMED by
  this office SURVIVES: prior-second Binance net-flow marks per-fill adverse selection
  (dec10-dec1 maker markout -0.20bp btc z-6.6, -0.30 doge z-3.2, -0.19 sol z-2.2, robust across
  vol terciles at H=10s; xrp null). Fill-mark office, per cell, queue-model test owed.
- **Job 2b (cross-coin coupling majors->alts, Greg): D6 SYNCHRONY KILL** (6/6 pairs lag-0,
  100% of days, sign-inconsistent tails). **M1 discriminator UNREADABLE** (naive mi_frac ~1 but
  shift-control also ~1 = the INFO-024/049 estimator floor, caught by the control — no
  structured/self-pole verdict). The INFO-040 STRENGTH METER fires and shift-nulls cleanly on
  all 6 pairs (real meanMI 5-8x floor, slope r2 0.24-0.37): cross-coin MI is real and
  state-dependent, but structured-vs-generic (vol-clustering) is left OPEN. No flatten overlay
  earned; candidate = a per-cell regime conditioner (descriptor tier first).
- **Job 3 (cross-coin dive propagation): SIMULTANEITY KILL.** BTC and ETH dives co-occur with
  alt dives in the SAME second (x2.2-4.9, z +3..+10), bidirectional halo, no major lead,
  per-week lags scatter. A flatten overlay keyed on "major dived" tells an alt cell nothing its
  own dive doesn't say at the same second. Sub-second edge, if any, needs tick data (out of scope).

Net: four kills (all the ranked-A crypto uses that touched cross-venue/cross-coin timing turn
out lag-0 synchronous at 1s — a coherent, repeated finding, not four separate nulls), plus one
real cross-venue fill-toxicity signal (fill-mark office) and one real cross-coin coupling-strength
readout (regime-conditioner candidate), both sub-fee and descriptor-tier, both with a defined
queue/vol next test. Everything reproduces the program's standing "venues synchronous at 1s" law
on fresh, per-cell, shift-nulled tapes.

## Data actually used

- Coinbase books -> 1s grid cache (`s61_cache.py` -> `cb_*.npz`), with an explicit
  `have` mask (NO blind forward-fill across collector gaps). Real coverage per coin is
  ~40.8h, not the wall-clock span: sol 40.8h (one 58.4h gap), btc 40.8h (2 gaps, 11.7h +
  143.7h -> 3 eras), doge 40.8h (2 gaps), xrp 29.2h (continuous), eth 40.8h (2 gaps).
  Median spreads (bps): sol 1.36, doge 1.39, xrp 0.96, eth 0.063, btc 0.0016
  (eth/btc are tickless-degenerate for spread-frame economics, as in S60).
- Binance-spot 30d 1-sec bins -> `bn_*.npz`. These are TRADE bins: a missing second is a
  genuinely zero-trade second (flow valid everywhere, mid stale). Coverage of seconds with
  trades: btc 86%, sol 61%, xrp 51%, doge 39%.
- Cross-venue alignment on unix epoch seconds; the clock-skew control is Job 1's PP baseline.

---

## JOB 1 — D6 cross-venue lead-lag map (Binance -> Coinbase), VERDICT: SYNCHRONY KILL at 1s, with one small named survivor

Script `s61_job1_leadlag.py` (+ selftest: a delay-5 copy is recovered exactly through the
masked-FFT path). Per coin, per 12h segment (13 usable segments across 4 coins), channels
PP (Binance ret -> Coinbase ret), F1 (Binance per-sec flow imbalance -> CB ret), NF
(Binance per-sec signed NET taker volume -> CB ret), FS (Binance flow -> Binance's own ret,
the same-venue reference). Exact circular cross-correlation via FFT; null = the same circular
cc read at 300 random offsets (the exact circular-shift tautology null); lags -30..+30s.

DATA:
1. **Lag-0 dominance everywhere.** All 4 channels x all 13 segments peak at lag 0
   (PP cc0 0.42-0.76, z +150..+355). This is the paper's kill condition #1, and it
   reproduces S20's "venues synchronous at 1s" on fresh tapes, per coin, per day.
2. **Clock skew bounded < 1s.** The PP peak sits exactly at 0 on every segment; the PP
   +-1s side-mass is symmetric-to-CB-leading (on btc and xrp cc(-1) > cc(+1), i.e. the
   Coinbase tape is marginally EARLIER). So any flow-lead claim at +1s is not collector skew:
   skew would push the price-price baseline the same way, and it pushes the other way.
3. **The one strictly-future survivor: Binance NET flow -> Coinbase next-second return.**
   NF cc(+1) is positive in 13/13 segments (per-lag z +1.0..+25.5), while its cc(-1) is
   near zero — an asymmetric, genuinely predictive tail that the F1 ratio-flow and the PP
   price channel do NOT show consistently (F1's asymmetry is positive on sol/doge, NEGATIVE
   on btc 5/5 segments — day-consistent per cell but not portable across coins; per-cell law).
   The lead is 1-2s deep only; nothing consistent at 5-30s.
4. **Magnitude (the honest part):** E[CB ret(t+1) | NF top decile] - bottom decile =
   +0.45bp (sol), +0.32 (btc), +0.49 (doge), +0.35 (xrp), t-stats 13-30. That is ~2 orders
   below the 16bp cb_real round-trip and comparable to the 1s return sd itself (0.6-1.4bp).

INTERPRETATION: at 1s resolution the venues are one price process; the actionable
"Binance leads, condition the Coinbase machine" map DOES NOT EXIST at this resolution —
the kill is clean and is the deliverable. The residual NF(+1s) tail is real, day-consistent,
skew-controlled, and sub-fee: it is quote-skew tier information, not a signal.
(It rhymes with §3.5R's same-venue delayed-OFI price discovery: order flow anywhere is
absorbed into the Coinbase mid with a ~1-2s tail.)

DEFLATIONARY READS: sub-second structure is invisible on a 1s instrument (the S20 caveat
stands); Binance bins' sparse seconds attenuate cc levels (handled: zero-trade seconds are
real zeros for flow; validity-masked for returns); the F1-vs-NF discrepancy on btc says the
*ratio* lean and *net volume* are different objects at 1s — do not interchange them.

OFFICE + next test (if anyone wants the survivor): fill-mark office only, as a maker
quote-skew conditioner. The falsifiable next test was RUN this session — see Job 2
conjunction below (it passes). Wiring would eventually require a live Binance trade feed
aggregated at 1s next to the Coinbase quoting host; it must never enter as a decision gate.

---

## JOB 2 — lean-conditioned maker markout (Coinbase books), VERDICT: NO deployable decile map (kill), plus two named deliverables

Script `s61_job2_markout.py`. Every second with taker volume = a passive-fill proxy event
(taker buy fills a resting ask -> maker short; vice versa). Maker markout = -side_taker *
mid move over H in {10,60,300}s; conditioning x = side_taker * lean_W[t-1] (strictly
pre-fill, W in {60,300}s); deciles of x; circular-shift null on the forward series under the
fixed event/decile structure (200 shifts); vol control = trailing 300s realized vol, both a
linear residualization and a tercile double-sort. Cells: sol/btc/doge/xrp Coinbase.

DATA (top-decile-minus-bottom-decile maker markout spread, bps):
- **sol**: adverse-direction sign on 6/6 (W,H) configs (e.g. W300/H300: dec1 +2.34 ->
  dec10 -3.23, spread -5.57bp) but z only -0.1..-1.1 — the shift-null variance at long H on
  a 41h tape swamps it. Sign-consistent, UNDERPOWERED, not a claim.
- **doge**: the only nominally significant cell: W300/H10 spread -0.66bp z=-3.8; W60/H60
  -1.03 z=-2.3; W300/H60 -2.06 z=-3.0. BUT the deciles are non-monotone, and the vol
  double-sort KILLS the strongest cell (within-tercile spreads -0.03/-0.22/+0.03 at H10).
- **btc**: weakly INVERTED (with-flow fills mark out BETTER for the maker; z ~ +2), tickless
  cell; treat as a momentum-vs-reversion per-cell quirk, not signal.
- **xrp**: null (|z| <= 1.7, sign-unstable).

The paper's kill condition fires, but with a twist worth recording:
- **The extreme-lean/thin-tape law reappears as an inverted-U vol confound.** Trailing rv
  by lean decile is humped: mid deciles 1.3-1.5bp/s, rail deciles 0.85-1.0 (doge). Extreme
  |lean| selects LOW-vol seconds (the dive chapter's thin-tape mechanics), so the lean-vol
  relation is NON-LINEAR: linear residualization changes nothing (resid spread == raw spread
  everywhere) while the tercile double-sort moves the verdict. METHODOLOGICAL DELIVERABLE:
  any lean-conditioned fill read must use a double-sort; linear vol residualization is a
  non-control here.
- **Fill-economics scaffold (tape-proxy level):** mean per-fill maker markout is small vs
  the half-spread on the real-spread cells: sol -0.08..-0.17bp and xrp -0.02..-0.06bp vs
  half-spreads 0.68/0.48bp; doge -0.43..-0.52 vs 0.70. CAVEAT: this is the taker-print
  proxy with NO queue model — real passive fills cluster at adverse moments, so these are
  optimistic bounds. The honest fill model (`maker_book._first_fill_index`) remains the owed
  piece (S54/S60 flag unchanged).

VERDICT: the SAME-VENUE trailing lean does not carry a robust per-fill adverse-selection
map on these tapes (kill; nulls reported per cell).

### Job 2 conjunction probe — the Job-1 survivor consumed by the Job-2 office: SURVIVES

Script `s61_job2_conjunction.py`: identical machinery, but the conditioner is the
CROSS-VENUE prior-second Binance net flow, x = side_taker * bn_netflow[t-1].

DATA (H=10s, dec10-dec1 maker markout spread):
- **btc -0.20bp z=-6.6**, vol-tercile spreads -0.17/-0.16/-0.10 (all negative — robust);
- **doge -0.30bp z=-3.2**, terciles -0.22/-0.33/-0.32 (robust);
- **sol -0.19bp z=-2.2**, terciles -0.18/-0.24/-0.24 (robust);
- xrp -0.04 z=-0.5 (null).
At H=60s the sign holds (btc z-2.1, others weaker); at H=300s it dissolves.

INTERPRETATION: fills aligned with the last second's Binance net flow are systematically
more adverse on 3/4 Coinbase cells, beyond volatility, beyond the shift null, at the 10s
horizon — exactly where the same-venue lean failed. The cross-venue net-flow tail (Job 1)
is not tradeable as a signal but IS per-fill toxicity information.

DEFLATIONARY: magnitudes are 0.2-0.3bp (vs sol half-spread 0.68bp, ~30-45% of the maker's
capture; on tickless btc the spread-frame economics don't apply); the event set is the
taker-print proxy (no queue position); xrp is a clean null cell.

OFFICE: fill-mark (quote width/size/skew conditioner), per cell (sol/doge/btc yes, xrp no).
FALSIFIABLE NEXT TEST: replay with the honest queue model (`maker_book._first_fill_index`)
— condition SIMULATED resting-quote fills (not taker prints) on bn_netflow[t-1] and require
the markout separation to survive queue/adverse-selection accounting; then a live shadow
column on the sandbox ledger (bn_nf_pre as a free descriptor) before any quoting change.
WIRING EVENTUALLY: live 1s Binance trade aggregation on the quoting host; consumed only by
quote width/size, never entry/exit decisions.

---

## JOB 3 — cross-coin dive propagation (BTC -> alts, Binance bins), VERDICT: SIMULTANEITY KILL

(Charter Job-3 pick: dive propagation over the stablecoin-basis spec — the basis monitor
needs Kraken tape, which is parked; propagation was fully runnable on in-hand data and it
then folded directly into Greg's mid-session Job 2b.)

Script `s61_job3_propagation.py`. Chapter variant (a) pure dive per coin (aligned =
lean_W * sign(drift_W) <= -d), W300/d0.30 (mid config, ~81 BTC onsets/day) and W600/d0.40;
single collector, so the paper's #1 cross-venue deflationary read (collector skew) is
structurally absent. Two reads vs circular-shift nulls: D6 state cross-correlation
(lags +-600s, per-week consistency) and onset-triggered rate in lag bins.

DATA (W300/d0.30):
- Onset-triggered alt-dive rate at |lag|<=1s of a BTC dive onset: **x4.9 (z+9.7) sol,
  x4.0 (z+9.3) doge, x2.8 (z+5.2) xrp** — a huge SAME-SECOND spike.
- The +-60s halo is small and BIDIRECTIONAL (sol +2..60s x1.42 z+5.0 vs -60..-2s x1.30
  z+3.4; xrp actually leads btc: x1.36 backward vs x1.18 forward). No consistent major lead.
- State cross-corr peaks: +2s (sol), -7s (doge), -9s (xrp), cc ~0.023-0.025, z +4..+5 —
  essentially lag-0 co-occurrence; per-week peak lags scatter wildly (+10/+23/+2/-496 ...),
  i.e. day-to-day inconsistency in the LAG, stability only in the co-occurrence itself.
- Coarse config (W600/d0.40): nothing significant (state z <= 1.3).
- ETH as the major (added under Job 2b's charter, same machinery): identical picture —
  state cc peaks at 0/+2/-2s (z +5..+11), same-second onset bin x4.6 (z+8.4) sol,
  x3.6 (z+7.6) doge, x2.2 (z+3.0) xrp, and the +-60s halo is again bidirectional with the
  BACKWARD bin slightly >= forward (eth->xrp -60..-2s x1.50 vs +2..60s x1.43). Neither
  major carries a usable lead.

INTERPRETATION: dives are a market-wide co-movement STATE — a common shock hits all coins
within the same second at this resolution. There is no exploitable BTC-first ordering: a
flatten overlay keyed on "BTC dived" tells an alt cell nothing its own dive does not say
simultaneously. Both kill conditions fired (simultaneity + lag inconsistency). Clean kill,
deliverable. (Any real propagation edge, if it exists, lives sub-second — tick data, out of
scope on these tapes.)

---

## JOB 2b (Greg, mid-session) — cross-coin coupling majors->alts: D6 SYNCHRONY KILL; M1 null-read FLOOR-DEGENERATE but the STRENGTH METER fires and survives the shift null

Scripts `s61_job2b_crosscoin.py` (+ eth-pairs runner, `s61_m1_strength.log`). Six pairs
(btc/eth x sol/doge/xrp), never pooled, on the Binance 30d 1s bins (single collector — the
cross-collector-skew deflationary read is structurally absent). ETHUSDT bins landed
mid-session and were folded in.

### Layer 1 — D6 lead-lag per pair per day (~29-30 days each), circular-shift null

DATA (per-day peak lag, channels RR = major ret -> alt ret, LL = lean60 -> lean60,
FR = major netflow -> alt ret):
- **peak at lag 0 on 100% of days** for every channel of every pair (one LL day at 97%).
  RR cc0 0.48-0.55 (med z +230..+320); LL cc0 0.22-0.27; FR cc0 0.18-0.23.
- Strictly-future asymmetry (+1..5s vs -1..-5s): SIGN-INCONSISTENT ACROSS PAIRS —
  btc-sol RR asym z -6.7 (sol marginally EARLIER than btc), btc-doge +2.0, btc-xrp -2.6,
  eth-sol +1.6; FR asym z NEGATIVE on all btc pairs (-3.5..-4.1): the alt's return leads
  the major's flow marginally more than the reverse. LL is perfectly symmetric (z+1 == z-1).
- Dive propagation for both majors (Job 3 + the ETH extension): same-second co-occurrence
  x2.2-4.9 (z +3..+10), bidirectional halo, no consistent major lead, per-week lags scatter.

VERDICT (D6): **kill condition #1 fires exactly as specified — lag-0 simultaneity at 1s
with no usable lead, uniform across all 6 pairs, 100% of days.** The majors do not lead the
alts at >=1s; if anything the small asymmetries point the other way on some pairs and are
sign-inconsistent (kill condition #3, day/pair inconsistency, also fires for any residual-
tail claim). The cross-coin relation at this resolution is ONE market-wide shock process.

### Layer 2 — M1 discriminator (does MI enter the null?)

DATA:
- Naive read: mi_frac 0.996-1.000 on every pair (returns channels) — but the **circular-
  shift control returns mi_frac 1.000 identically**, and sd(MI)/sd(H_a) = 0.10-0.14
  (netflow channels: 0.000-0.001, meanMI 0.000 — fully degenerate). This is the INFO-024/
  INFO-049 estimator-floor artifact reproduced on market data and CAUGHT BY THE CONTROL:
  windowed return-entropies inherit huge vol-clustering variance (units!), MI is scale-
  invariant and near-constant by comparison, so MI is trivially the lowest-variance
  direction whether or not any genuine pairing exists. **The MI-in-null read is UNREADABLE
  in this configuration — no structured-coupling claim, and no self-pole claim either.**
  (Methodological deliverable: on windowed market returns, always run the shifted-pair
  control before reading mi_frac; the naive read is always ~1.)
- The INFO-040 STRENGTH METER (MI locked to entropy, the biology signature MI ~ slope*H_a)
  is read

INTERPRETATION (kept separate): the strength-meter result says cross-coin coupling is real
and STATE-DEPENDENT — information sharing between coins scales with market activity/entropy.
DEFLATIONARY READ (visible): H_a on returns is ~log-vol, and correlation rising with
volatility is a known market phenomenon; the MI~H_a lock may be that phenomenon in the MI
lens (INFO-041's "generic" case), not law-like structured coupling. The discriminator that
would separate the two (null membership in a non-degenerate basis) is exactly the read the
floor blocks. VERDICT: genuine shift-nulled coupling-strength readout, structured-vs-generic
left OPEN — an honest partial, not a coupling-side claim.

Per-pair strength meter (MI ~ slope*H_a on 10s return windows; REAL vs 1/3-circular-shift):
  | pair    | REAL slope | REAL r2 | REAL meanMI | SHIFT slope | SHIFT r2 | SHIFT meanMI |
  |---------|-----------:|--------:|------------:|------------:|---------:|-------------:|
  | btc-sol |    +0.081  |  0.366  |    0.188    |   +0.0003   |  0.0001  |    0.026     |
  | btc-doge|    +0.059  |  0.297  |    0.129    |   -0.0000   |  0.000   |    0.022     |
  | btc-xrp |    +0.069  |  0.336  |    0.163    |   +0.0003   |  0.000   |    0.024     |
  | eth-sol |    +0.075  |  0.304  |    0.203    |   +0.0003   |  0.000   |    0.025     |
  | eth-doge|    +0.053  |  0.236  |    0.133    |   -0.0001   |  0.000   |    0.022     |
  | eth-xrp |    +0.060  |  0.268  |    0.162    |   +0.0005   |  0.000   |    0.024     |
  All 6: real meanMI 5-8x the shift KSG floor (~0.023), positive slope r2 0.24-0.37, shift
  r2 ~0. Consistent, per-pair, shift-nulled. (SOL couples hardest to both majors.) The
  uniformity itself argues "market-wide vol state" (the deflationary read) over pair-specific
  structured coupling.

OFFICES: no flatten overlay earned (D6 kill). The one candidate consumer of the M1 strength
meter is a REGIME CONDITIONER (per-cell): windowed cross-coin MI (or its cheap proxy,
rolling cross-coin corr) as a market-wide-state column on the sandbox ledger — descriptor
tier first, exactly like the dipole descriptors. FALSIFIABLE NEXT TEST: does per-cell entry
quality / corrector performance differ between high and low cross-coin-MI states beyond a
vol control? (Double-sort, per cell, shift-nulled — the Job 2 machinery ports.)

---

## Standing-constraint compliance

- Kraken untouched. Coinbase books + Binance instrument only.
- Kill-ledger compliance: no divergence entry gates, no winner-exit timing reads, no pooled
  fits (every table per cell/pair), no directional flow maps (the NF read enters only as
  fill-moment toxicity, never direction).
- Research only: all scripts + JSONs live in this scratchpad; repo tree untouched.

## Artifacts

- `s61_cache.py` (+ cb_*.npz / bn_*.npz caches, s61_cache_meta.json)
- `s61_job1_leadlag.py` -> s61_job1_results.json
- `s61_job2_markout.py` -> s61_job2_results.json
- `s61_job2_conjunction.py` -> s61_job2_conjunction_results.json
- `s61_job2b_crosscoin.py` -> s61_job2b_crosscoin_results.json (btc pairs) + s61_job2b_eth_results.json (eth pairs) + s61_job2b_eth.log
- `s61_m1_strength.py`-inline -> s61_m1_strength.json / .log (the INFO-040 strength meter, 6 pairs)
- `s61_job3_propagation.py` -> s61_job3_results.json (btc) + s61_job3_eth_results.json (eth major)
