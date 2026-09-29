# HANDOFF 2026-09-29 ~18:45Z (evening): 31-day ingest, 13-point day files, A100 ROOT loop, worker spread

Branch `claude/frankie-monday-cycle-0-urozez` (no merge base with trunk). Read with `DROP_IN_20260929_EVENING.md`.
Earlier today: `HANDOFF_20260929_TUEWED_DATAPOINTS.md`, `DROP_IN_20260929_ROLLING_INGEST.md`.
Session: https://claude.ai/code/session_01KVgJ3jbGzKRGKPfnEdrwoa (Greg called the new chat at ~18:42Z).

## Greg's standing calls from this chat (all still in force)
- INGESTION IS #1 until all 31 days are ingested. Never stop a running job; every vacant slot goes to an ingest first.
- 8 cores per day process (7 workers + parent), never more than a box's nproc. Main 32 = 2 pairs; twin 16 = 1 pair;
  i-08cee 8 = one pair at 3 workers each; a single straggler day may go on the small box.
- 13-point day files MUST be attached to a day before ANY of its calcs (root/teacher/classroom/jev/...). The
  orchestrator enforces it (external_ready). No day has run any calc yet; no day file exists yet (S3 frankie/day_external/ empty).
- ROOT goes on 4 A100 Pods: one day per Pod, all 16 vCPUs, workers pinned one per CPU (15 on CPUs 1-15, parent CPU 0),
  DATA_WORKERS=48 cap like Monday. Pods stay up and pull the next day ("Pod keeps going"); days start anywhere
  (boxes too) if Pods aren't ready; one claim per day. Greg later: "have days stay in the Pod while it runs its full run"
  (root -> teacher -> classroom -> reports -> data -> search on the Pod): DESIGNED, NOT CODED (see Pods below).
