# S74 WHOLE-LEG IMBALANCE SHAPES — findings (SOL / BTC / ETH / XRP)

CHARACTERIZATION only (arcs + turn signals + endpoint tables + per-cell equations). No gate, no AUC.
All legs come from the LIVE executor (`run_kraken_cell`), 4 majors, DOGE excluded. Shape/RATIO only —
no volume, no price. 4 cells kept DISTINCT (short/long by median leg DURATION, win/lose by net_bps>0);
per-cell averaging is used to draw the archetype picture (Greg-approved).

**Two channels, both signed to the trade's side, tracked whole-leg (birth→onset→close):**
- **TRADE imbalance** = rolling `(buy−sell)/(buy+sell)` (20s window).
- **BOOK imbalance** = rolling `(bidK−askK)/(bidK+askK)` at K=1/5/10.

Legs extended TURN-TO-TURN: valley/birth (`ignition_idx`, lookback ≤150s, bounded by prior close/book
start) → onset peak (t=0) → exhaustion at the actual `close_idx`. Normalized time per limb.
Script: `leg_imbalance.py`. Arcs saved to `leg_imbalance_arcs_{coin}.npz`; PNGs `leg_imbalance_{coin}.png`.

Run scope: SOL 699 legs/73.1h (base-win 62.5%), BTC 885/41.9h (67.5%), ETH 623/67.3h (55.7%),
XRP 635/73.1h (52.0%).

---

## 1. Does TRADE imbalance decide SHORT vs LONG? (Greg's hypothesis) — YES, in two senses

### (a) DIRECTION reading (SHORT=sell-side vs LONG=buy-side) — STRONG YES, trade only
Raw (unsigned) trade imbalance, buy-side vs sell-side legs:

| coin | trade valley (buy / sell) | trade PEAK (buy / sell) | gap@peak | book5 peak (buy/sell) gap |
|------|---------------------------|--------------------------|----------|----------------------------|
| SOL  | −0.852 / +0.941 | +0.338 / −0.153 | **+0.490** | +0.036/+0.013 (0.02) |
| BTC  | −0.765 / +0.870 | +0.385 / −0.185 | **+0.570** | −0.044/−0.066 (0.02) |
| ETH  | −0.834 / +0.924 | +0.305 / −0.168 | **+0.474** | −0.143/−0.198 (0.06) |
| XRP  | −0.838 / +0.885 | +0.447 / −0.273 | **+0.720** | −0.035/−0.074 (0.04) |

Trade-imbalance POLARITY *is* the trade direction: it starts maximally AGAINST the coming side at birth
(buy≈−0.8 / sell≈+0.9 — the hole is on the opposite side) and FLIPS to point WITH the side at onset
(buy≈+0.3..+0.45 / sell≈−0.17..−0.27). The sign of trade imbalance at onset is the buy/sell decider on all
4 coins. **BOOK imbalance does NOT decide direction** (buy-vs-sell gaps are ±0.02–0.06, sometimes reversed).

### (b) DURATION reading (short-dur vs long-dur cells) — PARTIAL YES, at the PEAK only
Signed-to-side trade imbalance, short-duration vs long-duration cells:

| coin | valley (short/long) | **PEAK (short/long)** | pre_mean (short/long) |
|------|---------------------|-----------------------|------------------------|
| SOL  | −0.905 / −0.895 (0.01) | **+0.131 / +0.346 (−0.215)** | −0.090 / −0.114 |
| BTC  | −0.799 / −0.853 (0.05) | **+0.195 / +0.341 (−0.146)** | −0.157 / −0.177 |
| ETH  | −0.883 / −0.887 (0.00) | **+0.129 / +0.326 (−0.197)** | −0.060 / −0.170 |
| XRP  | −0.867 / −0.864 (0.00) | **+0.245 / +0.445 (−0.200)** | −0.082 / −0.131 |

The **PEAK height separates duration** on all 4 coins: long-duration legs fire from a much higher trade-
imbalance peak (~+0.33–0.45) than short-duration legs (~+0.13–0.25). The **valley and the pre-fire mean do
NOT separate** (gaps ≈0). Reading: a bigger trade-flow surge at onset → a longer ride; the birth depth and
the average ascension level carry no duration information.

