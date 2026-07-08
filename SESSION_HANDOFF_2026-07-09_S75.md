# SESSION HANDOFF — S75 (2026-07-08/09) — SOL is a DIRECTION/SPREAD-CAPTURE wall; the book EARLY-SIGNAL is the real edge → BTC+ETH next

READ FIRST: `STRATEGY_INVENTORY.md` OPERATING CONTRACT + LIVE. Then this. Then `KICKOFF_2026-07-09_S75.md`
(the shape-gate spec, still valid for the METHOD) + `BTC_SIGNAL_SESSION_2026-07-08.md` (Greg's BTC paper —
the S76 plan). Branch: `claude/curve-shape-gate-s75-06m1vf` (== the S74 shape tip + all S75 work). Books:
`git show origin/data/<coin>-kraken-book:<coin>_kraken_book.jsonl.gz | gunzip > /tmp/kbook/<coin>_book.jsonl`.

## What S75 did — built the whole-curve shape gate on SOL, hit the direction wall, then found the real edge

All work in `research/shape_s71/sol_gate_run.py` (one file, many `mode` args) + `research/shape_s71/early_signal.py`
(Greg drop-in) + `research/shape_s71/early_signal_kraken.py`. Live-code only: every DECISION runs through
`run_kraken_cell`. Added an opt-in external `entry_gate` socket to `odcore/platform.py::run_stream`/`run_kraken_cell`
(default None = bit-identical) so a gate can be injected live.

### 1. The curve-shape ENTRY gate — built, every variant lands at ~62% (the wall)
Match each forming leg's RAW pre-fire curve (birth→onset, ignition-anchored, leakage-free, **NO normalize/average/
smooth** — Greg: the raw curve IS the edge) to the 4 per-cell archetypes (the sampled arcs `leg_imbalance_arcs_sol.npz`
+ their `best_form` equations), fire winner-shape / skip loser-shape, $5k flat.
- `arc` / `eq` (each signifier alone, raw, wiggle 0.15): **59.6% win / $6.68** vs ungated **61.7% / $11.26** — over-skips.
- `eqpeak` (equation primary + peak decider `.123/.146/.306/.374`): **49.0% / $2.95** — anti-selective.
- ⛔ MY ERROR (Greg caught it): I added [0,1] shape-normalization unasked → fired 698/699 legs (everything looks like
  a rising ramp once stretched). Reverted to raw. **Rule reaffirmed: do NOT normalize/average/smooth the curves.**

### 2. WHY nothing cracks 62% — win/lose IS DIRECTION (the load-bearing finding, S62 reproduced)
- **`flip` test:** reverse the side of SOL's losers (opposite trade over same window ≈ −gross): **long-lose 82%,
  short-lose 87% become winners.** $/hr ungated **11.26** → reverse-long-losers **29.62** → reverse-all-losers
  **41.88** (HINDSIGHT ceiling). The losers ARE winners entered backwards.
- ⇒ a winner and its "loser" twin have the **identical entry** (same shape, peak, dipole) → **no entry feature can
  separate them** → ~62% is the detector's direction hit-rate, a HARD CEILING on entry-side filtering. Confirmed
  across shape/peak/eqpeak/dipole-direction/dipole-strength — all ~62%.
- **`buckets`:** pre-fire peak means separate (SW .123 / SL .146 / LL .306 / LW .374) but per-trade **bleed ~50%**
  (SHORT: 46% of losers in the winner IQR / 51% vice-versa; LONG: 50%/45%). Peak ranks the 4 cells but can't
  classify a single trade.
- **`smallloser`:** small losers do NOT isolate — only 33% sit in the bottom-30% peak, and that region is 26%
  BIG-WINNERS → skipping it loses more big winners (53) than small losers (39). No entry descriptor finds them.

### 3. Direction is un-callable at entry AND mid-trade on SOL
- **`dipole` (causal divergence at the pivot):** all `expect` classes ~61% win (reversal 61.4 / continue 61.3 / …).
  As a wrong-direction detector: 39% precision (≈ base loser rate = noise). Flipping the "reversal" calls HURTS
  ($/hr 11.26→3.32). **Book is also flat on SOL** (see §4). Direction not predictable at entry on SOL.
- **`flipexit` (mid-trade flip when the flow-lean reverses against us):** a WASH — rescues 337 losers but BREAKS
  290 winners (a winner dipping and a loser turning are TWINS at the flow reversal = the "winners invisible" law).
  Mid-price no-flip ride = **−5.2 $/hr / 39% win** ⇒ **the deployed +11.26 edge is SPREAD CAPTURE, not direction.**
  With any taker cost to reverse, catastrophic (−33/hr).
- **`flipdist` (flip when price moves X bps adverse, Greg's "flip at 15"):** SOL barely MOVES — only **34/1522** legs
  reach 15 bps adverse, **ZERO** reach 30. Not "too soon" — there's almost no move. SOL is a small-band (worst loss
  ~−23 bps), mean-reverting, spread-capture coin. No directional excursion to flip into.
