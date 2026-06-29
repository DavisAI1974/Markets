# SESSION HANDOFF — S42 (2026-06-23) — LIQUIDITY DIVE: book imbalance is a real OOS next-move predictor + the QUIET FLOOR gate

Branch `claude/crypto-liquidity-signals-5c5vg9` (fast-forwarded onto the S41 tip — my S37 HEAD was a clean
ancestor of `crypto-backfill-validation-31tubb`, so all S38–S41 work merged with no divergence — then this
session on top; all pushed). Data + methods only.

## Data
- Book file `data/btc-book` branch -> `btc_coinbase_book.jsonl.gz`, extracted to `/tmp/book.jsonl.gz`
  (gitignored, same pattern as `realbins/`). **420,215 records, 100ms, 11.67h** (the full file is larger than
  the 5.83h S41 quoted), 3 gaps >1s. Per record: `ts, mid, spread, bids[[offset,size]×10], asks[…], buy, sell, n_trades`.
- Single cell only (btc_coinbase). Everything below is **CHARACTERIZATION, not deploy-grade** — per-cell rule
  needs multi-venue/multi-coin/multi-day book first (collector exists only for btc_coinbase; GHA needs Greg's click).

## Tools built + results

### `_liquidity_dive.py` — mine the liquidity layer (S41's only structured layer)
S41 missed two things: it used `abs_return` (magnitude) not SIGNED price, and never tested liquidity *dynamics*.
This adds signed return + depth-imbalance velocity / book withdrawal / one-sided depth, runs the agnostic 5-step
coupler (cross-slice) + an OOS exploitability readout. Channels (K=5 top depth): depth_imb, d_depth_imb,
d_total_depth, d_bid_depth, d_ask_depth, signed_ret, flow.

**PART B — exploitability (40% held-out test, circular-shift null, strictly-forward target):**
- **`depth_imb` (book imbalance LEVEL) predicts the SIGNED next move: OOS_r +0.164 next cell, null_z +60,
  63.1% directional hit.** Decays with horizon (+0.193/62% @0.5s; +0.118/55.5% @5s). Moves are sub-bp
  (0.06 bps next-cell -> 1.32 bps @5s).
- Two-sided xcorr: depth_imb **LEADS price by +0.1s** (cc +0.134), lead side > lag side -> genuinely
  predictive, the canonical top-of-book-imbalance next-tick signal recovered OOS.
- **`d_total_depth` (symmetric withdrawal) is NULL for direction** (r~0.00). Directional content is in the
  IMBALANCE, not total depth. `d_bid_depth` (+), `d_ask_depth` (−) are symmetric one-sided echoes. `flow`
  has mild signed content (+0.069/57%) but is dominated by depth_imb.
- Net-of-cost: sub-bp << Coinbase ~50–80 bps round-trip -> a **MAKER/quoting signal**, below the active fee floor.

**PART A — agnostic 5-step coupler (score_pair, all 5 steps + circular-shift tautology null), 10 slices:**
- **depth_imb~signed_ret survives the null in 7/10 slices, LEADS +0.08s** — a stable property, NOT S41's
  single-window fluke. d_depth_imb~signed_ret 5/10. Flow→price weak (≤4/10, low z). Liquidity↔liquidity
  mega-z pairs are mechanical (derivative vs its components), no tradeable content.

### `_quiet_floor.py` + `odcore/quiet_floor.py` — the QUIET FLOOR gate (Greg's directive on Chat's OD run)
Chat's run: book imbalance obeys a clean AR(1) RELAXATION, quiet/still between trades. Reproduced:
**φ_quiet=0.944** (Chat 0.947), quiet OOS-R2 0.76 > trade 0.62. Greg: use the quiet operator as a FLOOR so the
dipole stops firing while trend-following.
- Floor `floor_hat=φ_q·imb(t-1)+c_q`; innovation `innov=imb-floor_hat` absorbs the between-trade relaxation
  (std 0.15 quiet vs 0.22 trade; raw level 0.38 in both).
- Direction lives in the LEVEL — innovation alone dilutes next-cell hit 61.6→57.4%. So **use the floor as a
  GATE**: fire only when `|innov|>k·σ` (imbalance breaks the floor = a shock). At k=1.5σ the gate opens **7%
  on quiet cells vs 16% on trade cells (2.3×)** — silent between trades, fires on shocks — and gated direction
  (sign of level) keeps **62% hit** (k=2σ → 62.7%). Raw level holds "on" ~15% of all cells continuously (the
  churn). **Between-trade firing cut, direction kept.**
- `odcore/quiet_floor.py`: portable, leakage-safe `QuietFloor` (fits φ_q + gate σ on TRAIN quiet cells only),
  causal `floor_hat/innovation/gate/gated_signal`. Fit one per cell.

## Files / commits
`_liquidity_dive.py`, `_liquidity_dive_partA.json`, `_liquidity_dive_partB.json`, `_quiet_floor.py`,
`_quiet_floor_results.json`, `odcore/quiet_floor.py`, `S42_LIQUIDITY_DIVE_FINDINGS.md`.
Commits 64aa422 (PART B + causality), 1f3022d (quiet floor), 7185c98 (PART A).

## NEXT (S43) — see `KICKOFF_2026-06-23_S43.md`
1. More book data (the bottleneck): GHA `book_collector_btc.yml` needs Greg's manual run; add other
   venues/coins. Re-run `_liquidity_dive.py` + fit `QuietFloor` per cell once multi-cell book exists.
2. Maker-fill / queue model to turn the 63% next-cell signal into a net-of-rebate quoting edge (the realistic
   monetization of a sub-bp predictor).
3. Wire the QuietFloor gate into the live dipole path (gate = when to fire; level = direction).
