# SELF-EVAL S105 — SPECIALIST B (Monday), G17 re-refine + honest post-mortem

Author: Specialist B (Monday / Sunday-fold owner). Group G17 (Apr 12-24). Brain s102.6.
Owned days: 20260413, 20260420. Immutable blind = `forecasts/grp17.json`. Round-1 refine =
`forecasts/grp17_mbo_specialist_B.json` (coordinator selected both verbatim: 0413 -340, 0420 -90).
Consumes A's REFINE bridge `forecasts/grp17_mbo_A_bridge.json` (the load-bearing input this pass).

All USD at the render scale: $10,000 per $1.00, i.e. $100 per cent, $10 per 0.1c.

---

## The ground truth (from `g17_mbo_evidence.json`, decomposed)

| Day  | anchor/prior close | reopen open | close | GAP (open-anchor) | intraday (open->close) | DAY-MOVE (net) |
|------|--------------------|-------------|-------|-------------------|------------------------|----------------|
| 0413 | 2.653 (Fri 0410)   | 2.699       | 2.620 | **+460**          | **-790**               | **-330**       |
| 0420 | 2.675 (Fri 0417)   | 2.720       | 2.669 | **+450**          | **-510**               | **-60**        |

Both Mondays: a large overnight UP-gap (~+450), a `turn_down` at **07:48 ET** (07:48:51 and 07:48:52
— an essentially identical desk-repricing fingerprint, n=2, not pooled) inside the catch-up window, then
ALIGNED sell (ph2/ph3 sflow<0 with px<0, ph_absorb all-false) reasserting the D-1 tilt into the close.
The day-move is the residual of a big up-gap minus a real down-sell.

---

## Q1 — RE-REFINE consuming A's refine bridge. Does the number change from round 1?

**No — it barely moves, and that itself is the finding.** A's REFINE bridge steers:
- 0413 -> "moderate down ~ -300 to -350" (from blind -520).
- 0420 -> "near-flat / -50 to -150 down, two-sided" (from blind -400).

My round-1 posterior already consumed a near-identical A read (round-1 doctrine_note cites A's weekend
bridge) and emitted **-340** and **-90**. Re-consuming A's refine bridge properly:

- **0413 -> -335** (was -340). A's bridge (-330) and my chain-exhaustion cap (-340) converge; the +460
  reopen gap-up was a counter-chain head-fake given back inside a live down chain (A: gap = chain_drift
  noise, REJECTED at 07:48; ph1/ph2 sflow -1921/-1222 aligned = real sell). Causal derivation: down chain
  live + driver ahead => direction DOWN safe; the counter-chain gap-up eaten inside the move is the
  magnitude haircut off the blind's -520. **-335** (actual -330).
- **0420 -> -90** (unchanged). A's bridge is emphatic: the covering gap-up (+45) plus the resumed
  aligned sell (ph3 -823/px-450) roughly cancel to near-flat; direction stays DOWN (sellers won the
  catch-up, E right on sign) but the LIVE cold-shot caps it. Causal derivation: record-short exhaustion
  + cold-shot realizing INTO Monday => overnight covering SQUEEZE gap-up that offsets the resumed sell
  => **-90** (actual -60).

The re-refine is a CONFIRMATION, not a new number, because round 1 already leaned on A. The honest read
of that: **the quality of my refine was carried substantially by A's bridge**, which matters for Q4.

---

## Q2 — THE HONEST TEST: decision-legit vs hindsight (0420 focus)

Split of every input B used on 0420:

**Decision-legit (knowable BLIND, from the never-masked state):**
- E's 0417 handoff: `positioning_spent_fade`, "sellers resume". (specialist read off legit state)
- `cot` (pub 0417): managed_money_net -114,095, **1y pctile 0.94 = record short**. -> exhaustion/cover fuel.
- `weather_forecast`: `forecast_vs_normal +3.992` HDD, `mod_heat`, `forecast_run_delta +0.573`
  (strengthening); `weather_forecast_cycle.sunday_reopen` = the weekend cold cycles' add, explicitly
  "available BEFORE the Sun 18:00 ET reopen, decision-time-legit". **The cold-shot is decision-legit.**
