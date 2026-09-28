# Monday checklist (live; items are crossed off only from actual receipts)

Detail of each step: `CLAUDE_HANDOFF_20260927_DIGEST_SAVEPOINTS.md`, "Order after ROOT (corrected)".
Downstream dispatches go from ONE fixed ref cut at the staged commit (so edits here never move it).
Standing rule (Greg, 2026-09-27): before each step is dispatched, a quick READ-ONLY scan of its code for heavy CPU
work left on a single core; findings noted on the step's line before it runs.

## ROOT (run 36351808435, b35e79b7)
- [x] Preparation + prepared layers (reused 0-7, prepared 8-45)
- [x] Legacy tables
- [x] Member merge (14 shards) + copy-in: sources.sqlite finished
- [x] ROOT paused 01:05Z in its bedrock tables (bedrock.members on one core, ~10 h); superseded by the side builder
- [ ] Digest document + derive.json (after the restart: assembly only)
- [ ] calculations-receipt.json read, sha256 recorded (2,032,203 records, 0 failures)

## Save points
- [x] Save code built and on f1hr0c (0d1251f0); used by any restart and by the staged downstream runtime
- [x] Parallel bedrock table writer (same bytes as write_table), side builder, adopt-digest (0a2a5669)
- [x] Fixes: plain and published layer metadata (cf199fbe, d74d8982); bedrock layer ORDER taken from sources.sqlite's
      layer_index, since derive.json keys are sorted but ROOT numbered layers in memory order (8992b709)
- [x] Stop script for a side builder (4557b5de, staged run 36364575737)
- [x] ROOT paused 01:05Z (Greg's go): pause-for-terminal-digest-62338.json, checkpoint 2,032,203 records verified,
      ROOT and its 14 helpers exited; orphan check 01:09Z: none
- [x] First side builder (18 threads) stopped 01:06Z, nothing left alive
- [ ] Side builder on CPUs 2-15 + siblings (28 threads), run 36364840364 from 4557b5de, started 01:09Z
- [ ] Adopt ROOT's sources.sqlite + legacy tables 0-4 (run 36364858997)
- [ ] Restart ROOT on the staged commit, same inputs: reuses everything, assembles the document, writes
      calculations-receipt.json

## Downstream Monday
- [x] Publication slice, Option 3: DROPPED (Greg, 2026-09-27: no validations, straight to staging)
- [ ] Downstream runs from the newest staged commit (4557b5de now); earlier: staged dcef2467 (run 36360108539, 23:55Z; supersedes 39f64acf and 685155b6: principal inputs hashing
      in parallel and staggered). Dispatch ref: claude/frankie-monday-run-dcef2467. CODE_ROOT:
      /opt/frankie-box/code/dcef2467df14fea3d3df2c9a37c4f36317defdd8-36360108539-1/markets
      (pack sha256 c288c5ce..., 3,693 files, active checkout unchanged)
- [ ] Principal inputs (frankie_box_principal_inputs.sh). Scan: one heavy single-core step, the streamed sha256
      re-check of ROOT's evidence files (digest, derivation, result, pins, proof), about 1 GB/s; the digest dominates.
      One file's hash cannot be split; accepted. Everything else is small JSON and knowledge-snapshot assembly.
- [ ] Cycle 0 config (ACTION=config; existing prepared root r6-48; binds the five-lesson Granite priming).
      Scan: no heavy work (JSON reads, torch/numpy import for version readback, one git rev-parse, one file write).
- [ ] Granite Pod up (fhiwwlouzyx6l2)
- [ ] Launch (ACTION=launch; priming delivered in the first request; WAIT recorded)
- [ ] Principal: reading
      CPU probe while the principal runs (read-only, own lock): frankie_box_session_cpu.sh MODE=threads (per-thread
      CPU, pins, classroom helper labels, latest files) or MODE=profile (20 s py-spy, heaviest functions per thread).
- [ ] Principal: CLASSROOM (Dipole classroom)
- [ ] Principal: TEACH (exhaustion teach-back)
- [ ] Principal: writing
- [ ] Record initial (ACTION=record TURN=initial; classroom pre-grade)
- [ ] Resume 1 (ACTION=launch RESUME=1 WAIT_SHA256): grading + classroom correction request
- [ ] Correction (ACTION=correction; same BOSS session)
- [ ] Record correction (ACTION=record TURN=correction)
- [ ] Resume 2 (ACTION=launch RESUME=1): final grading, classroom receipt, cycle complete
- [ ] Retain (ACTION=retain)

Tuesday stays pending.
