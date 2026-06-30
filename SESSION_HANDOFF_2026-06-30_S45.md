# SESSION HANDOFF — S45 (2026-06-30) — the decisive maker test ran on the multi-coin book: per-cell operators flip DOGE NET+, fill autopsy pins the bleed on adverse selection, and the validated dipole FLIP detector is NOT wired into the maker path (the fix)

Branch note (see "Branches" below): worked on `claude/crypto-liquidity-signals-s45-y2ni2m` (the harness-assigned
branch — it was stale S37 + 3 default-branch collector commits; merged canonical `5c5vg9` in). Pushed S45 work
to that branch AND fast-forwarded `5c5vg9` + `5c5vg9-kb2i5c` to the same tip so the canonical line the handoffs
track stays current and synced. Greg's calls this session: "do what you feel is best about the branches"; Chat
takes the per-coin OD run; "dissect the firing trades — this is a fixable problem"; render the 10 trades in the
swing-diagram style; "the dipole flip is nailed — are we using it?"

## THE DECISIVE TEST RAN (NEXT #2) — multi-coin book accrued, `_maker_deploy_map.py` on all 5 cells
- **Data:** the book-collector cron pushed the alt branches at ~23:30 UTC 2026-06-29: `data/{eth,sol,doge,xrp}-book`
  each ~420k rows = **11.7h @ 100ms** (btc-book = 46.7h control). Re-extract: `git show origin/data/<coin>-book:<coin>_coinbase_book.jsonl.gz | gunzip > /tmp/<coin>_coinbase_book.jsonl.gz`. NOTE the GHA collector only
  commits at the END of its ~5h50m run (no mid-run partials); the 6h cron self-sustains accrual.
- **Result 1 — btc-locked operator (K=10) does NOT transfer.** First run (global K=10) returned ALL cells `rebate`
  (gross/fill < 0 before rebate): sol −0.45, doge −0.65, xrp −0.45, eth −0.32. The S44 prediction (SOL half-spread
  ~0.7 bps ≫ ~0.5 bps adverse selection → NET+) did **not** hold at the btc operator. NOT a kill — the btc operator
  failing to transfer is the per-cell signal to find each coin's own operator (Greg, S45).
