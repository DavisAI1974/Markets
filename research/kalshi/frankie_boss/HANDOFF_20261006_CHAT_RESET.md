# Frankie AWS workflow — new-chat implementation checkpoint

Greg requested this checkpoint to end a drifting chat. Fetch the latest branch and continue from the commit containing this file. Attachments are unnecessary. This is a partially wired implementation, **not a completed or executed workflow**.

Repository: `DavisAI1974/Markets`  
Branch: `chatgpt/frankie-30day-aws-workflow-20261006`  
Parent of this checkpoint: `1ca7450a8b5171bebbe8ac488cce1f0f3e4d7787`  
Original committed planning files: `53141aa8fbecc735315d5e1da9c2191d6523fb24`

## Read first and stay focused

1. Read this checkpoint, then `HANDOFF_20261006_AWS_WORKFLOW.md` and the canonical opening section of `SPEC-experiment-orchestrator.md` in this directory.
2. Read `.claude/skills/experiment-orchestrator/SKILL.md`, including its instruction that October canonical directives override September provenance. Read full-run-orchestrator sections 0, 3, 5 and 7.
3. Read `Frankie_30Day_AWS_Runbook_20261006.md`, `CODEX_HANDOFF_FRANKIE_30DAY_AWS_20261006.md`, `knowledge/CLASSROOM_RULES_V3.json` and `knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`.
4. Apply the local agent skill `/root/.codex/skills/context-engineering/SKILL.md` when available. It was read and applied in this chat: use a compact constraint list, actual source interfaces and targeted context; do not let stale conversation/spec text replace current directives.
5. Verify branch/tip and working tree. Preserve newer commits. Read files before editing. Do not reconstruct this chat's abandoned methodological proposals.

## Settled decisions — do not reopen or reinterpret

**Later authorization, 2026-10-06:** Greg approved save/restore-only hooks in `c15_teacher_r3.py` ("Add it")
to preserve complete teacher continuation state, including unfinished groups. This is a narrow exception to
the pinned-file restriction below; calculation definitions, inputs and outputs must remain scientifically unchanged.
The companion control stream and the already-active `teacher_changes.py` path carry the same recovery hooks.
Source/code provenance hashes naturally identify the new code. No additional test suite or validators: syntax
checks while wiring, then the one explicitly authorized real E2E and fixes for its actual failures.

**Step #1 remains in progress.** ROOT and teacher continuation hooks are now source-built. ROOT retains the
live adapter (including unfinished groups, caches and dictionary order), its canonical state, binner, previous book,
next INPUT cursor and all output spools. INPUT extraction also saves its rows and journal position. The teacher
retains both raw streams, whole-day totals/cohorts, complete rows, prepared normalizer chunks and each completed
worker result. Requested saves drain submitted work and retain the next calculation position; completed calculations
are reused. Teacher attachment/external-section publication can recover from an interrupted file pair.
These changes have syntax/source checks only, no runtime verification. They do not claim that unsaved process memory
survives an abrupt machine loss. A changed/unsaved spool is retained and refused rather than silently rewound.
Linux ownership/stop integration, classroom phase recovery and search recovery are being integrated separately;
other legal-knowledge/search changes remain working drafts until explicitly published.

**Current ordered ten-step list supersedes numbering below:** (1) Linux ownership and complete-state recovery;
(2) actual legal knowledge delivery; (3) complete existing discovery/search surfaces; (4) candidate/survivor promotion;
(5) freeze and confirmation; (6) discuss then wire Granite; (7) Jev CPU blind comparison; (8) three-lane operating
interface/dependencies; (9) Greg's explicit AWS go and one real ROOT-to-finish E2E; (10) separately authorized 30 days.
Print the checkbox list after #1 is complete in source and identify runtime verification separately.
**Greg requires a discussion before any work on #5 (freeze/confirmation).** Preserve existing local drafts but do not
publish/finalize that step before the discussion. Granite also requires the separately stated discussion before wiring.
Greg authorized parallel coding agents for #1 on 2026-10-06. Claude Code has a separate read-only AWS operating-path
and stale-Pod audit assignment; do not assume its proposed fixes have been applied.

Read-only AWS MCP investigation confirmed the two experiment boxes are stopped and neither has hibernation
configured. Step Functions can preserve successful workflow steps on redrive; ElastiCache stores application-written
cache data. Neither automatically captures a running calculation's internal state. Reuse helpful MCP capabilities
for the existing three-lane AWS CPU workflow; no new service provisioning or compute dispatch is authorized.

