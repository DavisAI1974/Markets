# SESSION HANDOFF — S114 (2026-08-06)

**Branch = `claude/kalshi-agents-coordinator-guard-sg0n15`. Brain s105.4 -> s105.9, 90 plays —
play CALLS unchanged. G24 BLIND RUN AND SCORED. No merge. THE G24 REFINE HAS NOT RUN and is the
next session's opener.**

---

## 1. G24 BLIND — the numbers, with named benchmarks (A-1)

Ten per-day specialists on causal slices, path contract clean, coordinator under the guard.

**6/10 direction, sum|err| 4,890, drift +1,010, survives 21%.**

| forecaster | sum\|err\| | vs blind |
|---|---|---|
| **BLIND** | 4,890 | — |
| zero_change | 4,970 | **0.98x — we TIED doing nothing** |
| seasonal_naive | 4,080 | **1.20x — we LOST to "last same-weekday move"** |
| persistence | 6,380 | 0.77x |

Best direction hit-rate of the walk, and it still ties the do-nothing forecaster. Hit-rate is not
the product; the curve is.

**THE DOMINANT FINDING — SYSTEMATIC UNDER-EMISSION, and it is getting worse.**
mean|guess| / mean|actual| = **0.29x**, under-emitted on **8 of 10 days**. Across blocks:
g22 0.55x, g23 0.68x, **g24 0.29x**. Max emission 250 against a max realized move of 1,360.
Emitting small IS emitting near-zero, which is why we tie zero_change. The registered forward test
`magnitude.emission_ceiling_check` was watching for a cap at ~550; the cap arrived at 250, so the
test was aimed at the wrong number.

**THREE COMPETING EXPLANATIONS, NONE PROMOTED (D37).** (a) the brief's stand-down passage biased
small — multiple specialists named "a confident wrong number is expensive and a declared stand-down
is cheap" as the line that did the most work; (b) shrinking was CORRECT — four specialists wrote
that their number moved toward zero because the brain refuted the instrument their read rested on
(D-1 flow at 44% next-day, heavy_buy_aggression 4/9); (c) the block was genuinely hard. The
under-emission is uniform (0.18-0.40, no clustering), which leans toward (a) — but n=1 block.
**NEXT RUN: vary the stand-down passage, hold everything else, compare the ratio.**

Committed: `forecasts/grp24.json`, `forecasts/g24_perday/`, render
`renders/ng_refine_s95/g24_blind_vs_actual.png`. **All immutable (NC-4).**

---

## 2. THE RENEWABLES FEED IS BUILT AND WIRED (G-5 / A-51)

Greg, repeatedly: *"I keep saying that we have to build the renewables part. That has to be done
before refine runs."*

New served block **`weather_forcing_forecast`** — forward wind and solar as a **31-member GEFS
ensemble DENSITY**, per day.

- Store `data/gefs_forcing/gefs_forcing.json`, 11 sessions, 31/31 members each. On S3 at
  `nymex/gefs_forcing/` and wired into `restore_substrate`.
- Wind CF p50 swings **0.157 -> 0.292 across the block (nearly 2x)**, p10-p90 spread 0.027 (a
  confident low-wind day) to 0.096. That is the width a specialist can decline on.
