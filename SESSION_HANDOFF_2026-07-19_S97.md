# SESSION HANDOFF - S97 (work date 2026-07-19) - G11 blind + refine (brain s100.2), MOS forecast temps, net-of-fee replay, the series-construction finding, and a HARD DATA GATE before G12

Branch: pushed to `claude/ng-coach-continuous-curve-7pk2gf` (S97 tip `d7ed89cd`). Reset the new session
branch onto it. git = CODE + committed renders/records; S3 = the tape; `scratchpad/aws.env` = keys
(gitignored; AWS pair + DATABENTO key both live and verified this session).

---

## THE GATE (Greg, S97, load-bearing - READ THIS FIRST)

**NO NEW GROUP RUNS UNTIL EVERY DATA INPUT BELOW IS BUILT AND WIRED.** Greg stopped the walk mid-session
specifically to close the data gaps first. G12 does not start until this list is done. The full list is in
"THE DATA GATE" section below - it is the primary deliverable of the next session.

Rationale in Greg's words, and it governs how every one of these is built: **we are not here to test
theses. We put what we believe is relevant information in front of the agent and IT decides how to use
it.** Do not gate an input on whether it "worked", do not score it for keep/drop, do not remove or
quarantine one that looks inert. Characterize per-instance where conditions discriminate ("works on {X},
not on {Y}") and leave the data in place.

---

## SESSION TOTAL

- **G11 (Sun Jan 18 - Fri Jan 30 2026, two contiguous weeks) one-shot blind on s99.2: direction 6/12,
  close-cum -500 guess vs +12,690 actual, drift -13,190.** Anchor 2.702 -> 4.416 (+17,140 incl gaps).
  **THIRD consecutive block-lean miss** (G9, G10, G11). The blind held the post-parabolic down-chain
  intact; the market reversed into a 63% rally. Blinded merge -> s100.1.
- **The G11 refine -> s100.2 (23 plays): direction 10/12, drift -3,890.** The two remaining misses (0127,
  0128) are the declared-irreducible cresting-ramp pause pair.
- **THE FLIP RULE IS KEPT.** Per-instance from the tape: **C1 (band-break) fires 1008, 1020, 1208, 1223
  and 0120, and correctly declines 0107 - five fires, one correct decline, ZERO false positives.** The
  blind missed the flip because **it never evaluated 0120, the actual flip day** - it checked 0119, 0122
  and 0129, and measured 0119 against the day-1 band. **C2 (continuation-collapse) works on low-activity
  tapes and not on high-activity ones**, and the mechanism is a SCALE ARTIFACT, not a conceptual flaw:
  every calibration instance carries 15-98 legs on 15-25k trades, while G11's sessions carry 160-550 legs
  on 75-125k trades, so an absolute `<=15% of legs` threshold is MECHANICALLY UNREACHABLE at that scale.
  C3 forward-confirmed; C4 forward-confirmed twice; the termination-vs-birth split survives G11 intact.
- **NEW PLAYS:** `magnitude.weekend_gap_delivery` (gap magnitude conditioned on whether the weekend model
  cycle DELIVERS a change: fresh shot +1500..+2500, priced shot +200..+400) and
  `signal.mos_first_appearance_vs_revision` (the MOS run-delta discriminates on FIRST-APPEARANCE adds,
  not on revisions to an already-priced shot).
- **BRAIN ARCHITECTURE (Greg's call):** every play now carries `requires` / `scope` / `forward_evidence`.
  **Refined rules NEVER override blind-applicable ones.** They are hindsight-fitted with zero forward
  evidence, so overriding would promote in-sample fits into the operating playbook untested and
  invisibly - and it would destroy the blind-vs-refined GAP, which is itself the measurement of how much
  of the edge is sequential (G7 3/10 blind vs 9/10 refined; R2 4/10 blind vs 10/10 refined). Promotion to
  blind-applicable is gated on forward evidence. Precedence stays SCOPE-based.
- **MOS forecast temps BUILT and in use.** `nws_temp_feed.py --mos-asof`, IEM NWS MOS archive,
  gas-weighted forecast HDD/CDD as-of D-1 evening for the 16 demand metros + `forecast_vs_normal` +
  the RUN-TO-RUN DELTA. 91/91 days complete Nov 2025 - Jan 2026, blind wall audited **0 violations across
  11,648 run stamps**, D+0 vs realized corr 0.9974. Additive - the realized-proxy block is untouched.
- **NET-OF-FEE REPLAY (`COACH_REPLAY_S97.md`): fees are NOT the binding constraint on this vehicle,
  DIRECTION is.** Zero of 51 events had the taker fee flip their sign. The S81/S82 size-vs-fee problem is
  a Kalshi problem and does not transfer to the NYMEX leg. Blind taker by block: G7 -1,910, G8 +5,700,
  G9 +14,400, G10 -2,425 - two of four lose. **G9's total is SIX NAMED EVENTS** (1211, 1223, 1209, 1231,
  1218, 1208); the other fourteen sum to -3,220. G9 was logged as a block-lean MISS yet is the best blind
  day-book - **the daily trade never carries the lean; they are two different edges.**
- **SERIES CONSTRUCTION FINDING** (`PASS2_CONTINUOUS_SERIES_NOTES.md`, deferred to pass 2 by Greg).

---

## THE SERIES-CONSTRUCTION FINDING (deferred to pass 2, do NOT re-base the walk yet)

`NG.v.0` picks the front month by THAT DAY's volume. Across the G11 expiry week it whipsawed
1000 <-> 1021 three times (-1.541, +1.420, -1.465) because the expiring FEBRUARY contract went parabolic
into delivery (3.0 -> 5.4), repeatedly pulling volume back to the dying contract. **G3-G10 each rolled
ONE-WAY and are clean** - the brain's narrative built on them stands. G11 was re-pulled on **`NG.n.0`
(OI-continuous, instrument 1021 throughout, no intra-block roll)**.

`NG.n.0` is NOT monotonic either: thin ~350-trade Sunday sessions can re-decide the front month
(20251109 flipped and 20251110 flipped back). Full detail, including the weekend-gap-as-spread-artifact
hypothesis and the pass-2 task list, is in `research/kalshi/PASS2_CONTINUOUS_SERIES_NOTES.md`.

Note the price BASIS differs between G11 and G3-G10. Absolute levels are not comparable across that
boundary; dollar magnitudes and structure are.

---

## THE DATA GATE - EVERYTHING TO BUILD BEFORE G12

Greg: do all of these before the next run. Cost is not a concern for data we need; Databento is
authorized. Each lands as a STANDALONE module exposing `*_asof(date) -> dict | None`, because
`decision_state` must be wired in ONE serial pass (see JOB 0).

### Launched in S97 - verify these landed, finish any that did not
1. **CFTC COT positioning** -> `research/kalshi/cot_feed.py`, `data/cot/`.
   Disaggregated report, NYMEX Henry Hub. managed_money long/short/net, producer_merchant_net,
   swap_dealer_net, other_reportable_net, total OI, w/w change in managed_money_net, and the net as a
   percentile of its trailing 1-yr and 3-yr range. **BLIND WALL: COT reports TUESDAY positions but
   publishes FRIDAY 15:30 ET - joins MUST key on PUBLICATION time, or three days of future positioning
   leak into every Wednesday and Thursday.**
   Why: the agent has no view of crowding. A heavily-short market meeting a bullish catalyst is the
   standard setup for a violent upside reversal - which is what G11 was.
2. **EIA storage regional + SALT/NON-SALT** -> `research/kalshi/storage_regional.py`,
   `data/storage_regional/`. Five regions (East, Midwest, South Central, Mountain, Pacific); South
   Central split SALT vs NON-SALT; per region level, weekly change, vs 5-yr, vs year-ago; days-of-supply
   if EIA publishes one. Additive - the national `storage` fields stay. Blind wall: Thursday 10:30 ET,
   strictly prior (match the S96 fix).
   Why: salt-dome storage is the fast-cycling swing capacity and moves short-dated prices far more than
   the national total. We feed one aggregate where the market watches five, and salt hardest.
3. **Contract structure + forward curve** -> `research/kalshi/contract_structure.py`,
   `data/contract_structure/`, plus `forward_curve.py` regenerated.
   `days_to_front_expiry` (authoritative from Databento `definition` if available, else the 3-business-
   days-before-delivery-month rule); `front_next_spread` plus its 1/3/5-day CHANGE (the rate of widening
   is the tell, more than the level); `open_interest` front and next + d/d change (Databento
   `statistics`); `oi_volume_divergence` (do NG.n.0 and NG.v.0 point at different instruments that day);
   `curve_regime` regenerated so it stops reading `'unknown'`, **including the March/April spread** (the
   most-watched structural spread in NG, end of withdrawal season).
   Why: this is the missing variable the refine named as the mechanism behind G11's largest day (0130,
   +5,020). The squeeze was fully visible in the Feb/Mar spread (-0.41 on Jan 16 -> -1.54 by Jan 22) and
   the agent could not see it.

