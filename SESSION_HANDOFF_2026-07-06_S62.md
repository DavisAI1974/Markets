# SESSION HANDOFF — S62 (2026-07-06) — THE 3-PIECE REBUILT + THE E300 BREAKTHROUGH + the DIRECTION reframe

**Primary artifacts:** `S62_RESUME.md` (running resume note) + this file. Branch reconciled to
canonical `5c5vg9` at open (designated branch was cut from the wrong parent AGAIN — reset first).
Fee frame = Coinbase (Greg handles fees; all tests fee=0, flip = 22bp taker cross — locked).

## 1. THE 3-PIECE RIG — rebuilt, reproduces R11 EXACTLY (`scripts/_s62_3piece_harness.py`)
Greg's 3-piece (R11): at first-underwater, HOLD winner-dip / FLATTEN chop-loser / FLIP trend-loser.
Rebuilt from `armed_midband_flips` + walked each leg's path. Reproduces every R11 SOL anchor to the
decimal: baseline **+1.77**, flatten-only oracle **+13.93** (R11 +13.9), full 3-way oracle **+26.02**
at flip_cost=22 (R11 +26.09), n=**971**, winners=**508**, winners-kept **508/508**. The flip is a
~22bp taker cross even at fee=0 (the locked convention).

**Entry-flip ORACLE per coin (flip the big losers at entry = the prize, winner-preserving):**
SOL +30 / ETH +23 / DOGE +22 / XRP +22 / BTC +14 $/hr @ $5k (all 5: baseline near zero -> big lift,
100% winners kept). This is the ceiling every classifier chases.

## 2. ⭐ THE BREAKTHROUGH — the 3-PIECE at E300 (`scripts/_s62_e300_3piece.py`)
The signal to separate big losers is NOT at entry (winners-invisible, ~0.55 AUC every in-container
way). It IS mid-leg. **Decide at E300 (300s after entry): the realized DEPTH predicts DEATH (final
gross<=-40) at AUC 0.69-0.77 on ALL 5 coins** — the first strong, robust, cross-coin classifier of
the session. $/hr (hold/flatten-chop/flip-trend, per-week OOS): **BTC +1.29 (crosses zero from
-0.81, 4/5 weeks), XRP +0.81**; ETH +0.21; SOL -0.05 / DOGE -0.43. In-leg TREND EFFICIENCY feature
added (smooth adverse = death, choppy = recovery) — the render-driven separator for SOL/DOGE.
HOW IT EARNS (load-bearing): via **death-vs-WINNER** separation (winners don't go deep -> depth
flags them) + the FLATTEN fallback — NOT by predicting recovery. One 30d window; needs 2nd-window
confirm. The deep-arm variant (`_s62_armed_trend.py`) is the same lever: ETH/BTC/DOGE +1.1..+1.6 at
arm -20/-30.

## 3. ⭐ THE REFRAME (Greg, load-bearing): it's a DIRECTION problem, not win/lose
The big losers are SHORTS into clean steady UPTRENDS (and longs into downtrends) — the machine
correctly sensed a big move and took the WRONG SIDE. A big-losing short is a big-winning long we
mislabeled. Confirmed in the SOL render (`docs/renders/s62/e300_sol.png`: 10 biggest losers = all
shorts into smooth uptrends). **Win-LONG vs WIN-SHORT coeffs are a PERFECT MIRROR (-1.0 in the
residual)** — a clean direction axis exists (unlike the 99%-parallel win/lose pair). So the target
is direction, not win/lose. BUT: predicting the winning direction at/near entry is ~chance (0.47-
0.56) from coeff, momentum, and dipole — because at the 600s scale the market MEAN-REVERTS (the
machine's own edge; a contrarian that buys valleys). See §5 for where the direction IS readable.

## 4. THE COEFF + DIPOLE tiers — mapped, ~chance at entry (do not re-chase in-container)
- **Loser signature (coeff):** BTC/ETH loser coeffs ARE in git (`fingerprint_dataset/coeffs/`,
  4,377 lose sigs). But in-container coeff at mid-band = ~chance every readout (centroid, multivariate,
  win/lose AND win-long/win-short direction). The old 0.93 in-sample was the S34 date/regime confound;
  the win-long/win-short spread is REAL in the archives (+0.027 btc) but collapses on current legs
  (+0.0009). Coeff gate on the flip = net-negative, and BACKWARDS on the target (says "short wins"
  for shorts-into-uptrends -> flattens 8/10 of the biggest losers). Scripts: `_s62_coeff_bridge.py`,
  `_s62_loser_flip.py`, `_s62_winner_flip.py`, `_s62_armed_gate.py`.
- **3 dipole agents (paper/dive/s61alt):** flow features are price-ORTHOGONAL but ~chance at entry
  (winners-invisible at the flow tier too). Persisted `data_s62/dipole_feats/` + reports.
- **Dipole-as-trend-gate agent:** the S36 divergence/aligned-flow read is ~chance (0.44-0.56) for
  DEATH-vs-RECOVERY at every arm depth. The dipole's real S36 edge was a DIFFERENT task (swing-
  reversal on bybit, sub-fee). `data_s62/dipole_trend/FINDING.md`. Key: death-vs-RECOVERY (which
  underwater leg bounces) is ~unpredictable from ANY causal signal at any depth = the true wall.

## 5. ⭐⭐ THE BEST LEAD FOR NEXT SESSION — the 1-HOUR TREND (test S63)
The market mean-reverts at 600s (machine's edge) — BUT the big losers are the minority FADING a
strong **1-HOUR** trend. Among big losers, the 1h trend (mom over 3600s) predicts the forward
direction at **0.58-0.67** (BTC 0.672, ETH 0.633, XRP 0.655, SOL 0.585) while overall momentum is
BELOW 0.5 (mean-reverting). Greg: "we need to know the trend — short or long" — at the RIGHT horizon
(1h, not 600s). The pieces from earlier converge: R13e flip pre600<-80 (+0.61, the 600s freight-
train), S57/S56 worst-10 = fade-the-freight-train, S36 dipole trend-follow. NEXT SESSION (Greg):
(1) build + test the **1h-trend-fade flip** at entry (signal = -side*mom1h; flip the strongest 1h-
trend-fades; per-week OOS, big10-flip, shuffle floor); (2) **spin the dipole/trend agent back up**
to build the ACCURATE 1h trend-following read (dipole at the 1h scale + momentum). This is the
promising thread — the big losers ARE trend-continuations that a 1h read can flag.

## STANDING / INFRA
Bins at /tmp/backfill (ephemeral, re-pull via backfill_binance_spot.py). Coeff caches /tmp/s62cache
(ephemeral). Renders docs/renders/s62/ (need `pip install matplotlib`). All scripts `scripts/_s62_*`.
Flip-then-manage (R13f) still queued. Kraken parked. Sync canonical after every push; a parallel
paper_trade cron pushes to canonical — rebase, don't clobber.
