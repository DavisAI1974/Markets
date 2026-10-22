# NG Exhaustion Chain Phase 2 — P-O-X Branch Reconciliation V2 — 2026-08-18

## Disposition

`P,O,X` remains active. No valid historical or held instance has been removed.

The correct posture is now:

- broad `P,O,X`: **keep and continue investigating**;
- `X -> opposite-polarity current`: **priority executable candidate, not yet frozen**;
- `X -> same-polarity current`: **active timing/re-origin branch under review**;
- losing instances: **preserved as boundary evidence**;
- one failed fold: **never an automatic kill condition**.

This does not change Phase 1, the detector, the 54-week base, held rows, the runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the already frozen SSOS paper play.

## All instances remain

The canonical population contains 666 valid `P,O,X` instances in the frozen 54-week base and 13 valid insert-only held-week instances, for 679 total observations available to this characterization. Zero valid instances were deleted.

The held 13 contain five negative, five flat, and three positive fixed-+60 outcomes. The negative held aggregate is therefore real evidence, but it is not a license to discard the observations that disagree with the earlier aggregate rule.

## The held failure is a branch fork

Current polarity relative to the latest X predecessor was already a permitted Phase-2 branch and is known at current `t0`.

### X -> opposite-polarity current

Gross +60 means from endpoint +5 entry:

- Eras 1–3: n=103, `+0.583t`
- Eras 4–5: n=65, `+0.108t`
- untouched confirmation: n=39, `+0.410t`
- held 20260329: n=6, `+0.500t`, **zero losing cases**

Across the 36 pre-held OOT weeks, this branch has n=207, gross mean `+0.401t`, same-week-demeaned mean `+0.340t`, 66.7% positive week deltas, and one-sided week sign-flip p≈`0.0122`.

The held exact same-week circular-shift p is only ≈`0.297`, so the six held observations are not enough to freeze a new play. But this is plainly not a held-only survivor: it was positive in every pre-held aggregate block and remained positive in the insertion.

### X -> same-polarity current

- Eras 1–3: n=106, `+0.283t`
- Eras 4–5: n=75, `+0.280t`
- untouched confirmation: n=39, `+0.487t`
- held: n=7, `-0.857t`

This is where all of the held reversal lives.

Inside the held week, the opposite-minus-same branch difference is about `+1.357t`. An exact permutation over the six-versus-seven branch labels gives two-sided p≈`0.0454`. That is forensic evidence of a structured branch split; it is not permission to optimize a new rule on the held week.

## The same-polarity branch looks mistimed, not simply absent

Held mean path from the fixed endpoint+5 entry:

| branch | +10 | +20 | +30 | +60 | +120 | +300 |
|---|---:|---:|---:|---:|---:|---:|
| X -> opposite current | 0.000 | +0.167 | +0.333 | +0.500 | +0.833 | 0.000 |
| X -> same current | 0.000 | -0.286 | -0.714 | -0.857 | -0.286 | **+0.571** |

The same branch therefore goes adverse after +10, bottoms around the original +60 decision horizon, then turns positive in aggregate by +300.

Of the five held same-branch cases that were negative at +60, four were nonnegative by +300 and two were outright positive. In the pre-held OOT sample, only 18 of 57 same-branch negative-at-60 cases were nonnegative by +300. The exploratory Fisher two-sided p for that recovery-rate difference is ≈`0.0493`.

This is not a basis for a new held-selected 300-second trade. It is evidence that calling the branch “dead” at +60 loses information about a delayed/re-origin family.

## New exhaustions are state transitions, not automatic invalidations

Every one of the five held same-branch +60 losers had another exhaustion start before the fixed +60 exit.

But successor-before-exit is not a universal invalidation historically. The effect depends on how the new exhaustion resolves relative to the current state. Therefore a future successor may be used only when it becomes observable, as a new causal checkpoint for **continue / reset / reverse / stand-down** semantics.

It may not be leaked backward into the original entry decision.

Tracing the five held +60 losers through their next exhaustion events shows that four are nonnegative by +300 despite their +60 loss. That is exactly the kind of rolling/re-origin behavior Phase 2 was designed to uncover.

## We did not find a legitimate post-hoc deletion rule

An exploratory threshold search examined causal-at-entry current timing/detector fields plus predecessor timing, flow, book, prominence, and already-available post-end history. Thresholds were selected from Eras 1–3 and inspected on Eras 4–5, untouched confirmation, and held.

No simple rule that retained at least two held same-branch observations stayed positive across all four blocks. In other words, there is no defensible one-variable carve-out that lets us label the losing held rows “invalid.”

They stay.

## Additional hypothesis: absolute polarity

A post-hoc split worth carrying forward—but **not promoting yet**—is absolute current polarity.

For `X -> opposite-current` with current DOWN polarity, gross means were approximately:

- Eras 1–3 `+0.696t`
- Eras 4–5 `+0.179t`
- confirmation `+0.650t`
- held `+0.600t` (n=5)

The same-current DOWN branch had already deteriorated before held: about `+0.217t`, `0.000t`, `-0.231t`, then `-1.667t` held.

Controlling against the same-week universe with the same current polarity does not remove the opposite-DOWN advantage. Still, absolute polarity was not the predeclared disposition split, so this remains a hypothesis requiring new OOT evidence.

## Next action

The strongest honest next test is not to delete anything. It is to build the `P,O,X` state transition forward:

1. preserve the original P-O-X identity;
2. branch at current `t0` by the already-allowed X→same versus X→opposite relation;
3. once a successor exhaustion actually appears, treat it as a new causal state checkpoint;
4. test whether the state should continue, reset, reverse, or become a fresh first-order chain;
5. separately discover the delayed-expression family instead of forcing every valid instance into a fixed +60 outcome.

Machine-readable record: `research/NG_EXHAUSTION_CHAIN_PHASE2_POX_BRANCH_RECONCILIATION_V2_20260818.json`.
