# HANDOFF 2026-09-30 ~02:45Z (early): days PAUSED after ROOT, agreed day workflow, traffic controller to build

Branch `claude/frankie-monday-cycle-0-urozez` (no merge base with trunk). Read with `DROP_IN_20260930.md`. Supersedes
`HANDOFF_20260929_NIGHT.md` (kept for history). Session: https://claude.ai/code/session_01VYXDCR7cYp9dmeoJqMqxLJ
Greg: start a NEW chat from this so old material is not dragged back in.

## Greg's standing calls (all in force)
- TOP RULE: filling every open space (free cores on main and the twin, every Pod) with days comes before any other work.
- A DAY NEVER LEAVES ITS SLOT (Pod or box) UNTIL EVERY KEPT STEP OF THE DAY IS DONE ("no more days quit before the end").
- The experiment day workflow = MONDAY'S RUN WITH FEWER STEPS (table below). DROPS CONFIRMED ("The drops are right").
- ZERO PROCESS CODE CHANGES until the workflow is fixed; then build the traffic controller to the table.
- PAUSE (02:40Z): days stop after their ROOT; no new days start until Greg's go.
- DAYS STAY WHERE THEY ARE (Greg, 2026-09-30 ~02:50Z: "leave the days in their boxes and pods to resume once we get
  our end right"): each Pod keeps its day and its finished ROOT on the Pod (no loop import, no clean, no delete, no stop,
  no new claim); main's 20231003 / 20221019 ROOTs stay in main's experiment-roots; the 6 earlier days stay on main. Each
  day RESUMES IN ITS OWN BOX OR POD when the traffic controller is built to the run table and Greg says go.
- Standing: 16 CPUs per day run (booked in the ledger, never fewer), 8 per ingest day process, never double-book; FIFO by
  arrival; ingestion #1 until all 31 days ingested; never stop a running job; no data dropped; counts never averages;
  py_compile / bash -n only; [skip ci] on every push; restage after every push; nothing long on a 6 h GitHub runner;
  before ANY placement count the live processes; codebase-memory MCP is a directive (index `deploy/aws/box` as
  `frankie-box` and `research/kalshi/frankie_boss` as `frankie-boss`: the whole repo times out at 60 s).
- Standing go on Jev Pods (one per trade day, deleted after). Granite only VOICES the post-class discussion (R17 amended);
  never calculations.