**Net:** trade imbalance is the decider Greg expected — cleanly for direction (sign flip birth→onset), and
for duration only through the onset PEAK HEIGHT (not valley, not mean). Book imbalance decides neither.

---

## 2. Endpoint imbalance tables — where the 4 cells DO / DON'T separate

### TRADE imbalance (signed to side), valley / peak / exhaustion
| coin | cell | valley | peak | exh(close) |
|------|------|--------|------|-----------|
| SOL | short-win  | −0.903 | +0.123 | +0.004 |
| SOL | short-lose | −0.908 | +0.146 | **−0.292** |
| SOL | long-win   | −0.889 | +0.374 | +0.085 |
| SOL | long-lose  | −0.902 | +0.306 | **−0.139** |
| BTC | short-win  | −0.793 | +0.257 | −0.024 |
| BTC | short-lose | −0.814 | +0.024 | **−0.342** |
| BTC | long-win   | −0.847 | +0.355 | −0.003 |
| BTC | long-lose  | −0.863 | +0.319 | **−0.424** |
| ETH | short-win  | −0.894 | +0.230 | +0.008 |
| ETH | short-lose | −0.867 | −0.006 | **−0.330** |
| ETH | long-win   | −0.901 | +0.364 | +0.105 |
| ETH | long-lose  | −0.870 | +0.282 | **−0.163** |
| XRP | short-win  | −0.890 | +0.297 | −0.007 |
| XRP | short-lose | −0.844 | +0.193 | **−0.152** |
| XRP | long-win   | −0.872 | +0.475 | +0.085 |
| XRP | long-lose  | −0.856 | +0.411 | **−0.195** |

- **TRADE valley: NO separation** — every cell is born ~−0.85 to −0.91 (universal deep opposite-side hole).
- **TRADE peak: separates by duration** (long>short), weakly by win/lose. Exception: BTC/ETH **short-lose
  peaks LOW** (+0.02 / −0.01) — short-duration losers barely get the flow to flip with-side at onset.
- **TRADE exhaustion (close): the CLEANEST universal win/lose separator on all 4 coins** — winners close
  ≈0 to +0.1 (flow stays balanced), **losers close −0.14 to −0.42 (flow flipped hard AGAINST the side)**.

### BOOK imbalance K=5 (signed to side), valley / peak / exhaustion
| coin | cell | valley | peak | exh |
|------|------|--------|------|-----|
| SOL | short-win  | −0.021 | −0.004 | +0.002 |
| SOL | short-lose | +0.023 | +0.005 | −0.003 |
| SOL | long-win   | −0.018 | +0.031 | +0.007 |
| SOL | long-lose  | −0.008 | +0.005 | +0.009 |
| BTC | short-win  | +0.018 | **+0.130** | +0.114 |
| BTC | short-lose | −0.245 | **−0.387** | −0.312 |
| BTC | long-win   | −0.003 | **+0.198** | +0.099 |
| BTC | long-lose  | −0.100 | **−0.192** | −0.177 |
| ETH | short-win  | −0.014 | +0.063 | +0.054 |
| ETH | short-lose | −0.001 | −0.060 | −0.116 |
| ETH | long-win   | +0.001 | +0.094 | −0.014 |
| ETH | long-lose  | +0.031 | +0.079 | −0.031 |
| XRP | short-win  | −0.008 | +0.046 | +0.058 |
| XRP | short-lose | −0.038 | −0.027 | −0.051 |
| XRP | long-win   | **+0.084** | **+0.093** | +0.068 |
| XRP | long-lose  | +0.034 | −0.007 | −0.033 |

- **SOL: book is FLAT (±0.03) — no separation at any point, any level (K1/5/10).** On SOL the book channel
  carries no cell information; trade imbalance is the whole story.
