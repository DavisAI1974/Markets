# FRANKIE'S OWN ACCOUNT OF THE S127 G24 RUN

## Run identity

- Group: `g24`
- Blind namespace: `research/kalshi/forecasts/frankie_g24_s127_chatgpt/`
- Sanctioned causal-artifact commit consumed: `5d0354b5230c5fe746c639608075e0a3f2a54735`
- Operator/runtime for this run: ChatGPT session, **not Claude and not an OpenAI API call**
- Specialists: existing A-E roles, unchanged
- Brain: full current brain, all 90 play bodies available on every blind day
- Data surface: complete already-served causal universe; no new data points added
- `spawn.py`: untouched
- Outcome wall: no `g24_actual.json` access until all 10 blind day files and the A bridge were frozen
- S121 session-close fix: full 20:00 ET -> next-day 20:00 ET path is now representable without relaxing chronology

## My score after the wall opened

| measure | S127 ChatGPT-operated Frankie | old g24 blind |
|---|---:|---:|
| MAE | **$802** | **$489** |
| p50 direction hits | **3/10** | **6/10** |
| CALLs | **7** | n/a |
| CALL direction hits | **2/7** | n/a |
| CALL MAE | **$1,038.6** | n/a |
| ABSTAINs | **3** | n/a |
| ABSTAIN p50 MAE | **$250** | n/a |
| block sum forecast | **+$1,050** | n/a |
| block sum actual | **-$930** | n/a |

I was worse than the old blind on this group. More data did not make me better by itself. The main failure was **reasoning priority and conflict resolution**, not lack of breadth in the data surface.

## Day-by-day account

### 2026-07-20 — B Monday — CALL +500, actual -710, error $1,210

**What I saw blind:** Friday flow was positive, Sunday-reopen flow was thin, Monday weather was warmer, COT was short/worsening, and there was no block-opening A bridge.

**What I did:** I made the weather/crowding setup the dominant read and assigned +100 to the gap with a +500 total day.

**What I got wrong:** I gave D-1 positive flow bullish next-day weight that the brain itself tells me not to give it. The high-confidence play `tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell` says the D-1 arm tested as a coin flip and explicitly says **never read a large same-day buy tilt as next-day bullish evidence**. Friday's +1333 lots cleared the play's lower bar. I had the warning in the 90-play brain and did not give it enough priority. I also missed the weekend gap badly: +100 forecast versus -330 actual.

**My diagnosis:** operator/reasoning-selection error. Not a missing-data excuse.

### 2026-07-21 — C core Tuesday — CALL -650, actual +390, error $1,040

**What I saw blind:** D-1 flow looked strongly sell-sided: -4537 lots, two-sided session share 0.469, 146 big prints at 0.305, all three phases negative.

**What I did:** I treated that as clean continuation DOWN.

**What I got wrong:** the blind packet does not carry the price half needed to distinguish delivered selling from absorbed selling. I treated a flow read as more direction-certain than it was. The brain's own audit work says D-1 flow is much weaker as a next-day sign than same-day flow mechanics. I should have treated the absence of price-bearing conviction as a larger uncertainty penalty instead of converting a thick sell tape directly into -650.

**My diagnosis:** I over-applied the generic D-1 direction source rule and underweighted the blind mask's effect on absorption/delivery classification.

### 2026-07-22 — E roll seam — CALL -400, actual +630, error $1,030

**What I saw blind:** modest D-1 sell tilt, a warmer 08:00 weather update, and the Q26 -> U26 Kalshi-underlying seam.

**What I did right:** I did **not** forecast the never-traded Q26/U26 roll offset as a market gap. I also refused to import Q26 frozen expiry/opex/squeeze structure directly onto the U26 scored leg. Hole #8 stayed closed.

**What I got wrong:** after correctly removing the mechanical seam, I still let the modest prior sell tilt own the sign. The new-leg day rallied +630. The remaining blind evidence was not strong enough to justify a -400 CALL.

