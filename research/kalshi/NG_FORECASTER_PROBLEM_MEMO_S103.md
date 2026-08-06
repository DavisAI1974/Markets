# NG Intraday Forecaster — the recurring MAGNITUDE / REGIME-SELECTION problem (S103 diagnostic memo for an outside reader)

**Purpose.** Hand this to a fresh reader (ChatGPT) with NO access to our code, tape, or data and ask:
*where is the flaw in our forecasting logic, and what would you change?* This memo is fully
self-contained — every term, number, and example is defined inline. We are looking for insight into
a **persistent, recurring** pattern, not a one-off bug.

---

## 1. What the system is (so you can reason about it cold)

We forecast the **daily direction and magnitude of natural-gas (NG) futures moves** (NYMEX Henry Hub),
which we then trade as the underlying of a Kalshi daily prediction-market contract. We "walk" the
calendar in **2-week blocks** (~10-12 trading sessions each), called Groups: G7, G8, ... We are
currently at **G16 (Mar 29 - Apr 10, 2026)**.

Each block runs a two-step loop:

1. **BLIND step (the skill test).** An agent forecasts every day of the block *without ever seeing the
   actual price tape for those days*. It sees only: (a) a versioned rulebook we call the **brain** (a
   JSON of ~36 "plays" = condition->behavior rules), and (b) a **decision-state**: the market
   conditions knowable *at the moment of forecast* (storage levels, weather forecasts, positioning
   reports, the futures curve, a calendar of scheduled events, and prior-session order-flow
   statistics). The blind produces, per day: an overnight gap guess, an intraday move guess (in
   dollars), and a shape. This is scored against the real tape.

2. **REFINE step.** After scoring, a second agent is *allowed to see the real tape* and reverse-engineers
   *why* each day moved, then writes GENERAL rules (never day-specific memorized answers) back into the
   brain. The rule is: **magnitudes must be DERIVED from measurable state, never fitted to the answer.**

We measure each day two ways: **direction** (did we get the sign right) and **drift** (cumulative
dollar error of "if you had followed the guess"). $1.00 of NG move = $10,000 in our units ("MULT").

**The actual files (if you have repo access — full index in the companion
`NG_FORECASTER_PROBLEM_MEMO_S103_ADDENDUM_FILES.md`):**
- The rulebook / "brain": `research/kalshi/knowledge/ng_brain.json` (version s102.3, ~36 plays).
- The BLIND instructions (how the blind is told to reason — the panel of 3):
  `research/kalshi/agents/blind_shared.md` + `agents/blind_angle_storage.md` +
  `agents/blind_angle_positioning.md` + `agents/blind_angle_weather.md`.
- The REFINE instructions: `research/kalshi/agents/refine.md`.
- The per-group loop + design intent: `research/kalshi/agents/README.md`.
- The renderer: `research/kalshi/continuous_rt.py`; the scorer: `continuous_score.py`.
- G16 (the block in this memo): decision-state `research/kalshi/renders/ng_refine_s95/grp16_state.json`;
  the 3 blind forecasts `forecasts/grp16_agent{A,B,C}.json`; the synthesis `forecasts/grp16.json`;
  the blind scorecard `renders/ng_refine_s95/g16_score.json`; the refined view
  `forecasts/grp16_refined_view.json`.
If you only open three: `agents/blind_shared.md` (the reasoning rules), `forecasts/grp16.json` +
`grp16_agent{A,B,C}.json` (the competing calls and how we combined them), and `grp16_state.json`
(what was knowable at forecast time).

---

## 2. THE PHENOMENON we want explained (the recurring pattern)

Across every block we have walked, the **BLIND scores mediocre-to-poor and the REFINE scores
near-perfect** — and it is remarkably consistent:

