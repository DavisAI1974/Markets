# FORECAST ARCHITECTURE — S111 (2026-08-05)

**Status: DESIGN, agreed with Greg in session S111. Nothing here is built.** Recorded as DECISIONS
**D32**. This document exists because the architecture was worked out in conversation and existed
nowhere else — it is the single most losable output of the session, and everything queued behind it
hangs off it.

Read with: `DECISIONS.md` D23-D32, `GAS_SIGNAL_BRIEFING_S111.md` (the measured constraints),
`COMPETITIVE_BRIEF_S111.md` (what the field looks like), `GAS_OPTIONS_SYNTHESIS_S111.md`.

---

## 0. WHAT WE ARE ACTUALLY BUILDING

Greg, verbatim, and it reframed the whole programme:

> *"The whole point in mapping what happened before and realizing the logic and why that day traded
> as it did is so that we can look at market conditions, what we think market conditions are going to
> be, and build forward curves from that."*

**The product is a PRICE CURVE.** "Curve" is the trader's noun for the pricing curve — do not read it
as a claim about smoothness. It is jagged. It is still a curve.

**The historical walk is not a scoring exercise. It is building a LIBRARY.** Each past session gets
two things attached: the conditions that were present, and the curve it actually traded. The refine's
real job has never been to get a day's number right — it has been to establish *why* that day traded
the way it did, because that "why" is the retrieval key. **A day we scored well but explained wrongly
is a corrupt library entry**, which is why a play being right for the wrong reason is treated as
seriously here as a play being wrong.

**Forecasting inverts it.** Project the conditions, reason to behaviour, retrieve the matching shape,
re-anchor its level, then monitor.

### The consequence that reorganises everything

**The curve is the product and it is the one thing we have never scored.** D27 records, as
reassurance, that "no score is affected — scoring reads `guess_day_move_usd` and never touches the
path." Under this architecture that sentence is the alarm. It also explains how two consecutive
groups emitted paths under two different cum conventions with nobody noticing until Greg looked at a
render: nothing downstream ever consumed them. We have been optimising a scalar and shipping the
product unmeasured.

---

## 1. THE MACHINE, IN ORDER

### 1.1 Project the conditions

From the served state and the forecast feeds, form a view of what the market conditions will be on
the target session. This is the step whose horizon is measured and short — see §4.

### 1.2 Reason to expected BEHAVIOUR

> *"We have to look ahead at what we think market conditions are going to be based on our 60-some
> inputs and come up with what we feel is how the market is going to behave that day."*

This is where the brain's plays operate, and it never gets skipped. Greg: *"we're always going to
have to be reconstructing no matter what."*

### 1.3 Retrieve a past day whose SHAPE matches that behaviour

**The analog does not do the forecasting. It renders it.** You have already concluded how the session
should behave; the library supplies a real, traded, detailed shape instead of a smooth guess, with
intraday texture nobody would invent by hand.

It also gives a built-in check: **if the projected conditions were right and the shape still does not
match, then either the condition set is wrong or the conditions-to-behaviour map is wrong.** Those are
separable failures.

Search order — a hierarchy, not a single distance:

1. **Seasonal window: ±2 weeks calendar, hard filter.** Greg's key. Day length and weather-forecast
   regime are the two biggest drivers, and a two-week window holds day length near-constant by
   construction. `solar.gw_day_length_h` is already served.
   *Side effect worth naming: this dissolves most of D23. The reason `gw_hdd >= 16.4` looked broken is
   that we were comparing July to January in the first place. Inside a two-week window the values are
   comparable and the transfer problem largely stops existing.*
2. **Regime label.** Four North American regimes from k-means on detrended standardized 500hPa PCs,
   free from ERA5. **This is what makes the dimension budget survivable — see §4.2.**
3. **Day class.** No Mondays scoring Fridays (S101 doctrine). EIA Thursday, options expiry, futures
   LTD and roll days are all deterministic day classes computable years ahead.
