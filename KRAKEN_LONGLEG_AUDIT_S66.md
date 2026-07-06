# S66 — LONG-LEG / CAPACITY AUDIT (did we overlook long-leg or high-cap cells?) — 2026-07-06

Extends `S66_CAPACITY_FINDINGS.md` Finding 1 (winners unfillable / losers fill in full = adverse selection in $).
Mandate (Greg): with the capacity model in hand, hunt for cells we passed over — majors with LONGER legs (more
fillable), or ANY coin/config more profitable **capacity-capped**. All runs through the LIVE path
(`run_kraken_cell` / `run_stream` / `kraken_flips`, `odcore/platform.py`) + `odcore/capacity.py`
(`caps_for_legs`, `window=None, price_eligible=True` = deployed whole-hold model, `_s66_capacity_demo_kraken.py:50`).
Fill grade is the **honest capacity cap** (never front-of-line). Scripts:
`scratchpad/longleg_majors.py`, `scratchpad/alt_scan.py` (Kraken 30d tape `/tmp/ktape`).

## BOTTOM LINE (measured)
**No overlooked long-leg or alt cell survives capacity-capping. Every major and every eligible alt is NEGATIVE
$/hr at every size and every hold/swing filter. "Bigger/longer legs fill better for winners" is FALSIFIED — big
swings AMPLIFY the adverse selection, they don't cure it.** The deployed fine flow-lean cell has no fillable
winner edge on any Kraken cell we can measure; this is the capacity-side confirmation that the S65 front-of-line
$/hr was fiction in **sign**, not just magnitude.

---

## 1. Majors — long-hold / big-swing capacity structure (MEASURED, deployed cfg, $5k/leg)
`longleg_majors.py` §1–3. Whole-hold price-eligible caps.

| coin | n | medHold | p90Hold | medSw | winFill$ | losFill$ | cap $/hr |
|---|---|---|---|---|---|---|---|
| eth | 8674 | 155s | 512s | 6.7 | **15** | 5,433 | **−13.09** |
| btc | 7670 | 151s | 500s | 4.6 | **128** | 17,621 | **−6.97** |
| sol | 10577 | 156s | 554s | 8.7 | 104 | 8,067 | −30.25 |
| doge | 4242 | 469s | 967s | 12.7 | 2 | 1,653 | −12.08 |
| xrp | 9007 | 195s | 610s | 8.1 | 103 | 9,249 | −22.73 |

**Trade ONLY long-hold / big-swing legs (capped $/hr @ $5k, same wall-clock denominator):**

| coin | all | hold>p75 | hold>p90 | sw≥20 | sw≥50 | sw≥20 & hold>p75 |
|---|---|---|---|---|---|---|
| eth | −13.09 | −3.53 | **−1.52** | −4.10 | −1.33 | −2.22 |
| btc | −6.97 | −1.85 | **−1.50** | −1.72 | −1.04 | −1.36 |
| sol | −30.25 | −6.69 | −1.88 | −15.12 | −2.66 | −3.74 |
| doge | −12.08 | −2.16 | −0.90 | −8.17 | −3.06 | −1.50 |
| xrp | −22.73 | −4.65 | −1.02 | −10.37 | −1.36 | −2.50 |

Filtering to the longest/biggest legs pulls $/hr **toward** zero (loser volume is proportional to wall-clock; fewer
legs = less loss booked) but **never crosses it**. BTC is the least-bad (deepest flow → highest winner cap), best
subset ≈ −1.0/hr — closest to break-even but still negative.

## 2. ⭐ Big swings FALSIFY "winners fill better" (MEASURED — the load-bearing kill)
`longleg_majors.py` §3, winner vs loser median cap **within swing buckets**:

| coin | bucket | winCap$ | losCap$ | loser/winner |
|---|---|---|---|---|
| eth | sw<20 | 16 | 4,534 | 289× |
| eth | 20–50 | 10 | 48,424 | 4,923× |
| eth | **sw≥50** | **25** | **206,539** | **8,322×** |
| btc | sw≥50 | 0 | 228,008 | ∞ |
| sol | sw≥50 | 84 | 66,068 | 789× |
| xrp | sw≥50 | 194 | 96,243 | 496× |

The winner cap stays ~$0–200 **regardless of swing size**, while the loser cap explodes with swing size (a big-swing
loser is a knife you catch in full). Adverse selection is **worse** in the big-swing tail, not better. This directly
refutes S66 Finding-doc candidate #2 ("bigger swings may fill better"). Mechanism is structural (price_eligible
correctly zeroes a winner's flow the moment price leaves the limit; `capacity.py:55-58`), matches S45/S52/S56.

## 3. Config lever — coarser REV (fewer/longer/bigger legs) does NOT rescue (MEASURED)
`longleg_majors.py` §4, base detect, fwd + reversed control, capped @ $5k:

| coin | rev | medHold | winCap$ | losCap$ | **fwd $/hr** | **rev $/hr** |
|---|---|---|---|---|---|---|
| eth | 0.10 | 151 | 17 | 8,994 | −17.32 | −19.25 |
| eth | 0.50 | 594 | 736 | 35,812 | −11.81 | **−7.63** |
| btc | 0.10 | 151 | 208 | 38,272 | −8.31 | −13.34 |
| btc | 0.50 | 604 | 4,951 | 144,231 | **−4.53** | −5.74 |
| sol | 0.50 | 589 | 1,086 | 28,369 | −18.29 | **−13.06** |
| xrp | 0.50 | 598 | 917 | 25,377 | −14.05 | −10.59 |