### Not started - build these next session
4. **MOS CYCLE TIMING FIX (the refine found this; it is a genuine defect).** Our MOS feed is as-of D-1
   evening, but the SUNDAY REOPEN is priced by a LATER model cycle - the Jan-24 +8.511 add first appears
   in our data about an HOUR AFTER the gap that priced it. Sunday reopens are exactly where the
   weekend-gap magnitude keeps getting missed. Needs the cycle actually available before the reopen,
   with the blind wall re-audited.
5. **Vol / range regime** - realized vol, ATR, range percentile, volume trend, computed from tape already
   on disk. Free. The brain's magnitude bands keep getting overshot (1119, 1128, 1211, 1223, 0130) and a
   vol-regime conditioner is the obvious missing variable.
6. **G11 fingerprints on `.n.0`** (`characterize_turns.py`) - **BLOCKS the C2 ratio reformulation**, which
   is the flip-rule fix. Without it the four-condition confirm cannot complete on modern high-activity
   tapes, and a G12 blind would inherit G11's exact failure mode.
7. **Model disagreement (GFS-MAV vs NAM-MET) as a forecast-uncertainty proxy.** Both are already pulled.
   The market prices uncertainty, not just the central case. NOTE: ingest existing model output only -
   the weather FORECASTER is Greg's spec, HANDS OFF.
