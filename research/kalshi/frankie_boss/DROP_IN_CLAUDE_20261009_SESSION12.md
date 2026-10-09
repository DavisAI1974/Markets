# Drop-in: Frankie, session 12 (from session 11, 2026-10-09)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). Parent only; helpers (model opus, worktree isolation, disjoint file sets) do the source
work; AWS via the Aws connector (one read-only STS call first). Branch ccr-d2f8f826-iefeah-frankie; SHALLOW:
git fetch --deepen=400. Read research/kalshi/frankie_boss/DROP_IN_CLAUDE_20261009_SESSION12.md (this file), then the
rules in DROP_IN_CLAUDE_20261009_SESSION10.md (top), then BOX_RECORD_20261009_S11.md (newest last).
THE GATE (Greg 2026-10-09): the FIRST CLASSROOM SESSION between the teacher and Frankie on day e2e-20231018-a2/20231018
must run end to end; nothing moves on until it does. Greg most wants to read the teacher's report (its own account).
Greg's rules added in session 11 (binding, on top of session 10's): never a size-based decision that weakens the science
(no value cut, capped, sampled or summarized to fit memory/time/bytes; only copies avoided); the teacher reads ALL the
99 planes streamed to it pinned together with the book and the event flow, and builds a second set beside the pinned
columns (read beside, never reconstruct the pinned functions); whatever Frankie sees is pinned on the 99's clocks and
must match; rows already done are merged at publication, never backfilled by recompute; push every fix to the box the
moment it lands; try an AWS call before scheduling it on an assumed cooldown; no infrastructure change calls at the end
of a session, let things land; new session after everything lands.
```

## State at the hand-over (12:09Z 2026-10-09; the box record has every step)
- Main box i-035994afa8bdf66a5 (r7i.16xlarge, us-east-1) RUNNING, KeepRunning=true. Root vol-0d36715924f03b86c
  16,000 IOPS / 1,250 MiB/s (accepted 11:19:57Z; let it finish optimizing; NO volume changes this day). Archive
  vol-004b68c077be09cc9 10,000/1,000 (revert to baseline when the day is done, not before).
- Code on the box: 4447d0fb (push 12:17:50Z, 10.9 s, delta over 2fb5ea06) is `current` = the GitHub tip. It carries
  26da953f (the CPU watchdog and the queue's control calls are helpers for every booker) and dec04c8e (the deeper
  TEACHER REPORT: frankie_box_teacher_findings.py, the <day>-teacher-account brain entry, learner_context
  ['teacher_account'] in TEACH). The running teacher (pid 10141) keeps 2fb5ea06; the class worker and the reports pick
  up 4447d0fb. Push route: build the pack
  (frankie_box_push_bundle.py build --base <box commit>), upload by presigned PUT to
  s3://frankie-granite42-568968024170-us-east-1/readiness/20260923/code-push/<sha>/<pack sha>.pack, presign GET, SSM:
  export the pin variables + BUNDLE_URL and `sh "$(readlink -f /opt/frankie-box/code/current)/deploy/aws/box/
  frankie_box_push_code.sh"` (~10-20 s); frankie_box_push_code.sh is unchanged since 45d0b10c.
- Day a2/20231018, attempt e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_repoint-1791535148-1706
  (64 CPUs), root worker pid 9964 (2fb5ea06), FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all carried:
  ROOT complete and receipted (2026-10-08 17:46Z) WITH bedrock. TEACHER running: pid 10141 on 2fb5ea06 since 12:02:26Z,
  resumed by seek from cursor 432,473 with the second set (planes joined on every row, book read, state split, carry
  feed, 1% guard); 435,200 rows (56.4%) at 12:08:48Z, failed 0, errors 0, sharing the 64 CPUs with the render (load 75).
  Rows done before 432,473 get the planes/book read/split merged at publication. DIGEST render running since 11:12:31Z
  (unit frankie-digest-render-111231, log logs/20231018-digest-render-20261009T111231Z.log; on table-0002, errors 0;
  work/derivation-digest-full.md not yet written). CLASSROOM not yet run; the class door (new code) waits for the digest
  event-driven, then the class worker runs classroom, data, search, batch lessons, frankie_lessons, exchange, voice
  (Granite meeting), school, reports inside the booking. Granite runtime verified on the box 11:05Z.
- Scheduled self check-ins of session 11: all cancelled or fired; session 12 owns the probes. Box progress file:
  /opt/frankie-box/work/experiment-teacher-rows/20231018/progress.json; day status: RUN=e2e-20231018-a2 DAY=20231018
  sh deploy/aws/box/frankie_box_day_status.sh.

