# RUN_SOP.md — THE SPEC BOOK for the NG forecaster group cycle

**v1, S110. BINDING (Greg, S110):** *"we need a repeatable standard that travels from one session to
the next... there should be a sop or spec book that is followed for these steps every time. no
guessing or ad libbing. just follow the guide doc."*

**THE RULE:** every recurring step below is executed EXACTLY as written here — same commands, same
spawn templates, same pause points — with only the SLOT VALUES changing per group. Slot values are
LOOKUPS (from `group_config.py`, committed artifacts, or the calendar feeds), never judgment calls.
If a step needs to change, the change is an EDIT TO THIS FILE, proposed in-session, adopted on
Greg's go, version-logged below — never an in-session improvisation. If reality and this file
disagree, STOP and say so; do not quietly adapt.

## CHANGE CONTROL — NOTHING RUNS OFF-SOP (Greg, S110, the factory standard)
*"Nothing is done in those places, and I mean nothing, without documentation and buy-in from
everyone. There's no changing things just because, there's no missed policies or SOPs that get
skipped or made up on the fly."*

1. **NO OFF-SOP EXECUTION.** If a needed step is not covered here, or a covered step cannot run as
   written, the line STOPS at that station. Report the gap. Do not compose a procedure and run it.
2. **THE CHANGE LOOP (the only way this file changes):** write the proposed edit as a concrete
   diff to this file, with WHY → Greg's explicit go is the buy-in → version-log entry (what, why,
   session, first group run under it) → only then execute. The specs of the machine may change as
   we go; the change is always logged and the process backbone stays the same.
3. **DEVIATIONS ARE NONCONFORMANCES.** A run that accidentally departed from this file is recorded
   as such in the group's record and the session handoff — never silently absorbed. Whether its
   output stands is Greg's call at the next pause.
5. **NOTHING THE NEXT SESSION MUST RUN MAY LIVE OUTSIDE GIT.** Greg, S111: *"fix in whatever doc
   you need to that things don't go on scratchpads anymore. this was in the audit file!"* A path
   under `~/.claude/projects/`, `workflows/scripts/`, `AppData/Local/Temp` or `/tmp` is SESSION
   SCRATCHPAD - it does not exist on a fresh container and it dies with the session. A handoff that
   names a file nobody else can open is a broken handoff. **INSTANCE (NC-2):** the S111 drop-in
   pointed S112 at an audit harness under `~/.claude/projects/.../workflows/scripts/`; S112 ran
   `git ls-files` against it, got ZERO, and had to re-author the harness. Written in the same
   session that diagnosed this exact disease as A-7. **ENFORCED, not asserted:** `plant_status.py`
   scans the newest drop-in, the newest handoff and this file for scratchpad markers and for
   referenced repo paths that are not `git ls-files`-tracked, and **FAILS** on either - which stops
   the line, since a FAIL row exits non-zero. Negative-tested by reintroducing NC-2 verbatim.

4. **GATES CANNOT BE SKIPPED OR SOFTENED.** A failing gate stops the line (jidoka). Routing around
   a gate, weakening a guard to pass, or "just this once" does not exist here.

6. **THERE IS NOTHING LOCAL - AND NO ARTIFACT MAY NAME A DESKTOP PATH (D34).** Greg, S112:
   *"all of this stuff is going to live in aws or git so there should be no paths from my
   desktop"*, *"there should be nothing local"*, *"right now everything gets pushed to git.
   zero to e drive."* The split is the whole rule: **git = code and records, S3 = data, `data/`
   is disposable** and rebuilt by `restore_substrate.py`. Item 5 governs what the next session
   must RUN; this item governs every path any artifact NAMES - citations, evidence lists,
   handoffs, ledgers, decision lines. **INSTANCE:** `BRAIN_AUDIT_PARTIAL_S111.json` carries 140
   instances and **51 of them, across 11 plays, cite `E:/Markets/research/kalshi/...`**. The
   files are real and committed; the citations open on exactly one machine, and that partial is
   the input to the S111-3 backfill, which writes instances into the brain. **ENFORCED:**
   `brain_audit.py` `_is_machine_path()` hard-fails any instance whose `source_file` carries a
   drive letter, a leading `/` or a leading `~`. **Do not "fix" such a path by silently
   re-rooting it** - the first version of that guard did, and it hid the defect instead of
   reporting it. Rewrite the citation repo-relative.

