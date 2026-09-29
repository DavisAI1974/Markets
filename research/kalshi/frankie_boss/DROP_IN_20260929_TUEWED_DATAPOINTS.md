# DROP-IN 2026-09-29 (next chat): continue the box work

Branch `claude/frankie-monday-cycle-0-urozez`. First: `git fetch origin claude/frankie-monday-cycle-0-urozez &&
git checkout -B claude/frankie-monday-cycle-0-urozez origin/claude/frankie-monday-cycle-0-urozez`; read
`HANDOFF_20260929_TUEWED_DATAPOINTS.md` (state, run ids, Greg's calls), then this list. Skills: codebase-memory CLI
index, using-agent-skills, experiment-orchestrator (+ full-run-orchestrator before any box step).

Rules (unchanged): NO DATA IS DROPPED (list the missing piece, never skip the day); counts, never averages (D37);
py_compile python3.12 and bash -n only, no tests/canaries; `[skip ci]` on every push; restage after every push before a
box dispatch (scripts refuse a staged checkout that differs from MARKETS_SHA); never edit the pinned files (swap);
keys are secrets and do not rotate; a probe on every long box run. Ask Greg for the AWS pair at the start (needed for
direct SSM probes and S3 reads from the container; put it in `~/.config/markets/env`, chmod 600, verify with STS).

## Greg's last words to this chat (~12:05Z): GO GIVEN for these two
- **Set up the Linux box now** ("Start setting up linux box. We have well over an hour of runway. Tell next guy to do
  it."): i-08cee7171c0a76a04, r6i.2xlarge, 8 vCPU / 64 GB, 300 GB gp3, us-east-2, STOPPED. Greg's go to START it is
  given. (The closing chat's start call was refused by Claude Code's permission check, not by AWS; nothing started.)
  Steps: start it; confirm SSM Online (instance profile; if none, attach the one the main box uses); OS, python3, disk;
  build `/opt/frankie-box` like the main box: the venv (same packages: read `pip freeze` of
  /opt/frankie-box/venv on the main box over SSM and install the same versions, incl. databento-dbn, zstandard,
  duckdb 1.5.5, numpy), the staged code through `frankie_box_stage_code.sh ACTION=stage` with
  `instance=i-08cee7171c0a76a04 region=us-east-2` (the workflow takes both inputs), the data layout
  (`/opt/frankie-box/{work,data,code,receipts,brain,tmp}`). Then two pairs can run on it (orchestrator with
  instance/region inputs). Grow its 300 GB disk if needed (Greg's go).
- **Bedrock tables get deleted** ("bedrock table gets deleted. We already have this data."): the bedrock projection
  `.projection-v2` (345 GB) and the bedrock digest table scratches of the Monday root
  (`work/monday-calculations/full-20211004-20260927-r1-48/work/derived/`), after naming the retained copy of the data
  (the inventory agent was told to list them with that evidence in `BOX_DATA_INVENTORY_20260929.md` and commit it).
  Deletion = a committed, named-only script like `frankie_box_cleanup_side.sh` (refuse open files; print what was
  removed and its bytes).

## Work list, in order
1. **Probe everything running** (handoff table): Wednesday 20211006 (then `ACTION=conform` on it), the four ingests of
   orchestrator run `pairs2-20260929-1`, Databento run 36564541947 (Oct 2024+2025), free fetch run 36557302661.
   Re-arm your own check-ins (the closing chat's triggers do not reach you).
2. **CPUs** (Greg: "We need more CPUs for 4 pairs and we have a 32 cpu box doing nothing"): EC2 shows the stopped boxes
   as r6i.2xlarge 8 vCPU Linux and r7i.4xlarge 16 vCPU **Windows** (CLAUDE.md says the Windows host was resized to 32
   vCPU; EC2 disagrees). Ask Greg which box; our pipeline is Linux (`/opt/frankie-box`, SSM, venv). Setting up a second
   Linux box = copy the setup (venv, markets checkout, scripts) to it, then the orchestrator runs with `instance=<id>`.
   Starting a box is Greg's go.
3. **Disk** (~258 GB free; one day's ingest ~25 GB): the old-data inventory `BOX_DATA_INVENTORY_20260929.md` (redo it
   read-only if it is not on the branch: classify everything under /opt/frankie-box into keep-active / keep-zip /
   duplicate / failed-unused / rebuildable with evidence from receipts and handoffs). Then, per Greg: delete failed,
   unused and duplicate runs (evidence listed), zip the keepers (zstd, sampled estimate first), move the zips off the
   box (S3 recommended; the box's role writes nothing to S3, so it needs a one-time upload permission: Greg's go).
   Old code checkouts (~104 GB) and `code/transfer-*` packs (~45 GB, the cache cleanup did not remove them: find why)
   are rebuildable.
4. **The 13 points for Tue/Wed**, once the free fetch lands: day files via
   `frankie_box_day_external.sh` (variables `CODE_ROOT=<staged> DAYS=20211005,20211006 RUN=tuewed-20211005-1
   HISTORY_RUN=36557302661 BRAIN=/opt/frankie-box/brain WORKERS=2`, presign `getprefix:` the history run and
   `nymex/ng_fut_parent_v0/` plus `put:` slots `frankie/day_external/<day>/day-external.json` and
   `day-external-receipt.json` for each day, presign_hours 6, timeout 10800). Then Tue/Wed: ROOT with DIGEST=on
   (`frankie_box_experiment_root.sh`, OUTPUT_ROOT=/opt/frankie-box/work/experiment-roots/<day>-arm-r1), teacher
   (`frankie_box_experiment_teacher.sh`), classroom V2 (`frankie_box_experiment_classroom_v2.sh`, Wed with
   PREVIOUS=<Tue root>/work/classroom), Jev (relay material, Jev Pod, relay Frankie outputs, reports). Or run them
   through the orchestrator with `STAGES=external,root,teacher,classroom,jev,data,search`.
5. **Wednesday 20211020** needs its free-source fetch (the run predates it) and its manifest (day facts for 20211019,
   20211020 and the other remaining days: `frankie_box_day_facts.sh`, then `derive_trading_day_manifest.py` in the
   container via a bare-namespace runner, since the package `__init__` imports torch).
6. **The rest of the 31 days**: day facts + manifests for every remaining day (2024-2025 days need
   `CONFIRMATION=staging-only`), then ingest in pairs (4 days at once, deferred verify), as disk and CPUs allow.
   Greg: "just do the rest of the 30 days and pause other jobs until it's done" (reading: ingest all first; confirm).
   Open with Greg: 2024-2025 are CONFIRMATION days in the orchestrator (left out without a frozen survivor list, never
   classroom days); late-September days (2025-09-30) are refused by the October-only rule.
7. **Fix before the next orchestrator dispatch**: the plan's presign keys lack the S3 segment folder (use each block
   manifest session's `archive_key`); resuming `pairs2-20260929-1` keeps its old plan (classroom only on 20211012/13):
   pass `CLASSROOM_ARM` explicitly or start a new run name so every day gets the classroom (Greg).
8. **Databento**: when Oct 2024+2025 lands, tell Greg it is safe to cancel the subscription. HOLD Oct 2021-2023 ($136
   for all five Octobers) and the 5-year MBO ($1,602) until he says.
9. **Open builds** (each on Greg's word): storage-estimate extractor over the archived pages; GUIDED answers for
   Frankie's code (the mastery ramp reaches GUIDED after two mastered TEACH days) or hold at TEACH; the BOSS teacher's
   answer turn in the three-way conference (SPEC-scientific-teacher.md item 5); squeeze_watch deferred by Greg.
