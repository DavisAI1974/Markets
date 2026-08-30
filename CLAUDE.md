# CLAUDE.md — DavisAI Markets / Kalshi (Updated 2026-08-30, Session 116)


## S116 — THE WORK WAS ALREADY BUILT, AND FIFTY-FIVE DROPS WERE RESTORED (read `SESSION_HANDOFF_2026-08-30_S116.md` + `research/kalshi/FRANKIE_A_ARM_PRIOR_WORK_RECOVERY_20260829.md` + `DROP_IN_FRANKIE_A_ARM_NEXT.md`)

**Branch = `chatgpt/frankie-raw-mbo-benchmark-20260828`. 552 -> 613 tests. NOTHING LAUNCHED.**
Decisions 57 -> 61. No group run, no merge.

**THE FINDING THAT MATTERS MOST. Greg: *"this should have already been built in some capacity
for the exhaustion prediction part. is this related?"* IT WAS THE SAME WORK.** Four estimand
proposals written earlier in the session for sections 4.10/4.11/4.12/4.16 were reinventing a
**frozen, hash-bound vocabulary built 2026-08-16 to 2026-08-25** across ~200 files. All four are
WITHDRAWN. **t0 is a DIPOLE FLOW SPIKE**, not a price-level event, and price never selects or
orients it. **PRIOR/T0/H+N already exists as `TIMING_LADDER`** with the classes strictly ordered.
**SAME/FLIP means polarity versus the LATEST PREDECESSOR**, frozen with committed counts of 1,546
FLIP / 1,883 SAME of 3,429. **The mirror is the SIDE-SWAPPED SIDE STRING**, already computed.
**`t` IS A PRICE TICK** — `3t/5t/8t/13t` are ZigZag reversal thresholds and 358/993/1802/4386 are
the median leg durations IN SECONDS they produce; Fibonacci is coincidental (2t was dropped after
a five-point sweep). **Greg's duration ruling restates a correction frozen on 2026-08-18**:
*"exhaustion is a duration / remaining-runway signal, not a direction predictor"* — and the frozen
program solves the clock problem better than my revision did, keeping absolute-second horizons but
anchoring them on the **dynamic episode endpoint, "never t0+60 by fiat."** **The fix was the
ANCHOR, not abolition.**

**AND THE BUILD PLAN CHANGED. The missing layer is not six adapters — it is the per-second roll20
/ dipole SUBSTRATE.** The built candidate is a 1-second flow event; the A-arm unit is the
nanosecond F_LAST group. **3,429 frozen events against 4.26M groups.** The registry REQUIRES the
bridge as `CAUSAL_STREAM_REQUIRED` and **nothing in the benchmark computes roll20 or any dipole
from the MBO stream** — which is why 4.10/4.11/4.12 have nothing to feed them. **The open question
for Greg is a UNIT question, not a phase question.** `PHASE_INDEX` scores **0 of 11** against the
built corpus and four names are reused with a different referent; `SEED_STATES` (P/O/S/X) and
`RecognitionLabel` (PRIOR/T0/H+N) ARE right and must stay.

**D60 — NOTHING IS DROPPED WITHOUT DISCUSSING IT FIRST.** Greg, on the cost: *"this is the problem
that i have been fighting the whole time that things are dropped for whatever reason and not
discussed and then we find out we have to rerun because it was important."* And: ***"i don't care
about memory. restore every piece."*** **Fifty-five confirmed drops across ingest, traversal and
output, every one restored.** The per-record `ApplyEffect` never reached the traversal at all
(`top_before_price_raw` and `removed` had **zero readers anywhere**); every frame asserted
`fifo_priority_reconstructed: True` while asking for the book WITHOUT order ids; the two
exact-evidence layers emitted **counts, not rows**, so the gate guaranteeing exact members was
satisfied by an integer; `AssignmentLedger` used one capped list as both sample and count, so
twenty mismatches and twenty million both read 20. **My first fix merely COUNTED the legacy rows,
reasoning that memory was a decision for Greg — that reasoning was itself the defect.**
**D61: restore by WRAPPING, never editing — the V4 adapter is hash-locked and editing it broke six
supply-chain locks in one commit.** `FullCaptureAdapter` keeps everything while the locked file
stays byte-identical.

**LAUNCH READINESS, MEASURED:** sections fed by the driver = **clocks, coverage, one clock
advance**; ten receive **zero**. Adapters wired **0**, execution gate referenced by non-test files
**0**, workflows dispatching the driver **0**. **THE LESSON: I assumed wiring existed because
components did, and assumed nothing existed because the contract did not define it. Both are the
same error. Verify by EXECUTION, and search the prior corpus BEFORE proposing a definition.**



## S115 A-ARM — THE GATE WAS ENFORCING THE API ARCHITECTURE GREG KEPT CORRECTING (read `SESSION_HANDOFF_2026-08-29_S115_A_ARM.md` + `DROP_IN_FRANKIE_A_ARM_NEXT.md`)

**Branch = `chatgpt/frankie-raw-mbo-benchmark-20260828` (the Frankie raw-MBO benchmark line, NOT
the forecaster trunk). 552 tests green, was 522. NOTHING LAUNCHED.** Decisions 51 -> 57.

**THE FINDING. Greg: *"we're not using the openai api!!! we are running 5.6sol like you ran the
blind/refine groups. i have said this every session."* He has — and the reason it kept needing
saying is that THE EXECUTION GATE STILL ENFORCED THE API ARCHITECTURE.**
`validate_principal_execution` demanded `provider`, `requested_model`, `served_model`,
`principal_invocation_id` and reconciling token `usage`. **None exist in an agent-session run, so
the gate would have REJECTED a correct Sol run and accepted only an API one.** The correction
lived in prose while the check demanded the opposite — the S114 do/dont lesson exactly: **a
decision recorded where nothing enforces it is a decision that has not landed.** Now file-based,
matching `native_staging.py`: a committed staged request plus a committed artifact, both
hash-bound; identical hashes are refused because a run that returned its own input produced no
findings. **The token-usage test was REPLACED, not dropped**, and a new test pins that a
provider-shaped record is REFUSED so the API shape cannot return.

