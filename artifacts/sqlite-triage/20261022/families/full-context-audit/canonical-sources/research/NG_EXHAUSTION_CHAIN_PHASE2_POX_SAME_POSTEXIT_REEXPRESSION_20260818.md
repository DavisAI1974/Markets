# NG Exhaustion Chain Phase 2 — P-O-X Same-Current Post-Exit Re-expression — 2026-08-18

Status: **POST-EXIT WATCH SUBTYPES CHARACTERIZED; NO NEW TRADE FROZEN.**

The parent rule remains settled: take a valid P-O-X trade, exit normally at structural endpoint `+60s`, then reset. This pass asks only what the already-observed parent path says about the unresolved same-current branch **after the position is flat**.

## Population and recovery definition

The population exactly matches the settled adverse same-current cases: 57 negative-at-`+60` P-O-X same-current parents across the 36 pre-held OOT weeks and 5 in held `20260329`.

“Recovered by +300” here means the original endpoint+5-to-horizon return is nonnegative at **either** endpoint `+120` or endpoint `+300`. It is a two-checkpoint delayed-re-expression measure, not a continuous first-passage reconstruction.

- Eras 1-3: 16/35 recovered at one of the two checkpoints (45.7%).
- Eras 4-5: 9/15 (60.0%).
- Untouched confirmation: 2/7 (28.6%).
- Combined pre-held 36 OOT weeks: 27/57 (47.4%).
- Held: 4/5 (80.0%).

The 27 pre-held recoveries are not one path shape: nine are nonnegative at +120 but negative again by +300, nine are nonnegative at +300, and the remaining nine are nonnegative at both checkpoints. That immediately blocks any interpretation of “recovery” as a guaranteed new trade.

## Exit-known path geometry splits the adverse branch

At the normal +60 exit, both the +30 and +60 parent returns are already known. Because NG returns are tick-discrete here, the clean split is:

- **shallow at +30** = no worse than `-1 tick`;
- **deep at +30** = `-2 ticks` or worse;
- **shallow adverse exit** = exactly `-1 tick` at +60;
- **deep adverse exit** = `-2 ticks` or worse at +60.

### Shallow at both +30 and +60

- Eras 1-3: 11/19 recover (57.9%).
- Eras 4-5: 7/8 (87.5%).
- Untouched confirmation: 2/3 (66.7%).
- Combined pre-held: **20/30 (66.7%)**.
- Held: **2/2**.

### Deep at both +30 and +60

- Eras 1-3: 1/7 recover (14.3%).
- Eras 4-5: 0/2.
- Untouched confirmation: 0/2.
- Combined pre-held: **1/11 (9.1%)**.
- Held: **0/1**.

Pre-held shallow-shallow versus deep-deep gives Fisher one-sided `p = 0.001281` and two-sided `p = 0.001393`. More importantly, the separation survives the later OOT blocks not used to expose the initial threshold: Eras 4-5 plus untouched confirmation are 9/11 versus 0/4 (`p = 0.01099`, one-sided). Held is too small for promotion and is reported only as forensic consistency.

The mixed geometries sit between those extremes: shallow-at-30/deep-at-60 recovers 5/13 pre-held, while deep-at-30/shallow-at-60 recovers 1/3.

## Interpretation

This gives the same-current branch a more useful post-exit decomposition:

**shallow adverse P-O-X-same** = high-priority delayed-re-expression watch;

**deep persistent adverse P-O-X-same** = low-recovery watch subtype.

Neither is an entry. The parent is already flat. A later trade still requires a trusted full SSOS or P-O-X-opposite setup under the existing reset/re-entry contract.

The guard matters. Even the shallow-shallow group has negative average +120/+300 return in parts of the historical sample because some non-recoverers are large and some early recoveries relapse. This is evidence about **probability and path state**, not a gross-return edge that authorizes buying/selling the delayed recovery directly.

The one deep-deep pre-held recovery is preserved. It is an exception to investigate, not a row to delete.

## Current state-machine picture

The P-O-X same-current branch can now be represented as:

**valid parent entry -> normal +60 exit -> classify the completed parent as shallow/mixed/deep adverse -> delayed-expression watch only -> independent trusted setup required for re-entry.**

That preserves the original mechanism, explains why many held losses later recovered, and keeps delayed expression separate from the hours-later fresh trusted re-entry chain.

Permanent Frankie, Frankie 1, the frozen detector, frozen canonical evidence, runway clock, protected spawn file, and frozen SSOS play remain unchanged.