4. **Shape distance**, on the behaviour concluded in §1.2.
5. **Condition compatibility as a GUARD, not a key.** After a shape match, verify the retrieved day's
   conditions are consistent with the projection. Two days can trace the same line for unrelated
   reasons; without this check we would never know.

### 1.4 Transplant: level is the only free parameter

> *"We can adjust the whole day up or down to adjust for the price differences but the shape should be
> very close if our market conditions that we predict match what's going on that day."*

**Amplitude is a REJECTION TEST, not a knob.**

> *"If you are also adjusting amplitude more than just a little, then you should be using a different
> forecast because there's probably a past day that is a better representation... a little knob
> turning is fine but if you're doing it too much then you're no longer forecasting."*

This is the refine's own **"magnitudes DERIVED, never fitted"** rule applied one step later. Three
consequences:

- **One free parameter cannot be tortured into fitting.** A single degree of freedom is the strongest
  overfitting guard available.
- **The retrieve-vs-construct boundary becomes EMERGENT rather than legislated.** Retrieve when a
  candidate passes the amplitude test; when nothing passes, that failure *is* the signal to construct.
  Far-out days fail more often because the projected conditions are fuzzier, producing exactly the
  pattern Greg described without anyone writing a horizon rule.
- **The rejection rate is free instrumentation** — how often no past day passes is a coverage measure
  for the library, needing no outcome data at all.

**The tolerance must be pre-committed.** "A little" will otherwise expand to whatever the day in front
of you needs — the same shape as the burn gate's both-ways clause, a rule that could accommodate any
outcome and therefore said nothing.

**Structural variables get replaced too, not just price level.** Coal capacity is the worked case: the
displaceable coal fleet shrinks monotonically, so an older analog is biased on that limb no matter how
well its weather matches. Correcting it is value replacement applied to a structural quantity.

### 1.5 Monitor, continuously, and adjust or scrap

> *"You'll see it within the first few trades and know you need to adjust for the next one. If you're
> still adjusting then it's time to look for something else."*

**The scrap signal is SLOPE, not level.**

> *"You can tell that it's wrong when the rate of increase or decrease is starting to differ, meaning
> the algebraic equation starts to change. Level movement keeps the same linear equation."*

Differencing removes the level automatically — no best-fit step, no fitting at all. The principle
underneath: **level errors are correctable, slope errors are not.** That is exactly why one is an
adjustment and the other is a scrap.

The state machine, as stated: slope agrees but level drifts → re-anchor and continue. Re-anchor again
→ on notice. Still adjusting → the analog is wrong, retrieve another. **Direction disagreement
short-circuits to immediate scrap** — that is a falsified story, not a strained one.

**Checks are triggered by the TAPE, not the clock.** A fixed cadence either misses the break or wastes
attention on a quiet market. Our `path_p50_curve` 2-hourly grid is a human summary and must not be
what the monitor consumes — **the retrieved analog's own tick tape is the reference**, at whatever
resolution the market is trading.

**Three instruments, one lagging, one leading, one falsifying:**
- **Slope divergence** — lagging by construction; a slope change is only measurable after it starts.
- **The dipole's exhaustion arm** — leading; reads the current leader failing before price turns.
  *Open, and stated correctly: it HAS been tested on NG. At S90 static divergence did NOT transfer,
  but exhaustion showed a faint RIGHT-SIGNED pulse (oppose+exhaust 0.410 vs trend+strengthen 0.382,
  +2.7pp) on n=1 trend day at 1-sec bins. Greg's load-bearing note then: the 1-sec canary is FAR too
  coarse, the edge lives at NATIVE TICK, and the real test is pending at native tick, per-cell,
  event-time. Already carried as `timing.subsecond_reversal_exhaustion` (conf 0.25), correctly scoped
  as a turn-timing/execution edge and never a blind open-time curve input. The open job is the
  resolution, not the question.*
- **Named structural events** — did the turn arrive at `turn_time_et`? A missed or inverted turn
  falsifies the story regardless of the residual.

