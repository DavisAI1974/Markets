# SUNDAY, RERUN ON THE CORRECTED CODE, WITH BOTH REDUCERS ON (measured 2026-09-02)

**Run 33630348943, commit `2dd7044`, box `i-08cee7171c0a76a04`, `mode=full`, one roster
object (`glbx-mdp3-20211003.mbo.dbn.zst`).** Independent witness: **CONFIRMED**.

This is the first Sunday traversal on code carrying all sixteen S119 defect fixes. Run
33605852433, which every prior number came from, was produced BEFORE them.

## What it cost

| | |
|---|---:|
| records / groups | **57,027 / 43,569** |
| `exact_member_ledger` | 10,630,127,166 |
| `exact_lifecycle_and_runway_ledger` | 265,048,572 |
| `legacy_observable_rows` | 29,329,182 |
| **total ledger bytes** | **10,924,504,920** |
| **bytes per record** | **191,567 (187.1 KiB)** |

Records and groups are IDENTICAL to the pre-fix run, so the corrected code traversed exactly
the same day to the same coverage. Every ledger's sink count matches the box's independent
`wc -c`, delta +0 on all three, and the three record counts agree.

**The projection was 28% high.** S118/S119 put Sunday at 14.0 GB from a per-record constant
of 246 KiB; it came in at 10.92 GB and 187.1 KiB. **This is not a reduction and must not be
reported as one** - the 246 KiB was measured on a 50,001-record canary over the opening of
the roster, and this is a complete session. They measure different things. What it does mean
is that the disk precheck is conservative, which is the safe direction to be wrong in.

## The read surface, which is a different question from the disk

| | |
|---|---:|
| averaged companion rows | **13,136** |
| key alias form | **ALIASED** |
| compact bytes as written | **12,365,788** |
| the same rows unaliased | **17,914,881** |
| **saved by aliasing** | **5,549,093 (31.0%)** |
| names aliased | 55 |

Measured by decoding this run's own rows with its own legend, not extrapolated. At 4 bytes
per token - a ratio for scale, not a claim about any tokenizer - that is about **1.39M
tokens** on Sunday.

**The S119 hand measurement said 33.8% and ~1.69M tokens. The real run says 31.0% and
~1.39M.** The rate was close; the total was high because the row count fell, 16,293 to
13,136. That is the fixes changing stratification - D-12 binned the stage index into closed
octaves, which collapses strata - and it is a real effect of the corrections rather than a
measurement error.

## 4.16 fired

**88,071 event-driven change points, status FED_BY_THE_TRAVERSAL**, from 91 tracks.

`observe_change_point` had no caller anywhere until S120, so run 33605852433 emitted only
the fixed horizons and the section correctly declared NOT_FED_BY_THE_TRAVERSAL. This is the
first run in which the other half of 4.16's emission rule has ever executed.

**The size decision it raised is answered by measurement.** Retained volume becomes
(open tracks x changes), and the whole lifecycle ledger that carries them is 265 MB - **2.4%
of the run**, against `exact_member_ledger` at 97.3%. Change points are affordable on this
slice. A weekday is ~100x the records and the rate is unmeasured, so this bounds Sunday and
projects nothing.

## Why the two reducers do not confound

Aliasing changes `layers.averaged_companions` in the result JSON. Change points change the
response section's rows on disk. Different places, separately attributable, so "the net
effect" was never a number anyone had to disentangle - which is why both could ship in one
run without spoiling either measurement.

## What is NOT settled here

- **The weekday row count.** Averaged rows scale with STRATA and strata saturate, so
  projecting Sunday's rate onto a full weekday overstates it. One weekday traversal settles
  it and nothing else will.
- **`plan_retrieval` is still untouched**, and D67's real value still sits there. Aliasing
  lowers the ceiling; declared refusable retrieval decides how much of the ceiling anyone
  reaches. They are complementary.
- **The drop question (D68/D76).** Nothing here recommends dropping anything. All sixteen
  calculations remain a small share of the bytes and `exact_member_ledger` remains the only
  thing with mass. Keep-everything is a first-class outcome.
