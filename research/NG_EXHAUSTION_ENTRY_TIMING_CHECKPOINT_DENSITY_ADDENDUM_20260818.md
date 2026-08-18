# NG Exhaustion Entry-Timing Checkpoint Density Addendum — 2026-08-18

Status: **AUTHORITATIVE USER-DIRECTED CHECKPOINT SPACING ADDENDUM.**

This addendum supersedes the coarser fallback checkpoint spacing previously written in:

- `CHATGPT_KICKOFF_NG_EXHAUSTION_ENTRY_TIMING_REVIVAL_20260818.md`
- `research/NG_EXHAUSTION_ENTRY_TIMING_REVIVAL_PROTOCOL_20260818.md`
- `research/NG_EXHAUSTION_EXACT_D1_CURRENT_PROTOCOL_20260818.md`

It does not change the preserve-all rule, the early-entry-first hierarchy, the knowability clocks, any frozen Phase-2 finding, or any protected component.

## Updated fallback checkpoint ladder

Fallback survivorship/late-entry analysis is used **only** for structures or subfamilies that are not sufficiently actionable at their earliest causal entry.

Starting from the applicable causal knowability clock:

- test `+1, +2, +3, +4, +5` seconds;
- then `+10, +15, +20` seconds;
- then test **every 5 seconds continuously after +20**: `+25, +30, +35, +40, ...`.

For the authorized current campaign, the dense 5-second grid continues through `+3600s` wherever the structure remains alive and the required tape is available. Longer landmarks may be added when support exists, but the 5-second grid through +3600 is not replaced by coarser spacing.

The older coarse landmarks such as +30/+45/+60/+90/+120/+180/+300/+600/+900/+1800/+3600 may still be reported as summary landmarks, but they are **not** the only evaluated checkpoints.

## Causal guard

At checkpoint `t`, a model or rule may use only:

- information causally available by the applicable knowability clock plus `t`;
- the causal fact that the structure has survived through `t`;
- price/order-flow/book information observed through `t` when that lane permits it.

It may not use realized final duration, final depth, future descendant identity, future path shape, or any later checkpoint information.

## Scope

This denser ladder applies to:

- exact-D1 fallback survivorship;
- D1 directional and chop/rotation revival research when fallback entry is required;
- exact D2-D5 fallback late-entry research after the earliest validated information horizon for the rule being tested.

Earliest validated entry still wins. A setup already causally predictable and net-profitable at its earliest decision point is **not delayed** merely to enter the dense checkpoint ladder.

No row is deleted if no checkpoint validates. Such rows remain preserved research evidence.
