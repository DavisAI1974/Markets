# DROP-IN: Frankie cycle 0, Granite decoupling (2026-09-28, end of chat; updated 2026-09-29)

**2026-09-29, the latest direction, read it first: `SPEC-decouple-granite.md`.**
- Greg: Granite keeps ONLY the roles the Excel build plan originally gave it:
  - C35, Frankie's engine for the reading and the writing;
  - C21-C24, the shadow critic;
  - C14, the classroom through C35.
- It is decoupled everywhere else, and the experiment's Granite pass is removed.
- r10 uses only those roles, so it proceeds on Greg's go.
- The spec is a draft Greg may still tweak.

**2026-09-29, latest: the scientific teacher and the classroom rules (drafts, Greg's to confirm).** Read
`SPEC-scientific-teacher.md` and `knowledge/CLASSROOM_RULES_V1.json` (17 rules, each with its source). Three seats, no
model in any: Frankie (his code, calcs, brain), the BOSS teacher (code), the scientific teacher (the experiment's
search: every claim tested with its own chance check, counts per cell and day). The two teachers stay tied with
separate roles. Not in the build plan yet; the tied teachers stay unwired for r10 until the search exists.

**2026-09-29, later: R3 ROLES ON THE R4 POD (Greg). r10 WAITS for the build.** Granite = the C21-C24 shadow critic only,
served from the R4 Pod, plus one self-assessment of how it performed; Granite has NOTHING to do with the classroom
(Greg 23:17 ET), which Frankie's code answers; Frankie does the analysis; the principal's reading, merges and writing
come off Granite. Read the DECISION block atop `SPEC-decouple-granite.md` and its R3 BUILD list.

**2026-09-29, tooling session: the Granite inventory and the unwiring are done. READ `GRANITE_CALL_INVENTORY_R10_20260929.md`.**
- Every Granite call reachable in r10 is listed with file:line, its build-plan R4 row and its gate.
- The three with no plan role are UNWIRED in `frankie_box_boss_session.py`: the classroom scientific-dialogue branch and
  the correction scientific-review branch are refusals now, and the serverless reading lane is removed (the Pods only;
  Greg: "Not using serverless anymore"). A `/opt/frankie-box/serverless.json` on the box makes r10 refuse at preflight;
  check with `frankie_box_serverless_config.sh ACTION=show`, move aside with `ACTION=remove` on Greg's go.
- Open for Greg: C14 names no Granite (the classroom through C35 is an inference); the critic knowledge loop, the critic
  priming and the correction's learning_history (2026-09-22, inside kept roles, not plan lines).
- Greg 2026-09-29: Granite "should just be a logic helper for frankie".
- `codebase-memory-mcp` is registered on this branch (`.mcp.json`, `enabledMcpjsonServers`); `.cbmignore` re-includes `deploy/`.

Paste this box into the new chat.

```
Frankie Monday cycle 0: Granite decoupling. Run using-agent-skills before anything.
Branch: claude/frankie-monday-cycle-0-urozez. Fetch it and check it out; the tip must be this drop-in's commit or later.
READ FIRST: research/kalshi/frankie_boss/SPEC-decouple-granite.md (Greg 2026-09-29: Granite ONLY in the roles the Excel
build plan originally gave it -- C35 engine for reading/writing, C21-C24 shadow critic, the C14 classroom through C35 --
decoupled everywhere else; a draft Greg may still tweak), then
research/kalshi/frankie_boss/DROP_IN_20260928_GRANITE_DECOUPLE.md (this file), then research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md, then
research/kalshi/frankie_boss/HANDOFF_20260928_JOINED_TEACHERS.md (every update block, in order).
Rules:
- No tests, no validations, no canaries. py_compile with python3.12 only. Put [skip ci] on every push.
- Launch stays on HOLD: no box run, Pod, Granite call or launch without Greg's explicit go.
- A probe on every long box run.
- Never edit frankie_box_projection.py or the pinned reader/teacher/normalizer/context files (swap, never edit).
- A cycle0.sh dispatch needs the staged CODE_ROOT commit == the branch tip, so restage after every push.
- Zero data dropped; no caps; no truncation; nothing normalized or averaged. Unknown or incomplete data is listed.
- Duplicate data declines the run, with the reason.
- Keys are secrets.
Next: confirm SPEC-decouple-granite.md with Greg (r10 uses only Granite's original plan roles, so it is not held by it), then rerun the Frankie part AND the classroom as r10 on the build-plan wiring (Greg: "Unwire everything that isn't in
the build plan and we rerun Frankie part in new chat"; "we'll have to rerun classroom too"), each step on Greg's go.
```

## The two teachers are TIED TOGETHER (Greg, 2026-09-28/29: state this in the handoff)
The two teacher specialists come from the 2026-09-22 handoffs (CODEX_HANDOFF_20260922_CHAT14.md and CHAT15.md):
1. **The original BOSS teacher.** Its mathematics, representation supervision, targets, masks and controls are kept. Scientific research is added to it.
2. **The classroom scientific teacher.** It covers mechanism and evidence.

They are tied together; they exchange specialties:
- The BOSS teacher hands over what it measured.
- The scientific teacher hands back mechanism readings, challenges and proposed tests.
- Each turn builds on the other's findings, and new discoveries from the exchange are recorded as the teachers' own findings.
- Frankie's findings (his independent and novel ones included) reach both teachers as claims, never truth (the three rules: his decision process withheld, graded outcomes kept out of lesson material, his findings are claims).

Where it lives:
- `SPEC-joined-teachers.md`;
- the exchange: `dipole_teacher_discussion.py` and `deploy/aws/box/frankie_box_teacher_discussion.py`;
- the joined data both teachers read: `frankie_box_joined_teacher.py` and `dipole_joined_teacher.py` (dfe08ca7).

**Current wiring:** built and tied, but switched OFF for r10 by the build-plan unwiring (77948797), because the exchange was added after the Excel plan R4.
- `classroom_scientific_dialogue: false` in the host config, and `JOINED` is refused.
- To turn it on: add the tied teachers to the Excel build plan, set the switch to true, and allow `JOINED`. That is Greg's call next chat.

## UNWIRED at the end of the chat (Greg: only what is in the build plan runs)
The build plan is `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`. Its Granite roles:
- C35: Frankie's engine for reading the delivered evidence and writing the four files;
- C21-C24: the shadow critic, under a closed schema;
- C14/D5: the governed 19-dimension classroom with its 171 pairs, training-only.

Unwired, because each was added after the plan (the code stays and is only disconnected):
- **The scientific-teacher dialogue and the BOSS-teacher discussion** (added 2026-09-22):
  - `run_actual_sunday_classroom` builds the classroom package WITHOUT shared knowledge unless the config says `classroom_scientific_dialogue: true`. The host config writes `false`.
  - The adapter and `make_principal_adapter` accept a plan classroom that carries none.
  - The principal still gets its shared-knowledge snapshot: in single-run mode it is Frankie's own knowledge manifest (brain entries plus the 18 preserved sections).
  - Result: the box classroom takes the plain path (19 components on the reading lane, the summary on the BOSS), and the correction is the plain classroom correction, with no scientific request.
- **The joined teacher data**: `ACTION=config JOINED=...` is refused.
- **The Granite exhaustion/D teach-back**: now code-only priming.
- **Jev's sit-in relay and the CLM sidecar**: never part of the principal; simply do not dispatch them.

The rerun therefore runs, in order: verify, labels, engine, derive, reading, merges, the governed classroom, the teach priming (code), writing, push, the correction.

## Greg's direction this chat (the load-bearing part)
- **Granite is a small piece of Frankie: a reasoning boost, nothing else.** Frankie is the system (code, calculations,
  brain). Whatever can be computed or copied is code; Granite gets a small, code-prepared question plus the exact rows
  it needs, and returns reasoning, which code checks against the data.
- **The bedrock is a logic helper, not Frankie's knowledge base.**
  - The teachers read the computed layer files in place.
  - Frankie's brain carries the derivation digest (5 legacy tables since V9), the ledgers, the analysis, layer statuses, the priming and the frozen files. It does not carry the bedrock layer contents.
- The priming for his pump must be catered to his exact role, which is to be defined next.

## DONE this chat
1. **The exhaustion/D priming is DECOUPLED from Granite** (Greg: "Decouple frankie from this part then"). This commit carries it.
   - The `teach` stage computes the facts by code and files them whole, with no model call:
     - `work/teach/exhaustion-teachback.json`, schema `FRANKIE_BOX_TEACH_PRIMING_V1`, with `model_calls: 0`;
     - `exhaustion-teachback.md`: the facts text plus the frozen files.
   - The brain entry and the docs carry that file.
   - The analysis section points at the priming file.
   - A record filed by the retired Granite teach-back still renders as it was.
   - Files: `deploy/aws/box/frankie_box_boss_session.py` (teach, _teach_section, writing prompt wording), `frankie_box_teach.py` (CODE_SCHEMA, facts_markdown), `frankie_box_brain.py` and `frankie_box_docs.py` (descriptions).
2. **Nothing needs rerunning because of it.**
   - The only completed principal run is cycle 00 of 20211003, on 2026-09-21: branches `root/cycle-00-response` 6879fb87 and d44e71ce. Its response keys are feedback, lessons, sections, session_id, request_sha256 and model identity. Its brain entry holds the digest, ledgers, analysis, derive and the derived-files listing. **No teach-back and no classroom ever ran.**
   - The Monday runs r2-r9 never reached the principal.
   - So no calculation or analysis was produced through the Granite teach-back, and the principal-inputs brain base (v9-r2) is unaffected.
3. **The joined teachers are BUILT, NOT RUN** (dfe08ca7):
   - builder: `frankie_box_joined_teacher.py`/`.sh`;
   - delivery to both teachers: `dipole_joined_teacher.py`, the scientific request, the box readings and the validators, with `ACTION=config JOINED=<MANIFEST.json>`.
   - Switched off for r10 (not in the Excel plan). Turning it on is Greg's call (see "The two teachers are TIED TOGETHER").
4. **r9 is stopped and its data kept**, along with every fix since: the single-read walk, the concurrent teacher, the uncapped teacher, the parts-not-truncation notes, and the duplicate refusal. See the handoff.

## NEXT (in order, each on Greg's word)
0. **The r10 rerun of the Frankie part and the classroom, on the plan wiring** (step 4 below), first.
1. **Later, not for this rerun; superseded by `SPEC-decouple-granite.md` unless Greg revisits it: the earlier Granite role table.** It is in the handoff under "Granite is a reasoning boost". The proposal:
   - To code: the reading notes (the data is already exact), the merges (line dedupe), the classroom observation transcription, and the accounting entry plus the ten ledgers.
   - Stays Granite: novel findings, the run analysis, the correction turn, the scientific teacher, the BOSS teacher and Frankie's replies.
   - The whole-corpus staged re-reads before each role are replaced by inputs that code selects for each question.
   - Open call: the classroom grade applies only to Granite's reasoning part once code does the transcription.
2. Build the code side of the agreed table (swap modules; never edit the pinned files).
3. Define and cater the priming to that role: which facts, which frozen files, and whether the joined couplings reach him.
4. Restage the tip. Then the r10 config:
   - `PREPARED=/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json`
   - `PRINCIPAL=/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json`
   - `RUN_ID=monday-20211004-20260928-r10`
   - `OUTPUT_ROOT=/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r10`
   Then the launch and the principal, with probes on both. No Jev relay (unwired). **Do not resend the dipole catalog.**

## Open calls for Greg (carried)
- DONE 2026-09-29: the Pearson coefficients STAY (Greg: "We want the coefficients, just not a bunch of dipole results flattened or normalized"); each of the 171 pairs now also carries co-movement COUNTS beside its coefficient. Grouping over a defined range is allowed, an average is not. Open: which "average plan" Greg meant to take out.
- The same Granite model plays every role, so agreement between roles is not independent confirmation.
- `concurrent_teacher`: when the teacher fails to pickle it falls back to in-process. Keep that fallback, or make it a hard stop?
- A full audit of anything still dropped or capped, across every process.

## WORK INSTRUCTIONS FOR THE NEXT SESSION (do these, in order)
The reference for what runs is the build plan, `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`.
- Sheets: Read Me, Build Plans, Components (C01-C35), Roadmap, Experiment Arms, Gates, Sources, Preservation Audit, Change Log R4.
- Read it with openpyxl. Install it in the container first if it is missing: `pip install openpyxl`.
- Anything not in it stays unwired unless Greg adds it to the plan.

Every box step goes through `.github/workflows/frankie_box_run.yml`: inputs `script` and `variables`, dispatched on this branch.

1. **Session start.**
   - Run using-agent-skills.
   - Fetch and check out `claude/frankie-monday-cycle-0-urozez`; confirm the tip is this drop-in's latest commit or later.
   - Read this drop-in and the build plan sheets Build Plans, Components and Gates.
2. **Check what is running or billing (read-only), before anything else.** The earlier chat did not verify Pod state after stopping r9.
   - The 4 A100 Pods from r6/r9 may still be up (about $6.36/h): BOSS kqp1qwzv6vo67a; readers x2vprjb4cs2ulu, mhj0jwod7yfdz5 and vbh922dqk8x2f9. Check them with the Runpod MCP (list pods) and `/opt/frankie-box/pods.json`.
   - Check the box processes with `frankie_box_read_log.sh MODE=processes`.
   - Report the state to Greg; never stop a Pod without his word.
3. **Stage the tip, on Greg's go.** Script `deploy/aws/box/frankie_box_stage_code.sh`, variables `ACTION=stage`. Note the staged `CODE_ROOT` (`/opt/frankie-box/code/<sha>-<run>-1/markets`). Push nothing between staging and the dispatches below, or restage.
4. **Build the r10 config.** Script `deploy/aws/box/frankie_box_cycle0.sh`, variables:
   `ACTION=config CODE_ROOT=<staged> RUN_ID=monday-20211004-20260928-r10`
   `PREPARED=/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48/prepared-configuration.json`
   `PRINCIPAL=/opt/frankie-box/work/principal-inputs/full-20211004-20260928-v9-r2/principal-inputs-receipt.json`
   `OUTPUT_ROOT=/opt/frankie-box/work/monday-run-config/full-20211004-20260928-r10`
   Do not pass `JOINED`; it is refused. Confirm the config writes `classroom_scientific_dialogue: false`.
5. **Launch, on Greg's go.** Same script, `ACTION=launch CODE_ROOT=<staged> CONFIGURATION=<r10 actual-host-configuration.json>`, timeout 43200.
   - Attach the probe at launch and at every check-in: `frankie_box_progress.sh`, or `frankie_box_read_log.sh MODE=tail FILE=work/runs/monday-20211004-20260928-r10/host-progress/progress.json`.
   - It prepares the context once (saved walk blocks and the concurrent teacher), builds a FRESH classroom package (the plan classroom, no shared knowledge), writes `execution/cycle-00/principal/session-request.json`, and stops at the WAIT (exit 3/4 is pending, not failure).
6. **Principal (the Frankie part and the classroom).** Same script:
   `ACTION=principal CODE_ROOT=<staged>`
   `CALCULATIONS=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
   `REQUEST_DIRECTORY=/opt/frankie-box/work/runs/monday-20211004-20260928-r10/execution/cycle-00/principal`
   Timeout 86400. Probe it. The stages are verify, labels, engine, derive, reading, merges, classroom (19 components and the summary), teach (code priming), writing and push.
7. **Record, then the correction turn.** Use `ACTION=record TURN=initial`, then `ACTION=correction`, then `ACTION=record TURN=correction`. Take the variables from `frankie_box_cycle0.sh`: CONFIGURATION, CALCULATIONS and REQUEST_DIRECTORY. There is no scientific dialogue now; the correction is the plain classroom correction.
8. **Do NOT dispatch:** Jev's relay, the CLM sidecar or the joined-teacher builder. They are unwired and not in the plan.
9. Update this drop-in and the handoff with the run ids and probe readings, and push with `[skip ci]`.

## Gotchas
- A cycle0.sh dispatch refuses unless the staged commit equals the dispatch ref's tip.
- Only ONE pending run per concurrency lock: a new box-run dispatch replaces a queued one.
- r9's run dir (`/opt/frankie-box/work/runs/monday-20211004-20260928-r9`) is kept.
  - r9 ran code 222ac66b, which had no save code, so it left NO saved walk blocks. r10 does the first full walk and saves its blocks as it goes, into the journal's walk-cache.
  - A stopped r10 resumes from them.
  - The saved blocks need at least 30 GB free (`FRANKIE_WALK_CACHE_MIN_FREE_GB`).

## RESEARCH TRACK: the experiment (Greg, 2026-09-29). Direction set; NOT yet in the Excel build plan
Greg's idea: run code over the raw ingest data and the cycle calculations thousands of ways, looking for correlations,
novel findings and trade strategies. Code does the search on the box's CPUs. The experiment's Granite pass is REMOVED (`SPEC-decouple-granite.md`); only the classroom arm (the plan classroom, on the first and last two discovery days) uses Granite, through C35.

- **No bedrock for the experiment.** The inputs are:
  - the raw ingest: each day's compact journal, every book level;
  - the cycle calculations, as JSON.
- **The calculations are written once per cycle and kept in two places** (built in this commit):
  - Frankie's brain entry: the derivation digest, as before.
  - The experiment store: `/opt/frankie-box/work/experiment-calcs/<day>/cycle-<NN>/`. It holds the derive stage's JSON layer files and derive.json, hard-linked with a MANIFEST giving bytes and sha256. The bedrock layers are not exported.
  - `brain_entry()` does this after every cycle via `frankie_box_brain.export_calculations`. A failure is noted and never blocks the cycle.
  - For the Monday root that already exists: `frankie_box_export_calcs.sh`, run on its own lock `box-export-*`, with `WORK=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work DAY=20211004 CYCLE=00`.
- **Days** (the day-class doctrine: never mix classes; report every day on its own, never pooled):
  - Midweek Tuesday/Wednesday first. Tue 2021-10-05 and Wed 2021-10-06 are already fetched to the box in the staged block 20211004-20211006 and just need ingesting.
  - Thursday (EIA print day) is its own class, done later.
  - Monday stays its own class.
  - Discovery: October days of 2021-2023. Confirmation: October days of 2024-2025, untouched until the discovery list is frozen. Then widen to all years, reported per season.
  - Source: the 5-year NG MBO pull on S3 (`nymex/ng_mbo_5y_v0`). Confirm coverage with a listing first.
- **The search, to be built:**
  - every raw and calculation series, times transforms, lags, cells, conditions and targets;
  - each test with its own circular-shift chance check, reported as counts (D37);
  - the leakage gate on every target;
  - survivors to symbolic regression (no Granite pass);
  - any trade idea judged per cell, net of fees at maker and taker, on the confirmation days.
  - The joined-teacher builder (dfe08ca7) is the starting slice. Point it at the raw journal and the experiment-calcs JSON instead of the bedrock.
- **Architecture (Greg):** a stripped-down version of today's run. An EXPERIMENT ORCHESTRATOR workflow calls only the needed pieces of today's run: fetch, ingest, the derive WITHOUT bedrock, and the export. The new search part is then built and attached to it.
  - Spec: `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`.
  - Before building, Greg adds the track to the Excel build plan (`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`).
