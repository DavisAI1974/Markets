# Drop-in: Frankie, 2026-10-07 night, session 4 (handoff from session 2/3)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer.
2. Read THIS file first, then DROP_IN_CLAUDE_20261007_NIGHT_SESSION2.md (section "Greg's decisions, later in
   session 2" is binding), then AWS_DEEP_DIVE_20261007.md, E2E_ONE_DAY_20231018.md and the newest sections of
   REVIEW_20261007_NIGHT_FRESH.md. All under research/kalshi/frankie_boss/.
3. Session = parent only: relay Greg's go, assign roles, commit returns by path, push. Spawn agents with model "opus".
   Every role: api-and-interface-design first; AWS only via the Aws connector (mcp__Aws__aws___*, read AND write);
   the GitHub MCP dispatches frankie_box_run.yml as the fallback route.
4. FIRST: check the main box and run e2e-20231018-a2 (saved or still running; see "Run state" below).
5. Then the open list, IN ORDER: apply the AWS stack to ROOT -> push/integrate -> relaunch (resume) a2 ->
   AWS work on every other workflow piece while ROOT runs.
```

## Greg's order that this session continues (verbatim intent)
"The intent was to build and apply the changes. Stop and apply the changes to ROOT, then push, then launch, then do
AWS work on every other piece of the workflow." The AWS deep dive found the tools; they were NOT applied yet. Greg
wants them APPLIED, stacked (use what we have plus the new ones; never pick just one).

## Run state at handoff
- Main box i-035994afa8bdf66a5 (us-east-1d, r7i.8xlarge, 32 vCPU, ~215 GiB RAM free, ~1.3 TB disk free) is UP with
  KeepRunning=true.
- Run e2e-20231018-a2 launched 19:53:42Z on code 98579cea (plan c027d58d: DAY_CPUS=32, one_day inspection, classroom
  arm, shared policy, native ON, side by side). External step done from S3 (day file d006252d...). ROOT read the
  journal with 31 workers (~11 min). At ~20:0xZ Greg ordered STOP; the run agent was told to SAVE it through
  `frankie_box_frankie_queue.sh ACTION=save RUN=e2e-20231018-a2 DAY=20231018`. VERIFY: is it saved (and at what
  position), or still running? Booking day-run-20231018-day_slot_root-1791402822-3111 (CPUs 0-31).
- a1 (e2e-20231018-a1) is retired; its booking was released.
- Resuming a2 after code changes: saved days follow the current source (205630a6). The ROOT's own identity checks
  still apply; tonight's AWS/code changes must not touch the timeline file (its hash is in the ROOT binding).
- Launch quirk: the DETACH=on start reports failure (exit 3, `systemctl is-active` after 10 s) even when it worked;
  check the box log, not the workflow color.

## Open list, in order
1. Apply the AWS stack to ROOT (none applied yet; an agent stopped before changing anything):
   - Raise the main box's gp3 throughput 1000 -> 1250 MB/s (r7i.8xlarge EBS ceiling; confirm with
     DescribeInstanceTypes; ModifyVolume; one modification per 6 h). Greg's order is the go.
   - Confirm the hyperthread map on the box (`lscpu -e` via SSM) matches the code's physical-core split (c046d6ca).
   - S3: a free gateway VPC endpoint for S3 in the main box's VPC if missing; ROOT pulls use the parallel ranged
     transfer; note the cross-region bento bucket (us-east-2) for Greg's archive/region decision.
   - Any other deep-dive item that fits ROOT on this box, safe and reversible: spool/digest I/O read-ahead and
     filesystem settings for the 300-400 GB of frames, CRT where a role holds credentials.
   - r8id clones with local NVMe, golden AMI, EC2 Fleet are for the multi-box 30-day run (new instances need
     Greg's go).
2. Commit, push and integrate any code change (integration branch ccr-5fce7de3-xa4hfg).
3. Relaunch: resume a2 (save -> resume through the queue; the day follows the current source), or a fresh a3 if
   the resume refuses. Probe every step; report the CPU spread, legacy/native rates, disk early, and units/min.
4. While ROOT runs: AWS work on every other piece (teacher, classroom, search/discovery, data, scientific teacher,
   exchange, Granite/Jev, school, reports, day files, ingest), apply-as-you-go, one agent per owner group.
5. Not yet integrated: the Granite/Jev token stacks (50a9daf9, on the work branch only, unreviewed). They are needed
   before the meeting/Jev stages, not before ROOT. Greg's open call: should Jev see recipe-encoded numbers, or
   should those two layers be switched off for Jev? Request to ccode_step8: experiment.py ~3011, the remote-route
   intent hash against the new stacked input.
6. Greg's other open calls:
   - (a) render the native tables into Frankie's digest (digest_bedrock=False today);
   - (b) digest every day vs classroom days only;
   - (c) spool archive policy and region for the 30 days.

## What landed tonight (all on ccr-d2f8f826-iefeah-frankie; integrated through 98579cea)
- Day files: all 13 ingested days complete on S3 with nothing missing (including the 2023 estimates and the three
  older history rows); 18 non-ingested days not built (Greg).
- ROOT:
  - the native pass reads records without bytes fields (ad46ca06);
  - legacy encoders with an ordered writer (9e7a7d90);
  - the pinned layer write (910ef886);
  - legacy ParallelBook, side by side on disjoint halves split by physical core with the replay on a whole core
    (8b5338d7, c046d6ca);
  - the parallel legacy digest table (bdc05a62);
  - DIGEST_V10 with a lossless bytes/nested-tuple cell, V9 still reads (8b5338d7).
- CPU: DAY_CPUS=32 (05032c5c); every piece sizes from the booked list (ee60a45f, c826cb1a, 82ca4e49); probes on every
  stage with units (dc6ac77, 2666e17); the classroom native-entry cutoff 60 min / 48 GB (4d5e585).
- Queue: retire for dead runs, and saved days follow the current source (205630a6).
- 13 points under their 99 entries with per-piece rows, the teacher's per-point list, point 6 read (3961861,
  1c993d7, ade08ce, e243b87); S3-first verified day file, no overwrite (3961861, 89d67e2).
- Classroom 18 of 18 native entries with per-level queues (83091a8, dcf97c7, d8eb215).
- Boxes: main box cleaned (12 only-copy days archived to S3 and verified; PySR 1.5.10 installed); the second box
  resized to r7i.16xlarge with 2 TB, stopped; an EC2 vCPU quota increase to 640 filed (us-east-1, request
  66c042562b594ac18e9966a1939b5b62Tf00eIjo).
- Reviews: the seventh follow-up APPROVED everything through 8b5338d7. c046d6ca and 50a9daf9 are unreviewed (Greg:
  no review needed for small fixes).

## Greg's standing rules (short)
Full data: never shrink to top 10 or drop anything; every stack lossless and parse-back proven. Pin CPUs on every step;
stack every efficiency, AWS and in-repo. Launch fast; "run it and fix after" for anything that doesn't stop the run or
change the science. No reviews for small fixes. Nothing gates ROOT on Granite. After the one-day run: multi-box ROOT
(clone boxes, number the 16-CPU groups, random day assignment, kill when done); status reports only for the one-day
run; knowledge reports plus Frankie's own report for the N-day run.

## Fix-after list
- The DETACH=on start reports failure falsely.
- The probe doesn't find ROOT's own progress file for units.
- The queue kick's environment whitelist (partly fixed).
- GitHub dispatch HTTP 500 at times.
- A dead pinned worker can hang a pool while the heartbeat says running (watch units/min).
- The disk check per lane for the multi-box run.

## Session-end state
(appended by the parent below)
