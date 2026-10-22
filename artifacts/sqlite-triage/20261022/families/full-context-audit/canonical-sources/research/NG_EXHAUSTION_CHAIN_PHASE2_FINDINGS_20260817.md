# NG Exhaustion Chain Phase 2 — Characterization and First Paper Play Freeze — 2026-08-18

Status: **PHASE 2 CHARACTERIZATION COMPLETE; FIRST CAUSAL PAPER-TRADING PLAY FROZEN FOR RESEARCH ONLY.**

No frozen detector, 54-week base row, held-week row, runway-clock file, permanent Frankie file, Frankie 1 file, or `research/kalshi/spawn.py` byte was changed.

## Step-0 gate

Workflow run `32078601056` completed successfully at source commit `27a5ef995bfb72aba57b397a95dcff4f433376ba`. Artifact `ng-exhaustion-phase1-55w-reconciled-final-20260817` (`9306082330`, `sha256:f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`) passed every required field: 55 weeks, 235,170 events, insert-only held week `20260329`, immutable 54-week base, no runway or permanent-Frankie mutation, and no hard failures. Phase 2 is therefore legitimately unlocked.

## 30s / 60s D2-D4 causal region

Every D2-D4 cell at 30s and 60s remains positive in the five discovery eras, the untouched-confirmation fold, and the inserted held week for ExtraTrees, KNN, and Ridge. The independent week-block null also survives in every cell.

| Info horizon | Depth | ExtraTrees disc / conf / held | KNN disc / conf / held | Ridge disc / conf / held | worst p |
|---:|---:|---:|---:|---:|---:|
| 30s | D2 | 0.009125 / 0.007239 / 0.006120 | 0.087283 / 0.042072 / 0.035838 | 0.011634 / 0.006204 / 0.004200 | 0.0000500 |
| 30s | D3 | 0.003861 / 0.003714 / 0.003727 | 0.048757 / 0.048895 / 0.054631 | 0.007878 / 0.004667 / 0.003748 | 0.0000500 |
| 30s | D4 | 0.003949 / 0.003730 / 0.003291 | 0.017900 / 0.027082 / 0.033101 | 0.005080 / 0.003625 / 0.001702 | 0.0000500 |
| 60s | D2 | 0.005945 / 0.005703 / 0.001154 | 0.087681 / 0.113907 / 0.109887 | 0.010077 / 0.005524 / 0.002613 | 0.0000500 |
| 60s | D3 | 0.003725 / 0.004778 / 0.003698 | 0.013878 / 0.019317 / 0.034504 | 0.006791 / 0.004430 / 0.004007 | 0.0000500 |
| 60s | D4 | 0.001817 / 0.002855 / 0.002532 | 0.003593 / 0.006415 / 0.007540 | 0.003910 / 0.002980 / 0.001847 | 0.0011499 |

The shape matters: D2 is generally the largest incremental step, while D3 and D4 are smaller but persistent. Higher-order information is real, but the evidence does **not** say that one immutable origin remains alive unchanged through every descendant.

## Short chains versus long chains

The strict all-model lineage distribution is sharply short-tailed. Out of 156,422 OOT origin instances, cumulative survival is 20,562 to D1+ (13.15%), 1,725 to D2+ (1.10%), 133 to D3+ (0.085%), 9 to D4+ (0.00575%), and 1 to D5+ (0.000639%).

For exact maximum depth, the median elapsed time is 65s at D1, 143s at D2, 216.5s at D3, 279s at D4, and 2,477s for the lone D5 survivor. That creates two empirical regimes: a common short-chain regime concentrated inside a few minutes, and a very rare long-chain tail.

The nine strict D4+ origins are heterogeneous. Their seed-state sequences are all different and their polarity sequences are all different. The sole D5 chain is `20260712-133468--1`, all DOWN polarity across six events, with 2,477 seconds from origin to D5. Because the long tail is only nine instances and has no repeated common state signature, **no long-chain trade is frozen yet**.

## Inherited origin versus rolling / re-origin

The held week is hostile to a simple fixed-origin story. For D1→D2, D2→D3, and D3→D4, same-origin adjacent-depth odds ratios stay near 1 for all three models, with non-significant two-sided tests. Examples: ExtraTrees `0.978 / 1.070 / 1.001`, KNN `0.923 / 1.055 / 1.093`, Ridge `1.031 / 1.049 / 1.021`.