**D52 THE CME TRADING-DAY SCHEDULE IS THE HOLIDAY AUTHORITY** (Greg: *"we follow cms trading day
schedule"*). Wired into `native_session`. Classes come from `plant_calendar`'s **RULES, not a
table** — the roster year is 2021 and `CME_HOLIDAYS` starts 2025-09-01, so a table would have read
"not a holiday" for every date in the window (the S112 expiring-table finding); the rules
reproduce all 16 committed entries, 0 mismatches. A `full_closure` is not a trade date and skips
like a Saturday. **A `partial_session` IS a trade date** — `flow_calendar` calling it "not a
business day" is the SETTLEMENT sense, and conflating it with the trading-day sense moves every
expiry-adjacent segment by a day. **`phase_within` REFUSES on a shortened date**: the close time
is recorded nowhere and a partial session runs NO settlement cycle, so those phases do not shift,
they do not exist. Roster verified unchanged BY EXECUTION.

**D53 THE A-ARM INPUT UNIT IS THE F_LAST GROUP.** Sections 4.6-4.16 were closed at their
boundaries and fed by nothing, because the contract specifies the CALCULATION and never the input
event. `native_group_adapters.py` is the missing layer — 4.8, 4.9, 4.13, 4.14 built and each
verified against the REAL calculator. **4.9 is a group-local ladder DELTA, not a book snapshot**,
and the scope travels ON the value (`LADDER_SCOPE`) because a caveat living only in prose expires.
**Lineage depth accumulates ACROSS groups** — within one cascade it would report max_depth 1
forever and read as a measurement rather than an artifact of the unit.

**SAY "UNFED", NEVER "REMAINING" — this wording misled once.** All sixteen sections ARE built and
tested (156 tests across the seven unfed ones alone). Only the ADAPTER is missing; their entry
points are each referenced by exactly one non-test file, the module that defines them.

**D55 THE BOX RECORD WAS STALE AND THE PREDICTED FAILURE HAPPENED.** Section 10a had written *"if
the instance was resized, the record was not updated, and the record is what the next session will
believe."* **Live-probed: `r6i.2xlarge`, 8 cores, 61.8 GiB, 32 GiB swap** — against a recorded
t3.xlarge/4/16. Greg right on every count, record wrong on every count. **AWS creds are GitHub-
secret scoped, so a session resolves NONE and only a workflow can settle it.** Corrected at source
in four live records; S91-S93 handoffs left untouched because a t3.xlarge was true when written.
**The one that mattered: the October sharded handoff sized workers at "three of four cores" on an
eight-core box.**

**D56 SIZE UP BEFORE THE RUN, THEN WATCH.** 5 of 16 sections nearly exhausted 62 GiB, so 16
sections needs ~200 GiB and 128 is still short — target `r6i.8xlarge`. **An EC2 type CANNOT change
on the fly; there is no live resize.** So the monitor is the WATCH, not the decision. Monitor LIVE
(capped self-trimming log, reports MIN_MEM_AVAILABLE / PEAK_SWAP_USED, never a mean); **resize
ARMED, NOT FIRED** (~4x hourly rate, Greg's call).

**D57 THE STEP1 WORKFLOWS NEVER TOUCHED STEP1 DATA.** Two fired on EVERY push to EVERY branch and
failed every time because **their YAML is invalid** — and **GitHub emits a JOBLESS startup-failure
run to REPORT a broken workflow, ignoring branch and paths filters.** Zero jobs: nothing
authenticated, no data moved. Both removed (0 of 186 now fail to parse); **the other 47 kept** —
valid, branch-filtered, zero runs across eight pushes. **Then I made the identical heredoc mistake
an hour later**, caught by `bash -n`. **RULE: verify a workflow by parsing the YAML, running
`bash -n` on every step, and RENDERING the remote script — never by reading it.**

## S114 — G24 WALKED BLIND (6/10) AND IT TIES DOING NOTHING, THE RENEWABLES FORCING IS WIRED, AND EVERY REPORTED DEFECT IS CLOSED (read `SESSION_HANDOFF_2026-08-06_S114.md` + `DROP_IN_S115.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-sg0n15`. Brain s105.4 -> s105.9, 90 plays — play
CALLS unchanged. G24 BLIND RUN AND SCORED. No merge. THE G24 REFINE HAS NOT RUN and is S115's
opener.** Decisions 44 -> 48.

**THE SCORE, WITH BENCHMARKS (A-1): 6/10 direction, sum|err| 4,890, drift +1,010, survives 21% —
and it is 0.98x zero_change (WE TIED DOING NOTHING) and 1.20x seasonal_naive (WE LOST TO "last
same-weekday move").** Best direction hit-rate of the walk. Hit-rate is not the product; the curve is.

**THE DOMINANT FINDING — SYSTEMATIC UNDER-EMISSION, AND IT IS GETTING WORSE.** mean|guess| /
mean|actual| = **0.29x, under on 8 of 10 days**, against g22 0.55x and g23 0.68x. Max emission 250
against a max realized move of 1,360. **Emitting small IS emitting near-zero, which is why we tie
zero_change.** Three competing explanations recorded and NONE promoted (D37): the brief's
stand-down passage biasing small; shrinking being CORRECT because four specialists had their sign
instrument refuted by the brain; or a genuinely hard block. Next run varies the stand-down passage
and holds everything else.

**THE RENEWABLES FORCING IS BUILT AND WIRED (D46, G-5/A-51).** New block
`weather_forcing_forecast`: forward wind and solar as a **31-member GEFS ensemble DENSITY**, per
day. Wind CF p50 swings **0.157 -> 0.292 across the block (nearly 2x)**, p10-p90 spread 0.027 to
0.096 — the width a specialist can decline on. **Blind-legal by vintage and AUDITED**: the 12Z
cycle of D-1, 10 of 10 days, 7.0h lead, zero violations. Wind and solar **never summed**. In
`state_health.REQUIRED_EVERY_DAY`. Four specialists had reported that no forward wind expectation
existed anywhere while `grid_stack.wind_mwh` is D+2 stale BY CONSTRUCTION.

**EVERY DATA DEFECT GOT A CAUSE, NOT A PATCH.** `model_disagreement` 100% null = a **BUILD-ORDER**
defect (store built 8 min before the raw archive landed) whose empty-but-PRESENT record **shadowed
the recompute fallback**. COT one publication stale **INVERTED a load-bearing term** (WoW -45,414 ->
**+2,953**) from Cloudflare 403ing urllib's default User-Agent *and* `--build` building 1 of 5
served codes. `storage_regional` frozen two prints behind `storage` in the same slice. **`vol_regime`
— the magnitude conditioner — carried 41 of 223 reopen STUBS inside its trailing sigma windows
(the header declared it and nothing ever filtered on it), and the S108 Monday-stub fix had never
reached it.** `options_surface.days_to_opex` was exempt from the relive for the WHOLE WALK because
`_RELIVE_FIELDS` walks top-level keys only. **The `ng_l1` writer did not exist** — `--schema mbp-1`
fell through to the trades writer, so a pull reported 333,530 rows and produced no file.

**PLAY EVALUABILITY (A-46), the highest-consensus request of the run.** `brain_view --state --day`
resolves every parsed condition against the specialist's OWN slice and stamps EVALUABLE /
INPUT_ABSENT / PARTIALLY_EVALUABLE, each numeric limb read out (`14.15 >= 3 -> ARMED`). **It
annotates, never drops.** It immediately found that `weather.summer_burn_lane_exclusion` — the play
that should have carried this block — pointed at a **PROSE pseudo-path**, which is why it stood down
on 8 of 10 days as **uncomputable, not inapplicable**. Now EVALUABLE and ARMED.

**TWO REGRESSIONS I SHIPPED AND CAUGHT, recorded because the pattern matters.** Making `scored_leg`
required turned g19-g23 **permanently red** (fixed structurally: states now stamp `_state_build`).
And `live_verdict` first flagged 43 of 90 by matching "degenerate" anywhere, catching plays that
merely DISCUSS degeneracy while concluding they are sound — **a false CANNOT_CHANGE_STATE talks a
specialist out of a working play.** Now 22, false positives clean.

**D45 THE REFINE DOES NOT NEED THE BLIND WALL** (Greg) — never gate or delay a refine on blind-wall
grounds. **D47 A STORE REBUILT IN A SESSION IS NOT A FIX UNTIL IT IS ON S3** — measured at close,
S3 still held PRE-FIX copies of four stores and `eia_surprise.json` was absent entirely; a fresh
session would have silently undone the day's work. **D48 all four keys in `~/.config/markets/env`**,
chmod 600, verified by name in KEYS.md.

**THE SCHEMA CORRECTION (Greg, at close): A LIVE STATUS ON DEAD EVIDENCE IS AN INVITATION TO FIRE
THE PLAY.** Measured: **15 of the 22 plays flagged by their OWN health or falsifier still read
PROVISIONAL** — the refutation was written down honestly in every case and simply sat BELOW the
`call`. That is the worst form of it, because **the falsifier fields were the run's most-praised
content** ("if you cut the view, cut CALLS before FALSIFIERS"), so a live status on a discharged
falsifier spends the credibility they earned. **AND THE do/dont RULE HAD SILENTLY EXPIRED**: S112
stamped 624 instances and caught 43 declines reading as fires, but never made it a SCHEMA RULE — so
every play merged since dropped it and **38 instances carried no action at all**, where a missing
action reads as a FIRE. Same defect, same door, two sessions later. **Brain s105.8 -> s105.9**: new
**`DEGENERATE`** status (the TRIGGER carries no information as written — distinct from REFUTED,
which says the CLAIM is wrong; the repair is to RE-SITE THE BAR, not discard the mechanism), **9
plays demoted on their OWN opening verdict**, `ACTION_ENUM` do/dont/observation with a hard gate,
and `fire_record` counting do/dont only so the 8 plays merged this session show **n=0 fires, n=0
declines** instead of an instance count implying a track record. **The full correction record —
five things we got RIGHT and should build on, six we got WRONG — lives in `brain_schema.py`
itself**, because that is the lesson: a finding recorded somewhere nothing reads is a finding that
expires.

**REFUTED AND WORTH KEEPING:** the "Monday stub in the 20260720 slice", filed by two specialists, is
NOT a defect — the block declares it three ways and the day's OWNER used it correctly. Both
reporters were non-owners reading a headline for a day they did not own.

## S113 — THE NO-AVERAGE RULE BECAME A FUNCTION, AND THE STORAGE LANE'S BIGGEST TERM TURNS OUT TO BE UNMODELLED (read `SESSION_HANDOFF_2026-08-05_S113.md` + `DROP_IN_S114.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`. Brain s105.0, 82 plays — UNCHANGED. No
group run, no merge.** Registry 87 items (75 live: 5 ESSENTIAL, 20 BIGGEST_WIN). Decisions 42.

**D37 — NO AVERAGE MAY BE A VERDICT, AND A REFUTED STORY DOES NOT DEMOTE A MEASUREMENT.** Greg had
to say the no-average rule for the tenth time, so it stopped being a sentence and became
`research/kalshi/per_event.py`. **AN R2, A CORRELATION AND A FITTED SLOPE ARE ALL AVERAGES** — that
is the form the rule kept being broken in, not the word "mean". Measured in ONE analysis: a pooled
correlation whose sign was opposite to every constituent cell (pooled, it said burning gas FILLS
storage); an R2 of 0.554 hiding a 92-improved / 72-worsened per-week record whose worst week got
WORSE; and an OLS slope quoted as evidence. The second half cost more: I wrote "DEMOTED" on an
observation because MY MECHANISM died. **An observation and the story explaining it are
independent** — the full cycle ran (a regularity held 9 of 9 monthly cells, three mechanisms
refuted, finally dropped for the right reason when its OWN evidence died holding burn constant
inside month).

**GREG TAUGHT UTILITY OPERATIONS AND IT KILLED FIVE OF MY MECHANISMS.** Registered, each measured
against our own data: **wind and solar are seasonally ANTI-CORRELATED** (wind 9.9 TWh/wk April vs
5.9 August; solar 3.5 June vs 1.4 December — never sum them into one "renewables" term); **time of
day is load-bearing** (*"Wind at night does nothing for gas demand. Wind at 7 in the morning
does"*) → A-28; **gas plays BOTH roles**, peaker and baseload, and is now more baseload than coal,
inverting our written stack → A-30; **coal is a startup-constrained RAMP** — ~24 h boiler warmup
forces a 1-2 week commitment, block-loaded at 100%, with tube leaks the reason for a shakedown week
→ A-31 + `coal_commitment.py`; **reliability is the trump card rarely played** (economic dispatch is
the base case, reliability-first a 2-3 month exception, regime-3 demand price-INSENSITIVE by
obligation); **the correlated-failure tail** (>$20 intraday gas when nothing has surplus, and
freeze-offs cut SUPPLY too) → A-33; **the mediated response** (a cold snap can show a coal ramp with
NO gas bump for a week) → A-34.

**D38 — BURN FOLLOWS GENERATION, NOT LOAD** (*"even if I don't have gas gen, my neighbor probably
has enough for both of us"*). A BA with no gas generation still creates gas demand. **CISO
net-imports p50 20.6% / MAX 41.7% of its load**; PJM runs both ways (2,691 export days, 25 import).
**US48 is the ONLY level where the interchange term collapses (p50 0.5%)** — the arithmetic
justification for D35 closing the BA list by reconciliation, not map coverage. **It is a BOUNDARY
term**: the storage/national roll-up needs NONE (it cancels pairwise), the HH lane needs its own
fence flow. Sign VERIFIED from the accounting identity `TI = sum(gen) − demand` — **not** by
assuming anyone is always an importer, because **power flows both ways in every system**.

**A-38 (ESSENTIAL) — THE STORAGE LANE'S DOMINANT COMPONENT HAS NO MODEL.** Greg scoped storage as
*"overall gas demand"*, so it was measured: STEO actuals, 52 monthly moves named individually,
**res/comm heating is the bigger mover on 33 of 52 and on 10 of the 10 largest**, and **on 12 of 52
power burn moved OPPOSITE to total demand** — every November in the record (202211 total **+16.1**
while power **−0.46**). **SCOPED PER D31: this does not refute the burn stack** (in summer res/comm
sit at their floor so all summer variance IS power burn; the HH lane is untouched). It says the
WINTER storage lane's dominant term — HDD to res/comm Bcf/d — is unmodelled. **The evidence is
MONTHLY and the traded object is weekly, so the weekly re-check comes before anything is built on
it.**

**BUILT: A-1** (three named benchmarks in `blind_score_nonpooled.py` — no error number without one
again); **A-13 / SOP v1.9** (BLD-1 and RFN-1 finally get `{DAY_CALENDAR}`, NC-1's structural cause;
verified by EMITTING, 22/22); **defect `h-frozen_countdowns`** (the price mask was freezing
distance-from-today fields — 20/20 mapping, FORWARD_ONLY g16-23); **`creds.py`** (ends the
scratchpad credential path, and ignores the container's injected `proxy-injected` placeholder that
would otherwise shadow the real AWS pair); **the restore do-not-destroy guard** plus the S3 push
that makes a local rebuild durable.

**NC-3, mine, and the third of its shape:** I reported that guard "negative-tested both directions"
when its firing branch had never executed — `NameError` on the next run, which aborted the restore
and took the data plane down. **A test that never produced the guard's OUTPUT did not test the
guard.**

**NEEDS GREG:** **A-11** (serving chain state means serving `cum_from_anchor`, which is PRICE
content — what non-price form may the blind hold?) and **THE BRAIN MERGE** (nothing from S113 is in
the brain, and specialists read the brain, not the registry — the largest gap at close).

## S112 — THE D29 WORK LIST IS CLOSED, THE BURN STACK IS REBUILT, AND EVERY LIST IS NOW COUNTED (read `SESSION_HANDOFF_2026-08-05_S112.md` + `DROP_IN_S113.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`. Brain s105.0, 82 plays — play CONTENT
unchanged, EVIDENCE transformed. No group run, no merge.**

**THE D29 WORK LIST IS CLOSED:** support unaudited **82 -> 0**, corpus unsearched **82 -> 2**,
conditions unparsed **74 -> 0**, no falsifier **65 -> 0**. The brain carries **624 instances — 306
`do` and 318 `dont`** across 55 plays holding both. Two audits ran: the 82-play support audit (**41
OUTCOME_CREDITED, 26 MECHANISM_VERIFIED, 10 NOVEL_N1** — half the brain rests on a number coming out
right rather than a mechanism being checked) and the decline audit (**384 declines, the rubric came
back negative 13 times, and 115 — 30% — are DATA_ABSENT**). **EQUAL FOOTING (Greg):** one
`instances[]` list, one `action` field, `do` vs `dont` — stamping found **43 declines already in the
brain reading as fires**.

**GREG REBUILT THE BURN STACK.** *"A stack would go nukes, coal, gas."* Coal is BASELOAD and cheaper,
so gas does not take its place. Wind and solar are *"just on or off. Not regulating to load."*
**Gas is the only term that regulates**, so anything that removes a forcing lands on gas. **HYDRO IS
AN INVERTED U AND BOTH TAILS ARE BULLISH** — past a river stage the Army Corps has the gates opened
and water goes through the SPILLWAY INSTEAD OF THE TURBINES, and *"hydro is never curtailed for
econ."* So the same low reading comes from two opposite states and **a single bar will be wrong in
one tail**. Measured on 119 scored days: the unaccounted slice falls 9.40% -> 7.04% while gas share
rises 34.8% -> 42.2%, about **2.0-2.3 Bcf/d** — the order of the 0629 wind event.

**THE HYDRO CARRY (A-20), Greg's hypothesis with its confounder.** *"When TVA is curtailed so are
those others."* A STATE co-occurrence, not a level correlation — the only form that survives the
inverted U. **Not the same rivers, the same HEADWATERS:** TVA's Blue Ridge, Nottely and Chatuge sit
physically in north Georgia, the Etowah drains the SOUTH side of the Tennessee Valley Divide while
the Toccoa drains the NORTH — **one storm total partitioned by a ridge**. **The confounder is pumped
storage** (Duke's Bad Creek + Jocassee ~2,200 MW, comparable to Southern's ENTIRE 2,730 MW hydro
fleet), which EIA-930 folds into `WAT`. **And TVA leads for a STATUTORY reason: FERC does not
regulate federal agency dams** — TVA runs under its own Act while the other four are FERC licensees
with binding guide curves. That makes the test DIRECTIONAL and falsifiable.

**D35 — THE TARGET IS TOTAL GAS DEMAND, NOT ATTRIBUTION** (*"don't care who is burning it or
where"*). No per-BA number is ever a deliverable — but per-BA is arithmetic we cannot skip, because
the stack is a per-BA subtraction and the response is convex, so **the total is not recoverable from
the average**. The BA list closes by **reconciliation to US48**, not map coverage. And the target is
not a national index: **Henry Hub is ONE physical point near Erath, Louisiana**, so the object is
**demand HH can SEE**, and the roll-up weight is burn x HH transmission.

**D36 + SOP STATION 0 — THE SESSION'S SHARPEST FINDING.** Greg asked whether the 13 S111 build
suggestions were still listed. **Twelve of thirteen had no registry item** — including the tropical
feed's sign INVERTING post-shale (a feed we built at S110), `vol_regime`'s smoothed state probability
computed WITH HINDSIGHT (a leak in the module that conditions magnitude), and EIA-930 excluding
behind-the-meter solar entirely. A briefing is a RECORD, correctly frozen, so its recommendations
live in prose nothing counts. Then: *"We can't spend time on an sop that we don't apply"* — **Station
0 is four andon checks that fired on the session that wrote them**, including catching an earlier
version of itself reading a `pending` placeholder as a pass. **It is RED on purpose: 6 of 7 briefings
have never been audited.**

**TWO REGISTRIES, because a list that is not counted is not a list.** **DOCUMENTS** —
`store/documents.json` + `store.py docs`, five classes, CONTENT gates because **mtime is not
staleness**: 55 of 151 tracked `.py` were absent from `KALSHI_TRADING.md`, and `PLANT_MAP.md` had
been edited that same session while naming none of the SOP's tools. First live catch was
`data_registry.py` itself. **DATA** — `data_registry.py` + `DATA_POINTS.md`: **1,717 served data
points, 1,129 READ BY NOTHING**, plus HELD-not-served (hydro fetched since 2019 and dropped at a
five-element serving list), PLANNED, and IDENTIFIED-not-committed.

**THE WORK IS TIERED: 61 open — 8 ESSENTIAL, 11 BIGGEST WIN, 42 REST** (`OPEN_ITEMS.md`, a render).
The essential eight are the honest gate on the next group, not the whole backlog. **G-28 first: it is
a LEAK CHECK, and until it clears, no group's magnitudes mean what they claim.**

**D34 — THERE IS NOTHING LOCAL.** git = code and records, S3 = data, `data/` disposable, and **no
artifact may name a desktop path**. The S111 audit partial carried 140 instances and **51, across 11
plays, cited `E:/Markets/...`**. Fixed 140/140. **Do not repair such a path by silently re-rooting
it** — my first guard did, and that hides the defect.

**THE PLANT (S112 additions).** `merge_gate.py` closes SOP gates 2 and 3 and **parks 5 of 5 real past
proposals**. `plant_calendar.py` is the clock from **RULES** (the hardcoded holiday table ends
2027-02-15), cal+0..cal+3 wrapping to day 1 — and **MEASURED: the calendar does NOT repeat on four
years**; the RULE is invariant, the DATE is not. `spawn.py` fills every SOP slot BY LOOKUP with NC-1
as a regression test. `chatgpt_handoff.py` generates the external brief from the registry, and
`delegated_prior` stops it re-asking a delivered question — which the first draft did three times.

**NEEDS GREG'S CALL:** **A-13** (`CAL_FACTS` reaches AUD-1 only — the structural cause of NC-1) and
**A-11** (serving chain state unblocks nine plays).

## S111 — THE TARGET CHANGED: THE PRODUCT IS A CURVE, AND WE HAD NEVER SCORED IT (read `research/kalshi/FORECAST_ARCHITECTURE_S111.md` FIRST, then `SESSION_HANDOFF_2026-08-05_S111.md` + `DROP_IN_S112.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`. Brain s105.0, 82 plays — content
unchanged, FORM restructured (`meta.schema = brain-schema-1`). No group run, no merge.**

**THE REFRAME (Greg, D32).** The walk is not a scoring exercise, it is a **LIBRARY BUILD**: each past
session with the conditions present and the curve it traded. Forecasting inverts it — project
conditions, reason to how the session should **BEHAVE**, retrieve a past day whose **SHAPE** matches
that behaviour, re-anchor its level, monitor continuously. **The analog does not do the forecasting,
it RENDERS it.** Level is the only free parameter; **amplitude is a REJECTION TEST, not a knob**
(*"a little knob turning is fine but if you're doing it too much then you're no longer forecasting"*).
**The scrap signal is SLOPE, not level** — level errors are correctable, slope errors are not. Checks
are **tape-triggered, not clock-triggered**. **The adjustment loop is the product.** One object, three
lanes (Kalshi wants a probability at a point, futures a trajectory, options a distribution over
trajectories), diverging as late as possible, with dispersion free from the cohort that passed the
match test but was not chosen.

**THE MEASUREMENT THAT REFRAMES THE SCOREBOARD.** The blind **loses to a zero-change forecast in six
of seven blocks** (MAE 1.13x the mean absolute actual move; direction 4-6/10 throughout), and the
939 -> 592 "improvement" is **the market getting quieter** — realized moves fell 799 -> 457 over the
same span. Shrinkage was tested and refuted. **It is a BENCHMARK, not a verdict** (Greg's correction):
those runs had `vol_regime` dead G16-G20, `session_b_share` a hard 0.0 across two groups, the book
layer stood down group-wide, and no ability to decline. **Never report an error number without a named
benchmark again.**

**AND WE CANNOT MEASURE SKILL UNTIL THE SYSTEM CAN DECLINE.** Greg: *"we didn't have a 'no call'
option so we had to pick something and it would make something up to justify its guess."* Measured:
**one high-confidence day in fifty**, and the confidence field does not discriminate (`low` beats
`med`). **NO CALL is a measurement prerequisite, not a trading feature** — and a matrix-profile
discord score is a number, so no contract change is needed.

**D23 MEASURED, AND IT INVERTED THE OBVIOUS FIX.** `condition_audit.py`: the measure is the
**degenerate-block share**, not the pooled fire rate — which is a cancellation artifact in the shape
D4 forbids, applied to a trigger instead of an error. `gw_hdd >= 16.4` fires 46.6% pooled and is
**0/10 on all four summer blocks**. The percentile form I recommended turned out to be the **worst**
in the set; the healthiest is an absolute bar sited at the **centre** of its distribution. Two
diseases: **transfer** (cured by shape form) and **discrimination** (cured by centring — a RATE
property, not a FORM property).

**THE BRAIN GETS A SCHEMA (D29).** 97 field names -> 24, twelve statuses -> seven, **provably
lossless** (367 ad-hoc keys preserved, 0 of 1,652 leaf values dropped; the dry run refused to write
three times). `brain_schema.py`. **The work list is now visible: 82 unaudited, 82 corpus-unsearched,
74 conditions unparsed, 65 with no falsifier.**

**THREE RESEARCH BRIEFINGS, all committed, all research not doctrine.** **Horizon: directional level
forecasting dies at 5-7 days measured on Henry Hub price itself** (not the day 10-12 meteorological
number); dispersion, the forward calendar and the revision process survive past it. **The dimension
budget `L = k/r^d` caps our matching dimension at ~3**, so a regime label is the only viable retrieval
key. **Gas is the least machine-penetrated liquid energy contract** (24.5% HFT vs WTI 52.1%, 19% of
volume with a human on both sides) — **but the Kalshi gas ladder is ~$3,600 of notional with eleven
ATM trades in 6.5 hours**, so the lag edge is uncontested because it is too small to contest. **ECMWF
ensemble members went free under CC-BY on 1 Oct 2025.** **LIVE RISK: the EIA Natural Gas Weekly
Update's final edition was the week ending 21 Jan 2026.**

**GREG'S STANDING CALLS.** **D31 nothing we declared dead is actually dead** — a refutation is SCOPED
to the cell and instrument it was measured on; the burn gate is first in line and its kill argument
rested on a heating-weighted degree-day index that is wrong in summer. **D30 a finding with no home in
DECISIONS.md does not exist** — the instance is the memo that created the file. **ONE STORE, GENERATED
VIEWS**: `RUN_SOP.md` has 13 slot placeholders filled by hand (that is how NC-1 happened);
curve-building doctrine belongs in the brain where specialists actually read it, plant policy stays in
the ledger, both files become renders.

## S110 — TWO GROUP CYCLES + TWO MERGES + THE FIRST RETIREMENT + THE PLANT'S OPERATING SYSTEM + THE PAPER DOCK (read `SESSION_HANDOFF_2026-08-02_S110.md` + `DROP_IN_S111.md` + `research/kalshi/agents/RUN_SOP.md` [BINDING])

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`. Brain s103.7 -> s104.0 -> s105.0, 82 plays.**

**G22 COMPLETE**: blind 4/10 sum|err| 5,965 drift -1,815 -> r1 **10/10 / 500 / -80** -> r2 **10/10 /
330 / +50**. **G23 COMPLETE (r1)**: blind 5/10 **5,920** drift **+4,900 surviving 83%** (the most
one-directional block of the walk and the FIRST to lean UP; actual cum -3,290 vs blind +1,610) ->
refine **10/10 / 720**. G23 was the last staged block.

**THE RESULT THAT MATTERS: A MERGED PLAY DIED ON ITS OWN FORWARD TEST.**
`weather.burn_conversion_gate` was merged at session start as the G22 centerpiece with a written
falsifier; G23 was its named test; **four specialists refuted it independently and its author refuted
it hardest**. D-0709's mechanism: **the CDD-add limb is a CONSTANT (d_gw_cdd h1 positive 20/20 across
two groups) - a limb that never changes sign cannot gate.** E-0710: both limbs pass and say "flip UP"
into a **-620** Monday, while the both-ways clause **capped a correct DOWN read** against a -660
actual - *"Not softened, it is my play."* E's mechanism: **burn is a numerator with no
balance-clearing denominator, so when the balance loosens at the demand peak, burn confirmation is
BEARISH information.** C-0715's cleanest evidence is **pre-graft and inside the play's own evidence
list**: G22 0624/0625, identical served burn 39.3, delivered **+800 and -60** on consecutive sessions.
RETIRED under a new declared class (status + refuting evidence as a new key). **THE DISSENT IS
RECORDED (Greg's instruction): C-0707 was RIGHT that the gate was mis-scoped on its day (+160
delivered), and NOBODY counted that instance - corrected tally 1-of-4, not 0-of-3.** The retirement
stands because it never rested on the tally. **Structural lesson merged: any tally assembled from
independent slices is systematically incomplete and must be recomputed at the coordinator.**

**THE LIVE CLAIM, AND IT IS BLIND-LEGAL: the IMPACT-COEFFICIENT COLLAPSE.** C-0714 retired the roll
window **within the same run** (container, not cause - removing roll supply did NOT restore impact:
realized 0.053 vs a 0.380 median, so *nothing was released because nothing was held*). What replaced
it: **k3 = price change per unit aggressor flow**, collapsing 0.302 -> 0.026 -> 0.018 after the 0709
void, with week-2 flows of +3,747/+6,326/+1,089/+1,333 producing only +200/-60/-20/+180. *A void is
price discovering where liquidity sits; once found, flow stops moving price.* **n=6 spanning G20+G23,
5/6 at <= $200 vs a 30% base rate, one counterexample named.** B-0706 adds an out-of-sample instance
by a different road (holiday thinness) plus the qualifier: **numb suppresses the NET 6.5x but the
RANGE only 1.5x.** **k3_prev is PRE-CUTOFF - it belongs in the blind's hands.**

**GREG'S OPEN DESIGN CALLS (D23-D27 in `DECISIONS.md`, his first business next session):** **D23
VALUE REPLACEMENT / SHAPE** - *"we can only pay attention to SHAPE for forecasting purposes; any time
you use it after that, the value has to be replaced"*; measured, **24 of 76 plays carried an absolute
bar and the plays that failed this session are the value-keyed ones**, sharpened by the burn gate's
death into: **a condition that cannot change state carries no information, whatever form it is written
in.** He expects to **test the changes on a new group**. **D24 RETRO-INSTANCE PROGRAM** - a mechanism
is n=1 until the corpus is searched, **qualified: past evidence is used WHEN AVAILABLE and a finding
is never disregarded for lacking it** (three states recorded distinctly). **D25 THE ORDER OF
REASONING**. **D26 the harness scoring convention** (20:00-to-20:00 vs a 17:00 clock; 0 on 8/8
Fridays identifies it). **D27 render continuity** (root-caused: why the drawn lines did not connect;
no score affected).

**THE PLANT (new, and the reason the rest survives):** **`agents/RUN_SOP.md` v1.6 = THE SPEC BOOK**
(verbatim spawn templates, slots by lookup, **nothing runs off-SOP**, deviations are nonconformances);
**`DECISIONS.md`** (append-only, 27 entries, **instance-inline rule**); **`plant_status.py`** andon
board + **`agents/QC_CHECKLIST.md`** (small-model, report-only); **batch records** + **inspection
certificates**; **`decision_trace.py`** binding reasoning to decisions by an id that stops resolving
the instant a number changes (**g22 30 ids, g23 40 ids, 0 unresolved**); **four reasoning ledgers**
carrying every specialist's ACTION beside its REASONING; `PLANT_MAP.md`, `KEYS.md`.

**THE DOCK: G0 CLOSED** - signed REST auth proven on BOTH prod and demo (HTTP 200); paper ledger with
four risk caps (11/11 selftest incl. negative tests proving each cap fires); daily paper loop quoting
the Kalshi public API **from the session container - no box needed for the paper stage**; tropical
feed built and live-smoked; `KALSHI_DOCK_S110.md` the full endpoint/auth reference. **Routing: NG
paper trades on the CLASSIC demo (KXNATGASD is live there); the margin platform has 33 perps and NO
natural gas.**

**NONCONFORMANCES (recorded, per the SOP's own rule):** NC-1 - a refine directive I wrote carried a
false calendar premise and C-0715 caught it against `flow_calendar`; plus my own D11 violation, caught
by the rule itself - I verified code **parsed** rather than **executed**, twice.

## S109 — G22 BLIND (4/10, sum|err| 5,965) + **HOLES #9/#10/#11** + the **STATE AUDITOR** role + the WEATHER MODEL REBUILT + brain s103.7 (68 plays) (read `SESSION_HANDOFF_2026-08-01_S109.md` + `DROP_IN_S110.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`.** The S108 filename-collision fix was
verified still live (`archive_blind.py` MOVEs; `assert_not_the_blind()` hashes) — the S109 box lists it
as open, but it was closed at S108 close-out. Nothing to redo.

**THE DEFECT, found auditing G22's staged state before spawning the blind.** `session_b_share` read
**exactly 0.0 on all 8 scored-leg days of G22 and of G23**, plus both `prior_full_session` limbs — 20
readings. **A FOURTH KIND of silently wrong input: WRONG ENCODING.** The two readers that can serve
`_tape_day_stats` disagree about how a side is spelled — the continuous reader appends the RAW TAPE
STRING (`"B"`/`"A"`/`"N"`), the S108 leg reader `tape_reconcile.load_leg_trades` appends flow_read's
SIGNED INT (`1`/`-1`/`0`) — and its docstring **claimed the two were mapped identically**. Every test in
the shared math is `s == "B"`, so on the leg path nothing matched, `buys` summed to 0, and the served
share was a flat zero. It is `state_health`-invisible for the same reason as holes #7 and #8: present,
numeric, in range, right owner, self-consistent.

**WHY ONLY THIS FIELD.** `_tape_enrich` copies `phase_b_share`, `big_print_b_share` and every
`*_two_sided` through from `flow_read` (the S107 defect-3 fix) — which **silently rescued them**.
`session_b_share` was the ONE b_share field missing from that copy list, so it alone showed the damage.
The omission was invisible for exactly as long as the harness's own value happened to be right.

**WHAT IT WOULD HAVE DONE.** 6 of 67 plays read the original series, 3 of them read ONLY it:
`daytype.eia_preprint_overextension_gate` limb (b) tests **`session_b_share` vs `big_print_b_share` for
COHERENCE** — a live 0.0 against a live 0.32-0.57 reads maximally INCOHERENT on **every day at once**,
and G22 carries two EIA Thursdays (0625, 0702), the day class that was 3,530 of G20's 7,880;
`timing.catalyst_continuity_frontrun` reads a sub-0.50 sell tape (0.0 is an extreme one, every day);
`direction.giveback_exhaustion_boundary` is a **SIGN** play. Blast radius is **forward-only** — G20, G21
and every earlier group were staged on the continuous string path and are untouched. **No completed
group's score is affected.**

**FIXED, three defences different in kind.** (1) SOURCE: `_tape_day_stats` normalizes the side encoding
at the point of use, so both readers compute the same quantity from the same math. (2) COPY-THROUGH:
`session_b_share` joins the `_tape_enrich` list, so flow_read's authoritative value overwrites.
(3) GUARD — **a RECONCILIATION, not a presence check**, because presence is exactly what passed:
`session_b_share == session_b_share_two_sided * (1 - unsided_volume_frac)` is an **algebraic IDENTITY**,
and `state_health` now treats a >0.002 breach as HARD. It reproduces every continuous-store day to 3 dp,
fails all 20 defective readings, and fires **zero** false positives across every historical group.
`load_leg_trades`' false docstring claim is corrected at the source.

**STATES REPAIRED WITHOUT A DATA PLANE** via `bshare_restage_repair.py` (committed, idempotent, dry-run
by default): the identity recovers the value from already-served quantities, so two staged groups are not
stranded waiting on keys that do not survive a session. Each repaired reading **declares itself** through
`session_b_share_basis`; carries up to ~0.002 of rounding error vs a re-stage off raw lots, and a later
re-stage overwrites it. Diff verified confined — 10 values changed + 10 basis keys added per group, none
removed. **G22 and G23 now pass `state_health` 0 hard.**

**THE ANCHOR WAS NEVER DELIVERED TO THE AGENTS (checked before spawning, on Greg's call).** The README
names the group data as three things — "the decision-state file **+ ANCHOR** + basis" — but
`grp<N>_state.json` carries **zero anchor-keyed leaves**, the specialist rule files are static and hold
no group data by design, and only **g15** ever had an anchor FILE. So the anchor has been a per-run
hand-carried number, which is exactly the shape S108 lost when the blind coordinator's hand-built alias
died with the scratchpad. A specialist spawned on "`grp22_state.json` ONLY" (as the S109 box words it)
has **no reference level for the cum-from-anchor path it is required to emit**.

`build_anchor_block.py` makes it a committed, reproducible artifact and **verifies rather than asserts**:
each group's anchor must equal the **PRIOR group's actual last-day close** — an independent measurement,
different file, different build step. That chain holds **exactly across G17->G23** (G22 3.198 = G21's
close on 06-19; G23 3.245 = G22's close on 07-03), and `anchor_lasthr_dir` is re-derived from the actual
price path and must agree (both -1, both confirmed). Either mismatch HARD-FAILS before a spawn: a wrong
anchor moves every day in the block by the same amount while every per-day error still looks locally
reasonable. Provenance is declared — final-hour levels come off the actual file's DOWNSAMPLED
`continuous` path, so trade count and signed flow are emitted **null by design** rather than computed
from a series that cannot support them.

**G22 AND G23 ARE THE FIRST TWO GROUPS OF THE WALK TO ANCHOR ON A HOLIDAY** (Juneteenth 06-19,
Independence Day observed 07-03; G17-G21 all anchor on normal Fridays). The anchor CLOSE is chain-verified
and sound. The anchor's LAST-HOUR DIRECTION comes off a tape ~1/5 as active (6,935 and 11,501 trades vs a
~37,000 median), and it feeds the E->A->B weekend seam — so the block carries an explicit
`holiday_caveat` telling the specialists to size the reopen read accordingly. Declared, not hidden.
Leak-audited: each anchor block contains only its own pre-block anchor session, zero in-window dates.
**Blind input is now the brain + `grp22_state.json` + `g22_anchor.json` — never the actual/evidence
files, which sit in the same directory and contain the answer.**

**G22 BLIND COMPLETE: 4/10 dir, sum|err| 5,965, drift -1,815, survives 30%** — second-best blind of the
walk on sum|err|, worst on direction. **THE DRIFT IS THE MISSED HILL**: realized gw_cdd ran 9.0 -> 17.5,
actual cum **+470**, blind cum **-1,345**, miss **-1,815** exactly.

**HOLE #11, and it VOIDED the first G22 blind: THE STATE LET EVERY SPECIALIST READ PAST ITS OWN DECISION
POINT.** A day's tape is served under the NEXT day's key, so with all ten days in one file day X's own
outcome sits one block later. **All three first-run specialists reached forward and ALL THREE DECLARED
IT** — D forecast an EIA print day already knowing the print; E built its whole handoff on its own day's
realized close phase. A prompt rule was not the fix (they were already under one); `build_causal_slices.py`
makes the future ABSENT. **HOLE #10**: `squeeze_watch`'s `_live` limbs were the FROZEN value under a live
name — S108 fixed a false negative here and shipped its mirror image, asserting `satisfied_live: true` on
five sessions whose live dte is 18-21 against a <=7 window.

**THE STATE AUDITOR is a new canonical role** (`agents/state_auditor.md`) — audit and forecast are now
separate jobs, which keeps the cross-day discovery channel that found eleven holes while the forecasters
run causally clean. Trialled blind on G21: found the off-instrument defect S108 called the hardest of the
eight, **without** the scored-leg reconciliation S108 used, and corrected a ground-truth claim of mine.

**THE WEATHER MODEL REBUILT (Greg, the session's most valuable thread).** Weather is **THE driver as a
continuous ASYMMETRIC SLOPE** (mild kills demand: big down; heat/cold: up but only some), with
`anomaly x duration x constraint` a **MULTIPLIER on top**. **A hill slopes, it does not gap** — that
resolves 0629, where the error was expecting the hill to gap (+480 forecast vs +50 actual). And **the gas
call is a STACK**: weather-driven load minus renewables minus what coal/nuclear can absorb. 0629
mechanically: gw_cdd 10.0 -> 14.8 exactly as forecast and **gas burn FELL 4.2 Bcf/d** because **wind rose
62%** — and `wind_mwh` was **served in every slice**, while A and B adjusted only for nuclear, 34x smaller.
Also: **summer gas demand is ~50% power burn**, so degree-day weights must be SEASONAL; the weights are
hand-set, unvalidated, and **OHIO HAS NO STATION AT ALL** against PJM being the largest gas-burning BA.

**Brain s103.6 -> s103.7**: +`supply.lng_export_throughput_vessel_line` (WIRED_UNPROVEN — the vessel line
is live and moving with zero consumers while `lng_feedgas_bcfd` is null and 278 days stale). 67 incumbents
byte-identical. **NEXT: the G22 REFINE**, then the auditor on G23.

## S108 — G20 DONE + G21 WALKED + **THREE MORE DATA HOLES** + brain s103.2 -> s103.6 (67 plays) (read `SESSION_HANDOFF_2026-08-01_S108.md` + `DROP_IN_S109.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`.** **G20 COMPLETE**: blind 6/10 err 788 ->
r1 10/10 err 79 -> **r2 10/10 err 64**, drift -2560 -> -360. **G21 COMPLETE (r1)**: blind 5/10 err 632
-> **refine 10/10, EVERY DAY UNDER 100, worst day 80**, five direction flips each on named evidence.

**THE SCORING RULE CHANGED (Greg, load-bearing): WE CANNOT AVERAGE ABOVE AND BELOW.** A day high by
4,000 and a day low by 4,000 net to ZERO on a forecaster that was catastrophically wrong twice. And
**mean error is a dashboard number, never a diagnosis — FIX OFF INDIVIDUAL EVENTS.** Measured, with
"survives" = |drift| as a share of total absolute error: G17 22% / G18 45% / G19 25% / G20 32% /
**G21 15%** — so drift flatters G21 MORE than any block. Honestly: drift -2560 -> +960 is a "62%
improvement"; **sum|err| 7880 -> 6320 is a 20% improvement**; the gap is cancellation. The lean fix
DE-CORRELATED the errors, it did not shrink them. `blind_score_nonpooled.py` prints all four together.
**The cost of ignoring this, measured**: G20 credited D's pre-print generator with 2,090 FROM DAY NETS,
intraday check never run — G21 found the SELECTION limb survives 4/4 and the **TIMING limb is refuted
1 of 4** (on its own firing day the 06:00-10:00 window delivered ZERO; onset 11:06, 36 min AFTER the
print). **A right day-net carried a false mechanism into the brain, and the mechanism is what gets
extrapolated.** s103.6 RETRACTS it.

**THE PERSISTENT DOWN LEAN IS GONE** (blind cum -2040 / -1720 / -1220 / -700 -> **+740**), traced to
**THE B_SHARE NORMALIZATION DEFECT**: every `*_b_share` divided by TOTAL volume while the tape carries
a third side value ('N') worth **13.49%** of volume — denominator only. Served mean 0.4078, clearing
0.50 on **5 of 223 sessions**; two-sided mean **0.4999** (dead on the 50/50 physics requires), clearing
on 107. Not a constant shift (corr 0.532; the two disagree about the 0.50 side **45.7%** of the time).
`session_signed_flow` was never affected, which is why nothing looked broken. Fixed ADDITIVELY. **The
first fix was INCOMPLETE** — C found the semantic also lives in PROSE ("under a sub-0.50 sell tape") on
a SIGN play; **a semantic can live in prose as well as in a bar**.

**HOLES #7 AND #8, each a NEW KIND.** S107's six were all EMPTY and `state_health` was built for that.
**#7 the `nws_temp` PARTIAL FETCH TAIL** — the last day of any pull is computed on incomplete hours and
is WRONG while reporting `coverage 1.0` (07-13 read 8.034/mod_cool as a tail, 13.548/hard_cool once a
later day was fetched — a 68% error and a REGIME FLIP inside G23's window). **#8 `tape_conditions`
OFF-INSTRUMENT after a roll** — the source is picked by "whichever store has MORE trades", which after a
roll is the DEFERRED contract: G21 served **18-60%** of the real tape with signed flow **SIGN-FLIPPED**
on the blind's ONLY open-time flow channel, a channel declared `never_masked`. **The doctrine says the
blind's one deliberate mask is the PRICE CURVE — this was an undeclared handicap on 4 of 10 days.** It
is the hardest of the eight because the block is populated, self-consistent, and recomputes coherently
off a different contract: it MANUFACTURED a false mechanism (C's "week-2 thinning", three corroborating
markers, all withdrawn) and **D independently "verified" the artifact by checking internal consistency.
Consistency was never the test** — only RECONCILIATION against the scored leg settles it. Fixed at the
source; `tape_reconcile.py` blocks the rest. G20 clean, G21 4 days, G22 clean, G23 1 day (now fixed).

**ALSO BUILT**: `session_bootstrap.py` (one command from empty to ready); the SessionStart hook restores
automatically and **no-ops LOUDLY** without creds; **stage-time exit states** (a group staged at S108+
runs BOTH rounds with NO data plane); the blind coordinator speaks the engine schema natively (killing a
per-run hand-built alias that died with the scratchpad); `chain_regime_age_sessions`; `phase_volume_lots`
(E, against its OWN play); `squeeze_watch`'s calendar limb derived live (it reported `active: false` at
dte=14 against a live 5 — a confident FALSE NEGATIVE inside its own window); **the MONDAY STUB fix**
(`prior_full_session` — Mondays were served 0.2-3% of a normal tape, the Friday never consulted).

**THE FILENAME COLLISION IS FIXED** (third occurrence): on G21 SIX OF TEN days were one command from
assembling BLIND numbers as the refine — every field check passed, because "present / right day / numeric
/ right owner" are all true of the blind's own file. Two defences: `archive_blind.py` archives by MOVE so
a missing posterior HARD-FAILS instead of reading blind, and `assert_not_the_blind()` hashes each round-1
posterior against the blind archive. Negative-tested. **The transferable lesson, shared with hole #8: a
field-level check cannot catch a wrong-but-well-formed input — only comparison against an independent
source can.** **OPEN, highest value first**: the live orchestrator; the `options_surface` strike ladder;
G21 round 2 (not run). **KEYS DO NOT ROTATE DURING THE WALK.** **NEXT: G22**, staged and reconciling.

## S107 — G19 ROUND 2 (err 34) + G20 BLIND SCORED + **SIX SILENT DATA HOLES** + brain s103.2 (62 plays) (read `SESSION_HANDOFF_2026-08-01_S107.md` + `DROP_IN_S108.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`.** **G19 COMPLETE**: blind 4/10 err 939 ->
refine r1 10/10 err 79 -> **r2 10/10 err 34**, zero direction changes anywhere, every day honestly
under actual. **G20 BLIND SCORED: 6/10, mean abs err 788 — but the FORWARD-CURVE DRIFT is -2560**
(block cum blind -700 vs actual +1860; blind ended 2.964 vs actual 3.220). The hit-rate flatters it;
the curve is the product. Same shape as G19 — a down lean held through a rally. The two EIA
Thursdays are 3,530 of the 7,880 (0528 +2100 actual vs +150; 0604 +1130 vs -450).

**THE REAL STORY OF S107: SIX decision-state blocks were silently EMPTY**, each reading downstream
exactly like a deliberate price mask. `storage`/`stor_surprise` (G18-G21), the signed-flow +
`l1_book` read (G20/G21), `options_surface` (G16/G20/G21), **`vol_regime` — DEAD SINCE G16 on a
hard-coded `SPAN_END`**, `squeeze_watch` frozen on an EXPIRED front (a false positive, not just
stale), and **`weather` — empty on EVERY staged group** from a path mismatch (`data/nws_temp/` vs
where the pull landed it). Three different mechanisms produce the same indistinguishable null:
`_load_json` returns `{}` for a missing file, feeds return `None` for no-coverage, and the one-shot
mask emits `{"value": null}` when it has nothing to freeze. **`vol_regime` is the module built to
condition MAGNITUDE — the brain's own stated dominant residual — and five groups were scaled without
it.** All closed; `vol_regime` fixed at the ROOT (span now derives from the tape, not a constant).

**BUILT: `state_health.py`** — a stage-time completeness assertion wired into `stage_group`. **A block
may be empty only if something DECLARED it may be**; anything else hard-fails BEFORE a specialist
reads it, instead of surfacing in a post-mortem where a data hole gets written into the brain as a
reasoning lesson. **`restore_substrate.py`** — one idempotent command rebuilds the whole data plane
(`data/` is gitignored and does NOT survive a session) and rebuilds `vol_regime`.

**ALSO FIXED**: a **PRICE LEAK** in the handoff chain (`--source blind` would have carried the
REALIZED close/open/day-move/signed-flow into the blind); `big_print_b_share` was the **WRONG SERIES**
(count-based shadowing the size-weighted one — the G19 post-mortem's "the 0.55 gate never fires,
block max 0.537" was an artifact; the size-weighted series reaches 0.550 and FIRES); three render
defects incl. **the blind curve never actually being drawn**; both coordinators had `brain_version`
hard-coded to s102.8 so every artifact since was mislabelled; **A is now a full coordinator owner**
(it owned G20's Memorial Day and both coordinators hard-failed the whole block on it); and a G20 EIA
calendar error caught in pre-flight **by a specialist stopping on its own** (a Monday holiday does
NOT shift the Thursday gas print — `owner_map` derives D's ownership from that list, so D's lens was
aimed at a non-print Friday).

**BRAIN s103.1 -> s103.2 (62 plays)**, 60/61 incumbents byte-identical: struck the false claim that
`flow_conviction` REPLACES the 0.55 arm (it is refine-only — needs realized price — while
`big_print_b_share` is open-time and is the BLIND's instrument in that role; complements, never
substitutes), and added `flow.big_print_bshare_thin_tape_guard` (measured on 204 sessions: the bar
does **NOT** float by season, but the thinnest big-print quartile carries double the dispersion —
below ~20 prints raise to ~0.60). Four specialists independently confirmed it on its first ride.

**FRAMING (Greg):** the walk is a **development loop, not a controlled experiment** — improve group
over group; never hold a group back on a degraded input set to preserve a comparison. Keep
ATTRIBUTION straight in post-mortems so a merge does not bank a data fix as evidence for a play.
**KEYS DO NOT ROTATE DURING THE WALK** (standing decision — see the AWS KEY section).
**NEXT: the G20 refine.** G21/G22 staged and passing `state_health`; **G23 BLOCKED** (weather missing
4 days).

## S106 — THE ONE-AGENT BLIND PROVED OUT ON G19 + brain s103.1 (61 plays) (read `SESSION_HANDOFF_2026-07-31_S106.md` + `DROP_IN_S107.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`**. FIRST group run under the S105
re-architecture: blind and refine ran the IDENTICAL committed files (`mbo_refine_shared.md` +
`mbo_specialist_{A..E}.md`), byte-identical, **NO agent file touched all session** — the ONLY difference
was the DATA (blind = `mask_after` state, price-derived blocks frozen at the anchor vintage;
`tape_conditions` never_masked). **The mask is a BUILT-IN PARAMETER** (`decision_state(days,
mask_after=)`), not something to build. **G19 blind 4/10 mean|err| 939 -> refine r1 10/10 mean|err| 79**
(every day <100, SIX sign-flips all correct, magnitudes derived and held UNDER actual). Greg caught the
**seam-day bug** mid-run (the roll seam is a REAL SCORED day on the post-roll leg; only the overnight GAP
voids — g17 0421 precedent) and round 1 was RE-RUN entirely for fairness. Greg then ordered a
**five-specialist post-mortem** (`forecasts/grp19_postmortem_{A..E}.json`): four root causes —
absorption read as a DAMP not a SIGN-FLIP; the wrong gate (`big_print_b_share>=0.55` NEVER fires in a
covering rally, block max 0.537); crowded-short-as-TAIL not p50 driver; and **EXTENSION-BLINDNESS from
the cum-0 reset** (Greg's own catch, "why wasn't he24 connected hr1") which caused BOTH failure modes —
B: *"starting fresh at cum 0 is exactly what let me invent a down chain against a week of up days."*
A found the doctrinal flaw: covering-self-limiting was **NON-FALSIFIABLE toward DOWN** (unfired->down AND
spent->down). **MERGED s102.9 -> s103.1 (61 plays)**: 18 proposals consolidated to **7 general plays**
(flow_conviction sign gate; absorption_is_reversal; covering_extension_distribution_flip;
covering_self_limiting_cot_wow_gate; seam_gap_up_prior_on_worsening_cot;
chain_label_must_track_realized_cum; friday_exit_close_location_over_flow_shape); **54/54 incumbents
byte-identical**, strictly additive. **THE PRIZE (B, corroborated by all five): NEITHER Monday miss
required the price curve** — both were fixable from the corrected handoff + the worsening COT alone;
price only CONFIRMED. So most of the refine's gain is AVAILABLE TO THE BLIND once the handoff carries
chain state. NEXT: G19 refine ROUND 2 (HE24->HE1, infra staged: databento + all 10 legs), then **G20
blind on s103.1 with the handoff carrying chain state = the real test**. **Scoreboard = forward-curve
error, NOT daily hit-rate.**

## S105 — BLIND RE-ARCHITECTED = REFINE GOLD MINUS ONLY THE PRICE CURVE + THE GOLD VAULT (read `SESSION_HANDOFF_2026-07-22_S105.md` + `DROP_IN_S106.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`**. Brain **s102.9, 54 plays (unchanged — no
merges)**. The walk STOPPED mid-G19 to fix a structural problem Greg spotted in the blind render. **G19
blind** (5-spec sequenced, full firehose) = 6/10 err 751 and a reported "+$2,290 P&L" that HID a ~15c
FORWARD-CURVE under-call (the score was a daily-directional metric; the integrated blind path sat ~15c
BELOW actual through the covering rally). **Two read-only audits**: (1) firehose plumbing = CLEAN to the
state file (G19 proof) but 3 silent-degrade defects, one active — `big_print_b_share` size-weighted is
computed then DROPPED, the old count-based value shadows it under the same name (`forecast_harness.py:630`
omits it); (2) **THE ROOT CAUSE** — the blind's directives CONTRADICT: `blind_shared.md` says "USE the MBO
firehose," all five `blind_class_{A..E}.md` say "NO MBO." Half-finished firehose rollout = the "weird."
**DECISION (Greg, decisive x4): BLIND = the refine GOLD specialist run in BLIND MODE, minus ONLY the
price curve** — no separate blind lens (that duplication caused the drift). BUILT + committed: FROZEN
gold `agents/refine_gold_s105/` (chmod 0444 + sha256 manifest); **`verify_gold.py` = the concrete walls**
(hard-fail any run on a tampered vault; wired into stage_group + both coordinators; tamper-proven);
render `break_gaps()` fix (no weekend straight-line bridge); THIRD off-site copy in the private repo
`DavisAI1974/Agent-Davis`. **RESOLVED (Greg, FINAL): blind and refine read the EXACT SAME committed rule
files (`mbo_refine_shared.md` + `mbo_specialist_{A..E}.md`), byte-identical; the ONLY difference is the
price curve, which lives in the DATA (blind = a price-MASKED state), never in a rule file.** No
blind-specific file exists - the old blind stack AND the `blind_mode.md` wrapper were both DELETED (a
separate file, even a copy, could drift/"sneakily corrupt how he functions"; one shared file cannot). No
A/B question, no validation tests (Greg eliminated them). NEXT: wire the blind spawn (same files +
price-masked state) + unify the coordinator schema (blind emits the refine
`expected_magnitude_usd`/`path_p50_curve`), render-continuity fix (one polyline), fix the 3 plumbing
defects, re-run the SUSPECT G19 blind, resume G20+. **Scoreboard = forward-curve error, NOT daily
direction hit-rate.**

## S104 — THE FRIDAY->MONDAY CASCADE CLEANUP + G15 MBO ROUND 2 (12/12, err 66) + COORDINATOR GUARD + brain s102.5 (read `SESSION_HANDOFF_2026-07-21_S104.md` + `DROP_IN_S105.md`)

**Branch = `claude/kalshi-agents-coordinator-guard-1175nr`** (carries the S103 MBO track + all S104; the
forecaster trunk now). **G15 MBO ROUND 2** (HE24->HE1 handoff injected, 5 Opus specialists, coordinator
--r2): **12/12 dir, mean abs err 66** (r1 72, blind 526); 10/12 days under-100; 0318 held the +1500
confirmed base (reactive tail not claimed). **COORDINATOR GUARD built** (SELECT/ASSEMBLE only - a
missing/non-numeric/wrong-owner posterior is a hard failure, never a silent blind fallback;
negative-tested) + **RENDER RULE** (actual curve + own p50 path ONLY; no re-anchored/scaled lines, no
gap bridges) + **canonical MBO specialist files** `agents/mbo_refine_shared.md` + `mbo_specialist_
{A..E}.md`. **THE CASCADE (Greg: "we missed Monday so bad because we missed Friday so bad")**: three
solo block-spanning cleanups, upstream first - E(Friday): 11/22 Fridays wrong-signed (worst day-class),
10/14 bad Mondays root to a mis-read Friday exit; 9-field weekend handoff_out spec (exit_type +
monday_bias). C(midweek): stretched-extreme-close gives back 6/6 (the midweek->Thu link), prior-exit
last-hour magnitude gate. B(Monday, clean inheritance): 10 of 11 wrong-signed Mondays flip right on
corrected Friday inheritance ALONE; sum |err| 35,030 -> 10,880 -> 8,000 (18 non-irreducible Mondays
mean ~107). **MERGED s102.5 (46 plays, incumbents 36/36 byte-identical)** + doctrine friday_monday_
cascade_s104. **STANDING ORDERS (Greg)**: FOCUS = FRIDAY AND MONDAY; group windows Sunday->2nd Friday
always; FIVE specialists for BOTH blind and refine, coordinator guarded; honest under-100 every day.
**S104.1 (post-close, Greg)**: E's SELF-ANALYSIS DONE (ONE dominant flaw = PRIOR-OVER-STATE on Friday
direction, 13/18 misses; ZERO wrong signs from absent data - the cascade is free to fix; prescription
#1 = a Friday turn/exhaustion GATE, build before G17). **SUNDAY FOLD DECIDED** (the ~2h reopen belongs
to Monday, CME trade-date convention, effective G17; Monday = Fri close -> Mon close). **WEEKEND SEAM
PAIRING**: the week-open chain is E -> A -> B (A = weekend-seam specialist, bridges E's exit to B's
Monday; A informs, B decides, B owns the number). **COORDINATOR FRIDAY SIGN-OFF** (refuses any
weekend-feeding day lacking handoff_out; negative-tested). Brain **s102.5 = 47 plays** (+boundary.
prior_close_flow_direction_disagreement, D's seam tell scoped to every overnight boundary). Agent
handbook agents/README.md rewritten for the 5-specialist era. G17 5-specialist blind = S105's opener.
NG MBO year pull DONE on S3 (312 files; per-contract legs required for roll-straddling groups -
NG.n.0 is the wrong pre-roll leg).

## S103 — G15 REFINED+MERGED + CANONICAL AGENT FILES + G16 BLIND-PANEL walked+refined+merged (brain s102.1 -> s102.3, 36 plays) + THE RECURRING-FLAW MEMO (read `SESSION_HANDOFF_2026-07-21_S103.md` + `KICKOFF_2026-07-22_S104.md` + `research/kalshi/agents/README.md` + `research/kalshi/NG_FORECASTER_PROBLEM_MEMO_S103.md`)

**G15 REFINE** (S103 opener): blind 8/12 -3260 -> refined 10/12, every day <=160; "too deep" REFUTED =
TURN-DETECTION (0318 missed give-back-exhaustion turn UP; 0326 over-sized counter; 0327 expiry-covering
rally). Merged **s102.2** (34 plays: giveback_exhaustion flow-absorption arm, NEW shoulder_counter_print_
damping, weekend_crest_friday expiry split). **CANONICAL DROP-IN AGENT FILES (Greg-ORDERED, the
wasted-cycles fix)**: `research/kalshi/agents/` = blind_shared.md + blind_angle_{storage,positioning,
weather}.md (the 3-agent BLIND PANEL) + refine.md + README.md; RENDERS = continuous_rt.py (change dates).
Spin the SAME files every group; ONLY the brain (via refine) + group data change. **G16 (Mar 29 - Apr 10,
11 sessions, Good Friday dark, clean May/996)** = the FIRST 3-agent blind panel (Greg's weekend idea):
blind **8/11, drift +2365 UNDER-sized** a steady S3 injection-bearish bleed 3.035->2.653; the 3 misses
were EXACTLY the panel's flagged divergence days. Refined **11/11, drift +40, every day <40** ("honest
under 100") -> merged **s102.3 (36 plays)**: NEW `selector.divergence_resolution` (stop AVERAGING bimodal
splits - default to the tape/flow regime; catalyst overrides only above HDD>=16.4 AND b_share>=0.50) +
NEW `magnitude.s1void_injection_chain_bleed` (the G15 "don't over-size shoulder" lesson is scoped to
COUNTER prints ONLY - chain-sided bleed days deliver full band). **THE RECURRING FLAW (Greg -> ChatGPT):
`NG_FORECASTER_PROBLEM_MEMO_S103.md`** - blind 30-70% vs refine 90-100% every block, and the magnitude
error FLIPS SIGN block-to-block (G15 over, G16 under) from mis-scoped lessons; the selector averages
instead of selects; the order-flow direction nowcast (session_b_share <0.50 all 11 G16 sessions = 11/11
if followed) is under-weighted. GROUP_PRECHECK_S103.md: shared substrate ONCE + roll map (May LTD 04-28
-> roll 04-21; June 05-27 -> 05-20); G17 two-leg May->June seam ~0421, G18 clean June. **G17 = S104's
opener, TURNKEY via the canonical loop.**

## S102 — G14 WALKED+MERGED (brain s102.1, 33 plays) + G15 BLIND SCORED (refine = S103's opener) + OPEN-CONDITIONS PROTOCOL (read `SESSION_HANDOFF_2026-07-21_S102.md` + `KICKOFF_2026-07-22_S103.md` + `research/kalshi/S102_MERGE_PROPOSAL.md`)

**G14** (Mar 1-13, FIRST SHOULDER BLOCK, basis = calendar-front 1008/NGJ26 per Greg's "the one that
settles closest to its close" Kalshi rule; 996 CONFIRMED = NGK26/May, resolves the G13 basis_caveat;
NGJ26 expiry 2026-03-27 per definitions): blind **4/12 / -4350** (clean masked holdout; a V read as a
down-give-back - market rallied 2.857->3.407 through ~15gw of warm cuts) -> **5-investigation refine
(A-E) + research sweep + iteration 2 -> refined v2 12/12 / drift +500 = pure band-position noise, ALL
residuals DERIVED** (Greg's "lines darn close to perfect" standard). **Brain s101.6 -> s102.1, 33
plays** (Greg-approved, additive-verified): SIX new plays (positioning_saturation_turn rung,
shoulder_weather_band_void, unpriced_shot_extension, weekend_chain_drift_day_move, weekend_crest_friday,
monday.window_deep_book_shakeout) + the SEASONAL SALIENCE SLIDER operational form S1/S2/S3 (**warm-cut
authority INVERTS in the shoulder** - wk1 cut-mass-vs-move monotone: winter -10.4gw->-10,110 vs
shoulder -16.3gw->+3,250; below ~21gw near-normals base warm cuts lose sign authority) + warm-cut
headroom gate + NEAR-SUM near-window-only + chain-state hardening (C1 6 fires/1 decline/0 false pos)
+ measured class_curve_profiles + fingerprint additions. **OPEN-CONDITIONS PROTOCOL (Greg-ORDERED):
both agents see ALL market data; the BLIND masked ONLY on price-curve content; new `tape_conditions`
decision_state block (prior-session trades/volume/B-share/big-prints/leg-count, never_masked) -
effective G15.** LIVE ARCHITECTURE recorded: live blind builds forecasts AND FORWARD CURVES; refine
becomes the INTRADAY REFINE AGENT reporting to the coach via **VOXA** (pending Greg's pointer); THREE
COACHES (NYMEX daily / Kalshi echo / OPTIONS its own lane). **G15** (Mar 15-27, first open-conditions
walk, basis = Kalshi underlying April/1008->May/996 roll 0320, seam -0.037 marked): blind **8/12 /
-3260** - DIRECTION right (give-back, actual -600) but MAGNITUDE too deep (guessed -3490); **REFINE
DEFERRED TO S103** (token-purchase session boundary) - targets 0318 +1900, 0326 opex/print, 0327
expiry +1160. DATA: MOS family + structure/options stores EXTENDED to end-of-raw (CME instrument-id-
reuse trap fixed); NG L1/mbp-1 YEAR pull running on the box **$0.00 in-sub** (Greg's L-data order);
NGJ26 + CL-year pulls DONE. **G15 REFINE IS GO - from a fresh S103.**

## AWS KEY — READ THIS BEFORE TOUCHING S3 (S100 standing note; cost us an hour on 2026-07-20)

### WHERE THE KEYS LIVE (S114, standing): `~/.config/markets/env`

One file, chmod 600, outside the repo: `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` +
`DATABENTO_API_KEY` + `EIA_API_KEY` as `NAME=VALUE` lines. Greg drops the values per-session
(nothing survives the container); install there plus `~/.aws/credentials` as the boto3 fallback.
`research/kalshi/creds.py` resolves env -> that file -> legacy scratchpad (warns), ignores the
container's `proxy-injected` placeholders, and **`creds.aws_client(service, region)` is the only
way to build a boto3 client**. Full inventory: `KEYS.md`.

### KEY ROTATION IS DEFERRED — DO NOT ROTATE DURING THE WALK (Greg, S107, STANDING)

Greg, verbatim: **"the keys won't rotate while we're running the groups."** Both the AWS pair and the
Databento key have been photographed into chat and both DO need rotating — **after the group walk is
finished, not during it.** Rotating mid-walk breaks S3 and Databento access and stalls every staged
group and every `restore_substrate.py` run. Treat this as a DECISION ALREADY MADE, not an open
to-do: do not rotate opportunistically, and do not re-raise it every session. Until then, handle the
keys correctly — `~/.aws/credentials`, `scratchpad/aws.env`, `scratchpad/bento.env`, all chmod 600,
outside the repo, never echoed into chat, a commit, or a log line.

- THE CURRENT KEY (verified live S100): access key ID `AKIAYI6JDCBVLKYQGLMH`, secret begins
  `txRGHd` (40 chars), account `...4170`, bucket `bento-568968024170-us-east-2-*`. The FULL
  secret is NEVER written in this repo (it is/was PUBLIC; AWS kills keys it finds on public
  GitHub). Full pair lives in: `scratchpad/aws.env` on Greg's box (untracked), and in cloud
  sessions `~/.aws/credentials` + `~/.claude/settings.json` env (both outside the repo).
- THE TRAP THAT BURNED S100's OPENER: Claude Code cloud containers inject PLACEHOLDER env vars
  (`AWS_ACCESS_KEY_ID=proxy-injected...`) which OVERRIDE `~/.aws/credentials` in boto3's
  precedence. Symptom: `InvalidClientTokenId` on a known-good key. Fix: run AWS-touching
  commands via `bash -lc` (login shell sources the profile exports of the real pair), or pass
  credentials explicitly; `~/.claude/settings.json` env carries them for future sessions.
- Session ritual: obtain pair -> `~/.aws/credentials` -> STS get-caller-identity via `bash -lc`
  (print pass/fail + account tail ONLY, never the secret) -> proceed. If STS fails on a
  known-good key, suspect the env-var override FIRST, not the key.

**S101 — TWO GROUPS WALKED + THE DAY-CLASS DOCTRINE + THE REST-OF-YEAR DATA MACHINE (read
`SESSION_HANDOFF_2026-07-21_S101.md` + `KICKOFF_2026-07-21_S102.md` [G14 = S102's opener, FRESH
session]):** **G12** blind 6/12 (+5480; the -7080 0201 dead-sponsor unwind gap = the walk's
largest) -> refine v2 **11/12 / -220** (gap OWNERSHIP anchor_structural>weekend_cycle>chain_drift
+ the DEAD-SPONSOR SIZING RULE, gap=-E of the post-expiry echo run, 13-gap back-check clean);
**G13** (the squeeze test, FIRST MASKED state) blind 4/12 (+2800; NO squeeze fired - thin
bleed-down broke the 3.159 shelf) -> refine **12/12 / -250** + the SQUEEZE-FINGERPRINT
retrospective (F1 failed-counter-flush conjunction n=3, F2 thin-regime ratchet confirm; pre-onset
primary per Greg). Brain **s101.2 -> s101.6, 27 plays**, all merges Greg-approved: DAY-CLASS =
the OVERARCHING descriptor (classify first, score only within class, "no Mondays scoring
Fridays"; Monday 06-10 ET catch-up window; holidays same-holiday-only w/ Sunday-like default;
extended 3-day weekends own sub-class; falsifiable), SEASONAL SALIENCE SLIDER (weather max
winter/summer, shoulders -> flows/maintenance/storage-trajectory; G14 = first shoulder test),
pricing-time rule (MOS appearance caller demoted 0/3), chain-state-is-tape-state, masking fix
(--mask-after, proven G13). DATA: the REST-OF-YEAR MACHINE detached on the box ($1.10 total:
NG+CL n0/n1 trades, all statistics/definitions raw incl. options); CL 51 stub-Mondays FREE
redecode running ($0 verified, window ~Aug 12-14); consensus hole CLOSED 18/18; STEO apr-jul
vintages; calendars -> Dec 31. FLAGS: the March n.0-vs-1008 BASIS DIVERGENCE (G14 setup decides);
MOS extension possibly still in flight (S102 status-check); **pyth sunset Jul 31 = TEN DAYS,
ESCALATE**. Venues: POLYMARKET STRUCK (intl geoblocked; US banned in Ohio); Kalshi-Ohio =
sports-only fight (our commodity leg clear); NEW third-lane candidate = CME NG event contracts
(on Globex, our data venue). **G14 (Mar 1-13) IS GO - from a fresh S102.**

**S100 — THE GATE CLOSED + THE LIVE LOOP'S FIRST BREATH (read
`SESSION_HANDOFF_2026-07-20_S100.md` + `KICKOFF_2026-07-21_S101.md` [G12 = S101's opener, FRESH
session per blind-run hygiene]):** live smoke PASSED (GLBX NG **median 7.7ms** via the box;
container can't reach live gateways); Mondays verified 22/22; July 1-18 pulled ($0, in-sub);
**feeds A-ph1 + E BUILT+WIRED** (cycle-level MOS: the 0118 Jan-24 +8.511 add was PRE-REOPEN
available - the weekend-gap blindness closed; basin freeze-offs: Permian+Haynesville sub-20F
from Jan-24 visible 0122); decision_state 23 blocks / 14 audit classes / 0 violations; ICE HH
positioning wired free (LD1 4.72nd pctile echoes NYMEX 2.83rd); **Tier 3 MERGED -> brain s101.2**
(usage doctrine, flip checklist, evidence registry, day-book PRIMARY scoring split, squeeze
doctrine, Greg's SUPERSESSION single-ownership + blind-run hygiene); **feed M DELIVERED**
(76,594-row lag map: ATM response 42%, delays 110-215s median, spreads 15c->4c - **taker does
NOT clear this regime; MAKER-FIRST**; `TWO_COACH_SPEC_S100.md` printed, approval pending);
determinations: FREE-FIRST standing, CL Mondays = free redecode (~Aug 12-14 window), pyth
sunset by Jul 31 (open). Dashboard session live (`DASHBOARD_HANDOFF_S100.md`). AWS key episode
solved permanently (see AWS KEY section above). **G12 IS GO - from a fresh S101.**
**S100.1 (dashboard session, same day): the READ PLANE is BUILT** - branch
`claude/dashboard-wiring-rgvahe`, `dashboard/` (FastAPI + read-only adapters + the v0.1
prototype wired with REAL/AWAITING/SIMULATED truth badges; 21/22 blocks verified on walk days;
executor lane deliberately last). Cruise-able snapshot artifacts (v0.1.1) + build/refresh notes:
the S100.1 addendum at the top of `DASHBOARD_HANDOFF_S100.md`; generator
`dashboard/make_snapshot.py`. **Same session, Greg green-lit THE OPTIONS LANE (third coach):**
research `OPTIONS_COACH_RESEARCH_S100.1.md`; feed I phase ii BUILT (`options_iv_surface.py`,
294k settle IVs, LNE backbone, LNE strike x10 scale trap measured - phase i's COMBINED pin
view merges mismatched ladders, unfixed, signal core owns it); phase MD measured
(`options_md_measures.py`: Samuelson sized, call skew confirmed per-cell, VRP + fat left tail,
ON-LNE gap inside noise = Black-76 justified); **G7-G11 settle-IV replay RUN**
(`options_replay.py`, blind calls translated to verticals, 51 events, squeeze-short declines
exercised; settle-marked, execution unmeasured). G12/G13 join after S101 walks them; Feb-window
stores (md_measures/replay inputs) must NOT feed the S101 blind agent. **S100.2 close-out: the
live-era bridge LANDED at $0.00 in-sub (surface now 180 sessions Oct 31 - Jul 17, S3
options_iv/ + options_ng_bridge/); build record = the S100.2 block atop
OPTIONS_COACH_RESEARCH_S100.1.md; S101's kickoff carries a .1 revision block (blind hygiene +
the combined-pin-view defect + per-group replay instruction).**

**S99 — FOUR MORE GATE FEEDS IN ONE SESSION + THE MONDAY REPAIR (read
`SESSION_HANDOFF_2026-07-20_S99.md` [SECURITY block FIRST] + `KICKOFF_2026-07-20_S100.md`):**
Item zero HELD (packet presented, recommendation = defer-and-measure + optional quotes; Greg
decides after rest — feed S gated on it). **Feeds T (STEO vintages) / R arm 1 (nuclear outages) /
Q (EIA-930 loads + day-ahead demand forecast + fuel mix) / I phase i (NG options OI pin map —
G13 GATE ITEM CLOSED; ON/LNE roots, "NG.OPT" resolves to nothing) built + WIRED same session:
decision_state 17 -> 21 blocks, audit-joins 12 classes x 101 days, 0 violations throughout.**
Costs measured: gate data ~$5 total (feed I actual $4.67); **Bento LIVE Standard $179/mo
SUBSCRIBED at close (smoke test = S100 opener)**; Pyth Pro declined ($500-10k/mo class).
STRUCTURAL: **the Pyth FREE era ends 2026-07-31** (all API keyed from $500/mo — pyth_collector
WTI/XAU/XAG sunset decision S100; Pyth NGD feeds NEVER published — 3 evidence lines);
**KXNATGASD settlement VERIFIED from spec** (Pyth per-contract NGD 1-min close 17:00 EDT,
underlying rolls forward 5bd before LTD — feed M spec consequence; Kalshi's `expiration_value`
IS the settle print, free); **settle-delta sweep: matched days median 0.1c — exchange-faithful;
all big deltas = roll-window calendar spread**; **THE MONDAY STUB FIND: NG 22 stubs Feb 2-Jun 29
(ALL G12/G13 Mondays — a silent walk blocker) REPAIRED (~$14, S92 script); CL 51 stubs (whole
year) HELD for Greg — free-redecode window closes ~Aug 12-14; July 1-18 NG never pulled.**
ICE HH positioning codes measured in our own CFTC files (023391/023392/0233AG/0233AH — cot
extension queued). SECURITY: the AWS key was photographed into chat — ROTATION = S100 item zero.
G12 still needs feeds A ph1 + E + Tier 3 merges; G13 additionally feed M. START S100 with the
drop-in box.

**S98 — THE DATA GATE LARGELY CLOSED IN ONE SESSION (read `SESSION_HANDOFF_2026-07-20_S98.md` +
`KICKOFF_2026-07-20_S99.md` + `research/kalshi/DATA_GATE_S98.md` [THE build list, feeds A-T]):**
Desk review (20-yr NYMEX/ICE lens) -> Greg: "rewrite our data plan to your specs" -> the gate
reorganized by regime family (DEMAND/POSITIONING/DELIVERY). **TWELVE feeds built/wired;
decision_state 8 -> 17 blocks; audit-joins 0 violations x 8 classes x 101 days all session.**
DECISIONS: **TWO-COACH architecture** (Kalshi initial primary, NYMEX dailies next; one signal core,
ledgers never pooled; build deep, subset down); **the futures->Kalshi LAG = THE STANDING LOOK-AHEAD,
established (S80 15-sig, S81 7-20s, S91 gold/silver), NEVER retest, live telemetry only**;
procurement policy = free-first, verify coverage, pay only MEASURED gaps. **Brain s100.3 MERGED**
(Greg approved): the C2 ratio reformulation REFUTED on comparable data (0120 true 0.714 vs 0107
false 0.718 - identical on every arm); C2 kept + scoped; **the flip confirm completes as C1+C3+C4
on the modern tape class** - forward test rides G12. Tier 1 done (G11 fingerprints on .n.0,
pre-G11 counts reproduced exactly). THREE S97 CONCERNS CLOSED AS MEASURED: vintage look-ahead =
ONE EIA revision event dated AFTER the winter (Mountain reclass ~10 Bcf/wk levels; one mislabeled
print Sep 4); regional store xls-vs-api diff 0/863; C2 resolved. STRUCTURAL DISCOVERIES:
**Kalshi had NO NG daily market in the walked winter** (KXNATGASD born 2026-03-27; Jan-Feb 2026
zero NG markets - the G7-G11 echo replay is impossible, feed M runs on the Mar 30+ life; dailies
skip Fridays; no historical book endpoint exists); the free weekly balance DIED 2025-10-02 (S&P
section removed; vessel line survives); **THE EIA SWEEP FIND: STEO monthly VINTAGES** = the
complete NG balance as-of each release, free, 1-34d stale (the API is current-vintage-only, the
archived workbooks are the source; join on RELEASE dates); the cash HH spot publishes in WEEKLY
BATCHES (naive T+1 would have leaked the Jan blowout a week early; decision-time-legit the +10.77
basis lands ON the 0130 17x day); the two positioning books sat at OPPOSITE extremes entering G11
(futures MM 2.83rd pctile vs options-implied 97.17th - now a wired variable). AWS: all three keys
ROTATED; `platform_sync.py` = the one door; ~15 S3 prefixes manifested; live-loop design =
us-east-1, sub-second suffices, LLM never in the hot path. MOS extended through Feb 27 (the
G12/G13 weather blindness closed; two builder traps documented). **S99 = ITEM ZERO the PAID-DATA
DISCUSSION (packet delivered), then feeds T/A/I/M/Q/R, Tier 3 doctrine proposals, THEN G12
(Feb 1-13) and G13 (Feb 15-27, the SQUEEZE TEST - opex 0224/expiry 0225 inside; requires feed I).**
START A FRESH SESSION with the S99 drop-in box.

**S97 — the walk paused at the hard data gate (read `SESSION_HANDOFF_2026-07-19_S97.md` [GATE section
FIRST] + `KICKOFF_2026-07-19_S98.md`):** G11 (Sun Jan 18 - Fri Jan 30) ran blind on s99.2 -> **6/12, drift
-13,190, the THIRD consecutive block-lean miss** (anchor 2.702 -> 4.416; the bleed reversed into a 63%
rally and the blind held the down-chain). Refine -> **s100.2, 23 plays: 10/12, drift -3,890.** **THE FLIP
RULE IS KEPT** — per-instance: **C1 (band-break) fires 1008/1020/1208/1223/0120 and correctly declines
0107 — five fires, one correct decline, ZERO false positives**; the blind missed because **it never
evaluated 0120, the actual flip day**. **C2 fails on HIGH-ACTIVITY tapes for a SCALE reason** (calibration
15-98 legs on 15-25k trades vs G11's 160-550 on 75-125k, so an absolute <=15%-of-legs bar is mechanically
unreachable) — the ratio reformulation is a FLAGGED BUILD GAP and **blocks G12** (needs G11 fingerprints
on .n.0 first). NEW plays `weekend_gap_delivery` + `mos_first_appearance_vs_revision`. **Brain
architecture (Greg): every play carries `requires`/`scope`/`forward_evidence`; refined rules NEVER
override blind-applicable ones (hindsight-fitted, zero forward evidence — and the blind-vs-refined GAP is
itself the measurement); promotion gated on forward evidence.** MOS forecast temps BUILT + in first use
(91/91 days, blind wall 0/11,648 violations). Net-of-fee replay: **fees are NOT the constraint, DIRECTION
is** (0/51 events had the taker fee flip a sign); G9's +14.4k is SIX named events, the other fourteen sum
-3,220; the block lean and the day-book are TWO DIFFERENT EDGES. Series-construction finding: NG.v.0
whipsawed 1000<->1021 through the G11 expiry week (Feb squeezed 3.0->5.4); G3-G10 are clean; G11 re-pulled
on **NG.n.0**; pass-2 deferred by Greg. **GREG STOPPED THE WALK: no new group runs until EVERY data input
in the handoff's GATE is built and wired.** THREE LANDED in S97 (committed + pushed, none wired yet):
**COT positioning** (`cot_feed.py`; caught a 47-day blind-wall leak — the 2025 shutdown suspended COT
publication Oct 1-Nov 12, so the naive Friday rule would have leaked across G6/G7; 0 violations after
overrides), **EIA regional + SALT/NON-SALT storage** (`storage_regional.py`; salt+nonsalt reconciles on
all 863 records; 0 violations over 6034 days), **contract structure + forward curve**
(`contract_structure.py`, 49 fields, expiries authoritative from definitions). **The last one caught a
flaw in its own spec: the OI-continuous front HIDES the squeeze** (0122 `front_next_spread` 0.093 because
n0 had already rolled) — a CALENDAR-FRONT block keeps the nearest-expiry pair visible, where the real
1.539 sits. **When wiring, expose the calendar-front fields or the feed cannot see what it exists for.**
STILL TO BUILD: MOS cycle timing (Sunday reopen priced by a later cycle than our D-1 feed), vol regime,
G11 fingerprints, C2 ratio reformulation, model disagreement, LNG feedgas, options, cross-market. **How
to build them (Greg): we are NOT testing theses — we put relevant info in front of the agent and IT
decides how to use it. Never gate an input on whether it "worked".** ALL SESSION DATA ON S3 (272 objects
/148MB verified; restore, do not re-pull). NEXT = wire decision_state SERIALLY, finish the gate, then G12
(Feb 1-13), then **G13 (Feb 15-27) = the SQUEEZE TEST** (carries the Feb 25 expiry).

**S96 (read `SESSION_HANDOFF_2026-07-17_S96.md` [session-total block at top] + `KICKOFF_2026-07-17_S97.md`):**
FOUR winter blocks walked, brain s95.2 -> **s99.2 (21 plays)**. PROTOCOL SETTLED (Greg): one-shot block-blind
= the canonical skill test; refine after EVERY group to the ITERATE-TO-TRACKING bar (general rules only, n>=2
spanning groups, never day-tuning); renders PRINTED to Greg before each refine merge; lessons merged BEFORE
the next group; blocks now START SUNDAY (reopen) / END FRIDAY (close). The arc: **G7** (Nov 5-18) blind 3/10
-> refine 9/10 -> s96.2 (giveback_exhaustion_boundary; Thursday side = running swing never print sign).
**G8** (Nov 19 - Dec 2) blind 7/10, lean right -> refine 10/10 -> s97.2 (catalyst_continuity_frontrun; R2
leg-vs-net; winter bands; thin AMPLIFIES delivery). **G9** (Dec 3-31, surplus-collapse December) = block-lean
MISS 1: 13/20 days but the market crested Dec 5 + SOLD THE COLD to -6150 (backwardation; first NEGATIVE roll
-0.504) -> refine 18/20 -> s98.2 (chain_polarity_flip; prints chain-sided at POLARITY 7/7; failed_rally_tell;
crash bands). **G10** (Jan 2-16) = block-lean MISS 2, a FALSE FLIP: 6/11, called a chain-birth off basing but
the down-chain never ended (0109 bullish draw SOLD -2760) -> refine **11/11 / drift +320** -> **s99.2**: the
flip CONFIRM hardened to FOUR mandatory conditions (band-break >=1.5x; old-side continuation-collapse <=15%;
printed-never-front-run; first-print arbiter), TERMINATION != BIRTH (chain birth needs a forward driver), NEW
third chain class **post_parabolic_bleed** (crashes single except into prints, bounces 1-2 days never 3).
Both lean-misses were POLARITY calls — the flip is now the hardest-guarded rule. LIVE-coach cadence (Greg):
rolling week-ahead arc + DAILY re-anchor pass that may OVERRIDE it (every strong rule consumes day-N-1 tape).
DATA next (Greg): forward-curve cache back ($0.07; curve_regime was 'unknown' all S96) + **historical
FORECAST temps via the IEM MOS archive** (forecast-vs-realized DELTA = the driver; back-fill the walked
winter). NEXT = G11 (Sun Jan 18 reopen -> Fri Jan 30; MLK thin; Feb->Mar roll ~Jan 26-27 INSIDE — check
first) blind on s99.2; then the net-of-fee coach replay (the money question). START A FRESH SESSION.

**One-line state (S116):** branch `chatgpt/frankie-raw-mbo-benchmark-20260828`, **613 tests
green, NOTHING LAUNCHED**, decisions 57 -> 61. **The four estimand proposals are WITHDRAWN — the
prior exhaustion program already built and froze that vocabulary**, and the build plan changed
with it: the missing layer is the **per-second roll20/dipole substrate**, not six F_LAST-group
adapters. **D60 restored 55 confirmed data drops**; **D61** says restore by wrapping the
hash-locked MBO adapter, never editing it. **The open question for Greg is a UNIT question.**
Ten of thirteen sections still receive zero data; nothing dispatches the driver.

**One-line state (S115 A-ARM):** branch `chatgpt/frankie-raw-mbo-benchmark-20260828`, **552
tests green, NOTHING LAUNCHED**, decisions 51 -> 57. **The execution gate was enforcing the API
architecture and would have rejected a correct Sol run — now file-based.** The CME trading-day
calendar is wired and REFUSES on a shortened session rather than guessing. The A-arm input unit is
the **F_LAST group** and the adapter layer exists for 4.8/4.9/4.13/4.14. **All sixteen sections are
BUILT — say "unfed", not "remaining".** The box was live-probed (**r6i.2xlarge, 8 cores, 61.8 GiB,
32 GiB swap**; the recorded t3.xlarge was wrong) and **AWS creds are workflow-scoped, so no session
can probe from a desk**. Monitor LIVE, **resize ARMED but NOT FIRED**. Waiting on Greg: the resize
size, the `corrected_information` shadow ruling, the `output_provider_invocation_response_receipts`
rename.

**One-line state (S114):** brain **s105.9, 90 plays — CALLS unchanged**. **G24 blind RUN AND
SCORED: 6/10, sum|err| 4,890 — 0.98x zero_change and 1.20x seasonal_naive, i.e. we tied doing
nothing and lost to naive.** **THE REFINE HAS NOT RUN — it is S115's opener.** The dominant problem
is **under-emission at 0.29x of realized magnitude, 8 of 10 days, worsening from 0.55x/0.68x**.
**The renewables forcing is WIRED** (31-member GEFS density, blind-wall audited 10/10, wind and
solar never summed). Every specialist-reported data defect closed WITH ITS CAUSE, and two
regressions of my own caught and fixed. **A-46 play evaluability is live** and found the
centrepiece play was standing down because its `state_path` was prose. **The data plane is SYNCED
to S3 and verified by reading back** — it was NOT, mid-session, and a fresh session would have
undone everything. Decisions 48. **Keys do NOT rotate during the walk.**

**One-line state (S113):** brain **s105.0, 82 plays — UNCHANGED. No group run, no merge**, and
**nothing from S113 is in the brain**, which is the largest gap at close (specialists read the
brain, not the registry). **D37 made the no-average rule a FUNCTION** (`per_event.py`) — an R2, a
correlation and a fitted slope are all averages — and separated an OBSERVATION from the STORY
explaining it. **Greg taught utility operations and it killed five of my mechanisms**: wind and
solar are seasonally ANTI-correlated, gas plays both peaker and baseload roles, coal is a
startup-constrained ramp on a 1-2 week commitment, reliability is the rarely-played trump card, and
the response can be MEDIATED (a cold snap with no gas bump for a week). **D38: burn follows
GENERATION, not load** — CISO net-imports p50 20.6% / MAX 41.7% of its load, US48 is the only level
where interchange collapses, and the term is a BOUNDARY term the storage roll-up does not need.
**A-38: for the WINTER storage lane, res/comm heating outmoves power burn on 33 of 52 actual months
and on 10 of the 10 largest, and on 12 of 52 power burn moved OPPOSITE to total demand** — scoped
per D31, it does not refute the burn stack, and its weekly re-check comes first. **Registry 87 items
(75 live: 5 ESSENTIAL, 20 BIGGEST_WIN).** **A-1 and A-13 closed** (SOP v1.9). **G23 was the last
staged block — G24 needs a DATA PULL.** **Keys do NOT rotate during the walk.**

**One-line state (S112):** brain **s105.0, 82 plays**, **624 instances (306 do / 318 dont)**. **No
group run, no merge.** The D29 work list is CLOSED. **Greg rebuilt the burn stack** — nukes, coal,
gas, with wind/solar/hydro as non-regulating forcings and **hydro an INVERTED U whose both tails are
bullish**. **D35: the target is total demand HENRY HUB CAN SEE** — HH is one point near Erath,
Louisiana, not a national index. **D36 + SOP Station 0**: 12 of the 13 S111 build suggestions had no
registry item, so a briefing's recommendations now become registry lines in the session they land,
**enforced by the andon**. **Two registries born**: documents (55 of 151 `.py` unindexed; mtime is
not staleness) and data (**1,717 served points, 1,129 read by NOTHING**). **61 open items tiered 8 /
11 / 42**; the essential eight are the gate on the next group, and **G-28's leak check comes first**.
**G23 was the last staged block — G24 needs a DATA PULL.** **Keys do NOT rotate during the walk.**
LEGACY line below (pre-S106):

**READ THIS FIRST, in order — do NOT read this whole file for detail, it points you at the detail:**
1. The latest `SESSION_HANDOFF_*.md` (highest S-number) — the actual current state.
2. The latest `KICKOFF_*.md` — the priorities for this session.
3. `KALSHI_TRADING.md` — the file index: every Kalshi file, what it does, current vs old.
4. Then `git log --oneline -1` — confirm you are NOT on the stale tip (see Branch discipline).

---

## What this project is

DavisAI Markets. The live product is **Kalshi prediction-market trading** (weather / macro / energy /
electricity event contracts). Crypto (the OD "info-dipole" / order-flow toolkit) was the proving ground
and is now history — the session-by-session record + the earlier OD/physics research lives in
`CLAUDE_ARCHIVE_OD.md` (nothing deleted; see Archive pointer). The operator toolkit that came out of it
is LIVE and documented below (see "OD toolkit") — it is the engine the Kalshi lag / signal work runs on,
and we regularly reach back into it for pieces.

Team: **Greg Davis** (founder, sets direction, owns the weather forecaster spec) + Claude (engineer).

---

## The trading rules (load-bearing — Greg, S80-S82)

- **EACH TRADE INDIVIDUALLY, never average.** No pooled hit-rate, no mean signed-bps, no averaged
  coefficient — every aggregate blurs away the per-trade fingerprint that IS the predictive content.
  Characterize the DISTRIBUTION + the per-trade fingerprint; never lead with the mean.
  **ENFORCED, NOT ASSERTED (D37, S113 — Greg had to say this for the tenth time): use
  `research/kalshi/per_event.py report(...)`.** It prints the D4 set (sum|err|, drift, survival,
  p50/p90 AND MAX), an improved/worsened COUNT, and **the largest ACTUAL moves named one by one** —
  and it returns NO scalar, so there is nothing to quote out of context. **AN R2, A CORRELATION AND A
  FITTED SLOPE ARE ALL AVERAGES** — that is the form the rule keeps being broken in, not the word
  "mean". Measured in ONE S113 analysis: a pooled correlation whose sign was opposite to every
  constituent cell (+0.178 vs −0.685 summer / −0.256 winter, i.e. pooled it said burning gas FILLS
  storage); an R2 of 0.554 hiding a 56%-of-weeks record whose worst week got WORSE; and an OLS slope
  quoted as evidence. Pairs with A-1: `blind_score_nonpooled.py` never reports an error number without
  a named benchmark.
- **YOUR STORY IS A GUESS; THE DATA IS THE FINDING (D37).** An OBSERVATION and the STORY explaining it
  are independent — a refuted mechanism never demotes the measurement it failed to explain, and a
  measurement is dropped only when ITS OWN evidence fails. S113 ran the full cycle: a regularity held
  9 monthly cells out of 9, three mechanisms were proposed and refuted (gas-backfill,
  weather-extremity, calendar), and it was finally dropped for the right reason — holding burn constant
  INSIDE month, non-parametrically, the effect vanished. Wrong reason to drop: my story died. Right
  reason: the evidence died. **And know the domain before theorising** — wind peaks in spring/autumn
  and troughs in summer while solar peaks at the solstice (measured on our own EIA-930: wind 9.9 TWh/wk
  in April vs 5.9 in August; solar 3.5 in June vs 1.4 in December), so `wind+solar` is a composite of
  two OPPOSITE annual cycles and must never be summed into one 'renewables' term.
- **Per-cell always, never pool.** Cells = moneyness × side × velocity/lag-class × release (for
  level-hits); regime × city × season × bucket × swing-dir (for weather). A signal that survives on a
  SUBSET of cells is KEPT and used on those cells — partial coverage is not failure. Report "works on
  {X}, not {Y}", never "X failed."
- **The merged signal architecture:** catalyst (release/news) = trigger + coarse size; book imbalance +
  flow + exhaustion = direction + magnitude; herd breadth = continuation, whale = scalp-only.
- **NYMEX is the CANARY; Kalshi is the delayed follower (Greg, S84).** The move happens on NYMEX/ICE
  first and reprices onto Kalshi seconds-to-a-minute later (futures lead, Kalshi never leads). Gather
  NYMEX as the leading signal, measure the lag, fire on Kalshi. Resolution: 1-min is USELESS (NYMEX
  moves fast); 1-sec is the historical floor and STILL undersamples — every 1-sec NYMEX readout is a
  LOWER BOUND, never the full tape. Data reality: Pyth has WTI (historical works) but NO natural gas
  and Brent-historical 404s; NG/Brent need Yahoo/other. See `research/kalshi/NYMEX_CANARY_NOTES_S84.md`.
- **Exclude the settle window** (the daily-settle exclusion / `SETTLE_UTC` guard) from every backtest.
- **Leakage gate before ANY backtest** (`odcore/leakage.py`) — pre-entry context must be invariant to
  future trades. This is mandatory and non-negotiable.
- **Zero synthetic trading data.** Ever.
- **Provisional until live.** A backtest edge is a hypothesis; nothing is "real" until it clears live.
- **Weather = Greg's spec, HANDS OFF.** The forecaster itself is Greg's own work; we only build the
  scoreboard/bridge (`kalshi_score.py`, the `(value,sigma)` bridge) and score PER REGIME vs the baseline.
- **`--events` on `news_coupling_research.py` is a BASENAME** joined onto `--data-dir`, not a path.
- **Keep `KALSHI_TRADING.md` current** — add new files to the top section, move superseded ones down.

---

## Operating discipline (cross-cutting)

- **NOTHING IS DROPPED WITHOUT DISCUSSING IT FIRST (Greg, S115, STANDING - D60).** Verbatim:
  *"we have all this data for a reason. do not drop any of it without discussing with me
  first. make that a rule"*, and *"do not leave any of the book data out. it may not seem
  relevant to you but it may to frankie."* A row, field, message or observable that reaches
  our code is either **USED**, or **RETAINED and counted**, or **REFUSED loudly**. Never
  silently ignored. "This looks like nonsense" is not a licence to discard - **relevance is
  the consumer's to decide, not the ingest layer's.** **The cost is why it is a rule:** *"this
  is the problem that i have been fighting the whole time that things are dropped for whatever
  reason and not discussed and then we find out we have to rerun because it was important."* A
  dropped input does not fail - it produces a number that is present, typed, in range and
  wrong - so it surfaces only after a full run, and the rerun is the expensive part. Two
  instances were found the day it was written: a replay book that ignored four row classes the
  authoritative book acts on, and `native_replay_driver` discarding the adapter's legacy rows,
  which carry the 10-level depth a REQUIRED registry group is built on.
  **THE ONE EXCEPTION, and it is narrow (Greg, same session):** *"if a row is truly blank and
  is measuring nothing then you can leave it off."* TRULY BLANK - carrying no measurement at
  all - not "looks irrelevant", not "we do not use it", not "it would cost memory". The burden
  is to SHOW it measures nothing, and if that cannot be shown from the row itself, it stays.

- **Falsification-first / Result Discipline.** Every claim needs a falsifiable test. Every result is ONE
  data point — map alternatives (incl. the deflationary reading) before promoting to a claim. Catalog
  MISSES with the same care as hits; a negative that sharpens the program (like the S82 level-hit result)
  is a real deliverable.
- **No tent-widening on outliers.** When something lands outside the pattern, find the specific reason —
  don't loosen the test or wave it off as transient.
- **Incremental validation.** Canary run (short) before any long/compute-heavy run; break long runs into
  chunks with stop gates.
- **git is the source of truth.** Commit + push working code/docs regularly. Large data stays LOCAL /
  gitignored (see Branch & data). Better, stronger, faster, cheaper.
- **No emojis / special symbols** in docs, commits, or anything pushed.

---

## Branch & data discipline (READ — recurring trap)

- **THERE IS NOTHING LOCAL — GIT OR S3, NOTHING ON THE E DRIVE (Greg, S112, STANDING; D34).**
  Verbatim: *"all of this stuff is going to live in aws or git so there should be no paths from my
  desktop"*, *"there should be nothing local"*, *"right now everything gets pushed to git. zero to
  e drive."* The split is the whole rule: **git = code and records, S3 = data, `data/` is
  DISPOSABLE** and rebuilt by `restore_substrate.py`. It binds two ways. (1) Nothing the next
  session must RUN may live outside git — no `~/.claude/projects/`, `workflows/scripts/`, `/tmp`
  or scratchpad path (D33, gated by `plant_status.py`). (2) **No artifact may NAME a desktop
  path** — not a citation, evidence list, ledger, handoff or decision line. INSTANCE: the S111
  audit partial carried 140 instances and **51 of them, across 11 plays, cited
  `E:/Markets/research/kalshi/...`**; the files were real and committed but the citations opened
  on exactly one machine, and that file is the input to the S111-3 backfill, which writes
  instances **into the brain**. Fixed S112 by `brain_audit.py fixpaths` (re-runnable, backed up)
  → 140/140 clean. **Do not repair such a path by silently re-rooting it** — the first version of
  that guard did, which hides the defect instead of reporting it. Rewrite it repo-relative.
  Still carrying hardcoded `E:\Markets\...`: the root-level OD/crypto-era scripts
  (`_balanced_rerun.py`, `_canary_fingerprint*.py`, `_build_*.py`) — archive, not the live
  forecaster, and named here so the gap is declared rather than discovered.
- **THE DROP-IN BOX'S BRANCH IS ALWAYS THE STARTING POINT (Greg, standing, 2026-07-20 S100).** The
  harness assigns each session its own auto-named branch — that branch is NEVER the work. First
  commands of every session: `git fetch origin <drop-in branch> && git checkout -B <drop-in branch>
  origin/<drop-in branch>`, then confirm the tip message matches the drop-in's stated tip. All
  development and pushes go to the drop-in branch.
- **The empty-checkout trap (observed S100):** when the harness-assigned branch does not exist on the
  remote, the container comes up on an orphan `master` with ZERO commits and an empty tree — every
  file read fails and the session looks broken. The fix is the same fetch + checkout above; nothing
  is lost.
- **The stale-tip trap:** the harness often cuts a fresh session branch from a stale old tip (the known
  bad one is **S70 `3c70ff5`**). ALWAYS run `git log --oneline -1` first. If the tip is old, you are NOT
  on the real work.
- **Canonical trunk = `claude/kalshi-s79-kickoff-ij8t9o`.** The GitHub Actions collectors auto-push data
  commits here, so it is the live rolling branch — develop and push here (pull/rebase first, the
  collectors commit too). Do not strand work on a fresh harness-assigned branch.
- **Durable data accrues on branches, code does not:** `data/kalshi-bins` (live bins + consensus),
  `data/pyth-ticks` (Pyth futures ticks), `data/*-book` / `data/*-bins` (crypto history). Fetch + gunzip
  the relevant branch at session start; VERIFY it actually accrued before trusting it.
- **Local/gitignored data stores:** `data/kalshi_hist_trades/`, `data/pyth_ticks/`, `data/kalshi/`,
  `data/level_hits_*.json`. Too big for git; re-pullable.
- **Workflows (kept, on the trunk):** `.github/workflows/kalshi_collectors_durable.yml` (6h),
  `pyth_collector_durable.yml` (6h). If a run sits `queued` and never executes, it is an account-level
  Actions issue (billing/minutes/runner cap), not the workflow. My token cannot click "Run workflow" —
  Greg dispatches manually.

---

## Where things live (see `KALSHI_TRADING.md` for the full index)

- **`research/kalshi/`** — all Kalshi code: collectors (`kalshi_collector.py`, `kalshi_history.py`,
  `pyth_collector.py`, `consensus_poll.py`), the lag thread (`futures_kalshi_lag.py`,
  `lag_exploit_backtest.py`), the level-hit thread (`level_hit_dataset.py`), release/scoring/weather
  (`release_book_signal.py`, `kalshi_score.py`, `kalshi_weather_forecast.py`), findings `*.md`.
- **`KALSHI_BUILD_SCOPE.md`** — the build scope / thesis.
- **`odcore/`** — the OD toolkit (below).
- **`.claude/skills/`** — session rituals: `kalshi-session-start` (branch/data/accrual checks),
  `kalshi-backtest` (the mandatory evaluation discipline), `kalshi-roll` (Pyth front-month roll).
- Shared: `news_ingest_rss.py`, `news_coupling_research.py`, `regime_classifier.py`.

---

## OD toolkit (live — we reach back into this; provenance in `CLAUDE_ARCHIVE_OD.md`)

The operator tools built in the crypto era (S20–S37) that the Kalshi pipeline runs on, plus the pieces
we periodically pull back out. All portable numpy; validated per-cell.

- **`odcore/leakage.py`** — the MANDATORY pre-backtest leakage gate (catches look-ahead 40/40). Nothing
  gets backtested without passing it.
- **`odcore/leadlag.py`** — raw cross-covariance-over-lag lead-lag + time-slide null (the S19 "right
  tool"; what `futures_kalshi_lag.py` is built on).
- **`odcore/info_dipole.py`** — signed order-flow features + `divergence()`: the 2-factor
  DIVERGENCE (flow opposes price → ~65% reversal) + EXHAUSTION (imbalance collapsing toward 0.5 =
  leader weakening) read. The FILTER in the filter/timing split. Also provisional `cell_signal`/`DEPLOY`
  — **`DEPLOY_VALIDATED=False`, never trade the directional map** (S36 robustness: trend artifacts).
- **`odcore/incremental.py`** — `RollingFlow`, O(1)/tick bit-faithful incremental operator (1.7µs/tick)
  for hot-path use.
- **`odcore/fingerprint.py`** — per-cell fingerprint encoder (verbatim ports of the live micro-feature
  math + chunker recipe; flow features stacked per cell).
- **`odcore/dipole_predictor.py`** — the 128-dim centroid-projection algebraic dipole
  (`build_centroids`/`project`; H_a/H_b = projections on win/lose centroids — centroid-based, NOT bins).
- **`odcore/null_extract.py` / `coupling_scanner.py` / `symbolic.py` (PySR) / `validation.py` /
  `sizing.py` / `stacking.py` / `generators.py`** — coupling discriminator, tautology-killing
  circular-shift null, symbolic regression, the walk-forward net-of-cost promotion gate, OD-native
  sizing, stacking.
- **Crypto data history** (for reaching back): `data/*-bins`, `data/*-book`, `data/*-kraken-book`,
  `data/perp-history` branches — 5 coins × 3 venues 1s bins + L2 books. Collector workflows were
  deleted from the trunk end-S82 (runner hog); the code is recoverable via git history if collection
  ever needs to restart.

The research findings behind these tools are the next section — the dipole research stays LIVE here,
not just in the archive.

---

## Dipole research (standing — the findings, kept live)

The information dipole (davisai.ai/dipole) is our directional/flow tool; Greg: the trend-following /
flow read may be one of our biggest edges, usable across the WHOLE platform — which is why this stays
in the live doc. Full detail: `S36_NETCOST_BACKTEST_FINDINGS.md`, `SESSION_HANDOFF_2026-06-22_S36.md` /
`_S36b` / `_S37`, and `CLAUDE_ARCHIVE_OD.md`.

- **The core read (S36, 2 factors, stack monotonically):** markets are follow-the-leader (a trend = a
  flow) until the leader exhausts → new leader, usually opposite; the edge is detecting the changeover.
  (1) **DIVERGENCE** — `aligned_flow = imb_level × sign(price_drift)`; strong divergence (≤ −0.20) →
  ~65% reversal, temporally stable, consistent 6/7 cells. (2) **EXHAUSTION** — the dipole COLLAPSING
  toward 0.5 (leader weakening; the MOVE toward balance, NOT the discrete crossing, which is a coin
  flip). Combined: oppose+exhaust 64% reversal > oppose+strengthen 58% > with-trend+exhaust 52% >
  with-trend+strengthen 49% (healthiest trend).
- **Discipline (load-bearing):** the signed flow is NOT a direct direction predictor — apparent
  directional lifts were trend/base-rate artifacts (Simpson's on a trending window) and died under
  window/forward sweep + temporal OOS + detrended targets. `DEPLOY_VALIDATED=False`; never trade the
  directional `cell_signal` map. The DIVERGENCE/FLIP read is the robust edge; static `imb_level` is
  the detector (differential flows are not).
- **Net-of-cost (S36b, per cell):** the 64% does NOT clear a 10bps round-trip pooled; the flow gate
  adds ~+3bps/trade over blind trend-following and clears walk-forward-robustly only on specific cells
  (btc_bybit sell/buy). Direction is the easy part — the edge is SIZE-vs-FEE (the same finding Kalshi
  S81/S82 reproduced on a different market).
- **The architecture split:** DIPOLE = the FILTER (which turns are real) + fine-resolution
  PRICE-REVERSAL = the TIMING (1-sec enters ~5–6bps off the true turn vs ~9–11 at 1-min). Fee-floor
  rule: never trade a swing smaller than round-trip fee + 2× entry slippage (taker floor ~22bps;
  resting a maker limit at the predicted turn drops it to ~4bps, with fill-risk). Per-cell regime
  master-gate rescues bleeder cells; leave winning cells un-gated.
- **The gated-swing stack (S37, `_info_dipole_gated_swing.py`):** timing (1-sec price-reversal) +
  filter (dipole divergence) + regime gate + maker floor, leakage-gated (PASS 6/6); PROVISIONAL 4/6
  cells clear on the single window — never size off one window.
- **The centroid-dipole lineage (S33–S35):** the real markets dipole is CENTROID-based, not bins —
  H_a/H_b = projections of a trade's 128-dim OD `operator_coefficients` on win/lose centroids; per-cell
  exact coeffs + the distinctive-fingerprint program (`bucket-distinctiveness-is-the-goal`: predict
  winners by their per-cell fingerprint, never by class-separation statistics).
- **Standing meta-rules:** tools are COMPLEMENTARY, not competing — evaluate by STACKING, never
  head-to-head ("even a 5% net edge is huge"). Per-cell always. On Kalshi today the dipole exhaustion
  read is live inside `release_book_signal.py` (direction = book-imbalance sign, magnitude/fade =
  imbalance + dipole exhaustion) and the level-hit context features.

---

## Current state & priorities

Detail is in the latest handoff + kickoff — this is the pointer, not the record.

Recent arc (compressed; full detail in each `SESSION_HANDOFF_*.md`):
- **S99** — item zero held (determination after rest); feeds T/R/Q/I built+wired (21 blocks, 12
  audit classes, 0 violations); Bento live subscribed; Pyth free era ends Jul 31 (NGD feeds never
  published; NATGAS 24/7 = Pro, declined); KXNATGASD settlement verified from spec (per-contract
  NGD 17:00 close, 5bd-forward roll, expiration_value = the settle print); settle-delta sweep
  exchange-faithful (median 0.1c matched; big deltas = roll-window spread); the Monday stub find
  (NG 22 repaired ~$14; CL 51 held, free-redecode window closes ~Aug 12; Jul 1-18 never pulled);
  ICE HH codes measured; AWS key photographed in chat -> rotation = S100 item zero.
  Detail: `SESSION_HANDOFF_2026-07-20_S99.md`, `KICKOFF_2026-07-20_S100.md`.
- **S98** — the gate largely CLOSED in one session: desk review -> DATA_GATE_S98 (feeds A-T by regime
  family); 12 feeds built/wired, decision_state 17 blocks, audit 0 violations throughout; brain
  s100.3 (C2 refuted on comparable data, confirm = C1+C3+C4 modern-class, forward test rides G12);
  two-coach architecture + the established look-ahead recorded; keys rotated, platform_sync + ~15
  manifested S3 prefixes; three S97 concerns closed as measured; structural finds (no winter Kalshi
  NG market; free weekly balance died 2025-10-02; STEO vintages = the free as-of balance; weekly-batch
  cash publication; futures-vs-options positioning at opposite extremes into G11). S99 = paid-data
  discussion FIRST, then T/A/I/M/Q/R + doctrine, then G12/G13.
  Detail: `SESSION_HANDOFF_2026-07-20_S98.md`, `research/kalshi/DATA_GATE_S98.md`.
- **S97** — G11 blind (6/12, drift -13,190, third straight block-lean miss) -> refine -> **brain s100.2,
  23 plays** (10/12, drift -3,890). The flip rule KEPT with a per-instance read: C1 clean (five fires, one
  correct decline, zero false positives), C2 broken on high-activity tapes by a SCALE artifact — the ratio
  reformulation is a build gap that BLOCKS G12. Plays now carry `requires`/`scope`/`forward_evidence`;
  refined NEVER overrides blind. MOS forecast temps built + first use. Net-of-fee replay: fees are not the
  constraint, DIRECTION is; the block lean and the day-book are two different edges. NG.v.0 whipsaws
  through expiry weeks (G3-G10 clean; G11 re-pulled on NG.n.0; pass-2 deferred). **Greg STOPPED the walk
  at a hard DATA GATE** — no group runs until every input in the S97 handoff is built and wired. Detail:
  `SESSION_HANDOFF_2026-07-19_S97.md`, `KICKOFF_2026-07-19_S98.md`,
  `research/kalshi/PASS2_CONTINUOUS_SERIES_NOTES.md`, `research/kalshi/COACH_REPLAY_S97.md`.
- **S96** — four winter blocks walked (G7-G10), protocol settled (one-shot canonical, refine per group,
  renders printed, Sunday-start blocks), brain s95.2 -> s99.2 (21 plays); two block-lean misses, both
  chain-polarity, which is why the flip confirm was hardened to four conditions.
  Detail: `SESSION_HANDOFF_2026-07-17_S96.md`.
- **S95** — continuous-curve rep + contract-roll adjustment (`roll_adjust.py`; the 0925 "+2760 gap" was the
  Oct->Nov roll, VOID); full G3-5 refine on roll-clean data; G6 first true blind holdout (V; give-back caught,
  recovery missed); brain ONE file, s95.1/s95.2. Detail: `SESSION_HANDOFF_2026-07-15_S95.md`.
- **S93** — the coach agent moved INTO AWS (Greg: the agent must live in his AWS, on the box, not a Claude
  Routine). Cleared the whole access chain (the `Claude` IAM user now has S3+EC2+SSM-full+Bedrock-full + inline
  PassRole; no permissions boundary) and stood the box up as the agent host: instance profile `Ssm` attached ->
  **box `i-08cee...` Online in SSM** (drive via `scratchpad/ssm_run.py`); **Bedrock LIVE in `us-east-1`** (model
  access is per-region — us-east-2 404s; boto3 converse OK for opus-4-1/4-5/4-6 + haiku-4-5); **Node 20 + Claude
  Code 2.1.197 installed on the box**, `/etc/markets/coach.env` wired (Bedrock=us-east-1, S3=us-east-2). ONE SNAG:
  Claude Code 2.1.197's model preflight rejects the Bedrock Opus IDs (boto3 invokes them fine) -> LLM not yet
  invoking. Per Greg, **OpenAI is now an accepted alternative agent backend** (loop is provider-agnostic). Brain
  did NOT advance (s92.1); no group scored/merged. Detail: `SESSION_HANDOFF_2026-07-14_S93.md`,
  `deploy/aws/COACH_AGENT_SETUP_S93.md`, `KICKOFF_2026-07-15_S94.md`.
- **S92** — NG intraday FORECASTER + DIRECTION cracked + the coach BRAIN. Built the full-toolbox per-leg
  characterizer (`month_characterize`: exhaustion suite + dipole + turning-point fingerprint + surprise/curve)
  and ran per-event (NO-pooling) learn/blind/hunt passes on 12 warm-season NG days. (1) **NG DIRECTION callable**
  — `dip_imb_level` order-flow imbalance sorts a leg's side 7%/93%, OOS-validated 100% strong-flow (34/34, 3
  unseen days); a nowcast for the Kalshi lag. (2) **Magnitude staircase** ($350->0.92, $500->1.00) + grind-vs-
  spike; book/dipole/exhaustion NOISE for SHAPE (magnitude confounds). (3) **Turning point = far-side liquidity
  RECRUITMENT, not consumption.** (4) **Coach BRAIN** `knowledge/ng_brain.json` + the self-growing loop (load ->
  forecast blind -> merge -> refine -> converge -> the agent becomes the COACH calling plays). (5) Year-box
  every-Monday-corrupt bug (Tue->Tue weeks + `_flush` 'wb' clobber) root-caused + FIXED ('ab') + DOW-naming + NG
  Mondays re-downloaded clean; box at ~Oct. (6) NYMEX-forward workflow git->S3 + NWS-hourly RT collector (need
  Greg's 3 GH secrets). Detail: `SESSION_HANDOFF_2026-07-14_S92.md`, `KICKOFF_2026-07-15_S93.md`.
- **S91** — YEAR-PULL REBUILT on a durable observable box + GOLD/SILVER depth-add VALIDATED. (1) The S90 box had
  failed (S3 year = corrupt July stubs, blind box); rebuilt: `pull_year --weekly` (per-week Databento jobs +
  marker-resume) + stub-aware resume-skip, on box `i-08cee7171c0a76a04` (200GB) streaming its log to S3 (v1 died
  on an awscli dependency; v2 boto3-only booted clean). (2) Gold/silver LAG confirmed on free Pyth XAU/XAG
  (gold 37/60, silver 26/54 sig, futures-lead, same as WTI/NG; cross-strike is NG-only) — collectors + XAU/XAG
  Pyth feeds wired, HH NGDQ6 feed confirmed correct. (3) Agents: NYMEX-products + Kalshi-ranking (KXGOLDD #1).
  Execution deferred to last (paper-trade Kalshi demo first). Open S92: verify the year landed clean, rotate
  keys, migrate data git→S3, validate the lag net-of-fee at size. Detail: `SESSION_HANDOFF_2026-07-14_S91.md`.
- **S90** — EVERYTHING TO AWS + a critical data-integrity fix. (1) Verifying the first S3 month exposed an
  80% loss: `batch_pull`'s flush gzipped each day BEFORE it was complete, so a later file's boundary rows
  overwrote it (only Fridays/last-day survived) — FIXED (hold latest-2 days unflushed; validated 32.8M/32.8M
  CL-July rows recovered). (2) `pull_year --reuse-done-jobs` + `redecode_job` rebuild corrupt months from
  already-paid Databento jobs FREE. (3) Durable **EC2 box** `i-0017dc36072eaa6c8` (needed EC2FullAccess on
  the `Claude` IAM user; no managed Lightsail-full policy exists) self-configures from S3 + runs the
  recovery+resume. (4) ALL bento data moved git→S3 (`nymex_tape/`+`nymex_mbp10/`); git holds NO bento now.
  (5) S3 tape reader `event_move_baseline.load_cont_day(source="s3")` + raw normalizer (JOB 2 core, wired
  into `month_characterize --source s3`). (6) RAW HOURLY weather ingestion `nws_temp_feed --ingest-hourly`
  → `weather/nws_hourly/` (every field/ob, no roll-up; the daily degree-day store was the same reduction
  mistake). (7) Weather interface spec + trade-distribution math + AWS deploy kit + the daily-cadence trigger
  note. NG dipole quick canary = static-divergence NULL (test exhaustion next). Secrets to ROTATE (Q5).
  Detail: `SESSION_HANDOFF_2026-07-13_S90.md`.
- **S89** — BUILT the durable RAW ingestion + moved the tick corpus to AWS S3. Zero-filter MBP-10 writer
  (removed the last silent row-drop; verified 76 fields/row, all 10 levels). `pull_year_mbp10.py`:
  month-at-a-time batch, gzip-each-day-as-it-lands (`batch_pull(flush_dir=)` bounds local to 1 day),
  `--worktree`/`--scratch`, and **`--dest s3://…` or git**. One-day proof (CL 2026-05-14 = 975k msgs,
  1.3 GB→61 MB gz). Now pulling the full-raw year (CL+NG, 2025-07..2026-07) to bucket
  `bento-568968024170-us-east-2-an` (us-east-2, prefix `nymex/`); split container Jan-Jun 2026 / Greg's
  box Jul-Dec 2025, resumable via bucket list. AWS+Databento keys are session-pasted SECRETS; corpus is
  on S3 now, not git. NEXT = finish/verify + rework scoring to read the raw S3 tape. Detail:
  `SESSION_HANDOFF_2026-07-13_S89.md`, `research/kalshi/AWS_INGEST_SETUP_S89.md`.
- **S83** — meta session: CLAUDE.md audit/split (this lean doc + `CLAUDE_ARCHIVE_OD.md`, dipole
  research + OD toolkit kept live); the three ritual skills (`kalshi-session-start`, `kalshi-backtest`,
  `kalshi-roll`). No research ran; `data/pyth-ticks` still absent at close.
- **S84** — Data reckoning + weather. NYMEX-canary principle set. Found Pyth has NO natgas (bogus `NGDQ6`
  id) → Databento = primary historical (true-tick CL+NG, `databento_backfill.py`). KXNATGASD = daily
  NG-futures market; KXPOWERKWH = monthly macro stat. Weather per-day fingerprint. Killed respawning
  crypto collectors. Detail: `SESSION_HANDOFF_2026-07-15_S84.md`.
- **S86** — Produced the **event-state MODEL** (`EVENT_STATE_DESIGN_S86.md`, Greg's driver model — see
  one-line state) + three leakage-gated builds on the 24 MBP-10 windows (~$0.42), all provisional/n=12/
  Apr-Jul/logged-without-mechanism: (1) MBP-10 depth run-length (push-book one-sidedness vs run length NG
  −0.17 / CL +0.52); (2) EIA seasonal-proxy surprise split (`eia_surprise.py`, 12/12; opposite-signed
  surprise/move NG vs CL); (3) pre-release VOLUME primed/coiled detector (`pre_release_volume`; NG quieter
  pre-release → bigger move, consistent across cells — first build off the model, no external feeds).
  Eyeball-validated (06-17 CL big move = the 2026 Hormuz crisis). NEXT = P3 lag join (needs a Kalshi
  historical pull; gates the $130 full-year MBP-10). Detail: `SESSION_HANDOFF_2026-07-13_S86.md`,
  `DEPTH_RUNLENGTH_FINDINGS_S86.md`, `EVENT_SURPRISE_FINDINGS_S86.md`, `PREVOL_FINDINGS_S86.md`.
- **S85** — Databento LIVE (key set, `pip install databento` 0.81). `event_move_baseline.py` BUILT + run
  on 12 NG + 12 CL real release windows (leakage PASS, `definition`-schema $10/tick): per-contract
  HOLD-TIME map (NG 60s=66% of move front-loaded; CL slower, 60s=27%, longer hold gets the rest — both
  kept, EV-net-of-fee is the gate). Futures move = the ceiling; lag join next. `databento_backfill.py`
  hardened (defs mode + point-in-time tick store, volume roll `.v.0`, retry/backoff). Schema decision =
  MBP-10 (depth, ~$130/yr both, ~$5 over credit; MBO off). Tape persisted on `data/nymex-ticks`
  (session-start restores it). Detail: `SESSION_HANDOFF_2026-07-12_S85.md`, `EVENT_MOVE_FINDINGS_S85.md`.
- **S88** — RAW-INGESTION correction (Greg, load-bearing): historical data is RAW, keep ALL the info; gates
  ONLY on the trade side. Rewrote the MBP-10 writer to keep everything (every message + all 10 levels, zero
  reduction). Built the data feeds `nws_temp_feed.py` (NWS gas-weighted HDD/CDD+precip) + `forward_curve.py`
  (backwardation/contango). Forecaster scoring scaffolding built (`month_characterize`, `bucket_continuation`,
  coin-style `forecaster_month_pass.workflow.js` — ran end-to-end, fixed a date-format leakage bug) but it
  pre-processes on the ingest side → must be reworked to read the RAW tape. NEXT = the durable raw-ingestion
  workflow. Detail: `SESSION_HANDOFF_2026-07-13_S88.md`, `KICKOFF_2026-07-14_S89.md`.
- **S87** — BUILT P3: `lag_join.py` lag-join engine (release + `--intraday`), NYMEX-driven entry/hold/exit,
  trend-hold dollar trailing stop, maker vs taker net-of-fee. PROVISIONAL but pays (CL/NG both positive
  gated; intraday 06-17 trend-hold −115c→+202c maker; leans on maker fill, tiny-n). Designed the intraday
  PATH FORECASTER as a stacked hold-length signal (`FORECAST_AGENT_DESIGN_S87.md` Greg's spec +
  `PATH_FORECAST_RESEARCH_S87.md` cited methods). Databento pull infra (`batch_pull`, `pull_year_mbp10.py`);
  1-yr continuous MBP-10 pull = pay-once to `data/nymex-ticks:nymex_cont/` = the forecaster's analog library
  (2-yr to S3 at go-live). Detail: `SESSION_HANDOFF_2026-07-13_S87.md`.

S86 priorities (see `KICKOFF_2026-07-12_S86.md`): (1) extend writer+baseline to consume MBP-10 DEPTH
(run-length/exhaustion read), then batch the full-year MBP-10 (watch disk); (2) historical surprise join
(EIA actuals + consensus) for the surprise-cell split; (3) the lag join = Kalshi echo net-of-fee vs the
futures move (realized-EV); (4) standing: NGDQ6 fix, weather forecaster scoring, Pyth live lag.

---

## Archive pointer

The full OD / info-dipole crypto research (S20–S37) and the earlier Information-Layer / four-forces /
gravity-time physics research (S3–S25, the INFO-0xx ledger, capability demos) live VERBATIM in
`CLAUDE_ARCHIVE_OD.md`. Nothing was deleted — it was moved out of the always-loaded context because it
is history, not the live Kalshi operating surface. Consult it only if a question reaches back into the
OD toolkit's provenance.

---

## Keeping this file lean (session-note workflow)

This file stays SHORT and CURRENT. Per session: write full detail to a `SESSION_HANDOFF_*.md`, update the
one-line state + header date/session at the top, fold only the new headline into the "Recent arc" list
(drop the oldest if it grows past ~6 entries), keep `KALSHI_TRADING.md` current, commit + push. Do NOT
paste session detail into this file — that is what the handoffs are for. The failure mode this structure
prevents: a bloated master a cheaper model silently half-ignores.
