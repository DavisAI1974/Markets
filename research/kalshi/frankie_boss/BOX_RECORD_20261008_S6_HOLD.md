# Hold role record, 2026-10-08 01:05-01:2xZ (session 6): pause a2 at the ROOT->teacher boundary on c9bf631

Box i-035994afa8bdf66a5 (us-east-1). Run e2e-20231018-a2, day 20231018, ROOT pid 14860, worker pid 14824
(unit frankie-queue-root-1791413028), booking day-run-20231018-day_slot_root-1791402822-3111.
R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1. Queue Q=/opt/frankie-box/work/frankie-queue.
Staged checkout CODE_ROOT=/opt/frankie-box/code/c9bf631e884813adb79d263c80afd52a7fd9d837-37695921903-1/markets
(git rev-parse HEAD = c9bf631e884813adb79d263c80afd52a7fd9d837, checked on the box).
Nothing killed, removed, moved or tagged. Two files written on the box: /opt/frankie-box/archive/.logs/hold-a2.sh and
its log hold-a2.log. One transient systemd unit started (frankie-hold-a2-20261008T011619Z, --collect).

## 1. Mechanism verified in the c9bf631 source (git show c9bf631:...)

(a) How the worker hands the marker to the ROOT child, and whether it signals the child.
- The worker NEVER sends SIGTERM to the ROOT child on a save (its only SIGTERMs are the handover of the worker itself,
  frankie_box_frankie_queue.py 437-469, and the class worker's own Bound signal, 930). The marker is the only channel.
- frankie_box_frankie_queue.py: _bind_owner (1194-1207) binds owner.marker = SAVE_DIR/<run>-<day>.save-request.json =
  Q/save/e2e-20231018-a2-20231018.save-request.json; _run_for (569-587) does run.bind_owner(entry['owner']).
- frankie_box_experiment.py: bind_owner (1088-1094) sets Run.stop_marker = owner['marker']; save_requested (1096-1098)
  = Path(marker).is_file(); check_save (1113-1116) raises SystemExit(75) when it stands. step() (1276-1279) hands exactly
  that path to every child as FRANKIE_LANE_STOP_FILE; after the child's proc.wait() it calls self.check_save() (1320),
  so a standing marker turns ANY child exit into SystemExit(75) in the day thread; child() (1257-1262) also calls
  check_save() BEFORE each child starts.
- frankie_box_experiment_root.py calculate_day (120-137): SIGTERM handler sets a flag; save_requested() = flag OR
  Path(FRANKIE_LANE_STOP_FILE).exists(). After _calculate_day RETURNS it checks save_requested() and raises
  TeacherSaved('ROOT completion published; resume uses the completed receipt'); TeacherSaved is SystemExit(75)
  (parallel_teacher.py 428-433, prints the message). _calculate_day writes calculations-receipt.json at line 403
  (_save_new_complete, exclusive link) BEFORE returning, so on this path the receipt exists.
- frankie_box_boss_session.py: on a2's route the legacy pass ends at probe 'root-legacy-finalize' (2288), then
  _complete_native_derivation (2563) -> _derive_bedrock(recovery=True) (2655): _await_native_overlap (joins the finished
  native child; it SIGTERMs the child only if alive AND a save stands, 1876), _native_stage (reuses the completed
  native-stage.json, 2696-2713), then THE LAST CHECK at 2667: save_requested() -> TeacherSaved('native calculation
  completion retained; projection remains to be resumed') = exit 75 WITHOUT a receipt. After 2667: _native_projection
  (2728: probe 'root-projection' at 2731, 'root-projection-publication' 2739) has no save check; derive.json,
  write_retained_digest (frankie_box_monday_calculations.py 89: probe 'root-digest') has no save_requested; probe
  'root-derived' (2583-2584); return to _calculate_day -> receipt -> return -> calculate_day's post-return check.
  frankie_box_cores.py `run` forwards the child's exit (75 passes through); frankie_box_stage_progress.py reads the stop
  file nowhere. The disk guard (limit 15 GB, 701 GB free) is not in play.
- So: a marker written once progress.json's stage is root-projection or later lets ROOT COMPLETE: receipt written, exit
  75 "ROOT completion published". Then experiment.py step() check_save -> SystemExit(75) in the day thread BEFORE
  root() records anything (root() 1540-1545 only runs after child() returns normally) -> _root_job except -> _thread_end
  (1569-1576) -> _save_result (1579-1591): holder['root'] is None so the entry becomes state 'saved' (not done),
  reason "saved on its day-bound marker ...", booking RETAINED (1636-1640 retain path), CPUs kept. The teacher is never
  reached (_finish_steps 1346 check_save precedes run.teacher). On the later ACTION=resume, root() finds the completed
  receipt via root_of and records 'reused' (1488-1538), then the finish steps run on the resumed source.
- Had the marker landed BEFORE root-projection (during root-legacy-finalize), ROOT would stop at 2667 with no receipt:
  still saved, but the ROOT would have to resume for its projection. That is why the watcher triggers only on the
  projection-or-later stages or the receipt.

(b) The exact file and when it is read.
- File: /opt/frankie-box/work/frankie-queue/save/e2e-20231018-a2-20231018.save-request.json (owner.marker).
- The ROOT child reads it (os.path exists) at its own check points only: the ones listed above; none inside projection,
  digest or receipt. The worker's Run reads it at boundaries (check_save), not on a poll: before every child start, after
  every child exit, at _finish_steps entry before the teacher. The worker's main loop poll (60 s) does not read it.

(c) ACTION=save on a running day.
- frankie_box_frankie_queue.sh: ACTION=save needs CODE_ROOT (under /opt/frankie-box/code), RUN, DAY, MARKETS_SHA equal
  to `git -C CODE_ROOT rev-parse HEAD`; execs `python -B frankie_box_frankie_queue.py --action save --run RUN --day DAY
  --rebook off`. request_save (2136-2164): accepted when the ROOT-line entry is 'running' (or done with finish running);
  writes the marker create-only (C.write_json exclusive); records entry['save_request'] and event 'save_requested';
  prints JSON {requested:{schema FRANKIE_QUEUE_SAVE_REQUEST_V1, run, day, attempt, booking, cpus, requested_at,
  requested_utc, by:'dispatch save'}, marker, entry_state, note:'the owner stops at its next boundary; ...'}; exit 0.
  A second call: SystemExit('a save request stands already: <marker>') exit 1, nothing changed.
- ACTION=status needs only CODE_ROOT (read-only, owner_status 2167-2197).
Nothing in the code contradicted the plan.

## 2. The watcher (verbatim: /opt/frankie-box/archive/.logs/hold-a2.sh, 3716 bytes, sha256 f47873b1f264eb63...)

Deviation from the brief: the poll is 5 s, not 20 s (one small JSON read; narrows the chance of missing the window
between the receipt and the worker's check_save, which is seconds). Trigger: stage in {root-projection,
root-projection-publication, root-digest, root-derived} or R/calculations-receipt.json exists. Guards: a teacher process
already running -> REFUSED, no marker; a marker already standing -> no second; ROOT pid gone without a receipt -> no fire.
After the trigger: ACTION=status every 60 s for 30 minutes, then exit.

```
#!/bin/bash
# hold-a2: pause run e2e-20231018-a2 day 20231018 at the ROOT->teacher boundary (Greg's standing instruction, 2026-10-08).
# Reads R/progress.json; once the ROOT is past its last pre-projection save check (stage root-projection or later, or
# the receipt exists) it runs the queue's ACTION=save exactly once (never a second marker), then logs ACTION=status
# every 60 s for 30 minutes and exits. Never kills, removes, moves or tags anything.
R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1
Q=/opt/frankie-box/work/frankie-queue
CODE_ROOT=/opt/frankie-box/code/c9bf631e884813adb79d263c80afd52a7fd9d837-37695921903-1/markets
MARKETS_SHA=c9bf631e884813adb79d263c80afd52a7fd9d837
RUN=e2e-20231018-a2
DAY=20231018
ROOT_PID=14860
MARKER=$Q/save/$RUN-$DAY.save-request.json
LOG=/opt/frankie-box/archive/.logs/hold-a2.log
WRAP=$CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh
PY=/opt/frankie-box/venv/bin/python
log(){ echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
stage(){ "$PY" -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("stage",""))
except Exception as e: print("unreadable:"+type(e).__name__)' "$R/progress.json" 2>/dev/null; }
yn(){ [ -e "$1" ] && echo yes || echo no; }
teacher_running(){ pgrep -f 'frankie_box_(experiment|joined|scientific)_teacher' >/dev/null 2>&1; }
log "watcher start pid $$ unit ${HOLD_UNIT:-?} poll 5s; R=$R marker=$MARKER"
n=0
while :; do
  s=$(stage)
  hit=0
  case "$s" in root-projection|root-projection-publication|root-digest|root-derived) hit=1;; esac
  [ -f "$R/calculations-receipt.json" ] && hit=1
  if [ "$hit" = 1 ]; then
    log "TRIGGER stage=$s receipt=$(yn "$R/calculations-receipt.json") legacy-stage.json=$(yn "$R/work/legacy-stage.json") pid$ROOT_PID=$(ps -o stat= -p $ROOT_PID 2>/dev/null || echo gone)"
    if teacher_running; then
      log "REFUSED: a teacher process is already running; not writing a marker"; pgrep -af 'frankie_box_(experiment|joined|scientific)_teacher' >> "$LOG"
    elif [ -f "$MARKER" ]; then
      log "marker already stands; not writing a second"; cat "$MARKER" >> "$LOG"; echo >> "$LOG"
    else
      log "FIRING ACTION=save RUN=$RUN DAY=$DAY"
      out=$(cd / && CODE_ROOT="$CODE_ROOT" MARKETS_SHA="$MARKETS_SHA" ACTION=save RUN="$RUN" DAY="$DAY" bash "$WRAP" 2>&1); rc=$?
      log "ACTION=save exit=$rc"; printf '%s\n' "$out" >> "$LOG"
      log "marker standing now: $(yn "$MARKER")"
    fi
    break
  fi
  if ! kill -0 $ROOT_PID 2>/dev/null; then
    log "ROOT pid $ROOT_PID is gone with stage=$s and no receipt; not firing (nothing to hold at the boundary)"
    pgrep -af 'frankie_box' >> "$LOG" 2>&1
    break
  fi
  n=$((n+1))
  if [ $((n % 12)) = 0 ]; then
    log "waiting stage=$s pid$ROOT_PID=$(ps -o stat=,etime= -p $ROOT_PID 2>/dev/null | tr -s ' ') legacy-stage.json=$(yn "$R/work/legacy-stage.json") marker=$(yn "$MARKER")"
  fi
  sleep 5
done
end=$(( $(date +%s) + 1800 ))
while [ "$(date +%s)" -lt "$end" ]; do
  log "STATUS stage=$(stage) receipt=$(yn "$R/calculations-receipt.json") pid$ROOT_PID=$(ps -o stat=,etime= -p $ROOT_PID 2>/dev/null | tr -s ' ' || echo gone) marker=$(yn "$MARKER") teacher=$(teacher_running && echo RUNNING || echo none)"
  (cd / && CODE_ROOT="$CODE_ROOT" ACTION=status RUN="$RUN" DAY="$DAY" bash "$WRAP" 2>&1 | "$PY" -c 'import json,sys
raw=sys.stdin.read()
try:
  d=json.loads(raw); r=d.get("root_entry") or {}
  print(json.dumps(dict(verdict=d.get("verdict"), entry_state=r.get("state"), finish=(r.get("finish") or {}).get("state"), save_request=bool(r.get("save_request")), marker=d.get("marker"), booking=d.get("booking"), worker=d.get("worker"))))
except Exception: print(raw[-1500:])') >> "$LOG" 2>&1
  sleep 60
done
log "watcher end"
```

## 3. Commands run (SSM AWS-RunShellScript via the Aws connector, SendCommand + GetCommandInvocation)

### 3.1 Arming attempt 1, command 6268b04f-3f52-498c-802f-4d4b131e70dc, 01:14:57Z: FAILED TO ARM (my error)
The base64 placeholder was not substituted into the shell text ("B64: parameter not set"), so hold-a2.sh was written with
0 bytes and unit frankie-hold-a2-20261008T011457Z ran bash on an empty file and exited at once (ActiveState inactive,
SubState dead, MainPID 0; --collect garbage-collects it). No marker written, nothing else touched. State printed then:
stage root-legacy-finalize; legacy-stage.json absent; receipt absent; 14860 R elapsed 02:31:06 46.8% CPU RSS 540612;
no children of 14860 left; save/ = the three .resumed-* archives only; teacher none; units: frankie-queue-root-1791413028
only; root free 701,115,736,064 B.

### 3.2 Arming attempt 2, command e2e9ac2d-dad8-4316-ae34-76f6a64d8d3f, 01:16:19Z: ARMED
```
== CURRENT STATE at 20261008T011619Z
-- stage=root-legacy-finalize (progress.json at: 2026-10-07T23:41:47Z)
-- legacy-stage.json: No such file or directory
-- receipt: No such file or directory
-- ps 14860:   14860 R  02:32:28  47.1%  RSS 540612
-- save/: e2e-20231018-a1-20231018.save-request.json.resumed-1791400389 (18:59:45Z),
          e2e-20231018-a2-20231018.save-request.json.resumed-1791409621 (20:05:24Z),
          e2e-20231018-a2-20231018.save-request.json.resumed-1791413028 (22:32:39Z)   [no standing marker]
-- teacher processes: none
-- frankie units: frankie-queue-root-1791413028.service loaded active running (worker, --scope e2e-20231018-a2:20231018)
-- existing hold watcher: none
-- root volume free: 701115584512
-- watcher script written: 3716 bytes, sha256 f47873b1f264eb63; bash -n: ok
== stage=root-legacy-finalize: not yet at projection; arming the detached watcher
Running as unit: frankie-hold-a2-20261008T011619Z.service
-- unit: MainPID=54716 ExecMainStartTimestamp=Thu 2026-10-08 01:16:19 UTC ActiveState=active SubState=running
-- watcher process: 54716 /bin/bash /opt/frankie-box/archive/.logs/hold-a2.sh
-- log tail: 2026-10-08T01:16:19Z watcher start pid 54716 unit frankie-hold-a2-20261008T011619Z poll 5s; ...
== ARMED frankie-hold-a2-20261008T011619Z at 2026-10-08T01:16:25Z; stage now root-legacy-finalize
```

### 3.3 Follow-up, command 3a57bfd5-1c34-409c-94b3-7ccda1ae30db, 01:17:45Z (read-only, 86 s after arming)
```
-- unit: MainPID=54716 ActiveState=active SubState=running
-- watcher process: 54716 /bin/bash /opt/frankie-box/archive/.logs/hold-a2.sh
-- stage: root-legacy-finalize running (progress.json at 2026-10-07T23:41:47Z)
-- legacy-stage.json: absent;  receipt: absent;  marker: absent;  teacher processes: none
-- ps 14860: R  elapsed 02:33:54  47.5% CPU  RSS 540612
-- newest under R/work: derived/ (mtime 01:10:15Z), native-stage.json 00:15:04Z, legacy-state.pkl 23:41:47Z
-- /proc/14860 open files: work/derived/.rows/frames.jsonl (1), experiment/e2e-20231018-a2/logs/20231018-root.log (2)
-- hold-a2.log tail:
2026-10-08T01:16:19Z watcher start pid 54716 unit frankie-hold-a2-20261008T011619Z poll 5s; ...
2026-10-08T01:17:14Z waiting stage=root-legacy-finalize pid14860=R 02:33:23 legacy-stage.json=no marker=no
```

## 4. Margin estimate
At 01:17:45Z the ROOT is still in the legacy finalize: the 472 GB layer re-read ended about 01:10Z (derived/ mtime
01:10:15Z) and it is now sequentially reading work/derived/.rows/frames.jsonl (496,743,568,399 B; at the ~1.09 GB/s
measured earlier that is ~7.6 min, so roughly 01:18-01:20Z if it reads the whole spool), then legacy-stage.json, the
native join (completed native-stage.json reused: fast), then probe 'root-projection'. The watcher was armed 01:16:19Z,
before any of that: margin at arming >= 2 min on the most pessimistic reading, more likely >= 4 min. It polls every
5 s; the fire window (root-projection through the receipt and the worker's post-child check_save) is the whole
projection + digest + receipt write, minutes long.

## 5. What the hold produces once it fires (from the code, section 1)
ROOT completes: calculations-receipt.json written, child prints "ROOT completion published; resume uses the completed
receipt", exit 75. The worker's day thread raises SystemExit(75) at step()'s check_save -> entry e2e-20231018-a2 /
20231018 state 'saved' ("saved on its day-bound marker ..."), booking day-run-20231018-day_slot_root-1791402822-3111
RETAINED with CPUs 0-31, worker idle on its line, NO teacher. Resume (after the restage): ACTION=resume RUN=e2e-20231018-a2
DAY=20231018 with the NEW CODE_ROOT/MARKETS_SHA, then kick LINE=root SCOPE=e2e-20231018-a2:20231018; root() finds the
completed receipt and records 'reused', then the teacher runs on the new source.
Watch: /opt/frankie-box/archive/.logs/hold-a2.log (TRIGGER / FIRING / ACTION=save exit / STATUS lines every 60 s for
30 min). If the log shows "REFUSED: a teacher process is already running", the boundary was missed and nothing was
written.

### 3.4 Follow-up 2, command 6c7ea070-c62f-4646-bc4c-cb01510403c9, 01:29:44Z (read-only): THE HOLD FIRED
- Marker written 01:20:55Z by the watcher at stage root-projection (receipt=no, teacher=none): /opt/frankie-box/work/
  frankie-queue/save/e2e-20231018-a2-20231018.save-request.json, 498 B, FRANKIE_QUEUE_SAVE_REQUEST_V1, requested_at
  1791422455.8881006 (01:20:55Z), sha256 e5c639e072d5fe6636a427ce23a5a1b16309b39e0bfb0c09b43379b508db2b5b, attempt
  e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_root-1791402822-3111, cpus 0-31, by "dispatch save".
  hold-a2.log: "01:20:55Z marker standing now: yes"; STATUS lines every 60 s from 01:20:55Z: verdict "save pending
  acknowledgment", entry_state running, finish null, save_request true, booking alive (retained null), worker 14824
  running (running [2], pending 1, stop null), teacher none.
- ROOT timeline from its log (/opt/frankie-box/work/experiment/e2e-20231018-a2/logs/20231018-root.log): 01:02:49Z
  legacy_book_imbalance.json written (4861.4 s); 01:10:14Z legacy_structure_observables.json written (9.4 s);
  01:17:50Z "bedrock: the pinned traversal (2ebb8ce8) on 771787 INPUT records for 44 layers" (legacy-stage.json
  written 01:17:50Z, 59,810 B); 01:20:52Z "bedrock: completed native results reused in place; no traversal or
  finalization replay" = the 2667 check passed with NO marker (written 3 s later at root-projection).
- At 01:29:44Z: ROOT 14860 alive (Sl, elapsed 2:45:53, 45.9% CPU), progress.json stage root-projection-member, state
  running, written 01:29:42Z (advancing); work/derived/.projection-v2/ created 01:20:58Z; derive.json and
  calculations-receipt.json absent (ROOT NOT completed yet). root.json seq 2: state running, save_request = the marker's
  identity, finish null, child null. Units: frankie-hold-a2-20261008T011619Z active/running (status logging until
  01:50:55Z), frankie-queue-root-1791413028 active/running. Teacher: none.
- root-projection-member = frankie_box_projection.py's per-kind progress ('root-projection-'+kind, lines 299/306, total =
  the member layer bytes) while it reads the layer. frankie_box_projection.py has no save_requested / stop-file / SIGTERM
  check (git grep at c9bf631); frankie_box_bedrock.py's checks live in the traversal (reused, not run). The box modules
  carrying save_requested at c9bf631: bedrock, boss_session, classroom_code, classroom_reader, experiment,
  experiment_classroom_v2, experiment_root, experiment_teacher, frankie_queue, native_checkpoint, successor_dispatch;
  none of them is on the path between root-projection and the receipt except experiment_root's post-return check.
  Expected: projection -> derive.json -> retained digest (root-digest) -> root-derived -> calculations-receipt.json ->
  "ROOT completion published" exit 75 -> entry saved, booking retained, no teacher.

### 3.5 Follow-up 3, command 81469ae4-6e5b-4f37-b8a9-6b83396a8f1f, 01:33:24Z (read-only): ROOT in root-digest, not saved yet
- Stages (watcher STATUS lines): root-projection 01:20:55Z -> root-projection-member 01:21:56-01:30:57Z ->
  root-projection-lifecycle 01:31:57Z -> root-projection-publication 01:32:57Z -> root-digest (progress.json at
  01:33:06Z, completed 0, total None, percent None). Every verdict "save pending acknowledgment", entry running,
  marker standing, teacher none.
- ROOT log 01:33:06Z: "bedrock: 43/44 layers derived by the pinned traversal on 583688 groups (86399.5 s of rows; the
  candidate lane needs 900 s); sections 4.2 derived (28 rows), 4.4 derived (1167376 rows)". work/derive.json written
  01:33:06Z (80,813 B). derivation-digest-full.md and calculations-receipt.json absent.
- ROOT 14860 alive Rl elapsed 02:49:33, with 30 python children 59921-59957 holding one fd each under R (digest
  workers); 14860 holds 5. root.json seq 2: running, finish null, save_request true, retained_booking
  day-run-20231018-day_slot_root-1791402822-3111. Booking file live (pids 14824 holder, 14860 step root), retained
  null, release null, CPUs 0-31. Units: frankie-hold-a2-20261008T011619Z + frankie-queue-root-1791413028 active.
- df: / 603,215,196,160 B avail (used 1,525,808,234,496 of 2,129,040,207,872; down from 701 GB at 01:16Z, the digest
  writes); archive 1,725,022,810,112 avail of 2,163,350,618,112.

### 3.6 Follow-up 4, command 2742863c-c4f7-493a-b491-dae3725d801e, 01:39:12Z (read-only): still root-digest
- progress.json stage root-digest, state running, completed 0, total None, percent None, at 01:33:06Z (unchanged).
  31 digest workers (children of 14860, pids 59921-59957), 31 processes with files open under R. ROOT 14860 Sl
  elapsed 02:55:21. Receipt and derivation-digest-full.md absent. ROOT log last line still 01:33:06Z.
- STATUS 01:33:57-01:38:58Z: save pending acknowledgment, entry running, marker standing, booking live (retained
  null), teacher none. Units: hold watcher + queue worker active. df: / avail 603,207,954,432 (flat since 01:33Z);
  archive avail 1,725,022,801,920. Digest elapsed 6 min 06 s at this read.
- Note: the watcher's status logging stops at 01:50:55Z; the hold itself needs no watcher after the marker (the ROOT
  child and the worker read the marker at their own check points), only the log stops.

