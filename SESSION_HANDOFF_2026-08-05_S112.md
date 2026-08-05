# SESSION HANDOFF — 2026-08-05, S112 (the session the brain got its evidence, and the plant got a store)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain **s105.0, 82 plays** — play CONTENT
unchanged, EVIDENCE transformed. No group run, no play merged.

---

## THE HEADLINE: THE D29 WORK LIST IS CLOSED

S111 made the work list visible. S112 closed it.

| | S111 | now |
|---|---|---|
| support unaudited | 82 | **0** |
| corpus not searched | 82 | **2** |
| conditions unparsed | 74 | **0** |
| no falsifier | 65 | **0** |

The brain now carries **624 instances — 306 `do` and 318 `dont`** across 55 plays that hold both.

---

## THE TWO AUDITS

**THE 82-PLAY SUPPORT AUDIT.** All eight batches, corrected rubric. **41 OUTCOME_CREDITED, 26
MECHANISM_VERIFIED, 10 NOVEL_N1** — so half the brain rests on a day's number coming out right
rather than on its mechanism being checked. The headline instance: `daytype.eia_preprint_overextension_gate`'s
brain record says the gate SPARED the band on both G20 Thursdays while the committed blind posterior
says in its own `day_class` that it FIRED and REFUSED the band. Mechanism: limb (a) is denominated in
chain cum dollars, **which the blind masks** — so the brain merged the refine's account of a gate that
only ever has to work in the blind. That day was +2,100 actual against a +150 emission.

**THE DECLINE AUDIT — 384 declines, and the rubric came back negative 13 times, which was the point.**
JUSTIFIED 203, **DATA_ABSENT 115 (30%)**, SCOPE 53, **MISSED_FIRE 7**, OUTCOME_CREDITED 6. My ledger
as first built had no class for a wrong decline — every entry read as a save by construction, the
same non-falsifiable disease the play audit spent the session finding. Nearly a third of declines are
the play unable to evaluate at all: `monday.window_deep_book_shakeout` 8 of 8, `selector.divergence_resolution`
13 of 13, `direction.flow_nowcast` 7 of 7 with `dip_imb_level` occurring **zero** times in g20-g23 state.

**EQUAL FOOTING (Greg).** One `instances[]` list, one `action` field, `do` vs `dont` — no parallel
structure. The stamping found 43 declines already in the brain **reading as fires**, because until the
field existed they had no way to read as anything else. Every decline carries its `verdict` and
`reason_class`, so a DATA_ABSENT decline can never be silently counted as a working off-switch.

---

## D34 — THERE IS NOTHING LOCAL

Greg, in three statements: *"all of this stuff is going to live in aws or git so there should be no
paths from my desktop"*, *"there should be nothing local"*, *"right now everything gets pushed to git.
zero to e drive."* This generalises D33 from executables to **evidence**.

**MEASURED:** `BRAIN_AUDIT_PARTIAL_S111.json` carried 140 instances and **51 of them, across 11 plays,
cited `E:/Markets/...`** — real committed files, citations openable on one machine. That partial is the
input to the backfill, which writes instances **into the brain**. Fixed by `brain_audit.py fixpaths`,
140/140 clean.

**The tempting repair was the wrong one and Greg caught it:** my first guard silently re-rooted the
paths. That hides the defect instead of reporting it. A desktop path now FAILS.

**The guard was calibrated against real citations before shipping, which changed it twice** — the first
draft would have failed 93 of 140 legitimate instances, because auditors write `fileA + fileB`,
`g{18,20,22}_actual.json`, `g17..g23_actual.json`. A guard that always shows red is one people learn
to ignore.

---

## THE STORE (A-7)

**`DECISIONS.md` and `RUN_SOP.md`'s appendix are now RENDERS.** Extract → render → **prove byte-identical**
before anything becomes the source of truth. Both proved out; the decisions round-trip caught a
corruption I would otherwise have committed (my parser read columns from the right end, but D21's
escaped pipes sit in `enforced_by`, so it landed mid-`sha256`).

**The andon gates drift.** `plant_status` gains a `store` row — exit 0 with renders matching, **exit 1
with "STOP THE LINE"** when a document is edited behind its store.

**`spawn.py` — NC-1 is structurally unreachable.** Every slot fills by lookup and declares its source.
`CAL_FACTS` is generated, quoting `flow_calendar`: the g23 block emits `20260715: in_bcom_roll TRUE,
bcom_roll_day_n 5` — the exact fact the directive denied — under a header saying the legs are offset.
Two selftests assert it.

**And wiring it exposed the structural cause of NC-1 (A-13):** `CAL_FACTS` appears in **AUD-1 only**.
No forecasting specialist has ever received calendar facts. That is why the false premise reached the
directive *and* sat unchallenged in the blind posterior — the blind had nothing to contradict it with.

**A-9 done:** the drop-in's work list is now GENERATED from the registry, so a DONE item cannot appear
as a live instruction — which the committed `DROP_IN_S112` did twice.

---

## THE UNATTENDED PLANT

**`merge_gate.py` — SOP gates 2 and 3.** Greg's triage: gate 1 dies at go-live, gate 3 is downstream
of gate 2. Objective admissibility → PROVISIONAL merge with a **registered forward test** → settle,
retirement SCOPED per D31 and refused without a scope. **The automation is the bookkeeping, not the
judgment** — falsifiers are prose, and a tool claiming to evaluate them would manufacture verdicts.
What is automatable is that a registered test cannot be forgotten, which is exactly how the burn gate
died correctly. **Run against the real G20/G21 proposals it parks all five**, agreeing with what the
independent audit found a year later.

