# SPEC: the experiment's ROOT on A100 Pods (Pod day runner)

Status 2026-09-29: BUILT, NOT RUN (py_compile / bash -n / sh -n only). Nothing was created, started or dispatched.

Greg, 2026-09-29: "What's wrong with the A100s? We used Pods a lot last night. After someone is done running we can clean
it and zip their work that we want to keep and move it off the Pod to the big box." Then (scope): "Agent work
immediately, then A100s immediately after to start running ROOT; when that day is done, clean up after the day by
deleting garbage and moving data to the big box to be read by other processes." Then: "Just the pod results. The pod
stays and brings the next people in, and as space frees up on other boxes they do the same."

So the Pods run the experiment's ROOT ONLY (`frankie_box_experiment_root.sh`, the same committed script, commit and
receipts as the orchestrator's `root` stage). Teacher, classroom, reports, data and search stay on the main box, which
reads the Pod's ROOT exactly where it would have written it. Ingestion keeps priority on the boxes.

## 1. Pieces (all additive)

| File | Runs on | What it does |
|---|---|---|
| `.github/workflows/frankie_box_run.yml` step "Pod ROOT loop" + marker `deploy/aws/box/frankie_box_pod_root_loop.sh` | GitHub runner | `ACTION=plan / status / create / loop`; the runner holds the keys. (A new workflow file cannot be dispatched until it is on the default branch, so the loop rides frankie_box_run.yml like the Jev Pod.) |
| `research/kalshi/frankie_boss/pod_root/controller.py` | runner | the loop: queue, claim, inputs, job, import, clean |
| `research/kalshi/frankie_boss/pod_root/pod_agent.py` | Pod / worker box | one day's ROOT per slot; ship back; clean on command |
| `research/kalshi/frankie_boss/pod_root/pod_bootstrap.sh` | Pod | the box's own `frankie_box_worker_setup.sh` + producers + agent |
| `research/kalshi/frankie_boss/pod_root/pod_transfer.py` | all three | presigned PUT/GET, 4 GiB chunks, zstd tar, sha256 manifest, verify |
| `deploy/aws/box/frankie_box_pod_root.sh` + `.py` | main box (SSM) | enable / queue / claim / export / import / release / status; worker box: work / jobs / clean / reupload |
| `deploy/aws/box/frankie_box_root_claims.py` | main box | the claim store |
| `deploy/aws/box/frankie_box_experiment.py` (hook) | main box | the `root` stage claims each day first; unchanged while the store does not exist |

## 2. The Pod

- **SKU**: RunPod secure cloud `NVIDIA A100-SXM4-80GB`, 1 GPU, **16 vCPU, 125 GB RAM** (the minimums
  `operations/pod_prepare.py` requests: "the A100 SXM secure listing"), **$1.59/h** each as billed on 2026-09-28
  (US-MD-1, `HANDOFF_20260928_R6_LAUNCH.md`; 4 Pods = $6.36/h). Taken from the code and handoffs, not re-read from
  RunPod's price page today. **The ROOT uses no GPU** (CPU code only), see open question 1.
- **Image and disk**: `ubuntu:24.04`; container disk 50 GB; a persistent volume **500 GB at `/opt/frankie-box`**
  (`--volume-gb`), so the box's layout and every absolute path the ROOT records are the same as on the main box, and a
  Pod restart keeps the venv, the checkouts and the job states. Port `8081/http` through the RunPod proxy
  (`https://<pod>-8081.proxy.runpod.net`, the same proxy the Granite Pods use), bearer token `POD_TOKEN`.
- **Code and venv, same pins as the box**: the Pod's entrypoint fetches `pod_bootstrap.sh` from GitHub at the pinned
  commit (the repository is public) which runs **`deploy/aws/box/frankie_box_worker_setup.sh` unchanged**: the same
  Python 3.13.15 build (actions/python-versions) and the main box's exact 75 pins, `/opt/frankie-box/markets` at the
  commit. The agent adds per job: the job's commit as a clean worktree `/opt/frankie-box/code/<commit>-pod-1/markets`
  (the ROOT script requires `/opt/frankie-box/code/*`, clean, HEAD = MARKETS_SHA) and the pinned producers checkout
  `/opt/frankie-box/producers` (lineage `ccode/frankie-receiver-feed-20260916` at `2ebb8ce8`), its ten producer files
  checked against the sha256 pins of `frankie_box_stage_producers.sh`; the pip freeze is compared with the 75 pins and
  recorded in each job's `setup.json`.
