# S62 RESUME — pick up here next session

## Where we landed (the arc)
Greg's reframe cracked the wall: the big losers are DIRECTION mistakes (shorts into clean
uptrends), not win/lose — confirmed in the SOL render (10 biggest losers = all shorts into
smooth uptrends; win-long/win-short coeffs are a perfect mirror -1.0). The signal to catch
them is NOT at entry (winners-invisible, ~0.55 AUC every in-container way: price, coeff
win/lose AND direction, 3 dipole agents' flow — all ~chance at entry).

## THE BREAKTHROUGH (committed, works): the 3-piece at E300
`scripts/_s62_e300_3piece.py` — decide MID-LEG at E300 (300s in), not at entry. The realized
DEPTH predicts DEATH (final <=-40) at AUC 0.69-0.77 on ALL 5 coins (first strong cross-coin
classifier). $/hr: BTC +1.29 (crosses zero, 4/5wk), XRP +0.81; ETH +0.21; SOL -0.05 / DOGE -0.43.
SOL/DOGE don't convert because at E300 a death and a dip-recovery look the same on depth; the
render says the separator is TREND EFFICIENCY (smooth adverse = death, choppy = recovery) — added
to the script (in-leg eff features + efficiency action split), NOT yet rerun/verified.

## Greg's LAST DIRECTION (in progress, the open thread): the ARMED FLIP
`scripts/_s62_armed_flip.py` — arm at first -10/-15 (early, before the -90), fire the flip ONLY
when CONFIRMED by the dipole "strong-trade" signal (own + cross-major adverse taker-flow lean at
the arm = flow driving hard against us = real trend) + coeff direction verify. Ran it:
NEGATIVE on all coins (sol -2.11, eth +0.22 best) BECAUSE the confirmation AUC at -10/-15 is only
0.53-0.60 (vs 0.72 at E300) — too EARLY to tell a death from a dip; fires on ~as many recoveries
as deaths. `scripts/_s62_armed_render.py` (SOL armed-flip render, arm point + fire marked) is
BUILT but NOT yet run (Greg ended the night before it rendered).

## THE OPEN QUESTION for next time
The tension: fire EARLY (Greg's want, catch the move) vs fire LATE (E300, enough info to confirm).
At -10/-15 the info isn't there yet (0.55). E300 has it (0.72) but less move left. Next moves to try:
1. Run `_s62_armed_render.py` (SOL) — SEE which legs the early flip fires on (deaths vs recoveries).
2. Rerun `_s62_e300_3piece.py` with the efficiency feature (does it lift SOL/DOGE?).
3. A MIDDLE arm depth / adaptive: arm at -10/-15 but only FIRE once the dipole strong-trade
   confirmation crosses a real threshold (may fire later than -15 but earlier than E300) — the
   "arm early, wait for the dipole to say yes" design at its natural firing time, not forced to -15.
4. The efficiency + dipole strong-trade as the confirm, swept over WHEN it's evaluated.

## Standing
Branch reconciled to canonical 5c5vg9; sync canonical after every push. Fee frame = Coinbase
(Greg handles fees; fee=0 in tests, flip=22bp taker). Bins at /tmp/backfill (ephemeral; re-pull
via backfill_binance_spot.py). Coeff caches /tmp/s62cache (ephemeral). Dipole feature files +
reports persisted in data_s62/dipole_feats/ + dipole_{paper,dive,s61alt}_s62.md. Renders in
docs/renders/s62/. matplotlib needs `pip install matplotlib` in a fresh container.

## GREG'S REFINED DESIGN (night-2 close — DO THIS FIRST next session)
The pure armed-flip lost because it flipped BLIND at -10/-15. Fix = gate the flip with the
win-long/win-short coeff, and sweep deeper arm numbers:
1. SWEEP the arm number: -20, -25, -30, -35, -40 (not just -10/-15). Deeper = more info (the
   confirm AUC rises with depth: 0.55 @ -15 -> 0.72 @ E300).
2. WIN-LONG/WIN-SHORT COEFF as a second required test at the arm. Check whether the FLIP
   direction (opposite of our side) is a WIN or LOSS per the direction coeff:
     - coeff says LOSS (flip wouldn't win either -> just chop) -> FLATTEN (cut, don't flip).
     - coeff says WIN  (flip direction is the real winner)     -> FIRE the flip on the number.
3. Fire SOONER (earlier arm) when the coeff confidently knows long vs short.
Net: arm at the number -> coeff gate -> WIN=flip / LOSS=flatten. This turns the blind early
flip into a gated one (flatten the chop, flip only confirmed-winning-direction reversals).
Build on `scripts/_s62_armed_flip.py` (add flatten action + coeff win/loss gate + arm sweep);
render SOL after (`_s62_armed_render.py`) to verify the big losers flip and the dip-recoveries
flatten (not flip). The direction coeff = win-long/win-short mirror axis (perfect -1.0), already
in `coeff_dir_map()`; here use it as a WIN/LOSS gate on the flip direction, not just a feature.
