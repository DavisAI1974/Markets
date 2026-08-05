# DROP-IN — S114

Single box (web version - no paste-and-verify split needed).

---

## 0. BRANCH AND BRING-UP

```
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
git log --oneline -1
pip install --quiet numpy pandas matplotlib boto3 databento
python research/kalshi/verify_gold.py            # MUST print PASS + runtime==gold
python research/kalshi/plant_status.py           # andon
python research/kalshi/brain_schema.py validate
python research/kalshi/store.py check            # renders must match their stores
python research/kalshi/creds.py                  # NEW - which secrets resolve, by NAME only
```

Expect the tip to be the S113 close-out. `data/` does not survive a session - expected; a group
staged at S108+ runs both rounds without a data plane.

**TWO BRING-UP FACTS THAT WILL OTHERWISE LOOK LIKE FAULTS.**

1. `state_health` reports HARD failures on G19's window (2026-05-11..05-22): storage,
   stor_surprise, weather, vol_regime empty. **This is a stale STAGED artifact on a completed
   group**, staged at S106/S107 before S107 fixed the six silent-empty blocks. It is not a live
   data-plane fault and it blocks nothing. A re-stage clears it.
2. **Credentials no longer come from `scratchpad/`** (Greg, S113: *"no more scratchpad. It's in the
   sop"*). `creds.py` resolves process env -> `~/.config/markets/env` (chmod 600, outside the repo)
   -> legacy scratchpad WITH A WARNING. **Use `creds.aws_client()`, never bare `boto3.client()`** -
   the container injects `AWS_ACCESS_KEY_ID=proxy-injected` which otherwise shadows the real pair
   and fails as though the key were dead. **KEYS DO NOT ROTATE DURING THE WALK.**

## 1. READ ORDER

`research/kalshi/FORECAST_ARCHITECTURE_S111.md` **FIRST** - the target is unchanged. Then
`SESSION_HANDOFF_2026-08-05_S113.md` -> `DECISIONS.md` (**D37 and D38 are new, and NC-3**) ->
`research/kalshi/agents/RUN_SOP.md` (BINDING - **v1.9 is new**) -> `OPEN_ITEMS.md` (**read A-38
first**) -> `DATA_POINTS.md` -> `CLAUDE.md` header.

## 2. STATE

Brain **s105.0, 82 plays - UNCHANGED. No group run in S113, no merge.** Registry **87 items, 75
live: 5 ESSENTIAL, 20 BIGGEST_WIN, 50 REST.** Decisions **42 entries** including NC-3. Defect
registry **14** (RETRO_REPAIRED 2 / FORWARD_ONLY 10 / OPEN 2).

**G23 was the last staged block - G24 needs a DATA PULL, not a re-stage.**

## 3. WHAT IS NEW AND BINDING

- **D37 - NO AVERAGE MAY BE A VERDICT, AND A REFUTED STORY DOES NOT DEMOTE A MEASUREMENT.** Greg had
  to say the no-average rule for the tenth time, so it is now a FUNCTION:
  `research/kalshi/per_event.py report(...)` prints the D4 set, an improved/worsened COUNT and the
  largest ACTUAL moves named one by one, and **returns no scalar**. **AN R2, A CORRELATION AND A
  FITTED SLOPE ARE ALL AVERAGES** - that is the form the rule kept being broken in, not the word
  "mean". Measured in one S113 analysis: a pooled correlation whose sign was opposite to every
  constituent cell, an R2 of 0.554 hiding a 92-improved / 72-worsened per-week record whose worst
  week got worse, and an OLS slope quoted as evidence. Second half: an OBSERVATION and the STORY
  explaining it are independent. A measurement is dropped only when ITS OWN evidence fails.
- **D38 - BURN FOLLOWS GENERATION, NOT LOAD.** A BA with no gas gen still creates gas demand; it
  imports the power and somebody else burns the fuel. CISO net-imports **p50 20.6% / MAX 41.7%** of
  its load. **US48 is the only level where the interchange term collapses (p50 0.5%)**, which is why
  D35 closes the BA list by reconciliation rather than map coverage. **The term is a BOUNDARY term:
  the storage/national roll-up needs NONE (it cancels pairwise), the HH lane needs its own fence
  flow.** Sign VERIFIED by the accounting identity `TI = sum(gen) - demand`, not by assuming anyone
  is always an importer - **power flows both ways in every system.**
- **SOP v1.9** - BLD-1 and RFN-1 carry `{DAY_CALENDAR}` (A-13, NC-1's structural cause). A blind
  specialist can now see that its prior trading session was Thursday, not Friday. `spawn.py
  selftest` 22/22.
- **NC-3** - I reported a guard "negative-tested both directions" when its firing branch had never
  executed; it raised `NameError` on the next run and took the data plane down. **A test that never
  produced the guard's OUTPUT did not test the guard.**

## 4. THE ONE FINDING TO ARGUE WITH BEFORE BUILDING ANYTHING (A-38)

Greg scoped the storage lane as *"overall gas demand"*, so it was measured. STEO jul26 vintage,
**actuals only**, 52 month-over-month moves in US total consumption, each named individually:

- **res/comm heating is the bigger mover on 33 of 52 months, and on 10 of the 10 largest.**
- **On 12 of 52, power burn moved OPPOSITE to total demand** - every November in the record (202211
  total **+16.1** while power **-0.46**).
- January 2025: 28.7% power burn, 42% heating. July 2025: 54.8% power burn.

**SCOPED PER D31 - this does NOT refute the burn stack.** In summer res/comm sit at their floor, so
essentially all summer variance IS power burn; the HH lane is untouched. It says only that for the
**winter storage lane** the dominant component - HDD to res/comm Bcf/d - is unmodelled, and the
registry was searched to confirm nothing covers it.

**DO THE WEEKLY RE-CHECK FIRST.** The evidence is MONTHLY; the traded objects are weekly (the EIA
print) and daily (the curve). A monthly seasonal transition may overstate the heating share at
trading horizon. Until that check runs, A-38 is a strong signal and not a settled fact - and it is
the thing most likely to change what the next build should be.

Evidence: `research/kalshi/data_records/us_gas_demand_by_sector_S113.csv`.

## 5. FIRST WORK - GENERATED FROM THE REGISTRY (A-9)

Regenerate any time with `python research/kalshi/store.py worklist`. Only OPEN and IN_PROGRESS can
appear, so a completed item cannot show up as a live instruction. The full tiered list with every
item's reasoning is `OPEN_ITEMS.md`, a render of `research/kalshi/OPEN_ITEMS.json` - read it, do not
edit it.

**75 live items: 5 ESSENTIAL, 20 BIGGEST WIN, 50 REST.** Order is IRREVERSIBLE, then RE-RAISED, then
TIER, then size.

- **G-11** (XS) Start accruing EIA weekly coal basin spot prices  [ESSENTIAL]  [IRREVERSIBLE - value is permanently lost by waiting]
- **A-17** (S) NUCLEAR PLANNED-OUTAGE SCHEDULE (forward) - agreed TWICE across sessions and never tracked until S112  [RE-RAISED]
- **G-1** (XS) Confirm what replaced the NGWU supply-demand balance  [ESSENTIAL]
- **A-11** (M) SERVE CHAIN STATE - it unblocks a whole play family at once  [ESSENTIAL]  [NEEDS GREG'S CALL - see 6]
- **A-37** (M) HH TERRITORY IS UNDELIMITED - the HH lane cannot have a number until the fence is drawn  [ESSENTIAL]
- **A-38** (L) THE STORAGE LANE'S DOMINANT DEMAND COMPONENT HAS NO MODEL  [ESSENTIAL]
- **A-15** (S) THE THERMAL STACK IS SERVED AND UNREAD - coal_mwh and nuclear_mwh have zero consumers  [BIGGEST WIN]
- **A-18** (S) SERVE THE MISSING SOUTHEAST BAs - we carry 1 of 6 in the largest summer-burn region  [BIGGEST WIN]
- **A-29** (S) WIND SPEED IS FETCHED ON BOTH PATHS AND DROPPED AT THE ROLL-UP - the index is dry bulb only  [BIGGEST WIN]
- **A-30** (S) GAS PLAYS BOTH ROLES AND IT IS PER-BA - gas is now more BASELOAD than coal, inverting our written stack  [BIGGEST WIN]
- **A-31** (S) COAL IS A STARTUP-CONSTRAINED RAMP, NOT A CEILING  [BIGGEST WIN]
- **A-35** (S) THE FLEET IS DRIFTING UNDER US - quieter middle, fatter tails  [BIGGEST WIN]

**A-28 (hourly EIA-930 ingest) is now UNBLOCKED by the key and six registered findings queue behind
it** - it is the highest-leverage single build in the BIGGEST_WIN tier for that reason.

## 6. WHAT NEEDS GREG BEFORE IT CAN BE BUILT

- **A-11 (SERVE CHAIN STATE) - a design call, not a build.** Serving chain state to the blind means
  serving `cum_from_anchor`, which is PRICE CONTENT; serving it live would leak the realized path -
  the same class as the A-12 trap caught in S113. Four of eight conditions-curation batches hit this
  independently, and nine plays are blocked on it. **The question is what NON-PRICE form of chain
  state the blind may hold.**
- **THE BRAIN MERGE.** Nothing from S113 is in `knowledge/ng_brain.json`. **The specialists read the
  brain, not the registry**, so D37, D38, A-38 and the whole S113 domain account (renewables
  seasonality, gas in both roles, the coal commitment cycle, the correlated-failure tail, the
  mediated response) reach a forecaster only through a merge - proposal plus adjudication, D8/D22,
  SOP STEP 6. **This is the largest single gap at S113 close.**

## 7. STILL OPEN FROM BEFORE, UNCHANGED

- **M-10** - four files still read `scratchpad/aws.env`: `databento_live_smoke.py`,
  `nuclear_outages.py`, `plant_status.py`, `session_bootstrap.py`. `platform_sync.py` was migrated
  in S113; use it as the pattern.
- **station0 / briefings FAIL** - 6 of 7 briefings never audited, now plus three committed S113
  papers (`CHATGPT_S112_SIX_WORKSTREAMS.md`, `CHATGPT_S113_T1_NUCLEAR_OUTAGE_SOURCES.md`,
  `CHATGPT_S113_A24_HIDDEN_EDGE_CANDIDATES.md`).
- **The paper remainder** - A-24a (its own top-ranked candidate), A-24d/e/f registered but untested;
  A-24g blocked on A-28.
- **G24 needs a DATA PULL.**