- **One day per Pod, every CPU** (Greg, 2026-09-29 18:15Z: "Give each day the entire A100's CPUs and as big a worker
  load as ROOT can handle"). The experiment ROOT's only parallel knob is `DATA_WORKERS`: the conformance read of the
  journal (`CompactConformanceReader`, workers from `frankie_journal_reader.worker_budget` = the process's CPU set minus
  its first CPU, capped at the request). The legacy pass that follows is the causal V4-adapter replay on one core by
  design (`Session.derive`, bedrock off); bedrock off also skips the traversal whose 15 processes made Monday's ROOT
  parallel. No thread environment variable is read on this path. Settings, copied from Monday's ROOT
  (`HANDOFF_20260928_SIDE_BUILDER_DISK.md`: `DATA_WORKERS: 48`, a cap): `POD_SLOTS=1`, `DATA_WORKERS=48`, the ROOT pinned
  to every usable CPU of the Pod (its affinity set, cut to the cgroup `cpu.max` quota when one is set), so on 16 vCPU
  the reader runs **15 workers + the parent**. The agent records `cpus`, `usable` and `reader_workers` per job.
  (`--slots 2` would split the CPUs in equal pinned shares; not used.)
- **Pinning plan** (Greg: "Start pinning workers to certain CPUs"): the ROOT process is started with affinity = all N
  usable CPUs (N read at job start, recorded); the reader leaves CPU 0 to the ordered consumer (the ROOT parent) and pins
  its N-1 workers one per CPU on CPUs 1..N-1 itself (`_assign_cpu`, one CPU each, never two on one); the legacy pass and,
  on classroom-arm days, the digest then run in the parent on one core. With bedrock off the digest writes only the five
  sequential legacy tables: the 16-core projection pool (`write_table_parallel`, CPUs >= 2) is used only for bedrock
  tables and is not reached. The parent itself is not hard-pinned to CPU 0 (that needs a change inside the ROOT; not
  made): it keeps the full set, and CPU 0 is the one no worker takes.

## 3. The gate and the claim

- **Ready** (box `ACTION=queue`, the orchestrator's own functions): the day is in the run's saved `plan.json`; its sealed
  ingest exists (the run's ingest step receipt, else `ingest_of`); **the day file is attached beside it**
  (`attached_day_file`: `day-external.json` + `day-external-receipt.json`, sha256 equal); no finished ROOT (`root_of`);
  no claim; no `frankie_box_experiment_root.py` of that day running on the box and no unfinished attempt written in the
  last 30 min. The gate is re-checked at claim time, again on the Pod before any calculation (the job stops at
  `failed_gate`), and the box refuses to place a ROOT whose `calculations-receipt.json` does not say `external.status =
  attached` with the sha256 of the day file attached on the box. `EXTERNAL_WAIT=off` does not apply to this path.
- **Not for Pods** (`box_only`): Monday 20211004 (gold standard, never rebuilt); a day that opens with another day's
  closing book read from outside its own ingest directory (the ROOT would read a path the Pod lacks); a confirmation
  day without the frozen survivor list.
- **The claim** (`frankie_box_root_claims.py`): one file per day, `/opt/frankie-box/work/root-claims/<run>/<day>.json`,
  created O_CREAT|O_EXCL on the main box (exactly one creator wins) with `{run, day, where, attempt, commit, started}`.
  Every runner takes it before a ROOT starts: the orchestrator locally (`where = box:<instance>`), a Pod or a worker box
  through the runner's SSM call of `ACTION=claim` (`pod:<id>`, `worker:<instance>`). Finished: `<day>.done.json` beside
  it (the day is never claimed again). Failed / lost: renamed to `<day>.released-<utc>-<n>.json` plus a `.reason.json`
  (never deleted) and the day is ready again. An S3 `If-None-Match` object was the alternative; the main-box file was
  chosen because the orchestrator can check it locally with no credential and SSM is the only path every runner has.
- **Box side of the claim (how a box takes a claimed day)**: the orchestrator's `root` stage, before starting a ROOT,
  claims the day. If a Pod holds it, the stage records `waiting` with the holder ("its ROOT runs there and lands under
  experiment-roots; the next start reuses it"). When the Pod's ROOT has been imported, the next orchestrator start finds
  it with `root_of()` and records `reused`, then runs teacher, classroom, reports, data, search on it. A claim of this
  box whose ROOT no longer runs (an orchestrator that stopped) is released and retaken. While
  `/opt/frankie-box/work/root-claims` does not exist the orchestrator does exactly what it did before; the controller's
  `loop` creates it (`ACTION=enable`).

## 4. Moving the bytes

The box's role has **no S3 write** and no Pod credential; the Pods hold **no AWS credential**. The runner presigns every
URL (SigV4, `--url-hours` 72, max 168; shorter if the runner's keys are session keys) and hands the box a private map by
`MAP_URL`, exactly as `frankie_box_run.yml` does. Transfer objects live in
`s3://frankie-granite42-568968024170-us-east-1/pod-root/<run>/<attempt>/{in,out}/` (us-east-1, the box's region) and are
deleted as soon as the box import verified them.

- **In (box -> Pod)**: the ROOT reads `ingestion-receipt.json`, `completion.json`, the journal (10-28 GB),
  `opening-book.c15.json` (when the ingest warmed its own book), `day-external.json` + its receipt (+ the frozen
  survivor list on a confirmation day). The **Monday gold standard is not needed**: the ROOT reads only the day's own
  sealed ingest. For a runner-ingested day (`ingest-<day>-gh-<run>-<attempt>`) the receipt, completion and journal are
  already on S3 (`frankie/ingest/<day>/gh-.../`) and the day file at `frankie/day_external/<day>/`: the Pod reads those
  directly (same bytes; the Pod checks every sha256 anyway). Anything else the box uploads itself (`ACTION=export`)
  through presigned PUT slots cut in **4 GiB parts** (S3's single PUT limit is 5 GB; no multipart, so no completion step
  the box cannot do). The Pod places each file at the **same absolute path** as on the main box, so the ROOT's source
  binding, pins and receipts are byte-for-byte what a box run writes.
- **Out (Pod -> box)**: after the ROOT, the Pod deletes its ingest copy (scratch), then streams **the whole ROOT
  directory** plus its evidence as one zstd (level 3) tar in 4 GiB chunks to presigned PUT slots (64 slots = 256 GiB
  compressed per day by default), then a manifest (every file's bytes and sha256, every directory, every chunk's
  sha256). The box (`ACTION=import`) streams the chunks back (each chunk's sha256 checked), extracts into a dot-named
  staging directory, **re-reads every file and compares bytes + sha256 with the manifest (nothing missing, nothing
  extra)**, checks the ROOT is this day's (the source binding names the box's own journal path and sha256; the day file
  is the one attached here), then renames the ROOT directory whole into
  `/opt/frankie-box/work/experiment-roots/<run>-<day>-a<N>` (the name `root_of()` / `Run.root` expect: `N` = the box's
  attempts of that day + 1, fixed at claim time) and the evidence into
  `/opt/frankie-box/work/experiment-pod-roots/<run>-<day>-a<N>/` (`pod/` + `transfer-manifest.json` +
  `import-receipt.json`). Disk floor 100 GB. Only then does the runner tell the Pod to clean.

### What is kept, what is scratch

| Kept (moved to the main box) | Scratch (deleted on the Pod) |
|---|---|
| the ROOT directory whole: `calculation-pins.json`, `source-binding.json`, `calculations-receipt.json`, `progress.json`, `work/derive.json`, `work/derived/legacy_*.json`, `work/derived/.rows/*.jsonl` (every INPUT record, prices, frames, structures, failures), the digest + `digest-proof.json` on classroom-arm days, `out/`, anything else the ROOT wrote (nothing pruned) | the day's ingest copy (journal, receipts, completion, opening book, day file): deleted right after the ROOT, the originals stay on the box |
| a failed or interrupted attempt's directory, placed as an interrupted attempt exactly as the orchestrator keeps one, and the claim released | the transfer chunks (deleted as each is uploaded) |
| the Pod's evidence: the job without URLs, `root.log`, `agent.log`, `setup.json` (commit, producer pins, freeze diff, host), receipts the ROOT wrote under `/opt/frankie-box/receipts` | the ROOT directory on the Pod, after the box verified every file |
| the import receipt (counts of files and bytes verified, problems listed) | the S3 transfer objects, after the same verification |

Kept on the Pod between days (reuse, not scratch): the venv, Python, the markets clone, the code worktrees, the producers
checkout, each job's small `state.json` and logs.

## 5. The loop (persistent Pods)

`frankie_box_run.yml script=deploy/aws/box/frankie_box_pod_root_loop.sh variables="ACTION=loop ..."` runs the controller
up to `BUDGET_MINUTES` (330; a GitHub job lasts at most 6 h). One thread per worker, every poll (60 s): the worker's finished jobs are handled (uploaded -> import -> verified -> clean
the Pod -> delete S3; failed before the ROOT -> release the claim -> clean; failed upload or interrupted -> fresh slots,
re-ship), then a free slot takes the next ready day (claim -> inputs -> job). It keeps polling while days wait for their
day file, so a day starts within one poll of its day file being attached. The state is durable (claims on the box, jobs
on the Pods, bytes on S3), so the controller can be re-dispatched any time; running ROOTs do not stop when it exits.
**Pods are never stopped or deleted by this path**: an idle Pod keeps billing until Greg stops it
(`frankie_pod_control.yml action=stop pod=<id>`).

Worker boxes (`boxes=i-...@region`): the same agent, run detached over SSM, one slot, only when the parent names the box
(after its ingests). Caveat: while a job runs there, the day's ingest copy sits under that box's `work/ingest-*`, where an
orchestrator on that box would see it as a sealed ingest.

## 6. Time and cost per day

- **ROOT hours per day: UNKNOWN (never measured).** The bedrock-off experiment ROOT is built but has not run on any day.
  Nearest measurements: the ingest's single-threaded causal replay of the same V4 adapter, 1.77 ms/record on Monday
  (2,032,203 records, ~1 h, `CODEX_HANDOFF_20260922.md`); the ROOT's legacy pass does that replay plus spooling and
  book transitions on one core, so more than that. Not an estimate to plan on.
- **Pod cost per day** = $1.59 x (ROOT hours + transfer hours), one day per Pod. Transfer in: the journal from S3 at an
  unmeasured rate. Transfer out: the ROOT's size is unmeasured for a bedrock-off day (the Monday ROOT's `.rows` alone
  were 57 GB, with bedrock).
- **Egress**: S3 -> Pod for the inputs, about $0.09/GB (10-28 GB journal: ~$0.90-2.50 a day); Pod -> S3 and S3 (us-east-1)
  -> box (us-east-1) carry no transfer charge.
- Measure on the first day: `root_seconds`, `root_max_rss_kb`, bytes and compressed bytes are in the Pod state, the
  manifest and the import receipt.

## 7. Dispatch order (each step on Greg's go)

1. Stage a commit that holds this code: `frankie_box_run.yml script=deploy/aws/box/frankie_box_stage_code.sh
   variables=ACTION=stage` -> `CODE_ROOT`. The orchestrator must run on a commit with the claim hook before Pods start
   (or run without the root stage), because an older orchestrator does not check claims.
2. The run's plan must be saved on the box: the orchestrator started once for the run (e.g. `STAGES=fetch,ingest,external`).
All through `frankie_box_run.yml` with `script=deploy/aws/box/frankie_box_pod_root_loop.sh` (a runner step; nothing runs
on the box from the marker itself; the controller calls the box over SSM):

3. `variables="ACTION=plan RUN=<RUN> CODE_ROOT=<CODE_ROOT>"`: read-only, no cost.
4. `variables="ACTION=create COUNT=4 CONFIRM=CREATE_4_PODS RUN=<RUN> CODE_ROOT=<CODE_ROOT>"`: 4 Pods, billing starts
   (~$6.36/h); the Pod ids are printed.
5. `variables="ACTION=loop RUN=<RUN> CODE_ROOT=<CODE_ROOT> PODS=<id1,id2,id3,id4>"`; re-dispatch before 6 h while days
   remain (one loop at a time: its own concurrency group).
6. `variables="ACTION=status RUN=<RUN> CODE_ROOT=<CODE_ROOT> PODS=<ids>"` any time. When the queue is done: stop the Pods
   (`frankie_pod_control.yml`), Greg's word.
7. Restart the orchestrator for the run: the imported ROOTs are `reused`; teacher, classroom, reports, data, search go on.

## 8. Open questions for Greg (not assumed)

1. The ROOT is CPU-only; the A100's GPU sits idle. Keep A100 Pods (16 vCPU/125 GB at $1.59/h), or use RunPod CPU
   Pods for ROOT?
2. The 4 A100 Pods from 2026-09-28 run the Granite image (vLLM, no shell): this path cannot use them without resetting
   their container, so it creates new Pods. Are the old ones still needed (the full run's critic), or should they be
   stopped?
3. `DATA_WORKERS=48` (Monday's cap; 15 effective on 16 vCPU) on the Pod vs the orchestrator's default 1: the source
   binding records it; the calculations read the same records. Acceptable?
4. Days ingested with deferred verification (`conformance.json` not yet written): may their ROOT start before
   `ACTION=conform`? The queue lists `conformed`; neither the orchestrator nor this path waits for it today.
5. RAM per ROOT is unmeasured (one day per 125 GB Pod; `root_max_rss_kb` is recorded on the first day).
6. Worker boxes: may the twin i-0d17573dbce871520 and i-08cee7171c0a76a04 take ROOT days, and when (after their
   ingests)? Is the twin set up (`frankie_box_worker_setup.sh`)?
7. Idle Pods bill: stop each Pod when the queue has no ready or waiting day, or keep them up for the next batch?
8. Enabling the claim store changes the orchestrator's root stage (it claims first). OK to enable at the first loop?
9. The runner's AWS keys: if they are session keys, presigned URLs expire with the session (a long ROOT could outlive
   its upload slots; the loop then re-issues them on `failed_ship`).
