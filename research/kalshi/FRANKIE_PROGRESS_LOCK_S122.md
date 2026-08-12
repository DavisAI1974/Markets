# Frankie Progress Lock — S122

This file is a human-readable pointer to the machine lock in `frankie_progress_lock_s122.json` and `frankie_progress_lock_s122.py`.

## Current measurement

The accepted current data-surface measurement is **1,914 served leaf fields across 44 decision-state blocks, with 1,222 old-brain unread fields**. `unread` means no name/mention in the legacy `ng_brain.json` readership metric. It does **not** mean unavailable to Frankie.

The committed 1,717 / 1,113 `store/data_points.json` object is a historical stale snapshot. It may remain for provenance until the real data-plane registry is regenerated, but it is not current truth and must not be used to shrink the HTML, the registry, or Frankie's access surface.

## Effective status rule

The historical `OPEN_ITEMS.json` still carries an S114 session marker and therefore cannot by itself prove that work is unbuilt. `frankie_progress_lock_s122.py` overlays current effective state without deleting historical provenance.

Fully completed items locked against reopening include A-1, A-13, A-14, A-16, A-22, A-25, A-32, A-46, A-48, A-51, A-52, G-5 and G-19.

S115 items A-42, A-50, A-59, A-61, A-62, A-65, A-66, A-67, A-68 and A-69 are locked as **IMPLEMENTED_EVIDENCE_PENDING** where appropriate: their mechanism/harness must not be rebuilt, while the remaining empirical/evidence operation is still allowed to remain open.

Later completed work locked against rebuilding includes A-82, C2C-018 full 90-play/lossless compaction, S121 endogenous-curve semantics, S121 kitchen-sink completeness, A-87 durable inventory and the S122 field-level target-cell manifest.

## Frankie access rule

For an exact target cutoff, every field that DavisAI possessed, that was causally available by that cutoff, and that is not contaminated by the future answer must be accessible to Frankie. Legacy play-reader count is irrelevant to access. Future/realized target price information stays masked.

## Known stale claims still physically present in old `data_registry.py`

The progress-lock checker deliberately detects the old hard-coded claims that forward wind/solar, zero-change/seasonal baselines and hydro WAT are missing. Those statements are retained temporarily only as evidence of why the old generator cannot be treated as authority. The next registry migration must remove/reconcile them and regenerate the current 1,914+ store on the real data plane.

Until that migration, the machine lock is the current status overlay and CI regression guard. Do not use stale S113/S114 gap prose to authorize duplicate implementation work.
