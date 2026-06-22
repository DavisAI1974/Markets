# SESSION HANDOFF — S38 (2026-06-22) — free-historical backfill BUILT + the multi-regime gated-swing re-run KILLS the single-window deploy map

Branch `claude/crypto-backfill-validation-31tubb` (PUSHED). Continues S37. All memories apply: crypto
platform only; zero synthetic; per-cell deploy; git is source of truth; falsification-first; never tune
off a single window.

## HEADLINE (load-bearing): the S37 single-window deploy map was OVERFIT — it does NOT survive multi-regime data
S37 left a PROVISIONAL per-cell map off ONE in-git 1-sec window (btc_kraken +466, eth_coinbase +392,
eth_bybit_perp +670, btc_bybit_perp C-gate +16; 4/6 "clear"). This session pulled FREE historical data,
built a multi-coin / multi-regime 1-sec set, and re-ran `_info_dipole_gated_swing.py` (leakage-gated, same
tool). **Result: only 2/9 cells clear net>0 at the maker floor, both thin/marginal; 7/9 stand aside. The
bybit_perp +466/+670 numbers are GONE.** This is exactly the overfit the S37 note warned against ("DO NOT
size off this one window"). The KILL gate is honest: **capital should NOT go in on these cells on this
evidence.**

PER-CELL DEPLOY MAP (multi-regime; `_info_dipole_gated_swing_results.json`):
| cell | span | deploy |
|---|---|---|
| btc_kraken | 13.9d | **deploy ER stand-aside +32** (recall 0.056, 33 calls — THIN, basically noise) |
| eth_coinbase | 13.9d | **deploy un-gated +60** (recall 0.151 — small; on GAPPY coinbase data, treat cautiously) |
| btc_bybit_perp | 21.0d | stand aside (best −25; un-gated −1306) |
| eth_bybit_perp | 21.0d | stand aside (best +0; −142) |
| sol_bybit_perp | 21.0d | stand aside (−854) |
| doge_bybit_perp | 21.0d | stand aside (−1336) |
| xrp_bybit_perp | 21.0d | stand aside (−76) |
| btc_coinbase | 13.9d | stand aside (−145; gappy data) |
| eth_kraken | 13.9d | stand aside (best +280 had <10 trades = degenerate; deployed-config −1410) |

Reading: the 5 CLEAN bybit_perp cells (21d, zero gaps >1h) ALL stand aside — the strongest signal in the
table, and it is negative. The two "clears" are a 33-call +32 (THIN) and a +60 on gap-degraded coinbase
data — too thin to size real money on. **Net-of-cost edge is NOT established across regimes. No capital.**

## WHAT WAS BUILT (steps 1–4 of the kickoff)
1. **Free-historical backfill suite onto the canonical branch + `backfill_bybit.py` (NEW).** Brought
   `backfill_binance_vision.py` / `backfill_coinbase_spot.py` / `backfill_kraken_spot.py` over from
   `origin/claude/continue-phase-2-pipeline-UFiGY`; wrote `backfill_bybit.py` for the Bybit public daily-dump
   archive (`public.bybit.com/trading/<SYM>/<SYM><DATE>.csv.gz`, free, back to listing). All four bin to
   1-sec in the EXACT collector schema; merge = RT wins, backfill fills gaps only; drops straight into
   `load_series`/`realbins`.
2. **DATA-INTEGRITY AUDIT (Greg's explicit ask — "make sure nothing has shifted; trade-data issues cost us
   weeks").** Verified before any run:
   - timestamps integer-second aligned, NO epoch/unit shift. Definitive overlap test: a Bybit dump for a date
     INSIDE the RT window, binned with the collector logic, matches RT bins at the same second to **median
     0.008 bps** (a 1-sec shift or ms/µs error would explode this).
   - taker buy/sell semantics consistent across every source AND every RT collector (**92.9%** imbalance-sign
     agreement on the overlap; a flip would read ~7%). Coinbase maker→taker flip, Kraken `b/s`=taker,
     Bybit/Binance taker — all cross-checked against the RT collectors.
   - Binance Vision = 13-digit ms (÷1000); Bybit/Kraken = epoch-seconds float; Coinbase ISO→epoch.
   - all 5 coins reachable on both dump sources (Bybit SOL perp listed after 2021 → Binance Vision covers
     SOL deep history); DOGE `0.08347` / XRP `1.1458` survive float binning. Verified Kraken REST pairs
     (DOGE = `DOGEUSD`→XDGUSD key; XRP→XXRPZUSD) and Coinbase alt products (200).
   - `backfill_bybit` merge preserves RT bins byte-identical (gap-fill only).
3. **Ran the backfills locally (autonomous, no GitHub click needed).** 21-day Bybit dumps for all 5 coins
   (BTC 55.5M trades→1.5M bins; +ETH/SOL/DOGE/XRP) + Coinbase/Kraken REST gap-fill for BTC/ETH. Materialized
   9 cells in `realbins/`: 5 bybit_perp (21d, contiguous, 0 gaps>1h), 2 kraken (13.9d, gap-free), 2 coinbase
   (13.9d but GAPPY — Coinbase REST walks back from now and stalls early, so it only filled the recent tip;
   btc_coinbase has one 185h hole). Gaps are near series-end; the index-based zigzag yields ≤1 spurious swing
   per seam → negligible; I ran the validated tool UNMODIFIED and flag the coinbase cells.
4. **Re-ran `_info_dipole_gated_swing.py`** → leakage gate PASS 9/9; the deploy map above. Tool now records
   per-cell `cell_spans` in the result JSON (self-documenting).

## WORKFLOW
`backfill_oneshot.yml` rewritten: 5-coin matrix (btc/eth/sol/doge/xrp) → each coin's `data/<coin>-bins`
branch, all 4 sources, **gzip-aware restore+push** (gunzip on restore / gzip on push, mirrors the durable
collectors) so it no longer re-triggers the 100 MiB push stall; checkout points at the dev branch; anti-
clobber guardrail. **I cannot trigger GHA runs (token lacks `actions:write`) — this is Greg's "Run workflow"
click.** It is NOT needed for this session's validation (data pulled locally); use it to commit the DEEP
(years, back to 2021) history durably to the data branches.

## CAVEATS (honest)
- 21 days is genuinely multi-regime vs the S37 single window, but still ONE ~3-week period (June 2026). The
  STRONGER test is the years of history available via Binance Vision / Bybit dumps (2021→) — run the oneshot
  to pull it; the result above could shift (likely still negative for the bybit cells given how clean/large
  they already are).
- Coinbase cells are gap-degraded this session (REST limit) — even eth_coinbase's +60 is on holey data.
- `realbins/` (≈900 MB) is gitignored and LOCAL; re-pull is one command per coin
  (`python backfill_bybit.py --symbol <SYM> --days N --bins-path realbins/<coin>_bybit_perp_bins.json`).
  Durable storage = the data branches via the oneshot workflow (or off-git S3/Render once authed).

## NEXT (priority)
1. **Deeper-history test:** trigger `backfill_oneshot.yml` for years of data (or pull locally) and re-run —
   confirm whether ANY cell clears net-of-cost across multiple regimes/years. Current read: it does not.
2. **Do NOT deploy capital** on the gated-swing dipole stack until a cell clears net>0 at maker with real
   trades across deep multi-regime history with margin (not a 33-call +32).
3. If the edge stays negative across deep history: the dipole-gated swing is falsified as a standalone
   capital strategy at these costs — revisit the maker-fill economics (NEXT #3) and the OD-BOOK thread, or
   re-scope the signal. Per `tools-are-complementary-not-competing`, keep the pieces, drop the deploy claim.
4. Default-branch sync (`new-session-o3vnm`): NOT done this session — I pushed only to the assigned dev
   branch `claude/crypto-backfill-validation-31tubb` per the hard "never push to a different branch" rule.
   If you want default re-synced, say so explicitly.

## TOOLS ADDED/CHANGED THIS SESSION
`backfill_bybit.py` (new); `backfill_{binance_vision,coinbase_spot,kraken_spot}.py` (brought to dev branch);
`.github/workflows/backfill_oneshot.yml` (rewritten: 5-coin matrix, gzip-aware); `_info_dipole_gated_swing.py`
(now self-documents data span; honest labels); `_info_dipole_gated_swing_results.json` (multi-regime re-run).