**The band is calibrated from the library, not chosen.** Replay past days against their own best
analogs and measure how good matches actually diverge hour by hour. That gives a threshold that came
from data. **Calibrate on two axes at once: detection rate AND alert rate** — a band that cries wolf
recreates the staffing problem in a different costume.

### 1.6 Architecture of the live loop

**The LLM never sits in the hot path** (S98 doctrine). A deterministic process computes slope
agreement and sign agreement on the tick stream and raises a flag; the reasoning agent is woken by the
flag to decide adjust-versus-scrap.

**Scrapping the forecast and exiting the trade are separate decisions and must stay separate.** The
monitor says the analog is no longer valid. What that means for a position depends on the instrument
— on a daily you can be wrong all session and right at settle; on futures the slope break *is* the
loss; on options a break that raises realized vol can help a long-gamma book while the directional
view dies. Couple them and you will be talked out of correct exits and into wrong ones.

---

## 2. WHY LIVE IS NOT A BLIND PROBLEM (intraday)

Greg's correction, and it stands:

> *"If we have our forecast and the trades are following along the historic curve, and the market
> conditions in real time are still tracking the historical ones, that's a pretty good gauge... the
> historical curve is our 'look ahead' essentially, with the caveat that it can change."*

Live at 10:00 holds **refine-grade information up to 10:00**, with the analog supplying 10:00 onward
and two independent confirmations running continuously (does the tape still track the shape, do the
conditions still match). That is a materially different information state from the blind.

**Where it does not hold:** the pre-open entry is blind-grade (no tape exists for that day yet), and
**multi-day has nothing to confirm against** — there is no D+5 tape until D+5 arrives. So the
confirmation advantage is an intraday advantage, which sharpens the horizon question rather than
dissolving it.

---

## 3. THE LIBRARY

**Contents per session:** the conditions present, the curve traded, the reasoning for why it traded
that way, and the outcome. Roughly seventy refine posteriors already exist and are exactly this
artifact — the walk has been building the library without calling it that.

**Depth arithmetic, and it is binding.** A ±2-week window is about 20 trading days per year. Split by
day class, roughly **4 candidates per class per year**. We hold about one year of NG tape ending
~2026-07-20. Three years puts it near a dozen per class; five years near twenty.

**Validity has a ceiling that depth cannot fix.** Greg: no further back than **1 year for coal load**,
because the fleet no longer exists — *"it's certainly not going to be going up from there."* One year
gives the level anchor (and spans a full seasonal cycle, which is why one year specifically); **the
announced retirement schedule gives the slope**, which is why no history is needed for the trajectory.
Beyond coal, the same warning appears from the analog literature: operational systems saturate near
four years of archive and then **degrade**, because the world changes underneath the library.

**Instances must be traceable.** An instance counts only if it traces to a posterior or an actual —
a date, a number, a file. Prose citing prose is one instance, not two. And per D24's qualification,
three states are recorded distinctly and never collapsed: **found / searched-none / not-searched.**

**A novel finding with no precedent is not a weak finding.** Greg: *"some things won't have past
instances because it was the first time we saw them but that doesn't make them bad."* Hence
`NOVEL_N1` in the support enum — an argued mechanism seen once is a different object from a claim
with no argument.

---

## 4. THE MEASURED CONSTRAINTS THIS DESIGN MUST RESPECT

### 4.1 Horizon

Directional level forecasting dies at **5-7 days**, measured on Henry Hub price itself — not at
day 10-12, which is where raw *meteorological* skill ends. The gap is the market having already
priced the forecastable part. What survives past day 7: **dispersion** (variance is additive and most
of the vol curve is deterministic), **the forward calendar** (maintenance, LNG in-service, expiry,
rolls — dated forward, no horizon limit), and **the revision process** (the run-to-run delta is what
actually moves price at day 6-15).

### 4.2 The dimension budget — the hardest constraint in the design

`L = k / r^d`. For a decent match at a single retrieval: d=3 needs ~1,000 sessions, d=4 needs ~10,000,
d=10 needs 10^10. **Our library supports a matching dimension of about 3, at most 4.** Condition on
ten things simultaneously and the retrieval returns a day provably no closer than a random one —
**and it will still return one, confidently, with a magnitude attached.**