| Block | Blind direction | Blind cumulative error | Refined direction | Refined error |
|---|---|---|---|---|
| G7  | 3/10 | large | 9/10  | small |
| G8  | 7/10 | lean-right | 10/10 | small |
| G9  | 13/20 (block-lean MISS) | crested early, sold the cold | 18/20 | small |
| G10 | 6/11 (false flip) | — | 11/11 | drift +320 |
| G11 | 6/12 | drift **-13,190** | 10/12 | -3,890 |
| G12 | 6/12 | +5,480 | 11/12 | -220 |
| G13 | 4/12 | +2,800 | 12/12 | -250 |
| G14 | 4/12 | **-4,350** | 12/12 | +500 |
| G15 | 8/12 | **-3,260** | 12/12-equiv | every day <160 |
| G16 | 8/11 | **+2,365** | 11/11 | drift +40, every day <40 |

**The blind sits structurally around 30-70% direction with large magnitude error. The refine sits
structurally at 90-100% with tiny error — every single time.** The refine insists (and we verify) that
its magnitudes are DERIVED from state that *was already present at blind time*. So the information to
make the right call was almost always available to the blind. **Why can the blind never do live what
the refine does in hindsight?** That gap is the phenomenon.

---

## 3. The magnitude error FLIPS SIGN block-to-block (the specific recurring flaw)

This is the part that most smells like a logic flaw rather than just "forecasting is hard." The blind's
magnitude error is not random — it **alternates between over-sizing and under-sizing, and the reason each
time is a MIS-SCOPED LESSON carried from the previous block.**

### G15 (Mar 15-27): blind OVER-sized a give-back
- The block was a give-back (prices drifting back down after a run). The blind correctly called "down,"
  but **guessed a cumulative -3,490 vs an actual -600** — nearly 6x too deep.
- Two specific failures:
  - **Wed 03-18: actual +1,900, blind guessed -400.** This was the day the give-back *ended and reversed
    up*. The turn signal was sitting in the prior session's order flow: on 03-17 the "big-print buy
    share" was 0.643 against an overall sell session of 0.413 — i.e., **large players were absorbing/buying
    the bottom** while the tape looked like selling. The blind read that divergence as merely "a reason to
    make today's down-day smaller" instead of "the bottom is in, tomorrow reverses up." It kept walking
    the chain down through the turn.
  - **Fri 03-27 (contract expiry): actual +1,160, blind guessed -350.** The blind applied a
    "crest-trim" pattern (sell the peak into the weekend). But the correct pattern was
    "expiry-covering-into-settle" (shorts buy to close before expiry = an all-day rally). Two patterns
    look similar; the blind picked the wrong one.

### G16 (Mar 29 - Apr 10): blind UNDER-sized a bleed (the OPPOSITE error)
- The block was a steady hard sell-off, 3.035 -> 2.653 (a -3,820 bleed). The blind again called "down"
  but **guessed only -1,455** — this time far too *shallow*.
- **Root cause we identified: the blind took G15's lesson ("don't over-size shoulder-season give-backs")
  and applied it as a UNIFORM damp on every down-day of G16.** But that lesson was only ever valid for
  *counter-trend* prints, not for *with-trend* bleed days. It over-generalized a scoped rule into a
  blanket one, and damped the whole block toward flat.

**So: G15 taught "smaller," and the blind over-applied "smaller" in G16 and missed a bleed. If G16 now
teaches "bigger," we are worried it will over-apply "bigger" next block.** This ping-pong is the flaw we
most want an outside eye on.

---

## 4. The SELECTOR flaw (how we resolve competing drivers) — with the exact example

For G16 we tried something new: we ran the blind as a **panel of 3 independent agents**, each told to
weight a different family of drivers first:
- Agent A: **storage/supply-trajectory first** (this is injection season; storage was building a surplus
  = bearish).
- Agent B: **positioning & market-structure first**.
- Agent C: **weather & day-pattern continuation first**.

Then we (the orchestrator) **synthesized** their three forecasts into one, day by day.