- **BTC: book SEPARATES win/lose STRONGLY and PERSISTENTLY at all three points** — winners book POSITIVE
  (with-side) valley→peak→close, losers book NEGATIVE (against-side) the entire leg. This holds at K1/5/10.
  Born-book sign already forecasts win/lose *before the leg fires* (winners ≈0/+0.02, losers −0.10/−0.25).
- **ETH: book weakly separates in the tail** — winners peak/hold slightly positive, short-lose goes
  negative (peak −0.06, close −0.12). Intermediate between SOL (flat) and BTC (strong).
- **XRP: book separates only the LONG-WIN cell** (born +0.084, stays positive) vs others near 0.

**Where they DON'T separate:** the TRADE VALLEY never separates any cells (universal birth depth). The BOOK
channel doesn't separate on SOL at all, and only weakly/partially on ETH/XRP. The one clean book separation
is BTC (all points, all K).

---

## 3. Turn / flatten signals — PEAK (exit/flip tell) and VALLEY (birth tell), per cell

### The universal shape (both limbs, all coins)
- **Pre-fire (ascension):** trade imbalance is born at its deep negative valley (~−0.85), FLATTENS at the
  bottom of the hole, then ASCENDS (hockey-stick / convex-cubic) to the onset peak. This is the birth tell.
- **Tail (post-onset):** trade imbalance DECAYS from the peak. Whether it decays to ~0 (winner) or crosses
  to negative (loser) is the exhaustion/flip tell.

### PEAK (t=0) exhaustion / flip tell — per cell
- **short-win / long-win (all coins):** trade tail decays GENTLY and holds ≥0 to the close (exh ≈ 0 to +0.1).
  Flow never flips against — the ride simply de-energizes. No adverse flip = the winner signature.
