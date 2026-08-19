# NG Exhaustion D1-D5 Predictability Timing Grid — 2026-08-19

Status: **AUTHORITATIVE TIMING CONTRACT FOR THE ENTRY-TIMING REVIVAL. PRESERVE ALL D1-D5. PHASE 2 REMAINS FROZEN.**

## Purpose

Determine, for every preserved exact D1-D5 chain/behavior, the **earliest causal moment at which the already-defined behavior becomes predictably callable**.

The answer may differ by D, motif, subfamily, timing family, regime, or true/false context. A behavior may validate:

1. **PRIOR** — before the target exhaustion begins, from already-causal predecessor-chain information;
2. **AT DETECTION** — when the target exhaustion itself becomes causally known under the frozen detector;
3. **AFTER DETECTION** — only after the target/setup has survived for one or more H seconds and new causal information has accumulated;
4. **NEVER ACTIONABLE** — no tested causal point validates. The row is still preserved.

**Earliest validated predictability wins.** If a behavior validates prior to the target, do not delay it to target detection. If it first validates at target detection, do not delay it. If it needs survival, use the first H checkpoint that validates.

This contract does not redefine direction, chain structure, D1-D5 membership, Phase-2 findings, the frozen detector, or the runway clock.

## Frozen populations

| Exact depth | Preserved population |
|---|---:|
| D1 | 18,837 forward-OOT exact D1 |
| D2 | 1,592 |
| D3 | 124 |
| D4 | 8 |
| D5 | 1 |

The first 18 base weeks remain `PRELINEAGE_UNLABELED` for exact-D1 membership unless a separately validated reverse backcast succeeds.

## Authoritative H grid — applies to every D1-D5 timing test

The active H values are:

`H = 1, 2, 3, 4, 5, 10, 15 seconds`

then every five seconds thereafter:

`H = 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, ...`

For the current authorized study, continue the five-second grid through:

`H = 3600 seconds`

where the structure is still alive and the necessary information/tape exists.

Equivalently:

`H_GRID = [1,2,3,4,5,10,15] + range(20,3601,5)`

This same H grid is used for **D1, D2, D3, D4, and D5**. No D gets a coarser timing lattice merely because it is deeper or lower-support.

The older coarse values `5,10,20,30,60,120,300` are retained only as historical audit/reference points from earlier work. They are **not the active H grid for this predictability study**.

## Clock definitions

### Target onset: `TARGET_T0`

The frozen canonical `t0_idx` is the retrospective onset of the target exhaustion. It is not automatically a live decision input.

### Target detector-known clock: `TARGET_DETECTOR_KNOWN = +0`

`+0` means the frozen detector's causal confirmation of the target exhaustion, i.e. the target row's frozen `dynamic_endpoint.causal_confirmation_idx`.

Do not substitute retrospective target onset for detector confirmation.

### H on predecessor information — PRIOR test

For predecessor `j` at active horizon `H`:

`PREDECESSOR_READY(j,H) = predecessor_j.causal_confirmation_idx + H`

For a D-depth rule requiring D predecessor states:

`RULE_READY(D,H) = max(PREDECESSOR_READY(j,H) for all required predecessors j)`

A candidate is **PRIOR at H** only when the complete information required by that rule is causally ready before the target begins:

`RULE_READY(D,H) <= TARGET_T0`

Record:

`PRIOR_LEAD_SECONDS = TARGET_T0 - RULE_READY(D,H)`

Test H in ascending order. The first chronologically/OOT validated H is the winning prior horizon.

Availability is not predictive skill. An H value being available before target t0 only makes that H eligible for a causal predictability test.

### H after target detection — survival/update test

If no PRIOR H validates and the behavior does not validate at `+0`, use the **same H grid** after `TARGET_DETECTOR_KNOWN`:

`+1,+2,+3,+4,+5,+10,+15,+20,+25,+30,...,+3600`

At each H use only information available by that checkpoint plus the causal fact that the target/setup has survived to H. Never leak later survival, final duration, final depth, descendant identity, or future path shape backward.

## Required timing values for every D

| D | Preserved n | PRIOR H values | Detection | AFTER-DETECTION H values |
|---|---:|---|---|---|
| D1 | 18,837 | `1,2,3,4,5,10,15,20,25,...,3600` | `+0` | `1,2,3,4,5,10,15,20,25,...,3600` |
| D2 | 1,592 | `1,2,3,4,5,10,15,20,25,...,3600` | `+0` | same H grid |
| D3 | 124 | `1,2,3,4,5,10,15,20,25,...,3600` | `+0` | same H grid |
| D4 | 8 | `1,2,3,4,5,10,15,20,25,...,3600` | `+0` | same H grid; low support labeled, never erased |
| D5 | 1 | `1,2,3,4,5,10,15,20,25,...,3600` | `+0` | same H grid; case study only, no universal law |

The search order for every D is therefore:

**earliest eligible PRIOR H -> later PRIOR H values as needed -> +0 target detector confirmation -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> ... -> +3600**

Stop searching later timing for a rule once an earlier point has genuinely validated under the predeclared chronological/OOT standard, except to retain later checkpoints as confirmation/alternative measurements. Later confirmation does not replace the earliest valid call.

## D-specific interpretation

### D1

Test when the already-defined D1 descendant behavior becomes predictable from the D1 origin/predecessor context. A D1 can be PRIOR if an H snapshot of its origin is causally complete and predictive before the descendant begins. Otherwise test the descendant at +0 and then the H grid after detection.

### D2

For a D2 rule, all required predecessor information for that rule must be causal at the tested H. Find whether the second-order behavior is predictable prior, at +0, or only after one of the H survival checkpoints.

### D3

Apply the identical H grid to all three required predecessor states. Preserve any earlier predictability; do not assume D3 must be later merely because it is deeper.

### D4

Apply the identical H grid to all four required predecessor states. The sample is small, so results must be labeled low-support rather than generalized or discarded.

### D5

Apply the identical H grid to all five required predecessor states. Preserve the single case and its timing result, but do not infer a universal D5 timing law from n=1.

## Historical h=5 availability reference — reference only

The existing higher-order availability audit at old `h=5` remains useful as a historical reference:

- D2: 1,059/1,592 ready before target t0;
- D3: 80/124;
- D4: 6/8;
- D5: 1/1.

This does not authorize skipping H=1,2,3,4 in the new timing study and does not prove predictive skill at H=5.

## Agent output required for every D1-D5 rule/subfamily

For every preserved rule/subfamily, output:

- exact D depth;
- support and weeks;
- every tested H in chronological order;
- earliest validated timing class: `PRIOR`, `AT_DETECTION`, `POST_DETECTION`, or `NO_VALIDATED_ACTIONABLE_POINT`;
- if `PRIOR`: winning H, `RULE_READY` timestamp, and actual lead seconds to target t0;
- if `AT_DETECTION`: +0 result;
- if `POST_DETECTION`: first validating H from the active dense grid;
- all earlier tested H/checkpoints and why they failed;
- remaining structural runway/opportunity at the winning time;
- chronological/OOT stability and held behavior where applicable;
- true/false/context decomposition under `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`;
- explicit leakage audit.

## Protected boundaries

Do not modify or retune the frozen exhaustion detector, canonical 54-week base or held rows, frozen Phase-1 lineage/scores, finalized Phase-2 findings/freeze, frozen exhaustion runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS paper play.

Do not use later signed-direction Lane 3/4 detours or subsequent reframing to redefine this timing program.

No permanent brain merge and no play freeze are authorized from this historical timing study.
