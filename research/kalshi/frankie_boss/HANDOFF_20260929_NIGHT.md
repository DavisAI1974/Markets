# HANDOFF 2026-09-29 ~21:10Z (night): day runs on 16 booked cores, 4 new ROOT Pods booting, ledger + FIFO queue + exchange built

Branch `claude/frankie-monday-cycle-0-urozez` (no merge base with trunk), tip `f86bb7c2` at close. Read with
`DROP_IN_20260929_NIGHT.md`. Earlier today: `HANDOFF_20260929_EVENING.md` (+ its addenda, written by the previous chat).
Session: https://claude.ai/code/session_01AbJHiaG5VPQxUinLQhyMVB

## Greg's standing calls from this chat (all still in force)
- CORES: every remaining-day run gets exactly 16 CPUs + its workers, never fewer; it WAITS until 16 are truly free. Never
  double-book a core or a worker. An ingest day process gets 8. Now enforced by code (the core ledger, below).
- ORDER: first in, first out, by ARRIVAL, not trading date. The 10th never needs the 9th for calculations, so the ROOT
  line is arrival-FIFO. CLASS days are sequential: class 1, then 2, ...; one class at a time; each class carries the class
  finished before it; school-day number = report number N (CLASSROOM/FRANKIE/JEV REPORT #N).
- FILL THE PODS FIRST with waiting day runs; boxes take a day when 16 cores are free.
- CLEAN BEFORE FILL: when a slot/space opens, clean trash and move important data to S3 before the next job fills it.
- Frankie doing the computes (code, no model) is fine. Granite may only VOICE the post-class discussion of the three seats
  (Frankie, BOSS teacher, scientific teacher) - never calculations. CLASSROOM_RULES_V2 (R17 amended) is committed.
- Standing go on Jev Pods: one per trade day, deleted after.
- Consensus: use the captures already on S3 (history run 36576414768) and override the receipt gate (missing receipt is
  listed as missing, never blocks). Greg also wants the consensus fetch run across regions with no runtime limit (boxes,
  not 6 h GitHub runners), each capture landing as it arrives - NOT BUILT.
- Ingestion #1 until all 31 days are ingested; never stop a running job; counts not averages; no data dropped;
  [skip ci] on every push; restage after every push; tell Greg before a push (he gave a standing go for finished work).

## What is running at close (verify by receipts first thing)
- MAIN i-035994afa8bdf66a5 (32 CPU, ~1.2 TB free): orchestrator run days-20260929-3 (GitHub run 36630611178, code
  f86bb7c2, CODE_ROOT=/opt/frankie-box/code/f86bb7c2994ca1e81eb84cd40ddb384f32b06afa-36629379426-1/markets,
  STAGES=root,teacher,classroom, PARALLEL_DAYS=2). Ledger bookings: 20211005 ROOT on CPUs 0-15, 20211006 ROOT on 16-31.
  The ROOT line holds 20211012, 20211013, 20221004, 20221005 for the Pods. 20211005 is BOX-ONLY (opens with Monday's
  closing book from the recovery receipt).
- 20251014 archive VERIFY (run 36630605941) was running (plan 13,524,605,735 B / 9 pieces, uploaded 20:51Z). Local copy
  is kept until Greg says delete.
- Consensus request 2 = 36618331994 (families=consensus, all 8 days) still running since 19:18Z; Wayback 503s. When it
  lands: day files are never overwritten - re-attaching needs Greg's call (move-aside or new run).
- TWIN i-0d17573dbce871520 (16 CPU, 43 GB free): IDLE at close. 20211019 SEALED (deferred verify: conform pending),
  20251015 SEALED, 20250930 + 20251001 SEALED and ARCHIVED to S3 VERIFIED (local copies kept; delete on Greg's word).
- i-08cee7171c0a76a04 (us-east-2, 8 CPU): 20241001/02 inline verify still running (were 61% / 81% at 20:0xZ).

## Pods
- NEW 4 ROOT Pods (A100, $1.59/h each), created 21:03Z at f86bb7c2 with the FIXED boot: rf8eux1c88pfn0, xfpt6fy3mjkn4l,
  6ijaa67k785doa, lunj1qj145rswp (registry s3://frankie-granite42-568968024170-us-east-1/pod-root/pods/). At 21:06Z all
  four answered HTTP 502 "Waiting for service to respond" = container up, agent still booting (apt, Python 3.13.15, 75
  pins incl. torch). The create run 36630617830 watches them up to 40 min and prints "POD <id> agent up".
  If a boot fails it now answers HTTP 503 with the failing step + log tail (ACTION=status prints it whole).
- To FILL them (next chat, Greg: "we will fill them in next chat"): frankie_box_run.yml
  script=deploy/aws/box/frankie_box_pod_root_loop.sh variables="ACTION=loop RUN=days-20260929-3 CODE_ROOT=<staged f86bb7c2
  root or newer> PODS=rf8eux1c88pfn0,xfpt6fy3mjkn4l,6ijaa67k785doa,lunj1qj145rswp" (re-dispatch before 6 h). Claims follow
  the ROOT line (refuses behind_in_root_line / not_in_root_line).
- OLD 4 ROOT Pods (43gf98vq9uvyre, yw57n1o2bi8cgz, qpk5n335z2d32k, 5tllncuexmpzek; MARKETS_SHA 0c0b4afb baked in, broken
  boot): a STOP was dispatched on my misreading of Greg's "Go"; the session's safety check then blocked follow-up, so
  their state is UNVERIFIED. They can never run the fixed boot (no env PATCH route). 500 GB volume each: delete only on
  Greg's word.
- EXITED, not billing GPU: 4 Granite-image A100s (kqp1qwzv6vo67a, x2vprjb4cs2ulu, mhj0jwod7yfdz5, vbh922dqk8x2f9) and 2
  L40S (fhiwwlouzyx6l2, g7y3g2w1kor4l3). kqp1 resume was refused (no free GPU on its host).
- Root cause of the 2 h of dead Pods: stock ubuntu:24.04 has no python3; the worker setup pipes the python-versions
  manifest into python3 before 3.13.15 exists; under set -eu the boot ended before the agent, every restart (fixed d92d978f).

## Built and pushed this chat (all [skip ci], py_compile / bash -n only, none tested on a box unless noted)
| commit | what |
|---|---|
| 6679c2e4 | sealed-day -> S3 archive route: frankie_box_archive_day.sh/.py plan/upload/verify/restore, putarchive slots, no delete. RUN on 20250930, 20251001 (verified) and 20251014 (upload done, verify running) |
| f0380110 | 3-way exchange stage (code only: BOSS teacher from its Dipole rows, scientific teacher from the search counts, Frankie's code replies), school knowledge base brain/school/<day>.json + index.json, voice STUB, reports after the exchange, build plan C36-C38/G27-G28 |
| 09c3ce68 | CLASSROOM_RULES_V2 (R17 amended: Granite may only voice the post-class discussion); classroom reads V2 (cache identity changes, rebuild accepted) |
| d92d978f | Pod boot: apt python3; failed boot serves HTTP 503 + failing step + log tail; controller prints 503 whole |
| 4582b7ca | CPU booking ledger frankie_box_cores.py/.sh: /opt/frankie-box/cpu-bookings/, day run books exactly 16 or waits (exit 75), ingest 8 per day process (inline verify = WORKERS*2+1), jobs start under taskset; ACTION=show probe. LIVE on main now |
| f86bb7c2 | Frankie's FIFO queue frankie_box_frankie_queue.py/.sh: ROOT line + class line, arrival order, one class at a time, school day = report N, detached systemd-run workers, own concurrency groups. ROOT line LIVE on main now |
Also: GRANITE_DISCUSSION_VOICE_ROLE_V1.md (Granite's explicit charter; DRAFT until the voice is wired).

## NOT done / open
1. Granite VOICE call: blocked. The edit to Session.boss in frankie_box_boss_session.py (optional system role = the
   charter, and a per-call deadline; it retries forever today) was refused by the session safety check ("Create Unsafe
   Agents"). Needs Greg's direct approval IN the session, then build the voice stage (the validator and the turn format
   already exist: frankie_box_exchange_voice.py). No Granite Pod exists for it yet.
2. Day files for 20211019 and 20211020 (both sealed now) - consensus for prints 2021-10-14/10-21 is in history run
   36576414768; attach with the orchestrator external stage in a new run name.
3. Conforms owed (deferred verify): 20221004, 20221005, 20211019, 20211020.
4. Remaining ingests: 20251021 (partitions fetched on main), 20251007/08 (fetched on i-08cee, after 20241001/02).
   Twin is idle now - use it (16 CPU = two 8-core ingest slots, or one 16-core day-run slot once the day is on it).
5. Consensus requests 3 (six 2023 days) and 4 (13 confirmation days) not dispatched. Multi-region no-limit consensus
   fetcher: not built.
6. Code fix owed: frankie_box_experiment.py presign_items (398-404) builds partition keys from archive_prefix and ignores
   member archive_key (404s for 20211011-13, 20221003-05); worked around by hand-corrected presign.
7. Queue agent's decisions for Greg (defaults applied): school files keep the by-trade-date leakage wall; a failed class
   day stops the class line (retried once, never skipped); Pods wait while a box-only day heads the ROOT line; first class
   carries the newest finished classroom on the box; a second orchestrator start can still replace a pending one.
8. Delete-on-word: twin's local 20250930/20251001 and main's 20251014 (all on S3; 20251014 once its verify passes); the
   old 4 ROOT Pods.
9. Monday 20211004: calculations-only brain entry written (/opt/frankie-box/brain/20211004-cycle-00, 91 MB: digest with the
   5 legacy tables + derive.md). The 43 bedrock layers are not in it (digest V9 design); Greg: not worrying about Monday.

## What went wrong this chat (so it is not repeated)
- 20211019/20 runner jobs hit the GitHub 6 h limit at 18:55Z and their progress was not saved first: ~6 h lost. Rule:
  never put a day that can outlast a hard limit on a GitHub runner; boxes only.
- A day run was started on 16 "free" cores that were not free (an inline-verify ingest ran 14 workers, not 7) -> ROOT
  workers collided on CPUs 1-15. Stopped at 11.62%. Fixed by the ledger; before any placement, count live processes.
- "Go" was read as "stop the old Pods" when Greg meant the queue order. Ask when a one-word go could match two questions.
- The twin fetch failed twice (block manifest prefix is not the S3 key -> use the canonical manifest's archive_key; and
  WORKERS defaults to 31 -> pass WORKERS=7 on a 16-CPU box).

## Addendum 21:17Z: Pod agents
Status check run 36632088486 (21:16Z): rf8eux1c88pfn0 and lunj1qj145rswp UP (agent answers: 14 usable CPUs, Python
3.13.15, markets_commit f86bb7c2, jobs []); xfpt6fy3mjkn4l and 6ijaa67k785doa still HTTP 502 "Waiting for service to
respond" 13 min into boot (no 503 = no failed step). The fixed boot is proven on 2 of 4. First thing next chat: ACTION=status
on all four; if a 502 persists past ~40 min with no 503, the create run 36630617830's log says what it saw. Then the loop.

## Addendum 21:30Z: ALL FOUR new ROOT Pods up
The create run 36630617830 finished success at 21:25:38Z: "agents up ['6ijaa67k785doa', 'lunj1qj145rswp',
'rf8eux1c88pfn0', 'xfpt6fy3mjkn4l']; never started []". Up at: lunj1qj145rswp 21:10:12Z, rf8eux1c88pfn0 21:12:16Z,
xfpt6fy3mjkn4l 21:22:34Z, 6ijaa67k785doa 21:25:38Z (boot 7 to 22 min; the host reports 128 CPUs, the agent's own status
reports 14 usable). No 503, no failed step. They are EMPTY and billing ($1.59/h each, $6.36/h for the four). Greg: "we
will fill them in next chat". The queue at 21:03Z: 20211012 ready, 20211013 / 20221004 / 20221005 behind_in_root_line,
20211005 / 20211006 root_running_on_box. Next chat: ACTION=status once, then ACTION=loop (drop-in step 2).
