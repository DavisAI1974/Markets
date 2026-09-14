# DROP-IN — S113

Single box (web version - no paste-and-verify split needed).

---

## 0. BRANCH AND BRING-UP

```
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
git log --oneline -1
pip install --quiet numpy pandas matplotlib boto3 databento
python research/kalshi/verify_gold.py            # MUST print PASS + runtime==gold
python research/kalshi/plant_status.py           # andon; now gates STORE DRIFT too
python research/kalshi/brain_schema.py validate
python research/kalshi/store.py check            # renders must match their stores
```
Expect the tip to be the S112 close-out. Keys and `data/` do not survive a session - expected; a
group staged at S108+ runs both rounds without a data plane.

## 1. READ ORDER

`research/kalshi/FORECAST_ARCHITECTURE_S111.md` **FIRST** - the target is unchanged and everything
hangs off it. Then `SESSION_HANDOFF_2026-08-05_S112.md` -> `DECISIONS.md` (**D34, D35, D36** are new)
-> `research/kalshi/agents/RUN_SOP.md` (BINDING - **read STATION 0 first, it is new and it is
enforced**) -> `OPEN_ITEMS.md` (the tiered work registry) -> `DATA_POINTS.md` (every data point we
hold, labelled READ or NOT READ) -> `CLAUDE.md` header.

## 2. STATE

Brain **s105.0, 82 plays** - play CONTENT unchanged, EVIDENCE transformed. No group run in S112, no
merge. **The D29 work list is CLOSED**: support unaudited 82 -> 0, corpus unsearched 82 -> 2,
conditions unparsed 74 -> 0, no falsifier 65 -> 0. The brain carries **624 instances - 306 `do` and
318 `dont`** across 55 plays holding both, every decline carrying its audit verdict.

**G23 was the last staged block - G24 needs a DATA PULL, not a re-stage.**

## 3. WHAT IS NEW AND BINDING

- **D34 THERE IS NOTHING LOCAL.** git = code and records, S3 = data, `data/` disposable. No artifact
  may name a desktop path. Enforced by `brain_audit.py _is_machine_path`.
