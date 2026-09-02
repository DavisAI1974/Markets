# A-clean S119 measured knowledge source

Positive, MEASURED knowledge from the first real principal run over a complete session
(run 33605852433: Sunday 2021-10-03, 57,027 records, 43,569 F_LAST groups) and from closing
the sixteen-defect register that run produced. Everything below is a number from that
artifact or a rule established by fixing it. No speculation is promoted here.

## Positive knowledge capsule candidates

1. **Two sections computing one estimand are a MEASUREMENT, not a duplication.** 4.9 and 4.12
   both compute `(bid - ask)/(bid + ask)`. On this run 4.9 returned exactly +/-1.0 on **152 of
   154** readings while 4.12 returned **[0.0116, 0.1109] on 3,454** and never approached a
   bound. One of them was reading a side-local, top-of-book view of a book stored at full
   depth. **All eight vertical section-6 gates passed**, because each checks a section against
   itself and a one-sided book is internally perfect. When two of your numbers disagree about
   one quantity, that disagreement is the most informative thing in the artifact; do not
   average them, do not pick one, name the substrate difference.

2. **The statistic that survives re-stratification is the second moment, not the mean.** Mean
   and extreme share both CANCEL under sign symmetry: a population pinned half at +1 and half
   at -1 has a mean of 0.0, and a stratum straddling both bounds yields no resolvable extremes.
   `E[x^2]` does neither. On this artifact it separates the two computations above as **0.9871
   against 0.0031**, where the mean managed 0.1291. When comparing two differently stratified
   views of one quantity, compare population-weighted `sum/n` AND `sum(sum_of_squares)/sum(n)`.

3. **A measure that ran and was handed nothing is indistinguishable from one that ran and
   found nothing.** Seven measures on this run reported an exact zero because nothing ever
   called them: the decision clock (n=0, **43,569 excluded**), phase depletion and refill (0.0
   in all **109** strata, zero exclusions), the SEARCHED phase duration (min = max = 0.0 for
   all **91** candidates), the recurrence count (min = max = 0.0 in all **28** strata), the
   4.13 censored age (n=0 against **21,651** censored), and runway completion (**91 opened, 0
   completed, 91 censored**). Before reading a zero as a finding, establish that the quantity
   had a path to the measure.

4. **A section can be BUILT and DARK, and the run still passes.** 4.2 existed as a contract
   line with no module, leaving `book_full` - **10.13 GB, 93.47% of the exact member ledger** -
   with no consumer anywhere in the artifact. 4.4's matcher was correct and was absent from the
   runner's section map entirely. **A passing verdict is not evidence that a section ran.**

5. **The censoring clock is an INPUT, never a field the subject fills in for itself.** 4.13's
   censored-age channel excluded **100%** of the censored because it derived age from an exit
   time stamped only by a qualifying successor - and a censored stage is by definition one that
   never got a successor. "Censored" and "has a duration" were mutually exclusive by
   construction. 4.6 has no such hole because its caller hands it the boundary time at the
   moment it censors.

6. **A quantity can be correctly wired, correctly attributed, and structurally unable to
   fire.** 4.8's same-side replacement numerator was 0.0 in all **205** strata, and neither
   proposed cause was right. It was scoped to a single F_LAST group, and on this tape depletion
   and same-side addition are mutually exclusive inside one: **24,617 of 43,569** runways carry
   zero depletion (pure-add groups) and the **18,952** with depletion contain no adds at all. A
   maker replacing size it just lost does so in a later group. Check the SCOPE before the
   wiring.

7. **Fixing one defect can arm a second that was inert beneath it.** 4.12 recorded **3,454
   stages and not one REVERSAL** while 4.10 recorded **90 of 91** runways as reversed, because
   each stage was filed under the previous second's phase. But the boundary-close path also
   stamped REVERSAL - harmless while the off-by-one hid it, and actively false the moment it is
   corrected, since a boundary-censored episode would then emit reversals that never happened.
   Before shipping a fix, ask what becomes reachable that was previously dead.

8. **Complementary is not independent.** 4.8's absorption and withdrawal ratios summed to
   exactly 1.0 in all **192** nonempty strata, because displayed depletion IS traded plus
   withdrawn. They carried one degree of freedom and were labelled as two coequal views
   answering different questions. Meanwhile `opposite_side_retreat_quantity` was computed for
   every group and used in no ratio at all - a genuinely free dimension sitting unused.

9. **Stratifying on a within-path index shatters the population.** 4.12 held **1,692 strata
   for 3,454 observations**, **848 at n=1**, none reaching n=30, producing 41.5% of the entire
   averaged layer to describe a population whose modal average is one member restating itself.
   The members of a stage-index stratum are the paths still running at that index, so the count
   is a SURVIVAL CURVE and any fixed bin width leaves the tail exactly where it was. Bin
   widths must double as the survivor count halves.

10. **A condition that cannot change state carries no information, and that applies to a
    stratum key as much as to a trigger.** 4.16's `starting_liquidity_regime` read
    `DEPTH_SKEW_BID` on all **84** at-risk rows. It is not a corrupted read - it uses the full
    reconstructed book - it is a bare sign comparison of two absolute depths whose sign never
    flipped on this instrument-day, corroborated by the reopen snapshot's 154 bid adds against
    90 ask and ~121 occupied bid prices against 76. A regime needs a reference it is compared
    AGAINST, not the other side of the same book.

11. **An empty string is not a declaration.** `cluster_version` was blank on **16,209 of
    16,293** averaged rows while the contract requires every average to declare it, and every
    gate passed. The absence of a statement and a statement that something did not happen are
    exactly what a declaration contract exists to separate.

12. **Diagnose at zero, because zero is when the diagnosis is needed.** 4.4 reported zero pairs
    against **3,454** unmatched stages with no distance distribution and no per-reason
    breakdown, so a total failure was visible and undiagnosable. A matcher that pairs nothing
    must still say how close the near misses came and which rule rejected each one.

13. **Where the bytes actually are.** Measured over 50,001 real records: **246,030 bytes per
    record**, of which **`book_full` alone is 94.7%** and the exact member ledger is 98.5%.
    **All sixteen calculations combined are ~1.5%**, and the most expensive of them,
    replenishment, is **0.6%**. Dropping a calculation saves essentially nothing. Separately,
    on the TOKEN surface - the averaged companions a principal actually reads - key names at
    all depths are **49.5%** of 20,023,101 compact bytes (56 names repeated 788,868 times), so
    aliasing saves about a third of what is read. **Storage and tokens are different questions
    and each measurement is true only of its own subject.**