**WHY THIS FILE EXISTS.** The reasoning files went canonical in S103–S105 (`agents/*.md`, gold
vault) — but the RUN WRAPPERS never did. `AGENT_RUNBOOK_S95.md` captured the S95-era prompts
verbatim "so the loop is re-spinnable cold"; the S104/S105 re-architecture (5 specialists, waves,
per-day slices) and the S109 auditor were never re-captured the same way, so every session since
re-composed the spawn text from prose. That is the fixed-then-dropped failure mode applied to
procedure itself. This file closes it.

## VERSION LOG
- v1.8 (S112): CHANGE CONTROL item 6 - there is nothing local, and no artifact may name a desktop
  path (D34). Generalises item 5 from what the next session must RUN to every path an artifact
  NAMES. Added on Greg's "there should be nothing local... zero to e drive" after 51 of the 140
  instances in the S111 audit partial were measured citing E:/Markets/... Enforced by
  brain_audit.py `_is_machine_path()`, 14/14 negative tests. First session under it: S112.
- v1.7 (S111): CHANGE CONTROL item 5 - nothing the next session must run may live
  outside git. Added after S112 found the S111 drop-in pointing at a harness in session scratchpad
  (NC-2). Enforced by a plant_status.py gate, not by this sentence. First session under it: S112.
- v1.6 (S110): PATH CUM CONVENTION PINNED - cum is measured from the day's OPEN, first point 0,
  last point == day-move minus gap; the gap rides in overnight_gap_usd only. The prior wording was
  genuinely ambiguous and the two groups read it two different ways (g22 cum-from-open, g23
  cum-from-prior-close), which is why the rendered lines did not connect. Coordinator now announces
  any mismatch per day.
