# NG Exhaustion D1-D5 Predictability Timing Grid — 2026-08-19

Status: **AUTHORITATIVE TIMING CONTRACT FOR THE ENTRY-TIMING REVIVAL. PRESERVE ALL D1-D5. PHASE 2 REMAINS FROZEN.**

## Purpose

Determine, for every preserved exact D1-D5 chain/behavior, the **earliest causal moment at which the already-defined behavior becomes predictably callable**.

The answer is allowed to differ by D, motif, subfamily, timing family, regime, or true/false context. A behavior may validate:

1. **PRIOR** — before the target exhaustion begins, from already-causal predecessor-chain information;
2. **AT DETECTION** — when the target exhaustion itself becomes causally known under the frozen detector;
3. **AFTER DETECTION** — only after the target/setup has survived for one or more seconds and new causal information has accumulated;
4. **NEVER ACTIONABLE** — no tested causal point validates with enough remaining runway/edge. The row is still preserved.

**Earliest validated predictability wins.** If a behavior is predictable prior to the target, do not delay it to target detection. If it first validates at target detection, do not delay it to +5 or +10. If it needs survival, use the first post-detection checkpoint that validates.

This contract does not redefine direction, chain structure, D1-D5 membership, Phase-2 findings, the frozen detector, or the runway clock.

## Frozen populations

| Exact depth | Preserved population | Meaning for this timing study |
|---|---:|---|
| D1 | 18,837 forward-OOT exact D1 | one-link chain population; test when its already-defined descendant behavior becomes predictable |
| D2 | 1,592 | two-link preserved chain population |
| D3 | 124 | three-link preserved chain population |
| D4 | 8 | four-link preserved chain population; low support must be labeled, never erased |
| D5 | 1 | five-link preserved chain population; case study only, no universal law from n=1 |

The first 18 base weeks remain `PRELINEAGE_UNLABELED` for exact-D1 membership unless a separately validated reverse backcast succeeds. They may not be manufactured into forward-OOT D1 labels.

## Clock definitions

### Target onset: `TARGET_T0`

The frozen canonical `t0_idx` is the retrospective onset of the target exhaustion. It is not automatically a live decision input.

### Target detector-known clock: `TARGET_DETECTOR_KNOWN = +0`

For post-target timing, **+0 means the frozen detector's causal confirmation of the target exhaustion**, i.e. the target row's frozen `dynamic_endpoint.causal_confirmation_idx` under the existing detector contract.

Do not substitute retrospective target onset for detector confirmation.

### Prior predecessor-information clocks

For each predecessor required by a D-depth rule, test the already-frozen aftermath information horizons:

`h = 5, 10, 20, 30, 60, 120, 300 seconds`

For predecessor `j` at horizon `h`:

`PREDECESSOR_READY(j,h) = predecessor_j.causal_confirmation_idx + h`

For a D-depth rule requiring D predecessor states:

`RULE_READY(D,h) = max(PREDECESSOR_READY(j,h) for all required predecessors j)`

A candidate is **PRIOR** at horizon `h` only when the information needed by that rule is causally ready before the target begins:

`RULE_READY(D,h) <= TARGET_T0`

Record the actual causal lead:

`PRIOR_LEAD_SECONDS = TARGET_T0 - RULE_READY(D,h)`

Do not invent a synthetic negative-time grid. Prior lead is whatever the frozen predecessor clocks actually provide.

A predecessor-information horizon being available is **not** proof of predictive skill. Each horizon must be tested chronologically/OOT.

## Universal post-detection checkpoint grid

For every D1-D5 rule that does **not** validate prior and does **not** validate at target detector confirmation, test survival/update checkpoints from the applicable causal clock at:

`+1, +2, +3, +4, +5, +10, +15 seconds`

then **every 5 seconds thereafter**:

`+20, +25, +30, +35, +40, ... , +3600 seconds`

where the setup is still structurally alive and the required tape/information exists.

`+0` is always measured separately as the target detector-confirmation decision point.

Thus the full default target-relative search is:

