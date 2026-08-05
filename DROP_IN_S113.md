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
hangs off it. Then `SESSION_HANDOFF_2026-08-05_S112.md` -> `DECISIONS.md` (D34 is new) ->
`research/kalshi/agents/RUN_SOP.md` (BINDING) -> `CLAUDE.md` header.

## 2. STATE

Brain **s105.0, 82 plays** - play CONTENT unchanged, EVIDENCE transformed. No group run in S112, no
merge. **The D29 work list is CLOSED**: support unaudited 82 -> 0, corpus unsearched 82 -> 2,
conditions unparsed 74 -> 0, no falsifier 65 -> 0. The brain carries **624 instances - 306 `do` and
318 `dont`** across 55 plays holding both, every decline carrying its audit verdict.

**G23 was the last staged block - G24 needs a DATA PULL, not a re-stage.**

## 3. WHAT IS NEW AND BINDING

- **D34 THERE IS NOTHING LOCAL.** git = code and records, S3 = data, `data/` disposable. No artifact
  may name a desktop path. Enforced by `brain_audit.py _is_machine_path`.
- **THE STORE.** `DECISIONS.md` and `RUN_SOP.md`'s appendix are RENDERS generated from `store/`.
  **Edit the store, never the document** - the andon FAILS on drift and a FAIL stops the line.
- **`spawn.py`** fills every SOP slot BY LOOKUP; NC-1 is a regression test.
- **`merge_gate.py`** closes SOP gates 2 and 3 unattended: objective admissibility -> PROVISIONAL
  merge with a REGISTERED forward test -> settle, scoped per D31. Parks 5 of 5 real past proposals.
- **`plant_calendar.py`** is the plant's clock from RULES. 1031 sessions, cal+0..cal+3, wrapping to
  cal+0 day 1 and incrementing `cycle`. **Never project past cal+3 by replaying dates** - the
  calendar does not repeat on four years (measured: Good Friday matches in 0 of the next 100).

## 4. FIRST WORK - GENERATED FROM THE REGISTRY (A-9)

Regenerate any time with `python research/kalshi/store.py worklist`. Only OPEN and IN_PROGRESS items
can appear, so a completed item cannot show up as a live instruction - which the committed
`DROP_IN_S112` did twice.

- **G-11** (XS) Start accruing EIA weekly coal basin spot prices  [IRREVERSIBLE - value is permanently lost by waiting]
- **A-14** (XS) flow_calendar.CME_HOLIDAYS documents an early_close class and contains ZERO entries of it
- **G-1** (XS) Confirm what replaced the NGWU supply-demand balance (NOT a repoint - the feed already knows both eras)
- **G-14** (XS) Fix the LNE strike decode at source (Databento display_factor bug)
- **A-1** (S) Wire zero-change and seasonal-naive baselines into blind_score_nonpooled
- **A-12** (S) vol_regime.n0_prev_* is a PER-BLOCK CONSTANT - valid only on a block's first day
- **A-13** (S) SOP CHANGE PROPOSAL: serve DAY_CALENDAR (+CAL_FACTS) to BLD-1 and RFN-1 - only the AUDITOR gets calendar today
- **A-3** (S) Compute the effective matching dimension d of any retrieval
- **A-8** (S) Wire the depth-based turn_exhaustion as the monitor's CONFIRMING turn channel
- **A-9** (S) Generate the drop-in's work list FROM the registry instead of restating it in prose

## 5. TWO ITEMS NEED GREG'S CALL BEFORE THEY CAN BE BUILT

- **A-13** - `CAL_FACTS` reaches **AUD-1 only**, so no forecasting specialist has ever received
  calendar facts. That is the structural cause of NC-1. `day_calendar()` is built and tested;
  adding `{DAY_CALENDAR}` to BLD-1 and RFN-1 is a change-controlled SOP edit (D10).
- **A-11** - serving chain state (`cum_from_anchor` + chain age) would unblock nine plays at once.
  Four of eight conditions-curation batches hit this independently.

**KEYS DO NOT ROTATE DURING THE WALK.** git = code + records, S3 = data. No emojis.