- **D35 THE TARGET IS TOTAL GAS DEMAND, NOT ATTRIBUTION** (Greg: *"we are trying to find overall gas
  demand. Don't care who is burning it or where"*). No per-BA number is ever a deliverable. But the
  per-BA decomposition is arithmetic we cannot skip: the stack is a per-BA subtraction (ERCOT's wind
  does not serve PJM's load) and the response is convex, so the total is not recoverable from the
  average. **The BA list closes by RECONCILIATION to US48, not by map coverage.** And the target is
  not a national index - **Henry Hub is ONE physical point near Erath, Louisiana**, so the object is
  demand HH can SEE, and the roll-up weight is burn x HH transmission.
- **D36 A BRIEFING'S RECOMMENDATIONS BECOME REGISTRY LINES IN THE SESSION IT LANDS.** Found because
  Greg asked whether the 13 S111 build suggestions were still listed: **12 of 13 had no item**,
  including a live wrong-sign risk on a feed we had already built and a leakage question in the
  module that conditions magnitude. Registered as G-16..G-28.
- **SOP STATION 0 - DOCUMENT IT NOW, and it is ENFORCED** (Greg: *"We can't spend time on an sop that
  we don't apply"*). `plant_status.py` runs four checks at every bring-up: `station0/why` (no item
  may carry an instruction without reasoning), `station0/briefings` (D36 - and a `pending`
  placeholder counts as NOT audited), `station0/defects` (every defect carries a repair class), and
  `station0/registry` (INFO - the item delta, so a silent session is loud). **It is RED right now on
  purpose: 6 of 7 briefings have never been audited.**
- **TWO NEW REGISTRIES.** `store/documents.json` + `store.py docs` - every working document with its
  class (LIVE / RENDER / VAULT / RECORD / ARCHIVE) and a CONTENT gate, because mtime is not
  staleness. `data_registry.py` + `DATA_POINTS.md` - four tiers, **1,717 served data points and 1,129
  read by NOTHING**.
- **NEW RENDERS - never hand-edit these:** `OPEN_ITEMS.md`, `DATA_POINTS.md`,
  `CHATGPT_HANDOFF_S113.md`, and the completeness appendix in `KALSHI_TRADING.md`.
- **THE STORE.** `DECISIONS.md` and `RUN_SOP.md`'s appendix are RENDERS generated from `store/`.
  **Edit the store, never the document** - the andon FAILS on drift and a FAIL stops the line.
- **`spawn.py`** fills every SOP slot BY LOOKUP; NC-1 is a regression test.
- **`merge_gate.py`** closes SOP gates 2 and 3 unattended: objective admissibility -> PROVISIONAL
  merge with a REGISTERED forward test -> settle, scoped per D31. Parks 5 of 5 real past proposals.
- **`plant_calendar.py`** is the plant's clock from RULES. 1031 sessions, cal+0..cal+3, wrapping to
  cal+0 day 1 and incrementing `cycle`. **Never project past cal+3 by replaying dates** - the
  calendar does not repeat on four years (measured: Good Friday matches in 0 of the next 100).

## 4. FIRST WORK - GENERATED FROM THE REGISTRY (A-9), NOW TIERED

Regenerate any time with `python research/kalshi/store.py worklist`. Only OPEN and IN_PROGRESS items
can appear, so a completed item cannot show up as a live instruction - which the committed
`DROP_IN_S112` did twice. **The full tiered list with every item's reasoning is `OPEN_ITEMS.md`**,
itself a render of `research/kalshi/OPEN_ITEMS.json` - read it, do not edit it.

**61 open items: 8 ESSENTIAL, 11 BIGGEST WIN, 42 REST.** Order is IRREVERSIBLE, then RE-RAISED, then
TIER, then size - effort is the tie-breaker and never the lead.

- **G-11** (XS) Start accruing EIA weekly coal basin spot prices  [ESSENTIAL]  [IRREVERSIBLE - value is permanently lost by waiting]
- **A-17** (S) NUCLEAR PLANNED-OUTAGE SCHEDULE (forward) - agreed TWICE across sessions and never tracked until S112  [RE-RAISED - Greg has had to ask for this at least twice, across sessions]
- **A-14** (XS) flow_calendar.CME_HOLIDAYS documents an early_close class and contains ZERO entries of it  [ESSENTIAL]
- **G-1** (XS) Confirm what replaced the NGWU supply-demand balance (NOT a repoint - the feed already knows both eras)  [ESSENTIAL]
- **A-1** (S) Wire zero-change and seasonal-naive baselines into blind_score_nonpooled  [ESSENTIAL]
- **A-12** (S) vol_regime.n0_prev_* is a PER-BLOCK CONSTANT - valid only on a block's first day  [ESSENTIAL]
- **A-13** (S) SOP CHANGE PROPOSAL: serve DAY_CALENDAR (+CAL_FACTS) to BLD-1 and RFN-1 - only the AUDITOR gets calendar today  [ESSENTIAL]
- **G-28** (S) VOL REGIME: Markov-switching form, and a LEAK to check in the state probability  [ESSENTIAL]
- **A-11** (M) SERVE CHAIN STATE (cum_from_anchor + chain age) in the decision state - it unblocks a whole play family at once  [ESSENTIAL]
- **A-16** (XS) SERVE HYDRO - it is ALREADY IN THE STORE back to 2019 and dropped at the serving read. The SUMMER shortfall is ~2 Bcf/d of gas fill  [BIGGEST WIN]
- **A-15** (S) THE THERMAL STACK IS SERVED AND UNREAD - coal_mwh and nuclear_mwh have zero consumers  [BIGGEST WIN]
- **A-18** (S) SERVE THE MISSING SOUTHEAST BAs - TVA, CPLE, DUK, FPL, SCEG (+check CPLW). We carry 1 of 6 in the largest summer-burn region  [BIGGEST WIN]
- **A-2** (M) Build NO CALL (matrix-profile discord + EIA sampling floor + ensemble gate)  [BIGGEST WIN]
- **A-4** (M) Score the CURVE, not the scalar - four error terms kept separate  [BIGGEST WIN]

**THE ESSENTIAL EIGHT ARE ROUGHLY A SESSION AND A HALF, and they are the honest gate on the next
group** - not the whole backlog. Greg asked to get the building done before the next group runs; the
building that actually blocks a trustworthy group is this tier, not all 61 items. In particular:

- **G-28 is a LEAK CHECK and it comes first.** If `vol_regime` uses a smoothed state probability
  anywhere, every historical group was conditioned on information the day did not have - in the
  module built to condition MAGNITUDE. Until it is checked, no group's magnitudes mean what they
  claim, so there is little point improving anything downstream of it.
- **A-1 makes every number readable.** The standing rule is "never report an error number without a
  named benchmark" and we currently cannot satisfy it.
- **G-11 is losing data every week.** Five-week rolling window, history proprietary.

## 5. TWO ITEMS NEED GREG'S CALL BEFORE THEY CAN BE BUILT

- **A-13** - `CAL_FACTS` reaches **AUD-1 only**, so no forecasting specialist has ever received
  calendar facts. That is the structural cause of NC-1. `day_calendar()` is built and tested;
  adding `{DAY_CALENDAR}` to BLD-1 and RFN-1 is a change-controlled SOP edit (D10).
- **A-11** - serving chain state (`cum_from_anchor` + chain age) would unblock nine plays at once.
  Four of eight conditions-curation batches hit this independently.

## 6. CHATGPT - WHAT IS ALREADY DONE, WHAT IS OUT, AND WHEN WE NEED IT BACK

**READ THIS BEFORE DELEGATING ANYTHING.** It caught a real duplication in the S112 close-out.

### What ChatGPT has ALREADY delivered (S112) - and where those answers are

Six tasks were sent and all six came back. **The answers are with Greg, NOT in this repository, and
none of them are wired.**

| task | subject | maps to |
|---|---|---|
| S112 T1 | the dipole direction result | G-5 |
| S112 T2 | ECMWF ENS + GEFS ensemble MEMBER retrieval | G-4 |
| S112 T3 | ISO day-ahead and 7-day wind, solar and load forecasts | G-4 |
| S112 T4 | gas-weighted degree-day construction + a summer replacement | A-5 / A-19 (adjacent) |
| S112 T5 | the North American weather regime label | G-7 |
| S112 T6 | LNG feedgas nomination sources | M-5 |

**ASK GREG FOR THESE AT BRING-UP, IN SECTION 0, BEFORE STARTING ANY DEPENDENT WORK.** They are the
input to four registry items and none of that work can be estimated, let alone built, without them.
This is a D34 situation in spirit: the work exists but not where the next session can run it, so the
first thing to do with each answer is COMMIT IT so it stops being a hand-carry.

### The near-miss, recorded because it will recur

The first generated `CHATGPT_HANDOFF_S113.md` **re-asked three questions ChatGPT had already
answered** - ECMWF/GEFS members, ISO forward wind and solar, LNG feedgas nominations - and heavily
overlapped a fourth. Nothing in the generator knew, because the registry recorded what was OPEN but
never recorded what had been DELEGATED. Greg caught it. Fixed structurally: items now carry
`delegated_prior`, the brief renders it in its own section, and a selftest fails the build if any
item is re-asked without declaring the prior ask inside its own text. **A work registry that tracks
only status cannot prevent duplicate delegation - it has to track who was asked.**

### What is OUT to ChatGPT now (S113) - four tasks, all source-hunting

`CHATGPT_HANDOFF_S113.md` plus one self-contained file per task under
`research/kalshi/chatgpt_tasks/S113_TASK_*.md`. Generated by `chatgpt_handoff.py`, so a finished item
can never appear as a live request.

- **A-17** forward nuclear outage schedules (NRC daily status, refuelling filings, ERCOT NP3-233-CD,
  PJM frcstd_gen_outages, EIA-860M for coal)
- **A-19** the utilities' own IRP weather-normalization STATION LISTS and the EIA-930 BA boundaries.
  Explicitly narrowed so it cannot re-run S112 T4.
- **A-20** the hydro sources - USGS gauges on both sides of the Tennessee Valley Divide, TVA
  machine-readability, USACE spill, pumped-storage capacity per BA for the dilution factor, and the
  FERC licence articles nobody has looked at
- **A-23** the triage of the 1,129 unread data points. **Send `DATA_POINTS.md` with this one** - it
  is the input.

**WHEN WE WANT IT:** A-20 and A-19 gate the hydro and station work, which is the largest open thread.
A-23's verdicts feed A-24. None of it blocks the walk, so it can run in parallel with a group - but
ask Greg for the S112 answers FIRST, because those are already paid for and still unwired.

**WHAT DOES NOT DELEGATE:** any fitting. No thresholds, weights or coefficients - a number tuned
without our states is hindsight-fitted with zero forward evidence, and per D35 the output is a
national total anyway, so per-BA parameters fitted elsewhere are numbers we would discard.

**KEYS DO NOT ROTATE DURING THE WALK.** git = code + records, S3 = data. No emojis.