`PRIOR via h=5/10/20/30/60/120/300 -> +0 -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> ... -> +3600`

Longer checkpoints may be added where support exists, but they may not replace the dense grid through +3600.

## Required timing values for every D

| D | PRIOR search | At target detection | Post-detection search |
|---|---|---|---|
| D1 | test predecessor/origin information at `h=5,10,20,30,60,120,300`; if the required D1 information is ready before its target descendant `t0`, record actual prior lead | `+0` at frozen target detector confirmation | `+1,+2,+3,+4,+5,+10,+15`, then every `+5s` from `+20` through `+3600` while alive |
| D2 | test both required predecessor states at `h=5,10,20,30,60,120,300`; PRIOR only when the complete rule is ready before target `t0` | `+0` | same dense grid through `+3600` |
| D3 | test all three required predecessor states at `h=5,10,20,30,60,120,300`; PRIOR only when the complete rule is ready before target `t0` | `+0` | same dense grid through `+3600` |
| D4 | test all four required predecessor states at `h=5,10,20,30,60,120,300`; preserve low support | `+0` | same dense grid through `+3600`; label low support rather than force a timing law |
| D5 | test all five required predecessor states at `h=5,10,20,30,60,120,300`; preserve n=1 as a case | `+0` | same dense grid through `+3600`; no universal timing law from the single case |

## Existing D2-D5 h=5 availability reference — availability only

The already-complete higher-order availability audit may be used only to locate possible prior/early clocks. It must not be mistaken for predictive proof.

At predecessor horizon `h=5`:

| D | Ready before target `t0` | Additional ready by target endpoint+5 | Additional ready by endpoint+60 | Total |
|---|---:|---:|---:|---:|
| D2 | 1,059 | 531 | 2 | 1,592 |
| D3 | 80 | 43 | 1 | 124 |
| D4 | 6 | 2 | 0 | 8 |
| D5 | 1 | 0 | 0 | 1 |

Combined: `1,146/1,725` D2-D5 cases have all required h=5 predecessor information before the target `t0`; `1,722/1,725` are ready by target endpoint+5; all `1,725/1,725` are ready by target endpoint+60.

These values answer only **when information exists**, not whether the behavior is predictable from it.

D1 prior availability must be measured directly under this timing program rather than inferred from the D2+ audit.

## Agent output required for every D1-D5 rule/subfamily

For every preserved rule/subfamily, output:

- exact D depth;
- support and weeks;
- earliest validated timing class: `PRIOR`, `AT_DETECTION`, `POST_DETECTION`, or `NO_VALIDATED_ACTIONABLE_POINT`;
- if `PRIOR`: winning predecessor horizon `h`, `RULE_READY` timestamp, and actual lead seconds to target `t0`;
- if `AT_DETECTION`: `+0` target detector-confirmation result;
- if `POST_DETECTION`: first validated checkpoint from the required dense grid;
- all earlier tested checkpoints and why they failed;
- remaining structural runway/opportunity at the winning time;
- chronological/OOT stability and held behavior where applicable;
- true/false/context decomposition under `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`;
- explicit leakage audit showing no realized final duration, final D depth, future descendant identity, or future path shape entered an earlier prediction.

A later checkpoint may be reported as a stronger-confirmation alternative, but it does not replace an earlier validated point unless the earlier point fails the predeclared actionability standard.

## D1-specific clarification

For exact D1, `PRIOR` means **before the D1 target/descendant begins**, using only already-causal information from its origin/predecessor context. It does not authorize pretending the original exhaustion was known before the frozen detector established it.

The D1 origin itself becomes a live exhaustion identity only at its own frozen detector-confirmation clock. From there, its h=5/10/20/30/60/120/300 information may become available early enough to predict its descendant before that descendant begins.

## Protected boundaries

Do not modify or retune:

- frozen exhaustion detector;
- canonical 54-week base or held rows;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings/freeze;
- frozen exhaustion runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS paper play.

Do not use later signed-direction Lane 3/4 detours or subsequent reframing to redefine this timing program.

No permanent brain merge and no play freeze are authorized from this historical timing study.