- "No more Pod start ups until next chat" (18:38Z). Disk cleanup is NOT now ("we won't worry about disk clean up this
  second"); when it resumes: clean a spot before new work goes in; cleaning is otherwise last priority.
- Reports: every trade day gets CLASSROOM REPORT #N, FRANKIE REPORT #N, JEV REPORT #N with ONE shared N per day;
  deterministic plain-language translators of recorded fields, NO interpretation, Jev verbatim; post each day's 3
  reports to Greg with download buttons (SendUserFile). Built, never run (d85f8e07).
- Jev: one per trade day (his Pod is started per classroom day with REPORT_NUMBER=N; ~$1.59/h, capped 8 h, deleted).
- A plain one-agent-per-job style: Greg wants ONE agent doing the consensus fetch + day files in the next chat.

## Boxes at 18:41Z
| Box | Running | Notes |
|---|---|---|
| main i-035994afa8bdf66a5 us-east-1 (32 CPU, 1.3 TB free) | conforms 20211006, 20211012, 20211013 (WORKERS=6, timeout 43200); ingest 20251014 (7 workers) | 20241008/09/15/16 SEALED (inline verify); 9-10 runner days placed as work/ingest-<day>-gh-36571235912-1 |
| Linux twin i-0d17573dbce871520 us-east-1 (16 CPU, 116 GB disk, 74 GB free) | 20251001 verify 94%; ingest 20251015 (7 workers) | 20250930 SEALED. Launched today (Greg), replaces the Windows box |
| i-08cee7171c0a76a04 us-east-2 (8 CPU, 223 GB free) | 20241001/02 verify 46%/64% (3 workers each) | 20251007/08 FETCHED there: ingest when 20241001/02 seal (DAYS_AT_ONCE=2 WORKERS=7 VERIFY=inline timeout 43200) |
- Windows box i-0e90ee6110ef609aa TERMINATED (Greg); snapshots snap-0ec119eebb2964b4d (root 120 GB) and
  snap-0142c4b8766b5b7ea (data 250 GB); the 250 GB volume vol-05c3d967e07b2d61f still exists (bills ~$20/mo): Greg's call.
- A 10-minute container loop re-spread workers (lost with this chat); the permanent fix is in the ingest wrapper (below).

## The 31 days
- SEALED on main: 20211005 (inline verified), 20211006, 20211012, 20211013, 20221004, 20221005 (deferred: conforms of
  06/12/13 running; 20221004/05 conform NOT yet run), 20241008, 20241009, 20241015, 20241016. Twin: 20250930.
- Runner-ingested (run 36571235912): 10 of 12 done and pulled onto main (pull agent: frankie_box_pull_runner_ingest.sh,
  POINTER_SOURCE=artifact, commit 0c0b4afb). 20211019/20211020 were still ingesting; GitHub 6 h job limit ~18:55Z.
  Insurance: their partitions are pre-fetched on main (block_20211019/20). If the runner jobs died: ingest them on the
  first free slot.
- Ingesting: 20251014 (main), 20251015 (twin), 20241001/02 (i-08cee verify), 20251001 (twin verify).
- Not started: 20251021 (fetched on main: next free main slot), 20251007/08 (fetched on i-08cee).
- Conforms still to run: 20221004, 20221005 (WORKERS=6, timeout 43200, after ingests).
- CONFORM FACT: ~140 entries/s per drain, NO resume (restart from 0), conformance.json written only at the end. The
  first Wed conform died at 65% on a 3 h RUN_TIMEOUT. Always timeout 43200. ROOT does NOT require conform
  (orchestrator design: deferred verify); a failed conform flags its day.

## Worker spread (speed fix, done)
worker_budget pins every reader worker to cpus[1:] of the process affinity, so side-by-side drains all landed on CPUs
1..N (measured: 1-6 at 100%, 7-31 idle). Re-pinning live made drains 4-5x faster (Wed conform 0.18 -> 0.90 %/min).
Commits: 9ee85ad7 frankie_box_spread_workers.sh (affinity only); d87dbe2a the ingest wrapper runs it every 60 s as a
sidecar during every ingest/conform (dispatches from d87dbe2a on carry it; older running jobs were covered by the lost
container loop -- re-run frankie_box_spread_workers.sh on a box by hand if its old drains show CPU piling).

## 13-point day files (the critical path)
- History: run 36576414768 (cancelled on Greg's word, but its always() upload saved) = COMPLETE, 0 gaps, all 31 days
  incl 20211020, for calendar, cot, storage, weather_obs, mos, eia930 (434 files). Only CONSENSUS is incomplete.
- Consensus (keyed by storage PRINT, not day), one request at a time (Greg), families=consensus, days input
  (975e242b): request 1 = 36609379489 (6 box days + 20211020; prints 2021-09-30/10-07/10-14/10-21, 2022-09-29/10-06;
  ALSO covers 20211019) RUNNING since 18:04Z at handoff. Next: request 2 = 20221011/12/18/19 (prints 2022-10-13/10-20);
  request 3 = the six 2023 days; request 4 = the 13 confirmation days (data only, no day file).
- Builder: per-family run ids (d36a3f9c, 9a4f45f3): orchestrator EXTERNAL_HISTORY_RUN=36576414768
  EXTERNAL_HISTORY_FAMILY_RUNS=consensus=<request run id>; fetch gaps listed in missing[] with reasons.
- Orchestrator run for the 6 box days: RUN=days-20260929-1 CREATED 18:29Z (plan.json exists; STAGES=ingest reused the
  sealed ingests) with DAYS=20211005,20211006,20211012,20211013,20221004,20221005 DAY_CLASS=midweek
  EXTERNAL_HISTORY_RUN=36576414768 EXTERNAL_HISTORY_FAMILY_RUNS=consensus=36609379489 PARALLEL_DAYS=2. When request 1
  lands: restage the tip, ACTION=plan (presign string), ACTION=start with the SAME variables + STAGES=ingest,external
  (presign_hours 6, timeout 10800). Readiness (agent report): all 6 have exactly one sealed ingest, journal sha256
  matches receipt, all non-consensus inputs on S3, only the day file missing; dry run of the full day passed.
- The 12 runner days get their own run (e.g. days-20260929-2) once on the box and their consensus request lands.

## Pods (A100)
- ROOT-only Pod loop BUILT (4cf1e061, 34008de4; never run): frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh,
  ACTION=plan|create|loop|status RUN=<run> CODE_ROOT=<staged>. Claims /opt/frankie-box/work/root-claims/<run>/<day>.json on
  main; results imported sha256-verified to /opt/frankie-box/work/experiment-roots/<run>-<day>-a<N>; new Pods get a 500 GB
  volume at /opt/frankie-box; loop re-dispatch before 6 h. Spec: SPEC-pod-day-runner.md.
- Create run 36612575712 (ACTION=create COUNT=4 CONFIRM=CREATE_4_PODS RUN=days-20260929-1, code 0c0b4afb) started
  18:30Z, still in its "agents coming up" wait at handoff: READ ITS LOG for the 4 Pod ids (they bill $1.59/h each
  while up). Their agent is ROOT-only at 0c0b4afb.
- FULL-DAY-on-Pod (Greg): designed, not coded (Pod builder's final report): SAVED_PLAN=1 + ONLY_DAYS=<day> on the
  orchestrator; two phases because classrooms chain day to day (A: root,teacher now; B: classroom,reports,data,search
  after the previous arm day's classroom is on the box, shipped to the Pod); ship back root (incl classroom,
  jev-material), teacher rows, data, search, brain/<day>-cycle-00, step receipts; report number assigned on the box at
  claim time; tar must keep hard links; Pod venv needs duckdb (frankie_box_venv_duckdb.sh). The running Pods need a new
  MARKETS_SHA (untested PATCH) or recreation for full days. Open questions for Greg: A100 vs CPU Pods (GPU idle for
  CPU steps); two-phase classroom OK?; how to give the 4 Pods the full-day agent.
- Last night's 4 Pods (kqp1qwzv6vo67a, x2vprjb4cs2ulu, mhj0jwod7yfdz5, vbh922dqk8x2f9): EXITED, Granite image, 100+50 GB:
  not used, not billing compute.
- ROOT disk risk: experiment ROOT has bedrock off but DIGEST=on for every arm day (5/5); Monday's digest alone was
  201 GB (of a 398 GB ROOT). Estimate 90-250 GB per day (unmeasured). Measure the first day before running many on main.

## Built today (commits on the branch)
520faa7f teacher CPU budget (TEACHER_CPUS / CPUS); d85f8e07 day reports (Classroom/Frankie/Jev #N); 20206723 swap-file
cleanup script; 9ee85ad7 + d87dbe2a worker spread; 44dac598 EIA key from SSM + retries; 975e242b days input;
d36a3f9c + 9a4f45f3 per-family history ids; dac7eec4 + 0c0b4afb runner-ingest pull; 4cf1e061 + 34008de4 Pod ROOT loop;
bb93f182 HOME for DuckDB under SSM (installer, search, orchestrator). DuckDB 1.5.5 + pyarrow INSTALLED on main
(run 36613581936).

## Disk (cleanup agent's inventory, nothing changed)
Main 1.35 TB free: trash ~0.8 GB (Monday canaries work/ingest-20211004-canary-*, dead unsealed
work/ingest-20211005-ingest-1790672828 + work/ingest-20211006-ingest-1790680900, old ssm-output, apt cache); ask Greg:
tmp/markets-measure + Sep-21 tmp 1.3 GB; optional S3 move: sealed confirmation days 20241008/09/15/16 (44.9 GB).
Twin 74-80 GB free: move 20250930 (15 GB) to S3 once safe; 20251001 after it seals. i-08cee: /mnt/markets August
research ~28 GB (246k files, symlinks; S3 has frankie/blind-october-v4/, bounded-3mo/, fullstack-october-2021/ that may
be copies -- check), pip cache 381 MB. Earlier today: i-08cee swap files removed (34 GB), main code cleanup (3.86 GB).
BLOCKER to resume S3 moves: frankie_box_run.yml put: slots allow only clm-sidecar/ and frankie/day_external/; an
archive prefix needs a workflow change (design in the cleanup report: pod_transfer chunks + sha256 manifest, symlink-aware).

## Keys
AWS pair (Claude IAM user) was set in this container's ~/.config/markets/env (Greg: fine to use; rotate after the build).
EIA key lives in SSM /markets/EIA_API_KEY (us-east-2); Greg also pasted it in chat (rotate later).

## Addendum ~18:50Z: runner-day pull FINAL
10/12 runner days PLACED on main and sha256-verified against their pointer artifacts (run 36611619437): each is the ONE
sealed ingest of its day at /opt/frankie-box/work/ingest-<day>-gh-36571235912-1 for 20221011 20221012 20221018 20221019
20231003 20231004 20231010 20231011 20231017 20231018 (records: /opt/frankie-box/receipts/runner-pull-<day>-gh-36571235912-1.json).
20211019/20211020 were still ingesting on runners at 18:30Z (6 h limit ~18:55Z). If they sealed, place them with:
frankie_box_run.yml script=deploy/aws/box/frankie_box_pull_runner_ingest.sh variables="DAYS=20211019,20211020
RUN=36571235912 ATTEMPT=1 PARALLEL=2 POINTER_SOURCE=artifact" timeout=10800 presign_hours=12
presign="getprefix:bento-568968024170-us-east-2-an/frankie/ingest/20211019/ getprefix:bento-568968024170-us-east-2-an/frankie/ingest/20211020/".
If the jobs were killed: ingest both on a box (partitions pre-fetched on main).

## Addendum ~18:55Z: day-file agent FINAL (no day file attached yet)
Consensus request 1 = 36609379489 (families=consensus; days 20211005,20211006,20211012,20211013,20211020,20221004,20221005;
prints 2021-09-30/10-07/10-14/10-21, 2022-09-29/10-06; also covers 20211019) still RUNNING, not cancelled.
When it lands: restage the tip; frankie_box_experiment.sh ACTION=plan then ACTION=start, RUN=days-20260929-1
DAY_CLASS=midweek DAYS=20211005,20211006,20211012,20211013,20221004,20221005 STAGES=ingest,external
EXTERNAL_HISTORY_RUN=36576414768 EXTERNAL_HISTORY_FAMILY_RUNS=consensus=36609379489 PARALLEL_DAYS=2 CODE_ROOT=<new staged>
(start refuses if the plan variables differ from the run's plan.json). Presign: getprefix:bento-568968024170-us-east-2-an/frankie/day_history/36576414768/
getprefix:.../frankie/day_history/36609379489/ getprefix:.../nymex/ng_fut_parent_v0/ + the 12 put: slots
frankie/day_external/<day>/day-external.json and day-external-receipt.json (ACTION=plan prints the exact string);
presign_hours 6, timeout 10800.
Remaining consensus requests, ONE at a time: ng_historical_mbo_5y_to_s3_20260820.yml mode=day_history families=consensus
days=...: req2 = 20221011,20221012,20221018,20221019 (prints 2022-10-13, 2022-10-20); req3 = 20231003,20231004,20231010,
20231011,20231017,20231018 (prints 2023-09-28/10-05/10-12/10-19); req4 = the 13 confirmation days (9 prints; data only,
no day file). The eia930-only run 36608262546 finished but is not needed.

## Addendum ~18:58Z: 20211019 + 20211020 need a BOX INGEST (runner jobs killed)
Runner-ingest jobs for 20211019 and 20211020 (run 36571235912) were KILLED at the 6 h limit (18:54:42Z / 18:55:07Z):
nothing on S3, no pointer artifact, nothing on the box. Ingest both on the first free box slot (ingestion #1): their
partitions were pre-fetched on MAIN at ~18:12Z (receipts/ingest-fetch-20211019-*, -20211020-*; verify they exist,
else fetch: presign native/20211001_20211101/glbx-mdp3-20211018/19/20.mbo.dbn.zst). Main at 18:41Z was allocated
~29/32 cores (3 conforms x 7 + 20251014 x 8); the twin frees a slot when 20251001 seals (was 94% at 18:41Z) but the
partitions would need a fetch there. Dispatch per day: frankie_box_ingest_block.sh ACTION=ingest DAYS_AT_ONCE=1
WORKERS=7 VERIFY=inline timeout 43200 MANIFEST=research/kalshi/frankie_boss/blocks/BLOCK_<day>_SOURCE_MANIFEST.json.
They get their day files from consensus request 1 (36609379489) once sealed.

## Addendum ~19:20Z: consensus request 1 CANCELLED -- do NOT build with 36609379489
Run 36609379489 ended CANCELLED at ~19:18Z (not by the day-file agent or this chat): its upload holds only 8 objects
and NO consensus/receipt.json. Building with consensus=36609379489 would list consensus.fetch as "no receipt" in every
day file, and a day file is never overwritten. So:
1. Dispatch a FRESH consensus-only request with the same days as request 1: ng_historical_mbo_5y_to_s3_20260820.yml
   mode=day_history families=consensus days=20211005,20211006,20211012,20211013,20211020,20221004,20221005 (also
   covers 20211019). One at a time, then requests 2-4 as listed above.
2. The run days-20260929-1 has consensus=36609379489 baked into its plan.json (start refuses a different plan), so build
   the 6 box days' files in a NEW run, e.g. RUN=days-20260929-2 with EXTERNAL_HISTORY_FAMILY_RUNS=consensus=<new id>
   (same DAYS/DAY_CLASS/EXTERNAL_HISTORY_RUN=36576414768), and point the Pod ROOT loop at that run
   (ACTION=loop RUN=days-20260929-2 ...). days-20260929-1 stays as evidence (ingest reuse only).