## FIRST ACTIONS of session 12 (in order)
1. STS (read-only), then one probe: progress.json, the newest /opt/frankie-box/work/experiment-teacher-rows/logs/*.log
   (second-set join, book read, guard lines, any traceback), the digest render log, free memory. PROBE RULE (session-11
   slip): never pin a probe onto CPUs the day holds (the booking is 0-63 = the whole box); a pinned probe is a legitimate
   CPU holder and the slot booking waits on it (now recorded as finish_slot_waiting). Use `systemd-run` without
   CPUAffinity or a short foreground command.
2. DONE in session 11 after the hand-over: the report-deepening helper landed dec04c8e (merged 4447d0fb, pushed to
   GitHub and to the box 12:17:50Z). It was checked on synthetic files only; the first real render is this day's TEACHER
   REPORT. Its assumptions to verify on the box: the sidecar's dstate layout (`status` / `state`), book_columns
   (`group.depth` / `group.sides.*.differs`), the MISSING/INVALID reason wording REASON_WANTS matches by token, that
   teacher-knowledge.json exists when the report renders. Every failure path is listed in the report, never fatal.
3. Nothing to push at the start: the box is on the GitHub tip. Any new fix: the route above.
4. Watch the teacher to publication (rows/s, memory; the publication merges planes onto the earlier rows and writes the
   sidecar, teacher-second-set.pkl, teacher-state-split.json, the full-list files, the receipt with `account`), then the
   class door opening on the digest, then the class worker's steps (first run of every one), then the reports:
   ROOT REPORT #N, TEACHER REPORT #N, classroom report, Frankie report. Give Greg the teacher's report whole.
5. If anything stalls: root-events.jsonl (finish_slot_waiting / root_slot_waiting name the holder), the day status, py-spy
   (in the box venv) on the parked process; fix the moment found, push, continue. Pausing at the classroom boundary is
   acceptable (Greg); proceeding without the digest is not.

## What happened in session 11 (the commits are the record; this is the map)
- Relaunch: a2 re-pointed on 64 CPUs, resumed, kicked; the teacher ran from 08:39Z.
- ROOT-chain inspection (read-only, then 27 commits in two batches): one-pass (the ~194 GB ledger read-back gone,
  write-stream witnesses, claims), every coded wait on the ROOT path event-driven, every code-state refusal record-only,
  disk/policy gates fit-only, duplicate-data refusals -> recorded deterministic choice, a same-day entry from another run
  queues behind. Kept compared (science identity): producers pin, RunIdentity, controller/scorer hashes, reproduction
  tables; CYCLE_CALCULATION_PINS compared by parsed content.
- Teacher throughput: round 1 (ship window rows without books) gave no gain; the ceiling is the number of Python objects
  pickled per batch (parent writes 15 MB/s, 70% of its time in pickle.dumps). Round 2 (helper, in flight at hand-over or
  landed, see the record): ship each group's bytes ONCE, never a per-batch object-graph walk; the workers receive the
  FULL book again (Greg: fix the reader, the data was never unneeded).
- Greg's reader direction (binding): the teacher's SECOND SET = every streamed plane's values on each row (51
  picture-routed planes of the 99; the 9 sealed answers and 2 sealed targets withheld by role), the seven causal clocks
  and the row key (match exactly, mismatches listed), the pinned 19 columns byte-identical in `coverage_columns`/
  `components`, new `book_columns` (book-derived counterparts of the pinned measures + reconciliation vs the event-derived
  values), `state_split` (the pinned sums split by the bedrock state labels: dipole, chain, prebirth; parts sum back to the
  totals; unknown-state bucket, nothing dropped), an `account` section on the receipt (what was read together, what was
  missing, wants, what would give better outputs, findings; all from recorded facts), a JSON-lines sidecar of the rows,
  the 1% full-object guard (FRANKIE_TEACHER_GUARD_EVERY, default 100), rows done before the resume cursor MERGED at
  publication from the ROOT planes (never recomputed), publication refuses any row lacking the second set.
- Resume/kick race fixed (3da710e2): a resume kicks for itself and carries settings; a covered kick leaves its request.
- Symlink gate fixed (b8867dde): archived inputs through symlinks accepted; a tarball member witnessed by its pin.
- Classroom chain (02461af3): the class door waits event-driven for the digest in its held slot; llama-server logs so the
  /health start wakes; a data export from another ROOT moved aside; a failed meeting non-blocking. No LINE=class kick is
  needed: the finish enqueues the class line (creates class.json) and kicks its worker; the class worker runs classroom,
  data, search, batch lessons, frankie_lessons, exchange, voice (Granite meeting), school, reports inside the booking.
- Consumer side (helper, in flight at hand-over or landed): school_day_of hands a day its held number; the classroom's
  48 GB / 60 min native cutoff removed (compute everything); the four whole-file readers of the teacher rows stream;
  the classroom reader/runners, exchange ledgers, Jev cutoff scope and school knowledge READ the second set; the day
  reports render the teacher's `account` as a first-person report .md with a citation per sentence.

## The exact sequence to the classroom session (do not skip a step)
1. Every helper commit is merged, compile-checked, pushed to GitHub and pushed to the box (route above) the moment it lands.
2. The running teacher (old code) must NOT publish without the second set: ACTION=save RUN=e2e-20231018-a2 DAY=20231018
   when the second-set code is on the box (or before the teacher nears the end, ~78%); it stops at its boundary and saves.
3. Resume ON THE NEW CODE with the settings in the shell (the fixed resume carries them and kicks for itself):
   CODE_ROOT=<newest checkout> MARKETS_SHA=<its sha> FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all \
   ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_frankie_queue.sh
   (ACTION=kick is only a fallback; a covered kick now leaves its request). Probe: RUN=... DAY=... sh
   deploy/aws/box/frankie_box_day_status.sh; progress: /opt/frankie-box/work/experiment-teacher-rows/20231018/progress.json.
4. The teacher resumes by seek, reads planes beside the flow for the remaining rows, merges the planes onto the rows done
   before, publishes with the second set; the finish (now on new code) waits for the digest at the class door, then the
   class line runs. Watch the digest render log and the class worker's first steps; the Granite meeting is the `voice`
   stage (first run; the health start is event-driven now).
5. Read the teacher's report .md and the classroom report (frankie_box_experiment_day_reports.py outputs) and give them
   to Greg whole.

## Open items for the next session (NO fixes were deferred by choice; these are the ones not reachable this session)
- ONE PASS for teacher + digest (Greg 2026-10-09 12:2xZ, DIRECTION for session 12): "When we get past the point of
  messing anything up we could start on the one pass build so it's ready for the bigger normal passes that we'll be
  starting for the 30 day. And also see if we can get more workflow pieces to get their info they need from the altered
  pass. It feels like that could save us time. But the calc, derived layers that we derive won't be candidates for
  that." So: (1) not before the a2/20231018 classroom session is through (nothing on this day is touched); (2) design
  one streaming pass over ROOT's layers that yields the teacher's rows AND the digest's pinned byte-exact tables (the
  digest's construction stays pinned and still resumes from saved tables; the pass is a second producer of the same
  bytes, proven byte-exact against today's render before it replaces anything); (3) survey every workflow piece that
  re-reads ROOT's stream files or the day file (class worker steps: classroom, data, search, batch lessons, exchange,
  voice, school, reports; Jev; the consumers in frankie_box_teacher_rows / adviser_market) and list which could take
  their inputs from the altered pass instead of their own read; (4) EXCLUDED by Greg: the calculated / derived layers
  (bedrock's producers, the derived geometry, anything computed rather than read) stay as they are produced today.
  Today teacher and render run concurrently in the same booking.
- Teacher report, deeper: LANDED (dec04c8e, on the box). Still open inside it: the account writer's own lists stay at 20
  entries (clock-mismatch examples, largest reconciliation differences) while teacher-reconciliation-differences.jsonl
  lists every one; the teacher side still lacks the carry-anchor calls (enable_anchors / note_row). The brief was: discovery and correlations as
  per-cell distributions (count, p50, p90, max per pinned/book column per state bucket; the teacher key's recorded
  correlation tables whole; co-occurrence of state labels vs pinned states/reasons; reconciliation classes), "what
  blocks my signal" (MISSING/INVALID reason counts per column with the want each maps to), "depth I lack" (top-3 history
  on the non-changes path, teacher_as_of lock clock, unresolved planes, unknown buckets, the one-day limit: show vs
  claim), "for Frankie's trade signals" from the counts only, and the account + the rendered TEACHER REPORT into the
  teacher brain stage entry as content and into the classroom's learner_context['teacher_account'].
- Jev gets the second set at his cutoff (6fadb637): if Jev runs before the exchange on a day he gets the cutoff row but
  no ledgered claims (names list empty); an explicit second_set_claims list on his request is the alternative.
- The teacher's heartbeat is keyed by batch, so the teacher report may say "not recorded by my step" for time per phase.
- The old V1 classroom runner now passes learner_context into its summary (gains the second-set sentences).
- The teacher key is built three times (Run.teacher_knowledge with the _repin correlations; the classroom from the
  attachment with the hardened correlations; the exchange's own ledgers). Merging them is a SCIENCE question (two
  different correlation re-pins): Greg's call.
- Anything that reads the native ledger BYTES (frankie_box_bedrock.ledger_path, frankie_box_market_timeline's ledger
  readers) still cannot read bedrock/ledgers on a2: the bytes are inside ledgers.tar.zst on the archive volume. The
  render and the teacher do not need them today; a reader that does needs a streaming member read or a restore.
- Granite 3B GGUF as the meeting model with 8B as escalation was a size-based choice (2026-10-06); Greg's rule now says
  no size-based decision may weaken the science: raise it with Greg.
- The native checkpointer's low-disk stop is now fit-only (projected > free); its estimate is a linear extrapolation and
  omits a resumed run's final ledger copy (ends on ENOSPC rather than an early stop in that case).
- The producers pin and RunIdentity stay compared (science identity); the cycle calculation pins compared by content.
- Session-11 slips to not repeat: a find's listing cut short led to a wrong "Granite not installed" claim (verify by
  running the setup script, it only verifies); an assumed AWS cooldown delayed the volume raise two hours (try first).