- `tape_conditions` 0417: `session_b_share 0.379` (fresh Monday sell tilt), never_masked.
- chain: down, mature, record-short. Decision-legit.

**Hindsight (only knowable because the MBO showed the reopen tape):**
- the **+45 gap magnitude** (open 2.72). The blind masks the price curve; the reopen tape is the MBO actual.
- the **-510 intraday sell** and the exact 07:48 turn magnitude.
- therefore the **precise -60 offset**.

**Could B have reached near-flat BLIND without seeing the -60?** Partially, honestly:
- The *direction of the correction* — "down but CAPPED to near-flat" — IS decision-derivable. Record-short
  0.94-pctile + a cold-shot realizing into Monday + spent covering is the textbook setup for an overnight
  covering **squeeze gap-up** that offsets a resumed sell. B could reason to that mechanism from legit state.
- The *magnitude* is NOT. Blind, B would know "large up-gap, capped fade" but not that +45 exactly cancels
  -510. Pure decision-legit, an honest blind B lands **~ -150 to -200** (knows the cap, not its size).
- The extra tightening to **-90** leaned on A's bridge, and **A's bridge read the +45 gap by OBSERVING the
  reopen** (A.reopen_watch.observed=true). So the last ~60-100 USD of precision on 0420 is A-observed, not
  B-derived. **I did not need to see -60, but I did need A's observed gap to get from ~-175 to -90.**

Crucial caveat that rescues this: **in LIVE trading the Sunday 18:00 ET reopen is real, observable data by
the time B decides the Monday in the 06-10 catch-up window.** So A's reopen_watch is hindsight only relative
to the *parallel one-shot blind*, not relative to a *live sequenced run*. The refine is a faithful preview
of what a live E->A->B panel would produce — see Q5.

---

## Q3 — WHY the blind Monday failed, quantified (process vs skill vs irreducible)

Decompose each blind miss into GAP error and INTRADAY error.

**0420 (blind -400, actual -60, miss = 340 too-negative):**
- blind gap +180 vs actual +450 -> **gap UNDER-called by 270 (79% of the miss)**
- blind intraday -580 vs actual -510 -> **fade OVER-sized by 70 (21%)**

This reframes the premise. The blind was NOT primarily "over-sized off mature-chain continuation" — it
already had the up-gap-then-catch-up-fade SHAPE (peak +180 at hr2, roll to -400). Its dominant error was
**under-sizing the covering squeeze gap-up**, which is *exactly* what A's live bridge supplies.
Attribution:
- **(a) missing live A-bridge (PROCESS gap, parallel spawn): ~270 / 340 = ~79%.** The covering-gap read
  is A's product; parallel spawn denied it to B live.
- **(b) B's own over-sizing off the mature chain: ~70 / 340 = ~21%.** Real but small.
- **(c) irreducible: ~50-70 band noise** (the exact +45/-510 offset).

**0413 (blind -520, actual -330, miss = 190 too-negative):**
- blind gap -40 vs actual +460 -> gap under-called / wrong-signed by 500
- blind intraday -480 vs actual -790 -> fade UNDER-sized by 310
- net = -500 + 310 = **-190. The two errors partially OFFSET.**

So 0413's tolerable net was partly luck: the blind under-called the up-gap AND under-called the down-sell,
and they cancelled. A live A-bridge (chain-exhaustion cap -> ~-330) plus B's own read would have gotten
there honestly instead of by offset. Process share here is muddier because of the cancellation; skill
share (recognizing the exhausting chain caps the fade) is decision-legit and would stand.

**Headline: the worst Monday miss (blind 0420) was ~80% a PROCESS failure — parallel spawn with no live
E->A->B handoff — and only ~20% B skill.**

---

## Q4 — Did the refine EARN it, or is it fitted?

Honest verdict, per day:

- **0413 -340 (actual -330): mostly EARNED, slightly over-claimed precision.** The cap-the-fade logic
  (mature exhausting chain, A: "grind not thrust") is decision-legit and would stand a live blind. Pure
  decision-legit I could honestly emit ~ -380 to -400; the tightening to -340 borrowed A's observed gap.
  So ~40-60 USD of the precision is A-observed, not B-derived. **Over-claim: modest.**

