# Drop-in: Frankie, 2026-10-07 night (session 2 of the agents' pass)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg, 2026-10-07 night). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip matches the last commit named at the bottom of this file (or newer).
2. Read this file, then REVIEW_20261007_EVENING_SLICES_AND_READINESS.md and
   REVIEW_20261007_EVENING_SECOND_PASS.md (both under research/kalshi/frankie_boss/).
3. Session = parent only: relay Greg's go, assign roles, commit returns by path, push. Spawn agents with
   model "opus" (Fable usage ran out). Every role: api-and-interface-design first; AWS via the Aws
   connector (mcp__Aws__aws___*, signed in as account root, read AND write); the project aws-mcp is expired.
4. NO RUNS until everything is right (Greg). No E2E, dispatch, box start, model call or install without
   his explicit go. Filling in historic day-file data is NOT a run (Greg).
5. Open list below, in order.
```

## Greg's decisions this session (all binding; code reflects them unless marked open)
- Jev uses Granite's settings, ALL of them (weights, build, runtime path, context, output, caps, ceilings,
  completion). No separate Jev pin set, no approval gate. (725dffd1)
- Granite and Jev SHARE ONE worker CPU of the day's lane, threads=1, sequential, wait recorded; no box,
  host or reserved block of their own. (725dffd1, 53678055)
- ALL days run on the main box i-035994afa8bdf66a5 (r7i.8xlarge = two 16-CPU lanes). No days on the small
  box i-0d17573dbce871520; its route stays an unused listed fallback. No install on the small box.
- The run is day-quantity agnostic (1, 2, 3 or N days, configured identically).
- The 99 layers combined for Frankie FIRST. The 2026-09-29 "no bedrock in the experiment" decision was
  REVERSED long ago; the native (bedrock) pass is ON by default for every new run (725dffd1, 05e97286).
- Clocks: clock_model_evaluation is stamped from the real Granite/Jev calls (frankie_box_model_clock.py,
  53678055, 445d6789); clock_prospective_discovery_confirmation is stamped at stage 10 (cc35cabd).
- Everything gets mapped to a 99 entry (closest entry with the reason when no exact fit). A value with no
  intrinsic event time is placed at 14:00 ET of its trading day with the note "this is not a
  time-specific event"; if published after 14:00 ET, at its publication time (never before availability).
- There must be 30 day files (Frankie's 13 points), not 17; an agent fills the historic data.
- KeepRunning means "only while in use": the run sets it at claim and clears it on every exit path; the
  idle guard (deploy/aws/idle_instance_guard.py + frankie_box_idle_guard.yml) stops idle Frankie boxes.
  The guard workflow is NOT on the default branch yet (it would fire every six hours there); hold it.

## Account state (real changes this session, as root)
- Inline policy FrankieBoxStep8A-20261007 on role Ssm (fbb4bcb), plus KeepRunningDescribe and
  KeepRunningTagMainBox (ec2:DescribeInstances; ec2:CreateTags on the main box, KeepRunning keys only).
- Pinned install on the main box at /opt/frankie-box/granite: llama.cpp b11440 and Granite 4.2 3B Q4_K_M,
  sha256s in CCODE_STEP8_REMAINDER_RETURN_20261007.md section 9. One install serves Granite and Jev.
- Both boxes STOPPED, KeepRunning=false, KeepRunningPolicy tag set.

## What landed (work branch, all SOURCE-BUILT / RUNTIME-UNVERIFIED)
9a2cf53 stage 12 | eff34d5 stages 4/6/7 | eca308a stage 5 | 7211b0d stages 8/9/10/14 (stage 10 built) |
06cb302 adviser/Granite/Jev, token stacks | c8c8fb0 Step 8 branch merged | 05e97286 day reports 99-table,
native-layer records | 725dffd1 Step 8 follow-up (native ON, B1-B5, stage 10 wired, Jev on Granite,
shared CPU, main box only) | 445d6789 Jev clock | cc35cabd confirmation clock | 53678055 model clock |
b72d8959 teach.facts missing-coverage, same-batch exclusion | 9464189e one 99 registry + core carry +
discovery producer | 52c44a20 classroom computes 12 of 18 native entries + external points.

## Open list, in order
1. Commit whatever the three agents running at the session end returned (see the bottom of this file):
   the Step 8 fixes of the second review (F1 BLOCKING: a waiting finish turns Jev into a permanent
   refusal; F2, F3, F6, F7, F8, F10, F11), correction_consumer's F5/F9, and the 30 day files.
2. Finish what they did not, then ONE fresh independent review of everything since 0166c4d1 (the review
   of the reviews' fixes and today's late slices), then integrate to ccr-5fce7de3-xa4hfg.
3. The 30 day files: complete, verified (values vs source, no future leak, receipt hashes), every point
   mapped to its 99 entry with event-time basis; the existing 17 preserved under
   frankie/day_external_superseded/<stamp>/ before any new write. Days without ingest are listed, not ingested.
4. Queued small items: Jev's sit_in no-room refusal hook into the model clock (jev_cpu SI.LOCAL);
   GRANITE_MEETING_RUNTIME_V1.json threads_rule wording; classroom's own A-clean word.
5. Greg's calls still open: (a) the six native entries no computation uses (order_lifecycle_clears,
   contract_session_roll_state, complete_state_reset_bootstrap_receipts, price_and_book_path,
   derived_price_flow_book_paths, derived_v4_mechanics_fifo_features): stay context, or he names the
   computation; (b) PySR install on the box for the discovery producer; (c) which day is day 1 (complete
   days with ingest + journal + day file in S3: 20221011, 20221012, 20221018, 20221019, 20231003, 20231004,
   20231010, 20231011, 20231017, 20231018); (d) the idle-guard workflow onto the default branch.
6. Then, on Greg's go only: the one-day E2E configured as the N-day run, the per-piece inspection reports,
   review with Greg and Frankie.

## Session-end state of the running agents
(appended by the parent below as they return)

### ccode_step8, second-review fixes (08e25531, partial)
DONE: F1 (a) Run.jev_done_receipt reuses a done Jev receipt; (b) queue _rebook_owner keeps a waiting
finish's owner binding with a recorded rebook decision and held_bookings, Run.jev_rebooked accepts it;
F3 inspection on every outcome (queue and disk-floor stop); F8 malformed day file = integrity, unreadable
= waiting; F10 reporter spawned without preexec_fn (taskset + start_new_session).
NOT STARTED: F2 and F11 (pod_root/controller.py), F6 and F7 (successor_dispatch waiting_school branch),
the F4 check (all99_admission reads native-layer-records.json; group stand-in gone), jev_cpu SI.LOCAL
model_clock hook, GRANITE_MEETING_RUNTIME_V1.json threads_rule wording, all99_admission via
frankie_box_all99_coverage.field with a canonical word, classroom_v2.py:282 input_witness path,
granite_meeting voice path recording selected['listed'], return record section 12.
Gap it named: a failed finish on the one-slot ROOT+finish route keeps its old owner binding with exact CPUs.

### correction_consumer, second-review fixes (cceb1911, partial)
DONE: F5 (boss_session derive bedrock_off_cause: caller_override / legacy_plan / native_pass_failed /
unstated, basis recorded; derive.json byte-identical when bedrock is on).
NOT STARTED: F9a late pieces in the day reports (late_pieces_changed; Run.reports_stale must return True
on it, ccode_step8), F9b current lessons after reuse or successor, reach_of on piece_disposition with the
canonical disposition/class (registry 9464189e), the dated section in SAME_SESSION_CORRECTION_CONSUMER.
Requests: experiment_root._calculate_day passes bedrock_off_cause; Run.reports_stale uses late_pieces_changed.

### Day-file agent (30 day files): see the next section if it returned; otherwise its state is unknown.
Before any day-file work, list frankie/day_external/ and frankie/day_external_superseded/ in S3
(bento-568968024170-us-east-2-an) to see what it wrote; every new write should have a superseded copy.