Two corollaries: more analogs *costs* dimension, and **depth does not rescue you**.

**This is why the regime label matters.** It collapses the match to d≈1-2, which is the only dimension
the library size permits, with a 7-46 day skill horizon that brackets the whole window.

**Action: compute the effective d of any retrieval and publish it beside the call. Hard-fail above
budget.**

### 4.3 The benchmark

Measured S111 across seven blocks: **blind MAE is ~1.13x the mean absolute actual move, losing to a
zero-change forecast in six of seven blocks.** Direction is 4-6/10 throughout. The apparent
improvement from 939 to 592 tracked realized volatility falling from 799 to 457 — the market got
quieter and we read it as progress.

**That is a benchmark, not a verdict.** Those runs were degraded (`vol_regime` dead G16-G20,
`session_b_share` a hard 0.0 across two groups, the book layer stood down group-wide, a session's tape
absent, forced calls throughout) and ran an architecture we are replacing. But it is the bar the new
architecture must clear, and **the zero-change and seasonal-naive baselines must be wired into
`blind_score_nonpooled` so no future number can be read without them.**

### 4.4 NO CALL is a measurement prerequisite, not a feature

The contract requires a numeric magnitude and the coordinator hard-fails on anything else, so a
specialist with no read still emits a number **and constructs a rationale to justify it**. Measured:
across 50 blind days with a declared confidence, **exactly one was declared high**, and the confidence
field does not discriminate accuracy at all — `low` slightly outperforms `med`.

**So we cannot currently measure forecast skill, because the machinery never let a genuine read
distinguish itself from a manufactured one.** Three free numeric triggers exist: matrix-profile
**discord** (today has no analog anywhere in the corpus), the EIA published sampling-error floor
(~4 Bcf at 90%), and an ensemble confidence gate. **A discord score is a number** — no contract change
required.

---

## 5. THE THREE LANES

**One object, three lanes, diverging as LATE as possible.**

Shared: data plane, condition projection, behaviour reasoning, library, retrieved analog.
Divergent: how each product reads it.

| lane | wants | notes |
|---|---|---|
| **Kalshi daily** | a probability at a point (17:00 settle vs strike) | horizon-native, already docked. A binary is a **digital**: `N(d2) − Vega·(∂σ/∂K)`, so positive gas call skew makes an upside digital worth **less** than naive flat-vol N(d2) |
| **Futures** | a trajectory, marked continuously | slope break *is* the loss; tightest response |
| **Options** | a distribution over trajectories | needs dispersion, not just a path |

**Ledgers are never pooled** (S98). A good number in one lane is not evidence in another. Kalshi is an
easier test than it looks — you can be wrong about the whole session shape and right at settle — so
**terminal accuracy and path accuracy get scored separately, and the path score gates expansion.**

**Dispersion comes free and resolves the pick-one-versus-distribution tension.** One analog for the
central path; **the cohort that passed the match test but was not chosen** gives the band. Nothing is
averaged, nothing is a shape that never traded.

**Do not compare our dispersion to implied vol naively.** Ours is a physical-measure sample; implied
is risk-neutral. Gas realized runs ~80% of implied (IV/RV ≈ 1.24), so a naive comparison fires "sell
vol" nearly every day — rediscovering a thirty-year-old published fact and mislabelling it as alpha.
And in gas, short vol dies on the **upside**.

---

## 6. SCORING — GREG'S BAR, AS A FUNCTION

> *"It can get the peaks and valleys a little wrong, but that's about it. More wrong than that and
> it's going to cost you a lot of money."*

Error terms, ranked by tolerance, **kept separate and never summed** (D4 — never average above and
below):

| term | tolerance |
|---|---|
| **direction of each leg** | none |
| **timing of the turns** | little |
| **amplitude of peaks and valleys** | some — the same tolerance as the amplitude reject test |
| **level** | free — that is what re-anchoring is for |