**My diagnosis:** correct structural hygiene, wrong residual directional decision. This should probably have been lower-authority/ABSTAIN unless a new-leg signal cleared a stronger bar.

### 2026-07-23 — D storage Thursday — ABSTAIN, p50 +150, actual -40, error $190

**What I saw blind:** the current survey consensus was absent, pre-print flow was internally split, and the first post-print delivery/absorption state was future-masked.

**What I did:** I refused to invent the consensus or the surprise sign. I kept a wide print-day market path but set `ABSTAIN`.

**Result:** the trade decision was appropriate and the p50 stayed close to flat. This is one of the run's better decisions.

**My diagnosis:** the fail-closed/ABSTAIN path worked.

### 2026-07-24 — E Friday — CALL -500, actual -40, error $460, direction hit

**What I saw blind:** coherent D-1 sell flow, a mildly loose prior storage print, and a real warmer-weather counterweight into the weekend.

**What I did:** I kept the sign DOWN but sized the continuation too aggressively.

**What I got wrong:** the weather counterweight and the fact that Friday's structural Q26 countdowns were unusable on U26 should have reduced magnitude more. Direction was right; conviction was too high.

**My diagnosis:** magnitude/authority error rather than sign error.

### A bridge 2026-07-24 -> 2026-07-27

**What I did:** I consumed E's Friday handoff, agreed that the forward weather driver remained ahead of Monday, and passed B a moderate-UP prior. I explicitly said A informs and B decides.

**What I did not have:** at the Friday cutoff I cannot know the actual Sunday reopen. More importantly, when B's Monday packet arrived, it served Sunday-reopen **weather/freeze-risk** updates, but the tape block still described the prior Friday session. I did not find a separate Sunday-reopen trade-flow/L1 block even though B's role says the Sunday session's thin prints should be used as positioning hints.

**My diagnosis:** the bridge mechanism was disciplined, but the Monday handoff lacked one channel its role expects. If that Sunday reopen tape already exists in the possessed firehose, it should be **wired**, not invented as a new data family.

### 2026-07-27 — B Monday — CALL +550, actual -1,360, error $1,910

**What I saw blind:** A's weather-UP prior, neutral Friday session flow, Sunday weather still warm, and a Monday 08:00 +1.096 CDD revision.

**What I did:** I let weather own the Monday catch-up call and forecast +100 gap / +550 total.

**What actually happened:** -610 gap and -1,360 total. This was the worst miss in the run.

**What I got wrong:** I treated a weather revision as if it could own price direction without adequate trade confirmation. I also did not have the Sunday-reopen trade-flow/L1 read that B's own role expects. Even with that gap, the correct response to weak confirmation should have been to reduce authority or ABSTAIN, not promote the weather prior into a CALL.

**My diagnosis:** primary reasoning error plus a concrete packet-wiring gap. The missing channel is not a reason to add more broad data points.

### 2026-07-28 — C core Tuesday — CALL +700, actual -800, error $1,500

**What I saw blind:** +3052 signed lots, session two-sided share 0.517, 174 big prints at 0.616, and positive middle/final phases.

**What I did:** I called that coherent D-1 buy continuation and sized +700.

**What I got wrong:** this is the clearest self-inflicted miss of the run. The brain's high-confidence play `tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell` was fully armed at all four thresholds: +3052 cleared >1000, >1500, >2000, and >3000. Its instruction is explicit: **never read a large same-day buy tilt as next-day bullish evidence**. Its audit says the D-1 arm is a coin flip. I had the play, its evaluability stamp, and its evidence, and I still promoted the exact forbidden inference.

**My diagnosis:** reasoning/consultation failure, not data failure. A high-confidence applicable play lost a conflict to a generic direction heuristic. This is the first thing I would fix before asking for any new data.

### 2026-07-29 — C core Wednesday — ABSTAIN, p50 -150, actual +340, error $490

**What I saw blind:** aggregate flow near neutral/buy, large prints sell-leaning, mixed phases, and a -0.469 D0 CDD revision.

**What I did:** I kept a mild negative market p50 but declined the trade.

