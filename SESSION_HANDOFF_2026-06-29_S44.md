# SESSION HANDOFF — S44 (2026-06-29) — multi-coin book collectors + QuietFloor gate wired into the live dipole

Branch: dev/push on `claude/crypto-liquidity-signals-5c5vg9-kb2i5c` (harness-designated; was stale at S37
`7256abd`, fast-forwarded to the canonical S43 tip `30d2425`) AND `claude/crypto-liquidity-signals-5c5vg9`
(canonical, per the drop-in). Greg's S44 call: **"do multi coin then wire quiet floor."**

## What ran (NEXT #1 then NEXT #4, in that order)

### NEXT #1 — multi-venue/multi-coin BOOK collectors (THE bottleneck)
The book existed for btc_coinbase only, and the S43 maker model is SPREAD-STARVED there (1-tick book,
half-spread ~0.0008 bps → no spread to pay for adverse selection). The fix that unblocks NEXT #2/#3 is
more cells, especially WIDER-spread ones.

- `coinbase_book_collector.py` — symbol-parameterized generalization of `coinbase_btcusd_book_collector.py`.
  Identical WS protocol (`level2_batch` + `matches`) and row schema; takes `--product` + `--out`. The old
  collector is kept (only doc-referenced; both write the same schema).
- `.github/workflows/book_collectors_durable.yml` — ONE matrix workflow over **btc/eth/sol/doge/xrp** on
  Coinbase, each persisting to its own `data/<coin>-book` branch via orphan force-push with the gz
  anti-clobber guardrail (copied from the trade-bin collectors). btc keeps the SAME file
  (`btc_coinbase_book.jsonl.gz`) + branch (`data/btc-book`), and the guardrail protects the existing 1.68M
  rows from any partial-run regression.
- **DELETED `book_collector_btc.yml`** — it collected btc only, its checkout `ref:` pointed at the now-dead
  branch `claude/divergence-exhaustion-backtest-wj65sm`, and keeping it would double-push `data/btc-book`
  (race). The matrix supersedes it.
- **Live smoke-test (18s, SOL-USD):** 170 rows @100ms, correct schema, **median half-spread ≈ 0.69 bps vs
  BTC's 0.0008 bps (~860× wider).** This is the whole point: SOL/DOGE/XRP are the wider-spread cells where
  half-spread (2–5 bps) ≫ adverse selection (~0.5 bps), so the gated signal-as-filter should clear net.

**BLOCKER (unchanged): needs Greg's manual GHA trigger.** The session token 403s on `workflow_dispatch`.
Greg: GitHub → Actions → **"Book Collectors (BTC/ETH/SOL/DOGE/XRP, durable)"** → Run workflow on branch
`claude/crypto-liquidity-signals-5c5vg9`. Data accrual is the ONLY remaining gate on the decisive
per-cell maker test (NEXT #2).

### NEXT #4 — QuietFloor gate wired into the live dipole (per cell, leakage-safe, hot-path-ready)
- `odcore/incremental.py`: **`IncrementalQuietGate`** — causal O(1)/tick port of
  `odcore.quiet_floor.QuietFloor` (holds fitted phi/c/sigma + the previous imbalance; reproduces the batch
  gate one tick at a time, no look-ahead). `RollingFlow` now takes an optional `gate=` and exposes
  `gated_signal()` — the live turn-detector with the floor wired in. Backward-compatible (gate opt-in).
- `odcore/generators.py`: **`dipole_gated`** registered in `SIGNALS` (fit QuietFloor on the train slice's
  quiet cells, apply causal gate, return sign(level) where open else 0).
- `_wire_quiet_gate_book.py`: per-cell production driver — builds the live book-depth dipole, gates it,
  reports churn/selectivity/direction, and proves the hot-path gate matches batch on real data.
- `_canary_quiet_gate.py`: leakage/causality/bit-faithfulness canary (PASS).

**CANARY FINDING (load-bearing — drove the channel choice):** on TRADE-flow ofi the 'quiet' cells have
zero flow by construction → the QuietFloor degenerates (phi≈0) → gating is a near-no-op (2% churn cut).
The relaxation edge is in the resting-size **book DEPTH imbalance**, which is non-zero and slowly relaxes
between trades (phi_q≈0.95). So the gate is wired on the depth channel; the generic hot-path hooks
(`IncrementalQuietGate`/`RollingFlow.gated_signal`) are ready for whatever imbalance series production
feeds them.

**Result on btc_coinbase book (1.68M cells, 46.7h, K=10, k=1.5, train 60%):**
| metric | value | reading |
|---|---|---|
| QuietFloor | phi=0.935, c≈0, sigma=0.160, r2_quiet=0.936 | real AR(1) relaxation (matches S42/Chat 0.947) |
| churn | raw level fires 100% → gated **6.9%** | stands aside 93% of the time — stops churning through trends |
| selectivity | gate open 4.9% quiet vs 12.3% trade = **2.54×** | fires on shocks, not the smooth relaxation (S42 ~2.3×) |
| direction (OOS next-cell hit) | raw 69.8% → **gated 70.9%** | fewer trades, level's direction retained/sharpened |
| hot path | IncrementalQuietGate vs batch = **0/1,682,107 mismatches** | the live O(1)/tick gate is bit-faithful |

Deploy form: **gate = WHEN to fire, imbalance level sign = DIRECTION.** Per cell
(`deploy-signal-per-cell-not-universal`); ready to fit+apply across venues as the multi-venue book accrues.

## Discipline / state
- OD-BOOK `.ttest_committed.json` sentinel UNTOUCHED — the taker KILL stays frozen.
- `_canary_incremental.py` still PASS (RollingFlow change is backward-compatible).
- Re-extract book: `git show origin/data/btc-book:btc_coinbase_book.jsonl.gz | gunzip > /tmp/od_book.jsonl.gz`
  (fetch `data/btc-book` first). Per-tick loops over 1.68M rows take a few min — run patiently.

## NEXT (priority)
1. **Greg: trigger the book matrix** (manual GHA) so eth/sol/doge/xrp book accrues. Everything below gates on it.
2. **Re-run `_maker_fill_model.py` PER CELL on a wider-spread alt (SOL/DOGE/XRP)** — the decisive deploy
   test the maker model was built for (half-spread should now pay for adverse selection).
3. **Re-run `_wire_quiet_gate_book.py` + fit `QuietFloor` PER CELL across venues**; confirm the gate's
   churn-cut + retained-direction hold beyond btc_coinbase.
4. Wire `RollingFlow.gated_signal()` / `dipole_gated` into the production emit path once a per-cell deploy
   map exists (the gate is built + canaried; it just needs the per-cell QuietFloor coefficients).
5. OD-BOOK threads 2/3 stay NOT built (gate held). Cross-domain falsification still open.
