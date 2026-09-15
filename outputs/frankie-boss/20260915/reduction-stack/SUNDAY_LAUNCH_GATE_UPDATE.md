# Sunday launch gate update

Actual inference and the nineteen-cycle Frankie run have not started.

## Completed evidence

- Actual combined GitHub journal run 34962256086 succeeded at code 549efa7376438320ede848483d7e5dd1035177ed.
- Complete exact journal: 569,667,584 bytes versus original 11,700,711,424 bytes (20.54x physical storage reduction).
- One semantic conformance pass completed in 715.1934 seconds, with one parent CPU and three dedicated workers.
- Original source completion, checkpoint, scope, prefix and journal commitments agree with the remote result. The independent remote receipt remains gate_authority=false.
- Complete result archive and all probes are retained in eight authenticated encrypted Git parts in runs/34962256086.
- Older independent verification 34958705448 was cancelled at the user's request.
- Original causal schedule completed all 57,027 records and all nineteen retained cutoffs.

## Diagnosed handoff failure and repair

The existing local handoff pinned the completed quartet and failed before creating any new prefix database. Its error was "completed logical schedule identity differs".

sunday_schedule.build_schedule hashes C15 packing in its declared field insertion order. The one-shot writer then serializes JSON with sort_keys=True. C15 map packing preserves map order, so rehashing the file's sorted maps produces a different digest despite equal values.

verified_sunday_schedule restores only the exact V1 schema order (including step, feedback, terminal and first-trade fields), rejects unknown fields, and checks the original published digest. The original file and all numerical values/cutoffs remain unchanged. The shared verifier is now called by the committed prefix helper and actual host on this branch; the frozen original checkout remains unchanged.

Focused actual-schedule regression run 34964666064 passed, preserving f6922f7a4b93b44394c6683e3d7c45782f27e250c81987bd54414fb124c60e42 and rejecting changed cutoffs and added fields. No source or schedule execution was repeated.

## Outstanding launch work

User selected GitHub execution unless a strong Sunday-specific reason prevents it. No new local task files are authorized. Existing local failure/evidence is retained.

The previous host relies on local absolute paths, closed source ancestors, nineteen prefix snapshots and a live cache/ownership lock while awaiting actual Frankie responses. GitHub-hosted jobs have a hard six-hour execution limit (https://docs.github.com/en/actions/reference/limits). A GitHub execution handoff must preserve durable request identity, exact prepared state, response provenance and recovery without duplicate inference across jobs. The existing host is not yet ported or launched on GitHub.

The remaining eighteen prefix witnesses, final independent data audit/seal, transport/admission integration and actual nineteen cycles remain required. Do not call journal completion or a green schedule regression the completed Sunday run.

The V2 reducer is a separate candidate; its additional token gains have not been verified or applied to the paid request.
