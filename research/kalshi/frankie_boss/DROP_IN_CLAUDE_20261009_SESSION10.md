# Drop-in: Frankie, 2026-10-09, session 10

Branch `ccr-d2f8f826-iefeah-frankie` (SHALLOW: `git fetch --deepen=400`). Parent only; roles (model opus) do the work.
AWS through the Aws connector (signed in 2026-10-09 as the account ROOT user; STS passed, account ...4170).
State at session start: unchanged from the session-9 PAUSE box (DROP_IN_CLAUDE_20261008_SESSION9.md): main box
i-035994afa8bdf66a5 STOPPED, a2/20231018 finish SAVED, receipt in place, digest not rendered, booking retained 0-63.

## Greg's operating rules (2026-10-09, standing; these override older drop-ins where they conflict)
1. PRIORITY ONE IS GETTING AND KEEPING THE WORKFLOW LAUNCHED. Whatever blocks it is fixed first, pushed, and put on the
   box immediately so the run moves forward.
2. A GATE, VALIDATOR OR CHECK WE CODED OURSELVES NEVER BLOCKS A RUN WHEN THE DATA IS FINE. If the only thing missing is a
   receipt for a 2nd/3rd/Nth pass that was eliminated as redundant, remove the gate and override it on the spot. Only a
   legitimate code concern (data actually missing or corrupt, a crash) stops the run.
3. FORWARD FIXES ARE MADE WHILE THE WORKFLOW RUNS, before the chain reaches that step. Never hold a launch for fixes to
   steps already passed or not yet reached.
4. NO LIST (Greg 2026-10-09). A needed fix is made the moment it is found, running or stopped; nothing is written down
   for later. The session-9 IMPROVEMENTS sheet is ELIMINATED (deleted; its open items were assigned to roles 2026-10-09).
5. NO STAGING POINTS. A fix that matters goes onto the box the moment it is committed and pushed. A non-critical fix
   rides the next box change, together with every other fix made since (steps already passed and not yet reached).
6. NO CODED WAIT TIMES. No fixed sleeps, no timed polls, no bounded lock waits on the chain: every hand-off is
   event-driven (the next stage starts the instant the previous one ends; a waiter wakes the instant its condition holds).
7. THE 6-MINUTE STAGE WAS OUR OWN DESIGN (GitHub Actions runner + pack + S3 + SSM + box helper), NOT AWS. The normal
   route is a direct push to the box in seconds; the GitHub stage is a fallback only.
8. CODE VERSION IS RECORDED, NEVER COMPARED. A running day picks up the newest code at its next step; no save/restage/
   resume just to change code. Data identity (sealed sources, pins, counts, data receipts) stays bound.
9. NO RECORDS OF CODE CHANGES (Greg 2026-10-09): the commits are the record. The only records kept are the run's own
   outputs per piece after it has run (the day reports: classroom report #N and Frankie report #N, written by
   frankie_box_experiment_day_reports.py, plus the stage receipts), read to check the piece gave the outputs and
   answered the questions it was meant to; and the parent's box record of what was done on the box.
10. Standing from session 9: one pass everywhere; no gates that re-check receipted data; an owned day is never retried
   from scratch; a box keeps its days end to end.

## Session 10 work (in flight; records below)
- Run-flow role: no coded waits (job 1) + code version recorded not compared (job 2).
- Code-push role: direct push to the box (git bundle -> S3 presigned URL -> SSM; /opt/frankie-box/code/current symlink).
- Three read-only auditors: duplicate/triplicate passes under other names (ROOT..teacher; classroom/data/search;
  scientific teacher..end). Findings go to fix roles, then everything lands BEFORE the relaunch (Greg 2026-10-09:
  "Make all of these changes and do a check for more duplicate and triplicate passes ... and get them out before we do
  the launch again"). Includes the classroom brain re-hash of the digest (frankie_box_brain.py ~971) and the render without
  FRANKIE_RENDER_BOOKING rewriting the receipt.
- Fleet role: a box keeps its days end to end, ENFORCED (claim_day refuses a non-owner box; the progress record's box is
  never rewritten).
- Relaunch after those land: StartInstances, KeepRunning=true, check the root volume's modification state and raise it
  before any render, direct push of the tip, resume + kick to the teacher (session-9 resume box, steps 1-5).
