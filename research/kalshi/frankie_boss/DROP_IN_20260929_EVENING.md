# DROP-IN 2026-09-29 evening (next chat): 31-day ingest, 13-point day files, ROOT on A100 Pods

Branch `claude/frankie-monday-cycle-0-urozez`: `git fetch origin claude/frankie-monday-cycle-0-urozez && git checkout -B
claude/frankie-monday-cycle-0-urozez origin/claude/frankie-monday-cycle-0-urozez`. Read
`research/kalshi/frankie_boss/HANDOFF_20260929_EVENING.md` (state, run ids, Greg's calls). Skills: full-run-orchestrator
and experiment-orchestrator before any box step; codebase-memory CLI index of the branch. AWS pair: ask Greg (put in
`~/.config/markets/env`, chmod 600, verify with STS). The EIA key is in SSM /markets/EIA_API_KEY (us-east-2).

Rules: INGESTION #1 until all 31 days are ingested (never stop a running job; free slots go to ingests first); 8 cores
per day process, never over nproc; no day runs any calc before its 13-point file is attached; no data dropped (missing is
listed with its reason); counts never averages; py_compile / bash -n only; `[skip ci]` on every push; restage after every
push before a staged-code dispatch; every ingest/conform timeout 43200; one agent per job, and they must not push over
each other's staged code (tell main before any push). No more Pod start-ups without Greg's word; disk cleanup waits.

## First (in order)
1. Probe the 3 boxes (main i-035994afa8bdf66a5 us-east-1, twin i-0d17573dbce871520 us-east-1, i-08cee7171c0a76a04
   us-east-2) and the runs: consensus request 1 = 36609379489; runner ingest 36571235912 (20211019/20 vs the 6 h limit
   ~18:55Z: if killed, ingest them on the first free slot -- partitions pre-fetched on main); Pod create 36612575712
   (read its log for the 4 Pod ids; they bill $1.59/h each while up). Re-run frankie_box_spread_workers.sh on each box if
   old drains pile onto CPUs 1..N.
2. Spin up ONE agent (Greg) for the consensus fetch + 13-point day files: when 36609379489 lands -> restage the tip ->
   orchestrator RUN=days-20260929-1 (plan exists) ACTION=plan then ACTION=start with DAYS=20211005,20211006,20211012,
   20211013,20221004,20221005 DAY_CLASS=midweek STAGES=ingest,external EXTERNAL_HISTORY_RUN=36576414768
   EXTERNAL_HISTORY_FAMILY_RUNS=consensus=36609379489 PARALLEL_DAYS=2 (presign from plan, presign_hours 6, timeout 10800).
   Verify by receipts (day-external.json beside each sealed ingest + S3 frankie/day_external/<day>/). Then consensus
   requests 2 (20221011/12/18/19), 3 (the six 2023 days), 4 (confirmation days, data only) one at a time; attach files to
   the runner days (20211019/20 use request 1) in a second run (days-20260929-2) once they are on main.
3. ROOT: the moment a day's file is attached, it goes to a Pod (ROOT-only loop works today:
   frankie_box_pod_root_loop.sh ACTION=loop RUN=days-20260929-1 CODE_ROOT=<staged> PODS=<ids from 36612575712>; re-dispatch
   before 6 h) or a box (orchestrator STAGES incl root, claim-aware). Measure the first ROOT's disk (estimate 90-250 GB/day,
   digest on) before running many on main. Greg wants the FULL day on the Pod: designed, not coded (handoff "Pods");
   ask Greg the open questions there before building it.
4. Then per day on the box (or Pod once full-day is built): teacher (TEACHER_CPUS), classroom V2 (chained: PREVIOUS =
   previous arm day's classroom), reports (Classroom/Frankie #N), Jev Pod per day with REPORT_NUMBER=N (+ relay
   ACTION=frankie after), data, search (DuckDB installed on main). Post each day's 3 reports to Greg (SendUserFile).
5. Remaining ingests as slots free: 20251021 (fetched on main), 20251007/08 (fetched on i-08cee, after 20241001/02 seal),
   then conforms 20221004, 20221005.