- **Result 2 — PER-CELL operator (the fix). `_gate_param_sweep.py` per coin: the thin alt books carry their
  depth-imbalance signal at TOP-OF-BOOK (K=1), not the deep K=10 btc wants.** Re-ran the deploy map with per-cell K
  (`PER_CELL_K` now in `_maker_deploy_map.py`; btc=10, alts=1; gate k held at the locked 1.5 to avoid over-tuning a
  single 11.7h window):

  ```
  cell            K   hrs  half_sp gated_hit  fav-anti gate_gross  verdict
  btc_coinbase   10  46.7   0.0008     70.9%    0.0509    -0.3734   rebate
  eth_coinbase    1  11.7   0.0316     67.0%    0.1036    -0.2600   rebate
  sol_coinbase    1  11.7   0.6700     80.8%    0.2034    -0.2978   rebate
  doge_coinbase   1  11.7   0.6908     73.8%    0.4169    +0.0372   NET+
  xrp_coinbase    1  11.7   0.4736     79.1%    0.0785    -0.2049   rebate
  ```

  Per-cell K=1 jumped the direction hit (sol 62→**81%**, xrp 61→**79%**), turned the side-filter edge positive
  (sol fav−anti −0.02→**+0.20**, doge −0.05→**+0.42**), and **flipped DOGE to NET+ before any rebate (+0.037)** —
  the existence proof that a wide-spread cell can clear with its OWN operator. sol/xrp/eth improved but stay just
  negative (within a maker rebate of breakeven; Coinbase doesn't pay one — other venues do). **PROVISIONAL: one
  11.7h window per alt, small fill counts (doge 55, sol 169, xrp 177, eth 887). Do NOT size off this — confirm as
  the book accrues + on a 2nd window.**

## FILL AUTOPSY (`_dissect_fills.py`) — WHY the fills bleed (Greg: "dissect the firing trades")
- **PnL identity (maker_book.py:99-108):** `gross/fill = half_spread + drift`, where
  `drift = signed(mid[exit] − mid[post]) = d_wait (post→fill) + d_hold (fill→hold)`, signed in our direction.
- **SOL aggregate (169 fills, K=1):** half_spread **+0.67**, mean drift **−0.97** (d_wait **−0.93**, d_hold −0.04)
  → mean gross **−0.30**. Mid moved AGAINST us on **58.6%** of fills; median queue wait 5 cells (500ms). Same
  mechanism every cell: eth gross −0.26 (half_sp only 0.03 — no spread, like btc), doge **+0.04**, xrp −0.20.
- **ROOT CAUSE = adverse selection, and it lives in the QUEUE WAIT, not the hold.** A passive quote only fills when
  flow is against it: a bid fills *because* sellers press → the mid is dropping while you queue → d_wait is
  structurally negative. The 0.67 bps half-spread is real but the average adverse move during the ~500ms wait
  (−0.93) is bigger. **The gate fires on an imbalance SHOCK, but a shock is EITHER a turn (the valley/peak) OR a
  trend-continuation (a falling knife). The current operator can't tell them apart, so it quotes into both.** The
  losers are the continuations; the winners are the genuine turns.
- **Renders:** `_render_trades.py` draws the 10 sampled SOL fills in Greg's swing-diagram style (`_render_trades_<coin>.png`, gitignored). All 5 losers are "Buy long" posted at the top of a cliff (bought into a downtrend);
  the +15 bps winner is "Sell short" at a peak that rolls over. Visual confirmation of the autopsy.

## THE FIX (Greg: "we have the dipole flip nailed — are we using it?") — NO, WE ARE NOT
- **Checked the code:** the maker path (`_maker_deploy_map.py`, `odcore/maker_book.py`, `_gate_param_sweep.py`)
  imports ONLY `quiet_floor.gated_signal` (the imbalance-shock gate). The validated S36 FLIP detector
  (`odcore/flip_detector.py`, `odcore/info_dipole.py` divergence+exhaustion, 64% reversal, leakage-PASS) is **not
  imported anywhere in the maker path.** `odcore/incremental.py` only mentions `info_dipole.divergence` in a COMMENT.
- **So the maker quotes on a shock gate that can't tell a turn from a falling knife — exactly the bleed the autopsy
  shows.** THE FIX (per-cell wiring, not new research): gate the maker quote on the FLIP/turn detector — post the
  bid only at a detected valley/flip, the ask only at a peak/flip — so adverse "bought-on-the-way-down" fills become
  favorable "bought-at-the-bottom" fills. This is the S36 trend-continuation-vs-FLIP read applied to the quote
  decision. doge already cleared on depth-K alone; the flip gate is the lever to pull sol/xrp/eth over too.

## NEXT (priority)
1. **WIRE THE FLIP DETECTOR INTO THE MAKER GATE.** Replace/AND the QuietFloor shock gate with
   `info_dipole.divergence` / `flip_detector` so we only quote at turns. Re-run `_maker_deploy_map.py` per cell;
   target: sol/xrp/eth join doge at NET+ (or NET+ after a venue rebate). Add the flip gate as a `dipole_gated`-style
   arm in `maker_book`/the deploy map. This is the decisive deploy lever now.
2. **Per-coin OD run (Chat).** Derive each coin's own operator for TURN/reversal prediction (the fill-toxicity
   signal), not just direction. Default `research/od_book/run_experiment.py` is VAL-only and SAFE; only
   `--commit-ttest` is locked and the btc sentinel (`.ttest_committed.json`, data_hash 7d69fda…, taker KILL) is
   FROZEN — do NOT delete it, and that taker T_test does not bear on the maker thread.
3. **Confirm per-cell K=1 + the NET+ on a 2nd window** as the book accrues (current alts are one 11.7h window; doge
   only 55 fills). Each alt nears the 100 MiB push cap in ~4-5 days → off-git/sharded storage (blocked on cloud auth).
4. **Lock per-cell operating points into the QuietFloor registry** (`odcore/quiet_registry.py`,
   `_wire_quiet_gate_book.py --write-registry`) once the flip-gated map is validated, then wire into the production
   emit path (NEXT #5).

## Branches (Greg: "do what you feel is best; note it for the next guy")
- Harness landed on `claude/crypto-liquidity-signals-s45-y2ni2m` = stale S37 (`7256abd`) + 3 default-branch
  collector-workflow commits. Merged canonical `5c5vg9` (`a25f619`) in (one trivial workflow-comment conflict,
  took the default-branch version). **S45 work pushed to `s45-y2ni2m` AND `5c5vg9` + `5c5vg9-kb2i5c`
  fast-forwarded to the same tip + pushed**, so all three are unified and the canonical line stays current
  regardless of where the next harness lands. Default branch (`new-session-o3vnm`) carries the cron'd collector
  workflows — leave it. If a future harness lands on stale S37 again, `git merge --ff-only origin/claude/crypto-liquidity-signals-5c5vg9` first (or merge if diverged, as this session did).

## Files (S45)
- `_dissect_fills.py` NEW (per-fill autopsy; `python _dissect_fills.py <coin> [K] [kgate]`), `_dissect_fills_sol.txt`.
- `_render_trades.py` NEW (swing-diagram renders; PNGs gitignored).
- `_maker_deploy_map.py` MODIFIED — `PER_CELL_K` operator map + per-cell K in the table/results.
- `_gate_param_sweep_results.json`, `_maker_deploy_map_results.json` refreshed (last run = the per-cell-K map).
- Discipline: OD-BOOK sentinel untouched. All results PROVISIONAL on one 11.7h window per alt.

## S45 ADDENDUM — the flip filter was wired BACKWARDS; CONFIRMING (continuation) polarity clears sol/doge/xrp NET+
- **Built the floor+flip combination (`_maker_flip_floor.py`).** First cut gated on `opposing` (book leans
  AGAINST the recent price move = the S36 reversal condition, `aligned = depth_imb*sign(price_drift) < 0`).
  It made the maker WORSE everywhere (sol −0.30→−0.86, doge +0.04→−0.33). Hold sweep (`_hold_sweep.py`) did
  not rescue it; reversing the direction (`_revtest`, deleted) lost on every cell (follow ≫ fade) — so the
  signal is NOT direction-reversed.
- **`_flip_debug.py` found the bug (Greg: "it's how we code it").** Splitting gated test fills by condition
  (sol): `confirming` (aligned>0) gross **+0.745** (d_wait −0.09) vs `opposing` gross −0.863 (d_wait −1.43);
  `confirm+exhaust` **+0.908**. CONFIRMING beats OPPOSING on ALL 4 cells. **The S36 flip detector predicts
  REVERSALS — a TAKER concept; a MAKER with queue priority can't get a clean fill at the turn (the turn fill
  IS the flush), it earns by providing liquidity WITH the flow (buy dips in uptrends).** So the detector is
  right, we pointed it the wrong way. Direction stays `sign(imb)`; only the flip POLARITY flips.
