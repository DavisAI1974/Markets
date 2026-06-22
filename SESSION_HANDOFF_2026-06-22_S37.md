# SESSION HANDOFF — S37 (2026-06-22) — git/branch fix + data-pipeline UNBLOCKED (5 coins x 3 venues) + NEXT #2 gated swing challenger + OD-BOOK thread

Branch `claude/divergence-exhaustion-backtest-wj65sm` (PUSHED; now == repo default). Continues S36b. All
S35/S36 memories apply: crypto platform only; zero synthetic; per-cell deploy; git is source of truth;
`tools-are-complementary-not-competing`; never tune off a single window.

## THE BIG UNBLOCK THIS SESSION: the in-git data pipeline was BROKEN; now fixed + expanded to 5 coins
The whole S36b bottleneck ("can't validate a near-breakeven swing strategy on ONE 1-sec window") had a
concrete cause nobody had diagnosed: **the durable collectors stalled ~06-14/06-19**. Root cause (from the
failed GHA run logs): `btc_coinbase_bins.json` grew to **103 MB > GitHub's 100 MiB/file push limit**, so
every collector run collected fine but the **push was rejected** -> no new bins landed. Fixed two ways:
1. **Gzip the bins on the data branch** (`btc/eth_collectors_durable.yml`): store `<f>.json.gz` (104 MB ->
   16 MB, 6.4x, verified), gunzip on restore, gzip on push, gz-aware anti-clobber guardrail; collectors +
   loaders still use raw `.json` locally (legacy-raw fallback handles the one-time migration). Buys ~6 weeks
   of runway. BTC/ETH resume on their next 6h cron.
2. **Added the other 3 coins (SOL, DOGE, XRP) x 3 venues** — the "5 assets x 3 venues" set Greg runs
   box-side, now durable in git. Generic symbol-parameterized collectors `coinbase_collector.py` /
   `kraken_collector.py` / `bybit_perp_collector.py` (--product/--symbol, backward-compatible, exact BTC/ETH
   bin schema) + a matrix workflow `alt_collectors_durable.yml` (one job per coin -> own `data/<coin>-bins`
   branch, **gzip from day one**). Live-validated; **caught the Kraken DOGE symbol** = `DOGE/USD` on v2 (NOT
   the legacy `XDG`, which returns nothing). First run launched (in_progress at handoff).
- **Net effect: 5 coins x 3 venues = 15 cells are accruing again.** As multi-window/multi-regime data builds
  (hours -> days), the gated-swing strategy can finally be validated across many windows/cells instead of
  overfitting one. THIS was the gating resource the whole S36b thread was waiting on.
- **Durable long-term storage:** gzip is a ~6-week band-aid; the real answer is off-git storage (S3 / Render
  disk). Blocked on cloud auth (see Infra below).

## NEXT #2 DONE — the unified GATED SWING challenger (per-cell STACK, not a bake-off)
`_info_dipole_gated_swing.py` -> `_info_dipole_gated_swing_results.json`. Per Greg's "not a true competition,
use where each is good": composes the pieces by what each is good at, **per cell** — TIMING = the 1-sec
price-reversal trigger (`candidates`), FILTER = the OD dipole `divergence()` (the 64% read), STAND-ASIDE =
the regime gate (ER/C), COST = the maker floor. **MANDATORY `assert_no_leakage` gate runs first (PASS 6/6).**
Per-cell deploy decision: pick the config {un-gated | ER-gated | C-gated} that clears net>0 at maker with
enough real trades (the degenerate failure is NO trades, not low recall — the regime gate legitimately
trades less, so we must NOT reject low recall; THIN flag for low coverage).

PROVISIONAL on the single in-git 1-sec window (reproduces S36b numbers exactly -> faithful composition):
| cell | deploy |
|---|---|
| btc_kraken | dipole un-gated **+466** (recall 0.447) |
| eth_coinbase | dipole un-gated **+392** (recall 0.151) |
| eth_bybit_perp | dipole un-gated **+670** (recall 0.073 — THIN) |
| btc_bybit_perp | **C-gate stand-aside +16** (the regime gate rescuing the bleeder -173->+16, THIN) |
| btc_coinbase / eth_kraken | stand aside |
4/6 clear. The stack earns each piece per cell. **DO NOT size off this one window** — re-run on the accruing
multi-regime/multi-coin data (now flowing) for the real per-cell deploy map.

