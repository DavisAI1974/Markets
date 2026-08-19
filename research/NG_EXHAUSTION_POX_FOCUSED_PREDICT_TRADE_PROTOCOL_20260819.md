# NG Exhaustion Focused P-O-X Predictability + Tradeability Protocol — 2026-08-19

Status: **ACTIVE ISOLATED RESEARCH CONTRACT; NO PROMOTION; NO PERMANENT FRANKIE MERGE.**

## Purpose

Continue the focused P-O-X line from the furthest completed Phase-2 work without reopening settled Phase-2 findings. The target is predictability and executable raw-tape tradeability, not retrospective relabeling.

## Immutable / protected boundary

Do not modify or retune:

- frozen exhaustion detector;
- canonical evidence rows;
- Phase-1 lineage or scores;
- finalized Phase-2 findings;
- runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

This study is additive only.

## Preserve-all POX population

The focused population is the preserve-all **3,429-case P-O-X set**. The following partition is an invariant and must fail closed if not reproduced:

- total P-O-X cases: **3,429**;
- later FLIP branch: **1,444** (42.1%);
- later SAME branch: **1,985** (57.9%).

A case is never deleted merely because it is losing, short, delayed, choppy, non-executable at an early checkpoint, or inconsistent with an aggregate rule. Checkpoint availability is a field on a preserved case, not a population filter.

The older 679-case Phase-2 P-O-X parent population remains valid historical evidence, but it is a narrower fixed-entry / causal-history subset and must not replace the 3,429-case preserve-all population in this focused study.

## State interpretation

Treat P-O-X as a state-transition problem:

1. P-O-X completes as a structural ancestry state.
2. The X event has strong near-term initial continuation behavior that must be modeled/traded separately.
3. A later successor branch resolves as FLIP or SAME relative to the X event polarity.
4. SAME may include delayed/re-expression behavior; it must not be collapsed into an immediate universal continuation rule.
5. Once a successor exhaustion is causally confirmed, prior P-O-X ancestry is not automatically inherited. Prior work rejected universal inherited state and universal next-exhaustion exit rules.

## Chronology / contamination wall

This POX study must be completed standalone before reading or using independent D0-D5 result artifacts.

Allowed inputs:

- immutable 54-week canonical event table;
- immutable held 20260329 canonical event table;
- authoritative raw NG tape for those weeks;
- previously finalized POX findings/protocol constraints.

Forbidden inputs during POX rule selection:

- D0 standalone result artifact;
- D1-D5 predictability result artifact;
- D1-D5 chain-birth result artifact;
- any rule, threshold, feature choice, or trade decision selected from those independent outcomes.

The POX-vs-D0-D5 incremental crosswalk is explicitly deferred until both sides are independently frozen.

## Population and labels

For each canonical week, preserve every consecutive canonical exhaustion triple whose states are `P,O,X` and for which the next canonical exhaustion exists before the weekly boundary.

For each preserved POX triple:

- `P`, `O`, `X` are the three consecutive exhaustion events oldest to newest;
- the next canonical exhaustion is the successor branch event;
- `FLIP` means successor polarity differs from X polarity;
- `SAME` means successor polarity equals X polarity.

The successor branch label is future information and may never be used as an input before it becomes causally observable.

## Target A — earliest causal prediction of POX itself

Build a binary predictor for whether the current third event after a causal `P,O` ancestry will finalize as `X`.

Test checkpoints in chronological order:

1. `PRIOR_PO`: after P and O state information is causally available but strictly before the current event t0;
2. `X_CONFIRM_H0`: frozen detector confirmation of the current event;
3. `X_CONFIRM_PLUS_H`: dense causal raw-tape prefixes after current confirmation at H = 1,2,3,4,5,10,15,20,30,45,60 seconds, subject to predecessor-state availability.

Do not use final X seed-state information as an input. It is the label.

The earliest validated checkpoint wins. Do not delay a valid earlier signal merely because a later checkpoint scores better.

## Target B — preserve initial X continuation

At the exact timestamp of the earliest validated POX signal, attach executable raw-tape economics in the X-event polarity direction.

Report at minimum:

- signal timestamp;
- first raw trade at/after signal as entry;
- fixed holds +5,+10,+20,+30,+60 seconds;
- gross ticks;
- net ticks under 0.5 / 1.0 / 2.0 tick round-trip stress;
- MFE / MAE;
- positive trade rate and positive-week rate;
- chronological block results;
- false-positive predictor trades as well as true POX trades.

The historical approximately 94.4% near-term sign-persistence result is a population invariant to reproduce/define precisely, not a license to assume every case wins.

## Target C — predict later FLIP vs SAME branch

Within the preserved 3,429 true POX cases, predict successor branch using only information available by each checkpoint.

Test the same dense X-confirmation checkpoints before successor t0. No successor state, polarity, seed state, or post-successor tape may enter an earlier prediction.

Record:

- earliest checkpoint with stable chronological branch-prediction value;
- calibration / AUC / Brier / log-loss against the block base rate;
- top-confidence lift;
- FLIP and SAME errors preserved separately;
- whether early branch prediction adds enough value to alter trade management.

## Target D — when branch becomes causally knowable

The branch becomes observationally known only when the successor itself satisfies the frozen detector's causal confirmation. Before that point it can only be predicted.

Record the distribution of:

- X signal -> successor t0;
- X signal -> successor confirmation;
- X +60 checkpoint -> successor confirmation.

Never backdate successor knowledge.

## Target E — hold / exit / reset / re-entry

Compare, without post-hoc deletion:

- fixed initial continuation holds;
- exit at successor causal confirmation when it arrives before a planned hold;
- continue old X direction through successor confirmation;
- reverse old X direction at successor confirmation;
- follow successor polarity from successor confirmation;
- stand down at successor confirmation.

A successor exhaustion is a **new causal state checkpoint**. Prior P-O-X ancestry is not inherited automatically.

A universal action is valid only if it improves/stabilizes across chronological OOT blocks. Otherwise the state-machine action remains conditional/unresolved.

For SAME/delayed re-expression, test post-+60 watch/re-entry separately. A delayed recovery observation is not allowed to rewrite the original entry or erase the original loss.

## Model / validation discipline

Use time-ordered blocks only. The earliest 18 pre-held weeks are research/training; later pre-held blocks and untouched confirmation are OOT checks; held 20260329 remains a final forensic check and is not a threshold-selection fold.

Model parameters and confidence thresholds must be selected without held information. Any rule that changes sign, loses net expectancy after realistic cost stress, or fails a later block is retained as a failed/conditional rule under:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

No result from this pass is promoted into a frozen play. Fresh prospective/OOT validation is required before promotion.

## Required durable outputs

Produce:

1. machine-readable preserve-all case ledger;
2. POX predictor results;
3. initial-continuation trade economics;
4. FLIP-vs-SAME branch predictor results;
5. successor checkpoint action economics;
6. delayed/re-expression watch results;
7. failed/conditional rule ledger;
8. brain proposal — proposal only;
9. separate trade-strategy proposal — proposal only;
10. explicit deferred D0-D5 incremental crosswalk marker.

No permanent Frankie merge and no frozen-play mutation are authorized by this protocol.