- **Corrected result (floor + flip=CONFIRMING [+ exhaustion], per-cell K=1, gross/fill before rebate, PROVISIONAL
  one 11.7h window, small n):** sol +0.75 (exhaust +0.91, n=33), xrp +0.14, doge +0.12 (exhaust), eth −0.20
  (0.03 bps half-spread — structurally rebate-only). 3/4 wide-spread alts clear NET+.
- **NEXT (revised #1):** flip `_maker_flip_floor.py` to the CONFIRMING polarity (`aligned>0`), add the exhaustion
  factor, re-run the deploy map, and CONFIRM on a 2nd window as the book accrues (fill counts are tiny: sol
  n=33–52, doge n=13–22). Then wire floor + confirming-flip into the production emit path. The maker edge here
  is trend-CONTINUATION liquidity provision, not swing-reversal.
- Files: `_maker_flip_floor.py` (opposing version — flip to confirming), `_flip_debug.py` (the per-condition
  autopsy), `_hold_sweep.py`, `_render_trades.py` (+`confirm`/`opposing` modes). Renders gitignored.

## S45 FINAL — THE STRATEGY (supersedes "flip to confirming"): MAKER-AT-THE-TURN / asymmetric conviction quoting
The confirm-vs-opposing result was for a SYMMETRIC hold=1 maker. Walking the losers one-by-one (`_render_one.py`)
with Greg surfaced the real strategy, a different execution model entirely. Full spec:
`STRATEGY_maker_at_the_turn_S45.md`. In brief:
- A symmetric two-sided passive maker is at the counterparty's mercy — mid-trend you are the adversely-selected
  victim (loser #1: posted a BID at a peak, filled by the sell flush, −9.98 bps).
- **Be a maker ONLY at the turns, ONE-SIDED, skewing the quote with the alpha:** at a PEAK (flip=top) post the
  best OFFER + pull the bid → euphoric buyers lift it → SHORT the top (maker, +spread); ride down keeping the
  best offer, bid PULLED (never catch the knife); at the VALLEY (flip=bottom) post the best BID + pull the offer
  → capitulation sellers hit it → cover the bottom (maker). BOTH legs maker; the S40 climax aggressor (~2x vol AT
  the turn) is the adversely-selected victim on both ends; you never cross the spread (taker only as fallback).
- Loser #1 under this logic: post the OFFER at the peak → short ~75.09 → cover at the ~74.96 valley ≈ **+16 bps**
  instead of −9.98. Same instant, same book, correct execution.
- **S46 BUILD = wire it** (new `odcore/swing_maker.py` or extend `maker_book.py`): position state machine
  {flat,short,long}; one-sided quoting that swaps sides at each flip; direction from the flip detector at a causal
  price extreme; hold to the NEXT turn; maker-both-legs + taker fallback. Then re-evaluate the SAME SOL losers
  (expect them to invert) and produce the per-cell verdict. Validation gates in the spec (flip marks the extreme
  in time? enough climax volume to fill the passive quote? round-trip net of two maker legs vs the flip's ~36%
  wrong-tail; trade only swings ≳ 20 bps per the S36b fee floor). PROVISIONAL on one 11.7h window — confirm as the
  book accrues.
- Renders for the build are committed in `docs/renders/` (`_render_trades_sol_{floor,confirm,opposing}.png`,
  `_loser_sol_floor_0.png`) — gitignore overridden so any session has them.