## OD-BOOK thread (Chat/Architect's order-book dynamics operator) — built, parked, collecting
Chat's spec (`EXP_book_dynamics_operator_1.md`): use OD as a *dynamics recoverer* (recover the book's
forward operator), not a detector. Thread 1 built end-to-end, leakage-disciplined, falsification-first:
- `coinbase_btcusd_book_collector.py` — L2 top-10/side depth on a 100ms grid, gzipped JSONL (the resting-size
  book state our trade collectors discard). `book_collector_btc.yml` — durable GHA -> `data/btc-book`
  (collection running).
- `research/od_book/`: `book_state` (45-dim x(t)), `splits` (walk-forward, leakage-asserted), `champion`
  (VAR/ridge), `challenger_od` (exact-DMD operator recovery + spectrum), `metrics` (OOS R² + turn-as-
  consequence net-22bps + salvage), `run_experiment` (one-shot-guarded T_test), `KILL_GATE.md` (frozen).
- Early read on ONE 18.8-min real window: **DMD operator ties VAR** (the spec's anticipated KILL-mode #1 —
  linear model absorbs the dynamics) and is net-negative after fees. Built to point at the multi-day
  `data/btc-book` data. Threads 2 (regime operator) and 3 (cross-asset transfer) only if thread 1 clears.

## GIT / BRANCH FIX (root cause of repeated wrong-branch landings)
- The harness assigned this session to a STALE snapshot branch `claude/divergence-exhaustion-backtest-wj65sm-65uts0`
  (S31 content) instead of the real S36b branch `claude/divergence-exhaustion-backtest-wj65sm`. Cause: the
  repo default branch (`claude/new-session-o3vnm`) carried stale S31 code, so auto-created session branches
  inherited it.
- **Fix:** force-updated the **default branch -> the canonical S36b tip + this session's work**, so future
  sessions inherit the right content regardless of the setting (couldn't flip the default-branch *pointer*:
  no API tool, and the mobile/desktop GitHub settings UI wouldn't render it). I keep default synced to
  canonical on every push. Stray `-65uts0` could NOT be deleted (the env git proxy refuses ref deletions) —
  **cosmetic; delete it from the GitHub Branches UI when convenient.**

## INFRA reality (for "finish setting up AWS")
- **No AWS connector / CLI / creds** in this environment. **Render** connector is present but has **no
  authenticated workspace** (`list_workspaces` 400s) -> can't deploy there yet. Render `virginia` region =
  AWS us-east-1 = Coinbase's region (the co-region play), so once Render is connected we can host durable
  collection + off-git storage there. Real EC2/colo for the live hot path = AWS via creds/IaC (write IaC,
  Greg applies). NONE of this blocks current work — the gzip fix resumed collection for free.
- My GitHub token **can't trigger workflow runs** (403 actions:write). Scheduled crons fire fine; manual
  "Run workflow" is Greg's click.

## STATE / WHAT'S RUNNING
- **SOL/DOGE/XRP collectors:** first run in_progress; 6h cron + workflow_dispatch going forward; -> `data/{sol,doge,xrp}-bins` (gzipped).
- **BTC/ETH collectors:** gzip-fixed; resume on next 6h cron (or Greg clicks "Run workflow" to resume now).
- **OD-BOOK book collector:** durable run going -> `data/btc-book`.
- 15 cells accruing total.

## NEXT (priority)
1. **Let the data accrue** (now flowing) and **re-run `_info_dipole_gated_swing.py`** across the multi-window /
   multi-coin / multi-regime set -> the real (non-overfit) per-cell deploy map across all 15 cells. This is
   the S36b NEXT #1 finally unblocked.
2. **NEXT #3:** confirm exchange hosting regions (Coinbase=us-east-1; Kraken/Bybit?) + model maker fills for
   the live sub-second maker path (research; unblocked).
3. **Durable off-git storage** (S3/Render) once Greg connects Render workspace or AWS — gzip is a ~6-week band-aid.
4. **OD-BOOK:** once `data/btc-book` has enough, run thread-1 T_test (`run_experiment --commit-ttest`); advance threads 2/3 only if it clears.
5. **Greg's broader merge-math thread** (separate from the dipole) — his dig with the Architect.

## TOOLS ADDED THIS SESSION
`_info_dipole_gated_swing.py`; `coinbase_collector.py` / `kraken_collector.py` / `bybit_perp_collector.py`
(generic); `coinbase_btcusd_book_collector.py`; `research/od_book/*`. Workflows: `alt_collectors_durable.yml`
(new), `book_collector_btc.yml` (new), `btc/eth_collectors_durable.yml` (gzip-fixed).
