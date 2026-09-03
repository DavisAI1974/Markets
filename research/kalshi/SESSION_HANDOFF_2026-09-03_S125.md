# SESSION HANDOFF 2026-09-03 S125 - FRANKIE RAN, SUNDAY TRAVERSED AND UPLOADED NOTHING

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Last code commit: `7b7400b`
(census v10); the docs commits sit on top of it, so read the branch head rather than a
hash written before the commit that carries it.
2,021 tests / 6,433 subtests green. D61 adapter hash unchanged
(`4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`).

## 0. THE STATE IN ONE PARAGRAPH

The canary ran and was ACCEPTED - the first traversal ever completed on this lineage - and all
four falsifiers were answered on it. The full Sunday was then dispatched to the box at
`mode=full`, and it TRAVERSED but delivered nothing durable: every object at its prefix is
timestamped at staging time, and `ledgers/`, `calculation_result.json`,
`small_artifacts.tar.gz` and `PLAIN_SHA256SUMS` are all absent. The most likely cause is
already recorded in this repo's own history - the box instance role has no S3 write - and the
results are probably still on the box's 300 GB volume. **That is item zero and it is Greg's,
because granting an account-level role new permissions is not a session's call.** Separately,
the field census - 78% of the traversal at the time it was measured - is now 11.98x faster and
byte-identical, verified against a pinned reference implementation on 25 adversarial shapes.

## 1. THE CANARY - ACCEPTED, AND WHAT IT SAID

Run 33745123325-1, commit `7d0068d`, prefix

    nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/7d0068d8ae720772415bf84c8c0689e84408d642/33745123325-1/canary/

- verdict ACCEPTED, **0 failed gates**, 18 of 18 contract sections fed.
- `candidates_without_stratum: 0` - a defect COUNT reading zero, i.e. the healthy outcome.
  Recorded because I first labelled it "NOT fed" by applying falsiness to a map of counts.
- **F-20 PASS**: `withheld_no_own_clock` 0 and `withheld_close_occasion` 0, against 43,569 and
  65,960 before the wiring. This is the first time the falsifier has been ANSWERABLE at all.
- **F-30 PASS**: `raw_actions` PRESENT on the member row.
- **F-26 PASS**: `activity_since` PRESENT on the event anchors.
- **4.16**: 51 change-point tracks.

## 2. SUNDAY - THE BLOCKER, WITH THE EVIDENCE

Run 33746436209, `mode=full`, source `glbx-mdp3-20211003.mbo.dbn.zst` (57,027 records).

Every object under the run prefix carries the SAME timestamp, 11:01:49, which is the staging
write. Present: `checkpoints/adapter-state-000000.json`, `checkpoint-000000.json`,
`FILE_SHA256SUMS`, `chat_packet_contract.json`, `launch_receipt.json`, `source_manifest.json`,
`sources/*.dbn.zst`. **Absent: `ledgers/`, `calculation_result.json`, `small_artifacts.tar.gz`,
`PLAIN_SHA256SUMS`.**

The box was observed at 99.9% CPU, 8m48s of CPU time and 3.7 GB RSS at 11:07, and had no
CPU-burning process by 12:19. So it ran and finished or died; it did not hang.

The cause is named in `research/kalshi/FRANKIE_A_ARM_FULL_DISPATCH_BLOCKER_20260830.md`:

> the box role has no S3 access at all ... A run ending A_ARM_RESULTS_ON_BOX is a finished
> traversal and an unfinished run.

Reads are worked around with an inline manifest and presigned GETs. **The UPLOAD cannot be.**
The scoped policy that fixes it is written in that file and NOT applied.

SSM command id for the dispatch: `9c8fc423-16b7-4435-bab8-b6368424b691`.

**What to do first next session:** check the box volume for the ledgers before re-running
anything. A completed traversal sitting on a disk is not a failed run, it is an undelivered
one, and re-running it burns the spend twice.

## 3. F-20 ON SUNDAY - STILL OWED

The stream receipt workflow `.github/workflows/frankie_stream_receipt_20260903.yml` exists and
was proven on the canary. It handles a gzipped box ledger and verifies the decompressed bytes
against the box's own `PLAIN_SHA256SUMS`. It CANNOT run on Sunday until the ledgers are
retrievable. Pass `subdir: ROOT` for a box run - see section 6.

## 4. THE CENSUS - 1.00x TO 11.98x, BYTE-IDENTICAL

Measured on a real 181,380-byte member row, best of three, 20 rows per trial:

    ORIGINAL (pre-optimisation)     41.5 rows/sec    1.00x
    v9 as committed                388.1 rows/sec    9.36x
    HEAD (v10)                     496.8 rows/sec   11.98x

Byte-identical summary against the pre-optimisation walk at every step. The ladder, stacked:
per-list field lookup and `touched` add hoisted out of the element loop; whole-column folding
with C builtins; a transpose branch for the list-of-dicts shape (a ladder is hundreds of
sibling level dicts with the same keys); sibling-list CONCATENATION so a ladder's hundreds of
per-level `orders` lists become one walk; the type-set tests replacing per-element genexprs;
and the bulk `set.update` for `distinct`.

**TWO EXPERIMENTS WERE REVERTED, and they are recorded so nobody re-runs them.** A path-string
cache measured 1.73x against the 1.82x it replaced - slower, because the f-string it avoided
is cheaper than the dict lookup that replaced it. A generation stamp to avoid re-hashing paths
gained nothing, because CPython caches a string's hash after first use, so there was nothing
to save.

