# Trade-data cleanup runbook — binning problem (2026-06-09)

Answer to "do we have to rerun all the trade data?": **No.** You cannot re-collect
the past from a live WS feed anyway, and you don't need to — the corruption is
localized and mostly repairable. Re-run only the *downstream* that consumed the
bad inputs (kraken-pair discovery + the validation time-split). Everything else stands.

## The three bugs and where the fix is live
| # | Bug | Effect | Fix | Live? |
|---|-----|--------|-----|-------|
| 1 | Kraken v2 `snapshot` replay counted on every reconnect (`kraken_{btcusd,eth}_collector.py`) | **Duplicated** volume, dumped into the reconnect second | accumulate `mtype == "update"` only | **Yes** — code branch `continue-phase-2-pipeline-UFiGY` (the workflow `ref:`), also default `new-session-o3vnm` + `beautiful-shaw`. Takes effect next scheduled run. |
| 2 | Inconsistent grid policy (kraken skips quiet seconds, bybit zero-pads, coinbase fills) | **Apparent** missing seconds; breaks cross-venue alignment | `scripts/bins_integrity.py --normalize` (one regular 1s grid) + `odcore.io.load_bins` already gap-fills | **Yes** (tool + loader) |
| 3 | Commit step `if: always()` force-pushes even on a crashed run | **Real** lost seconds (clobber) | anti-clobber guardrail: never push a file with fewer bins than the data branch | **Yes** — guardrail now on default `new-session-o3vnm` (where scheduled runs read the YAML) |

## What is clean / unaffected (do NOT redo)
- **Coinbase & Bybit bins** — no snapshot replay; correct.
- **Coinbase/Bybit-pair discovery coefficients** — clean inputs → trustworthy.
- **The dipole result's features** (operator_coefficients, z=+9.6 on cs100) — the
  features come from the bins around each trade, not from `entry_ts`.

## What to repair (existing on-disk bins)
The snapshot duplication is confined to a handful of reconnect-spike seconds
(btc_kraken: 9 seconds = **~10% of total kraken volume**; eth_kraken: 5). You can't
un-sum an aggregate, so the honest repair is to **drop those seconds' volume** (mid
is kept, so price stays continuous). Two equivalent paths:

```bash
# A. Materialize a flagged clean copy (real bins verbatim + _suspect flags + zero-grid):
python scripts/bins_integrity.py --normalize realbins/*kraken*.json --out-dir realbins_clean
#    -> odcore.io.load_bins() then auto-zeroes the flagged seconds.

# B. Or mask on the fly from raw, no rewrite:
#    load_bins(path, mask_spikes=True)   # zeroes seconds > max(20*median, 50) trades
```
Audit any bins file at any time:
```bash
python scripts/bins_integrity.py --report realbins/*.json --json integrity.json
```

## What to re-run (downstream only)
1. **Kraken-pair discovery** (`markets_*_kraken_*` buckets): rebuild from spike-masked
   kraken bins, then re-run coeff-gen for those pairs only (refrag-bound, local box).
   coinbase/bybit pairs untouched.
2. **Validation time-split** — blocked by the win-bucket `entry_ts` collapse (below),
   not by the bins.

## Knowledge-base propagation (the JSONs are USED in the KBs)
The per-trade discovery JSONs and evidence snapshots are replicated into all 3 KBs
(OD `E:\refrag\discoveries`, Refrag `E:\refrag\docs`, Factory `F:\Factory\knowledge`)
per the S27 3-copy policy, and downstream reads from them. So a tainted coeff JSON is
tainted in THREE places. Cleanup is not done at re-run — it must propagate:
- After re-running any affected bucket (kraken spikes; win side if the check says so),
  **re-archive the corrected JSONs to all 3 KBs** and **supersede/retire the bad
  snapshots** (don't leave a stale `evidence_snapshot_*` next to the corrected one —
  mark it superseded by run_id/timestamp so a KB reader can't pick the tainted copy).
- The integrity/repair outputs (`bins_integrity.py --report`/`--normalize`) are
  knowledge JSONs too → write them to all 3 KBs.
- coinbase/bybit JSONs are clean → their KB copies stay; no churn.

## Win-bucket date collapse (separate bug, refrag-side)
The win/lose pool builder + `_patch_win_buckets_entry_ts.py` are **not in this repo**
(refrag-bound, local). `markets_adapter.py` carries correct time keys
(`window_start`/`window_end`) off the bin timestamps, so the collapse is in the
refrag trade-gen where win-trade `entry_ts` is overwritten with a constant. This is
why `od_larger_set_val.py` notes *"NO time key exists"* and falls back to a
sorted-filename split. Fix at source (stop overwriting `entry_ts`), rebuild the win
buckets, then the validation can do an honest temporal split. Owner: local/refrag.

## Forward state (no action needed)
- Next scheduled collector run (cron `0 */6 * * *`) uses deduped collectors + the
  guardrail. The one run that was already `in_progress` at fix time does one last
  old-style push; the schedule self-heals after.
