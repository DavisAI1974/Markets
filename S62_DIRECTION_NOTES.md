# S62 DIRECTION-REFRAME NOTES (Greg's insight: big losers are mis-DIRECTED, not win/lose)

Greg's reframe (load-bearing): the big losers aren't a win/lose problem — they're a DIRECTION
problem. The machine correctly senses a big move and takes a position; it just takes the WRONG
SIDE. A big-losing long is a big-winning short we mislabeled. So the target isn't win-vs-lose
(winners-invisible, because winners and losers of the SAME side look identical) — it's
win-LONG vs win-SHORT. "What are the coeffs for win-long and win-short?"

## R1 — WIN-LONG vs WIN-SHORT are a PERFECT MIRROR (confirmed)
Git centroids: win-long = win coeffs of the {coin}_coinbase_BUY cell; win-short = win coeffs of
the SELL cell. Raw cos(win-long, win-short) = 0.9997 (shared common-mode), BUT the RESIDUAL
(after removing the shared mean) cos = **-1.0000 — a perfect mirror** (btc + eth). The direction
lives cleanly in the ~9% residual as an anti-correlated axis (the S40 buy/sell mirror). This is
UNLIKE the win/lose pair, whose residual was same-side mush. So there IS a clean DIRECTION axis.

## R2 — but the direction axis does NOT predict the winning direction on current legs
Project current-leg coeffs (in-container pipeline) onto the direction axis:
- git axis: ETH AUC(win-dir) 0.548-0.559 (orthogonal to side, 0.512), BTC 0.48 (chance).
- RE-DERIVED axis (current win-long vs win-short, per-week OOS, same-period): sol 0.514 / eth 0.491
  / btc 0.471 = CHANCE. The git 0.55 was the S34 date confound leaking.
- Flip the strong disagreements: net-negative/flat everywhere (flips ~as many winners as big-losers).
- FUNDAMENTAL: given the side is known, "predict winning direction" is informationally IDENTICAL to
  "predict win/lose" (price_dir = side for winners, -side for losers) -> same ~0.55 ceiling.

## R3 — the RIGHT instrument for direction is MOMENTUM (trend), not the coeff
The direction of a big move is carried by momentum (the freight-train). Among the BIG MOVERS
(|gross|>=40), longer-term raw momentum predicts the winning direction:
- BTC mom1800 big-movers AUC **0.591**; ETH mom600/1800 **0.55**; SOL ~0.51.
- All-legs AUC is BELOW chance (0.43-0.46) — the machine correctly MEAN-REVERTS small wiggles and
  only loses by FADING BIG TRENDS. Greg's mechanism, confirmed: big losers = trend-fades.

## R4 — trend-fade flip: BTC is week-CONSISTENT (the one robust directional edge), but small
Multi-scale trend-fade (-side*momentum at 300/600/1200/1800/3600s), predict loss-side, per-week OOS,
flip the strongest:
- **BTC: base -1.18 -> +0.39, per-week Δ +0.5/+0.3/-0.1/+0.9/+0.6 = 4/5 weeks POSITIVE** (first
  non-week-fragile directional signal all session; catches 16 bigL vs 16 win, bigL bigger -> net+).
  BUT doesn't cross zero (-1.18 -> -0.79).
- SOL +0.16 marginal; ETH -0.56 OOS (its promising single-scale +0.78 was in-sample-cutoff optimism).
- STACKING trend + cheap + dipole-flow DILUTES it (btc +0.39 -> +0.05): more features overfit 30d.

## VERDICT
Greg's reframe is conceptually RIGHT (mirror -1.0; big losers = trend-fades) and gave the first
week-CONSISTENT directional edge (BTC trend-fade +0.39). But the magnitude is the same ~0.55
winners-invisible ceiling approached from the direction angle — because direction == win/lose given
side. Nothing crosses into clear profit in-container. The pure simple trend signal beats every stack.
Path: (1) BTC trend-fade consistency is the thread (needs a 2nd window + a stronger direction read);
(2) flip-THEN-MANAGE (R13f) sidesteps entry-prediction by managing the reversed leg AFTER the
trend-fade flip fires; (3) the encoder tier (E: drive) — the one untried signal, but honestly may
also hit the ceiling (S35 0.72-0.84 was date-confounded; onset canary failed).
