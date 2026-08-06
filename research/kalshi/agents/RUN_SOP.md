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
- v1.11 (S114): THE BRAIN IS SERVED BY ROLE AND PHASE, AND A MISSION BRIEF IS DELIVERED PRE-LAUNCH.
  Logged BEFORE execute this time, which is what item 2 asks for and what v1.10 recorded failing.
  WHY, in Greg's words: *"We don't want the agents seeing nonsense when they are making a
  forecast"*; *"they should get instructions on what their reason for being is before they launch
  but that shouldn't touch them when making a curve. They should always be aware of how to make
  good decisions while they are making the curve"*; *"They are just told to do math basically and
  not really told that the values flow together over time and they are building a picture basically
  and not just dots."* WHAT CHANGED:
  (a) **BLD-1 and RFN-1 gain the `{MISSION}` slot** - a pre-launch brief GENERATED from the brain's
  new `mission` section, never typed into the template, so it cannot drift from the brain. It states
  the problem, the named benchmark (the blind loses to zero-change on six of seven blocks), what
  success is, the emission-ceiling failure mode, where the specialist's day sits in the library
  build and what it hands forward, that the path is ONE continuous object sampled at eight times
  rather than eight independent numbers, what the curve is FOR (three lanes, the 17:00 settle, the
  paper dock), how the variables chain into a tradeable conjunction, and that the job is
  load-bearing in BOTH directions - which is why a declared stand-down beats a manufactured number.
  (b) **BLD-1 and RFN-1 gain the `{VIEW}` slot** - the specialist is pointed at
  `brain_view.py --role specialist`, not at the raw brain. Same brain, scoped: `failure_localization`
  (post-outcome) and `doctrine_legacy` (superseded) are withheld, the mission is withheld from the
  WORKING view because it is orientation, and `meta.view_withheld` names every withholding and its
  reason. NOT a blind wall - D2's one deliberate mask is the PRICE CURVE and the brain carries no
  price. Honest measurement: the withheld sections are 0.6% of the file, so this is a correctness
  fix, not a context saving.
  (c) **`spawn.py` fills both slots BY LOOKUP** (NC-1 discipline), 22/22 selftest.
  (d) **`brain_schema.py validate` gains the SECTION-INDEX GATE** - every top-level brain section
  must be declared in `meta.sections` with `is`, `read_by` and `roles`, so a section cannot be added
  silently or serve to nobody by accident. Six negative branches exercised, each printing its output
  (NC-3). A section does NOT have to fit the play schema (Greg: *"Same doc but doesn't have to fit
  the schema"*) - declaration is the only requirement.
  SCOPE LIMIT: no change to what a specialist is ASKED to produce, to the mask, to the scoring, or
  to any play. REGISTERED FORWARD TEST: `mission.brief_continuity_and_shape`, due g24, with the
  mechanical baseline measured on g22's committed blind before any rehearsal.
- v1.10 (S114): RUN-WRAPPER CHANGES, LOGGED LATE - and the lateness is the point. Greg asked twice
  that the SOP be re-read and followed; it was not re-read, and change-control item 2 (diff -> WHY
  -> explicit go -> version-log -> THEN execute) was broken by this session's own work. Recorded
  here as remediation rather than tidied away, per item 3: a deviation is a nonconformance, never
  silently absorbed. WHAT CHANGED, all in the run wrappers the steps invoke, none in a template:
  (a) **STEP 3.4 / 5.3 - the DUE-LIST GATE.** `due_gate.py` is new and is wired into both
  coordinators: ANNOUNCE in the blind (a SystemExit there would discard a completed run's numbers)
  and HARD in the refine (jidoka, item 4 - the refine is where a merged play's falsifier is
  evaluable). WHY: `merge_gate` claimed "the coordinator serves the DUE list and hard-fails if a
  due test goes unreported - the one thing that makes unattended merging survivable", and a grep
  of both coordinators returned ZERO references. Eight registered forward tests had nothing holding
  them. Selftest runs four negative tests and prints BOTH branches' output (NC-3's rule).
  (b) **STEP 3.4 - `assert_not_the_refine`.** NC-4: running the blind coordinator on an
  already-refined group assembled REFINE posteriors over the immutable blind record (g22: 4/10
  sum|err| 5,965 -> 10/10 500). First guard used the archive's existence and was insufficient -
  g15/g17/g18/g23 are refined with no archive - so it is now a RECONCILIATION against the committed
  record (S108 hole #8's lesson). Negative-tested on all four exposed groups.
  (c) **REHEARSAL NAMESPACES.** `spawn.py --namespace` redirects the emitted prompt's read AND write
  paths; `merge_perday --suffix` and `stage_group --suffix` keep output off canonical names;
  `build_causal_slices --state-suffix` slices from a re-staged state. The STORED TEMPLATES ARE
  BYTE-IDENTICAL (spawn selftest 22/22), which is why this is a wrapper change and not a template
  change. WHY: BLD-1 hardcodes `forecasts/g{N}_perday/`, which for an already-run group holds the
  committed posteriors - NC-4's shape one layer up, inside the template rather than a coordinator.
  (d) **STATION 0 gains `sop_version`** - a FAIL when a run wrapper has changed since RUN_SOP.md was
  last touched. It fired on this very session (7 wrappers) and that is what produced this entry.
  ENFORCEMENT NOTE: the standing gap is registered as **M-11 (ESSENTIAL)** - every SOP provision
  that held this session had a machine behind it; every one violated was prose. First group under
  v1.10: the next one run. The g22 REHEARSAL (S114) runs under it in a rehearsal namespace and is
  explicitly NOT a scored group cycle - STEP 1 (state audit) and STEP 4 (archive) are skipped by
  design, which is a declared deviation, not a silent one.
- v1.9 (S113): BLD-1 and RFN-1 gain the `{DAY_CALENDAR}` slot - A-13, and the structural cause of
  NC-1. A per-day forecaster had NO calendar channel of its own: `CAL_FACTS` reached AUD-1 only, so
  a false calendar premise typed into a refine directive met nothing that could contradict it, and
  the blind posterior inherited it too. The slot was already GENERATED by `spawn.py day_calendar()`
  from plant_calendar RULES and filled by lookup - it was simply never rendered into a prompt, which
  is this desk's own signature defect (built, plausible, never executed). CAL_FACTS deliberately
  stays AUD-1-only: it quotes every served day and belongs to the auditor who reads the block, not
  to a specialist who owns one day. Blind-legal by construction - the state already serves
  days_to_next_eia_release, days_to_futures_expiry, days_to_opex and next_eia_release_datetime_et,
  all dated AHEAD; D2's one deliberate mask is the PRICE CURVE. Verified by EMITTING the prompt and
  reading the delivered text, not by checking the slot table: on the Monday after Independence Day
  observed the blind prompt now names `PRIOR TRADING SESSION: 20260703 Fri, class partial_session,
  3 calendar day(s) back <- NOT the previous calendar day`. `spawn.py selftest` 22/22. First group
  under it: the next one run.
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

## STATION 0 - DOCUMENT IT NOW (added S112 on Greg's instruction, binding)

Greg, S112, verbatim: *"This makes me crazy that we talk about updating things or carrying them
over somehow and then they don't get done. We have to put something in the sop about immediately
documenting things like this."*

He is right and it is measured, four times over in one session:

- **A-17** - the nuclear maintenance schedule was agreed in conversation AT LEAST TWICE across
  sessions and never became a registry line. It surfaced only because Greg remembered.
- **D36** - the S111 research synthesis ranked thirteen under-used data sources. **Twelve of the
  thirteen had no registry item.** Among them a live WRONG-SIGN risk on a feed we had already built,
  and a LEAKAGE question in the module that conditions magnitude.
- **A-9** - the committed `DROP_IN_S112` listed two ALREADY-DONE items as live instructions.
- **`delegated_prior`** - the first generated S113 ChatGPT brief re-asked three questions ChatGPT
  had already answered, because the registry tracked what was open and never what was delegated.

Every one is the same defect: **a document that states work, sitting apart from the list that counts
it.** `plant_status` can report "61 open items". It cannot report "and twelve things we agreed to
that belong to no item", because nothing that was never entered can be counted.

### THE RULE

**A thing agreed becomes a registry line IN THE SESSION IT IS AGREED, before that session ends.**
Not when someone remembers, not at close-out, not "next session will pick it up".

This binds to five kinds of thing, and the list is deliberately wide:

1. **Anything Greg says to do, carry over, or come back to** - including an aside. A-17 was an aside
   twice.
2. **Every numbered recommendation in a research briefing, memo or external hand-off** (D36),
   **including the ones we decide against** - a rejected recommendation with a recorded reason is
   tracked; an unrecorded one returns as a surprise.
3. **Every defect found**, whether or not it is fixed the same session, with its repair class:
   RETRO_REPAIRED, FORWARD_ONLY or OPEN. Measured: only 2 of 13 known defects ever had history
   rebuilt.
4. **Every feed or field we decide to serve, drop, or stop reading** - `data_registry.py` counts
   what is served and read, and cannot count a decision that was never written.
5. **Every delegation** - who was asked, for what, and whether it came back. Track it on the item
   with `delegated_prior`.

### HOW, so the rule costs seconds and not minutes

    python research/kalshi/store.py docs --write     # regenerates OPEN_ITEMS.md and the file index

Add the entry to `research/kalshi/OPEN_ITEMS.json` with `id`, `title`, `source` (Greg's words
verbatim where they exist), `first_raised`, `status`, `size`, and a `why` that carries the REASONING
rather than a summary of it. Then regenerate. **`OPEN_ITEMS.md` is a RENDER - never edit it.**

### THE STANDARD FOR `why`

Write it so a session six months from now can act without re-deriving the argument. State the
measurement if there is one, name the instance that motivated it, and record what would falsify it.
An item that says only what to do is an item somebody will do wrong.

### THIS STATION IS ENFORCED, NOT DESCRIBED

Greg, S112: *"We can't spend time on an sop that we don't apply."* The first version of this station
was prose - which is the exact disease it describes. **`plant_status.py` now runs it at every
bring-up and every close-out**, four checks:

| check | what it refuses |
|---|---|
| `station0/why` | any live item whose `why` carries an instruction but no reasoning |
| `station0/briefings` | any briefing, synthesis or memo whose recommendations were never audited against the registry (D36). **A `pending` placeholder counts as NOT audited** - presence is not completion |
| `station0/defects` | any defect with no repair class (RETRO_REPAIRED / FORWARD_ONLY / OPEN) |
| `station0/registry` | INFO, not pass/fail: prints the item count and how many were added since the last commit, so a session that agreed things and entered none is LOUD rather than silent |

**What is deliberately NOT gated:** no machine can tell whether something said in conversation was
entered. The gates refuse the SHAPES THAT ALWAYS ACCOMPANY A MISS - an unaudited briefing, a defect
with no class, an item with no reasoning - and make the registry delta visible. The judgment stays
human; the bookkeeping does not.

**Both checks fired on the session that wrote them.** `station0/why` caught M-4 and M-8 carrying
instructions with no reasoning. `station0/briefings` caught six of seven briefings never audited -
and caught an earlier version of itself reading a `pending` placeholder as a pass.

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
WHY YOU EXIST - read this once, now, before you touch the state. It is your orientation, not a
reference: it is deliberately NOT repeated in your brain view, because it is not something to
consult while you are drawing the curve. Generated from the brain's `mission` section, so it is
always the current one.
{MISSION}

END OF BRIEF. Everything below is the job.

Follow them exactly. Blind mode is a DATA fact, not a rule change: your state has the price curve
masked; you forecast from the market forces (flow, positioning, fundamentals, weather, storage,
structure, calendar). Causality is physics: your state is a per-day causal slice and contains
nothing past your decision point. Do not attempt to obtain masked or future data.

SPAWN PARAMETERS
- GROUP {GID} (N={N}), SPECIALIST {X}, ROUND 1, BLIND. Brain: run `python brain_view.py --role specialist --out {VIEW}` FIRST and read {VIEW},
  NOT knowledge/ng_brain.json ({BRAIN_V}). It is the same brain, scoped to your role: the
  post-outcome failure-localization doctrine and the superseded doctrine_legacy are
  withheld, and meta.view_withheld tells you what was withheld and why. If you believe you
  need a withheld section, SAY SO in your report - do not open the raw file to route around
  the scoping. This is a relevance filter, not a blind wall: D2's one deliberate mask is
  the PRICE CURVE, and the brain carries no price.
- YOUR DAY: {DAY} ({dow}, {day_class}). You own this one day in this run.
- YOUR STATE (the only state you read): renders/ng_refine_s95/{GID}_causal_slices/state_{DAY}.json
- ANCHOR (group reference level, cum-from-anchor is measured from it): {ANCHOR}
  (respect direction_caveat: an anchor at the tick resolution floor does not carry a lean)
- CALENDAR FOR YOUR DAY (facts, not hints - do not reinterpret them into a lean):
{DAY_CALENDAR}
  Your PRIOR TRADING SESSION is named there and is NOT always the previous calendar day. The
  handoff you inherit comes from that session; the seam you are crossing is the gap shown.
  Blind-legal by construction: the state already serves days_to_next_eia_release,
  days_to_futures_expiry, days_to_opex and next_eia_release_datetime_et, all dated AHEAD.
  Calendar is deterministic and public; D2's one deliberate mask is the PRICE CURVE.
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
WHY YOU EXIST - read this once, now, before you touch the state. It is your orientation, not a
reference: it is deliberately NOT repeated in your brain view, because it is not something to
consult while you are drawing the curve. Generated from the brain's `mission` section, so it is
always the current one.
{MISSION}

END OF BRIEF. Everything below is the job.

Refine mode = the identical engine with the price curve VISIBLE. Same kitchen sink as the blind
plus the realized price/curve — that is your causal evidence. Doctrine binds: the blind stays the
core predictor; MBO is a posterior update; magnitudes DERIVED, never fitted; honest bar (emit what
the causal read supports even where the actual went further); general mechanisms only (n>=2).

SPAWN PARAMETERS
- GROUP {GID} (N={N}), SPECIALIST {X}, ROUND 1, REFINE. Brain: run `python brain_view.py --role specialist --out {VIEW}` FIRST and read {VIEW},
  NOT knowledge/ng_brain.json ({BRAIN_V}). It is the same brain, scoped to your role: the
  post-outcome failure-localization doctrine and the superseded doctrine_legacy are
  withheld, and meta.view_withheld tells you what was withheld and why. If you believe you
  need a withheld section, SAY SO in your report - do not open the raw file to route around
  the scoping. This is a relevance filter, not a blind wall: D2's one deliberate mask is
  the PRICE CURVE, and the brain carries no price.
- YOUR DAY: {DAY} ({dow}, {day_class}).
- CALENDAR FOR YOUR DAY (facts, not hints - do not reinterpret them into a lean):
{DAY_CALENDAR}
  Your PRIOR TRADING SESSION is named there and is NOT always the previous calendar day. The
  handoff you inherit comes from that session; the seam you are crossing is the gap shown.
  Blind-legal by construction: the state already serves days_to_next_eia_release,
  days_to_futures_expiry, days_to_opex and next_eia_release_datetime_et, all dated AHEAD.
  Calendar is deterministic and public; D2's one deliberate mask is the PRICE CURVE.
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

### FJ-1 — failure judge, post-outcome (runs after a group is scored)
```
You are the FAILURE JUDGE for group {GID} of the NG forecaster walk. Your canonical role file is
research/kalshi/agents/failure_judge.md - read it FIRST, in full, and follow it exactly. It defines
your three turns, the root-cause rule, the disambiguation table, your output contract and your
honest limit. You produce NO forecasts, no direction calls, no price reasoning and no numbers of
your own. You run AFTER the outcome is known.

WHY YOU EXIST - read this once, now. Generated from the brain's `mission` section.
{MISSION}

END OF BRIEF. Everything below is the job.

THE TAXONOMY IS FROZEN AND MACHINE-CHECKED. Load it from research/kalshi/failure_localization.py -
do NOT reconstruct the components, the 41 modes or the fault sides from memory. Two labels in that
file are DECLARED LOCAL EXTENSIONS, not the paper's (`Context Delivery Failure` on model-context,
`Owner Premise Error` on model-owner); they exist because the paper's model-context edge carries no
harness-side mode at all. Use them where they fit and say so. Any (edge, mode, fault_side) triple
outside the frozen table is REFUSED by `failure_localization.validate()` - run it on your own
output before you hand it back, and fix your labels rather than the table.

BRAIN: run `python brain_view.py --role failure_judge --phase post_outcome --out {VIEW}` and read
that. It serves you the failure_localization doctrine, reasoning_method and the plays; the
forecasting-only sections are withheld by design and meta.view_withheld says which and why.

WHAT YOU ARE JUDGING
- Group: {GID} (N={N}). Block: {DAYS}.
- The posteriors, the actual, the served slices, the ledgers and the code are ALL open to you.
  There is no blind wall for this role (D39: post-outcome the question is whether a value was
  RIGHT, not whether it was knowable).
- Start from the days with the largest |err| but do NOT stop there: the root-cause rule will
  often move the label to an EARLIER day that scored fine. Say so explicitly when it does.

YOUR DELIVERABLE
1. forecasts/{GID}_failure_localization.json in EXACTLY the role file's output schema, including
   `would_a_different_label_change_the_repair` on every finding - if that is false, mark the
   finding low confidence and say why you kept it.
2. A prose report: findings ranked, each naming the earliest unrecovered failure, the consequences
   you are NOT labelling, and what a second judge disagreeing would change. State the honest limit
   (Cohen's kappa 0.76, best of four models against human labels) in your own words.
Say `unclassifiable` rather than force a label. A forced label is the emission-ceiling failure
wearing different clothes: a defensible answer produced because the contract demanded one.
```
