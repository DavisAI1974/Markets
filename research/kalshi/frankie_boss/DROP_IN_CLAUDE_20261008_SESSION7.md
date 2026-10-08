# Drop-in: Frankie, 2026-10-08, session 7 (handoff from session 6; Greg paused for the night, boxes STOPPED)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer. The clone is SHALLOW: `git fetch --deepen=400`
   before any merge-base question (session 6 lost ten minutes to "no common ancestor").
2. Read THIS file, then the "Session 6" sections at the end of E2E_ONE_DAY_20231018.md (handoff, review fixes, ROOT
   dedupe, digest, endings), REVIEW_20261008_STAGE_HANDOFF.md, DEDUPE_PASS_20261008_WORKFLOW.md, ENDINGS_PASS_20261008.md,
   AWS_TOOLS_STACK_20261008.md (section 7 = digest rendering services).
3. Session = parent only; spawn agents with model "fable"; api-and-interface-design first; AWS via the Aws connector.
   Permission mode: Greg runs the session in auto normally; in another mode the agents' SubagentHandback is refused and the
   parent cannot direct a kill/resume (the classifier blocks it): agents then report by SendMessage to main.
4. FIRST: the main box i-035994afa8bdf66a5 was STOPPED at the end of session 6 (KeepRunning=false). Start it only on
   Greg's go; then the day e2e-20231018-a2/20231018 is SAVED (see "Run state") and resumes with ACTION=resume + ACTION=kick
   on the newest staged checkout; the teacher starts next.
