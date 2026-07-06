# SESSION HANDOFF — S66 (2026-07-06) — branch reconcile + E300 on DOGE/XRP + the BIG small-cap data pull (overnight)

Greg stopped for the night mid-session; this captures the durable state + what's collecting while away.
Read `STRATEGY_INVENTORY.md` (the new **S66 IN-PROGRESS** block at top) first.

## THE REORDER (Greg, load-bearing)
The capital model is BLOCKED until (a) ALL proposed improvement tests are run per-cell on **majors AND small
caps** (E300, bigline, S42 direction, divergence-filter, …), and (b) the **small caps are actually figured
out** — we've only ever worked the majors sleeve. So S66 ≠ "build the allocator"; S66 = complete the per-cell
test matrix + build out the small-cap universe FIRST. The allocator comes last, on the complete cell set.

## DONE THIS SESSION
1. **Branch reconciled.** `claude/davisai-s66-kickoff-4kjp87` was cut from a stale S59-infra parent (missing 320
   commits — the whole S38→S65 line). `reset --hard` to canonical S65 tip `5a2b537`; force-pushed; origin matches.
   Note: "canonical 5c5vg9" in the drop-ins is a SESSION LABEL, not a git SHA — the real canonical was
   `origin/claude/davisai-s65-kickoff-ia18ve`. Only loss: a stale `book_collector_btc.yml` (superseded).
2. **Confirmed the missing agent reads.** S65 landed only 2 COVERAGE audits (`PIECES_TEST_execution_kraken.md`,
   `PIECES_TEST_dipole.md`). The **dipole-EXPERT** deep read and the **ARCHITECT** read never landed. TODO S66.
3. **E300 death-selector on DOGE/XRP (Greg's directive) — RUN on Binance preview:**
   | coin | legs | AUC | base $/hr | 3piece | Δ | per-week Δ |
   |---|---|---|---|---|---|---|
   | DOGE | 512 | 0.685 | +0.63 | +1.32 | +0.69 | −0.4 +0.2 +1.6 +1.5 +0.7 (4/5 wk+) |
   | XRP | 785 | 0.768 | +1.10 | +3.08 | +1.98 | +5.0 +1.3 +0.9 −0.1 +6.1 (4/5 wk+) |
   AUC matches S62's 0.69–0.77 cross-coin. Driver = `scripts/_s66_e300_run.py {binance|kraken}` (drives
   `_s62_e300_3piece` **unmodified** — sim=live rule). **Kraken deploy-grade re-run auto-fires** when XRP tape lands.
4. **Answered "is Binance applicable for Kraken E300":** proxy for MAJORS signal-existence (AUC) only — prices
   arb'd (lag-0 synchrony). NOT deploy $/hr (kr_mk0 0bp / fill / spread / liquidity are Kraken-specific). For
   SMALL CAPS Binance is useless (most eligibles 404 on Binance; edge is Kraken low-liq microstructure).
   ⇒ every deploy-grade number runs on **Kraken tape**.

## DATA — the big unlock (no 30d wait)
- Kraken REST `Trades` = HISTORICAL backfill (`backfill_kraken_trades.py`, one pair, self-throttling backoff).
- Majors: **BTC+ETH already 27.7d** on box (`realbins/{btc,eth}_kraken_bins.json`). SOL/XRP/DOGE 30d pulling to
  `/tmp/ktape` (DOGE done; XRP/SOL ~55%). ⚠ Kraken REST DOGE = **XDGUSD** (legacy), BTC = **XBTUSD**.
- Small caps: **SECONDS each** (XDCUSD 30d = 34k trades = 4s).
- **The eligible universe is 352, not 6** — Kraken has **352 rebate-eligible (maker_deep = −2bp) USD alt pairs**
  (`/tmp/eligible_pairs.txt`), derived from AssetPairs `fees_maker` deepest tier < 0. S64's ~6 was a tiny slice.

## RUNNING WHILE AWAY (durable)
- **`scripts/_s66_overnight_collect.sh`** (PID launched, `nohup`, log `/tmp/overnight_collect.log`): pulls all
  352 eligible alts @ **120d** Kraken tape (par=4), gzips + commits every 20 pairs to the orphan data branch
  **`data/kraken-smallcap-tape`** → survives a container recycle; **resumable** (skips committed pairs). Absorbs
  SOL/XRP/DOGE majors at the end. 120d ≈ 17 weeks for the per-week+reversed gate (vs 5 on 30d).
  - ⚠ If the container recycled overnight, a fresh session just re-runs the same script — it resumes from the
    committed pairs on `data/kraken-smallcap-tape`.

## NEXT (S66 continue)
1. **Kraken E300 DOGE/XRP** (deploy-grade; auto-firing) — record vs the Binance preview.
2. **Materialize `data/kraken-smallcap-tape`** and run the full improvement-test matrix per-cell on the small-cap
   universe + majors: S54 gate (shuffle + reversed + per-week ×N), the KRAKEN lean zigzag stack, E300, bigline,
   S42 book-depth direction — PER-COIN law (keep where it works). This is the small-cap sleeve buildout.
3. **THEN** the $5k-pool anti-resting capital model on the COMPLETE cell set (majors + confirmed small caps).
4. **Get the dipole-EXPERT + ARCHITECT reads** (never landed in S65).
5. Resolve S64 "**RE**" pair identity (RED/REKT/RENDER/REN?).

## Files (S66): `scripts/_s66_e300_run.py`, `scripts/_s66_overnight_collect.sh`; branch `data/kraken-smallcap-tape`
(durable small-cap tape). Scratch: `/tmp/backfill` (Binance 30d), `/tmp/ktape` (Kraken majors 30d), `/tmp/ktape_sc`.
