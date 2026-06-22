# Vendored build kit — external/at-risk files brought into the markets repo (S35b, 2026-06-21)

Greg asked (phone-limited window) to pull into the markets repo any build files that live
*outside* it and that upcoming steps need. These were UNTRACKED at the `E:\Markets` root (the
"basic_equations originals" the BUILD_PLAN flags as external) — present on the E: drive only, which
is exFAT-locked ([[markets-env-hard-lock]]). Copying them here makes them durable in git
(`DavisAI1974/Markets`). The runtime copies still live at the `E:\Markets` root; treat these as the
canonical/durable mirror.

## What's here (all small pure-Python; data stays local)
**Live heavy tier + fingerprint construction (the predictor needs these):**
- `_markets_gate_v2.py` — validated live 128-dim OD-coeff recompute (pre-entry 30m -> refrag) +
  centroid projection `info_score` (the HEAVY tier; `markets-deploy-feature-parity-gap`).
- `_markets_dipole_export_centroids.py`, `_markets_dipole_export_centroids_v2.py` — build the
  per-cell win/lose centroids the dipole/fingerprint projects onto.
- `_markets_algebraic_dipole.py`, `_markets_dipole_kfold.py`, `_markets_dipole_separation.py`,
  `_markets_dipole_chunker_stack.py` — the verbatim original OD dipole construction
  (`markets-dipole-construction-is-centroid-based`).

**Pipeline machinery (coeff runs / candidate building):**
- `_run_clean_rerun.py` — batch/archive helpers (`_count_summary_results`, `_archive_evidence_graph`);
  imported by `_run_onset_coeffs.py` and `_run_sameperiod_cand.py`.
- `_extract_coeff_index.py` — index coeffs from `operator_discoveries` (regenerate the index locally).
- `_build_sameperiod_cand.py`, `_run_sameperiod_cand.py`, `_eligible_cross_section.py` — the S34
  same-period discovery pipeline (the onset re-run `_run_onset_coeffs.py` is a copy of this).

**Vendored refrag adapter (makes the canary self-contained):**
- `markets_bar_loader.py` — copied from `E:\refrag\adapters`; stdlib-only (no refrag internals), so it
  vendors cleanly. Provides `_venue_stem` used by the fingerprint canaries.

## The ONE external dependency that is NOT vendorable: refrag
`E:\refrag` (the OD discovery engine, `DavisAI1974` deepnova/refrag) is **~98 GB** (≈97 GB is
`discoveries/` + `artifacts/` data; ~1 GB code). It is its own git repo and is referenced by
absolute path (`E:\refrag\...`). It CANNOT go in the markets repo (size + GitHub limits). The live
HEAVY tier (`_markets_gate_v2.py` coeff recompute) and the discovery re-runs require `E:\refrag`
present locally — it is, and stays put. The per-cell coeffs live in
`E:\refrag\discoveries\operator_discoveries\` (local data, never git; `markets-data-lives-local-not-git`).

Already-cloned and present locally (not re-fetched): `E:\basic_equations_src` (the OD research repo,
four-sciences chem code; the markets dipole logic is reconstructed in `odcore/`).
