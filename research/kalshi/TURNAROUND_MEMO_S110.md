# TURNAROUND MEMO — S110 (the gas platform)

Ordered by Greg, S110: *"become Jack Welch... take your experience of turning GE and Chrysler from
having these types of problems into well oiled machines and do that with this."* Two-fold per his
spec: **Part 1 nuts-and-bolts** (component finds and fixes), **Part 2 the facility** (flow,
departments, one plant instead of pieces). Plus the **paper-trading go-plan**. Gas only.

The lens is candor. Everything below is stated as it is, not as the handoffs wished it.

---

## PART 0 — STATE OF THE BUSINESS, FACED AS IT IS

**What this company actually is today:** a *development shop* with a genuinely good product in
beta — the NG daily forecaster — and **no shipping dock in operation**. Twenty-three groups
walked. A six-role agent line whose rework station (the refine) reliably lands every day under
100 on named evidence. A blind that has improved from coin-flip-with-a-lean to second-best-on-the-
honest-metric while the instrument panel around it was being rebuilt mid-flight. Sixty-eight plays
of which **exactly two are STABLE**. A live data feed smoke-tested once, at 7.7 ms — a thousand
times inside the edge's 7–20 s window — and never turned on again. An execution-economics model
(fees, fills, lag shape) built in S100 and idle since. **Zero paper trades have ever been placed.**

**The disease, named and now quantified.** Twelve silent data holes in the last four sessions,
every one found by a person or agent *reading*, none by a gate that existed at the time. Ten of
the twenty-four decision-state blocks — cash_basis, grid_stack, nuclear_outages, options_surface,
solar, steo_vintage, storage_consensus, storage_regional, storage_vintage, weather_forecast_cycle
— have **zero codified consumers** in the brain: roughly 40% of the raw-material lines feed no
machine. When reading is voluntary, it measurably fails under load: on 0629 the wind subtractor
was served in every slice, moved 34x more than the nuclear adjustment both bridge agents made, and
nobody looked. The same pattern in procedure: fixes verified on one reader and dead on the other
(f2, today), solutions built and never wired (forward_stamps, the CDD ladder), decisions
re-litigated because the record of deciding them lived in a session instead of the machine.

**The Welch verdict:** the engineering is better than the organization. The product improves
every cycle; the *plant* loses parts between shifts. Fix the plant, and the product's improvement
rate compounds instead of leaking.

---

## PART 1 — NUTS AND BOLTS (the Iacocca walk-through)

Every component gets a disposition: **WIRE** (give it a consumer/guard and it earns its place),
**FIX** (defective, named repair), **PARK** (deliberately idle, stated why and when it returns),
**CLOSE** (stop carrying it). Effort: S = under an hour, M = a session-chunk, L = a full session+.

### 1.1 RECEIVING — the feeds (the zero-consumer table, dispositioned)

