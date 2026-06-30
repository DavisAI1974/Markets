# STRATEGY — Maker-at-the-Turn / asymmetric conviction quoting (S45, Greg)

Status: SPEC (not yet wired). This is the strategy to BUILD next session. It supersedes the symmetric,
two-sided, hold=1 maker tests in the S45 handoff (those numbers do NOT apply here — different execution
model). Renders that motivate it: `docs/renders/_render_trades_sol_floor.png` (the bleeding symmetric
maker), `_render_trades_sol_confirm.png` vs `_render_trades_sol_opposing.png` (polarity), and
`_loser_sol_floor_0.png` (the canonical falling-knife loser).

## The core realization (Greg, S45)
A symmetric, two-sided passive maker is **at the counterparty's mercy** — you only fill when someone
trades against you, and mid-trend that someone is RIGHT and you are the adversely-selected victim. That is
every red fill in the autopsy (`_dissect_fills.py`): a bid fills because sellers press → mid drops while
you queue → `d_wait` is structurally negative and swamps the half-spread.

The fix is to be a maker ONLY at the turns, and ONLY on the side where the aggressor is WRONG:
- **At a PEAK (dipole/flip says top):** post the best OFFER, pull the bid. Aggressive BUYERS lift your
  offer (they're buying the high — euphoria/climax, adversely selected) → you are filled SHORT at the top,
  as a maker (earn the spread, no fee).
- **Ride it down** keeping the best OFFER (chase it down to stay at the front; bounce-buyers keep lifting
  you), bid stays PULLED so sellers can NOT hit it (that is the knife-catching fill we must never take).
- **At the VALLEY (flip says bottom):** post the best BID, pull the offer. Aggressive SELLERS hit your bid
  (they're dumping the low — capitulation, adversely selected) → you cover/flatten the short at the bottom,
  again as a maker.
- **Ride back up** keeping the best BID (offer pulled), repeat into the next peak.

Both legs are MAKER; you collect the spread on BOTH turns and never cross it. Taker is only a FALLBACK to
flatten if a turn does not bring enough opposing volume to fill the passive quote.

The one-line principle: **skew the quotes with the alpha.** Provide liquidity to the people who are wrong
(buyers at tops, sellers at bottoms — the S40 capitulation CLIMAX, ~2x volume AT the turn) and refuse it to
the people who are right. Symmetric making made US the victim; one-sided making at the turn makes the
aggressor the victim.

## Why our backtest lost (reconciliation)
We showed BOTH sides continuously and at hold=1, so we got filled by the RIGHT-side aggressors mid-trend
(sellers hitting our bid as price fell = catching knives → `d_wait −6.66` on loser #1). Direction came from
`depth_imb` (which said "bid-heavy → buy" at a peak and was wrong). The fix changes three things:
1. **Entry trigger** = flip/turn detector AT a price extreme, not the QuietFloor shock gate firing anywhere.
2. **Direction** = fade the extreme (short the peak / buy the valley), from the FLIP — not from the level.
3. **Exposure** = ONE-SIDED (only the conviction side shown; the other side pulled), re-quoted as price
   moves; **hold to the NEXT turn** (the swing), not hold=1.

Note this is NOT the earlier "confirm vs opposing" result: that was for continuous two-sided hold=1 making
(where CONFIRM/continuation won). This strategy is the SWING/reversal trade executed correctly (maker fill
at the extreme where the aggressor is wrong), which the hold=1 test could not represent.

## Quoting state machine (to wire)
```
near a PEAK (flip = top):      show OFFER, pull BID    -> lifted -> SHORT the top (maker)
on the way DOWN:               chase OFFER down, BID pulled  (no knife-catching)
near a VALLEY (flip = bottom): show BID, pull OFFER    -> hit   -> cover/LONG the bottom (maker)
on the way UP:                 chase BID up, OFFER pulled
```
Position state machine {flat, short, long}; flip switches the shown side; fills are the aggressor volume
clearing the queue on the shown side; PnL accrues over the swing (peak->valley), both legs maker.

## What to build next session
1. **Wire the executor** into `odcore/maker_book.py` (or a new `odcore/swing_maker.py`): one-sided,
   flip-gated-at-extreme, hold-to-next-turn, maker-both-legs with taker fallback. Direction from the flip
   detector (`odcore/info_dipole.py` divergence / `odcore/flip_detector.py`) at a causal price extreme.
2. **Re-evaluate the SAME SOL trades** we walked through under the new logic (esp. the losers). Expectation:
   loser #1 (BID −9.98 at a peak) becomes a SHORT lifted at ~75.09, covered at the ~74.96 valley ≈ +16 bps.
   Re-render with `_render_trades.py` to confirm entries now sit short-at-peaks / long-at-valleys.
3. **Per-cell verdict** (sol/doge/xrp/eth, btc control), PROVISIONAL on one 11.7h window (small n).

## Validation questions (the honest gates)
- Does the flip/turn detector mark the extreme **causally and in time** (not late)? (S36b: 1-sec price
  reversal lands ~5-6 bps off the true turn — that is the budget.)
- Is there enough **climax/aggressor volume at the turn** to actually fill the passive quote? (S40 says yes
  — ~2x volume at the turn — but verify per cell; no climax → no fill → skip the turn or cross as taker.)
- **Round-trip net**: two maker legs (peak short + valley cover) ≈ swing size + 2x half-spread, vs the wrong
  -tail risk (flip's ~36% no-reversal: one-sided shorting into a continued rip). Gate tightly on
  flip + exhaustion/climax; cap inventory.
- Net must clear the S36b fee-floor logic: trade only swings ≳ 20 bps.

## Setup for the build session (data is gitignored, re-fetch)
Extract each cell's book to /tmp:
`for c in sol doge xrp eth btc; do git fetch origin data/$c-book; git show origin/data/$c-book:${c}_coinbase_book.jsonl.gz | gunzip > /tmp/${c}_coinbase_book.jsonl.gz; done`
Per-cell depth-K: btc=10, alts=1 (top-of-book). Branches: dev/push on s45-y2ni2m AND 5c5vg9 + -kb2i5c (synced).