Coarsening REV raises the absolute winner cap (eth $17→$736; btc $208→$4,951, approaching $5k) and nudges capped
$/hr toward zero, but (a) **never crosses zero**, and (b) **destroys the direction premium** — the REVERSED control
is ≈ or **better** than forward at coarse REV (eth/sol reversed beats forward). So the S65 per-coin REV lever, which
was net-positive front-of-line, is **not robust to capacity**: capacity-capped, forward and reversed are both
losing and indistinguishable. Coarsening buys longer legs but not a fillable *winner* edge.

## 4. Size-to-winner-capacity is FALSIFIED (MEASURED — no size flips positive)
Deployed cfg, capped $/hr across small desired sizes (winner-cap ≈ $50–128 median, so shrinking should recover the
raw edge if the winner distribution allowed it):

| coin | cap@$50 | cap@$100 | cap@$500 | uncap@$50 (fiction) |
|---|---|---|---|---|
| eth | −0.102 | −0.217 | −1.237 | **+0.084** |
| btc | −0.030 | −0.070 | −0.485 | **+0.079** |
| doge | −0.143 | −0.295 | −1.482 | **+0.008** |

The uncapped (fill-everything) edge is positive; the moment fill is capacity-bounded it is negative **even at
$50/leg**. Too much winner-cap mass sits below $50, so no size recovers it — adverse selection is scale-invariant
down to the floor. S66 candidate #1 ("size to winner capacity") does not produce a positive cell.

## 5. Overlooked coins — eligible Kraken alts (MEASURED, `alt_scan.py`, coarse rev=0.30 fwd)

| coin | cov% | n | medHold | medSw | UNCAP@$2k | CAP@$500 | CAP@$2k | winFill$ | losFill$ |
|---|---|---|---|---|---|---|---|---|---|
| HYPE | 7 | 5224 | 417 | 22 | −0.71 | −2.91 | −12.63 | 127 | 17,522 |
| APE | 0 | 1102 | 603 | 32 | **+1.95** | −0.64 | −1.43 | **0** | 153 |
| XDC | 1 | 2187 | 582 | 11 | −2.70 | −0.93 | −2.70 | 0 | 349 |
| GWEI | 2 | 2960 | 514 | 61 | −0.28 | −5.17 | −17.13 | 5 | 937 |
| SHX | 1 | 2344 | 516 | 30 | −14.79 | −3.39 | −6.75 | 22 | 310 |
| AIOZ | 0 | 235 | 654 | 52 | +0.03 | −0.22 | −0.33 | 0 | 52 |
| SYN | 3 | 3259 | 466 | 106 | −10.74 | −10.54 | −43.48 | 67 | 3,413 |
| NIGHT | 1 | 2956 | 499 | 24 | −0.48 | −1.76 | −5.24 | 0 | 560 |

**No alt is better; most are worse.** Two adversarial artifacts, both fatal:
- **Long legs on alts are DEAD-TIME artifacts:** coverage is 0–7% (93–100% of 1-second bins have *no trade*). The
  400–650s "holds" are the coin not trading, not a fillable long position. Exactly the eligibility artifact the
  mandate warned to flag.
- **No raw edge to cap:** most alts are negative even UNCAPPED (fiction). The only tiny-positive uncapped cells
  (APE +1.95, AIOZ +0.03) have **winFill = $0** — a resting maker there simply never fills on the winning side.
  (These match the S64 note that SHX/AIOZ only pass at coarse W2400; here even that posture is unfillable.)

The 33-pair `data/kraken-smallcap-tape` branch is thinner still (usd24 ≈ $8k–90k, ~200–900 trades/day per
`/tmp/eligible_liquidity.json`) — categorically below anything with fillable winner capacity; not worth materializing.

---

## Adversarial caveats (what could move this)
- **Fill model is a TAPE proxy**, not the book. `capacity.py` bounds fill by opposing taker $ through a fixed limit
  (whole-hold, price-eligible). The definitive grade needs the ~30h Kraken **book** + the executor's own open-fill
  accounting (S66 Finding-doc caveat). What is **robust** and reproduced here across all cells is the *direction*:
  winners unfillable, losers fill, capacity-capped ≪ front-of-line — the same sign as S45/S52/S56 on three venues.
- **Denominator convention:** filtered-subset $/hr uses the full wall-clock hours (flat between traded legs) — the
  project $/hr scoreboard. It does not credit capital freed for other cells; that is an allocator question, not a
  per-cell rescue.
- **Not a kill of the stack** — it says the deployable size and the winner-fill problem are unsolved on the fine
  flow-lean cell for every Kraken cell measured. The winner-side path remains the S35 encoder fingerprint
  (match-winner − match-loss), not a longer/bigger leg.

## Verdict for the deploy map
- **Long-leg capacity we can use: none.** BTC is the only cell within ~$1/hr of break-even (deepest flow → highest
  winner cap at coarse REV); it is the sole "long legs almost fill" candidate, still negative under this model — the
  first cell to re-grade when the multi-day book lands.
- **Coarser REV:** helps magnitude, not sign, and voids the direction premium — do not adopt as a capacity fix.
- **Overlooked coins:** none. Eligible-alt "long legs" are dead-time; capped $/hr strictly worse than majors.
