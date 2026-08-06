# SESSION HANDOFF — 2026-08-05, S111 (the session the target changed)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain **s105.0, 82 plays** — unchanged in
content, **restructured in form** (see THE BRAIN GETS A SCHEMA).

No group was run. No play was merged. The session's output is a **reframe, three research briefings,
four binding decisions, a schema, and a set of measurements that invalidate how we have been reading
our own scoreboard.**

---

## THE HEADLINE: THE PRODUCT IS A CURVE, AND WE HAVE NEVER SCORED IT

Greg laid out the forecasting architecture across a long thread. It is written in full in
**`research/kalshi/FORECAST_ARCHITECTURE_S111.md`** and recorded as **D32**. The short form:

The walk is not a scoring exercise, it is a **library build**. Each past session gets its conditions
and the curve it traded. Forecasting inverts it — project conditions, reason to how the session should
**behave**, retrieve a past day whose **shape** matches that behaviour, re-anchor its level, monitor.
**The analog does not do the forecasting; it renders it.**

**Consequence:** the curve is the product and the scoreboard has never touched it. D27 records as
reassurance that "no score is affected — scoring reads `guess_day_move_usd` and never touches the
path." Under this architecture that is the alarm, and it explains how two consecutive groups shipped
paths under different cum conventions with nobody noticing until Greg looked at a render.