| block | state | disposition |
|---|---|---|
| `grid_stack` | live, sound, **0 plays** — and it explained 0629 mechanically | **WIRE (M)**: the renewable-subtractor play family (P0.7) + winter backfill G7–G13 (queued step ⑤) makes the residual testable in cold. Highest-value wire on the board. |
| `storage_consensus` | **FIX at source (M)**: post-print capture look-ahead (auditor f2, S109) destroys ~78% of decision-time surprise on affected prints; store died after 07-09 (f4, repaired-with-basis in state). Feed rerun needs the data plane. Until fixed, specialists' estimates[]-reconstruction workaround stands. |
| `options_surface` | strikes were 10x off **in every group carrying it** (fixed in the two live states S110; guard HARD) | **FIX at source (S, needs plane)** + **WIRE (M)**: it costs specialist budget today and pays nothing; either a pin/OI play consumes it or it gets PARKED out of the states. Decide after G23. |
| `cash_basis` | HH-only; the constraint limb of the weather multiplier (Chicago citygate) is exactly what it cannot see | **WIRE-later (L)**: the citygate basis stack is the one plausibly-paid item (P0 pt 4). PARK until the free items land; do not stage it silently meanwhile. |
| `nuclear_outages` | sound, 0 plays | **WIRE (S)**: fold into the gas-call stack arithmetic (it is already a subtractor term in `gas_call_residual.py`) so its consumer is the residual, then it rides P0.7. |
| `solar` (calendar) | sound, 0 plays; the duck-curve clock built on Greg's ask | **WIRE (S)** same route: it is the residual's clock. A feed whose consumer is another feed is fine — *a play must name the pair*. |
| `steo_vintage` / `storage_vintage` / `storage_regional` | sound, declared, 0 plays | **PARK-in-place (S)**: keep staging (cheap, audited clean), mark "context channels — no play yet" in the state note so the auditor stops re-proving them and specialists know they are background. Regional returns when the citygate/constraint work starts. |
| `weather_forecast_cycle` (sunday_reopen) | HDD-only until S109; CDD added; **0 plays** despite Friday/Monday being the declared focus | **WIRE (M)**: the weekend-add channel belongs inside whatever replaces `weekend_gap_delivery`'s summer arm (P3). If the gap is genuinely unforecastable (P3's boundary play), the WIRE is "cited as evidence," which still counts — a consumer is a reader, not necessarily a trigger. |
| `ngwu_balance` vessel line | WIRED_UNPROVEN (S109, Greg's call) — now has a consumer | Correctly dispositioned already. Hurricane season Aug–Oct is live: see 1.6 tropical. |
| `vol_regime` | v0 basis entirely null; n0 off the scored tape in the leg era (f3, declared S110) | **FIX at source (M, needs plane)**: rebuild the n0 store off the legs for the leg era, or re-point the magnitude scalers at leg-derived stats. Until then the n0_era_basis declaration carries it honestly. |
| `pyth` collectors (WTI/XAU/XAG) | free era ENDED 2026-07-31; not gas | **CLOSE (S)**: gas-only says retire the workflow on the trunk, archive the code path. One line in the ECO log. |

**The standing rule this table enforces (proposed as SOP doctrine):** *a feed enters the
decision state only with a named consumer — a play, a specialist directive line, or another feed
that reads it — or an explicit PARK note.* Served-but-unread was the enemy in four straight
sessions; this is the structural kill.

### 1.2 QUALITY CONTROL — gates and guards

- **What is now true (good):** every guard added since S108 is a RECONCILIATION against an
  independent quantity, not a presence check — the b_share identity, squeeze-vs-flow_calendar,
  and S110's four (phase-sum, consensus freshness, strike scale, n0 era). All negative-tested
  with published fire-counts. `verify_gold` walls the engine. The coordinator guard + Friday
  sign-off + archive-by-MOVE + `assert_not_the_blind` wall the line.
- **FIX — the f2 class (S):** adopt the rule that closed today's hole as SOP text: **no fix is
  done until a test proves the fixed path EXECUTES and the guard fires on the original defect.**
  S108's fix was verified on reader A, dead on reader B, and its gate watched the wrong reader
  for two groups. Also adopt: **when a fix touches one of N parallel readers of a quantity, the
  fix review must enumerate all N** (the copy-through list missing `session_b_share` was the same
  species, hole #9).
- **BUILD — incoming-inspection manifest (S):** `state_health` prints pass/fail; make it emit a
  per-group `inspection.json` (guard list + verdicts + versions) that travels with the state —
  the certificate the batch record (Part 2) staples in.
- **BUILD — the QC shift (M):** the Sonnet/Haiku conformance checklist (Greg's order, task open):
  every item a command + expected output + stop-and-report. Spec in Part 2.4.

### 1.3 THE LINE — machinery defects and half-builds

- **Two schema dialects (FIX, S):** the blind coordinator reads `guessed_net_usd`, the refine
  coordinator reads `expected_magnitude_usd`. Same quantity, two names, one more filename-collision
  class waiting. Unify on the shared-file contract with a compatibility read.
- **Brain status taxonomy drift (FIX, S):** 68 plays carry ten different free-text statuses
  including one 40-word sentence. Normalize to the enum {HYPOTHESIS, PROPOSED, PROVISIONAL,
  STABLE, RETIRED, WIRED_UNPROVEN} + a `status_note`. Only 2 of 68 are STABLE — see 1.4.
- **G21 round 2 (DECIDE):** open since S109. Either run it for the r2 comparability row or CLOSE
  it explicitly (the r1 result stands on its own). Costs a session-chunk; the walk does not block
  on it. Recommend: CLOSE unless a specific r2 question needs it.
- **Live orchestrator (CLOSE):** the S105 escalation clause ("if a fixed sequence still causes
  issues, build a live orchestrator"). The sequenced spawn has now run five groups without an
  ordering failure. Strike it from the open list; the clause self-reactivates if waves misbehave.
- **`AGENT_RUNBOOK_S95.md` (CLOSE, S):** superseded by `agents/RUN_SOP.md` v1.1; mark it
  historical at the top so no future session follows the S95-era skeletons.

### 1.4 THE BRAIN — product engineering

- **No promotion/demotion cadence exists.** 46 PROVISIONAL plays accumulate forward evidence
  nobody schedules a review of. **BUILD (S):** a promotion review rides every group close-out —
  any play with n>=3 forward confirmations across >=2 groups is a promotion candidate on Greg's
  go; any play refuted in its own scope twice is a retirement candidate. The scoreboard exists in
  the posteriors; this is bookkeeping, not research.
- **Named build gaps that block play families (carried from S109, all free):** CDD-vs-normal (the
  anomaly instrument that separates hill from spike), forecast surprise + persistence, seasonal
  station weights + the Ohio/Baltimore holes, coal headroom (EIA-860M + ISO outage aggregates).
  These are the SLOPE channel's missing limbs and they gate the weather play family P0 proposes.
- **The tropical gap is LIVE RISK (BUILD, M, free):** Aug–Oct hurricane season with zero tropical
  feed, in the season where the Gulf carries both the liquefaction fleet and production. NHC
  outlooks are free and structured. `freeze_risk` is the winter twin — same shape, other season.

### 1.5 DATA PLANE, KEYS, RUNWAY

- **The staged runway ENDS at G23** (the year store closes ~07-20; G23's anchor basis says it is
  the last fully-staged block). After G23 the walk needs either a year-pull extension (paid,
  Databento historical) or it hands the baton to the LIVE feed — which is the paper-trading
  decision arriving on its own schedule. **DECIDE at G23 close.**
- **Keys:** rotation stays deferred during the walk (standing, not re-raised). The key INVENTORY
  is now one undocumented file (`scratchpad/aws.env`: AWS pair + Databento + EIA). **BUILD (S):**
  a `KEYS.md` inventory — name, holder, where it lives, what breaks without it, rotation state —
  no secrets in it, ever. Paper trading adds two new entries (Kalshi demo, Kalshi prod) that do
  not exist yet anywhere.
- **CL free-redecode window closes ~Aug 12–14** (parked non-gas item, FYI deadline only, per the
  gas-only scope. One decision line from Greg kills or keeps it before the window shuts.)

### 1.6 SHIPPING — the paper-trading chain, audited component by component

| component | state | gap |
|---|---|---|
| live market data | **PROVEN** — Bento Live Standard subscribed (S99, $179/mo); smoke 7.7 ms median (S100) | runs ONLY from an AWS box (container cannot reach port 13000 — structural); the live collector family (`ng_live_collector/operator/watchdog`, S101-02) is built for systemd and has never run as a service |
| settlement truth | **PROVEN** — KXNATGASD settlement verified from spec (S99): per-contract NGD 1-min close 17:00 ET, 5bd forward roll; Kalshi's own `expiration_value` = the settle print, free | none — this is done and documented |
| execution economics | **BUILT, idle** — `kalshi_fill_model.py` (fees verified vs published schedule), `lag_execution_map.py` (bracket response map on the KXNATGASD life) | never connected to a decision source |
| the decision source | **THE PRODUCT** — the brain + the live blind (the S106 finding stands: most of the refine's gain is available to the blind via the handoff) | no LIVE daily loop exists: state build -> forecast -> order intent has only ever run as the walk |
| order placement | **DOES NOT EXIST** | no Kalshi trading-API client, no demo account/keys, no order/position/P&L ledger, no risk caps |
| monitoring | **DOES NOT EXIST** as a service | watchdog exists for the collector only; no andon for the loop |

**The honest summary: five of six links exist; the one that has never existed is the actual
dock — account, order client, ledger, caps. That is one focused build.**

---

## PART 2 — THE FACILITY (the Welch org chart)

### 2.1 The plant map — departments, named

```
RECEIVING            feeds/collectors (EIA, NWS/MOS, CFTC, Bento, Kalshi public, calendars)
INCOMING QC          state_health reconciliations + tape_reconcile   [certificate: inspection.json - to build]
STAGING              stage_group -> grp state + anchor + evidence + exit states + causal slices
PRE-LINE QC          THE STATE AUDITOR (canonical 6th role, runs before every blind)
PRODUCTION           the blind - waves C/D/E -> A -> B on per-day slices
IN-PROCESS QC        coordinator guard + Friday sign-off + verify_gold + merge_perday owner guard
SCORING              blind_score_nonpooled (per-day, sum|err|, drift, survival - never a mean alone)
REWORK               the refine, rounds 1-2 (HE24->HE1) - same engine, price visible
RELEASE AUTHORITY    Greg - merge gate (proposal + adjudication, incumbents byte-identical)
WAREHOUSE            git = code/states/posteriors; S3 = raw tape/stores
SHIPPING             paper -> live trading  [the dock: not yet built - Part 3]
MAINTENANCE          session_bootstrap, restore_substrate, key handling, collector workflows
QA LAB               the auditor role + the conformance checklist (the recurring QC shift - to build)
DOCUMENT CONTROL     RUN_SOP v1.1 (change control) + the DECISION LEDGER (to build) + ECO log
```

### 2.2 The seams — where the plant is still "different pieces"

1. **The shift change (the session boundary) — the #1 seam.** Keys, data/, scratchpad, and every
   uncommitted thought die at the boundary; the S109 auditor wrapper died there; solutions decided
   in-session rot there. The SOP fixed *procedure*. What still leaks is *state*: *what happened,
   what was decided, what is mid-flight.* **Fix = the BATCH RECORD** (2.3) + the DECISION LEDGER
   (2.5). A factory does not re-learn the plant at every shift change; it reads the traveler on
   the pallet.
2. **Two buildings.** The walk lives on this branch; the durable collectors auto-push to the old
   trunk (`claude/kalshi-s79-kickoff-ij8t9o`); live-feed work runs only on AWS boxes; the
   container cannot reach live gateways. Nobody holds one map of WHAT RUNS WHERE. **Fix (S):** a
   one-page `PLANT_MAP.md` — every standing process, its host, its branch, its trigger, its
   heartbeat. The andon board (2.4) then reads it.
3. **QA has no schedule.** The auditor runs per group (now in SOP). The *platform* audit (this
   memo) happened because Greg ordered it. **Fix:** the conformance checklist runs per session
   (cheap model); a full platform audit recurs on a stated cadence (every N groups / monthly),
   in the SOP, so drift is caught by rhythm rather than by pain.
4. **Knowledge transfer is prose-heavy.** The handoff/kickoff/CLAUDE.md system works but is
   long-form; the failure mode it feeds is "a cheaper model silently half-ignores" (already named
   in CLAUDE.md). The batch record + decision ledger move the load-bearing facts into small
   structured files a checklist can VERIFY rather than trust.

### 2.3 THE BATCH RECORD (build, S-M) — the traveler on the pallet

One JSON per group, `forecasts/g<N>_batch_record.json`, appended at each station: staging
(inputs, spec versions: SOP vX, brain sX, state sha), inspection verdicts, audit findings +
adjudications, blind runs (who/when/model), coordination, scores, refine rounds, merge decisions,
nonconformances. The close-out diff then has a machine-readable base, and "which spec version made
this number" has a one-line answer forever. This is lot traceability — the thing Toyota and Coke
both refuse to run without.

### 2.4 THE ANDON BOARD + QC SHIFT (build, M) — Greg's checklist order, specified

`plant_status.py` — one command, no arguments, prints: branch/tip vs expected; gold vault verdict;
per-group line position (staged / audited / blind / scored / refined / merged) off the batch
records; state_health verdicts for live groups; canonical-name occupancy vs blind archives;
uncommitted-file count; standing-process heartbeats where visible. **The conformance checklist**
(`agents/QC_CHECKLIST.md`) is the small-model wrapper around it: run the command, compare each
line to the expected block, report PASS/FAIL per line, **never fix anything** — report-only,
andon-cord authority, zero judgment items. Sonnet/Haiku-runnable by construction because every
item is command + expected-output + stop rule.

### 2.5 THE DECISION LEDGER (build, S) — the relitigation killer

`DECISIONS.md`, append-only, one line per binding decision: date/session, the decision verbatim,
status (**DECIDED / BUILT / WIRED / VERIFIED / RETIRED**), and what enforces it (guard, SOP
section, or "doc-only" — the dangerous class). Seed it from the standing corpus: keys-do-not-
rotate; blind-mask-is-price-only; causality-is-physics; never-average-above-below; one-group-at-
a-time; refined-never-overrides-blind; the S108 collision fix (VERIFIED); the S109 wrapper gap
(closed by SOP v1); f2's fix rule. The conformance sweep reads the ledger and flags any
DECIDED-but-doc-only item older than two sessions — **that is the exact organism that kept
biting: decided, dropped, relitigated.**

### 2.6 Synergy — the same calculation seen from opposite sides

Part 1's wires are not independent: grid_stack + solar + nuclear_outages all terminate in ONE
machine (`gas_call_residual` — the stack: weather load minus renewables minus absorbable), and its
missing winter arm is step ⑤'s backfill. The weather build gaps (anomaly, persistence, seasonal
weights) all feed ONE channel (the slope instrument P0 made top priority). The plant lesson:
wire DEPARTMENTS to each other, not fields to plays one at a time — the residual is Receiving's
first *assembled sub-component* rather than four raw materials sold separately.

---

## PART 3 — PAPER TRADING GO-PLAN (NG / KXNATGASD only, ranked)

**The one human-gated item is the account.** Everything else is code we largely already have.

| # | item | owner | effort | detail |
|---|---|---|---|---|
| **G0** | **Kalshi demo/paper account + trading API keys** | **Greg** | account signup + key issue | The only link that has never existed. Kalshi's demo environment (separate keys from prod) is the target; verify current demo availability at signup. Keys go in the (new) KEYS.md inventory, values outside the repo, per standing key discipline. |
| G1 | The PAPER LEDGER | me | 1 session | Order intents, simulated fills via `kalshi_fill_model` (taker fee formula already verified), positions, realized/unrealized P&L net-of-fee, per-event log (never pooled), daily settle against `expiration_value`. Pure code, no external dependency, can be built BEFORE G0 and run against recorded quotes. |
| G2 | The LIVE DAILY LOOP skeleton | me + the box | 1 session | On the AWS box (container cannot reach gateways): morning state build -> the live blind forecast (same engine, SOP-templated) -> order intents with RISK CAPS (max contracts/day, max loss/day, no averaging in) -> paper fills -> EOD score. The two-coach doctrine: this is the Kalshi daily coach, shadow mode. |
| G3 | Collector-as-a-service | me + the box | half session | `ng_live_collector` + `ng_live_watchdog` under systemd timers as designed (S101-02, never yet run as a service); health.json feeds the andon board. |
| G4 | Monitoring + QC shift | me | rides 2.4 | plant_status + checklist covers the loop; add the loop's heartbeat line. |
| G5 | Key rotation | Greg + me | post-walk, standing | Unchanged decision: after the walk. Paper trading with demo keys does not require it; LIVE money does. |
| G6 | Walk/live sequencing | Greg | decision | The staged runway ends at G23. Recommendation: finish G22 refine -> G23 (the walk's last staged block) while G0-G3 build in parallel; paper trading starts the week G23 closes, so the shop never idles and the walk's last lessons ride into the first paper week. |

**What paper trading is for (stated so the scoreboard is honest from day one):** it tests the
DOCK, not the edge — fills, latency, the loop's plumbing, the fee model against reality, the
cadence. The edge's forward test is the walk's job and then the live-shadow ledger's. Per-event
always; the first pooled "paper Sharpe" anyone computes gets thrown out by standing rule.

---

## THE ASK (decisions, smallest set)

1. **Part 1 dispositions** — the table stands as written? Flag any WIRE/PARK/CLOSE you want
   flipped (the two loudest: retire pyth collectors; close the live-orchestrator open item).
2. **Part 2 builds** — batch record, andon+checklist, decision ledger, PLANT_MAP: build order as
   listed? (All S/M; I sequence them into session gaps, none block the walk.)
3. **G0** — provision the Kalshi demo account/keys when ready; everything else in Part 3 I can
   stage without it.
4. **G6** — bless the parallel track (walk finishes G22/G23 while the dock builds), or serialize.