**And accuracy has a time dimension we have never scored.** A forecast right at 09:00 is worth far
more than the same forecast right at 16:00, because by then the market has priced it and there is
nothing to enter. "How early was this decidable" belongs in the score beside "was it right" — the edge
converts into early entry, and the futures-to-Kalshi lag is why.

---

## 7. WHAT IS MEASURED, WHAT IS ASSUMED, WHAT IS OPEN

**Measured:** the horizon boundary (5-7 days); the dimension budget; the zero-forecast benchmark
failure; the forced-call contamination; the degeneracy of specific bars; that gas is the least
machine-penetrated liquid energy contract (24.5% average HFT share vs WTI 52.1%, 19% of volume with a
human on both sides); that the Kalshi gas ladder is ~$3,600 of notional with eleven ATM trades in
6.5 hours.

**Assumed and not yet tested:** that analog retrieval outperforms the play-chain blind — *the analog
method has never been run*; that shape match plus condition guard beats either alone; that the dipole
exhaustion arm works on gas; that the amplitude reject test has a stable tolerance.

**Open:** the target fire rate for a condition (deliberately not asserted — inventing one repeats the
disease); the smoothing window for slope detection; how early a shape break is reliably detectable;
whether the retrieval key should be shape-first or condition-first; the D26 scoring clock, which stops
being academic the moment a daily is traded.

---

## 8. ONE STORE, GENERATED VIEWS

The recurring failure this session is one disease in three costumes: **a document that describes what
should happen, sitting apart from the machinery that makes it happen.**

- SOP v1.6 pinned cum-from-OPEN, and it reached the agents only because someone hand-copied it into
  the BLD-1 template.
- **D25 — an explicit instruction about the order a specialist should reason in — has never been read
  by a specialist**, because `DECISIONS.md` is served to nobody.
- The S110 memo's two `FIX` items never became decision lines and were therefore never done.
- `RUN_SOP.md` carries **13 slot placeholders across 36 occurrences, every one filled by hand** —
  which is exactly how NC-1 happened, a calendar premise asserted from prose instead of looked up.

**The fix is the same in all four cases: one store, and the documents become generated views.**

- Spawn templates live in the store as structured objects. **`spawn.py` fills slots BY LOOKUP** from
  `group_config`, `flow_calendar` and the anchor artifact, and emits the exact prompt. Running
  off-SOP becomes impossible rather than forbidden, and NC-1 becomes structurally unreachable.
- **Curve-building doctrine lives in the brain** (`reasoning_method` / `doctrine`), which *is* served
  at spawn. **Plant policy stays in `DECISIONS.md`.** The split rule: *does a specialist need it to
  build a curve?* → brain. *Does it govern how the plant runs?* → ledger.
- `RUN_SOP.md` and `DECISIONS.md` keep existing as human-readable renders. They stop being sources of
  truth.

The pattern already exists in miniature: `decision_trace.py --embed` writes the self-contained record,
answer beside explanation, because Greg asked for exactly this at S110 — *"I don't want a context file
out there that isn't tied to the decision it was used to make."* This is that principle applied to the
whole store instead of to one day's number.

---

## 9. ORDER OF WORK

1. **Wire the benchmarks** into `blind_score_nonpooled` — zero-change and seasonal-naive, always
   printed. Cheapest item, and it makes every future number readable.
2. **Build NO CALL** (discord score + EIA sampling floor). It is the prerequisite for any subsequent
   measurement being interpretable, not a trading nicety.
3. **Compute the effective matching dimension** of any retrieval before building on it.
4. **Score the curve**, not the scalar — the four error terms, kept separate.
5. **Build the library index**: seasonal window, regime label, day class, shape descriptor. The
   shape vocabulary is already emitted (`onset_time_et`, `turn_time_et`, `trend_vs_chop`,
   `continuation_vs_reversal`, `path_p50_curve`) and has never been collected or searched.
6. **Test the dipole exhaustion arm on gas** — S90's unfinished item, and the only leading instrument.
7. **One store + generated spawns.**
8. Then, and only then, a new group under the new architecture.