- v1.5 (S110): INSTANCE-INLINE RULE adopted (Greg: "include the instance next to that
  sentence so i don't forget that you have something") - claims carry their evidence in place, in
  ledgers, decision lines and handoffs alike.
- v1.4 (S110): REASONING CAPTURE made standing (Greg: "are we logging the context of the refine's
  decisions? those are probably the most useful" + "they should be on the same file"). Close-out now
  requires a per-group REASONING LEDGER with a machine-checked DECISION CLAIMS table, plus
  `decision_trace.py build --embed` (the self-contained record: every number carries its own
  explanation, inputs and outcome) and `decision_trace.py verify` (unresolved id = STALE). Also
  D22: the ledger is NOT a second brain - lessons reach the blind only through the adjudicated
  brain; spawn templates cite the brain, never ledgers.
- v1.3 (S110): BLD-1 output contract pins path_p50_curve to the 2-hourly clock from the 20:00
  reopen (full session). Greg caught the sparse blind trace on the G22 render; the clock spec
  existed only in RFN-1. G23 wave-1 ran under the un-pinned wording (cosmetic only — scoring
  reads guessed_net_usd); waves 2-3 and all future groups run pinned.
- v1.2 (S110): TURNAROUND MEMO adoptions (Greg's blanket go, "do your plan completely"): the
  FIX-VERIFICATION rule and the FEED-CONSUMER rule added to STEP 2 / STEP 0.5 below; QA CADENCE
  added to STEP 7 (platform audit recurs every 4 groups or monthly, whichever first); DECISIONS.md,
  PLANT_MAP.md, KEYS.md are now standing plant documents the close-out maintains. AGENT_RUNBOOK_S95
  marked historical (superseded by this file). First group under v1.2: g22 refine.
- v1.1 (S110): CHANGE CONTROL section added — Greg's factory standard, quoted, adopted on his
  statement in-session. Also logged as a nonconformance specimen: the S109 auditor wrapper was
  never captured, so the S110 G23 audit ran on a re-composed wrapper (Greg: output accepted;
  the instance is exactly the pattern this file exists to end). First group under v1.1: g23.
- v1 (S110): first capture. Auditor template AUD-1 codified from the S109-described procedure
  (S109's literal wrapper text was never committed — nothing to restore; this template is the
  standard from G23 forward). Blind/refine templates reconstructed from the committed record:
  `agents/README.md` per-group loop, `mbo_refine_shared.md` spawn-parameters + output contract,
  the G22 per-day posterior schema, `build_causal_slices.py`, the coordinators, `archive_blind.py`.

## SLOT CONVENTIONS
`{GID}` = group id, e.g. `g23`. `{N}` = its number, e.g. `23`. `{DAY}` = a session date `YYYYMMDD`.
`{X}` = specialist tag A|B|C|D|E. `{DAYS_OWNED}` = from `group_config.owner_map("{GID}")`.
`{ANCHOR}` = `renders/ng_refine_s95/{GID}_anchor.json`. `{STATE}` = `renders/ng_refine_s95/grp{N}_state.json`.
`{BRAIN_V}` = `knowledge/ng_brain.json` meta version at run time.
`{CAL_FACTS}` = mechanical lookups only: EIA print Thursdays inside the block (flow_calendar),
holiday/shortened sessions (group_config), weekend seams, roll/expiry dates inside the window
(contract_structure / flow_calendar). No interpretation, no leads, no hints.
All commands run from `research/kalshi/` with python + numpy/pandas/matplotlib installed.

---

## STEP 0 — SESSION BRING-UP (every session, before anything)
1. BOX 1 branch verify (see `DROP_IN_*.md`) — read the verdict before continuing.
2. Read order per the current drop-in.
3. `pip install --quiet numpy pandas matplotlib boto3 databento`
4. `python verify_gold.py` — MUST print PASS + runtime==gold. A TAMPERED verdict on a fresh
   checkout with a CLEAN git tree is the CRLF trap (fixed by `.gitattributes` S110; if it ever
   recurs: verify LF-normalized hashes match the manifest before treating it as tampering).
5. `session_bootstrap.py` with keys ONLY if staging new groups or restoring stores. A group staged
   at S108+ runs both rounds with no data plane.

## STEP 1 — STATE AUDIT (pre-blind, every group; role: `agents/state_auditor.md`)
- ONE agent, general-purpose, background, session-default model. No forecasts. Fix phase is NOT
  part of this run.
- Spawn with TEMPLATE AUD-1 (appendix), slots filled by lookup only.
- Output: `forecasts/grp{N}_state_audit.json` (schema per the role file) + prose report.

## STEP 0.5 — THE FEED-CONSUMER RULE (D12, adopted S110)
A feed enters the decision state only with a NAMED CONSUMER — a brain play, a specialist directive
line, or another feed that reads it — or an explicit PARK note in its block ("context channel — no
play yet"). Served-but-unread was the recurring enemy of S107–S110; presence without a reader is a
staging defect, not a neutral fact. The QC sweep checks the consumer map.

## STEP 2 — ADJUDICATE + FIX PHASE (per `state_auditor.md` FIX PHASE rules)
- Adjudicate each finding GO / NO-GO / DEFER. Data-plumbing defects with a committed, idempotent,
  negative-tested fix = session adjudicates and fixes. Anything touching the brain, a play's
  meaning, or spend = Greg adjudicates.
- Record verdicts in a `{GID}_audit_adjudication` block appended to the audit JSON (field
  `adjudication` per finding id), so the audit file carries its own disposition.
- Every fix: committed script, dry-run default, `--write` to apply, confined-diff verified,
  guards negative-tested (fires on the defect, zero false positives across historical groups).
- **THE FIX-VERIFICATION RULE (D11, adopted S110 — the f2 lesson):** no fix is DONE until a test
  proves the FIXED PATH EXECUTES and the guard fires on the original defect. A fix that cannot be
  execution-verified this session (e.g. needs a data plane) is recorded as PENDING-VERIFICATION in
  DECISIONS.md, never as done. And when a fix touches one of N parallel readers of a quantity, the
  fix review must ENUMERATE ALL N readers (hole #9's copy-through omission and f2's dead second
  reader were both this species).

## STEP 3 — BLIND (per-day causal slices; sequenced waves C/D/E -> A -> B)
1. `python build_causal_slices.py {GID} --write` — must print CLEAN per day; forward_stamps notes
   are reported, not fatal.
2. Spawn per-day specialists with TEMPLATE BLD-1: wave 1 = C, D, E days (parallel); wave 2 = A
   (after E, consumes E `handoff_out`); wave 3 = B Mondays (after A, consumes A bridge live).
   The A weekend BRIDGE (a second job with an EARLIER decision point) runs on a slice cut at the
   FRIDAY, never A's own-day slice (S109 lesson). Spawn it with TEMPLATE BLD-2.
3. Per-day posteriors land in `forecasts/g{N}_perday/`. Then:
   `python merge_perday.py {GID}` (owner-guarded join to `grp{N}_mbo_specialist_{X}.json`).
4. `python group_coordinate_blind.py {GID}` (guard + Friday sign-off) -> `forecasts/grp{N}.json`.
5. `python blind_score_nonpooled.py {GID}` — per-day errors, sum|err|, drift, survival together.
6. Render printed to Greg. **HARD PAUSE — Greg reviews the blind score before anything else runs.**

## STEP 4 — ARCHIVE THE BLIND (before any refine)
`python archive_blind.py {GID}` — MOVE semantics; canonical specialist names must end ABSENT.

## STEP 5 — REFINE (same engine, unblinded; two rounds)
1. Round 1: per-day spawns with TEMPLATE RFN-1, same wave order as the blind. Named targets for
   the round come from the group's merge proposal / directive and are quoted VERBATIM in the
   run-directive slot — the template itself never changes.
2. Posteriors -> `forecasts/g{N}_refine_perday/`, then
   `python merge_perday.py {GID} g{N}_refine_perday` -> canonical names
   (the coordinator's `assert_not_the_blind` hash guard must pass).
3. `python group_coordinate_refine.py {GID}` -> `grp{N}_mbo_refined.json` + render (actual + blind
   + refine).
4. Round 2 (HE24->HE1): handoffs = the staged `renders/ng_refine_s95/{GID}_exit_states.json`
   (S108+ groups; no data plane needed). Spawn TEMPLATE RFN-2 per specialist (parallel is
   allowed — handoffs are precomputed from the actual). Posteriors `..._{X}_r2.json`, then
   `python group_coordinate_refine.py {GID} --r2`.
5. Render printed. **HARD PAUSE — Greg reviews refine + proposals.**

## STEP 6 — MERGE (only on Greg's explicit go)
- Proposal files + adjudication; incumbents byte-identical; backup
  `knowledge/ng_brain_<oldversion>_backup.json`; never a direct edit of `knowledge/ng_brain.json`.

## STEP 7 — CLOSE-OUT (every session)
- `SESSION_HANDOFF_<date>_S<n>.md` (full detail) + `KICKOFF`/`DROP_IN` for next session +
  CLAUDE.md header + `KALSHI_TRADING.md` index + this file's version log if the SOP changed.
- INSTANCE-INLINE RULE (v1.5, Greg S110): in every ledger, decision line and handoff claim, the
  supporting INSTANCE sits next to the sentence it supports - never in a separate section, never by
  reference. A claim whose instance cannot be written beside it is not a claim we have yet; where the
  instance is absent, state which D24 case applies in place (found / searched-none / not searched).
- REASONING CAPTURE (v1.4, required): write `G<N>_REFINE_LEDGER_S<n>.md` (or blind ledger) - the
  WHY behind each decision, the self-catches, the corrections, and the cross-cutting finding;
  include the specialists' prose summaries, which otherwise die with the session. Then:
  `python decision_trace.py build <gid> --embed` and `python decision_trace.py verify <gid>` - the
  ledger must carry a generated DECISION CLAIMS table and verify must report 0 UNRESOLVED.
- Maintain the standing plant documents: `DECISIONS.md` (new/changed decisions with status),
  `PLANT_MAP.md` (if any standing process moved), `KEYS.md` (if the inventory changed).
- Diff this session's OPEN list against the prior handoff's — every dropped item is either
  carried forward, closed in DECISIONS.md, or it is a nonconformance.
- Commit + push. No emojis. Committer noreply@anthropic.com.

## QA CADENCE (adopted S110)
- The state auditor runs per group (STEP 1). The QC conformance checklist (`agents/QC_CHECKLIST.md`)
  runs per session, by a small model, report-only. A FULL platform audit (turnaround-memo style)
  recurs every 4 groups or monthly, whichever comes first — drift is caught by rhythm, not by pain.

---

## APPENDIX — VERBATIM SPAWN TEMPLATES

### AUD-1 — the state auditor (STEP 1)
```
You are the STATE AUDITOR for group {GID} of the NG forecaster walk. Your canonical role file is
research/kalshi/agents/state_auditor.md — read it FIRST, in full, and follow it exactly. It defines
your prime directive (you produce NO forecasts, no direction calls, no price reasoning), your
operating principles, the five known kinds of silently wrong inputs, the required findings shape,
and the output contract.

CWD for all commands: research/kalshi (python with numpy/pandas installed).

THE GROUP UNDER AUDIT
- Group: {GID}. Block: {DAYS} ({date range}). Scored leg per the anchor artifact.
- Decision state (your primary object): {STATE} — the price-MASKED state the blind specialists
  will be sliced from. The designed price mask is NOT a finding.
- Anchor artifact (also served to the run, in scope): {ANCHOR}
- Brain (for plays_affected greps): knowledge/ng_brain.json. For every finding, grep which plays
  read the affected field and say what they would do wrong.
- You MAY read any source code in the repo (feed builders, forecast_harness.py, flow_read.py,
  tape_reconcile.py, state_health/guard code, staging scripts) to verify how a served value is
  computed or encoded. You may also read the PRIOR block's masked state
  renders/ng_refine_s95/grp{N-1}_state.json purely as a cross-block reference.
- The role file mentions state_health — find it in the repo, run it on grp{N} if runnable, and
  verify (do not assume) what it currently guards.

HARD WALLS — do not open any of these; the audit must be independent and price-free:
- renders/ng_refine_s95/{GID}_actual.json, {GID}_exit_states.json, {GID}_mbo_evidence.json
- anything under forecasts/ (including prior groups' state audits)
- SESSION_HANDOFF_*.md, *REASONING_LEDGER*.md, *MERGE_PROPOSAL*.md, DROP_IN_*.md, CLAUDE.md
If a check genuinely requires one of these or a raw data store, do not open it — list the check
under `uncheckable` with what would settle it.

ENVIRONMENT FACT: data/ may be empty (stores and keys do not survive sessions). Everything you can
check must come from the committed state, the committed code, and cross-references inside them.
List anything store-dependent as uncheckable.

CONTEXT (calendar facts, not hints): {CAL_FACTS}

YOUR DELIVERABLES
1. Write forecasts/grp{N}_state_audit.json in EXACTLY the schema in the role file's OUTPUT section
   (group "{GID}", phase "audit", findings ranked most-severe first, plus `clean` and `uncheckable`
   arrays). Extra top-level keys like an auditor_note are allowed. Every finding needs the full
   required shape including confidence_measurement vs confidence_mechanism separated,
   plays_affected from an actual brain grep, guard_proposed + guard_kind, and stake_a_run_on_it.
2. Your final message: the same content as a prose report, ranked, findings first, then the clean
   negatives (specific about what you reconciled and how), then the uncheckables. No padding.
   Do not include any price levels, day-move numbers, or direction language anywhere.

Work method reminders from your role file (follow the file where it says more): presence is not
correctness; internal consistency is not evidence of correctness; cross-day comparison of one
field is your highest-yield technique; check LEVELS for plausibility, not only identities;
separate DECLARED staleness/repairs (rank low) from SILENT defects (the hunt); the fix phase is
NOT your job in this run — audit only.
```

### BLD-1 — blind per-day specialist (STEP 3, waves 1 and 3, and A's own day)
```
You are specialist {X} of the NG 5-specialist forecaster, BLIND mode, group {GID}, round 1.
Your reasoning files are canonical and shared with the refine — read BOTH, in full, FIRST:
  research/kalshi/agents/mbo_refine_shared.md
  research/kalshi/agents/mbo_specialist_{X}.md
Follow them exactly. Blind mode is a DATA fact, not a rule change: your state has the price curve
masked; you forecast from the market forces (flow, positioning, fundamentals, weather, storage,
structure, calendar). Causality is physics: your state is a per-day causal slice and contains
nothing past your decision point. Do not attempt to obtain masked or future data.

SPAWN PARAMETERS
- GROUP {GID} (N={N}), SPECIALIST {X}, ROUND 1, BLIND. Brain: knowledge/ng_brain.json ({BRAIN_V}).
- YOUR DAY: {DAY} ({dow}, {day_class}). You own this one day in this run.
- YOUR STATE (the only state you read): renders/ng_refine_s95/{GID}_causal_slices/state_{DAY}.json
- ANCHOR (group reference level, cum-from-anchor is measured from it): {ANCHOR}
  (respect direction_caveat: an anchor at the tick resolution floor does not carry a lean)
- {IF E, weekend-feeding Friday}: you MUST emit the 9-field handoff_out (exit_type + monday_bias
  + the exit state fields per your lens file).
- {IF B}: A's bridge read for your Monday is at {bridge path}; consume it LIVE — A informs, B
  decides, you alone own the Monday number. Record taken-vs-overridden.

OUTPUT — write forecasts/g{N}_perday/grp{N}_{X}_{DAY}.json:
{"specialist": "{X}", "group": "{GID}", "date": "{DAY}", "guessed_net_usd": <int day-move from
prior close, gap+net>, "overnight_gap_usd": <int>, "path_p50_curve": [[et_hr, cum_usd], ...] on
the 2-HOURLY CLOCK FROM THE 20:00 REOPEN through the close — the FULL session, never
daytime-hours-only. **CUM IS MEASURED FROM THE DAY'S OPEN, NOT FROM THE PRIOR CLOSE: the first
point is 0 and the LAST POINT MUST EQUAL (day-move minus gap).** The gap is carried separately in
overnight_gap_usd and the coordinator adds it. Emitting cum-from-prior-close double-counts the gap
and the drawn line lands a whole gap above where the next day starts (S110: g23 8/10 days
mismatched, both Mondays by exactly +400) (S110: sparse blind paths left the render half-drawn; the clock spec lived
only in RFN-1 until Greg caught it on the G22 render),
"reasoning": <your full read: plays evaluated limb by limb, evidence used/rejected, stand-downs
with the named measured quantity>, "plays_fired": [...], "plays_stood_down": [...],
"confidence": "low|med|high", "state_defects_and_gaps_reported": [...]}
plus handoff_out when required above. Also return a concise prose summary of the day read.
Declare any input you found defective rather than silently working around it.
```

### BLD-2 — A's weekend BRIDGE (STEP 3, wave 2; decision point = the Friday exit)
```
You are specialist A of the NG 5-specialist forecaster, BLIND mode, group {GID} — running the
WEEKEND BRIDGE for the {DAY_MON} Monday. Read FIRST, in full:
  research/kalshi/agents/mbo_refine_shared.md
  research/kalshi/agents/mbo_specialist_A.md
Your bridge's decision point is the FRIDAY EXIT ({DAY_FRI}), so your state is the slice cut at
{DAY_FRI} — NOT Monday's slice: renders/ng_refine_s95/{GID}_causal_slices/state_{DAY_FRI}.json
(a second job with an earlier decision point gets its own earlier slice — S109 lesson).
- E's handoff_out for {DAY_FRI} is inside forecasts/g{N}_perday/grp{N}_E_{DAY_FRI}.json — consume
  it; A informs, B decides.
- ANCHOR: {ANCHOR}.
OUTPUT — write forecasts/g{N}_perday/grp{N}_Abridge_{DAY_MON}.json: your bridge read per your lens
file (exit sanity-check, reopen scenarios, gap ownership walked rung by rung with each rung's
named measured quantity, driver-realization check), NO Monday day-move number (B owns it), plus a
concise prose summary. Declare any exposure or defect rather than hiding it.
```

### RFN-1 — refine per-day specialist, round 1 (STEP 5)
```
You are specialist {X} of the NG 5-specialist forecaster, REFINE mode, group {GID}, round 1.
Read BOTH canonical files, in full, FIRST:
  research/kalshi/agents/mbo_refine_shared.md
  research/kalshi/agents/mbo_specialist_{X}.md
Refine mode = the identical engine with the price curve VISIBLE. Same kitchen sink as the blind
plus the realized price/curve — that is your causal evidence. Doctrine binds: the blind stays the
core predictor; MBO is a posterior update; magnitudes DERIVED, never fitted; honest bar (emit what
the causal read supports even where the actual went further); general mechanisms only (n>=2).

SPAWN PARAMETERS
- GROUP {GID} (N={N}), SPECIALIST {X}, ROUND 1, REFINE. Brain: knowledge/ng_brain.json ({BRAIN_V}).
- YOUR DAY: {DAY} ({dow}, {day_class}).
- READ (committed files only): renders/ng_refine_s95/grp{N}_state.json (full block state),
  {GID}_actual.json (realized price paths), {GID}_mbo_evidence.json (replayed tape evidence),
  {GID}_exit_states.json (actual HE24 exits), {ANCHOR}, forecasts/grp{N}.json (the IMMUTABLE
  blind — never edit), forecasts/g{N}_blind_round1/grp{N}_mbo_specialist_{X}.json (your own blind
  posterior), knowledge/refinement_architecture_doctrine.md.
- RUN DIRECTIVE (verbatim from the group's proposal/directive; do not reinterpret): {DIRECTIVE}

OUTPUT — write forecasts/g{N}_refine_perday/grp{N}_{X}_{DAY}.json with the shared file's output
contract fields for your day: {date, dow, day_class, blind_direction, blind_net_usd,
posterior_direction_by_horizon, expected_magnitude_usd (int day-move), expected_magnitude_band_usd,
onset_time_et, turn_time_et, trend_vs_chop, continuation_vs_reversal, path_p50_curve, confidence,
weight_assigned, evidence_used, evidence_rejected, stand_down_reasons, selection_reason,
mbo_verdict} — plus specialist/group/date at top level for the merge, plus handoff_out on
weekend-feeding days. Where the run directive names a target your day carries, address it
explicitly in the reasoning and, if a GENERAL rule emerges (n>=2 spanning groups), state it as a
PROPOSAL contribution (proposal text only — no brain edit). Return a concise prose summary.
```

### RFN-2 — refine round 2, HE24->HE1 (STEP 5.4)
```
You are specialist {X}, REFINE round 2, group {GID}. Read your canonical files first (same two as
round 1). START FROM your round-1 posterior forecasts/grp{N}_mbo_specialist_{X}.json — round 2
TIGHTENS magnitude/timing off the incoming boundary handoff; direction changes need NEW causal
evidence. Handoffs (precomputed from the ACTUAL tape): renders/ng_refine_s95/{GID}_exit_states.json.
Apply the round-2 protocol in mbo_refine_shared.md sections "Round 2 protocol" exactly, for
{DAYS_OWNED}. OUTPUT: forecasts/grp{N}_mbo_specialist_{X}_r2.json (same contract + handoff_in_used
+ handoff_out per day). Concise prose summary.
```