### 3.7 Follow-up 5, command 953c6bbf-1965-40de-8737-11773797321e, 01:51:49Z (read-only): still root-digest; watcher ended
- progress.json root-digest unchanged since 01:33:06Z; digest elapsed 18 min 43 s. ROOT 14860 Sl elapsed 03:07:57, 31
  digest children. Receipt and derivation-digest-full.md absent. root.json seq 2 running, save_request true, finish
  null, retained_booking day-run-20231018-day_slot_root-1791402822-3111; booking live (14824, 14860), retained null.
- hold-a2.log: STATUS to 01:50:00Z all "save pending acknowledgment"; "01:51:00Z watcher end" (30-minute window over;
  unit collected). The marker stands; the hold completes without the watcher.
- Units: frankie-queue-root-1791413028 only. Teacher none. df / avail 601,180,950,528 (used +2.03 GB since 01:39Z);
  archive avail 1,725,022,760,960.
- Staged checkouts: ebc7ef38b7a4e19bd6f55bc587627366041ea0e0-37714676063-1/markets LANDED 01:49:40Z (HEAD ebc7ef38);
  b474c51e not present; c9bf631e, 275367fe, 98579cea, 18cbc5a4 still live directories; eight older ones archived
  (symlinks to /opt/frankie-box/archive/code/*.tar.zst, 00:49-00:51Z).
