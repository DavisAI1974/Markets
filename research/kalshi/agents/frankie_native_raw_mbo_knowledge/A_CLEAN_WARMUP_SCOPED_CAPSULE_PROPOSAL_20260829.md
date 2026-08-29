# A-clean Warmup-Scoped Positive Knowledge — PROPOSAL

Date: 2026-08-29 UTC
Status: **PROPOSAL FOR D1 — NOT INSTALLED, NOT REGISTERED, NOT HASH-BOUND**

This is a candidate replacement for `A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md`, built to the
rule that A-clean may carry prior knowledge but not prior knowledge *of the days it is
about to be scored on*. It is not wired into the knowledge manifest and changes nothing
until you say so.

## Why this shape

The existing capsule's four substantive findings are all derived from October 4 and 5, the
`HELD_OUT_BLIND` days, and all are calculations rather than opinions. The permitted
reduced-data opinions already have their own correct channel — the V3 carryforward, which
states outright that V3 outputs are not empirical truth and are admitted only for gap
diagnoses and helper architecture. Nothing here disturbs that.

Everything below is computed from October 1 and October 3 only, both
`WARMUP_DEVELOPMENT`. A live Frankie carrying knowledge from prior sessions is exactly this
situation; a Frankie carrying a prior pass over the session it is about to trade is not.

## Carried method rules (unchanged, no day content)

1. **Causal rule:** exact evidence becomes available only at F_LAST on `ts_recv_ns`; retain
   event, first-receive, and close clocks separately, and never smooth across
   day/family/side/session/phase identities.
2. **Parallel-view rule:** daily means provide regime and scale; exact groups, orders, FIFO
   queues, transitions and checkpoints provide causal mechanism. Valid differences are
   `COMPLEMENTARY_SCOPE_DIFFERENCE`, never contradictions or pooled averages.

## Warmup-derived regime knowledge

Denominators are F_LAST-closed groups: October 1 = 1,118,738; October 3 = 43,569.

3. **Day-regime clue, warmup-sited.** Full-depth imbalance differs between the two warmup
   sessions on every summary statistic: October 1 first 0.092565947 / last 0.078886311 /
   min -0.098496241 / max 0.206649283 / mean 0.056964194, against October 3 first
   0.078886311 / last 0.058006941 / min -0.021144920 / max 0.171483622 / mean 0.065535499.
   A day's mean and its extrema disagree about which session is more bid-supported, which
   is the point: the mean is regime, the extrema are mechanism.

4. **Scale is not stationary across sessions.** October 1 carries 1,504,374 records in
   1,118,738 groups; October 3 carries 57,027 in 43,569 — a 26-fold difference in activity
   between two adjacent warmup sessions. Bid depth mean 1,573.439 versus 952.288, bid
   orders 669.550 versus 383.908, bid levels 377.412 versus 287.215. Any bar sited on an
   absolute count is being sited on a moving object.

5. **Multiplicity is heavy-tailed within a session.** Actions per group are 1.344706 on
   October 1 and 1.308889 on October 3, while the maximum group sizes on those days are
   786 and 245 actions. A mean near 1.3 and a maximum in the hundreds cannot both be
   summarized by the mean.

6. **Sidedness is small and the unsided share is not.** Signed message skew is +0.922% B on
   October 1 and +2.249% B on October 3, against unsided fractions of 9.359% and 8.661%.
   The unsided residual is several times the size of the directional signal, so any B-share
   computed on total volume is dominated by its denominator.

7. **Spread scale differs by an order of magnitude between adjacent warmup sessions.**
   October 1 spread mean 0.002598022 against October 3 0.005698019, with October 3's
   minimum recorded at -0.060000000 — a negative reading that is a state to explain rather
   than a value to average.

## What was removed and why

| Removed | Reason |
|---|---|
| October 5 versus October 4 imbalance, depth, orders, levels, message skew | Cross-day comparison over both held-out days; computable only after processing all of both |
| Cancel-linked share 82.652% / 82.495% "by held-out day" | Held-out day statistic; the source states the family census comes from the held-out ledger |
| Order `786260864394`, ask side at 5.758 on October 4, group 1,166,147, 4.297-second lifecycle | A named order's terminal outcome on a held-out day, before its F_LAST |
| October 5's 21:00 withdrawal being larger and more bid-cancel-heavy | Held-out cross-day comparison |

## Findings that could be restored by recomputation

Three mechanisms in the original capsule are plausibly real and are simply evidenced on the
wrong days. Each could return if recomputed on October 1 and 3:

- **Post-fill disposition mix.** `TFCN + TFM + TFMN` branch shares and the same-ID linkage
  rule. The existing counts (38,510 / 39,766) are held-out; the warmup equivalents were
  never computed.
- **An exact order lifecycle template.** `AN → TFMN → TFCN` as a shape is a mechanism, not
  an answer. October 1 has 1,118,738 groups, so exemplars certainly exist there.
- **The 21:00 UTC withdrawal and restart anchor.** The source records it only for October 4
  and 5. Whether October 1 and 3 show the same `C…C→N` group, quiet interval and ordered
  add restart is unverified and is a cheap check.

Restoring these on warmup is the difference between a capsule with two mechanisms and one
with five, so it is probably worth the recomputation before sealing.

## A caveat that matters more than it looks

October 1 is a Friday and October 3 is a Sunday reopen. The held-out days are a Monday and a
Tuesday. Under this project's own day-class doctrine — classify first, score only within
class, no Mondays scoring Fridays — warmup-derived regime knowledge is **out of class** for
the days being scored. That is a limitation of the warmup set, not of this re-scope, and it
argues for carrying warmup knowledge as *method and scale calibration* rather than as a
directional prior about how the held-out sessions will behave.

## One separate leak to close either way

The source review records that each next source's `first` equals the preceding source's
`last`, chaining October 1→3, 3→4 and **4→5**. The 3→4 link is harmless: October 4's opening
state is lawfully available when October 4 begins. The **4→5 link is not** — it discloses
October 4's terminal book state, which is not available at October 4's open. Any carried
continuity claim should stop at 3→4.
