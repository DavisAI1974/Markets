# SESSION HANDOFF — S51 (2026-07-02) — rebate lever quantified (super-linear); Bybit venue picked + book crons LIVE; v2 queue-honest fill model; scale-in probed (one-shot survives); 4x pipeline speedup; ⚠ no single "$X/hr ceiling" — the number is a MATRIX

Branch: designated `claude/crypto-liquidity-signals-s51-n9qblw` == canonical `5c5vg9` (synced every push).
Read `S51_REBATE_FINDINGS.md` (the full results) + `KICKOFF_2026-07-03_S52.md` (next session). Books load from
`/tmp/<coin>_coinbase_book.jsonl.gz`; NEW venue books accrue on `data/{sol,eth}-bybit-book`.

## ⚠ STANDING CORRECTION (Greg, session close — carry this into every future doc)
**Do NOT quote "$18/hr" (or any single number) as THE ceiling.** That figure is ONE CELL of a matrix:
{Coinbase, mk0, FLAT sizing, v1 fill, one window}. The same legs read differently across the measured axes:
SIZED at deploy sizes (+8–21% over flat), maker −1 bp (+$71/hr v1 ceiling), −2 bp + wider book (+$142),
v2 queue-honest (−$7 worst-case mk0 → +$20 at −1 bp), scale-in variants under rebate (+$18–43/hr @$1k cap),
and ALL of it is pre-Bybit (10x tape). The honest statement is the MATRIX + which cell you're citing.
**Greg's follow-up concern (S52 Job 1): the $/hr projections may still under-credit SIZING-ON-WINNERS —
make that accounting airtight before citing any per-scenario $/hr as final.**

## What S51 did
### Job 0 — reconcile + paper run
Designated branch reset to canonical `5c5vg9` (only a default-branch cron commit differed). `paper_trade.py`
ran clean: +0 new trades (no new book window yet), ledger 25,845 across all runs; **sized_net > flat_net on
ALL 5 cells forward** (sol +9,225 flat → +10,705 sized; the sizing lift is real OOS, not backtest-only).