- **AWS CPU boxes only. Pods are retired.** No RunPod creation/dispatch, historical A100 ROOT launches or Jev Pod revival. `pod_root` paths are legacy names for reused controller/worker machinery.
- Exactly three lanes: two held 16-CPU lanes on main `r7i.8xlarge`, one on Linux `r7i.4xlarge`. Reuse the CPU ledger, claims, FIFO lines, receipts and common day runner. Fifteen workers plus coordinator. A day keeps its same box/lane/work/cache from ROOT to completion or explicit stop/save. Giant journal/ROOT artifacts remain with the owner.
- Preserve Frankie inputs, calculations, planes, adapters, replay and Memory A. Do not edit pinned `frankie_box_projection.py`, `context_session.py`, `c15_journal.py` or `c15_teacher_r3.py`.
- New nonlinear/multivariable mathematical discovery is central. Keep the existing equation-discovery engine and fitting mathematics. Do not replace discovery with a fixed catalogue or counts-only promotion engine.
- Greg's averaging concern means collapsing outputs from, for example, 100 runs into an average. It **does not authorize altering internal equation-fitting objectives or mathematics**. The abandoned suggestion to adapt average-based objectives was removed. `odcore/symbolic.py` is unchanged.
- A single occurrence has equal validity, certainty, survivor, teaching and knowledge treatment after the mathematics/science/source/timing work is double-checked and holds. No minimum occurrences/days, rarity uncertainty, confidence discount or hypothesis-only restriction because rare. Actual contradictions/incomplete checks are judged on their merits. No relevant occurrence on another day supplies no new test and does not downgrade a checked discovery.
- Every day has its own causal 13-point external file. Values are date-specific, but consecutive days can legitimately share released values or be close. Never force differences, invent values or reuse a wrong-day file. All retained records/fields must reach applicable computation; a field-consumption count alone does not establish completed contextual search.
- New legal knowledge must reach Frankie immediately after **each** producing stage, before his next dependent step. Other lanes refresh at the next legal boundary with consumed-version receipts. Preserve host-answer walls and causal timing. Jev stays blind until his own claims are sealed; tested knowledge may then reach Frankie immediately.
- Discovery October 2021–2023; freeze once before untouched October 2024–2025 confirmation. No same-day circular survivor teaching. Keep separate day classes and individual findings.
- **Settle Granite with Greg after core wiring and before final workflow wiring/E2E.** Candidate remains 3B Q4_K_M, local/free standard GitHub CPU if adequate, then small AWS CPU. Granite is a bounded active post-class facilitator; no critic, self-assessment, scientific seat, grading, calculations or survivor judgment. Do not introduce Pod/GPU execution under the historical fallback wording.
- No fourth lane, new discovery engine, validator/canary framework, test farm or broad A/B.
- Read-only AWS/GitHub investigation is permitted. **No instance start, stage dispatch, E2E or 30-day compute launch without Greg's explicit AWS go.** “Proceed” and “commit/push” are implementation/publication instructions, not compute authorization.

## What this checkpoint adds

### Linux ROOT-to-finish foundation

`research/kalshi/frankie_boss/pod_root/pod_agent.py` routes `workflow=root-to-finish` jobs to the common `Run` and queue day runner after setup/input verification. It books a held day slot, uses existing stage receipts, calls teacher/classroom/search/lessons/end stages in the existing order, publishes small state and completion receipts, and retains the journal/ROOT locally. Renew/resume modes use the same retained job. Failed days retain ownership; cleanup/shipping is refused for this workflow. The legacy `ship()` branch is explicitly refused rather than calling the runner accidentally.

`pod_root/controller.py` submits Linux full-day jobs, services request/reply coordination through presigned S3 slots and main-box SSM, renews mailbox URLs, and retains ambiguous submissions/failed days instead of allowing reassignment. Pod create/dispatch arguments are rejected. The loop permits exactly `--boxes i-0d17573dbce871520@us-east-1 --slots 1`; two main lanes remain the existing main queue's responsibility. This is **not yet the final three-lane launch entry point**.

`deploy/aws/box/frankie_box_pod_root.py` adds main-side `coordinate`; its shell adds coordinate/renew/resume and fixes a pre-existing shell parameter-message quoting error. The legacy loop marker now describes the AWS CPU route. Names are retained for compatibility, not a Pod architecture.

### Small-state transport and stage receipts

New `deploy/aws/box/frankie_box_lane_state.py` implements hash-checked small knowledge snapshots, owner namespaces, large-source pointers, durable request/reply mailboxes, legal-visibility selection, consumed-version witnesses, central class FIFO coordination and small completion receipts. It rejects changed/missing included sources, path traversal/symlink destinations, host-only knowledge, and cross-owner coordination. Main queue workers do not take over a remote day/class. Remote class completion wakes the main class worker.

`frankie_box_experiment.py` publishes remote stage boundaries and records pulled versions. ROOT brain sources include the new external consumption receipt where present. **Imported knowledge is currently transported/stored but `visible_knowledge()` is not yet connected to the classroom/brain corpus. Version receipts do not prove Frankie consumed actual findings.** Search brain entries currently carry the search manifest, not the full discoveries. These are explicit remaining wiring gaps, not finished immediate-learning behavior.

### External-file and search input preparation

`operations/frankie_day_external.py` validates trading-day/session bounds, unique columns, row widths and native publication stamps. `computation_receipt()` reads every external table row/field through the as-of guard with exact source/row hashes and descriptive counts; adjacent-day equality is legal. ROOT writes `external-computation.json`; the data inventory exports it. The existing thirteen search aliases retain native integer timestamps/values rather than float conversion.

