# Drop-in: Frankie, session 11 (from session 10, 2026-10-09)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). Parent only; helpers (model opus) do the source work; AWS via the Aws connector (one
read-only STS call first). Branch ccr-d2f8f826-iefeah-frankie; SHALLOW: git fetch --deepen=400. Read
research/kalshi/frankie_boss/DROP_IN_CLAUDE_20261009_SESSION11.md (this file), then the rules in
DROP_IN_CLAUDE_20261009_SESSION10.md, then BOX_RECORD_20261009_S10.md (newest last).
Everything from session 10 is DONE, committed and ON THE BOX. This session has two jobs, in order:
  1. RELAUNCH day e2e-20231018-a2/20231018 at the teacher on its SAME attempt (commands below).
  2. INSPECT ROOT from start to receipt for anything session 10 missed (one helper, read-only first, then fixes
     pushed straight to the box): second passes, whole re-reads where a claim would do, coded waits, code-version
     comparisons, gates that block fine data.
Greg's rules (DROP_IN_CLAUDE_20261009_SESSION10.md, top): launch first and keep it running; our own gates never
block fine data; no coded waits; no staging points (fixes go on the box the moment they are pushed); code version
recorded, never compared (every save keyed on data + a format integer); no lists; no records of code changes;
disregard failing tests unless they show a data/run problem; never change the science.
```

## State at handoff (session 10 end)
- Main box i-035994afa8bdf66a5 (r7i.16xlarge, us-east-1): STOPPED at the end of session 10, KeepRunning=false.
- Code on the box: the session-10 tip 45d0b10c (direct push; see the box record for code_root). /opt/frankie-box/code/
  current points at it; CODE_ROOT defaults to the newest staged/pushed checkout.
- Day a2/20231018: ROOT complete and receipted in /opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1
  (receipt 2026-10-08 17:46Z). The 07:11Z relaunch on the old code was refused by the shared-policy CODE HASH (fixed
  in 8c34302); that refusal ended the finish 'failed' and released the owner and the 64-CPU booking. Nothing was
  lost. NOT resumed in session 10 (Greg: no launch in session 10).
- Digest: not rendered yet; saved tables 0000/0001 and table-0002's passes in
  R/.digest-bb89b168639a4b768e3a21df0f79ab04 are REUSED by the new code (1bebbd2, checked against old-code saves).
- Volumes: root vol-0d36715924f03b86c at 16,000 IOPS / 1,000 MiB/s since 06:37Z (the plan was 1,250: raise it to
  16,000/1,250 once AWS's 6 h cooldown ends, ~12:37Z 2026-10-09, before the render). Archive vol-004b68c077be09cc9 at
  10,000/1,000 (revert to baseline when the day is done). Root volume free: ~716 GB; archive ~1.6 TB.

## Relaunch (job 1), over SSM via the Aws connector
1. StartInstances i-035994afa8bdf66a5; CreateTags KeepRunning=true; wait SSM Online. Raise the root volume to
   16,000/1,250 if the cooldown has passed (DescribeVolumesModifications first).
2. On the box (CODE_ROOT/MARKETS_SHA default to the newest checkout; give them explicitly from the box record):
   ```
   RUN=e2e-20231018-a2 DAY=20231018 ATTEMPT=e2e-20231018-a2-20231018-a1 SIZE=64 \
   REASON="resume at the teacher on the receipted ROOT after the code-hash policy refusal (finish e6d70d12 07:11:07Z)" \
   BY=parent sh deploy/aws/box/frankie_box_queue_repoint.sh
   ```
   expect: status repointed, phase finish, finish unknown, size 64. Note the booking id it prints.
3. `ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_frankie_queue.sh` (expect phase finish)
4. `FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018 sh
   deploy/aws/box/frankie_box_frankie_queue.sh` (validate is off by default now; the kick returns at once). The
   finish re-admits the day at the teacher on the -a1 ROOT. Probe:
   `RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_day_status.sh`.
   Fallback if 64 CPUs cannot be booked: step 4 alone (the failed finish retries once per worker start on the plan's 32).
5. Before the kick, look at /opt/frankie-box/work/experiment-teacher-rows/20231018/receipt.json: if a stale teacher
   publication is there that does not bind this ROOT/ingest, Run.teacher refuses it (a conflict with retained output in
   the same directory); move it aside with a note, then kick.
6. Once the teacher runs: the digest INSIDE the day's booking, with the NEW booking id from step 2:
   `CODE_ROOT=<checkout> MARKETS_SHA=<sha> OUTPUT_ROOT=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1
   FRANKIE_RENDER_BOOKING=<booking from step 2> bash $CODE_ROOT/deploy/aws/box/frankie_box_render_digest.sh`
   (resumes from the saved tables/passes; the parts go to the archive volume automatically when root is tight; it
   prints a "DIGEST disk plan" line).

## What changed in session 10 (all on the box; details in the commits)
- No coded waits: event-driven hand-offs (frankie_box_wake: inotify / pidfd); kicks return at once; workers live until
  their scope is done; a parked scope re-kicks on the next queue change or when the file it waits on appears; the CPU
  watchdog is event-driven with no cap; classroom stop file watched.
- Code version recorded, never compared: in the queue, the wrappers, and EVERY save/checkpoint (teacher, classroom,
  search, scientific teacher, exchange, Jev, day reports, digest, ROOT/native/projection, ingest, research pins).
  Kept compared on purpose (science identity): the experiment runner's controller/scorer hashes, the reproduction/
  reformulation tables; two research pins that mix model weights with code (context_session, mbo_source).
- One pass: the ROOT-boundary clean no longer copies ~1 TB; journal/ledgers/digest taken by claim everywhere; the
  timeline reads each stream once; the teacher's walk feeds the classroom (carry) and the exchange/Jev (cutoff
  context); the scientific teacher reuses its result / reads only the FINALIZE rows; the digest is written once with
  no assembly copy; the SOCRATIC/VERIFY learner shares the teacher's walk (Greg's yes); the teacher resumes by seek.
- Validate off by default; FRANKIE_* settings forwarded to every later step.
- Fleet: a box keeps its days end to end, enforced.
- Direct code push: deploy/aws/box/frankie_box_push_bundle.py (parent side) + frankie_box_push_code.sh (box side):
  delta pack -> S3 presigned -> SSM, ~10-25 s; the GitHub stage is a fallback only.
- The shared-policy gate that refused the teacher is gone; the receipted ROOT is always used.

## Watch on the first run (untried on the box)
- Granite meeting start: llama-server /health is now checked when the server writes a log line or exits (no 2 s
  poll). If the server does not log after it turns healthy, the start waits out the meeting's own budget.
- The digest's disk plan uses a 1.5x bound (an assumption); its line says where the parts go.
- Everything above is source-built; only the pushes and the 07:11Z refusal ran on the box in session 10.
