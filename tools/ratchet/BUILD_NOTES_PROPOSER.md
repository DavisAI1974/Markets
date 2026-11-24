Build notes for the proposer (running record; one dated line per piece).

Baseline before any change: tests/agent_program/test_stage3_ratchet.py gives 6 passed, 14 errors (the base commit 048acb0 is not in the local platform checkout, so the clone fixture fails).

2026-11-24 piece 0 done: the reader takes a line with `corrects` repeating a run number of the same session as that run's next revision; other repeats still refused. Next: piece 1 (tools/ratchet/proposer.py and loop.py changes).
