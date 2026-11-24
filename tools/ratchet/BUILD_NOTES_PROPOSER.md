Build notes for the proposer (running record; one dated line per piece).

Baseline before any change (retaken 2026-11-24 after the main session fetched commit 048acb0 into the platform checkout, run on the tree before the proposer work): tests/agent_program/test_stage3_ratchet.py gives 20 passed. The first note, 6 passed and 14 errors, was taken before that fetch.

2026-11-24 piece 0 done: the reader takes a line with `corrects` repeating a run number of the same session as that run's next revision; other repeats still refused. Next: piece 1 (tools/ratchet/proposer.py and loop.py changes).
2026-11-24 piece 1 code done: tools/ratchet/proposer.py (MailboxProposer) and loop.py (proposal into the trial's environment, --mailbox, --proposal-timeout-s, --context-budget, --graph-dir). test_stage3_ratchet.py now gives 20 passed (the platform checkout now holds commit 048acb0; before that it was 6 passed, 14 errors from the missing commit). Checks for the proposer come in piece 4. Next: piece 2 (ready.py).
2026-11-24 piece 2 done: tools/ratchet/ready.py (report only; starts nothing). On the old platform_exit.md it reports the path ../markets-data as not ready. Next: piece 3 (control file), then 4 (tests), 5 (manual).
2026-11-24 piece 3 done: platform_exit.md corrected (data path, proposer budget) and notes added; ready check on it reports ready true. Next: piece 4 tests, piece 5 manual.
