# SESSION HANDOFF — S28 (2026-06-09) — trade-data binning corruption fixed (forward); coeff-gen re-run scoped

Live read order for a fresh chat: **this file + `CLAUDE_session_note_2026-06-09_S28.md` + `CLEANUP_RUNBOOK.md`**,
then `KICKOFF_2026-06-10_S29.md`. Do NOT read the 207 KB `CLAUDE (5).md` unless you need deep archive.
KEEP PAIRS SEPARATE; never pool; zero synthetic data.

## What S28 did
Pivoted off the planned S27 coeff-gen trajectory to root-cause the missing/duplicated trade data Greg flagged
(the data the coeff runs consumed). Three bugs, all fixed forward and pushed:

1. **Kraken snapshot-replay duplication.** `kraken_{btcusd,eth}_collector.py` counted Kraken v2's `snapshot`
   (recent-trade replay sent on every reconnect) → re-counted trades dumped into the reconnect second.
   ~10% of btc_kraken volume sat in 9 seconds. FIX: accumulate `mtype == "update"` only.
2. **Inconsistent grid policy.** kraken skips quiet seconds (18–28% raw coverage), bybit zero-pads, coinbase fills.
   FIX: `scripts/bins_integrity.py --normalize` (lossless 1 s re-grid) + `odcore.io.load_bins` gap-fill.
3. **`if: always()` force-push clobber.** A crashed collector run overwrote good cumulative bins. FIX: anti-clobber
   guardrail (never push a file with fewer bins than the data branch holds).

## Branches (CRITICAL — live collectors are not on the working branch)
- `new-session-o3vnm` = **default** → governs scheduled workflow YAML. **HAS dedup + guardrail.**
- `continue-phase-2-pipeline-UFiGY` = workflow checkout `ref:` → governs collector code. **HAS dedup + guardrail.**
- `beautiful-shaw-040328` = canonical OD branch. **HAS dedup + guardrail + `bins_integrity.py` + loader fix + runbook.**
- `zealous-cannon-aej9yf` = session mirror of beautiful-shaw.
Next scheduled run (cron `0 */6 * * *`) is the first clean one. The run already in-progress at fix time does one
last old-style push, then it self-heals.

## Files added/changed (on beautiful-shaw)
- `kraken_btcusd_collector.py`, `kraken_eth_collector.py` — dedup.
- `.github/workflows/{btc,eth}_collectors_durable.yml` — anti-clobber guardrail.
- `scripts/bins_integrity.py` — `--report` audit / `--normalize` lossless re-grid + `_suspect` spike flags.
- `odcore/io.py` — `load_bins(..., mask_spikes=False)` honors `_suspect`, opt-in spike guard, mid preserved.
- `CLEANUP_RUNBOOK.md`, `CLAUDE_session_note_2026-06-09_S28.md`.

## Coeff-gen re-run scope (the actual question)
- **coinbase/bybit** coeffs → KEEP (clean inputs; 16 of 24 buckets).
- **kraken** coeffs → only ≤4.0% (btc) / ≤2.7% (eth) of kraken trades have a feature window overlapping a spike;
  drop those (`_suspect`/`mask_spikes`) or re-run the 8 kraken buckets.
- **wins (all venues)** → UNRESOLVED. Greg's pre-coeff screenshots PROVE all 12 `*_win.json` collapsed to
  `1 unique_ts`; `*_win.fixed_ts.json` patched versions exist; loses fine. Whether the coeffs are valid depends on
  **which win file the coeff run consumed** and whether the window anchors on `entry_ts` (collapsed) or
  `source_id`/`window_start` (fine). RESOLVE on the box: (1) check the coeff-run input path; (2) inspect one
  per-trade discovery JSON's window key. Then keep-or-rerun-wins, and re-run `od_larger_set_val.py` for an honest
  temporal split.

## Owed / not doable from cloud (refrag-bound, local box)
- Fix `entry_ts` at source in the refrag trade-gen (the win/lose builder + `_patch_win_buckets_entry_ts.py` are NOT
  in this repo); rebuild win buckets; re-validate.
- Re-run kraken-pair discovery on spike-masked bins (optional given the ≤4% bound).