- **`losscap` (deep-bail sweep) — ⚠ BUGGY:** every bail depth −20..−200 returned identical (1855 legs / 8% / −53
  $/hr) → the price_stop isn't being applied right via `dataclasses.replace(cfg, bail=...)`. **Do not trust those
  numbers; fix before using.** (Likely an x_bp sign/units issue for the SOL cell.)

### ⭐ SOL VERDICT (Greg: "we're moving on"): SOL is capped at ~62% / +11.26 $/hr on the entry+direction axis, and
that's near its ceiling. The edge is spread capture (already deployed). Direction is the win/lose axis but it's
unpredictable at entry, uncorrectable mid-trade, and the moves are too small to flip on distance. Not a missing
trick — SOL's structure. **Stop fighting SOL; go where direction is real (BTC/ETH).**

## ⭐⭐ THE REAL EDGE — the BOOK EARLY-SIGNAL (tonight's win; `early_signal.py` + `early_signal_kraken.py`)
Greg's drop-in `early_signal.py`: proximity-weighted top-K book depth imbalance → **MAGNITUDE** (entry filter) +
**SIGN** (direction, +1 long / −1 short); `fit_direction_sign()` fits the sign per venue×cell with hit-rate + weight.
**Fit on OUR Kraken books (100ms→1s grid, horizon 60s, min_conv 0.5) — confirms Greg's ranking:**

| coin | sign | hit@60s all | hit@60s strong (n) | weight |
|---|---|---|---|---|
| **BTC** | +1 | 0.668 | **0.714** (83,347) | **HIGH** ⭐ |
| ETH | +1 | 0.531 | 0.554 (50,019) | HIGH-ish |
| XRP | +1 | 0.521 | 0.564 (12,954) | LOW |
| SOL | +1 | 0.532 | 0.852 *(n=27 → noise)* | FLAT |
| DOGE | −1 | 0.504 | 0.493 | ZERO/flat |

**BTC book direction = 71.4% at 60s on strong leans (83k samples) — a real, tradeable directional edge, and the fix
for "entering backwards" that SOL never had.** SOL's book is flat (only 27 snaps even cross the strong-lean bar).

## Greg's BTC paper (`BTC_SIGNAL_SESSION_2026-07-08.md`) — the S76 plan
- Forward book signal LEADS price +1s (Coinbase 196h OOS). **BTC + ETH strong (ETH as strong as BTC); SOL flat.**
- Economics = fee-floor: dead at taker, positive at **0% maker** (Coinbase Liquidity Program = 0% maker all tiers,
  BTC-USD 10× AMV multiplier). Kraken Pro 0% maker at $10M/mo (our tier). US-eligible venues mapped.
- **Signal lives at ~60s** (not 15–30s). **Ride-to-reversal exit** (wide ~30 bps trailing stop, ~10 min holds) =
  first net-positive (+7.4 @0% maker, +5.4 @ taker) but fragile (n=100, one window).
- The threshold "both-agree" scalar gate reproduced the S75 negative (win% up, net not — over-skips fat winners) →
  **confirms the whole-curve shape-match is the right frame, not a scalar.**

## ⭐ NEXT (S76) — BTC + ETH TOGETHER (Greg)
1. **Point the whole-curve shape gate at BTC + ETH (Kraken), with FALLBACKS** (Greg: "try the shape with fallbacks").
   Reuse the S75 gate machinery (raw curve, per-cell arcs+equations — REBUILD the archetypes on BTC/ETH; SOL's were
   the wrong coin). Aim the exit at the ~60s horizon.
2. **STACK the book direction signal** (`early_signal` / `fit_direction_sign`, HIGH on BTC/ETH) — the book gives the
   DIRECTION on BTC/ETH that SOL never had (71% / 55%). This is the piece that breaks the 62% wall on these coins.
3. **Ride-to-reversal exit** (wide trailing stop, ~60s+ holds) per the paper.
4. **Validate multi-window** (the paper's numbers are one 8-day window; don't size on it).
- Firing stays LOCKED (Greg-only). The book direction is a per-cell weighted component; re-fit `direction_sign` per
  venue×cell (BTC/ETH +1 on Kraken confirmed tonight).

## Files (all committed on the branch)
`research/shape_s71/sol_gate_run.py` (modes: arc/eq/eqpeak/walk/peak/buckets/flip/dipole/strength/flipexit/
smallloser/losscap⚠/flipdist) · `early_signal.py` · `early_signal_kraken.py` · `odcore/platform.py` (opt-in
external `entry_gate`, bit-identical default) · `BTC_SIGNAL_SESSION_2026-07-08.md` (the paper).

## RULES (standing, reaffirmed tonight)
Firing LOCKED (Greg-only) · live-code-only (decision via `run_kraken_cell`) · **NEVER normalize/average/smooth the
curves** (the raw curve is the edge) · shape/RATIO only (no volume/price) · win/lose = DIRECTION (entry can't see it;
~62% is the ceiling) · the book gives direction on BTC/ETH, FLAT on SOL · doge on its own track.
