# Monday checklist (live; items are crossed off only from actual receipts)

Detail of each step: `CLAUDE_HANDOFF_20260927_DIGEST_SAVEPOINTS.md`, "Order after ROOT (corrected)".
Downstream dispatches go from ONE fixed ref cut at the staged commit (so edits here never move it).

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
- [ ] Publication slice, Option 3 (receipt-level evidence; unverified hash checks listed)
- [ ] Stage ONE commit; fixed dispatch ref cut at it; CODE_ROOT recorded
- [ ] Principal inputs (frankie_box_principal_inputs.sh)
- [ ] Cycle 0 config (ACTION=config; existing prepared root r6-48; binds the five-lesson Granite priming)
- [ ] Granite Pod up (fhiwwlouzyx6l2)
- [ ] Launch (ACTION=launch; priming delivered in the first request; WAIT recorded)
- [ ] Principal: reading
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
