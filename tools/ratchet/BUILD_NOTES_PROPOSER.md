Build notes for the proposer (running record; one dated line per piece).

Baseline before any change: tests/agent_program/test_stage3_ratchet.py gives 6 passed, 14 errors (the base commit 048acb0 is not in the local platform checkout, so the clone fixture fails).

2026-11-24 piece 0 done: the reader takes a line with `corrects` repeating a run number of the same session as that run's next revision; other repeats still refused. Next: piece 1 (tools/ratchet/proposer.py and loop.py changes).
2026-11-24 piece 1 code done: tools/ratchet/proposer.py (MailboxProposer) and loop.py (proposal into the trial's environment, --mailbox, --proposal-timeout-s, --context-budget, --graph-dir). test_stage3_ratchet.py now gives 20 passed (the platform checkout now holds commit 048acb0; before that it was 6 passed, 14 errors from the missing commit). Checks for the proposer come in piece 4. Next: piece 2 (ready.py).
2026-11-24 piece 2 done: tools/ratchet/ready.py (report only; starts nothing). On the old platform_exit.md it reports the path ../markets-data as not ready. Next: piece 3 (control file), then 4 (tests), 5 (manual).