Load-bearing pieces, in Greg's words: **level is the only free parameter, amplitude is a rejection
test not a knob** (*"a little knob turning is fine but if you're doing it too much then you're no
longer forecasting"*); **the scrap signal is slope, not level** (*"level movement keeps the same
linear equation"*) — level errors are correctable, slope errors are not; **checks are tape-triggered,
not clock-triggered**; **the adjustment loop is the product** (*"you just have to adjust faster and
better than everyone else"*); one object, three lanes, diverging as late as possible, with dispersion
free from the cohort that passed the match test but was not chosen.

---

## THE MEASUREMENTS, AND TWO OF THEM SHOULD CHANGE HOW WE READ THE WALK

### 1. The blind loses to a zero-change forecast in six of seven blocks

Extraction validates against the committed record exactly (G19 939, G20 788, G21 632, G22 596,
G23 592).

| block | mean abs actual | MAE | MAE ÷ actual | dir |
|---|---|---|---|---|
| g17 | 355 | 451 | 1.27 | 5/10 |
| g18 | 583 | 521 | 0.89 | 5/10 |
| g19 | 799 | 939 | 1.17 | 4/10 |
| g20 | 738 | 788 | 1.07 | 6/10 |
| g21 | 588 | 632 | 1.07 | 5/10 |
| g22 | 527 | 596 | 1.13 | 4/10 |
| g23 | 457 | 592 | 1.30 | 5/10 |

Forecasting zero gives MAE **exactly equal** to the mean absolute actual move. **The improvement
narrative — 939 down to 592 — is the market getting quieter**, not the forecaster improving: realized
moves fell 799 → 457 over the same span. The shrinkage hypothesis was tested and **refuted** (mean
absolute blind forecast is flat at 324/272/266/352/322/290/311), so this is not compression. The
forecast systematically calls about **57%** of the move that actually happens.

**This is a benchmark, not a verdict** (Greg's correction, and it is right): those runs were degraded
— `vol_regime`, the magnitude conditioner, **dead G16-G20**; `session_b_share` a hard **0.0 on all
eight scored-leg days of both G22 and G23**; the MBO book layer **stood down group-wide** for
g21/g22/g23; 0710's tape absent from every slice; `contract_structure` frozen at one vintage;
`options_surface` strikes 10x wrong until S110; the first G22 blind voided outright. It measures a
machine with several senses unplugged, on an architecture we are replacing.

**ACTION CARRIED:** wire zero-change and seasonal-naive baselines into `blind_score_nonpooled` so no
future number can be read without them. For seven blocks we compared MAE to previous MAE and called
the fall an improvement, having never computed what doing nothing would have scored.

### 2. We cannot currently measure forecast skill at all, because the system cannot decline

Greg: *"we didn't have a 'no call' option so we had to pick something and it would make something up
to justify its guess."* Measured across 50 blind days carrying a declared confidence: **exactly one
was declared high**, and the confidence field **does not discriminate** — `low` slightly outperforms
`med` on both the zero ratio (1.14 vs 1.16) and direction (50% vs 45%).

So the corpus has no clean-read population to compare against. **A forced number and a confident one
are indistinguishable downstream** — which is exactly what C-0715 wrote when it concluded NO CALL was
correct handling and the contract would not let it say so. **NO CALL is therefore a measurement
prerequisite, not a trading feature.** Three free numeric triggers exist (matrix-profile discord, the
EIA published sampling-error floor ~4 Bcf at 90%, an ensemble confidence gate) and **a discord score
is a number**, so no contract change is required.

### 3. D23 measured — and it inverted my own recommendation twice

Built `condition_audit.py` (report-only). The measure is the **degenerate-block share** — of the
blocks where a condition was evaluable, in how many did it give the same answer every day — not the
pooled fire rate, which is a cancellation artifact in the shape D4 forbids, applied to a trigger
instead of an error.

`gw_hdd >= 16.4` fires **46.6% pooled over 161 sessions** and looks healthy; per block it is 12/12
g11, 12/12 g12, 19/20 g9 and **0/10 on all four summer blocks**, discriminating only in the shoulder.
**I recommended converting value bars to percentile form; the two percentile conditions already in the
brain turned out to be the worst in the set** (`<= 5th percentile`, degenerate in 10 of 11 blocks),
while the healthiest measured is an **absolute** bar sited at the centre of its distribution. Two
diseases, conflated: **transfer** failure (cured by shape form) and **discrimination** failure (cured
by centring — a rate property, not a form property). Full detail in **D28**.

---

## THREE RESEARCH BRIEFINGS (all committed, all research and not doctrine)

**`GAS_SIGNAL_BRIEFING_S111.md`** (+ synthesis-only cut). Six lenses. **Directional level forecasting
dies at 5-7 days measured on Henry Hub price itself** — not the day 10-12 meteorological number; the
gap is the market having already priced the forecastable part. What survives past day 7: dispersion,
the forward calendar, and the revision process. **The dimension budget is the hardest finding:**
`L = k/r^d` caps our matching dimension at about 3, so a regime label is the only viable retrieval
key. Top gaps: ISO day-ahead net load (the sign-flipper that fixes 0629), **ECMWF ensemble members,
free under CC-BY since 1 Oct 2025**, forecast-progression deltas, LNG feedgas. **Live risk flagged:
the EIA Natural Gas Weekly Update's final edition was the week ending 21 Jan 2026** — if our weekly
balance reads it, it has been silently stale for six months.

**`GAS_OPTIONS_SYNTHESIS_S111.md`** (+ full). Conclusion: **our forecaster does not support an options
business today**, and the one-day ATM straddle price is the yardstick that decides it. The x10 LNE
strike trap is **solved** — a confirmed Databento bug (12 Jun 2024): decode strikes with the
*underlying future's* display_factor. **Gas has inverse leverage** — vol responds more to up shocks —
so long puts are the worst possible expression of our down-lean weather model. **Weeklies do not exist
as a venue** (~4,000 contracts/day across five expiries).

**`COMPETITIVE_BRIEF_S111.md`** (+ full). **Gas is the least machine-penetrated liquid energy
contract**: 24.5% average HFT share against WTI's 52.1%, **19% of volume with a human on both sides**,
and the CFTC's own market-quality result *fails* in natural gas. But: **the Kalshi gas ladder is
~$3,600 of notional with eleven ATM trades in 6.5 hours** — the lag edge is uncontested because it is
too small to contest, and Kalshi lists hourly contracts on WTI, gold, silver, platinum and palladium
but **only daily/weekly/monthly on gas**. Also: **the hedgers are not on our screen** (ICE cleared LD1
is 20% larger than NYMEX NG and is 57.7% producer/merchant long), and **~72% of Henry Hub volume
involves a calendar-spread leg**. Positioning: a calibrated distribution conditioned on the burn stack
and day class, not a direction call.

---

## THE BRAIN GETS A SCHEMA (D29)

Before: 82 plays carrying **97 distinct field names**, most appearing once, with `forward_evidence`
fragmented across four separate keys. **Nothing could be asked of the brain as a whole** — every audit
this session had to be a bespoke regex. After: **24 field names, 7 statuses.**

`brain_schema.py` — validate / migrate / sections / report, dry-run default, backup first.
**Lossless by construction**: 367 ad-hoc keys preserved verbatim under `legacy_notes`, and `--write`
refuses unless a round-trip proves every leaf value still reachable (**1,652 leaves, 0 lost**).
**The dry run stopped itself three times across the two migrations** — twice on real losslessness bugs
I had introduced, once on an unmapped status per the SOP rule that a gap stops the line.

`conditions[]` is populated **only from a hand-curated map (8 of 82)** — regex-parsing prose triggers
is the error that produced holes #8 and #9. The other 74 are `unparsed`: an open task, never a guess.

Greg's calls: **`DESCRIPTOR`** added to the status enum (a real category — `structure.squeeze_unwind`
says of itself *"DESCRIPTOR grade, regime context, not a scored play"*), and **`NOVEL_N1`** to the
support enum (*"some things won't have past instances because it was the first time we saw them but
that doesn't make them bad"*).

**Non-play sections migrated and APPLIED** (S111, after the audit was stopped):
`doctrine_tier3` → `doctrine` with the session as a field (10 of 21 entries carried one);
`open_frontier` normalized from 27 strings + 6 dicts to one shape; `fingerprints` session key moved.
Round-trip lossless (2,598 leaves, 0 lost); backup `ng_brain_s105.0_presections_backup.json`.
`reasoning_method`, `mechanisms` and `ruled_out_by_target` were surveyed and **left alone — already
clean**.

**The work list is now visible instead of invisible: 82 of 82 unaudited for support, 82 of 82
corpus-unsearched, 74 conditions unparsed, 65 with no falsifier.**

---

## DECISIONS D29-D32

**D29** the brain has a schema. **D30 a finding with no home in DECISIONS.md does not exist** — the
instance is the memo that created the file: `TURNAROUND_MEMO_S110` section 1.3 had four items, the two
marked CLOSE became D15/D16 and are retired, **the two marked FIX never became decision lines and
neither was done**. By S111 the brain carried twelve statuses including the exact 40-word sentence the
memo quoted, and both magnitude dialects are still live. **D31 nothing we declared dead is actually
dead** — a refutation is scoped to the cell and instrument it was measured on; the burn gate should
have been scoped to summer injection-season days, and its load-bearing kill argument rested on a
**heating-weighted** degree-day index the vendor methodology says is wrong in summer. **D32** the
forecast architecture.

---

## OPEN, IN PRIORITY ORDER

1. **RE-RUN THE 82-PLAY AUDIT, all eight batches, under a CORRECTED RUBRIC** (Greg's call: "let's do
   all 8 in the next session"). The S111 run was stopped at 3 of 8. **The partial is real and it is
   the headline finding: 19 of 32 plays are OUTCOME_CREDITED — the S108 signature, right answer wrong
   reason — against my regex's estimate of 9 in all 82.** It traced **140 instances** across 32 plays
   and caught the seeded burn gate unprompted. Saved as `BRAIN_AUDIT_PARTIAL_S111.json`. **Fix the
   rubric first**: it conflates `ASSERTED` with a genuinely novel n=1 finding, which Greg flagged —
   `NOVEL_N1` is already in the schema enum.
2. **Wire the zero-change and seasonal-naive benchmarks** into `blind_score_nonpooled`.
4. **Build NO CALL** — the prerequisite for any subsequent measurement being interpretable.
5. **Check whether the weekly balance reads the dead EIA page.** Minutes; live staleness risk.
6. **One store + generated spawns.** `RUN_SOP.md` carries 13 slot placeholders across 36 occurrences,
   every one filled by hand — which is how NC-1 happened. Curve-building doctrine moves into the
   brain (served at spawn); plant policy stays in the ledger; both files become renders.
7. Reinstate the burn gate under D31, decided by the seasonal degree-day weight rebuild.
8. G24 needs a **data pull**, not a re-stage (`group_config` g23: "data year ends ~07-20").

---

## NONCONFORMANCES AND CORRECTIONS (mine, this session)

- **I killed a healthy workflow on a bad diagnosis.** Two refutation agents ran eleven hours; I read
  elapsed time as a stall and stopped them. The cause was that Greg's phone was off and approval
  prompts had nowhere to go. Recovered by resume — cached batches, only the unfinished lenses re-ran.
- **I stated three things that later measurement reversed**: that TRAIL beat FIXED, then that it lost
  (the paired test excluded asymmetrically; full enumeration says neither); that 31% of served
  quantities are "block context" (76% are dead feeds and 24% are blind-mask artifacts — my tool
  discarded `_`-prefixed keys and was structurally blind to `_mask_note`); and that the corpus "cannot
  measure information at all" (the control had no resolution; low power lands *at* the null, not
  below it).
- **A false claim reached a commit.** `condition_audit.py` asserted `gw_hdd >= 16.4` "never
  discriminates INSIDE a block" while the tool's own output says it splits in 7 of 14. That sentence
  went into the commit message and into D28. **Still to fix.**
- - **A-6 corrected on Greg's challenge.** I wrote that the dipole exhaustion arm was "never tested on
  gas". It was — S90 ran it on NG NYMEX directly: static divergence did not transfer, exhaustion gave a
  faint right-signed pulse (0.410 vs 0.382) on one trend day at 1-sec bins, and Greg's own note said the
  1-sec canary is far too coarse because the edge lives at native tick. It is already a brain play. The
  open item is the RESOLUTION of the test, not whether it was done.
- **125 served quantities are globally constant** — one value across all 60 scored days of all six
  blocks (`storage_vintage` frozen at an as-of date in March, `ngwu_balance` dead since September).
  Served-but-dead at a scale nobody had counted. Belongs on the andon board.
