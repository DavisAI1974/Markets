# DROP-IN 2026-09-29 night (next chat): fill the 4 ROOT Pods, keep day runs on 16 booked cores, finish ingestion

Branch `claude/frankie-monday-cycle-0-urozez`: `git fetch origin claude/frankie-monday-cycle-0-urozez && git checkout -B
claude/frankie-monday-cycle-0-urozez origin/claude/frankie-monday-cycle-0-urozez` (tip f86bb7c2 or a later handoff doc
commit). Read `research/kalshi/frankie_boss/HANDOFF_20260929_NIGHT.md` (state, run ids, Pod ids, Greg's calls). Skills
first: full-run-orchestrator, experiment-orchestrator; codebase-memory MCP index of the branch (Greg: the MCP is a
directive). AWS pair: ask Greg (put in `~/.config/markets/env`, chmod 600, verify with STS; `pip install boto3` if absent).
EIA key in SSM /markets/EIA_API_KEY (us-east-2). No Runpod key in the container: Pod actions go through the workflows.

Rules: 16 CPUs per day run (booked in the ledger, never fewer, wait for 16), 8 per ingest day process, never double-book;
first-in first-out for ROOT and for classes (classes one at a time, school day = report N); fill Pods first; clean
(trash + move to S3) before filling a freed slot; ingestion #1 until all 31 are ingested; never stop a running job; no
data dropped; counts never averages; py_compile / bash -n only; [skip ci] on every push; restage after every push;
timeout 43200 for ingest/conform/day runs; before ANY placement count the live processes (frankie_box_cores.sh
ACTION=show); never leave a job on a GitHub runner that can outlast its 6 h limit.

## First (in order)
1. Probe: main (frankie_box_cores.sh ACTION=show CODE_ROOT=<staged>; days-20260929-3 progress.json; the ROOT receipts of
   20211005/20211006), twin, i-08cee, and runs 36630611178 (day run), 36630605941 (20251014 verify), 36618331994
   (consensus request 2), 36630617830 (Pod create: "agent up" lines).
2. Pods: ALL FOUR AGENTS UP at 21:25Z (handoff addendum 21:30Z), empty and billing. ACTION=status on
   rf8eux1c88pfn0,xfpt6fy3mjkn4l,6ijaa67k785doa,lunj1qj145rswp, then start the loop
   (ACTION=loop RUN=days-20260929-3 CODE_ROOT=<staged> PODS=<the 4>) - it fills them from the ROOT line (20211012,
   20211013, 20221004, 20221005). A 503 = a failed boot with its failing step: fix pod_bootstrap.sh, push, restage,
   recreate (Pods keep their creation commit). Old 4 Pods + their 500 GB volumes: delete only on Greg's word.
3. Twin is idle: ingest 20251021 there (fetch its partitions first - use the canonical manifest's archive_key paths,
   WORKERS=7, VERIFY=deferred, timeout 43200), or conforms 20211019/20211020 (deferred verify).
4. Attach day files for 20211019/20211020 (new run name, EXTERNAL_HISTORY_RUN=36576414768, no family override,
   presign from plan with any partition item corrected to archive_key), then they enter the ROOT line.
5. Granite voice: needs Greg's direct approval in-session for the Session.boss edit (system role = charter, per-call
   deadline); then build the voice stage and create a Granite Pod per meeting.
6. Then: consensus requests 3/4 (or the multi-region no-limit fetcher Greg asked for), conforms 20221004/05, ingests
   20251007/08, the 13 confirmation days' data only.
