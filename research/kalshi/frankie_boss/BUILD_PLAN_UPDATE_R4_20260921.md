# Build plan workbook R4 (2026-09-21): brought to what is built and what has run

Greg, 2026-09-21: "update the excel sheet build plan to reflect what we have built presently. I don't feel that we
have been keeping up with that." The R3 closeout workbook (`artifacts/Frankie_BOSS_Build_Plan_R3_20260914_Closeout.xlsx`,
sha256 `8862589effeee8ccb745dba6fe97a270921571c5524bd8d1b98df04f03817b23`, pinned in `CLOSEOUT_VERIFICATION_20260914.md`)
is untouched. The R4 workbook is a new file beside it: `artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx` (sha256
`7256972fcec5396707f2c40b39fa21b142a36237a6611eeb1e707bc72b201c4d`), generated from R3 by a script that changes cells by
row key and column header (never by position) and records every change on a new sheet `Change Log R4` (sheet, row,
cell, old value, new value, evidence): 129 entries. Historical readiness scores and the historical checkpoint lines are
preserved and annotated, not rewritten (the R3 Read Me says not to recalculate them).

## What changed, by sheet

- Read Me: title, the two status lines, the test-count note (family 1018 passed on 2026-09-18; 2715 passed locally on
  2026-09-21 with 15 environmental failures identical on the base commit), the completed-software line.
- Build Plans: A (running as the Sunday principal; since 09-21 on Frankie's box with the BOSS as engine), B1 (built;
  first real-data cycles run), B2_GATED (shadow critic live on the retained Pod; the same vLLM is the principal engine).
- Components: C01-C06, C11-C15, C19, C21-C29 updated to built-and-run where a real run exists (the Sunday ingestion,
  the 2026-09-15 cycle 0, the 2026-09-20/21 critic runs); five new rows C32-C36 for what R3 had no row for: the journal
  reduction stack, the day pipeline and host/box SSM route, the principal adapter and recorder, Frankie's box harness
  with the BOSS engine session.
- Roadmap: stage 1 closed, 2-3 complete (integrated tree 2026-09-16), 4 complete for the historical source (live feed
  external), 6 first real cycles run, 8 running (retained Pod shadow critic), 9 superseded by the authorized Sunday-only
  run (Memory A VALID, Greg 2026-09-17), 12 partial software.
- Experiment Arms: A-memory, B1-memory, B2-memory readiness state the real runs; D5 the classroom.
- Gates: G02, G03, G16 COMPLETE with their evidence; G05 passed on the historical source (live only open); G06, G07,
  G09, G17, G19 carry the run evidence (timing-label resolution is now code: the source contract's detector reproduces
  the first run's 29 labels); G20-G22, G25, G26 Partial per the 09-14 reconciliation.
- Sources: eight rows added (the 09-16 reconciliation, the 09-18 and 09-20 handoffs, the 09-21 drop-in, the retained
  runtime configuration, the first Sunday run package, the box harness, the ship review).
- Preservation Audit: five rows added (ingestion gold standard, the 4096 retirement, no runtime Pod stops, the principal
  engine correction, the authorized operational run).

## What is NOT claimed

No eight-arm or D0-D5 comparison has run; no blind October 4/5 result exists; the live feed remains an external gate;
the critic's cycle-0 output was empty; the two-cycle run's cycle 0 is at the HOLD. Nothing in R4 passes a gate whose
passing evidence requires a result that does not exist.

Generator: the session scratch script (not committed; the change log sheet is the record).
