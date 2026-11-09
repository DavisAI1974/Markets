# Paper candidates — Codex independent specification

These rules are experimental paper specifications. They are not deployed, and no measured return is claimed. The matching [JSON](PAPER_STRATEGIES.json) records the same inputs, thresholds, execution assumptions and risk rules. All historical alternatives remain in the research register.

## P01: touch order-count imbalance
At every 3-second UTC grid cutoff, use the latest fully completed valid group and its original order counts. Require a one-tick spread and positive total count. Count imbalance is (bid count - ask count)/(bid count + ask count). A crossing to at least+1/3 proposes long; a crossing to at most-1/3 proposes short. First valid observation only initializes state; any missing/stale/reset interval clears the previous trigger state. There is no entry while a position is open.

The threshold is a provisional 2:1 count ratio, not a validated threshold from the historical correlation. Recheck after the simulated 100-ms latency; if the side no longer qualifies, suppress and log it. Maximum hold is 5 seconds from first actual entry fill. Opposite qualifying side requests exit, never immediate reversal. Current dipole/flow state is logged for comparison without treating it as an independent confirming vote.

Evidence: C04/C09/C10 and the full saved coupling rows. Touch associations repeat at short horizons but flats/adverse outcomes are numerous and later horizons weaken. Costs and actual fills remain unmeasured for this rule.

## P02: hit-side replenishment
Use the same grid and valid one-tick spread. Over (cutoff-1 second, cutoff], calculate by side (touch additions + additions within four ticks)/passive fills, requiring positive fills. A crossing to ratio at least 2 on the bid side proposes long; on the ask side proposes short. If both qualify, record both and submit no order. First observation/recovery only initializes state.

The threshold of two added lots per filled lot is provisional, not the retrospective daily tercile. Recheck after 100 ms; maximum hold is 1 second from first entry fill. An opposing qualifying side requests exit, not reversal. Log the flow, empty half-windows and expiring contributions.

Evidence: C06/C13. The short association recurs across the four dates but small denominators, delayed observations, spreads and costs may overwhelm it. This is not a claim that those exact paper settings were tested.

## O03: price-response sequence recorder
No orders and no positions. Trigger on each eligible completed-group midpoint change of at least two ticks. Preserve the old/new quote, fixed-price queues, source action order, print/fill/add/cancel identities and same-group mechanisms. Follow strictly subsequent behavior at 1/5/25/100/250/500 ms and 1/5/20/60/600 seconds, using the last eligible observed group at/before each target and recording its age rather than interpolating.

Keep exact first half/full return and the subsequent whole available path; retain no-response, adverse continuation and right-censored cases. Attach only then-known dipole/flow states. Moving-rank depth is separate from replenishment at a fixed old/new price. Same-group actions are not later reactions.

This directly addresses price→market behavior→later price. It does not identify a causal price effect. Evidence: C11–C13/C21. A verified NG recorder and source clocks are required.

## O04: duration and flow-state context
No directional orders. Use the exact frozen Family A classifier only when its 61 required samples, lineage and availability are verified. For 3/5/8/13-tick absolute-distance targets, original totals are 358/993/1802/4386 seconds for fast-collapse and 700/1802/3455/6836 for persistent. Remaining time is max(0,total-elapsed since t 0). Keep the calibratedv 4 as a separate version until the exact factor and band files are pinned.

The deadline is not an instruction to reverse and is not a natural event endpoint. Evidence: C16/C18/C27. Bands and day dependence are material; live classifier/calibration wiring remains unverified.

## Shared execution and risk specification for P01/P02
Each candidate gets a separate virtual ledger, one contract maximum, no adds and no automatic voting between candidates. No order is enabled in the supplied configuration.

After provisional 100-ms delay and trigger recheck, the proposed paper order is a one-contract marketable-limit IOC at the current opposing touch with one tick tolerance in trade direction. Require simulator liquidity and an order receipt; do not fill at a midpoint or assume the observed touch is still available. Keep partial fills, cancel unfilled remainder and do not chase. Exits use the same latency and execution constraints.

Use provisional 4-tick stop and 4-tick target measured from actual weighted entry fill, long at executable bid and short at executable ask. These are triggers, not guaranteed exit prices. Time limit starts at first fill. Exit priority is integrity pause/cancel, exposure or loss limit, stop, time limit, target, then signal reversal. If there is no valid quote during a gap, retain unresolved exposure rather than invent a fill.

Maximum 20 entries per session;60-second cooldown after exit. Daily loss limit is 20 tick-contract units of realized net plus marked open exposure, with fees converted using the pinned contract tick value. Missing/unresolved fees or marks pause new entries. At the limit, cancel entries and request exit; no new entries until the next verified session. A fresh qualifying trigger after cooldown is required for the opposite side.

Skip new entries for a last completed-group age over 1 second, unresolved source gap/reset, clock regression, invalid/crossed quote, missing contract or required denominator, or unknown fee. Cancel pending orders and pause on disconnect; reconcile durable order/position state, a fresh snapshot and full lookback before restart.

All these engineering settings are provisional. The current fee is null and the NG route is unverified, so execution remains blocked. Never substitute the repository's cryptocurrency minute-close adapter or its invented spread/fee model.

## Logging, evaluation and retained alternatives
Record all opportunities, raw operands, source and separate decision/action clocks; conflicting and suppressed signals; order/ack/fill/partial/miss/cancel/exit; available liquidity, spread, fees, latency and slippage; excursions, holding time, net results and missing endpoints. Freeze code/configuration before new data. Do not tune away adverse cases during evaluation.

All 11 stack arms,10 continuous precursor predicates, original/inverse family screens, SSOS and the historical 146-entry register stay in the analysis. Missing operational definitions remain explicit pending work. Selecting these first concrete configurations does not delete any other observation or hypothesis.

See [PAPER_READINESS.md](PAPER_READINESS.md) for the exact capability checks and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) for deferred research. No reconciliation with Ccode's report is part of delivery.
