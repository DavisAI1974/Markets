# PASS-2 NOTES - continuous-series construction (found S97, deferred by Greg to the second pass)

Greg's call (S97): do NOT re-base the walk now. Finish the first pass over the historical data,
then fix on the refinement pass. This file records what was found so it is not lost.

## The finding

The NG "continuous front month" is selected AT PULL TIME by Databento symbology, so the contract
choice is baked into the S3 files - it cannot be re-mapped locally.

- `NG.v.0` (VOLUME roll) - what the whole walk G3-G10 was pulled on.
- `NG.n.0` (OPEN-INTEREST roll) - what the G11 window was re-pulled on (S97).

Neither is monotonic. Both can switch contract and switch BACK.

### Observed instrument changes

`.v.0`, the walked winter (from the committed `*_rt.json` roll records):

    G3-G5   20250925   869 -> 864    +0.276    one-way
    G6      20251027   864 -> 863    +0.659    one-way
    G7                 none
    G8      20251123   863 -> 1018   +0.039    one-way
    G9      20251225   1018 -> 1000  -0.504    one-way
    G10                none (stayed 1000)
    G11     20260122   1000 -> 1021  -1.541  \
            20260123   1021 -> 1000  +1.420   > ALTERNATES (pathological)
            20260125   1000 -> 1021  -1.465  /

G3-G10 each rolled exactly once and never returned - those blocks are CLEAN and the brain's
narrative built on them stands. The whipsaw is unique to the G11 window: the expiring February
contract went parabolic into delivery (3.0 -> 5.4), repeatedly pulling volume back to the dying
contract, so a volume-selected front month flip-flopped. Feb/Mar spread widened -0.41 (Jan 16)
to -1.54 (Jan 22) as Feb squeezed.

`.n.0`, Nov 1 - Jan 15:

    20251109 (Sun)  1018 -> 1021   -0.639
    20251110 (Mon)  1021 -> 1018   +0.736    flips BACK
    20251207 (Sun)  1018 -> 1021   -1.222    (this one stuck - a real roll)

## Root cause of the .n.0 flips: THIN SUNDAY SESSIONS

    20251107 Fri  n=14,490  iid 1018   4.49-4.63
    20251109 Sun  n=   368  iid 1021   3.91-3.95
    20251110 Mon  n=16,799  iid 1018   4.49-4.71

A ~350-trade Sunday session determines which contract the continuous series tracks. Weekday
sessions run 15k-125k trades.

## THE CONSEQUENCE THAT MATTERS - weekend-gap reads may be spread artifacts

`daytype.monday_weekend_gap` reads the weekend repricing AT THE SUNDAY REOPEN GAP. If the Sunday
session sits on a different contract than the preceding Friday, the measured "gap" is a CALENDAR
SPREAD, not a market move.

Demonstrated in the G11 window under `.v.0`:
  20260123 (Fri) iid 1000 close 5.353
  20260125 (Sun) iid 1021 open  3.888
  -> the -1.465 "weekend gap" is 100% contract spread, 0% price move.

The handoff records "weekend-gap Monday REVERSALS are huge + under-sized (1020 +$2770 vs guessed
$580)". That is the shape a spread artifact would produce. NOT established - this is a falsifiable
hypothesis to TEST on pass 2, per-event, never pooled.

G11 itself is clean on this point: Sundays 20260118 and 20260125 both sit on iid 1021 alongside
every weekday in the block, so its +0.210 and +0.248 weekend gaps are genuine repricing.

## PASS-2 TASKS

1. Audit every Sunday reopen in the walk: was the Sunday session on the SAME instrument as the
   adjacent Friday and Monday? Any Sunday that was not has a contaminated gap read.
2. Re-test `daytype.monday_weekend_gap` on roll-clean gaps only. Per-event, never pooled.
3. Decide the canonical construction. Recommendation: stop using Databento's continuous aliases
   and pull EXPLICIT contract symbols, defining the roll ourselves (e.g. N days before expiry, or
   OI crossover measured on WEEKDAY sessions only, carried through adjacent thin Sundays). That is
   deterministic, monotonic by construction, and matches how a trader actually rolls. It also
   removes the possibility of a thin session re-deciding the series.
4. Re-derive the walked blocks on the chosen construction and check which recorded findings move.
   Blocks G3-G10 rolled one-way, so most should be stable - verify, do not assume.

## PROTOCOL FIX (separate, applies from G12)

The roll check cannot be run by the orchestrator without loading tape and therefore SEEING the
block's price path - a blind-wall breach of the orchestrator, which then designs the blind setup.
From G12 on, a subagent runs the roll check and returns ONLY the roll date and spread, never prices.

G11 caveat to carry in the record: the orchestrator saw G11's price path before the blind agent was
spawned (the kickoff ordered roll_offsets first). The forecast subagent was genuinely blind and its
prompt carried no outcome information, but the price-basis choice (.n.0) was made with outcome
knowledge, on the stated principled ground that it was the single-contract series for that window.
