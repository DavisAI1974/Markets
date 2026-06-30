# SESSION HANDOFF — S46 (2026-06-30) — WIRED the maker-at-the-turn executor to Greg's full spec; leakage PASS; all 5 cells net+; wrong-tail exhaustion gate built but marginal

Branch: `claude/crypto-liquidity-signals-s46-gwvm31` (harness; merged canonical `5c5vg9` S45 tip in via ff,
then pushed S46 work here). All numbers PROVISIONAL on ONE ~11.7h window (do NOT size off them).

## WHAT WAS BUILT — `odcore/swing_maker.py` (NEW, sanctioned by the strategy doc) + `_render_trades.py` swing/swingwalk modes
The S46 job was to wire the **maker-at-the-turn** strategy. Greg corrected it live (3 phone screenshots from the
S45 chat + messages); the final executor matches his spec exactly:
- **Post ONLY the conviction side, re-quote as price moves, NEVER show the off-side.** best BID on the valley +
  all the way UP (long; sellers hit us as price rises); best OFFER at the peak + all the way DOWN (short; buyers
  lift us). Flip the shown side at each turn. At the peak the offer fill BOTH sells the long and goes short
  ("sell at peak and go short at peak").
- **"Have the BEST bid/offer" = front of queue** (price improvement): fill on the first REAL opposing trade.
  This is load-bearing — joining behind SOL's deep top-of-book (queue_frac=1) fills <10% and bleeds 89% to taker;
  at the front the turn aggressor hits us as a MAKER.
- **NO time/climax windows** (Greg: "the time windows are irrelevant"). The conviction quote rests the whole leg
  (turn to turn); fill = first opposing trade (`_next_positive`, O(n)), capped only at the next turn.
- **Taker is the LAST option** — only when no opposing trade arrives before the next turn. On SOL: 90% maker / 10% taker.
- Direction = the validated CAUSAL flip detector (`odcore/flip_detector.py`, S40 W=60/REV=0.10 scaled to 100ms =
  W=600); the QuietFloor `confirm`s the shock. Causal: decisions use data<=flip; marks use the future.

## RESULTS (PROVISIONAL, one 11.7h window)
- **Leakage: PASS** — `assert_no_leakage` on the flip/position signal (W=600,REV=0.10), 7 idxs x 3 reps, 0 fails.
- **Walk-through (`_render_trades.py sol 1 1.5 swingwalk`)** — the SAME 10 S45 floor-signal trades, OLD vs NEW:
  **loser #1 BID −9.98 → SHORT +12.66 (maker)**; every old BID-into-a-peak loser inverts to a short; the +15.16
  peak → SHORT +18.46. NEW sum +68.82 vs OLD +2.58 over those moments.
- **Per-cell verdict (gross/leg before fees; maker% / net-per-leg / win):**
  ```
  cell  K  maker%  net/leg  win%  half_sp   mean_swing
  sol   1   90%    +2.19    74%   0.67       3.64
  doge  1   50%    +1.12    53%   0.69       3.76
  xrp   1   84%    +1.01    65%   0.47       2.51
  eth   1   88%    +0.40    52%   0.03       2.23
  btc  10   97%    +0.60    62%   0.0008     1.81   (spread-starved control — still net+ on SWING capture, not spread)
  ```
  All 5 net-positive. net/leg tracks half-spread (edge is largely spread capture) EXCEPT btc, which is net+ on
  pure swing capture (0.0008 half-spread) — the turn-to-turn timing itself carries.
- **Wrong-tail gate (`entry_gate` + `exhaustion_gate` via `info_dipole.divergence`):** built + A/B'd. Gating
  entries on flow-opposition-OR-exhaustion and HOLDING (riding the trend) through unconfirmed flips: SOL 796→507
  legs, taker 81→52, swings≥20bps 5→8, BUT net/leg +2.19→+1.99 and win 74→71%. **Marginal/slightly-negative on
  this one window** — the dipole divergence does not cleanly isolate the wrong-tail here. KEPT OFF by default
  (executor supports `entry_gate`; render reports the A/B). Revisit as data accrues.

## HONEST CAVEATS
- Front-of-queue assumes best-price priority (latency/colocation) and the model credits the full half-spread
  (price improvement gives up a little). mean swing ~2–4 bps on this window — most swings are below the 20bps
  fee floor; the few that clear it are net+ (sol +25.9/leg, n=5). The edge is real but small & PROVISIONAL.
- The remaining red legs are the genuine flip wrong-tail (~36% no-reversal); the exhaustion gate didn't fix it.

## FILES (S46)
- `odcore/swing_maker.py` NEW — the executor (front-of-queue, no window, taker last-option, entry_gate).
- `_render_trades.py` — added `swing` (per-cell verdict + render), `swingwalk` (OLD-vs-NEW walk-through),
  `exhaustion_gate()`; existing floor/confirm/opposing modes untouched (QUEUE_FRAC kept = S45 baseline only).
- Renders: `_render_trades_sol_swingwalk.png`, `_render_trades_<coin>_swing.png` (gitignored).

## NEXT (S47)
1. **Confirm on a 2nd window / as the book accrues** — every S46 number is one 11.7h window. The 6h cron is
   accruing the alt books; re-run the per-cell verdict + walk-through on a fresh window before sizing.
2. **The inventory/scaling refinement** — the spec's "re-quote the ask at each new lower price, EXTENDING the
   short all the way down" is approximated by a single entry per leg; model the scale-in for a better avg entry.
3. **Wrong-tail** — the exhaustion gate is marginal; try climax-volume confirmation (S40 ~2x vol AT the turn)
   and/or a per-cell gate tune (NOT on one window).
4. **Per-leg fees / venue rebate** — current net is gross-of-fee (half-spread is in the prices). Add the taker
   fee on the last-option exits + any maker rebate for a true net deploy number.
5. Lock the operating points into the QuietFloor registry once validated on >1 window, then the production emit path.
