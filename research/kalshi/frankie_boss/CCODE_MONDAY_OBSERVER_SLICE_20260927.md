# CCode Monday Observer Slice — 2026-09-27

This is the next small slice for the already-running Monday ROOT resume. Read the current handoff and `CLAUDE.md` first. Newer evidence in the live run supersedes this note.

## Live state

- Resume workflow: `36339291716`
- Runtime commit: `2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a`
- Calculation root: `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- ROOT PID reported after admission: `60813`
- Admission passed; the process reused the finalized scientific state. Scientific records must remain at `2,032,203`; do not rebuild or replay them.
- The five-file retirement is already complete. Do not dispatch retirement again.

## Do exactly this slice

1. Confirm workflow `36339291716` is still the only active Monday calculation run. Do not dispatch another calculation, staging run, canary, comparison, validator, or orchestration job.
2. Dispatch or use exactly one read-only projection observer over the existing calculation root. Use the committed observer route already approved for this runtime; do not invent a new script or attach tracing.
3. Capture the observer's actual output/receipt, including:
   - ROOT PID and process token, and proof they remain the admitted process;
   - checkpoint identity and the full terminal checkpoint SHA256;
   - projection plan hash;
   - completed member and lifecycle compressed-range counts;
   - ordered byte frontiers and source identities;
   - compressed archive bytes and existing receipt hashes;
   - available filesystem bytes and the remaining projection reserve.
4. Accept the observer only if the PID/token are unchanged, the plan hash is the retained plan, every reported range is receipt-backed and ordered with no gap/overlap, and source identities match the sealed ledgers. If any check fails, preserve the output and stop.
5. If the observer is clean, leave PID `60813` running and wait for this same ROOT resume to reach its natural terminal state. Take one read-only terminal read when it changes state and record the final calculation receipt/digest status.

## Hard stop

Stop after the clean observer receipt and, if it finishes during this slice, the single terminal status read. Do not begin projection publication recovery, digest publication, downstream staging, principal/classroom work, delivery, grading, cleanup, or retention. Do not create a new root, duplicate staging, change the runtime, rebuild records, replay ingestion, broaden deletion, or add tests/canaries.

Report the real workflow/SSM/observer IDs, timestamps, hashes, byte counts, PID/token evidence, and any blocker. If the observer is still running, report that fact and stop; do not poll in a loop or dispatch a second observer.