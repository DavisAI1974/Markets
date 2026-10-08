# Independent RE-REVIEW, pass 2: the fixes for B1-B7 of REVIEW_20261008_FLEET_SOURCE.md (2026-10-08; READ-ONLY, this file only)

Scope: branch `ccr-d2f8f826-iefeah-frankie`, fix commits 0c1b9d6c, 73293c51, cda7b0e3, b11b541d, c914f658 (tip read:
a62862b5, which adds only a box snapshot record on top of c914f658). Inputs read: the original review (B1-B7 and their
scenarios), the findings table in FLEET_SOURCE_STATUS_SESSION8.md, the slice-(f) section of E2E_ONE_DAY_20231018.md,
then `git diff 90e46f33..c914f658` on the six fleet files, the toys `tests/test_frankie_*fleet*.py`
(run: `python -m unittest discover -s tests -p 'test_frankie_*fleet*.py'` -> 64 tests OK, 0.5 s), and the call sites
into the queue / cores / experiment modules where a fix depends on them. Nothing run on a box, no AWS call.
Line numbers are those of tip c914f658 unless a file is named at another commit.

Method per B item: the ORIGINAL scenario re-traced against the new code (CLOSED / STILL OPEN / PARTIALLY with file:line),
then what the fix introduced. Findings are written incrementally below as each item is traced.

---------------------------------------------------------------------------------------------------------------------------
