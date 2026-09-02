# KEY NAMES ARE HALF OF WHAT FRANKIE READS (measured 2026-09-02)

**Storage and tokens are different questions, and answering one with the other's number is
how D67 came to say aliasing saves nothing.** It saves nothing on the ledgers. It saves a
third of what the principal actually reads.

Measured on run 33605852433 - the complete Sunday session, 57,027 records, 43,569 groups -
over its real `layers.averaged_companions.rows`, counting every key at every depth.

## The measurement

| | |
|---|---:|
| averaged companion rows | **16,293** |
| compact bytes | **20,023,101** |
| distinct key names | **56** |
| key instances (all depths) | **788,868** |
| **key-name bytes** | **9,914,257 = 49.5%** |
| after 1-2 character aliasing | 3,155,472 |
| **saving** | **6,758,785 = 33.8% of the section** |

Top-level keys alone are only 7.0%. The other 42.5% is nested - `stratum`, `declaration`,
`value` and `excluded_missing_members` are objects carrying their own repeated names, and a
measurement that stops at the outer level misses six sevenths of the cost.

**The single biggest cost is the Kaplan-Meier survival object.** `at_risk`, `censored`,
`events`, `survival` and `time` each appear **41,996 times**, about 2 MB in key names
between them. That is one estimand's field vocabulary repeated across every survival
stratum in the run.

## What it means in tokens, on Sunday

At 4 bytes per token - a ratio for scale, not a claim about any tokenizer:

| | bytes | ~tokens |
|---|---:|---:|
| averaged companions | 20,023,101 | 5.01M |
| everything else (the skeleton) | 136,784 | 34k |
| after aliasing | 13,392,077 | 3.35M |
| **saved** | **6,767,808** | **1.69M** |

## D67 IS SCOPED, NOT OVERTURNED

S118 measured key names at ~0.1% of a row and concluded nova aliasing saves essentially
nothing. **That is correct for the rows it measured** - exact member rows, where `book_full`
is one enormous nested value and swamps everything around it. It is wrong for the averaged
companions, which are the opposite shape: many short values, few distinct names, hundreds of
thousands of repetitions.

So the two statements live side by side, each scoped to its subject:

- **Storage.** The ledgers are 10.8 GB and `book_full` dominates them. Aliasing saves close
  to nothing. Nothing about the disk conversation changes.
- **Tokens.** The averaged companions are the read surface - what a principal is handed.
  Aliasing removes about a third of it.

This is the session's recurring defect in its mildest form: a measurement true of its
subject, restated as a general fact about a different one. It cost nothing here because
nobody acted on it, which is luck rather than method.

## The other days, and why this number is soft

Sunday produces 0.2857 averaged rows per record; the canary's 50,001-record slice produces
0.2597. Extrapolating Sunday's rate to the 5,610,662 records of October 1, 4 and 5:

| if rows scale linearly | |
|---|---:|
| rows | ~1,603,004 |
| bytes | ~1.97 GB |
| tokens | ~492M |
| **saving at 33.8%** | **~0.67 GB, ~166M tokens** |

**Treat the absolute figures as an upper bound, not an estimate.** Averaged rows scale with
STRATA, and strata saturate: more records buy more families, more cutoffs and more sessions,
but sub-linearly, because most new records fall into strata that already exist. Both
measured points are small slices well inside the un-saturated regime, so linear projection
almost certainly overstates a full weekday.

What IS transferable is the **rate**. 33.8% is a property of the row shape - 56 names,
repeated - and the same estimands produce the same vocabulary whatever day they run on. So
the saving is about a third of whatever the averaged section turns out to be.

**One weekday traversal settles it**, and nothing else will. Until then the row count for a
full session is unmeasured, and naming a per-day byte figure with confidence would be the
215-KB-per-record error in a new costume.

## What this does not touch

`plan_retrieval` is untouched and is still where D67's real value sits. The skeleton is 137
KB; Frankie read it whole and pulled the averaged rows section by section, so the practical
cost of the Sunday run was never 5M tokens. Aliasing lowers the ceiling; declared,
refusable retrieval decides how much of the ceiling anyone ever reaches. They are
complementary and neither substitutes for the other.