`frankie_box_experiment_search.py` and `_transforms.py` preserve integer/nanosecond precision, nested/list/byte leaves, mixed numeric/text channels, all existing cross-transform combinations and all text cell columns; alignment gates are per numeric field. Nested field collisions refuse instead of silently overwriting. The empty unclassified-step mask has a boolean dtype.

New `frankie_box_experiment_surface.py` prepares a full native journal-ordinal reader, ordinal bindings, all external table fields and state masks. **It is not called by the search yet.** The active search remains the legacy first slice: F_LAST axis, grouped INPUT aggregates, unfinished conditions/targets and limited claim integration. Do not claim all-field search completion from this preparation.

### No-Pod Jev guard and policy correction

`Run.jev()` now reports `waiting` with preserved blind classroom material until CPU transport is wired; it no longer supplies a Jev Pod dispatch or treats unsent material as completed. The rest of Jev's sealed-claim/test flow still needs wiring. Earlier commit `1ca7450a` amended R06 and related classroom/final-review wording for equal checked single-occurrence treatment. This checkpoint adds the corrected averaging/discovery interpretation and no-Pod rule to the canonical spec/runbook.

## Continue in this order

1. Review and finish the remote runner/small-state foundation without expanding architecture. In particular: actual legal knowledge consumption by learner stages; immutable source/version provenance; actual search findings rather than manifest counts; existing ROOT reuse/attempt identity; interrupted submission/resume and retained affinity; same-owner failure recovery; same-day/confirmation answer walls; previous-class small carry state; teacher knowledge on reused rows. Do not equate SSM success or uploaded versions with completed learning.
2. Connect the full applicable existing search surface: native per-event/full-field input, all cross-transform pairs, cells/conditions, targets including fills/exhaustion, Dipole on search-only days, scoped historical/Frankie/Jev claims, and preserved symbolic equation discovery. Current cell code compresses selected indices before lag counting; preserve the original causal axis when conditioning. Freeze the tested lag/scope instead of selecting a new best lag on confirmation. Use exact day-specific source bindings and list not-measurable cases rather than silently skipping.
3. Wire candidates/survivor batches, double-checks and one-time freeze, then confirmation against frozen specifications with existing applicable maker/taker costs. No producer/freeze path is finished in this checkpoint. No rarity gates. Do not invent fee assumptions or acceptance redesigns. Existing symbolic module's historical prose is not current R06 policy.
4. Bring Greg a focused Granite implementation discussion **before final launch wiring or real E2E**. Then wire the bounded small CPU facilitator using the role/rules. Current voice transport remains a stub.
5. Finish Jev's authorized CPU route, blind claim sealing/testing and immediate tested-knowledge publication; no fourth experimental lane and no Pod.
6. Finish the actual three-lane launch entry point, discovery→freeze→confirmation dependency order, and concrete launch/status/resume/stop commands in the runbook. The current low-level renew/resume actions are not a finished operating interface. Audit stale Pod-oriented GitHub workflow labels/branches before any dispatch; no Pod command is authorized.
7. Only after wiring/Granite and Greg's explicit AWS go: one real ROOT-to-finish E2E, fix actual failures, and launch the 30 days only when authorized.

## Verification and execution status

This checkpoint is limited to source/syntax verification (Python 3.12 compile, shell syntax, diff/branch/source checks). No experiment, scientific comparison, Granite model run, E2E, GitHub compute dispatch or AWS compute was executed. No instance was started. No validator/test framework was created. Runtime behavior remains unproven until the authorized real E2E.

Prior read-only AWS inspection found these instances **stopped**; verify again before operations:

| Purpose | Instance | Region | Type |
| --- | --- | --- | --- |
| Main two lanes | `i-035994afa8bdf66a5` | `us-east-1` | `r7i.8xlarge` |
| Linux one lane | `i-0d17573dbce871520` | `us-east-1` | `r7i.4xlarge` |
| Existing small CPU candidate | `i-08cee7171c0a76a04` | `us-east-2` | `r6i.2xlarge` |

Keep main protected root volume `vol-0d36715924f03b86c` intact. The existing instance role/profile `Ssm` has AmazonSSMManagedInstanceCore, without S3/SendCommand grants. The chosen transport uses a credentialed controller plus presigned mailbox slots; no IAM change was made. Keep signed URLs private.

Use the connected GitHub/Aws MCP. For AWS `run_script`, import `aws_mcp`, inspect `help(aws_mcp)` and discover helpers with `await aws_mcp.search_functions(...)`. Search docs topic `agent_skills` before `retrieve_skill`; use exact returned skill names. Direct `call_boto3` operations take PascalCase operation names; inspect reported API calls. Do not mistake tool availability for compute authorization.

Pushes require `[skip ci]`. Stage the final exact commit only when authorized; a later push requires restaging. Do not run billed CI or rebuild retained ingest/ROOT to check wiring. New chat needs no attachment and must report source-built versus runtime-verified status separately.
