# MODEL DISAGREEMENT FEED - BUILD NOTES (DATA_GATE_S98 feed C, family D)

Built 2026-07-20 by the feed C build agent. Module `research/kalshi/model_disagreement.py`, store
`data/model_disagreement/model_disagreement.json` (**119 days, 2025-11-01 .. 2026-02-27**, 3.7 MB,
local - git holds CODE, the store is DATA for the S3 push). Nothing existing was edited; all inputs
read-only. No network was used at any point: the feed COMPUTES from the local raw archive, it does
not fetch.

Feed A's February extension landed mid-build (the canonical index grew 91 -> 119 days during this
session); per the feed C spec the store was rebuilt to cover it, so G12 (Feb 1-13) and G13
(Feb 15-27) both have this input.

WHY (verbatim from the gate): the market prices UNCERTAINTY, not just the central case. G11's
0125/0126 whipsaw happened on a wobbling forecast. This feed makes a wobble visible as state:
which horizons the two short-range models disagree on, and WHICH model moved run-to-run. It is an
input the agent reads, never a scored thesis.

## 1. Structures found (investigated, not assumed)

- `weather/mos_asof/raw/` was FULLY PRESENT locally - **no S3 restore was needed**. Two complete
  fetch windows: the original S97 pull ({METRO}_{MODEL}_2025-10-29_2026-02-09.json, 48 files) and
  feed A's February re-pull ({METRO}_{MODEL}_2025-10-29_2026-03-09.json, 48 files), plus two ORD
  re-pull windows (2026-01-17..01-29). The loader merges all windows per metro/model with LOUD
  conflict detection: **zero value conflicts across the entire ~3.5-month overlap region** (the two
  independent IEM pulls agree row-for-row; the ORD subsets had already verified exact).
- Raw row = `{runtime, ftime, tmp}` verbatim UTC; runtime = model initialization (the blind-wall
  key); missing temps are absent rows, never zeros (upstream discipline, inherited).
- `mos_asof_index.json` span at final build: **2025-11-01 .. 2026-02-27 (119 days)** - this store
  covers exactly that span.
- Model cycle geometry AS ARCHIVED (measured from the run stamps, not from bulletin nominals):
  - GFS (MAV): 4 cycles/day (00/06/12/18Z) -> latest eligible cycle at the D-1-evening wall is 18Z D-1.
  - NAM (MET): 2 cycles/day (00/12Z only; MET is only issued from the 00Z/12Z NAM) -> latest is 12Z D-1.
  - MEX (GFS extended): 2 cycles/day (00/12Z), 12-hourly temps -> latest is 12Z D-1.
  - Archived temp grids for BOTH MAV and MET run 3-hourly to +60h then 6-hourly to +72h (21 ftimes
    per run measured). The MET bulletin's nominal +84h reach does NOT exist in the archived `tmp`
    rows - temps stop at +72h. This is why the overlap and stability reaches below are what they are.

## 2. Run-selection logic: inherited, not re-derived

The module imports the canonical functions from `nws_temp_feed` (same directory, read-only import):
`_mos_cutoff_utc` (wall = D-1T23:59Z = 17:59 CT D-1 evening; the 00Z cycle of D itself EXCLUDED),
`_runset_asof` (24h evening batch, hard assert inside), `_day_temp_from_run` (gas-day
America/Chicago, min-obs per model: GFS 5 / NAM 5 / MEX 2), `degree_days`, `station_weights`.
The only new selection code is the single-model walk (`_model_station_read`) - the canonical
`_station_forecast` minus its GFS->NAM->MEX preference ladder, cycle choice identical
(latest eligible first). Drift from the canonical feed is therefore impossible by construction,
and the selftest proves the reproduction (section 7).

## 3. Overlap geometry (the measured answer to "which horizons does MET cover")

Under the D-1-evening as-of, per-model coverage of target gas day D+h:

| read | horizons covered | mechanics |
|---|---|---|
| Disagreement MAV vs MET (matched pair) | **h0, h1 only** - all 119 days | at h2 the 18Z-D-1 MAV window puts only 3 obs (6-hourly tail) inside the gas day (< min 5); MET's 12Z-D-1 window only 2 |
| GFS (MAV) run stability | **h0 only** | the PRIOR batch (18Z D-2) reaches a D+1 target with only 3 obs |
| NAM (MET) run stability | **h0 only** | prior batch (12Z D-2) reaches a D+1 target with only 2 obs (+66/+72) |
| MEX run stability | **h0..h5** | 12-hourly grid, min 2 obs; at h6/h7 the prior batch leaves < 2 obs in the target gas day |

