# CODEX HANDOFF, 2026-10-14: the first full Frankie day (a2/20231018): teacher and ROOT done, day-end saved, box stopped

Written by Claude at the end of session 13 for Codex (or a fresh Claude). Greg's usage is low; this file is meant to be
enough on its own. All times are UTC (Z). Nothing in here is a guess unless it says "unknown" or "expected".

**October 14 review corrections:** interrupted batch children request the bound owner's day save marker, including
lesson keys such as `discovery-01-historical`. Exchange publication again retains the complete source-bound rows
measurement beside its context; retries reload it and attach the shared key's ledgers. Shared teacher-key lookups
refresh after an unchanged source acquires new file metadata, using a separate atomic lookup that points at an
immutable, hash-pinned key manifest. Existing manifest pins remain valid. The earlier meeting, doctor-completion
and external-key decoding corrections remain in source. These changes have source, syntax and diff review only;
runtime behavior remains unverified, and no AWS operation or execution was performed.

**Greg's latest clarification, October 14 ET:** keep ALL 99 planes and the teacher's second set pinned together
with the existing original row keys, event flow, source cursors and causal clocks. Recovery must retain partial
calculations and partial output when a process is one-third done, then continue at its saved position. Reuse the
existing save hooks; do not impose arbitrary timer, group or stage-completion recovery cutoffs. Timing/readiness
markers are not recovery gates. This is a requirement, not a claim that every existing path already satisfies it.

Current source follow-up: second-set book-record parts now retain partial output positions and running totals with
the existing teacher atomic save helper, and reuse the saved prefix/carry when reopened. Interrupted files are
preserved. Completed parts retain their carry as well. Classroom segment saves retain each returned in-order
portion immediately and keep it after the sub-step returns, closing the former deletion-before-phase-save gap.
Individual in-flight row/worker calculations, out-of-order result retention, native open-group continuation and
sequential ingest recovery are not established by these changes. No new native checkpoint protocol was installed.
Source review, AST parsing and diff checks only; no tests, scientific execution, benchmark, AWS mutation or start.
See the precise limits and revised timing-marker wording in NATIVE_STREAM_TIMING_SCOPE_20261014.md.

**Current source contract and next timing scope:** read
`NATIVE_STREAM_TIMING_SCOPE_20261014.md`. New fresh sequential day ingests with prepared INPUTs select
`FRANKIE_NATIVE_DBN_MEMBER_PROVENANCE_V1`: original verified DBN member hashes on native rows, with the
completed physical journal pinned separately. The ingestion envelope, saved global cursor, native continuation,
and teacher artifact selection bind that policy. Old receipts and the saved a2 attempt retain journal stamping.
This resolves the per-record final-journal-hash dependency in source; it does not implement early native execution.
The committed-prefix notifications, continuing ROOT consumers and shared-picture/teacher segment readers remain
to be wired. Existing full-day checks stay in place. The bounded timing scope is one block-1 classroom gauge plus
one contiguous 35-minute ingestion/ROOT prefix (first frontier at 30 minutes, then continue from the saved cursor),
in one attended session with a 30-minute wall-work budget. Save/reopen at actual partial progress within that scope;
30/35-minute markers do not restrict recovery. That combined run is not launch-ready until the actual
continuation entry point and bounded stop path exist. Do not substitute a saved-day resume. No AWS start, mutation,
scientific execution, test or benchmark was performed; only source review, syntax parsing and diff checks.

