# Markets migration inventory — EARLY STATUS (NOT COMPLETE)

Date: 2026-11-08.
Destination: `DavisAI1974/Markets`
Branch: `research/markets-adaptive-wavepacket-migration-20261108`
Source: `DavisAI1974/BuildMap@8b4295dcb4044a6e4df4b7dbad897a81348fe6e2`.
Path: `research/kalshi/adaptive_wavepacket_20261108/buildmap_source_snapshot/`.

**At handoff publication, only 63 of 131 UTF-8 source files were committed. Source PDF and DOCX reports were not yet transferred.** Existing Markets code is untouched. This is an **in-progress** log; DO NOT issue a final migration completeness/CI/production acceptance claim until a destination source-tree manifest and content-hash comparison are produced.

Required final checkpoint:
- All 131 UTF-8 source files copied and content compared to pinned BuildMap Git tree.
- Two non-UTF8 reports byte-for-byte copied or explicitly recorded as missing with stable source links. No silent omission.
- Entire BuildMap/native scanner/source viewer/UI and its tests included, not merely a shadow adapter.
- Archived original scientific docs/hand-offs retained; authoritative Markets-specific new handoff reflects BuildMap **INCLUDED, TESTS PENDING**.
- If test paths use original repository-root layout, run them in the copied snapshot working directory; do not conflate old successful source CI with new cross-repo end-to-end validation.
- Existing Markets and Frankie data/source branches untouched; new migration branch only.
- No scientific data, negative result, outlier, rank-deficient finding or unsupported hypothesis discarded.