**`plant_calendar.py` — the plant's clock from RULES.** `flow_calendar.CME_HOLIDAYS` is a hardcoded
table ending **2027-02-15, 194 days of runway**; past it every date reads "not a holiday". Rules
reproduce all 16 committed entries, 0 mismatches. 1031 sessions, **cal+0..cal+3**, wrapping to cal+0
day 1 and incrementing `cycle`.

**MEASURED, because it decides the design: the calendar does NOT repeat on four years.** Memorial Day
runs 05-25 / 05-27 / 05-29 / 05-31 across 2026/2030/2034/2038; Good Friday shifts +16 or −12/−19 days
and lands on the same date four years later in **0 of the next 100 years**. 4 years = 208 weeks + 5
days. **The RULE is invariant — which is why the loop works; the DATE is not — which only matters if
dates are replayed rather than recomputed.** Hardcoding cal+0..cal+3 is correct because these are
already-happened sessions being re-walked; the store carries the never-project-past-cal+3 boundary
beside the data.

**The wrap is the valuable part:** re-walking a session on a later cycle with a better brain is a
REPEAT MEASUREMENT, which is what makes "the runs get better" measurable instead of an impression.

---

## MY OWN ERRORS, CAUGHT AND CORRECTED

- **I banked an instance the owning specialist forbade.** `grp21_mbo_specialist_A.json`: *"Do not bank
  0619 as forward evidence for `daytype.covering_giveback_self_limiting` (de-triggered, not tested)."*
  The backfill banked it anyway from E's file. **And the contamination propagated** — the decline audit
  then scored that row JUSTIFIED, because its batch was also given E's file. Two independent passes
  banked a day the owner declared never asked.
- **My first two retractions barely worked.** The D29 migration left **shadow copies** in `legacy_notes`;
  retracting a live field while its twin survives is theatre. Both swept; 17 duplicated keys measured.
- **A vacuous test.** "repeats every 100 years? YES" — the range was empty, so `all()` passed having
  compared nothing. Same shape as the D33 guard that passed by never firing.
- **A wrong blast-radius claim.** I said the four missing early-close dates touched no walked group;
  I had searched `group_config`, which only holds g17+. They are in g8 and g9.
- **A divergence I created:** `spawn.py` carried abridged templates and no BLD-2/RFN-1/RFN-2 — the A-7
  disease, committed by the tool built to end it. Now loaded from the store.

---

## NEW REGISTRY ITEMS

**M-9** OD-era scripts still hardcode `E:\\Markets` · **A-9** drop-in work list generated (DONE) ·
**A-10** the book/dipole feature block is dead in `fingerprints.json` from 2026-01-18, blocking A-6
and A-8 · **A-11** serve chain state — unblocks nine plays · **A-12** `vol_regime.n0_prev_*` is a
per-block constant, valid only on a block's first day · **A-13** serve DAY_CALENDAR to BLD-1/RFN-1 ·
**A-14** `CME_HOLIDAYS` documents an `early_close` class and contains zero entries of it.

---

## OPEN, IN PRIORITY ORDER

Generated: `python research/kalshi/store.py worklist`. **G-11** is irreversible — every week waited is
permanently lost. **A-13** and **A-11** need Greg's call. **A-1** (zero-change baseline) remains the
cheapest thing that makes every future number readable.

---

## CHATGPT: PRIOR SCOPE, THE NEAR-MISS, AND WHAT IS OUT NOW

**Six S112 tasks were delivered and NONE are in the repo** - the answers are with Greg. They map to
G-5 (dipole direction), G-4 (ECMWF/GEFS members; ISO forward wind and solar), A-5/A-19 (degree-day
construction and a summer replacement), G-7 (the regime label) and M-5 (LNG feedgas nominations).
S113 must collect them at bring-up and COMMIT them, because paid-for work sitting outside git is the
same defect D34 was written for.

**THE NEAR-MISS, and it is the more useful half.** The first generated S113 brief re-asked three of
those six questions and heavily overlapped a fourth. The generator had no way to know: the registry
tracked what was OPEN and never tracked what had been DELEGATED. Greg caught it before it shipped.
Fixed structurally rather than by memory - items carry `delegated_prior`, the brief renders it as its
own section, and a selftest fails the build if an item is re-asked without declaring the prior ask in
its own text. **A registry that tracks only status cannot prevent duplicate delegation; it has to
track who was asked.** Same shape as A-9 one document over, and as A-17 one level up.

**OUT NOW (four tasks, all source-hunting, none requiring our data):** A-17 forward nuclear outage
schedules; A-19 the utilities' own IRP station lists and the EIA-930 BA boundaries, narrowed so it
cannot re-run S112 T4; A-20 the hydro sources including the FERC licence articles; and A-23 the
triage of the 1,129 unread data points, which ships with `DATA_POINTS.md` as its input.

**The delegation line is real:** source hunting delegates, fitting does not. A coefficient tuned
without our states is hindsight-fitted with zero forward evidence, and per D35 the output is a
national total, so per-BA parameters fitted elsewhere are numbers we would discard.