So the feed's information geometry is: the MAV/MET DISAGREEMENT pair sees today and tomorrow; the
D+2..D+5 strip is MEX-only territory where the per-model STABILITY read is the uncertainty signal;
h6/h7 are structurally dark for run-to-run change (and were already None in the canonical composite).
Horizons outside a read's reach are None with the reason NAMED in the row - never zero.

## 4. Coverage per date

**All 119 days complete: overlap horizons [0,1] on every date, every value row carries the full
16/16 metro common set, zero partial rows anywhere in disagreement or stability, zero raw-archive
gaps, MEX stability reach h0-h5 on every day.** There are no per-date deviations to name. Per-date
state summary (max/mean |spread| are the within-date shape descriptors; per-horizon rows in the
store are canonical):

| date | overlap_h | max abs spread @ h | mean abs spread | coverage |
|---|---|---|---|---|
| 2025-11-01 | [0, 1] | 2.665 @ h1 | 1.99 | complete |
| 2025-11-02 | [0, 1] | 0.983 @ h0 | 0.945 | complete |
| 2025-11-03 | [0, 1] | 1.435 @ h1 | 1.167 | complete |
| 2025-11-04 | [0, 1] | 1.374 @ h1 | 1.302 | complete |
| 2025-11-05 | [0, 1] | 1.13 @ h0 | 0.947 | complete |
| 2025-11-06 | [0, 1] | 1.576 @ h1 | 1.389 | complete |
| 2025-11-07 | [0, 1] | 2.258 @ h1 | 2.209 | complete |
| 2025-11-08 | [0, 1] | 1.264 @ h0 | 1.016 | complete |
| 2025-11-09 | [0, 1] | 1.151 @ h0 | 0.948 | complete |
| 2025-11-10 | [0, 1] | 0.882 @ h0 | 0.863 | complete |
| 2025-11-11 | [0, 1] | 2.699 @ h1 | 1.482 | complete |
| 2025-11-12 | [0, 1] | 1.5 @ h0 | 1.485 | complete |
| 2025-11-13 | [0, 1] | 1.977 @ h1 | 1.363 | complete |
| 2025-11-14 | [0, 1] | 1.649 @ h0 | 1.634 | complete |
| 2025-11-15 | [0, 1] | 0.742 @ h0 | 0.674 | complete |
| 2025-11-16 | [0, 1] | 1.031 @ h1 | 0.737 | complete |
| 2025-11-17 | [0, 1] | 1.953 @ h1 | 1.582 | complete |
| 2025-11-18 | [0, 1] | 1.191 @ h1 | 0.907 | complete |
| 2025-11-19 | [0, 1] | 2.236 @ h1 | 1.128 | complete |
| 2025-11-20 | [0, 1] | 1.194 @ h1 | 1.041 | complete |
| 2025-11-21 | [0, 1] | 3.18 @ h1 | 2.038 | complete |
| 2025-11-22 | [0, 1] | 2.301 @ h1 | 1.838 | complete |
| 2025-11-23 | [0, 1] | 2.379 @ h0 | 2.112 | complete |
| 2025-11-24 | [0, 1] | 1.643 @ h0 | 1.446 | complete |
| 2025-11-25 | [0, 1] | 1.022 @ h0 | 0.849 | complete |
| 2025-11-26 | [0, 1] | 0.891 @ h0 | 0.516 | complete |
| 2025-11-27 | [0, 1] | 0.439 @ h1 | 0.392 | complete |
| 2025-11-28 | [0, 1] | 0.705 @ h0 | 0.381 | complete |
| 2025-11-29 | [0, 1] | 0.132 @ h0 | 0.077 | complete |
| 2025-11-30 | [0, 1] | 0.368 @ h1 | 0.262 | complete |
| 2025-12-01 | [0, 1] | 0.09 @ h1 | 0.084 | complete |
| 2025-12-02 | [0, 1] | 0.725 @ h0 | 0.703 | complete |
| 2025-12-03 | [0, 1] | 1.121 @ h1 | 0.656 | complete |
| 2025-12-04 | [0, 1] | 1.193 @ h1 | 1.097 | complete |
| 2025-12-05 | [0, 1] | 1.079 @ h1 | 0.919 | complete |
| 2025-12-06 | [0, 1] | 0.635 @ h1 | 0.407 | complete |
| 2025-12-07 | [0, 1] | 1.264 @ h0 | 0.723 | complete |
| 2025-12-08 | [0, 1] | 0.133 @ h1 | 0.096 | complete |
| 2025-12-09 | [0, 1] | 0.096 @ h0 | 0.075 | complete |
| 2025-12-10 | [0, 1] | 0.649 @ h0 | 0.514 | complete |
| 2025-12-11 | [0, 1] | 0.725 @ h0 | 0.701 | complete |
| 2025-12-12 | [0, 1] | 0.787 @ h0 | 0.476 | complete |
| 2025-12-13 | [0, 1] | 1.126 @ h1 | 0.756 | complete |
| 2025-12-14 | [0, 1] | 1.006 @ h0 | 0.637 | complete |
| 2025-12-15 | [0, 1] | 1.28 @ h1 | 1.056 | complete |
| 2025-12-16 | [0, 1] | 0.896 @ h0 | 0.606 | complete |
| 2025-12-17 | [0, 1] | 1.303 @ h1 | 1.188 | complete |
| 2025-12-18 | [0, 1] | 0.626 @ h0 | 0.373 | complete |
| 2025-12-19 | [0, 1] | 0.492 @ h0 | 0.487 | complete |
| 2025-12-20 | [0, 1] | 0.647 @ h0 | 0.481 | complete |
| 2025-12-21 | [0, 1] | 1.306 @ h1 | 0.792 | complete |
| 2025-12-22 | [0, 1] | 1.121 @ h0 | 0.758 | complete |
| 2025-12-23 | [0, 1] | 1.023 @ h0 | 0.594 | complete |
| 2025-12-24 | [0, 1] | 1.475 @ h1 | 1.211 | complete |
| 2025-12-25 | [0, 1] | 2.778 @ h1 | 2.144 | complete |
| 2025-12-26 | [0, 1] | 2.034 @ h0 | 1.917 | complete |
| 2025-12-27 | [0, 1] | 1.092 @ h0 | 0.558 | complete |
| 2025-12-28 | [0, 1] | 1.475 @ h1 | 1.056 | complete |
| 2025-12-29 | [0, 1] | 0.772 @ h1 | 0.615 | complete |
| 2025-12-30 | [0, 1] | 0.75 @ h1 | 0.547 | complete |
| 2025-12-31 | [0, 1] | 0.669 @ h0 | 0.43 | complete |
| 2026-01-01 | [0, 1] | 0.197 @ h1 | 0.18 | complete |
| 2026-01-02 | [0, 1] | 0.41 @ h1 | 0.21 | complete |
| 2026-01-03 | [0, 1] | 0.913 @ h1 | 0.676 | complete |
| 2026-01-04 | [0, 1] | 2.961 @ h1 | 2.348 | complete |
| 2026-01-05 | [0, 1] | 1.742 @ h0 | 1.628 | complete |
| 2026-01-06 | [0, 1] | 1.752 @ h1 | 1.472 | complete |
| 2026-01-07 | [0, 1] | 1.342 @ h1 | 1.13 | complete |
| 2026-01-08 | [0, 1] | 2.191 @ h1 | 1.767 | complete |
| 2026-01-09 | [0, 1] | 1.849 @ h0 | 1.458 | complete |
| 2026-01-10 | [0, 1] | 1.109 @ h1 | 1.069 | complete |
| 2026-01-11 | [0, 1] | 1.342 @ h1 | 0.772 | complete |
| 2026-01-12 | [0, 1] | 0.731 @ h0 | 0.427 | complete |
| 2026-01-13 | [0, 1] | 1.5 @ h0 | 1.209 | complete |
| 2026-01-14 | [0, 1] | 1.317 @ h0 | 0.976 | complete |
| 2026-01-15 | [0, 1] | 1.174 @ h0 | 0.962 | complete |
| 2026-01-16 | [0, 1] | 2.899 @ h1 | 1.684 | complete |
| 2026-01-17 | [0, 1] | 1.193 @ h0 | 0.935 | complete |
| 2026-01-18 | [0, 1] | 0.857 @ h0 | 0.839 | complete |
| 2026-01-19 | [0, 1] | 0.983 @ h1 | 0.573 | complete |
| 2026-01-20 | [0, 1] | 1.599 @ h1 | 1.194 | complete |
| 2026-01-21 | [0, 1] | 1.618 @ h1 | 1.507 | complete |
| 2026-01-22 | [0, 1] | 0.997 @ h1 | 0.603 | complete |
| 2026-01-23 | [0, 1] | 1.474 @ h1 | 0.833 | complete |
| 2026-01-24 | [0, 1] | 0.778 @ h1 | 0.547 | complete |
| 2026-01-25 | [0, 1] | 1.733 @ h1 | 1.125 | complete |
| 2026-01-26 | [0, 1] | 1.75 @ h0 | 1.609 | complete |
| 2026-01-27 | [0, 1] | 1.848 @ h1 | 1.767 | complete |
| 2026-01-28 | [0, 1] | 0.798 @ h0 | 0.415 | complete |
| 2026-01-29 | [0, 1] | 0.214 @ h0 | 0.127 | complete |
| 2026-01-30 | [0, 1] | 0.095 @ h0 | 0.075 | complete |
| 2026-01-31 | [0, 1] | 0.528 @ h1 | 0.278 | complete |
| 2026-02-01 | [0, 1] | 0.952 @ h0 | 0.937 | complete |
| 2026-02-02 | [0, 1] | 0.969 @ h0 | 0.717 | complete |
| 2026-02-03 | [0, 1] | 1.056 @ h1 | 0.675 | complete |
| 2026-02-04 | [0, 1] | 0.191 @ h1 | 0.169 | complete |
| 2026-02-05 | [0, 1] | 0.298 @ h1 | 0.275 | complete |
| 2026-02-06 | [0, 1] | 0.266 @ h1 | 0.155 | complete |
| 2026-02-07 | [0, 1] | 1.169 @ h1 | 0.913 | complete |
| 2026-02-08 | [0, 1] | 0.435 @ h0 | 0.385 | complete |
| 2026-02-09 | [0, 1] | 1.366 @ h1 | 0.894 | complete |
| 2026-02-10 | [0, 1] | 1.287 @ h1 | 1.277 | complete |
| 2026-02-11 | [0, 1] | 0.947 @ h1 | 0.735 | complete |
| 2026-02-12 | [0, 1] | 1.43 @ h0 | 1.369 | complete |
| 2026-02-13 | [0, 1] | 1.236 @ h0 | 0.984 | complete |
| 2026-02-14 | [0, 1] | 1.076 @ h1 | 0.958 | complete |
| 2026-02-15 | [0, 1] | 1.711 @ h0 | 1.679 | complete |
| 2026-02-16 | [0, 1] | 2.702 @ h0 | 2.147 | complete |
| 2026-02-17 | [0, 1] | 2.537 @ h0 | 2.268 | complete |
| 2026-02-18 | [0, 1] | 1.871 @ h0 | 1.05 | complete |
| 2026-02-19 | [0, 1] | 0.197 @ h0 | 0.166 | complete |
| 2026-02-20 | [0, 1] | 1.354 @ h1 | 0.985 | complete |
| 2026-02-21 | [0, 1] | 1.278 @ h0 | 0.932 | complete |
| 2026-02-22 | [0, 1] | 0.064 @ h0 | 0.063 | complete |
| 2026-02-23 | [0, 1] | 0.273 @ h1 | 0.163 | complete |
| 2026-02-24 | [0, 1] | 0.408 @ h0 | 0.376 | complete |
| 2026-02-25 | [0, 1] | 1.486 @ h1 | 0.837 | complete |
| 2026-02-26 | [0, 1] | 0.275 @ h1 | 0.218 | complete |
| 2026-02-27 | [0, 1] | 2.469 @ h1 | 2.105 | complete |