8. **LNG feedgas demand.** Structurally one of the biggest modern NG drivers (a Freeport-class outage
   reprices the curve for months). HONEST STATUS: daily pipeline nomination data is paid
   (Genscape / Wood Mackenzie); EIA publishes monthly, which is too slow. **Probably NOT obtainable on
   current sources.** Do not fake a proxy - report the gap.
9. **Options: IV, skew, gamma positioning.** Options expire the DAY BEFORE futures expiry, driving
   pinning and squeeze mechanics - plausibly part of what drove G11's February. Available on GLBX,
   substantial build. Greg's standing note has the NYMEX-options survey queued as the eventual real
   trading vehicle, so this may fold into that.
10. **Cross-market**: power prices (gas sets marginal power price), coal-switching economics, TTF/JKM
    (LNG arb pulls US cargoes). Real drivers, slower-moving. Lowest priority of the list.

### Also required before G12
11. **The C2 ratio reformulation** (needs item 6). The refine flagged the fix direction - a ratio
    (old/new) rather than an absolute share-of-legs threshold, which separated 0.00-0.42 true vs 1.23
    false on fingerprint-comparable data. **That number is a FLAGGED BUILD GAP, not a fitted threshold** -
    derive it properly, do not adopt it as-is.

---

## JOB ORDER FOR S98

**JOB 0 - WIRE `decision_state`, SERIALLY, ONE HAND.** Every feed above lands as a standalone module
precisely so this is one collision-free pass. All new fields ADDITIVE - never replace or rename existing
ones. MISSING IS EXPLICIT, NEVER ZERO (a zeroed HDD in January, a zeroed storage level, or a zeroed
front/next spread during a squeeze are each catastrophic false signals). Re-audit the blind wall across
ALL joins afterward. `forecast_harness.py --selftest` must PASS.

**JOB 1 - finish the data gate** (items 4-11 above).

**JOB 2 - G12** (Sun Feb 1 - Fri Feb 13 2026) on the merged brain, one-shot blind, with the full input
set. Clean block, no expiry.

