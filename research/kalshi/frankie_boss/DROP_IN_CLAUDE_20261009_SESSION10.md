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
4. THE FIX LIST IS TEMPORARY. It is emptied while the run is going, or all at once if the run has to stop. Nothing is
   parked for the end.
5. NO STAGING POINTS. A fix that matters goes onto the box the moment it is committed and pushed. A non-critical fix
   rides the next box change, together with everything else on the list (fixes for steps already passed and not yet
   reached).
6. NO CODED WAIT TIMES. No fixed sleeps, no timed polls, no bounded lock waits on the chain: every hand-off is
   event-driven (the next stage starts the instant the previous one ends; a waiter wakes the instant its condition holds).
7. THE 6-MINUTE STAGE WAS OUR OWN DESIGN (GitHub Actions runner + pack + S3 + SSM + box helper), NOT AWS. The normal
   route is a direct push to the box in seconds; the GitHub stage is a fallback only.
8. CODE VERSION IS RECORDED, NEVER COMPARED. A running day picks up the newest code at its next step; no save/restage/
   resume just to change code. Data identity (sealed sources, pins, counts, data receipts) stays bound.
9. Standing from session 9: one pass everywhere; no gates that re-check receipted data; an owned day is never retried
   from scratch; a box keeps its days end to end.

## Session 10 work (in flight; records below)
- Run-flow role: no coded waits (job 1) + code version recorded not compared (job 2). Record S10_RUNFLOW_20261009.md.
- Code-push role: direct push to the box (git bundle -> S3 presigned URL -> SSM; /opt/frankie-box/code/current symlink).
  Record S10_CODE_PUSH_20261009.md.
- Three read-only auditors: duplicate/triplicate passes under other names (ROOT..teacher; classroom/data/search;
  scientific teacher..end). Findings go to fix roles, then everything lands BEFORE the relaunch (Greg 2026-10-09:
  "Make all of these changes and do a check for more duplicate and triplicate passes ... and get them out before we do
  the launch again"). Includes IMPROVEMENTS_20261008_S9.md "not done" #5 (classroom brain re-hash of the digest) and #6
  (render without FRANKIE_RENDER_BOOKING rewrites the receipt).
- Relaunch after those land: StartInstances, KeepRunning=true, check the root volume's modification state and raise it
  before any render, direct push of the tip, resume + kick to the teacher (session-9 resume box, steps 1-5).