- **short-lose / long-lose (all coins):** trade tail decays THROUGH zero into strong negative (exh −0.14 to
  −0.42). The flow REVERSES onto the other side mid-tail — that reversal IS the loss. On SOL/XRP the loser
  tail often bottoms (valley near t≈0.8–0.98) then gives a tiny end-bounce (the next leg's birth beginning).
- **Does BOOK flip at the peak, before/with the trade flip?** NO. On no coin does book imbalance "flip" at
  the peak — it is a slow, persistent LEAN, not a turn-timed signal. On BTC book holds its sign (winner +,
  loser −) straight through the peak and tail; it does not lead or coincide with the trade-imbalance tail
  reversal. The FLIP at the peak is a trade-flow phenomenon; the book contributes a standing win/lose
  CONTEXT (on BTC), not a turn tell.

### VALLEY (birth) tell — per cell
- **Trade imbalance:** all cells born at ~−0.85 to −0.91 and flatten there before ascending — the birth tell
  (max opposite-side flow, then reversal up) is UNIVERSAL and does NOT distinguish win/lose or duration.
- **Book imbalance at birth = the pre-fire win/lose tell on BTC:** winners born book ≈0/+0.02, losers born
  book ≈−0.10/−0.25 — the loser's book is already leaning against the side at the valley, before ignition.
  On SOL book birth ≈0 for all (no tell); on XRP only long-win is born book-positive (+0.08).

---

## 4. THE EQUATIONS — 8 per coin (4 cells × 2 limbs, split at the fire)

Pre-fire x∈[0,1]: 0=birth/valley → 1=fire/onset. Tail x∈[0,1]: 0=fire → 1=close. Best functional form is
chosen PER cell/limb by adjusted-R² among {linear, quadratic, cubic, hockey(2-seg kink), exp}; forms differ
per cell as Greg allowed. "cleaner representation" = mean fit-R² across the 8 equations, per coin.

### SOL — cleaner in TRADE (R²: trade 0.968 vs book 0.926; book arcs are flat/uninformative)
TRADE:
- short-win  PRE `y=−0.875+2.117x (x≤0.32), blade +0.963` R²0.989 | start−0.903 peak+0.123 —
  TAIL `y=+0.107+0.090x−1.536x²+0.901x³` R²0.933 | peak+0.123→close+0.004, exhaust peak@t0.03
- short-lose PRE `y=−0.883+2.372x (x≤0.15), blade +1.208` R²0.983 | −0.908→+0.146 —
  TAIL `y=+0.208−0.978x (x≤0.55), blade −0.364` R²0.977 | +0.146→**−0.292**, monotone decline
- long-win   PRE `y=−0.834+2.197x−2.292x²+1.543x³` R²0.991 | −0.889→+0.374 —
  TAIL `y=+0.354−0.596x (x≤0.65), blade −1.195` R²0.911 | +0.374→+0.085, monotone
- long-lose  PRE `y=−0.883+2.203x (x≤0.15), blade +1.268` R²0.989 | −0.902→+0.306 —
  TAIL `y=+0.389−1.174x (x≤0.80), blade +0.948` R²0.967 | +0.306→**−0.139**, valley@t0.80 then bounce

### BTC — cleaner in BOOK (R²: book 0.990 vs trade 0.979; book also SEPARATES win/lose)
TRADE:
- short-win  PRE `y=−0.785+2.108x−2.033x²+1.114x³` R²0.996 | −0.793→+0.257 —
  TAIL `y=+0.273−0.406x (x≤0.40), blade −0.771` R²0.962 | +0.257→−0.024
- short-lose PRE `y=−0.805+1.665x (x≤0.17), blade +0.897` R²0.989 | −0.814→+0.024 (low peak) —
  TAIL `y=−0.054+0.815x−3.143x²+1.830x³` R²0.964 | +0.024→**−0.342**, peak@t0.15
- long-win   PRE `y=−0.833+1.953x (x≤0.15), blade +1.167` R²0.996 | −0.847→+0.355 —
  TAIL `y=+0.441−1.233x+1.340x²−0.916x³` R²0.948 | +0.355→−0.003
- long-lose  PRE `y=−0.878+2.493x−3.713x²+2.531x³` R²0.993 | −0.863→+0.319 —
  TAIL `y=+0.343−1.242x+0.906x²−0.608x³` R²0.980 | +0.319→**−0.424**

BOOK (K5) — the distinct-shape channel on BTC:
- short-win  PRE `y=+0.025−0.016x+0.326x²−0.198x³` R²0.995 | +0.018→**+0.130** (rises, with-side) —
  TAIL `y=+0.128+0.053x−0.249x²+0.184x³` R²0.987 | +0.130→+0.114 (holds POSITIVE)
- short-lose PRE `y=−0.244−0.050x (x≤0.57), blade −0.276` R²0.990 | −0.245→**−0.387** (sinks, against-side) —
  TAIL `y=−0.390−0.019x (x≤0.42), blade +0.140` R²0.994 | −0.387→−0.312 (holds NEGATIVE)
- long-win   PRE `y=−0.001+0.325x (x≤0.38), blade +0.136` R²0.996 | −0.003→**+0.198** —
  TAIL `y=+0.208+0.165x−1.090x²+0.817x³` R²0.997 | +0.198→+0.099 (holds positive)
- long-lose  PRE `y=−0.105+0.100x (x≤0.40), blade −0.188` R²0.986 | −0.100→**−0.192** —
  TAIL `y=−0.196−0.574x+1.269x²−0.693x³` R²0.972 | −0.192→−0.177 (holds negative)

### ETH — cleaner in TRADE (R²: trade 0.962 vs book 0.952, close; book weak-separating in tail)
TRADE:
- short-win  PRE `y=−0.890+3.207x−3.390x²+1.535x³` R²0.983 | −0.894→+0.230 —
  TAIL `y=+0.224−0.649x` (linear) R²0.934 | +0.230→+0.008
- short-lose PRE `y=−0.868+2.724x−2.715x²+1.233x³` R²0.979 | −0.867→−0.006 (peak≈0) —
  TAIL `y=−0.002−0.095x (x≤0.15), blade −0.644` R²0.954 | −0.006→**−0.330**
- long-win   PRE `y=−0.846+1.834x−1.689x²+1.279x³` R²0.984 | −0.901→+0.364 —
  TAIL `y=+0.406−0.537x (x≤0.70), blade −1.309` R²0.932 | +0.364→+0.105
- long-lose  PRE `y=−0.849+2.349x−2.821x²+1.778x³` R²0.990 | −0.870→+0.282 —
  TAIL `y=+0.297−0.629x (x≤0.42), blade −1.104` R²0.939 | +0.282→**−0.163**
BOOK (K5): sw PRE `−0.015+0.045x,blade+0.154` →peak+0.063 / TAIL cubic hold +0.054;
sl PRE `+0.005−0.003x,blade−0.288`→−0.060 / TAIL `−0.062−0.109x…`→−0.116 (valley@0.79);
lw PRE cubic→+0.094 / TAIL `+0.092+0.070x,blade−0.173`→−0.014 (peak@0.20);
ll PRE cubic→+0.079 / TAIL `+0.084−0.338x,blade−0.005`→−0.031 (flatten@0.35).

### XRP — cleaner in TRADE (R²: trade 0.966 vs book 0.900; book flat except long-win)
TRADE:
- short-win  PRE `y=−0.896+2.999x−3.764x²+2.211x³` R²0.989 | −0.890→+0.297 —
  TAIL `y=+0.317−1.172x+0.213x²+0.260x³` R²0.958 | +0.297→−0.007, valley@t0.98
- short-lose PRE `y=−0.861+3.010x (x≤0.15), blade +1.037` R²0.980 | −0.844→+0.193 —
  TAIL `y=+0.214−0.743x−0.808x²+0.862x³` R²0.963 | +0.193→**−0.152**, valley@t0.93
- long-win   PRE `y=−0.919+2.779x−3.257x²+2.041x³` R²0.990 | −0.872→+0.475 (highest peak) —
  TAIL `y=+0.455−1.483x+2.674x²−2.112x³` R²0.907 | +0.475→+0.085, monotone
- long-lose  PRE `y=−0.864+2.278x−2.620x²+1.727x³` R²0.993 | −0.856→+0.411 —
  TAIL `y=+0.435−1.656x+2.204x²−1.501x³` R²0.948 | +0.411→**−0.195**, monotone
BOOK (K5): only long-win carries a distinct positive shape (PRE cubic +0.084→+0.093, TAIL holds +0.068);
sw/sl/ll book arcs are near-flat (|coeffs| small, R² 0.78–0.99 fitting low-amplitude wiggle).

### Which representation is cleaner/more distinct?
- **By fit-R²:** TRADE cleaner on SOL/ETH/XRP; BOOK cleaner on BTC.
- **By separation (the thing that matters):** the TRADE tail equation separates win/lose on ALL 4 coins
  (winner tails end ≈0, loser tails end −0.14..−0.42). The BOOK equation separates win/lose ONLY on BTC
  (winner book-shapes stay POSITIVE, loser book-shapes stay NEGATIVE at both limbs; K1/5/10 agree), weakly
  on ETH, and only for the long-win cell on XRP; on SOL book equations are flat noise.
- **The pre-fire ascension form is the same family everywhere** (deep-born hockey/convex-cubic rocketing to
  the onset peak); cells differ mainly in blade slope and peak height, not in kind. The TAIL forms are the
  distinguishing equations (win = flatten near 0; lose = decline through 0 to negative).

---

## 5. Result-disciplined caveats
- **Trade valley and pre-fire MEAN do NOT decide anything** (win/lose or duration) — only the trade PEAK
  height (duration) and the trade TAIL sign (win/lose) do. Reported plainly; the ascension level is not a tell.
- **Book imbalance is coin-specific, not universal:** a strong, standing win/lose separator on BTC; weak on
  ETH; long-win-only on XRP; **flat and uninformative on SOL.** Do not treat book imbalance as a cross-coin
  signal.
- **Book does not flip at the peak** on any coin — it is a persistent lean, not a turn/exit tell. The turn
  signal at both the valley and the peak lives in the TRADE channel; the book adds standing context (BTC).
- All numbers are per-cell MEAN arcs from the live executor over one multi-day book window per coin; this is
  characterization of the archetype shapes, not a per-trade gate and not sizing-grade.