- **BLIND-LEGAL BY VINTAGE, AUDITED NOT ASSERTED**: the 12Z cycle of D-1, knowable ~13:00 ET
  against a 20:00 ET reopen. **10 of 10 days, 7.0h lead, ZERO violations.** (Greg: the refine does
  NOT need the blind wall — this audit is for the blind's benefit and does not gate the refine.)
- **Wind and solar served SEPARATELY, never summed** — seasonally anti-correlated (D37, S113).
- In `state_health.REQUIRED_EVERY_DAY`, so its absence can never again be invisible (hole #4 was
  exactly a block behind a try/except with no entry there).

**WHY IT MATTERED:** four specialists independently reported that no forward wind expectation
existed anywhere, while `grid_stack.wind_mwh` is D+2 stale BY CONSTRUCTION — so on the exact
channel the 0629 lesson is about, wind could only corroborate, never forecast.

---

## 3. EVERY DATA DEFECT FOUND, WITH ITS CAUSE

Each cause found, not patched. Each guard negative-tested so it produced its own output (NC-3).

- **`model_disagreement` 100% null** (8 of 10 specialists' top complaint). Cause: **BUILD ORDER** —
  the store was built 8 minutes BEFORE the raw MOS archive landed, and the empty-but-PRESENT record
  **shadowed the on-the-fly recompute fallback**, which only fires when a date is MISSING. Rebuilt.
  Its h>=2 "beyond model reach" note was ACCURATE and still misled three specialists (each computed
  "h2 is +48h, inside reach"); the binding constraint is FULL-GAS-DAY coverage (~+77h). Rewritten.
- **COT one publication stale, and it INVERTED A LOAD-BEARING TERM.** Three specialists built
  fat-upper-tail arguments on WoW **-45,414**; the fresh publication says **+2,953** (slight
  covering). Two causes: (1) cftc.gov sits behind Cloudflare, which 403s urllib's default
  User-Agent while serving any browser UA, so the current year silently stopped downloading while
  cached years satisfied the not-force branch; (2) `--build` built **1 of the 5 SERVED codes**.
- **`storage` / `stor_surprise` a full print stale** beside a fresh `storage_consensus`. Fixed
  additively (+2 prints, 0 changed). **And a THIRD block nobody had paired**: `storage_regional`
  frozen at 07-16 while `storage` advanced to 07-30 — two EIA-weekly blocks in one slice, two
  prints apart. `state_health` now asserts same-publication as-of agreement.
- **`vol_regime` — the magnitude conditioner, TWO defects.** (a) A DISTRIBUTION OVER INCOMPARABLE
  OBJECTS: the header declares "Sundays are REAL (thin) sessions" and **nothing downstream ever
  filtered on it** — 41 of 223 sessions (18.4%, 36 Sundays) carry <15% of median trades with median
  |net| 250 vs 600, dragging every trailing sigma down (+12% at the g24 anchor once removed).
  (b) **The S108 Monday-stub fix never reached this module** — on every Monday `*_prev_*` described
  the ~1h Sunday reopen (294 prints) instead of Friday (13,743).
- **Nested countdowns were exempt from the relive.** `_RELIVE_FIELDS` walks top-level keys only, so
  `options_surface.days_to_opex` — one level down in `months[]` — was frozen for the WHOLE WALK. It
  served 10 against a live 1, and 10 against an opex already PASSED. Now 8/5/1/0/-3.
- **`freeze_risk`** served `days_below: 0` for basins with every tmin null — a count with no
  measurement. Now null + named reason.
- **`scored_leg`** — new per-day block naming the scored contract, with a post-seam structural-mask
  caveat. Five specialists were resolving their own leg by hand.
- **The phase clock.** Phases are equal thirds of each session's own trade span, so the mapping
  MOVES: phase 2 ran 03:59-11:59 ET on one g24 session and 03:00-09:59 on the next. E-0724 inferred
  "phase 2 is the US session", was right on its day, would have been wrong on the other. Now serves
  `phase_bounds_et`. **Fourth time the `_tape_enrich` whitelist has caused or nearly caused a
  silent failure.**
- **The `ng_l1` writer DID NOT EXIST.** `--schema mbp-1` fell through to the TRADES writer, which
  discards every book field — a pull reported 333,530 rows and produced no L1 file. 8 of 10 g24
  sessions had no quote imbalance or spread. Writer built, 9 sessions pulled ($0.00 in-sub), pushed
  to S3, `l1_book` now True across the block.

**REFUTED, and worth keeping:** the "Monday stub in the 20260720 slice", filed by TWO specialists,
is NOT a defect. The block declares it three ways and **the day's OWNER used it correctly** — *"I
did not use the Sunday stub as a tilt (the state says not to)"* — and corrected its own first
draft. Both reporters were non-owners reading a headline for a day they did not own.

**REFUTED:** `grid_stack.age_days` constant at 2 is CORRECT — a fixed EIA-930 publication lag.

---

## 4. BRAIN s105.4 -> s105.8 (90 plays, 0 calls changed)

- `+ run_findings` section — the g24 negatives and positives, **attribution left contested where
  two explanations survive**. Withheld WHOLESALE from a reader inside its own window, because a
  block-level score carries no date and survives MMDD redaction. (My first draft of its own
  explanatory note quoted a real score as an illustration and leaked past the guard it described.)
- `+ handoff_out_schema` — the 9-field spec RELOCATED verbatim from a S104 session doc no
  specialist opens. E-0724 had reverse-engineered it from a neighbouring group's posterior that
  speculated into its own blind window.
- `+ b_share_basis_rule` — a 0.50 bar is read TWO-SIDED unless a play names otherwise (grounded in
  the S108 measurement: two-sided mean 0.4999, raw 0.4078).
- `~ terminal_impact_coefficient_carry` — struck a FALSE blind-legality claim (4 specialists; its
  own author among them).
- `~ 8 plays` — prose moved out of `confidence` into `confidence_note`, value nulled rather than
  invented; schema type-gate added and negative-tested (incl. bool, an int subclass that would sort
  as 1.0).
- `~ weekend_gap_wide_band_emission` — the 0.5-1.0x sigma band **holds on 1 of its own 4
  instances**. Struck. Per D37 the OBSERVATION survives (emit sign + wide band, never a point);
  only the sigma-width STORY dies.
- `~ 5 plays` — broken `state_path`s found by the A-46 sweep (see below).

**GENERATED VIEW ADDITIONS (never a second copy):** `instrument_priors` (53 of 90 plays carry a
measured track record buried in `health.can_change_state` — C-0721: *"they are the honest prior on
every instrument I have"*) and `live_verdict`, which hoists each play's OWN refuting line above its
call. **22 of 90 flagged.**

---

## 5. PLAY EVALUABILITY (A-46) — the highest-consensus request of the run

Every specialist asked for it in near-identical words. `brain_view --state <state> --day <YYYYMMDD>`
now resolves every parsed condition against the specialist's OWN served slice and stamps each play
**EVALUABLE / PARTIALLY_EVALUABLE / INPUT_ABSENT / NO_PARSED_CONDITIONS**, with each numeric limb
read out (`14.15 >= 3 -> ARMED`). **ANNOTATES, never drops** — the same specialists asked not to
lose falsifiers, health notes or contradicting instances. No leak: every value comes from the slice
the reader already holds. Wired into BLD-1 and RFN-1 via the template STORE.

**It immediately found two broken state_paths nobody had exercised:**
- `weather.summer_burn_lane_exclusion` pointed at a **PROSE pseudo-path** — which is WHY the play
  that should have carried this block stood down on 8 of 10 days as **uncomputable, not
  inapplicable**. Repointed at `grid_stack.bas.US48.gas_share_chg_7d` (added this session): now
  **EVALUABLE and ARMED**. The fix also shows why no substitution was available — on 20260727 gas
  MWh FELL 82,071 while gas SHARE ROSE +0.0135. **Opposite signs.**
- four weather plays pointed at `flow_calendar.month`, which does not exist.

INPUT_ABSENT 6 -> 2, EVALUABLE 26 -> 31.

---

## 6. TWO REGRESSIONS I SHIPPED AND CAUGHT

Recorded because the pattern matters more than the fixes.

1. **`scored_leg` as a hard requirement turned g19-g23 permanently red** — their state files predate
   the field and cannot carry it. A permanently-red andon is one people learn to ignore (S112
   Station 0). Fixed STRUCTURALLY: states now stamp `_state_build` (built_utc + the block vocabulary
   the builder knew), and `state_health` distinguishes "the builder did not know this block" (soft,
   re-stage) from "the builder knew it and produced nothing" (hard). 5 branches negative-tested;
   partial absence stays HARD even on a legacy state, because that IS a defect.
2. **`live_verdict` first flagged 43 of 90 by matching "degenerate" anywhere** — catching plays that
   merely DISCUSS degeneracy while concluding they are sound (`crash_regime_bands` "Within its
   stated regime, yes"; `failed_rally_tell` "YES on the refine side"). **A false CANNOT_CHANGE_STATE
   talks a specialist out of a working play** — the exact opposite of the point. Now reads the
   opening verdict only: 22 flagged, false positives clean.

Also: I edited `RUN_SOP.md` directly, which is exactly the A-7 divergence
`store/sop_templates.json` exists to prevent. Reverted, edited the store, re-rendered the appendix.

---

## 7. THE WEEKEND WAVE GATE — a process defect, not just a missing guard

E-0731 (a Friday): *"my handoff hands no chain state forward at all — I complied my way into an
empty field. That is not a reasoning failure, it is a PLUMBING GAP."* B-0727: *"A did not run and
three plays lost their stated input."*

**ROOT CAUSE: g24's owner map has NO A DAY AT ALL** — correctly, because A does not own a session,
it produces a BRIDGE artifact (BLD-2). So the SOP's wave 2 was **skipped by omission** and nothing
noticed. `spawn` now refuses a Monday whose in-block Friday has no A bridge, or records
`--no-bridge` as a declared deviation. 4 branches negative-tested.

---

## 8. FORWARD TESTS SETTLED

- **`reasoning_method.decision_order` — CONFIRMED on its stated falsifier.** At least 6 of 10
  posteriors show a pre-influence read differing from the post-chain estimate, and **20260723
  FLIPPED SIGN** (pre-influence DOWN, chain UP), attributable to two named scope clauses. Not
  degraded: sum|err| 4,890 vs g22's 5,965 on a market only 6% quieter.
- **`mission.brief_continuity_and_shape` — CONFIRMED on mechanical counts, ATTRIBUTION CONTESTED.**
  Contract violations **0 of 10** against g22's 10 of 10 and g23's 9 of 10; unattached days 0 vs
  g23's 8; largest-step share p50 0.22 vs 0.32/0.29. **The quietness artifact the falsifier warned
  about was checked**: mean |actual move| g22 527, g23 457, g24 497 — g24 was NOT quieter. BUT the
  brief and `path_contract.py` landed in the SAME session and this block cannot separate them.
- **3 winter-scoped tests re-scoped OFF g24** (a 20-31 July block, gw_hdd 0.0 every day) — they
  could never resolve and would have read DUE forever. A forward test needs an ELIGIBLE block, not
  the next one.

---

## 9. THE AUDIT WORKFLOW FAILED — and the agents behaved correctly

A 9-agent Workflow audit was launched and **every agent had a broken tool layer** — the permission
handler stripped required parameters from every call (Bash, Read, Grep, Glob, and StructuredOutput
alike). Zero successful tool calls, 764k tokens. **Every one of them refused to fabricate findings
and reported the blocker instead**, which is exactly right (NC-3). The `Agent` tool worked fine in
the same session — 10 blind specialists ran successfully — so the fault is Workflow-specific. The
audit was then done directly.

---

## 10. WHAT THE NEXT SESSION DOES — THE G24 REFINE

**The data plane is SYNCED. Verified: a fresh session's `restore_substrate` now pulls the FIXED
stores.** This was NOT true mid-session — S3 held pre-fix copies of `model_disagreement`,
`storage_regional`, `vol_regime` and all five COT books, and `eia_surprise.json` was absent from S3
entirely. Pushed and re-verified from S3 at close.

1. `git fetch origin claude/kalshi-agents-coordinator-guard-sg0n15 && git checkout -B ... origin/...`
   Confirm the tip is **`62382e2`** or later.
2. `python research/kalshi/restore_substrate.py`
3. **RE-STAGE g24 UNMASKED for the refine.** `renders/ng_refine_s95/grp24_state.json` is the
   IMMUTABLE record of what the blind read — the refine needs its own. A fresh build is
   **0 hard / 3 soft** (was 0 hard / 12 soft).
4. **`python research/kalshi/archive_blind.py g24` BEFORE `merge_perday`** — merge writes the
   CANONICAL specialist filenames and would otherwise overwrite the blind's (NC-4).
5. Spawn the refine per RFN-1. The emitted prompt now carries `--state`/`--day` so specialists get
   the A-46 evaluability annotation.
6. `group_coordinate_refine.py g24`, then `blind_score_nonpooled.py g24`, then render.

**THE REFINE DOES NOT NEED THE BLIND WALL (Greg, S114).** Do not gate or delay it on blind-wall
grounds.

---

## 11. OPEN AT CLOSE

- **THE BLIND ANCHOR / BLIND SUBDIRECTORY — deferred to next session by Greg.** `g24_actual.json`,
  `g24_exit_states.json` and `g24_mbo_evidence.json` sit in the same directory as the anchor a blind
  specialist is told to read. Named in S109, still live. Blind-only, so it does not block the refine.
- **Is open interest OVER-MASKED?** It is exchange-published and not a price, but the one-shot mask
  freezes it through roll week — the one week OI migration is the informative series. Needs a call.
- `weather_forecast_cycle` nets 18Z/00Z/06Z into ONE delta vector, so a specialist can derive the
  total add but not WHEN it arrived — five of twelve path points are a timing judgment where a
  per-cycle breakdown would make them arithmetic.
- The unwalked head 2025-07-22 -> 2025-09-05 (34 sessions, ~3 blocks) — the only remaining walk gap.
  **G25 is impossible** (only 3 of 10 sessions have happened).
- `storage_vintage` 5 months stale (STEO archived workbooks, not pulled).
- **Keys do NOT rotate during the walk** (D1, standing).

---

## 12. THE SCHEMA CORRECTION (added at close, Greg's call)

*"We should have a big correction that should be noted in the schema when the agents ignore the
things that was our biggest win. Not good."* — and *"build on the instances that we got right in
the schema and note the stuff we got wrong."*

**THE MEASURED DEFECT: 15 of the 22 plays flagged by their OWN health or falsifier still read
PROVISIONAL.** In every case the refutation was written down honestly — it just sat BELOW the
`call`, under a status saying the play was in good standing. That is the worst form of the fault,
because **the falsifier fields were the run's most-praised content** (every specialist named them;
one said "if you cut the view, cut CALLS before FALSIFIERS"), so a live status on a discharged
falsifier spends exactly the credibility they earned.

**AND THE do/dont RULE HAD SILENTLY EXPIRED.** S112 stamped `do`/`dont` across 624 instances and
found 43 declines reading as fires — but it was never made a SCHEMA RULE. So it held for the
instances that existed then and **every play merged since dropped it: 38 instances carried no
action at all.** A missing action reads as a FIRE. The identical defect, by the identical door,
two sessions later.

**WHAT WENT IN, brain s105.8 -> s105.9 (no play added, no call changed):**
- `DEGENERATE` status — the TRIGGER carries no information as written (the D23 disease). Distinct
  from `REFUTED`, which says the CLAIM is wrong. **The repair differs**: re-site the bar, keep the
  mechanism. **9 plays demoted on their OWN opening verdict**, never on my inference.
- `ACTION_ENUM` = do / dont / **observation** (narrow: a corpus measurement on a day the play was
  not run as a gate) + a hard gate. All 38 stamped.
- `fire_record` per play, do/dont counted and observations EXCLUDED — so the 8 plays merged at S114
  now show **n=0 fires, n=0 declines**, which is the honest reading of a merged-but-never-run play
  instead of letting an instance count imply a track record.
- `check_status_honesty`, `check_instance_actions`, `check_field_types` — all three negative-tested.
- A full **S114 CORRECTION RECORD** written into `brain_schema.py` itself, covering **five things
  we got RIGHT and should build on** (falsifiers are the most valuable field; contradicting
  instances earn their keep; equal footing works; a play's OWN opening words are a trustworthy
  classifier while prose anywhere in the body is not; declaring an absence beats removing it) and
  **six we got WRONG** (a cleanup that does not become a gate expires; a live status on dead
  evidence; a field that is a float on most plays and a sentence on a few; a play asserting an
  input it does not have; a test whose premise can expire; and — the one that caught three of my
  own guards — the fix needs the same scepticism as the defect).

It is kept in the ENFORCING file rather than a session doc, because that is the lesson: **a finding
recorded somewhere nothing reads is a finding that expires.** Mirrored into the brain as
`reasoning_method.what_a_play_status_means_S114` so specialists — who read the brain, not the
schema — get the operative half.