```

## Run state at handoff (session 6, VERIFIED 03:17Z 2026-10-08)
- Main box i-035994afa8bdf66a5 STOPPED 03:17:03Z (KeepRunning=false); root vol-0d36715924f03b86c + archive vol-004b68c077be09cc9
  kept. Other instances already stopped: us-east-1 i-0d17573dbce871520 frankie-linux-r7i4xl (r7i.16xlarge, the second box),
  us-east-2 i-08cee7171c0a76a04 markets-year-pull-v2. Only EBS storage accrues.
- Day e2e-20231018-a2/20231018: root.json state SAVED on its marker (save/e2e-20231018-a2-20231018.save-request.json standing,
  written 03:09:51Z on 6076950; archived by the next ACTION=resume), booking ...-3111 retained (CPUs 0-31), owner commit
  6076950, NO receipt, derive.json still the 01:33:06Z one, no teacher. Three ROOT kills tonight, all 'saved' on the marker
  path: c9bf631 02:08:14Z (digest), e0d7ae0 02:59:54Z (layer parse), 6076950 03:14:11Z (layer parse).
- Operator records of this session: BOX_RECORD_20261008_S6_{PROBE,HOLD,CLEAN,RELAUNCH}.md (+ the hold watcher and clean-a2 v2
  scripts as .txt) in this directory.
- Run e2e-20231018-a2, day 20231018 (a CLASSROOM-ARM day: plan classroom_arm=['20231018'], role discovery, cls midweek),
  attempt e2e-20231018-a2-20231018-a1, R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1, booking
  day-run-20231018-day_slot_root-1791402822-3111 (CPUs 0-31) RETAINED through every save. Expected final state: entry SAVED
  on its day-bound marker, calculations-receipt.json WRITTEN by the resumed ROOT on checkout 6076950 (digest off, clean off),
  no teacher started. If the receipt is ABSENT (the shutdown killed before it): the next resume redoes only the claims route
  (minutes) + one 7-min frames read on this old seal, then writes the receipt.
- ROOT's digest for this day is NOT rendered (FRANKIE_ROOT_DIGEST=off). The classroom step shows a visible WAIT with the
  render command until work/derivation-digest-full.md exists: `CODE_ROOT=<tip checkout> MARKETS_SHA=<tip> OUTPUT_ROOT=$R
  FRANKIE_LANE_CPUS=<free CPUs> taskset -c <same> bash $CODE_ROOT/deploy/aws/box/frankie_box_render_digest.sh` (experiment
  roots accepted; FULL DEPTH, every row; refuses CPUs inside a live booking). Cost with the present writer ~2.4 h+ (five
  decodes of the 497 GB frames spool); the 5->2 decode reductions were being built at close (check the E2E record).
  Greg's rule, verbatim: "no! There we go dropping data like I said not to. We stream the data in and get 32 cpus and
  workers on this job." NO top-ten form. Where to render: after the teacher, before the classroom, on the whole lane
  (default), or on the stopped 64-vCPU second box via an EBS volume clone (Greg's go; AWS_TOOLS_STACK section 7).
- Box disk: root volume ~794 GB free after the manual clean (198.7 GB of redundant native segments zipped at 19.8x to the
  archive volume; the 472 GB inline layer STAYS: the resume's reuse witnesses it through safe_path, symlink refused; the
  497 GB frames spool and 194 GB native ledgers stay for the same reason; bind mount is the sanctioned route, built in
  root_move, runtime-unverified). Archive volume /opt/frankie-box/archive 1.71 TB free. experiment-teacher-rows is a REAL
  empty directory again (+ README naming the archived tar.zst). Both volumes stay attached across the stop.
- Staged checkouts on the box: c9bf631 (a2's ROOT seal), ebc7ef3, b474c51, 7468399, e0d7ae0, 6076950 (the resumed one).
  Resume on 6076950 or a newer staged tip; never a WIP snapshot (every "WIP snapshot" commit is mid-edit by design).
- Session 5's container was still alive during session 6 and pushed two BOX_RECORD_*.md files; its disk guard
  (pid 32657, 15 GB floor) may still run on the box; harmless.

- 03:12Z UPDATE: the second resume on 6076950 did NOT reach the receipt either. Cause (exact, from the box): the sealed-
  record shortcut missed because frankie_box_monday_calculations.inline_layer_without_array anchors its tail parse on
  `"reason"` right after the array's `],`, while a2's sealed layer ends `], "producer": ..., "reason": null, "status":
  "derived"`; so load_retained_layers fell back to the whole Python parse of the 472 GB inline layer at ~27 MB/s (4.8 h).
  Greg ordered the shutdown; the child was killed with the marker standing -> SAVED, NO RECEIPT. The fix IS ON THE TIP (commit 133c9ba or newer): inline_layer_without_array anchors on the array's top-level close
  (any trailing keys), spool claims carry their sealed counts from the ROOT's own records (INPUT/prices/frames/structures/
  failures), the legacy-stage reuse takes every spool by claim; toys 29/29 + 17/17. STAGE IT (frankie_box_run.yml stage_code
  ACTION=stage on the work branch) before the next resume; the resume then reads the layer's head + 64 KiB tail and each
  spool's 64 KiB tail (no big read) and writes the receipt in minutes.

## What session 6 built (ALL SOURCE-BUILT / RUNTIME-UNVERIFIED unless marked LIVE)
- LIVE on the box: the hold (save marker at projection) fired exactly as designed; ROOT c9bf631 SIGKILLed mid-digest
  (02:08Z) and again on e0d7ae0 (02:59Z) with the marker standing -> entry SAVED both times (Run.child check_save after
  proc.wait, SystemExit 75); resume + kick on a new checkout with FRANKIE_* run settings in the kick env (FA-6) works;
  the queue's source rebind at admission works; the manual clean (clean-a2.sh v2, 168 s, 3 zips) works.
- Stage handoff (frankie_box_stage_handoff.py, root_move.py, root_validate.py; wired at every piece in frankie_queue):
  validate once on the lane -> the day's own save marker -> detached clean+zip+move (symlink; bind mount for guarded
  prefixes; redundant native segments by exact arithmetic; Glacier second copy in an unpinned unit) -> automatic
  resume+kick on the launching checkout -> next stage. Single switch FRANKIE_CLEAN_ON_SAVE (default on). Review:
  BLOCKED as wired -> patches A-I applied (101/101; probes 0 defects). Greg's calls open: finding 10 (small stages do
  not stop after validating), finding 12 (DIGEST off by default on non-classroom days; on for classroom-arm days).
- Durable writes hash on the write stream (no read-back; FRANKIE_DURABLE_READBACK=on restores); file claims
  FRANKIE_FILE_CLAIM_V1 at the seal and on reuse (stat + last 64 KiB); legacy-stage/native/INPUT/pickle double reads
  gone; projection pool lane-sized; FRANKIE_ROOT_DIGEST run setting; the retained-digest route for experiment roots;
  classroom visible WAIT; a live TypeError at experiment_root.py:418 fixed (every shared-policy ROOT would have crashed
  at its receipt on the tip).
- Dedupe pass over every other piece (9 items), endings pass (classroom answers pooled, side writers, brain publication by
  claim; teacher attachment pickle beside the snapshot); blocked identity-bound items B1-B6 named for Greg's re-pin.
- ROOT AWS audit (day_external on the shared transport, probes in bytes, bounded stops; gateway endpoint exists in
  us-east-1; R1 cross-region reads decision; R2 fs settings canary). AWS tools research: 113 skills, six stacks, dry-run
  account stack script deploy/aws/frankie_aws_stack.py; no render skill exists; best digest stack = same renderer on
  more cores (second box 64 vCPU 14 min/pass; r7i.48xlarge ~5 min/pass needs the 640-vCPU quota).

## Open, in order
1. Start the box (Greg's go), confirm saved + receipt, resume + kick a2 on the newest staged tip with FRANKIE_ROOT_DIGEST=off
   (the digest is rendered separately) and FRANKIE_CLEAN_ON_SAVE as Greg decides (off = a2's clean stays manual).
2. Render 20231018's digest (full depth) before the classroom: where/when per Greg; run the 2 GB canary first.
3. Commit/stage whatever the digest role left (5->2 decodes, spool claims with the sealed count, canary scripts).
4. Greg's calls: findings 10/12; (f) archive policy both (volume + Glacier) decided, S3 bucket region (R1); (c) decided as
   claim + stat + tail (never stat alone); the re-pin list B1-B6; the second-box/48xlarge digest render.
5. Switch the session back to auto before the automatic chain runs unattended.

## Digest commands (full depth, nothing dropped; FRANKIE_DIGEST_DECODES unset = 2 decodes, ~58 min on 32 CPUs for the frames table; =5 = the present writer, same bytes)
- Canary first (2 GiB slice of a2's frames spool, old writer vs new, sha256 of both, ~2 min on a 16-CPU lane; dry run without RUN=1):
  `CODE_ROOT=/opt/frankie-box/code/<tip>-<run>-1/markets FRANKIE_LANE_CPUS=<free CPUs> RUN=1 bash "$CODE_ROOT/deploy/aws/box/frankie_box_digest_canary_slice.sh"`
- Render (after R/calculations-receipt.json exists; refuses CPUs inside a live booking):
  `R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1; CODE_ROOT=<tip checkout> MARKETS_SHA=<tip> OUTPUT_ROOT=$R FRANKIE_LANE_CPUS=<free CPUs> bash "$CODE_ROOT/deploy/aws/box/frankie_box_render_digest.sh"`

## Tip at handoff
- Work branch tip at handoff: the commit carrying this line (parent of this commit = ff9364a: digest decode ladder + canary;
  133c9ba: the resume fixes). Stage THIS tip or newer before the resume; every "WIP snapshot" commit in between is mid-edit.
