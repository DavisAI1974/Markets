# Drop-in: Frankie, 2026-10-07 night, session 3

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer.
2. Read this file, then DROP_IN_CLAUDE_20261007_NIGHT_SESSION2.md (all of Greg's decisions; the section
   "Greg's decisions, later in session 2" is binding), then E2E_ONE_DAY_20231018.md, AWS_DEEP_DIVE_20261007.md,
   and the last sections of REVIEW_20261007_NIGHT_FRESH.md. All under research/kalshi/frankie_boss/.
3. Session = parent only: relay Greg's go, assign roles, commit returns by path, push. Spawn agents with
   model "opus". Every role: api-and-interface-design first; AWS only via the Aws connector (mcp__Aws__aws___*,
   read AND write). It must be re-authorized in claude.ai connector settings if it shows as needing auth.
4. Greg's GO for the one-day E2E on 20231018 stands. Launch as soon as the open list is done.
```

## Where it stands
- Code: work branch and integration branch `ccr-5fce7de3-xa4hfg` at 5ed89bcc (integrated, reviewed through the
  seventh follow-up), plus docs after it. Everything since 18cbc5a is reviewed and APPROVED.
- Day files: all 13 ingested days complete on S3 with nothing missing (20231018 = d006252d...). The 18 non-ingested
  days are not built (Greg: don't chase days without an ingest).
- Main box i-035994afa8bdf66a5 (r7i.8xlarge, 32 vCPU, 1.4 TB free, PySR 1.5.10/Julia 1.11.9 installed) was left
  RUNNING and IDLE with KeepRunning=true at the end of session 2, waiting on the launch. CHECK ITS STATE FIRST, and
  stop it if nothing will launch soon.
- Second box i-0d17573dbce871520 resized to r7i.16xlarge (64 vCPU, 512 GB, 2 TB disk), stopped, nothing installed.
- EC2 vCPU quota increase to 640 filed in us-east-1 (request 66c042562b594ac18e9966a1939b5b62Tf00eIjo, pending at filing).
- E2E run a1 (e2e-20231018-a1) is dead: saved at INPUT 6,329, its ROOT binding pins the old timeline hash. It is
  replaced by a fresh a2.

## Greg's decisions this session (binding; also in session 2's drop-in)
- Full frame sections stay (full depth, order ids, queues, observation, native frame, INPUT records). NEVER shrink to
  top 10 or drop any data. Every stack is lossless and parse-back proven.
- A day gets 32 CPUs (DAY_CPUS=32), and every piece sizes from the booked list.
- ROOT runs native and legacy SIDE BY SIDE (FRANKIE_ROOT_NATIVE_OVERLAP=on), on disjoint halves of the 32 CPUs.
- The digest gains bytes (DIGEST_V10 X cell); V9 still reads.
- Pin CPUs on every step, and stack every efficiency (AWS and in-repo); don't pick just one.
- Saved days follow the current source (205630a6); ACTION=retire for dead runs.
- No reviews needed for small fixes; skip test slices. Launch as soon as ready; "run it and fix after" for anything
  that doesn't stop the run or change the science.
- After the one-day run: a multi-box ROOT. Clone boxes, number the 16-CPU groups 1..N, assign days randomly, kill the
  boxes when done (see AWS_DEEP_DIVE for the stacked plan: r8id clones, golden AMI, EC2 Fleet, one region).

## Open list, in order
1. Commit the two agents that were in flight at the end of session 2, if their files are on the branch. In a new
   container their uncommitted work is LOST, so session 2 waited for them; check the bottom of this file for whether
   they landed:
   - Granite/Jev token stacks (frankie_box_adviser_market.py, frankie_box_granite_meeting.py, clm_sidecar/sit_in.py,
     frankie_box_jev_cpu.py): every proven lossless stack applied to everything Granite and Jev read.
   - ROOT hyperthread-aware split (frankie_box_boss_session.py): native and legacy split by physical core, the replay
     on a core with an idle sibling.
2. Greg's calls still open:
   - (a) render the native tables into Frankie's digest (digest_bedrock=False today);
   - (b) digest every day vs classroom days only (matters for the 30 days);
   - (c) main-box gp3 1000 -> 1250 MB/s;
   - (d) spool archive policy for the 30 days.
3. Launch the one-day E2E (run agent route, from E2E_ONE_DAY_20231018.md and CCODE_STEP8_REMAINDER_RETURN section 25):
   1. Stage the integrated commit; verify HEAD and the Granite pins.
   2. `frankie_box_frankie_queue.sh ACTION=retire RUN=e2e-20231018-a1`.
   3. Release a1's retained booking (CPUs 0-15) with `frankie_box_cores.sh ACTION=release` and a reason. Greg's
      E2E go covers it.
   4. Plan `e2e-20231018-a2` with DAYS=20231018 DAY_CLASS=midweek DAY_CPUS=32.
   5. Start with DETACH=on and the presign without the day_external PUT slots; overlap on.
   6. Probe every step; send a per-CPU spread note at each stage boundary and every 30 min.
   7. Watch units/min (a dead pinned worker hangs a pool while the heartbeat says running), and check disk early
      (~400 GB frames plus the layer file).
   8. At the end, copy the inspection md files to S3, clear KeepRunning and stop the box.
4. After Greg's thumbs-up: Frankie's own report into his brain, readable knowledge reports, the horizon analysis, the
   multi-box ROOT build.

## Fix-after list (from the E2E record)
- DETACH=on start shows a workflow failure when the start worked.
- The probe doesn't find ROOT's own progress file (no units).
- The queue kick's environment whitelist (partly fixed for the overlap setting).
- GitHub Actions dispatch returned HTTP 500 at times (the SSM route works).

## Session-end state
(appended by the parent below)
