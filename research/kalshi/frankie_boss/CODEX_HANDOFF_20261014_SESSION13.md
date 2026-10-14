# CODEX HANDOFF, 2026-10-14: the first full Frankie day (a2/20231018), where it stands, what to do next

Written by Claude at the end of session 13 for Codex (or a fresh Claude). Greg's usage is low; this file is meant to be
enough on its own. All times are UTC (Z). Nothing in here is a guess unless it says "unknown" or "expected".

## 0. READ THIS FIRST: the box state is UNKNOWN since 2026-10-10 12:52Z

- Both AWS connectors in the Claude session died at 12:52Z on 2026-10-10 ("needs sign-in" and "expired credentials")
  and never came back through 2026-10-13 20:57Z (28 retries). Greg was told once. Nothing on the box has been seen
  since 12:52Z on 2026-10-10.
- At that moment the box was RUNNING, tag KeepRunning=true, the day in progress (section 4). Nothing stopped it from
  our side. If it is still running and the day has finished, it is an idle r7i.16xlarge billing by the hour (about
  $4.2/h on demand in us-east-1, so roughly $100 per day idle). Check it first.
- You need working AWS access before anything else. Options: Greg re-authorizes the AWS connector, or the keys go in
  `~/.config/markets/env` (chmod 600; see `KEYS.md` and `research/kalshi/creds.py`). Never echo a secret. Keys do not
  rotate during the walk (Greg's standing decision).

## 1. Where everything is

- Repo `DavisAI1974/Markets`. Work branch `ccr-d2f8f826-iefeah-frankie`. It is a SHALLOW clone in cloud sessions:
  run `git fetch --deepen=400` before any merge-base. Tip at writing = the commit that adds this file (code tip is
  `2f02022`; later commits are docs only).
- Claude's session branch `ccr-8e841020-rtna5z` carries the same commits. Work on `ccr-d2f8f826-iefeah-frankie`.
- Session record (most detailed, newest at top): `research/kalshi/frankie_boss/DROP_IN_CLAUDE_20261009_SESSION13.md`.
  Before that: `DROP_IN_CLAUDE_20261009_SESSION12.md` (Greg's hub design) and `..._SESSION11.md`, `..._SESSION10.md`
  (Greg's operating rules at its top).
- Block-1 teacher report as written on the box: `research/kalshi/frankie_boss/TEACHER_REPORT_20231018_BLOCK1.md`.
- Hub design and calculation order: `research/kalshi/frankie_boss/HUB_CALC_ORDER_MAP_20261009.md`.
- `AGENTS.md` older pointers (CURRENT_WORKFLOW_SETUP_20261007, CODEX_HANDOFF_20261007_WORKFLOW_CONTINUATION, the
  three 16-CPU lanes, "no starts without Greg's go") are BACKGROUND. They are superseded by Greg's session 10-12 rules
  in section 3: the one-day E2E is authorized and running on one 64-CPU box, and keeping it running is priority one.

## 2. What the project is and what we are trying to accomplish

Frankie is the learner in an experiment on natural-gas futures market data (CME NG, MBO order-book tape from
Databento, stored in S3). The experiment teaches Frankie market conditions one trading day at a time.

The pieces of one day, in the order the data flows:

1. **Ingest.** The day's raw MBO tape becomes a reduced journal. A trading day is named by its trade date and runs
   18:00 ET the prior calendar day to 17:00 ET (the 20231018 day starts 2023-10-17 22:00Z).
2. **ROOT.** Builds the day file: every market-condition calculation ("the 99 planes") on the full day, plus a digest.
   For this day the digest render is off (`FRANKIE_ROOT_DIGEST=off`).
3. **The teacher (the BOSS role).** Walks the whole day row by row (771,787 rows for 20231018) and writes the teacher
   rows: the answers and evidence the classroom is graded against. Since session 12 it SEALS the day in blocks as it
   goes (first block 5 minutes, then 30-minute blocks, on the receive clock), so the classroom can start before the
   walk ends. After the walk it builds the "second set" (all 99 planes beside book and flow, on the whole day) and
   publishes the final rows.
4. **The classroom (Frankie).** One lesson per sealed block, strictly one lesson at a time: Frankie gets the block's
   lesson, answers 19 questions, is graded against the teacher's pinned key, gets corrections, writes novel findings
   and a brain update, then the external section runs at the block's cutoff. Each block writes a `session.json` and a
   `TEACHER_REPORT.md`.
5. **Day-end.** After the teacher publishes: the whole-day classroom (SOCRATIC/VERIFY, market context, exhaustion,
   the teacher account, brain entry `<day>-cycle-00`), then Jev (a blind comparison adviser), the exchange, the
   meeting, the school (consolidated knowledge), and the numbered day reports.

**The immediate goal (Greg's gate):** run ONE day, `e2e-20231018-a2/20231018`, end to end through every piece, on
the box, with the full science. The deliverable Greg wants to read is the teacher's second set and its first-person
TEACHER REPORT for the whole day.

**After that, in Greg's order:** remove the temporary swapfile and revert the archive volume; wire the HUB (one
teacher core with a spoke to each piece under one turn lock, ordered by prerequisites; design in the session 12
drop-in and HUB_CALC_ORDER_MAP_20261009.md); the one-pass build; the ROOT fix; then the 30-day run (30 October days
across 2021-2025; every later day streams: the teacher seals as the data arrives and lessons start on block 1).

## 3. Greg's binding rules (sessions 10-12; follow them exactly)

1. THE SCIENCE IS NEVER WEAKENED FOR SPEED. Nothing computed, answered, graded, carried or written as evidence is
   reduced, sampled, truncated or approximated. Speed comes only from doing the same work once, in the right order,
   or at once where nothing depends on anything.
2. ONE LESSON AT A TIME (`BLOCK_LESSONS_AT_ONCE = 1` in `frankie_box_experiment.py`). Inside a lesson, independent
   pieces run at once.
3. Everything runs at once except what needs another piece's output first. The order is prerequisites only.
4. Block 1 (the first 5 minutes, 1,588 rows) is THE GAUGE: re-run through the whole classroom session on every code
   version (`deploy/aws/box/frankie_box_block_gauge.py`). Every speed claim is that number. Current: 159.0 s.
5. DISCUSSION FIRST on the external section. Do NOT change the external section or the hashing until Greg picks
   (section 6).
6. Keeping the workflow running is priority one. Our own gates never block a run when the data is fine. No coded
   waits; hand-offs are event-driven. Fixes go on the box the moment they are pushed (push route, section 7). The code
   version is recorded, never compared. No lists or records of code changes beyond commits. Push every fix. No
   infrastructure change calls at a session's end. A dead piece is REVIVED, never skipped. Forward reads are not a
   concern (only the forecaster stays blind).
7. No emojis or special symbols in anything pushed. Commits end with `[skip ci]` on this branch.

## 4. Last known state (2026-10-10 12:52Z) and what was expected after it

Box `i-035994afa8bdf66a5`, r7i.16xlarge (64 CPU, 495 GB RAM), us-east-1, driven only over SSM. Code on the box:
`/opt/frankie-box/code/current` = `2f02022`.

| Piece | State at 12:52Z on 2026-10-10 |
|---|---|
| Teacher walk | Done 04:04Z: 47 blocks sealed, block 47 final, cursor 771,787 = whole day |
| Teacher process | pid 19448, restarted 11:50Z on `2f02022`; re-feeding the 47 sealed blocks as carry, then the second set, then publication |
| Classroom blocks | All 47 block sessions complete (one `session.json` each) |
| Day-end classroom onward | Waiting for the teacher's published rows (nothing skipped) |
| Swap | 400 GB swapfile active (`swapon -p -1`), not in fstab |
| Evidence-hash fix | Not touched; waiting on Greg |

Expected after 12:52Z if nothing broke: re-feed done near 13:35Z; second-set assembly about 2.5 h, so near 16:05Z;
then the second-set pickle and the final publication (the step that OOM-killed it before, now with swap headroom);
then the day-end classroom on the whole day, Jev, exchange, meeting, school, day reports. How long the whole-day
classroom takes is unknown; the evidence-hash cost (section 6) applies to it at a much larger scale than per block.

What may have happened instead, and how to tell (probe commands in section 7):
- The day finished: the class events and the day-reports directory show it, and the box sits idle.
- Something died: a unit stopped, an OOM line in dmesg, a teacher log ending in a traceback. Find the cause first,
  then resume (section 7). Every kill of the teacher before publication costs the whole second set; there is no save
  point between the walk save and the publication.
- The box was stopped by someone: swap is gone after any start; redo `swapon` before resuming.

## 5. What happened in session 13 (2026-10-09 23:5x to 2026-10-10 12:52Z)

- 23:58Z box started, tip `4e5ca5d` pushed, `ACTION=resume` at 00:01Z. Teacher continued its walk; classroom ran
  blocks 23-42.
- 04:04Z teacher walk ended (47 blocks). It went into the whole-day second set (one thread, ~305 GB RSS).
- 06:09-06:11Z FIRST KILL. Ubuntu's `apt-daily-upgrade` ran unattended-upgrades; needrestart restarted the frankie
  units: SIGTERM then SIGKILL of root, class and teacher. The teacher lost 2.5 h of second set; the classroom lost
  block 43. Fixed on the box (apt timers and services disabled and masked, unattended-upgrades off,
  `/etc/apt/apt.conf.d/99frankie-no-auto-upgrade`, needrestart list mode) and for every future box in
  `deploy/aws/box/frankie_box_worker_setup.sh` (commit `ca1b726`). Resumed 06:45Z.
- 08:27Z a bug: a resume after the walk's last seal made the teacher's block feed raise "no row was fed" (nothing left
  to cut), the manifest read `failed`, and the publication would have taken the slow fallback and lost the sealed
  sidecar pin. Fixed in `_BlockFeed.merged_rest` in `deploy/aws/box/frankie_box_experiment_teacher.py` (commit
  `2f02022`); the sealer resets `failed` to `sealing` on resume. Pushed to the box; the running teacher was not
  restarted for it (that would have cost about 5 h).
- 11:21Z SECOND KILL. The kernel OOM-killed the teacher (anon RSS 514.8 GB on the 495 GB box) while it streamed the
  second-set pickle (`teacher-second-set.pkl.pending`, 39.8 GB written; pickle's memo grows). Cause: the 400 GB
  swapfile from session 8 is not in fstab, so the box start at 23:58Z had lost it. The root worker logged "the day goes
  on without them (missing-coverage rule)" and ended; the class worker kept waiting (correct: nothing skipped).
- 11:50Z `swapon -p -1 /opt/frankie-box/archive/swapfile` (400 GB active), then `ACTION=resume`: teacher restarted on
  `2f02022` (pid 19448). Commit `3e5cca6` records this.
- 12:52Z AWS access lost for the rest of the session.

## 6. The decision waiting on Greg: the evidence-hash cost

Profile of block 1 (`deploy/aws/box/frankie_box_block_profile.py`, cProfile): the external section spends almost all
its time in `research/kalshi/frankie_boss/c15_journal.py` `evidence_hash` -> `causal_packet.py` `canonical_bytes` ->
`_canon`, a pure-Python recursive canonicalizer, hashing ~56 MB objects 13 times per block (4 in pre-binding, 9 in
grade/correction). The external science itself (answers) is 0.16 s. The main chain's key binding and store writes very
likely pay the same cost, and the whole-day classroom pays it on ~770k rows.

Facts proven (locally by Claude and by a helper agent; no box run):
- `evidence_hash(x) = sha256(SCHEMA + NUL + canonical_bytes(pack(x)))`. `pack` emits only lists, exact str/int/bool
  and tag strings (floats as IEEE hex strings, bytes as hex, None as `["null"]`, dicts as tagged lists). On `pack`
  output `_canon` is the identity, so
  `canonical_bytes(pack(x)) == json.dumps(pack(x), sort_keys=True, separators=(',',':'), ensure_ascii=True).encode()`
  byte for byte. Tested on every edge type and on 7.9 MB and 30 MB row-shaped objects: same bytes, same hash, 3.5x to
  10x faster.
- The fast path is valid ONLY inside `evidence_hash` (and the journal's `canonical_bytes(pack(...))` uses). It must
  never replace `canonical_bytes` on raw values, where `_canon` quantizes floats, sorts mapping keys and converts numpy.

Recommendation given to Greg (he has not picked):
- (b) First: the fast canonicalizer inside `evidence_hash`, run in SHADOW mode on the box (every call computes both
  ways and asserts equal) on block 1 and one large block, then switch.
- (a) Then: hash each object once per block and carry the hash at the named sites (the external key enters 5 large
  hashes per block where only 2 are new content; the main chain repeats similarly).
- Then: the block store's write-once serialization (store writes 22.9 s to about 7 s).
- Estimated block 1: 159 s now, about 42 s with (a)+(b). A 9,000-row block: about 300 s now, about 85 s.
- Side finding: cyclic GC doubles a large hash's cost (`gc.freeze()` took one from 3.44 s to 1.54 s).
- Other options Greg was shown earlier (now secondary): external part once per day; build the section once per day
  file and slice per cutoff (block 1 section sha `052d6fe90ba24d753b3029388105d812ea6644e307e755e0959913f310caecc7`
  must reproduce); one external section in the hub for all spokes; incremental per block.

Do not implement any of this until Greg picks (rule 5). When he does: build, prove byte-identical hashes in shadow
mode and on the gauge, push to the box, restart only the class worker (never the teacher for a classroom change).

Greg's two unanswered questions from session 12 (ask him; do not guess): "the piece that speeds it up 250 M per sec"
and "the other 8 on 8 consecutive days".

## 7. Commands

All box work goes through SSM `AWS-RunShellScript` in us-east-1. Keep each command under about 55 s; long jobs go
under `systemd-run` because an SSM shell's children die with the command.

**Box start (only if it is stopped):** `StartInstances` on `i-035994afa8bdf66a5`, tag `KeepRunning=true`, wait for
SSM Online, then ALWAYS:
```
swapon -p -1 /opt/frankie-box/archive/swapfile && swapon --show && free -g
```

**Probe (read-only):**
```
date -u; swapon --show; free -g | head -3
systemctl list-units --no-pager --plain 'frankie-*'
journalctl --no-pager --since "2026-10-10 11:50" -u 'frankie-*' | grep -Ei 'stop|kill|fail|deactivat' | tail -20
pgrep -af frankie_box_experiment_teacher; for p in $(pgrep -f frankie_box_experiment_teacher); do grep VmRSS /proc/$p/status; done
L=$(ls -t /opt/frankie-box/work/experiment-teacher-rows/logs/20231018-*.log | head -1); echo $L; tail -n 25 $L
python3 -c "import json;d=json.load(open('/opt/frankie-box/work/experiment-teacher-rows/20231018/teacher-blocks.json'));print({k:d.get(k) for k in ('status','next_block','next_cursor')})"
ls -la /opt/frankie-box/work/experiment-teacher-rows/20231018/
tail -n 15 /opt/frankie-box/work/frankie-queue/logs/root-worker.log
tail -n 15 /opt/frankie-box/work/frankie-queue/logs/class-worker.log
tail -n 5 /opt/frankie-box/work/frankie-queue/class-events.jsonl
dmesg -T | grep -i 'out of memory' | tail -5
df -h /opt/frankie-box /opt/frankie-box/archive
```
The teacher's in-memory progress during assembly: `/opt/frankie-box/venv/bin/py-spy dump --pid <teacher> --locals`
(look for the `cursor` local in the `assemble` frame). Classroom outputs:
`/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/classroom/` (`blocks/<n>/session.json`,
`TEACHER_REPORT.md`, then the day-end files).

**Resume the day (after any kill or box start; swap first):**
```
CR=$(readlink -f /opt/frankie-box/code/current); cd $CR
CODE_ROOT=$CR MARKETS_SHA=$(basename $(dirname $CR) | cut -d- -f1) FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all \
  ACTION=resume SCOPE=e2e-20231018-a2:20231018 RUN=e2e-20231018-a2 DAY=20231018 \
  sh deploy/aws/box/frankie_box_frankie_queue.sh
```
Resume reconciles a dead finish holder itself, restarts the teacher child on `current`, and the early class door
re-enqueues the class line. If the class line does not start within a minute, kick it:
```
CODE_ROOT=$CR MARKETS_SHA=<sha> FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all ACTION=kick LINE=class \
  SCOPE=e2e-20231018-a2:20231018 RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_frankie_queue.sh
```

**Push code to the box (the moment a fix is committed):**
```
python3 deploy/aws/box/frankie_box_push_bundle.py build --commit <sha> --base <box current sha> --output <pack>
# presigned PUT and GET on s3://frankie-granite42-568968024170-us-east-1/readiness/20260923/code-push/<sha8>/<packsha>.pack
curl -X PUT --upload-file <pack> "<PUT url>"
# then over SSM:
export BASE_SHA=.. BUNDLE_BYTES=.. BUNDLE_KIND=delta BUNDLE_SHA256=.. MARKETS_SHA=.. BUNDLE_URL='<GET url>'
sh "$(readlink -f /opt/frankie-box/code/current)/deploy/aws/box/frankie_box_push_code.sh"
```
A classroom change: stop the `frankie-queue-class-*` unit, wait for `pgrep -f 'line class'` to be empty (up to 90 s),
kick the class line, confirm the new worker's cmdline names the new code root. A teacher change: `ACTION=save`, stop
the `frankie-queue-root-*` unit, wait for the teacher pid to exit, then `ACTION=resume`. Restarting the teacher during
the second set throws away hours of work: avoid it unless the fix is required for correctness.

**Gauge (block 1 on current code):**
```
systemd-run --unit=frankie-gauge-$(date +%s) --collect -p WorkingDirectory=$CR sh -c "/opt/frankie-box/venv/bin/python -B \
  deploy/aws/box/frankie_box_block_gauge.py --rows-dir /opt/frankie-box/work/experiment-teacher-rows/20231018 \
  --ingest-dir /opt/frankie-box/work/ingest-20231018-gh-36571235912-1 --day 20231018 --out /opt/frankie-box/work/gauge-block1 \
  > /opt/frankie-box/work/gauge-block1/run-\$(date +%H%M%S).log 2>&1"
```

## 8. Next steps, in order

1. Get AWS access. Check the instance state (DescribeInstances) and, if running, run the probe.
2. If a piece died: read its log and dmesg, name the cause, fix it (push the fix if it is code), `swapon` if needed,
   resume. Report the cause and the fix to Greg in plain words.
3. If the day finished: confirm every day-end output exists (whole-day classroom, Jev, exchange, meeting, school,
   numbered day reports) and the teacher's whole-day TEACHER REPORT. Bring that report back into the repo the way the
   block-1 report was (`TEACHER_REPORT_20231018_BLOCK1.md`) and give it to Greg to read. Then stop the box only on
   Greg's word, or if it is plainly idle and he has said so before (he stopped it himself for breaks).
4. If it is still running: keep it running; probe on a sensible cadence; do not restart the teacher for anything
   that is not a correctness fix.
5. Ask Greg for his pick on the evidence-hash fix (section 6) and his two open questions. Build only after he picks.
6. After the day and Greg's read: remove the swapfile; revert the archive volume to baseline; then the hub wiring
   (compare each piece by value with `frankie_box_hub_compare.py` before switching it), the one-pass build, the ROOT
   fix; then the 30-day run on Greg's go.

## 9. Traps learned the hard way

- Swap is not persistent. Every box start needs `swapon -p -1 /opt/frankie-box/archive/swapfile` before the teacher's
  second set, or the pickle step OOMs the 495 GB box.
- Ubuntu auto-upgrades restart services. The setup script now disables them; a box built before `ca1b726` needs the
  same block applied by hand.
- SSM shells kill their children when the command ends. Long work goes under `systemd-run`.
- The MCP `run_script` tool times out at 60 s. Keep each SSM command short and poll.
- `head -20` on a directory listing once hid the classroom `session.json` files. List the exact paths.
- The teacher writes nothing during the second-set assembly; the manifest stays `sealing`. Use py-spy to see progress.
- The root worker's "the day goes on without them" after a teacher failure is the missing-coverage rule; the class
  worker correctly keeps waiting. A resume revives the teacher; nothing is skipped.
- Kill points with no save: between the walk save and the publication. Each kill there costs the whole second set.