The stronger interpretation is therefore a **rolling causal state machine**: the market keeps information from several recent exhaustion episodes, but the useful state is refreshed/re-originated locally rather than being carried by one permanent ancestor.

A concrete rolling motif emerged: the four immediately preceding +60 seed states `S,S,O,S` continue to predict the next event even when a fifth, older predecessor is added. In the 54-week base, the target continuation mean stays positive for every fifth-state bucket (`O +0.083t`, `S +0.425t`, `P +0.239t`, `X +0.308t`). The held week is nonnegative in every deeper-state bucket. That is direct evidence that the useful object is the recent four-state window, not a unique deeper origin.

State legend: `S = collapsed_same_flow_reload`, `O = collapsed_opposite_flow_reversal`, `P = persistent_exhaustion`, `X = collapsed_sparse_indeterminate`.

## Independent play search and falsification

The executable search was deliberately kept simple and causal: exact predecessor seed-state sequences at D2-D4, 30s/60s exits, optionally split only by the current event's polarity relation to the latest predecessor. The current event's own +60 state and all future price information were forbidden.

Chronological selection used four blocks: eras 1-3 (18 OOT weeks) for direction discovery, eras 4-5 (12 OOT weeks) for replication, the six untouched-confirmation weeks, and finally the insert-only held week.

The strongest candidate before the held week was `P,O,X -> continuation to +60s`. It looked good in all three pre-held blocks but **reversed on the held week** (`-0.231t` gross; negative same-week delta), so it was killed. This is exactly the falsifier behavior we wanted.

The next strongest survivor is the D4 rolling motif `S,S,O,S`.

| Block | n | Gross mean | Same-week delta | Positive-week delta | one-sided p |
|---|---:|---:|---:|---:|---:|
| Eras 1-3 discovery | 389 | +0.396t | +0.427t | 66.7% | 0.0156 |
| Eras 4-5 replication | 306 | +0.196t | +0.092t | 58.3% | 0.2448 |
| Untouched confirmation | 131 | +0.168t | +0.220t | 66.7% | 0.1289 |
| Held 20260329 | 27 | +0.815t | +0.834t | 100.0% | — |

On the held week, an exact within-week circular-shift falsifier gives one-sided `p = 0.01088`. Across the full 54-week base, the play occurs 1,242 times among 49,832 causally eligible/no-overlap D4 targets (2.49%) and averages `+0.256t` gross from entry to exit. Held frequency is 27/826 (3.27%) with `+0.815t` gross.

## Frozen research paper play: `NG_CHAIN_D4_SSOS_CONTINUATION_V1`

The four immediately preceding exhaustion episodes, oldest to newest, must be `S,S,O,S`, and each predecessor must satisfy the Phase-1 h=60 D4 causal-availability wall before the current event starts. The current event's polarity is known at t0; no current +60 state is used.

Wait for the current exhaustion endpoint to be causally confirmed. If a successor exhaustion starts before confirmation, stand down. Enter **with the current exhaustion polarity** at structural endpoint `+5s` only if confirmation is already known by then. Exit at structural endpoint `+30s`. The evaluated holding period is therefore 25 seconds.

Invalidation is fail-closed: missing predecessor availability, censored/unconfirmed endpoint, successor-before-confirmation, missing polarity/price, or any Trader Frankie risk/health/duplicate/account/kill-switch rejection means no order.

The information window is materially longer than the trade: across the 54-week play instances, the oldest of the four predecessor events is a median 467s before the current t0 (IQR 336-821s), while the latest predecessor is a median 123s before t0. The trade itself is fixed at 25s.

This is **paper only**. The `+0.256t` 54-week mean is gross and does not include spread, fees, slippage, queueing, or broker execution. It is not a live-edge claim and it is not promoted into permanent Frankie or Frankie 1.

## What Phase 2 says now

1. The 30s/60s D2-D4 higher-order signal is real and survives every Phase-1 confirmation/falsifier layer, including the held insertion.
2. Most chains are short; strict D4+ fixed-origin chains are extraordinarily rare.
3. The dominant mechanism looks rolling/re-originated, with recent multi-event state windows carrying information even when a deeper origin changes.
4. A specific D4 rolling motif now has a frozen causal paper contract. Long-chain execution remains research-only because the strict tail is too sparse and heterogeneous.

Permanent Frankie, Frankie 1, the runway clock, and all frozen Phase-1 evidence remain unchanged.
