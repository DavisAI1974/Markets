# Markets working tree for the Adaptive Locality engine and BuildMap component

This directory started as an exact copy of `../buildmap_source_snapshot/` (BuildMap commit
`8b4295dcb4044a6e4df4b7dbad897a81348fe6e2`). The snapshot is frozen provenance and is never edited.
All Markets-side fixes, new controls, new tests and documentation addenda land HERE.

Rules carried over unchanged: nothing scientific is dropped; no averaging, smoothing or substitution of
original evidence; every abstention keeps its reason; no scientific calculation is eliminated; no
Frankie/AWS/Search/ingestion connection; launch stays HOLD.

Fix tracking: `../CCODE_INDEPENDENT_REVIEW_20261108.md` (finding ids PG-*, M-*, T-*, N-*, R-*, E-*, BM-*).
Each fix is recorded in `FIX_LOG_20261108.md` in this directory with the finding id, files, and the test that
proves it.

Run (from this directory):

    python3 -m compileall -q adaptive_locality
    python3 -m unittest discover -s tests -p 'test_adaptive_locality*.py'
    npm ci --ignore-scripts --no-audit --no-fund && node --test tests/