**THE DIFFERENTIAL IS THE REASON ANY OF THIS IS TRUSTABLE**, and it had to be fixed twice.
`tests/test_native_mbo_field_census_differential.py` pins a `ReferenceCensus` with its OWN
`_RefField` - a copy of the pre-optimisation field - against the live class over 25 adversarial
shapes. The first version subclassed `MboFieldCensus` and reused the LIVE `_Field`, so a defect
injected into `_Field` cancelled on both sides and the differential was blind to it. The
reviewer proved that by injection. Second gap: the corpus had no empty list, which is exactly
the defect I shipped (below).

## 5. THE BUG I SHIPPED, AND THE ONE I ALMOST SHIPPED

**C1, real, found by the code-reviewer.** Hoisting `touched.add(path)` out of the element loop
was wrong for an EMPTY list: the original never reached `<path>[]` at all, the optimised
version invented a field with zero observations, and the row then counted as carrying a field
it does not carry. Present-but-empty reading as present is the exact collapse the module's
docstring exists to prevent. `confirmed_at_this_cutoff` is `[]` on every group with no 4.11
call, and it is live at `native_clocks.py:559`. Fixed with an early return, and the fix
measured FASTER.

**The `--emit-change-points` flag does not exist** - the launcher has `--no-change-points`. The
launch workflow set the wrong polarity at TWO sites, and the second was inside the box-dispatch
Python heredoc, which would have burned the spend. Fixed at both. A regression test now runs
every flag the workflow passes against the launcher's `--help`, verified RED before green.

**`REQUIRED_STARTING_TIP` was unreachable** - pinned to `82e1405`, which is on a disjoint
history. Repinned to `cd0d7a5` on Greg's call.

## 6. THREE GITHUB ACTIONS GOTCHAS, EACH MEASURED THE HARD WAY

I got the `subdir` input wrong THREE times in a row. Recording all three because the first two
diagnoses were plausible and wrong.

1. **An empty workflow input never arrives.** GitHub substitutes the input's own `default:`
   before any expression sees it. Passing `subdir: ""` reached the job as `canary` and 404'd
   on a path a box run never writes.
2. **`a && b || c` cannot carry a falsy value.** `X && '' || Y` yields `Y`, because the empty
   result is falsy and `||` takes the alternative. So an expression can never produce `""`,
   and rewriting the condition cannot beat that.
3. **The fix is to translate in bash, not in the expression.** The value passes through
   verbatim and the step turns the literal `ROOT` into `""`.

Both `frankie_canary_result_read_20260903.yml` and `frankie_stream_receipt_20260903.yml` carry
this as a comment block at the `SUBDIR` env.

## 7. PARALLELISM - THE FIGURE ON RECORD IS STALE

The profile workflow `.github/workflows/frankie_traversal_profile_20260903.yml` buckets cost by
the file the code lives in and computes the Amdahl ceiling on 8 cores. It measured the census
at 78% of the traversal and a **1.04x** parallel ceiling, i.e. a process pool buys nothing.

**That 1.04x is now stale.** The census is 11.98x faster, so it is no longer 78% of anything,
and at HEAD the ceiling is roughly 4.3x. Also, **~26% of the run was never attributed to any
bucket and was never decomposed.** RE-PROFILE BEFORE OPTIMISING FURTHER. Do not quote 1.04x.

Order-book reconstruction remains genuinely serial - `adapter.apply` mutates `book_full`, FIFO
priority and the native priority ids on every record, so record N+1 depends on record N. That
part no core count helps.

## 8. THE ROSTER AND ITS EXACT SIZES

Read off the source manifest, not estimated:

    glbx-mdp3-20211003.mbo.dbn.zst     57,027 records   rec/byte 0.058   Sunday, position 1
    glbx-mdp3-20211001.mbo.dbn.zst  1,504,374 records   rec/byte 0.059
    glbx-mdp3-20211004.mbo.dbn.zst  1,994,358 records   rec/byte 0.058
    glbx-mdp3-20211005.mbo.dbn.zst  2,111,930 records   rec/byte 0.059
    TOTAL                           5,667,689 records

Records per byte is 0.058-0.059 on all four, so compressed size IS a fair proxy here - but it
was checked rather than assumed, because the earlier runtime projection split the roster total
in proportion to compressed bytes without verifying that.

Greg's roster ruling, verbatim: *"we had sun, mon, tues and wed. stick with those regardless of
what anything else says"* and *"we're doing the Sunday first because it's small"*.

**CARRY-GATE CAVEAT:** Sunday is roster position 1, so while Oct 1's artifact is `MISSING`,
`build_finding_memory` raises `SeedBuildError`. That is the carry refusing a later day while an
earlier artifact is absent, working as designed. It is not a defect and must not be relaxed.

## 9. OPEN REVIEW ITEMS

- **O1** - the dispatch rule now exists in three copies (canary bash, box-dispatch heredoc,
  regression test). Three copies is how a polarity bug survives a fix at one site.
- **O4** - there is no census off switch. Likely closeable now that the census is 12x cheaper;
  confirm against a re-profile rather than by argument.
- The reviewer's Gap A and Gap B corpus additions for the differential.

## 10. THE ORPHANED COMMITS

Roughly 50 commits from lineage `d5b7b51` sit on no remote branch and are GC-eligible. Named
here so their disappearance is not later mistaken for a loss.
