# fingerprint_dataset — self-contained coeff + test data for lightweight fingerprint tests (S35b)

Greg (phone-limited): keep enough coeff + test data IN the markets repo to run lightweight tests
without the local machine's bulk (the full coeff records are ~47GB; `E:\refrag` is ~98GB; raw
`live_data_history` is ~9GB). Everything here is the COMPACT form the fingerprint actually needs.
~9 MB total. (refrag itself is NOT vendored — Greg has a workaround.)

## Contents
- `coeffs/coeff_index.json.gz` — **16,484 OD coeff signatures**, compact `{source_id: {coef:[128],
  label, cell, lineage}}`. Lineages: `cs2000_clean` (win+lose, 14,994), `cand_sp` (win, 1,919),
  `onset` (win, 495 — the S35b re-anchored set at true per-episode onsets). 4.6 MB gz. Built by
  `_build_fingerprint_dataset.py` (regex-extracts the 128-dim vectors; reuses the cs2000 shards).
- `coeffs/coeff_index_summary.json` — per-cell win/lose counts by lineage.
- `onsets/winner_onsets.json` — 1,560 winners mapped to true episode onset: `onset_micros` (the
  fresh pre-entry 6 micros), `stored_micros` (the contaminated mid-trade ones), `true_onset_ts_utc`,
  `old_entry_ts_utc`, `onset_moved`, `net_bps`. The training labels for the entry fingerprint.
- `onset_lists/markets_<cell>_onset.cap100.json` — the per-cell winner lists fed to the onset coeff
  re-run (entry_ts = true onset; per-episode source_id).
- `test_bars/<venue>_minbars.json` — 18,491 minute bars (2026-05-22..24, 6 venues) covering the onset
  pre-entry windows, so the encoder/onset canary runs without `live_data_history`. 2.8 MB.

## Tests
- `_test_coeff_lightweight.py` (repo root) — bar-free: loads `coeff_index.json.gz`, verifies 128-dim,
  per-cell win+lose present, **individual-coeff DISTINCTIVENESS** (96–99.7% distinct per cell, 12/12
  pass — the S35 metric, NOT centroid separation), and that the centroid/projection machinery
  computes. Documents the centroid common-mode collapse (cross-centroid cosine ~0.994) as the
  expected artifact (why we do not grade by centroids). PASSES.
- Next (build step, data is ready here): an onset micro canary using `test_bars/` + `winner_onsets`
  to check the encoder reproduces the ONSET micros pre-entry — the wiring GATE.

## Provenance / discipline
All derived from LOCAL data (`E:\refrag\discoveries\operator_discoveries`, `live_data_history`); the
bulk stays local ([[markets-data-lives-local-not-git]]). This compact slice is the fingerprint
payload, committed by Greg's S35b request so the build is reproducible off git alone.
