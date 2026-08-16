# S133 - S131 CURRENT-FRANKIE G3 POST-SCORE REFINE

Status: POST-FREEZE REFINE. The S131 blind is immutable. Nothing in this document changes the
forecast, score, S131 packet plane, S129 artifact, G24, specialist roles, schema, or `spawn.py`.
No hydration and no new datapoint family are introduced.

## Source of truth

- Frozen aggregate: `research/kalshi/forecasts/frankie_g3_s131_corrected_reblind/grp3_s131_blind_frozen.json`
- Frozen SHA256: `3368822121b9c515891c83cb5b3d0a4d85881acff7f3d57cc1e7189870836771`
- Freeze commit: `1b6881f25e1504febccd13a2b8db4b4f615ad51c`
- Authoritative post-freeze score workflow: run `31913743729`
- Authoritative score basis: exact NGV25. S129 endpoint actuals were exact NGV25 session open-to-close
  nets, so S129 endpoint metrics compare only to S131 session-net endpoint metrics.

S131 session-net score: direction 4/10; CALL direction 4/8; MAE $562; RMSE $725.7; max error $1,440.
S131 full-day score including gaps: direction 4/10; MAE $637; RMSE $762.2; max error $1,460.
On the exact shared 11-point intraday clock, S131 MAE was $296.5 versus S129 $295.6 and RMSE was
$454.2 versus $405.5. Restoring the correct data plane therefore fixed the validity of the test but
did NOT by itself improve the common-grid curve score. The remaining problem is not "add more data".

## Headline diagnosis

Frankie did not fail for one reason.

1. **Reasoning-authority defect:** on several CALL days, a slow balance/regime backdrop became the
   practical day-sign owner after the faster continuation/turn discriminator was unavailable. Raw D-1
   flow was then allowed to add "corroboration" even though Frankie explicitly knew that price was
   required to distinguish delivery from absorption/exhaustion. The prose correctly named the missing
   discriminator, but the arithmetic still benefited from the incomplete proxy.

2. **One-shot protocol versus current-brain mismatch:** the current brain already knows important
   day-boundary continuation/exhaustion rules that require completed day-N-1 price/tape. S131 was a
   deliberately one-shot historical canary and withheld that realized in-window price. The brain could
   therefore contain the right lesson and still be unable to evaluate it. This is especially decisive
   on Sep 15 -> Sep 16.

3. **Old ABSTAIN curve-contract defect:** S131 inherited the old S120 rule that ABSTAIN meant zero net
   plus an all-zero curve. Sep 17 and Sep 18 therefore scored as literal flat-market forecasts even
   though the specialists were withholding direction, not forecasting zero travel. S132 already fixes
   this by requiring a full event-driven curve and P25/P50/P75 range even when disposition is ABSTAIN.

4. **True historical information gaps:** weekend forecast-weather/stability vintages and several
   Sep-2025 structural anchor stores genuinely do not exist in the archive. These explain some gap /
   seam uncertainty. They remain unavailable. No hydration or synthetic reconstruction is permitted.

## Why Frankie acted that way - causal chain

### Sep 08 - B, +250 CALL vs +650 full day (+190 session, +460 actual gap)

Frankie saw a strong Friday buy-flow state, mid-book/improving COT, and a loose slow balance. He chose
UP but capped the size and forecast only +50 for the weekend gap because the historical weekend
forecast-weather/stability plane was absent. Direction was right; the major miss was the gap magnitude.
This is primarily a historical-information limitation, not a brain-direction defect.

### Sep 09 - C, -200 CALL vs +120

C correctly said the prior Monday buy flow could not be labeled delivered versus absorbed because
price was masked. But after standing down that direction owner, C still derived DOWN from storage
surplus + weak gas burn / stronger wind. Those are real state variables, but here they became a
one-session sign substitute. This is the smaller first example of the reasoning-authority defect.

### Sep 10 - C, -300 CALL vs -750

Direction was correct. The tape was internally mixed but the late flow and slow demand/balance stack
supported a DOWN lean. The miss is mostly magnitude. No special brain correction is justified from
this day.

### Sep 11 - D, -350 CALL vs -1,000 full day (-1,010 session)

D correctly separated EIA range from sign and explicitly acknowledged that the strongest current D
arbiter is the first legal post-print delivery/absorption read, which is future at the open. The side
was right but the catalyst move was badly under-sized. This is mainly a magnitude/timing residual;
S132's event-driven curve and uncertainty contract is the correct output fix. Do not teach D that an
unknown print sign was somehow knowable at the open.

### Sep 12 - E, -320 CALL vs +270

E did substantial decontamination work: GSCI/BCOM programs were live, so gross D-1 selling was demoted.
But E still assigned the sell flow a negative corroboration term and let loose storage + weak gas-burn
context own the Friday sign while the price/exit-turn state was unavailable. The Friday specialist's
own turn/exit doctrine is price-sensitive. This is another reasoning-authority failure: a backdrop plus
an incomplete flow proxy became a day-sign engine when the actual sign-owning exit discriminator was
not evaluable.