The panel behaved beautifully in one respect: the three agents **agreed** on the down days and the block
direction, and they **disagreed exactly on the 3 days that turned out to be the hardest** — a genuine,
useful uncertainty signal. We even flagged those days as "divergence / high uncertainty."

**And then we got all 3 flagged days wrong.** Here is why, and it is the crux:

- On the divergence days our synthesis **damped to the middle / averaged** the competing views. Example,
  **Tue 04-07**: Agent A guessed **+250**, Agent B **+500**, Agent C **-300**. We synthesized to **~0
  (flat)**. The actual was **-220.** Averaging a bimodal disagreement (two say strongly up, one says
  down) produces a number that *no one* believed and that is wrong whichever camp was right. **When the
  truth is "one regime or the other," the mean is the worst estimator.**
- The other two flagged misses, same shape:
  - **Wed 04-01: actual -600, we guessed +100.** Agents B/C leaned mild-up ("far-window cold building,
    pre-report coil"); Agent A leaned down. We split toward up. The fundamental "cold building" story
    overrode a sell-tape that was screaming down.
  - **Mon 04-06: actual -470, we guessed +300.** A modest cold snap was entering the near-term forecast,
    so B/C called it up. But the cold was *sub-threshold* (heating-degree-days ~15.8, in a band we have
    flagged as "too small to move price in shoulder season") — it had no physical demand mass to sustain
    an intraday rally. It priced ONCE in the weekend reopen gap (04-05, which we did call up correctly,
    +400) and then the sell-tape immediately reasserted. We treated a sub-threshold cold add like a
    winter cold add.

**The pattern:** every one of these misses is a day where a FUNDAMENTAL story (cold coming, surplus
building, pre-report positioning) pointed one way, an ORDER-FLOW signal pointed the other, and **we let
the fundamental narrative win — or we averaged — instead of deferring to the flow.**

---

## 5. The signal we keep under-weighting (concrete, with numbers)

We collect a never-hidden, decision-time-legal statistic each day: **the prior session's order-flow
"sell share"** (fraction of volume that hit the bid vs lifted the offer; <0.50 = net selling pressure).

In G16 this number was **below 0.50 on ALL 11 sessions** (range 0.396 - 0.495). It was a **persistent,
uninterrupted sell-tape for two straight weeks.** Every single intraday session went down. The only up
move in the whole block was the one overnight *gap* (the cold-add reopen), not an intraday move.

**This single signal, taken as the direction call, would have gone 11/11.** It was in front of the blind
the entire time. But the blind treats it as a minor tie-breaker, subordinate to the fundamental-family
reasoning, so on the days the fundamentals told a compelling (wrong) story, the flow got overruled.

We separately have an even finer order-flow tool (per-trade "dip_imb_level" / order-flow imbalance) that
in earlier research called direction with ~93% accuracy on strong-flow legs — but it lives in the
"execution layer" and we have deliberately kept it *out* of the open-time blind forecast. That may be
part of the problem.

---

## 6. Where the blind is GOOD vs BAD (the cluster pattern)

**Good:** pure continuation days inside an already-clear regime. When the tape is obviously trending and
nothing competes, the blind nails direction and size. The G16 consensus down-days (03-29, 03-30, EIA
report days 04-02 and 04-09, 04-08, 04-10) all scored fine.

**Bad, and it clusters on four day-types:**
1. **TURN days** — where a move exhausts and reverses (G15 03-18). The blind extrapolates the running
   trend through the turn.
2. **DIVERGENCE days** — competing drivers point opposite ways (G16 04-07). The blind averages/hedges.
3. **COUNTER-CATALYST days** — a scheduled event or weather change points against the prevailing tape
   (G16 04-01, 04-06; G15 03-26). The blind lets the catalyst narrative override the tape.
4. **REGIME-BOUNDARY magnitude** — shoulder-season vs winter sizing, where a rule true in one regime is
   false in the other (the G15<->G16 over/under ping-pong; also an earlier finding that "warm-weather
   cuts invert their price meaning in shoulder season").

---

## 7. Our current hypotheses for the ROOT cause (please critique / extend)

1. **Order-flow direction is under-weighted at open time.** The persistent sell-tape (sell-share <0.50)
   and the finer imbalance tool are strong *direction nowcasts*, but the blind treats fundamentals as
   primary and flow as a tie-breaker. Hypothesis: **flow should be the primary direction gate, and the
   fundamental families should set magnitude/where-it-can-go, not sign** — especially when they conflict.

2. **Rules lack machine-checkable SCOPE, so lessons leak across regimes.** "Don't over-size the shoulder"
   was true for counter-prints and got applied to with-trend bleeds. Every rule may need explicit,
   testable pre-conditions (regime, day-type, driver-alignment) so it *cannot* fire outside its
   validated scope. Hypothesis: the ping-pong over/under error is entirely a scope-leakage artifact.

3. **We BLEND competing hypotheses instead of SELECTING one.** Averaging is the wrong operator when the
   outcome is bimodal (regime A or regime B, not the average of the two). We just wrote a first
   "divergence-resolution" rule (in an injection-season sell regime, default DOWN unless the opposing
   catalyst clears specific thresholds), but we suspect the deeper fix is a **regime CLASSIFIER** that
   picks one driver as dominant per day rather than a synthesizer that compromises.

4. **The blind/refine gap may be structural and unclosable by rules alone.** The refine always wins
   because it sees the tape. Maybe the blind can never classify the regime from open-time state as well
   as the refine classifies it from the realized tape — in which case the real product is not "forecast
   the day" but "detect the regime *live, intraday* as the tape reveals it" (we have a separate
   futures->Kalshi latency edge that lets us react a few seconds behind the futures move). Is open-time
   point-forecasting even the right frame, or should we forecast a *distribution/scenario tree* and let
   the live tape collapse it?

---

## 8. Specific questions for you (ChatGPT)

1. Is the over/under **magnitude ping-pong** (Section 3) best explained by scope-leakage of lessons, or
   is there a more fundamental estimator problem?
2. When independent models **disagree bimodally** (Section 4, the 04-07 example), what is the right
   combination operator? (We suspect: NOT the mean. Classify-and-select? Weight by a regime prior?
   Defer to the flow nowcast?)
3. Given a **persistent order-flow direction signal** that would have gone 11/11 (Section 5), how should
   a forecaster weight a strong nowcast against a compelling but wrong fundamental narrative? Is there a
   principled way to know when the narrative should override the tape and when it should not?
4. Is the **structural blind-vs-refine gap** (Section 2) evidence that open-time point-forecasting is the
   wrong frame, and we should forecast scenarios + detect the regime live?
5. What are we **not** looking at? What overlooked pattern, timing effect, or combination would you test?

---

## Appendix: quick glossary
- **Block/Group:** a ~2-week walk segment (G16 = Mar 29 - Apr 10, 2026).
- **Blind:** forecast with no access to the block's actual prices (the skill test).
- **Refine:** post-hoc analysis allowed to see the tape; writes general rules back to the brain.
- **Brain:** versioned JSON rulebook (~36 condition->behavior "plays"); the ONLY thing that changes
  block-to-block besides the market data.
- **Drift:** cumulative dollar error of following the guess. MULT: $1.00 move = $10,000.
- **Decision-state:** all conditions knowable at forecast time (storage, weather forecast, positioning,
  curve, event calendar, prior-session order-flow stats).
- **Sell-share / b_share:** fraction of prior-session volume that hit the bid (<0.50 = net selling).
- **S1-void / injection / shoulder:** spring/fall "shoulder" seasons have weak heating/cooling demand, so
  weather matters less and storage-trajectory/flows dominate — a regime where winter rules mis-fire.
- **Give-back:** prices retracing after a run. **Bleed:** a steady one-directional sell-off.
- **EIA report days:** weekly storage report (Thursdays) — scheduled catalysts.