**Result:** p50 sign was wrong, but the ABSTAIN was appropriate given the internal conflict.

**My diagnosis:** good authority control, imperfect market lean.

### 2026-07-30 — D storage Thursday — ABSTAIN, p50 +250, actual +180, error $70

**What I saw blind:** current survey consensus still absent at the cutoff, aggregate flow flat, big prints strongly buy, and +0.643 D0 CDD.

**What I did:** I refused to invent a print surprise, kept the large print-day range, and ABSTAINED.

**Result:** best numerical p50 of the run, while preserving the no-call decision.

**My diagnosis:** D's refusal logic worked very well here.

### 2026-07-31 — E Friday — CALL +600, actual +480, error $120, direction hit

**What I saw blind:** +1099 signed lots, 129 big prints at 0.569, and the known 07/30 storage print at +28 versus +37 survey (-9 Bcf tighter than consensus), plus a small positive Friday CDD revision.

**What I did:** I called +600 and separated the Friday bullish call from the outgoing weekend handoff because forward CDD decayed into the next Monday.

**Result:** good sign and magnitude.

**My diagnosis:** this was the cleanest CALL of the run because multiple independent causal channels aligned and I did not need to manufacture missing information.

## What the run says about the 1,800+ data surface

**I do not want more broad data points yet.** The served surface was sufficient to run every day and to expose my mistakes. In at least two major misses (07/20 and 07/28), the brain already contained the warning I needed. Adding another hundred fields would not have repaired that.

What I would change before expanding the data universe:

1. **Surface conflicts among already-served plays more forcefully without pruning anything.** When a high-confidence, fully-armed play directly prohibits an inference that a generic heuristic is about to make, that conflict should be impossible to overlook. All 90 plays should remain available.
2. **Wire the already-possessed Sunday-reopen trade-flow/L1 state into B's Monday packet if it exists.** B's role explicitly expects it. This is a serving/wiring issue, not a request for a new data family.
3. **Preserve and probably use ABSTAIN more aggressively.** My three ABSTAIN p50s had $250 MAE versus $1,038.6 on CALLs. The refusal mechanism was materially better calibrated than my confident calls in this run.
4. **Keep D's missing-consensus discipline.** Both storage Thursdays were handled better because I refused to fabricate a survey number or use future post-print evidence.
5. **Do not reopen S114/S125/S126 substrate work from this result.** Wind/solar, M-13, causal slices, role parity, and the roll hole #8 guard all behaved as designed. The measured problem is downstream reasoning and one Monday serving seam.

## What I did not have

- A separately served Sunday-reopen trade-flow/L1 read in the 07/27 Monday packet, despite B's role expecting Sunday thin prints as positioning hints.
- Current pre-print storage survey consensus on 07/23 and 07/30. I treated this as a named gap and did not fabricate it.
- Price-bearing delivery-vs-absorption during blind mode. That is **not** a gap to fix; it is the causal wall.
- Current U26 price-derived contract-structure values immediately after the Q26->U26 seam. The packet explicitly warned that frozen structural price blocks were Q26 vintage. I respected the warning; I am not asking to weaken that wall.
- `magnitude.emission_ceiling_check` input on the run. It was repeatedly `INPUT_ABSENT`; I did not reverse-engineer it.

## My answer to Greg

The setup is better for **auditability** than the old run: I could see the full data universe, all 90 plays, exact play evaluability, named defects, and the explicit scored-leg caveat. Nothing important had to be hidden from me to make the packet fit.

But this run also proves that **availability is not the same as correct consultation**. I had enough information to avoid at least some of my largest mistakes and still selected the wrong evidence hierarchy. My next work should be on how I resolve conflicts among the brain I already have, not on adding more inputs.

The strongest positive result is that the causal walls and ABSTAIN behavior held. The strongest negative result is the 07/27-07/28 wrong-way cluster. I would not promote this run as an improvement over the old blind. I would use it as a clean failure sample, fix the reasoning-priority seam and Monday reopen wiring, then run the next blind group before deciding whether the data universe needs to grow.