### Sep 15 - B, -120 CALL vs +490 full day (+200 session, +290 actual gap)

B correctly refused to manufacture a Sunday-gap sign from absent weekend weather/stability history and
kept the call small. But the one-shot protocol also denied B the completed Sep-12 realized exit/turn
state that current day-boundary rules are designed to consume in sequential/live operation. The miss
is split between a genuine weekend-information gap and the one-shot sequential-information wall.

### Sep 16 - C, -250 CALL vs +1,210 full day (+1,200 session) - PRIMARY REASONING MISS

This is the largest endpoint and curve miss and the clearest explanation of why Frankie "acted that
way." C saw:

- loose storage / weak power-demand backdrop;
- D-1 Sep-15 aggregate sell flow of -3,340 lots with all three phase-flow buckets negative;
- no price-bearing delivery-vs-absorption state;
- no price cum / chain-age state under the one-shot wall.

C explicitly knew D-1 aggregate flow was weak next-day authority and explicitly stood down the
price-bearing `direction.flow_conviction_sign_gate`. Yet the arithmetic still granted about -80 of
"corroboration" to the coherent sell tape and allowed the slow bearish balance to own the sign.

The crucial finding is that **the current brain already contains the missing market lesson**.
`direction.giveback_exhaustion_boundary` requires day-N-1 actual price/tape and its recorded evidence
contains the specific general filter: when the old swing-side legs have already collapsed, stand down
continuation. Its legacy evidence records Sep-15 down-side continuation collapse as the filter that
prevents a resume-down call into the Sep-16 counter-grind. S131 could not evaluate that rule because
its one-shot protocol intentionally withheld in-window realized day-N-1 price/leg structure.

Therefore Sep-16 is NOT evidence that Frankie needs another Sep-16 rule. It is evidence that:

1. incomplete raw flow must not be allowed to recreate a stood-down price-sensitive sign play; and
2. live/sequential/refine Frankie must consume legally completed prior-session tape rather than run
   with the stricter one-shot historical information wall.

### Sep 17 - C, ABSTAIN vs -430

C reached a real collision: loose balance versus buy-side D-1 flow and demand arrival, with no lawful
price/absorption adjudicator. Withholding direction was defensible. The error was representing that
withholding as an all-zero expected path. This is the S120 output-contract defect fixed by S132, not a
reason to force C to invent a sign.

### Sep 18 - D, ABSTAIN vs -1,370

This is even more clearly NOT a simple Frankie-reasoning failure. The decision-time pre-print consensus
for Sep-18 was absent; price/overextension state was unavailable; and D's strongest current arbiter
requires the first 60-second post-print impulse, which is inside the target session. D correctly refused
to manufacture the day sign. The old flat-ABSTAIN representation created a large curve/endpoint penalty.
S132 fixes the representation; no hindsight rule should tell D that the -1,370 selloff was knowable
before the print from information that was not present.

### Sep 19 - E, -180 CALL vs -270

This is a useful control day. Once the Sep-18 print and the widened storage surplus were legally known,
E derived a small bearish state, treated post-print sell flow only as corroboration, and damped the lean
with stronger gas demand/tighter supply. The call was directionally and approximately right. Do not
change this behavior.

## Refinement decision

### Brain

**NO NEW BRAIN PLAY. NO BROAD BRAIN REWRITE.** The central Sep-16 lesson already exists in the current
brain. Adding a duplicate rule would make the playbook worse and would fit the walked day twice.

### Runtime

S133 adds a narrow reasoning-authority contract in `frankie_s133_reasoning_runtime.py`:

- every CALL must identify an evaluable direction owner;
- raw D-1 flow without paired price/shape cannot increase next-session directional confidence as
  "corroboration";
- slow balance remains regime/backdrop/magnitude/risk unless a canonical play explicitly owns day sign;
- if the sign owner is missing/conflicted, Frankie may ABSTAIN but still must emit the non-flat S132
  event-driven full curve/range;
- the default path stays one-shot and injects no prior-session realized price;
- an explicit sequential/live/refine path may attach completed prior-session MBO evidence only when
  its date is strictly earlier than the decision day; own/future evidence fails closed.

### Data

No new datapoints. No hydration. Existing ~1,800+ served fields remain the stopping point. Genuine
Sep-2025 archive gaps remain unavailable/null.

## What this refine should change in future behavior

The desired change is not "be more bullish after selling" or any other fitted sign rule. It is:

> When Frankie knows the discriminator that decides continuation versus absorption/turn is unavailable,
> he must not smuggle the missing decision back in through raw flow plus a slow backdrop. In one-shot
> mode that may force lower authority. In live/sequential mode, legally completed prior-session price
> and tape should be carried forward so the existing brain can evaluate the correct day-boundary rule.

That is the causal lesson from S131.