## THE RUN TABLE: the agreed day workflow (Greg, 2026-09-30: "I like your run plan"; drops confirmed)
| # | Monday step (what it hands on) | Experiment day |
|---|---|---|
| 1 | Fetch + ingest: sealed journal and receipt | KEEP |
| 2 | 13-point day file beside the ingest (Frankie, both teachers and the search read it) | KEEP |
| 3 | Authorship | DROP |
| 4 | ROOT calculations: derive.json, 5 legacy layers, row spools, digest on classroom days: ROOT hands its sheets to Frankie | KEEP (bedrock off) |
| 5 | Trading-day preparation part 1: the native context walk | DROP |
| 6 | Trading-day preparation part 2: the BOSS teacher (JournalTeacherR3) reads Frankie's ingest (every level, whole day) -> Dipole rows | KEEP |
| 7 | Principal inputs + host config | DROP |
| 8 | Launch/cycle: context, principal model call, Granite B2 critic | DROP, except the classroom pieces below |
| 9 | Classroom package: prepare_integrated_cycle (ROOT's sheets + teacher rows + day file) | KEEP |
| 10 | Classroom: the principal's classroom stage answered by Frankie's code (19 components, summary, correction), finishing his calcs from ROOT's sheets | KEEP |
| 11 | The meeting: Frankie + the BOSS teacher + the scientific teacher (the search), Granite opening and voicing the conversation (CLASSROOM_RULES_V2, R17 amended) | KEEP (Granite voice call NOT wired: Run.voice records not_wired; needs Greg's go on the Session.boss edit) |
| 12 | Frankie's brain entry: classroom ledgers + his lessons | KEEP |
| 13 | Record / correction / retain | DROP, except the brain entry and the day reports |
| 14 | Jev: blind outside student, his own Pod, claims only | KEEP |
| 15 | Experiment-only: data export, search, lessons, day reports (CLASSROOM / FRANKIE / JEV REPORT #N) | KEEP |
Dependency order found tonight (from the code, for the builder): teacher rows before the classroom package; data export and
search BEFORE Frankie's class (Frankie's lessons and the three-way exchange need the day's search; the exchange also needs
the batch lessons). A day waits IN its slot for its class (one class at a time, school-day order); its CPUs stay unbooked
while it waits so the class books them (no deadlock).
FIRST-RUN CHECK (Greg): the first time Frankie runs his part, ask him "is this the right order of the day's steps?" and
record his answer in the day report before the order is locked (his classroom is code: ask through his session or the
meeting's Granite voice once wired; if neither can, tell Greg). Also written into SPEC-experiment-orchestrator.md.

## What was wrong tonight (root cause)
The ROOT-line worker (frankie_box_frankie_queue.py, "the traffic controller") released a day's 16 CPUs the moment its ROOT
ended; the next day took the slot within seconds; the teacher then found "0 free of 16 needed", recorded waiting, and the
orchestrator ended (run 36630611178, exit 3). So 6 days stopped after ROOT: 20211005, 20211006, 20211012, 20211013,
20221004, 20221005 (all ROOT done, receipts clean; none reached teacher, Frankie or Jev; class line never created).
The code was built that way; nothing crashed.

## State at 02:45Z (verify by receipts first thing)
- MAIN i-035994afa8bdf66a5 (32 CPU, ~1.25 TB free): ROOT 20231003 (CPUs 16-31) and ROOT 20221019 (CPUs 0-15), run
  days-20260930-1, under the ORIGINAL ROOT worker pid 86310 (code f86bb7c2), which got SIGTERM: it takes no new days and
  ends when those two ROOTs end. Then main is EMPTY (paused, by design).
- The waiting worker at 1be6bce8 (deadlock) was STOPPED (pid 96169; receipt
  /opt/frankie-box/receipts/stop-waiting-worker-2026-09-30T022409Z.json). No other worker is waiting.
- Orchestrator days-20260930-1 (detached, pid 89607): STOPPED while waiting at 02:28:00Z (run 36659940928; receipt
  /opt/frankie-box/receipts/stop-orchestrator-days-20260930-1-2026-09-30T022800Z.json). Its finished steps keep their
  receipts (ingest reused x11, external done x11, ROOT line entries); a later start skips them.
- 4 ROOT Pods (A100, $1.59/h each, created 01:21Z at f4d20539, agents up by 01:39Z): 0o3wfhj6vxvqis 20221011,
  kj93q89dnpuhdp 20221012, tthwp8ztjxhqcw 20221018, s8u7611dxa5i24 20211020 (this one is capped at 14 usable CPUs).
  ROOTs started ~01:45-01:50Z. The Pod loop (run 36656174396) was CANCELLED (pause): no new claims; finished ROOTs wait on
  the Pod/S3 until a loop runs again to IMPORT them to main (a new loop would also claim the queued days: decide first).
  Pods keep billing while idle: stop only on Greg's word.
- TWIN i-0d17573dbce871520 (16 CPU): ingest 20251021 (run 36653790488, WORKERS=7 deferred) + conform 20211019
  (run 36653793146). ~40 GB free.
- 8-CORE i-08cee7171c0a76a04 (us-east-2): ingest 20251007 (run 36654357901, WORKERS=7 deferred). 20241001/02 finished earlier.
- Day files (13 points) ATTACHED tonight for 11 days (run days-20260930-1): 20211020, 20221011, 20221012, 20221018,
  20221019, 20231003, 20231004, 20231010, 20231011, 20231017, 20231018. The 6 earlier days already had theirs.
  Confirmation days get NO day file until the survivor list is frozen.
- ROOT line on main: seq 1-6 (days-20260929-3) done; seq 7-10 on Pods; 11-12 on main; 13-17 queued (20231004, 20231010,
  20231011, 20231017, 20231018).
- Old Pods: 4 frankie-root-09292103 (rf8eux1c88pfn0, xfpt6fy3mjkn4l, 6ijaa67k785doa, lunj1qj145rswp) EXITED, cannot resume
  (Runpod 402 on resume; create works); 4 frankie-root-09291832 and 6 granite-smoke EXITED. Delete only on Greg's word.

## Code on the branch (all [skip ci], py_compile / bash -n only)
| commit | what | live? |
|---|---|---|
| 4801bee4 | orchestrator DETACH=on (systemd unit, never a 6 h runner) | used for days-20260930-1 |
| 21c622af | presign_items uses each member's archive_key | used |
| 1cb83635 | frankie_box_run.yml: plan / status / DETACH starts get their own concurrency group | live |
| 4ce74a1f, ba387059, 1be6bce8, 966f1442 | ROOT worker whole-day attempts (966f1442 = dependency order + ACTION=handover) | NOT live; do not hand over; rebuild the controller to the run table instead |
| 1055c818 | control: frankie_box_stop_waiting_worker.sh | used (02:24Z) |
| 0cdae5cc | control: frankie_box_stop_orchestrator.sh RUN=; drops confirmed; pause recorded | used (02:28Z) |
Staged on main: /opt/frankie-box/code/966f14425555f846286aefa3d0680f387eb7d58b-36659164910-1/markets (not used). Restage the
new tip before any dispatch that checks MARKETS_SHA.

## Open for Greg
1. Go to build the traffic controller to the run table (the ROOT-line worker + the Pods), then restart.
2. Granite: go on the Session.boss edit (system role = charter, per-call deadline) and a Granite Pod per meeting.
3. The Pods: after their ROOTs, keep idle or stop? Import their ROOTs with a loop now (it would claim queued days too)?
4. DuckDB on main for the search (frankie_box_venv_duckdb.sh ACTION=install): not verified installed.
5. Delete-on-word: old Pods + volumes; twin's local 20250930/20251001; main's 20251014 (all on S3).

## Next ingest work (ingestion #1)
20211019: after its conform, archive twin -> S3 -> restore on main (frankie_box_archive_day.sh plan/upload/verify, then
restore on main), then its day file. 20251008 on i-08cee after 20251007. Conforms owed: 20221004, 20221005, 20211020.
Consensus requests 3/4 or the multi-region fetcher (not built).