Largest matched-horizon disagreements in the store (each an individual state fact, not a pool):
2025-11-21 (-3.18 @ h1), 2026-01-04 (-2.961 @ h1), 2026-01-16 (-2.899 @ h1), 2025-12-25
(-2.778 @ h1), 2026-02-16 (-2.702 @ h0), 2026-02-17 (-2.537 @ h0), 2026-02-27 (-2.469 @ h1).
Observed fact, stated without interpretation: the ten largest spreads are all NEGATIVE, i.e. on the
big-disagreement days the NAM-MET carried more heating demand than the GFS-MAV. Of note for the
walk's designed tests: 02-16/02-17 sit at the OPEN of G13 (the squeeze test) and 02-27 is its final
day.

## 5. The 0125/0126 case (factual demonstration, printed by --selftest)

Target 2026-01-30 (the G11 final day), per-model split:

- As-of 01-24 evening (store day 2026-01-25, h5): **MEX run-delta -2.315; GFS None; NAM None** -
  the cut the gate names, now attributed: it was the EXTENDED model, at a horizon the short-range
  models could not reach.
- As-of 01-25 evening (store day 2026-01-26, h4): **MEX run-delta +3.197** - the re-add, same
  target, next evening batch.
- The surrounding far-strip was live all week: as-of 01-23 evening the MEX added +2.584 (h4) /
  +1.927 (h3) / +1.570 (h5) across targets 01-26..01-29; as-of 01-22 evening it had added +4.500
  toward target 01-28.