- **0420 -90 (actual -60): HALF earned, half A-informed.** The direction-of-correction (near-flat capped)
  is genuinely earned from record-short + cold-shot + spent-covering — that is skill on decision-legit
  state. But the exact -90 leaned on A's *observed* +45 gap. Pure decision-legit, the earned blind number
  is ~ -150 to -200, not -90. **Over-claim: real — I present -90 as if fully derived when ~half its
  precision is A's unblinded reopen observation.**

Where I UNDER-claimed: nowhere material; if anything I under-stated in round 1 how much of my accuracy was
A's bridge rather than my own lens. Correcting that here.

The blunt answer to Greg: **the refine did not fit to the -60 actual directly, but it leaned heavily on
A's bridge, and A's bridge is unblinded (it read the reopen tape).** Relative to the parallel one-shot
blind, that is a look-ahead. Relative to a live sequenced run where the reopen is real by decision time,
it is legitimate. The refine's 10/10-adjacent Monday result is therefore **honest for LIVE, optimistic for
the historical blind** — the gap between them is exactly the E->A->B sequencing the panel doesn't yet have.

---

## Q5 — PRESCRIPTION: sequenced spawn or live orchestrator? Would it have fixed blind 0420?

**Both, and specifically a live-orchestrator that sequences E -> A -> B and fires B's Monday number in the
06-10 catch-up window, AFTER the Sun 18:00 reopen is observable.** Reasons:

1. **A post-hoc SELECTOR coordinator cannot fix this.** It only picks B's already-emitted -400; the error
   is upstream of selection, in the number B was forced to commit blind and parallel. The fix must be at
   spawn/orchestration time.

2. **Sequenced E->A->B alone recovers the dominant component.** With A's bridge live, B up-sizes the gap
   toward the covering-squeeze read and holds (not over-sizes) the fade. That recovers ~270 of the 340
   (the gap under-call), taking blind 0420 from -400 to roughly **-130 to -170** — direction right,
   magnitude honest, the remaining ~70 being B's own fade-tightening from the observed catch-up conviction.
   So **sequencing alone fixes ~80% of the miss but NOT all the way to -60** (the last leg needs the
   observed +45/-510 offset, which a live B watching the catch-up window actually gets).

3. **The live-orchestrator is the real unlock, because the Sunday reopen is genuinely observable live.**
   The historical one-shot blind masks the price curve, so the reopen looks like hindsight; live, it is
   Sunday-night data available before Monday's catch-up window. An orchestrator that (a) runs E's Friday
   sign-off, (b) lets A observe the reopen and emit the bridge, (c) then has B commit the Monday number in
   the catch-up window consuming both — would make the refine-grade -90/-60 a *decision-legit live* number,
   not a look-ahead. That is the process the parallel panel structurally cannot do.

**Would sequencing alone have fixed blind 0420?** Most of it: -400 -> ~-150, a ~250 USD improvement,
direction preserved, honest magnitude. The final ~90 to reach -60 requires B firing in the catch-up window
against the observed reopen (the live-orchestrator step), not just receiving A's bridge at Friday close.

---

## Bottom line for Greg

- Re-refined Mondays: **0413 -335, 0420 -90** (round-1 -340/-90 essentially unchanged; coordinator already
  carries -340/-90). Actuals -330 / -60.
- The worst Monday (blind 0420, -400 vs -60) was **~79% a PROCESS failure** (parallel spawn, no live
  A-bridge -> under-sized the covering gap-up), **~21% B over-sizing the fade**, ~irreducible band noise.
- The refine leaned substantially on A's bridge, which is unblinded; the *direction of correction*
  (near-flat, capped) was decision-derivable from record-short + cold-shot + spent-covering, but the
  *precise -90/-60* borrowed A's observed +45 gap. Honest earned-blind number for 0420 is ~ -150 to -200.
- Prescription: **sequenced E->A->B with a LIVE orchestrator** (B fires in the 06-10 catch-up window after
  the observed reopen), not a post-hoc selector. That recovers ~80% of the blind 0420 miss on sequencing
  alone and makes the refine-grade number decision-legit live.
