# Monday checklist (live; items are crossed off only from actual receipts)

Detail of each step: `CLAUDE_HANDOFF_20260927_DIGEST_SAVEPOINTS.md`, "Order after ROOT (corrected)".
Downstream dispatches go from ONE fixed ref cut at the staged commit (so edits here never move it).
Standing rule (Greg, 2026-09-27): before each step is dispatched, a quick READ-ONLY scan of its code for heavy CPU
work left on a single core; findings noted on the step's line before it runs.

## ROOT (run 36351808435, b35e79b7)
- [x] Preparation + prepared layers (reused 0-7, prepared 8-45)
- [x] Legacy tables
- [ ] Member merge (14 shards; 23:19Z most at layer 37 of 46, merge-09 at 31)
- [ ] Bedrock tables (bedrock.members measured, one core)
- [ ] Digest document + derive.json
- [ ] calculations-receipt.json read, sha256 recorded (2,032,203 records, 0 failures)

## Save points
- [x] Save code built and on f1hr0c (0d1251f0); used by any restart and by the staged downstream runtime
- [ ] (only if ROOT must restart) adopt the finished merge shards: frankie_box_adopt_merge.sh

## Downstream Monday
- [x] Publication slice, Option 3: DROPPED (Greg, 2026-09-27: no validations, straight to staging)
- [x] Staged 39f64acf (run 36359220114, 23:38Z, beside ROOT on its own lock). Dispatch ref:
      claude/frankie-monday-run-39f64acf. CODE_ROOT:
      /opt/frankie-box/code/39f64acff739543dd59557db7f0918c55a530cdc-36359220114-1/markets
      (pack sha256 6ac06b03..., 3,693 files, active checkout unchanged)
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