- When target 01-30 finally entered the short-range window: as-of 01-29 evening (h1) MAV 37.132 vs
  MET 37.171, spread -0.039; as-of 01-30 morning wall (h0) MAV 36.604 vs MET 36.699, spread -0.095.
  The two matched models AGREED (among the smallest mean-abs-spread days in the whole store, 0.127
  and 0.075) while the contest lived entirely in the extended-range run-to-run whipsaw days earlier.

Cross-reference, feed A's motivating case: the largest MEX run-delta in the store is **+8.511 on
store day 2026-01-19 (as-of 01-18 evening) at h5, target 2026-01-24** - the same +8.511 Jan-24 add
DATA_GATE_S98 feed A names. The per-model split shows it, too, was an extended-model move. In the
February extension the same class of far-strip event appears again: as-of 02-23 evening the MEX
added +7.188 at h5 (target 2026-03-01, inside G13's expiry week), and as-of 02-25 evening +4.455
(h5) / +4.337 (h4) toward targets 03-03/03-02. Facts only; the agent decides what they mean.

## 6. Store and function

- `model_disagreement_asof(date) -> dict | None` (str or date/datetime): store lookup first;
  outside the store it computes on the fly from the local raw archive under the same wall; honest
  None where the archive cannot cover the date at all. Verified: 2025-09-01 -> None (pre-archive),
  2026-05-01 -> None; dates just past the span but inside raw (through ~2026-03-08) compute on the
  fly.
- Day record: `disagreement[8]` (per horizon: mav_gw_hdd/met_gw_hdd/spread_gw_hdd/abs/cdd variants,
  common-set metro geometry named, per-metro run stamps), `stability{GFS,NAM,MEX}[8]` (per-model
  d_gw_hdd/d_gw_cdd, both batches' run stamps), `summary` (n_overlap_horizons,
  max_abs_spread_gw_hdd + its horizon, mean_abs_spread_over_overlap - labeled a WITHIN-DATE shape
  descriptor, never a pooled conclusion).
- Spread convention: `spread_gw_hdd = MAV minus MET`, signed; computed on the COMMON metro set only
  so a coverage difference can never masquerade as disagreement (same rule the canonical composite
  run_delta uses).

## 7. Selftest record (2026-07-20)

First pass, on the pre-extension 91-day store: **ALL PASS** - 29,120 run stamps checked / 0
blind-wall violations; canonical composite reproduced 273/273 (MEX split, h>=3) and 91/91 (all-GFS
h0); 91/91 days recomputed from raw byte-equal; 0 zeroed values behind any null; the no-overlap
None demonstration and the 0125/0126 factual case printed.

Final pass on the extended 119-day store: results recorded below when the run completes (same
suite; the store's own build-time integrity facts - zero raw conflicts, zero gaps, uniform
coverage - are already verified above).

## 8. Caveats and named gaps (all honest, none blocking)

1. **Initialization mismatch inside the pair:** the D-1-evening MAV is 18Z-initialized, the MET
   12Z-initialized (MET only exists at 00/12Z). That is the true decision-time geometry - the
   freshest of each model an evening decision actually had - and the per-metro run stamps expose it
   on every row. Cycle-level treatment belongs to feed A, not this feed.
2. **Archived MET temps stop at +72h** (nominal +84h reach does not exist in the IEM `tmp` rows) -
   measured, and the reason MET cannot widen the overlap beyond h1.
3. **MEX is stability-only.** It is one model family (GFS extended), so a MAV-vs-MEX "disagreement"
   would partly be a same-family horizon artifact; it is exposed as run-to-run stability instead.
   A true second extended family (ECMWF) is a named gate gap (not freely archived - gate doctrine).
4. **Span is pinned to the canonical MOS index** (now through 2026-02-27 including feed A's
   February extension). If the index is ever extended again, rebuild with
   `python research/kalshi/model_disagreement.py --build` - one command, span auto-derived, no code
   change.
5. The summary block is a within-date descriptor; per-horizon rows are canonical (no-pooling rule).
6. The store is local DATA (3.7 MB): orchestrator to push `data/model_disagreement/` to S3 and add
   the path to .gitignore per the platform taxonomy (builder does not commit).