**JOB 3 - G13** (Sun Feb 15 - Fri Feb 27 2026). **Contains the Feb 25 2026 front-month expiry - this is
the SQUEEZE TEST.** Because `.n.0` rolls out of the dying contract early, G13 will NOT contain a price
spike even if the expiring contract squeezes hard; the agent's only view of the event is the front/next
spread blowing out and the expiry clock running down. A miss there means something different than a
directional miss does.

**JOB 4 - pass 2** on the series construction (`PASS2_CONTINUOUS_SERIES_NOTES.md`) once the first pass
over the historical data is complete. Greg: do not re-base the walk before then.

---

## CONCERNS / OPEN RISKS CARRIED INTO S98

Ordered by how much damage they do if ignored. None of these are blockers on their own; several are
things that would quietly corrupt results rather than fail loudly, which is why they are written down.

**1. REVISION VINTAGE - a residual look-ahead the blind wall does NOT catch.** The new regional storage
feed carries EIA's LATEST REVISED estimates. The blind wall governs WHEN a report becomes visible, not
WHICH VINTAGE - so an old week's level may differ from what actually printed that Thursday, and the agent
sees a number nobody had at the time. **This very likely also affects the EXISTING national `storage`
field and `eia_surprise.py`**, which would mean the whole walk has carried a small revision-vintage
look-ahead. Gas storage revisions are typically a few Bcf so the effect is probably small - but "probably
small" is not measured, and this is exactly the class of thing the leakage gate exists to catch. ASSESS
before leaning on storage for magnitude work. Point-in-time vintages need EIA's separate revision archive.

**2. STORAGE SOURCE UNVERIFIED.** DEMO_KEY hit its shared global quota mid-build, so the store came from
EIA's `ir.eia.gov/ngs/ngshistory.xls` workbook, not the API. Row counts and date ranges match for the two
series fetched before the quota died; VALUES were never cross-checked. **Re-run `--source api` with a
REAL EIA key.** DEMO_KEY is shared globally and will keep doing this - get a real key.

**3. THE C2 RATIO REFORMULATION BLOCKS G12.** Until G11 fingerprints exist on `.n.0` (gate item 6) and C2
is rebuilt as a ratio (item 11), the four-condition flip confirm CANNOT COMPLETE on modern high-activity
tapes. A G12 blind run before that fix inherits G11's exact failure mode for the same mechanical reason.
Do not run G12 first and hope.

**4. THE BLOCK LEAN IS THE WEAKEST PART OF THE SYSTEM - three consecutive misses (G9, G10, G11).** All
three were chain-polarity calls, and the rule has now failed in BOTH directions: fired falsely (G10),
then failed to fire (G11). The per-instance refine shows C1 is clean and C2 is mechanically broken, which
explains G11 - but that is one block's explanation, not a demonstration that the lean is fixed.

**5. THE BLOCK LEAN AND THE DAY-BOOK ARE TWO DIFFERENT EDGES, and we have not decided which we trade.**
The net-of-fee replay found G9 was logged as a block-lean MISS yet produced the best blind day-book
(+14,400 taker). The daily trade never carries the lean. This is unresolved and it matters for what the
coach is actually FOR.

**6. G11 IS NOT A PRISTINE HOLDOUT.** The orchestrator saw the block's price path before the blind agent
was spawned (the roll check requires loading tape). The subagent was genuinely blind; the price-basis
choice was not. Protocol fix is recorded for G12 - a subagent runs the roll check and returns only date
and spread.

**7. `NG.n.0` IS NOT MONOTONIC EITHER.** Thin ~350-trade Sunday sessions can re-decide the front month
(20251109 flipped, 20251110 flipped back). G11's window happens to be clean, but the general problem is
NOT solved - see `PASS2_CONTINUOUS_SERIES_NOTES.md`. Also: the PRICE BASIS differs between G11 (`.n.0`)
and G3-G10 (`.v.0`), so absolute levels are not comparable across that boundary. Dollar magnitudes and
structure are.