### Job 1 — the rebate lever, measured (super-linear, not linear)
`scripts/_capacity_model.py` extended to scenario sweep (maker 0/−1/−2 bps × spread 1.0/1.5x) over the SAME
real legs (leg indices are fee/spread-independent → channels build once, executor re-runs per scenario; flat
vs SIZED at every scenario). SOL sized v1 numbers: mk0 +$18/hr → **−1 bp +$71 (3.9x)** → −2 bp +$124 → −2 bp
+ 1.5x spread +$142. Super-linear because the rebate FLIPS losing legs positive, not just scales winners.
**Rebate × sizing hypothesis (S50) CORRECTED:** the sizing lift SHRINKS in % under a rebate (SOL +21%→+8%;
uniform per-leg add lifts the flat baseline) and →0 at the flow-capped ceiling (sizing can't buy more flow).
Sizing stays ON (it compounds at deploy sizes; forward ledger +16% on SOL) — see the S52 Job-1 caveat above.

### Job 2 — venue shortlist (primary sources) + Greg's TOTAL-$/hr frame
Agent-verified from official docs: **Bybit MM Incentive Program = the reachable rebate** (−0.1 to −1.25 bps,
qualifies on MAKER SHARE ≥0.03% weighted — an EMAIL APPLICATION, not a volume wall; institutional_services@
bybit.com, 1-month trial). **Backpack** second (SOL-native, MM5 first month + $300k/mo pool; exact bps
image-locked — confirm with vip@backpack.exchange). Gate/KuCoin = $30–50M walls; Binance/OKX/Deribit/dYdX/
Hyperliquid unreachable small; **Bitfinex = zero-fee but NO rebate**.
**Greg (load-bearing): maximize OUR $/hr — rebate size and venue volume are only inputs.** Measured (venues'
own APIs): SOL tape Bybit ~$47M/hr vs Coinbase ~$4.7M/hr (10x) vs Backpack ~$1M vs Bitfinex ~$0.05M (flow-
dead: best per-trade economics, worst per-hour — zero-fee + 6.6 bps spread but our wall ~$2/hr). ETH: Bybit
~$111M/hr (10x Coinbase). **Bybit's standard maker is +2 bps = our edge NEGATIVE → the MM program is the
VIABILITY GATE on Bybit, not a nice-to-have; past it, the 10x tape is the money.** Bybit REST is CloudFront-
geoblocked from some DCs; WS works everywhere we run (collector is WS-only).

### Job 3 — Bybit venue books COLLECTING (the decisive data)
`bybit_book_collector.py` (new, on 5c5vg9): v5 linear-perp L2, SAME row schema as the Coinbase collector →
the whole pipeline reads venue books unchanged. Smoke-tested LIVE (584 rows/60s, 0 reconnects; SOLUSDT median
spread 1.24 bps vs Coinbase 1.36). `bybit_book_collectors_durable.yml` pushed to the DEFAULT branch (Greg-
approved; cron 0 */6, SOL+ETH → `data/{sol,eth}-bybit-book`, same anti-clobber guardrail).

### Job 4 — v2 QUEUE-HONEST fill model (wired into `_capacity_model.py`)
`_leg_caps` now returns (v1 front-of-queue, v2 back-of-queue = window flow MINUS the best-level size resting
ahead). v1/v2 = the truth bracket (we post at the turn: improving the book = front, joining a level = back).
**v2: at mk0 the strategy does NOT print worst-case (4/5 cells' v2 ceilings NEGATIVE); a −1 bp rebate flips
every cell positive; queue-honesty favors DEEP books — ETH overtakes SOL (44% legs fillable vs 20%; −2 bp v2
ceiling +$92 vs +$46).** So collect/compare BOTH on Bybit (done — both in the cron).

### Job 5 — per-leg size cap: FALSIFIED on the forward ledger (no change)
Cap ∈ {1..4} × {mk0, +1bp} on 25,845 multi-window trades, matched-capital: net rises MONOTONICALLY to the
existing `hi_clip=4.0` on sol/eth/btc (doge/xrp peak earlier by ~1% noise). Tightening LOSES money; the
loaded-up legs are net-positive in aggregate. `hi_clip=4.0` IS the validated cap.

### Greg's scale-in / one-legged picture — probed hard, executor VALIDATED
Greg described the strategy; two probes tested the scale-in reading (accumulate along the slide):
- `scripts/_scale_in_probe.py`: **mechanism falsified — LOSERS soak ~2x the opposing flow of winners** (SOL
  med $6.7k vs $3.6k; the S45 adverse-selection autopsy re-confirmed). Big naive $ at large caps carried
  inventory 4–20x the exit-turn flow = mark-to-close fiction.
- `scripts/_inventory_sim.py` (the faithful netting version — the flatten IS the next leg's entry): mk0
  ~break-even/negative; −1 bp prints (+$18–87/hr); **but the REVERSED-SIDE CONTROL beats conviction on SOL
  at mk0** → the front-of-queue class rewards fill VOLUME, not signal — cannot validate the variant. Re-test
  ONLY on the venue book with the queue-aware model (S52+, after data accrues).
- **Clarified with Greg: the deployed executor IS his one-legged design** (verified on 5,376 SOL legs: 0
  overlapping legs; off-side never shown; median entry 0.69 bps / 1.6s from the turn; 99.8% maker closes;
  97% side alternation). The probes are evidence FOR the design — deviations tested worse.

### Pipeline speedup — 4x per cell, verified BIT-IDENTICAL (money-neutral)
Each cell was parsing the gzip book 3x (+ 8 np.sum/row). `load_book` rewritten (sequential prefix K<8 —
bit-identical below numpy's pairwise threshold; np.sum kept at K=10; captures `spread`); `build_channels`/
`median_spread_bps` take `raw=` to reuse ONE parse; both deploy callers updated. **Old-vs-new (worktree at
efd646b): doge 1,865 + sol 5,376 trades, 0 differing fields. 142.7s → 39.5s per cell.**

## Git / state
Commits (both branches synced each push): `ed81849` (rebate sweep + speedup + venue shortlist),
`af3c592` (v2 fill + size-cap falsification), `6758f7e` (bybit collector), `4ffd792` (scale-in probes +
findings), + this close-out. Default branch got `5299f53` (bybit book cron; Greg-approved push).
Results JSONs: `_capacity_model_results.json`, `_scale_in_probe_results.json`, `_inventory_sim_results*.json`.

## NEXT (S52) — see `KICKOFF_2026-07-03_S52.md`
1. **JOB 1 (Greg): the SIZING-ON-WINNERS accounting** — reconcile every $/hr projection with the sizing lift
   at each capacity level/scenario; investigate winner-side sizing beyond entry-conviction (post-entry
   confirmation adds, market-delivered size) — leakage-gated, forward-ledger-evaluated, never one-window.
2. Bybit book: first windows land within ~6–12h of session close → run the FULL stack per venue-cell
   (spread, turn structure, v1/v2 capacity, netting sim under the reachable rebate).
3. Greg: send the Bybit MM application (+ Backpack VIP email).
