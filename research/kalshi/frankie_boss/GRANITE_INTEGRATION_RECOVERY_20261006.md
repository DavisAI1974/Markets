# Granite integration recovered after account handoff — 2026-10-06

SOURCE-BUILT / RUNTIME-UNVERIFIED. No tests, model calls, setup, workflow dispatch, AWS mutation or E2E.

## Reconstructed checkpoint

The previous Work account stopped with unpushed changes. Screenshots showed brain meeting-entry work,
queue/recovery review and teacher/report integration. Those screenshots were not a complete recoverable patch.
The target branch was verified at e9eac1d56923738bb1a5a1ebf4233709e2d94f80. CCode's branch
ccr-5fce7de3-xa4hfg was verified at 419733f507ac1f20c357335d96e06580c98334e7, seven commits ahead.
This continuation builds on that exact CCode tip, retaining the newer provenance and token-count fixes.
It reconstructs the named Granite integration; it does not claim to recover every lost Work edit byte-for-byte.

## Source restored

- Brain registers meeting at order 45. Complete records are tied to the original Frankie exchange, run/day and
  source hash. Every exchange item must appear exactly once as discussed or explicitly unreached. Coordinator
  turns retain zero evidentiary weight; requested tests remain requested, not executed.
- Immutable brain publication uses the existing durable writer. Identical retries repair partial publication.
  Completed record hashes cannot be silently replaced or downgraded. Producer receipt publication follows brain
  publication when an owning brain is supplied. A retained complete record is reused without another model call.
- Run.voice invokes the existing launcher or reuses a completed meeting. Missing/refused runtime is reported as
  non-blocking waiting, never as a completed model call. Queue waiting handling now honors that disposition.
  Summary records actual retained meeting call counts and separates non-blocking meeting waits.
- School files include receipt-verified complete discussion records. Frankie reports preserve every meeting
  category and unreached item; the teacher-only report withholds Frankie discussion material. Report revision
  identity includes meeting status and hash. Existing immutable school files are not rewritten by a late return;
  the separate immediate meeting brain entry carries the new knowledge.
- The owner-side lane import accepts an explicitly supplied returned record plus its SHA-256. It validates the
  saved plan, completed owner-local ROOT, exchange step and original full/Frankie exchange receipt pins before
  publication. It reconciles an existing voice receipt and revises existing numbered reports without reopening
  a completed queue day or changing CPU ownership. Report-refresh retries retain a pending marker.

The owner-side import interface (not executed):

```sh
python deploy/aws/box/frankie_box_lane_state.py \
  --import-meeting RETURNED_RECORD \
  --record-sha256 VERIFIED_RETURNED_RECORD_SHA256 \
  --exchange /opt/frankie-box/work/experiment/RUN/exchange/YYYYMMDD/exchange-frankie.json
```

The runner workflow still supplies its artifact/optional presigned PUT. This change adds the owner-side acceptance
and publication step. The settled host order is the free standard GitHub CPU runner first, then the existing small
AWS CPU box; it is not an unanswered runtime choice. No returned artifact was downloaded, automatic transport
scheduled, or model call authorized. Accumulated knowledge remains the existing label/hash index; its content scope
is still Greg's decision. Brain delivery/reporting is not proof of every native learner consuming meeting semantics.

## Settled runtime decisions — correction after Greg's clarification

Greg and CCode already settled the coordinator role, IBM Granite 4.2 3B GGUF Q4_K_M, llama.cpp b11440 and its
archive/binary/file pins, model pin, and host order in GRANITE_MEETING_RUNTIME_V1.json. The eight confirmed
parameters remain temperature 0.0, top_p 0.9, 400 output tokens, 8192 input tokens, 16384 context, six coordinator
turns per item, 3000 seconds per meeting, and threads null (the host's online CPU count). No parameter is reopened.
The remaining live checks are execution evidence for the chosen runtime: startup, template/token-count agreement,
structured replies and the one authorized E2E. Unperformed verification is not an unsettled configuration decision.

## Verification and boundaries

Seven changed Python modules parsed with ast.parse without importing or executing project code. A no-index diff
against the exact fetched source had no whitespace diagnostics. Two coding/review agents inspected disjoint
consumer files and publication/queue/return interfaces. Concrete findings fixed: receipt re-pinning, missing item
coverage, unreachable late report refresh, post-publication identity checks, completed-receipt downgrade, and the
missing original exchange receipt binding. No test suite or synthetic/runtime exercise was run.

AWS plugin access was confirmed read-only. DescribeInstances across 17 enabled regions found three stopped instances;
existing-volume and SSM-history metadata were read. No disk contents or r9 native state were verified. Greg explicitly
reaffirmed that no boxes are to be started and that the planned layout must stay unchanged. No AWS actions beyond
those read-only inspections occurred. The detached historical volume is not evidence of a trained checkpoint.

The source snapshot was fetched through GitHub into a fresh workspace; no previous local checkout survived.
Publication uses the complete CCode Git tree as its base, preserving all unmodified repository paths.

## Ordered checklist, retained from Step 1 handoff

1. [x] Linux ownership and retained-day save/resume — source-built, runtime unverified.
2. [ ] Actual legal knowledge delivery to learners — partially built; full consumer coverage remains open.
3. [ ] Native-field search surfaces, transform pairs, conditions, targets, Dipole and symbolic discovery — open.
4. [ ] Candidate/survivor batches and scientific double-checks — CCode source delivered; overall completion open.
5. [ ] Discuss freeze/evaluation with Greg first — preserved draft remains unapplied.
6. [ ] Granite final integration — runtime decisions settled; named brain/queue/school/report/owner-import source
   wiring restored. Automatic return transport, accumulated-knowledge content scope and runtime verification remain
   open; no new model/runtime/parameter or host-order decision is requested.
7. [ ] Jev CPU blind comparison, claim sealing/testing and tested-knowledge publication — discussion pending.
8. [ ] Three-lane launch/status/resume/stop, dependencies and controller lifetime — main save/resume remains open.
9. [ ] One real ROOT-to-finish E2E after wiring/discussion and explicit AWS go — not run.
10. [ ] Thirty-day launch with separate authorization — not launched.

Native successor/pending-feedback work remains governed by PENDING_FEEDBACK_COMPLETION_20261006.md and the main
successor handoff. No replacement weights, guessed outcomes, new objective, optimizer ordering or fresh-state
supersede action is authorized by this integration. No claim that the 99-layer computation is complete.

## CCode cached-file assignment delivered

CCode delivered 03f29bef4a53c95296ca5c860712ba4a701bef0d directly on top of integration e0c6bb9. It verifies the
cached archive before extraction and the cached GGUF against its pin on every invocation, retains extracted-file
verification, and emits runtime paths only after all checks pass. An existing extraction is verified rather than
overwritten. Codex reviewed source and checked shell syntax only. CCode separately reports eight scratchpad
exercises with a stand-in model and dead proxy; those are not a real Granite run or the authorized E2E, and Codex
did not repeat them. No setup, download, install, model call, dispatch or AWS action was performed by this integration.