**Codex continuation, 2026-10-14 (Greg's evening of October 13 ET):** Greg authorized the complete efficiency design
and source integration before any test: share exact calculations/tables, remove unnecessary passes, wire the hub,
then use one small timing run as the test. He explicitly approved: "Do the faster hash encoder if it doesn't change
anything". The candidate preserves the existing evidence bytes/hash formula; raw-value canonicalization remains
unchanged and PrePacked values retain the legacy fallback. The gauge defaults to shadow comparison in that same
small run, with comparison costs reported separately. Source changes are not runtime verification. AWS access works;
a fresh DescribeInstances read still shows the main box STOPPED, KeepRunning=false. No source work starts or resumes
the box. The saved a2 day, all retained data and infrastructure remain unchanged. These instructions supersede the
older ordering and unanswered hash-choice wording below.

Greg also clarified that safe steps should start when the first 30 minutes of a day have been ingested, then consume
new data incrementally. This is a data-readiness threshold, not a 30-minute wall-clock delay. Preserve complete event
groups, original cursor order, carry state, look-ahead/answer boundaries and exact reduction order. A step that needs
the whole day may prepare its independent inputs early but must finalize only after those dependencies exist. Do not
restart or replay the accumulated prefix for every new block. Existing first-five-minute teacher/classroom lessons
may start earlier when their own inputs are ready; the block-1 timing gauge stays unchanged.

Source review distinguishes two different boundaries: teacher-to-classroom sealed-block consumption already exists;
raw compact ingestion to ROOT still requires the whole-day seal. The latter is NOT implemented by removing a hub
prerequisite: it needs committed prefix boundaries and continuable consumers. Do not claim the current source runs
ROOT or the teacher after the first 30 minutes of raw ingestion. The historical handoff is evidence to check against
the code and observed state, not an authority overriding Greg or a guarantee that its conclusions are correct.

The coherent streaming design is one continuing day, not repeated prefix runs:

| Boundary | Start/continue rule | Completion rule |
|---|---|---|
| Compact ingest | At 30 minutes of receive-clock coverage, drain pending encoders and publish a committed frontier with original ordinal range, count/head, source identity and opening/carry state; notify on subsequent committed increments | Publish the original whole-day completion only after full conformance |
| ROOT legacy/native | Consume each newly committed INPUT once; preserve adapter, pending groups, binner and scientific calculator state; temporary EOF means await the next frontier | Finalize once at true day EOF and reconcile accumulated counts/head with the final source |
| Shared market picture / teacher | Read committed source and calculation segments at their original causal availability; keep unresolved groups/horizons pending | Whole-day products retain their full-day dependencies |
| Classroom | Consume sealed teacher blocks in order, one successful lesson at a time, as soon as their own evidence is available | Whole-day lesson remains separate from block completion |
| Day-end | Prepare only independent inputs early | Final key, terminal outcomes, final projections, exchange, school and reports wait for their actual prerequisites |

The first three new frontier contracts above remain source work, not a deployed capability. Existing complete-source
identities cannot be replaced by successively larger prefix identities; current saved attempts must keep their original
contracts. A single instrument's F_LAST is not proof that every instrument group is closed: carry open groups explicitly.

**Latest continuation, October 13 evening ET / October 14 UTC: source review before a chat change.**
The first efficiency publication is `bd8f4f1e6684865c71b410f0fd63a68d2dda3e59`. Read the branch's current tip for the
following follow-up changes; the commit containing this paragraph has `[skip ci]`. No test, benchmark, scientific run,
AWS mutation, instance start or day resume was performed for these changes. Box deployment remains pending while it is
stopped. Greg asked when to change chat: after this source publication and handoff, before the remaining design decision.

Codex independently reviewed `bd8f4f1` and found two correctness defects. Both are corrected in the follow-up source:

- A waiting meeting explicitly marked nonblocking (`refused`, `inputs_only`, `runtime_failed`, or `remote_pending`) now
  satisfies the hub under the exact same predicate as the queue. Its disposition is published; no completed meeting
  content is invented. This preserves school/report progress and later meeting updates.
- Doctor shutdown now requires the exact retained queue owner's terminal `done` / `finish.finished` state, no remaining
  child/revival work, and no unfinished/stale hub operation. A reports publication alone cannot end recovery; a
  non-classroom day does not need a nonexistent reports hub operation. Required late report revisions/currentness checks
  run inside the reports hub operation and failed/waiting revisions prevent the owner's close.

The external-key review also found repeated whole-key decoding despite cached verification. The lesson now owns one
immutable decoded tree plus its series/pair lookup tables. Grading reads those directly. Public materialization and
pre-messages copy their published values, and the existing final grade canonicalization detaches its output. Original
dict/list/tuple evidence types, insertion order, field values and hash formulas remain the source contract; actual
equivalence, memory use and speed remain unverified until the one small timing run.

**Historical prerequisite, resolved for new prepared ingests by the current contract above.** `frankie_box_bedrock.source_object` and
`iter_driver_records` stamp the *final physical journal SHA-256* into `source_dbn_sha256` on every native INPUT. Source
inspection of the actual pinned producer (`2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`) confirmed that the adapter's normalized
records/raw actions and retained member rows include it. Replacing it with a manifest/stream ID changes the native
evidence rows and their hashes. The native pass cannot start before that digest exists under the present exact evidence
contract; full-picture teacher/block work must not declare the still-running native producer absent to get around it.
That source review originally left the choice open. Greg's next instruction was to resolve this dependency;
the current source contract uses the actual already-verified DBN member identity for NEW prepared ingests and
retains the final journal pin separately. This is a versioned provenance change, not an encoder optimization.
The saved a2 identity stays intact. Runtime/recovery behavior remains unverified until the authorized small run.

Safe preparation is now wired into the actual daily route, beginning during ingestion rather than waiting for the day:

| Source change | Work removed | Boundaries retained |
|---|---|---|
| Fresh sequential compact ingest observes original accepted INPUT payloads and writes ROOT's exact typed spool as they arrive | ROOT's later journal decode/extraction pass; about `2N` INPUT/APPLIED entries for `N` source records (1,543,574 for 771,787 records, excluding any extra control entries) | Same journal block cuts, bodies, hashes and file bytes; same complete receipt and inline/deferred conformance disposition |
| ROOT reuses the receipt-pinned prepared spool | Repeated serialization/allocation of the same INPUT rows | Final journal path/count/head/size/SHA checked; immutable descriptor; strong file claim or full SHA/count fallback; no partial descriptor accepted |
| Native full-state saves retain exact validated byte offsets | New saves avoid decoding/skipping the computed INPUT prefix on recovery | Same source hash, count, row boundary and saved scientific state; older saves locate their ordinal once |
| Prepared spool retains receive-clock extrema | Final native span calculation needs no extra full INPUT scan when the clock projection is unchanged | Original min/max formula; older/unusual sources retain the original projected scan |
| External key and lookup reuse | Repeated whole-key JSON decoding and per-grade lookup construction | Same graded values, role walls and independently owned publications |

`frankie_box_ingest_block.sh PREPARE_INPUTS=auto` enables this only for a fresh sequential full ingest. The CLI option is
`--prepare-inputs DIRECTORY`; old receipts, parallel ingestion, canaries and resumes keep their established routes.
This is genuine shared preparation, **not** implementation of native/teacher processing at the first 30-minute frontier.
The draft generic frontier/resume framework was not included as an unused capability. Legacy calculations could also
be separated from the terminal identity wrapper, but that continuation route is still unbuilt. No speedup percentage or
full-day cost claim is established. The first-block classroom gauge alone does not exercise this new ingestion/ROOT
path: the bounded timing-run coverage is now in NATIVE_STREAM_TIMING_SCOPE_20261014.md; complete its stated
continuation wiring before any AWS start.

## 0. READ THIS FIRST: the box is STOPPED and the day is SAVED mid day-end (read on the box 2026-10-14 01:2xZ)

- Box `i-035994afa8bdf66a5` is STOPPED, tag KeepRunning=false. Greg had it stopped on 2026-10-14 at about 01:0xZ,
  then it was started for about 10 minutes for a READ-ONLY look (nothing resumed, nothing changed) and stopped again.
  No other EC2 instance is running in any region. Its two 2 TB gp3 disks (root and archive) still bill while stopped
  (about $11/day together).
- WHAT IT COST: the AWS connectors died at 2026-10-10 12:52Z and nobody watched the box after that. Its CPU history
  shows the work ended at about 00:09Z on 2026-10-11, and the box then sat IDLE until it was stopped on 2026-10-14,
  about 2.5 days at roughly $4.2/h (on demand). Lesson: a running box must never be left without someone able to see
  it; if access is lost, the person is told plainly that it is still billing.
- Greg, 2026-10-14, on seeing this: "We were only supposed to be doing small slice checks for timing why did we get
  here doing all this??" He said it is not important now. Read it as his intent: before any long run, confirm with him
  whether he wants the full day or small timing slices. Do NOT start the box or resume the day without his word.
- WHAT STILL BILLS (account inventory 2026-10-14; Greg: keep anything whose removal would lose data, keep both
  Lightsail servers, he will find a permanent solution later). Nothing is running in EC2. Kept, all holding data:
  us-east-1 volumes `vol-0d36715924f03b86c` and `vol-004b68c077be09cc9` (the main box's root and archive, 2 TB each),
  `vol-0fbf7bc0991bc8e39` (2 TB, on the stopped `i-0d17573dbce871520` frankie-linux-r7i4xl), two UNATTACHED 2 TB
  volumes `vol-0c53052c4a6b38bfe` and `vol-0025eb0f8dc9d97b9` (content not checked), two 2 TB snapshots from Oct 8;
  us-east-2 `vol-05a0b1e56f8c16478` (300 GB, stopped `i-08cee7171c0a76a04` markets-year-pull-v2) and two snapshots;
  S3 `bento-568968024170-us-east-2-an` (623 GB market data), `frankie-granite42-568968024170-us-east-1` (113 GB),
  `frankie-archive-568968024170-us-east-1` (empty); Lightsail `Od-discovery` and `market_watch` (us-east-2, running).
  Roughly $1,000-1,100 a month in total, almost all of it the ten-plus TB of gp3 disks.
- DISK SPEED LOWERED (2026-10-14, no data touched): the main box's two volumes were set to 16,000 IOPS / 1,250 MB/s
  (root) and 10,000 IOPS / 1,000 MB/s (archive); both are now the free gp3 baseline 3,000 IOPS / 125 MB/s (saves about
  $180/month). BEFORE ANY RUN ON THAT BOX, raise them back with `ModifyVolume` (same values), or ROOT, the teacher and
  the classroom will run far slower. A volume can be modified once every 6 hours.
- The day's state as read on the box is in section 4. The teacher and ROOT are DONE; the whole-day classroom is SAVED
  after its first phase; Jev, exchange, meeting, school and day reports have NOT run.
- AWS access: the AWS connector worked again on 2026-10-14. If it fails for you, Greg re-authorizes it, or the keys go
  in `~/.config/markets/env` (chmod 600; see `KEYS.md` and `research/kalshi/creds.py`). Never echo a secret. Keys do
  not rotate during the walk (Greg's standing decision).

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
  in section 3 and his current instructions above. The earlier one-day E2E authorization is not permission to restart
  this stopped box or resume the saved day; the current test scope is a small timing run after source work.

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

**The earlier goal (historical, not current launch authorization):** run ONE day, `e2e-20231018-a2/20231018`, end to end through every piece, on
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

## 4. The day's state, read on the box 2026-10-14 01:2xZ (box now STOPPED)

Code on the box: `/opt/frankie-box/code/current` = `2f02022`. On boot nothing auto-starts: no frankie unit or process
ran during the read. Disks: root 63% used (743 GB free), archive 73% used (559 GB free).

| Piece | State |
|---|---|
| Teacher | DONE. Published 2026-10-10 20:18:42Z: manifest `complete: true`, 47 blocks, all 771,787 rows merged at publication, `receipt.json` (144 MB). Teacher account (`teacher-account.md`, 281 MB, 23:00Z), `teacher-findings.json`, `teacher-knowledge.json`, `teacher-second-set-read.boss.json` written |
| ROOT finish | DONE. `finish_end` 2026-10-10 23:54Z, then the big files moved to the archive disk (symlinks plus `.ARCHIVED.README.txt` beside each) |
| Classroom blocks | DONE. All 47 block sessions (`blocks/<n>/session.json`) |
| Whole-day classroom | SAVED, not finished. Started 22:25:51Z on 2026-10-10; its first phase `package` completed (6,177 s, about 1.7 h); at 00:09:20Z on 2026-10-11 a stop was requested and it saved itself ("every completed operation and the continuation state retained"; `saved-phases/<sha>.pkl` 2.6 GB) |
| Jev, exchange, meeting, school, day reports | NOT RUN |
| Queue | Both workers parked `waiting_owner` since 00:09:34Z on 2026-10-11: "the class is saved on its owner; ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 resumes it" |
| Swap | Not active (lost at every box start; see section 7) |

Paths: teacher outputs `/opt/frankie-box/work/experiment-teacher-rows/20231018/`; classroom
`/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/classroom/` (`phase-progress.json`,
`saved-phases/`, `blocks/`); queue `/opt/frankie-box/work/frankie-queue/` (`class.json`, `root.json`, `logs/`, `save/`).

OPEN QUESTION: what requested the classroom stop at 00:09:20Z on 2026-10-11 is not identified. Nobody in the Claude
session sent a save (no AWS access then). The `save/` folder holds older `.resumed-*` request markers from Oct 8-9;
the read did not show a new request. It coincides with the root worker's re-kick after the finish ended (23:54Z) and
the root worker's `worker_end` at 00:09:34Z. Find the cause before relying on a long unattended day-end run.

Also seen: the teacher manifest still carries `reason: "merge end: ValueError: no row was fed"` from the 08:27Z
failure, beside `complete: true`; the publication pinned the sealed blocks after the `2f02022` fix. The class worker
log contains older "ROOT is refused under the plan's shared market policy" lines from earlier sessions (the resume
on Oct 9 overrode them); they are not from this run's end.

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
- 12:52Z AWS access lost; it did not return until 2026-10-14. Unseen in between: the teacher finished its second
  set and published at 20:18Z; the whole-day classroom started at 22:25Z; the ROOT finish ended at 23:54Z; the
  classroom saved itself on a stop request at 00:09Z on Oct 11; the box then sat idle about 2.5 days.
- 2026-10-14: AWS back. Box stopped on Greg's order (about 01:0xZ), started for a 10-minute read-only look
  (01:2xZ; section 4), stopped again. Nothing was lost by the stops: the box had been idle and the class saved.

## 6. The evidence-hash cost (byte-identical faster encoder now approved; see continuation above)

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

Recommendation originally given to Greg (historical; the continuation above records his approval):
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

Greg has now approved the byte-identical faster encoder. Integrate all authorized efficiency work before the one
small timing run; its shadow mode compares the candidate and legacy bytes. Do not substitute a full day resume for
that test, and do not claim a speedup from source inspection or from shadow-inclusive wall time.

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

## 8. Next steps, in order (only on Greg's word)

1. Complete and review the integrated efficiency source changes, push with [skip ci], then present the concrete
   block-1 timing run. This small run is the test; no separate test suite, per-change benchmarks or full-day resume.
   Start the box only with Greg's word, restore disk run speed first, keep visibility throughout and stop promptly.
2. If separately authorized to finish the saved day: start the box, tag KeepRunning=true, `swapon` (section 7), find what requested the 00:09Z
   classroom stop (section 4) so it cannot recur unseen, then `ACTION=resume`. The whole-day classroom continues from
   its saved `package` phase; then Jev, exchange, meeting, school and the day reports. Watch it the whole time; stop
   the box the moment it is done or if access to it is lost.
3. Bring the whole-day teacher account (`teacher-account.md`, 281 MB; read it on the box or excerpt it) and the
   day-end reports to Greg; the block-1 report is already in the repo (`TEACHER_REPORT_20231018_BLOCK1.md`).
4. The two historical questions ("250 M per sec" and "the other 8 on 8 consecutive days") still need Greg's meaning.
   They are not permission to start more days or change the scientific work.
5. Discuss the swapfile and archive-volume change separately. Keep all data, snapshots, S3 and Lightsail as directed.
   Neither an extended run nor removal/resizing of retained storage follows from source optimization approval.

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