**8. MOS CYCLE TIMING is a real defect, not a nice-to-have** (gate item 4). The Sunday reopen is priced
by a LATER model cycle than our D-1 evening feed - the refine found the Jan-24 +8.511 add first appears
in our data about an hour AFTER the gap that priced it. Sunday reopens are precisely where the
weekend-gap magnitude keeps getting missed (+2,100 and +2,480 in G11, +2,770 at G7's 1020).

**9. COT LIMITS worth carrying:** futures-only, not futures-and-options-combined (options positioning is
a separate picture); NYMEX contract 023651 only, so it does NOT capture ICE Henry Hub positioning, which
is large; publication times are date-plus-15:30-ET, not observed timestamps; 12 dates in Jan-Mar 2019
flagged `derived_unreliable` (outside the coverage window, affects percentile history only).

**10. TAPE IS ON LOCAL DISK ONLY.** `data/nymex_cont_n0/` and `data/nymex_cont_n1/` (Nov 2025 - Feb 2026)
are gitignored and NOT on S3. The standing rule is git = CODE, S3 = DATA - right now this data exists in
exactly one place. Push it to S3.

**11. KEYS WERE EXPOSED IN-CHAT THIS SESSION** (AWS pair via screenshot, Databento key as text). ROTATE
both before the next session, same as the S96 pair.

**12. VERIFY WHAT THE LAST BUILD LANDED.** The contract-structure + forward-curve agent was still running
at session close. Check `research/kalshi/contract_structure.py`, `data/contract_structure/`, and the
modified `forward_curve.py` before wiring, and confirm `curve_regime` actually stops reading `'unknown'`.

---

## PROTOCOL

Unchanged and settled: one-shot block-blind is the canonical skill test; refine after EVERY group
(iterate-to-tracking, GENERAL rules only, n>=2 spanning groups, uniform application, irreducibles
declared); renders PRINTED to Greg before each refine merge; lessons merged BEFORE the next group;
**blocks run SUNDAY reopen -> FRIDAY close of the SECOND week (two contiguous weeks)**.

**NEW protocol fix (from S97, apply at G12):** the roll check cannot be run by the orchestrator without
loading tape and therefore SEEING the block's price path. **A SUBAGENT must run the roll check and return
ONLY the roll date and spread - never prices.**

**S97 CAVEAT ON RECORD:** the orchestrator saw G11's price path before the blind agent was spawned (the
kickoff ordered `roll_offsets` first). The forecast subagent was genuinely blind and its prompt carried no
outcome information, but the price-basis choice (`.n.0`) was made with outcome knowledge, on the stated
principled ground that it was the single-contract series for that window. G11 is therefore not a pristine
holdout.

---

## STATE

- Brain `research/kalshi/knowledge/ng_brain.json` = **s100.2, 23 plays**. Backups:
  `ng_brain_s99.2_backup.json`, `ng_brain_s100.1_backup.json`; proposal kept as
  `ng_brain_s100.2_proposal.json`.
- Forecast record: `forecasts/grp11.json` (blind + refined fields per day, with per-day reasoning).
- Renders (committed): `g11_blind.png`, `g11_refined.png`, `g11_score.json`, `grp11_state.json`.
- `COACH_REPLAY_S97.md` (net-of-fee), `PASS2_CONTINUOUS_SERIES_NOTES.md`.
- MOS: `weather/mos_asof/` (index + normals committed; `raw/` ~50 MB gitignored),
  `SCHEMA_MOS_ASOF.md`.
- Tape on disk (gitignored, NOT in git): `data/nymex_cont_n0/` (front, Nov 2025 - Feb 2026),
  `data/nymex_cont_n1/` (next, same range). Consider pushing both to S3 - git = CODE, S3 = DATA.
- Databento spend this session: ~$1.22 plus the contract-structure agent's pulls.

## RULES (unchanged)

PER-EVENT, never pool/average as a conclusion; drift is a DESCRIPTOR; general rules only, no
point-fitting; blind wall (decision-time only, storage strictly-prior, MOS as-of); one-shot canonical;
refine per group with renders printed first; Sunday-start / Friday-end two-week blocks; net-of-fee maker
AND taker; git = CODE, S3 = DATA; flag weekday holidays (thin AMPLIFIES delivery, DAMPS holds); rolls
marked, never traded; flips: four-condition confirm, NEVER front-run a flip; NG != WTI; weather
forecaster HANDS OFF; provisional-until-live; keys are SECRETS; no emojis.
