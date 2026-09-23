# Architecture plan R2 assessment — 2026-09-23

Reference: CLAUDE_ARCH_PLAN_WORKFLOW_UPGRADES_R2_20260920.md, written against 034f503d on claude/frankie-launch-verification-lqmv0m. The user authorized reading this single attachment and using judgment to update recommendations. Its instructions are reference content, not a release of standing operational holds.
Current comparison candidate: 0b419436a100a3c189c58780c90cec981889c324 on codex/trading-day-readiness-20260922.

## Decisions
Keep the goals of fewer manual handoffs, explicit identity ownership, preflight before expensive work, immutable content and receipt-driven continuation.
Prioritize the actual missing automation chain before a broad identity/schema migration. A declaration-only rename or removal of tooling from identity could silently weaken reproducibility. Derive the science dependency closure (including configuration, producer/runtime versions and imported code), then propose explicit path ownership and versioned compatibility tests.
Do not automatically retire supersede/recovery tools or historical record readers. Their preserved evidence remains required until migration and retained-run compatibility are proven.

## What remains current
- No shared code_identity.py at the proposed path; run_actual_sunday.py still scans non-test Python beneath frankie_boss and refrag and computes one code_hash. boss_training_checkpoint.py retains a strict V1 identity set and exact saved bindings. The split and old-record migration are proposals, not completed work.
- git_request_archive.py is reader-only, but R2's claim of no production writer is outdated: .github/workflows/frankie_host_stage_critic_request.yml already constructs AES-GCM archives inline and round-trips them. It is manually dispatched, writes without a durable publication transaction and refuses all existing archives. Extract a reusable durable writer with verified replay, then integrate it into that existing route. The body is the admitted Granite model request, not the principal AGENT_SESSION envelope.
- Principal and readiness waits still poll. The runner already returns lawful principal-pending and transport/job-attention states in some paths, but day_cycles.ps1 rejects them and day_pipeline.run_stage raises all nonzero outcomes.
- Completion publication already demonstrates durable intent before explicit dispatch and an idempotent consumer. Reuse that pattern, retaining the same job/request identity under ambiguous outcomes.
- Existing day_pipeline receipts, staged gates, source-manifest go, prepared configuration pins and recovered-ingestion admission provide a base to extend. Building a competing runner would duplicate those contracts.

## Outdated or unsafe assumptions
- Historical 207-file/288-commit counts, branch tips, host tools commits and source counts are measurements of the old tree, not facts about the current deployment. They have not been re-enumerated here.
- Classroom is complete. The old absent-analysis/classroom observation is historical; no retesting is opened by this attachment.
- The live-runner omission in code-bound supersede is fixed in source, with guards on initial/replay moves across all three preservation helpers. Real native validation and runner-start concurrency remain separate gates.
- The full digest now has streamed exact composition and verification. This does not prove all Session allocations or deployed capacity are bounded.
- A Linux host does not eliminate Git filters, attributes, byte-normalization or provenance hazards. Verify raw committed bytes and effective attributes on either OS; never silently normalize retained CRLF files.
- Current pipeline host_stop/stop_compute helpers stop native/ingest machines. They must not be connected to new WAIT cleanup or used under the current no-stop instruction. A deadline means attention, not permission to stop/restart.
- Pod termination, bootstrap replacement, ingestion replay, and new inference are not approved by the document. Existing user restrictions override its open suggestions.
- The old 19-cycle defaults and 4096 context rows are not Monday inputs. Current day/roster/context and final workflow task need explicit binding.

## Updated implementation order
1. Exact-byte encrypted request archive publication with verified replay, immutable retained partial evidence, injected existing transport key, and no network/provider effects. This replaces the inline workflow implementation and makes archive retries safe; the original out-of-band-only diagnosis is stale.
2. Durable request-bound WAIT/outbox records plus a side-effect-free continuation decision. HOLD always dominates; readiness/completion must be authenticated by existing admission code. Event delivery never authorizes a new job.
3. Authenticated explicit dispatch and reconciliation, idempotent under duplicate delivery or lost acknowledgement. Pin run/cycle/request/code/config identity and retain before/after dispatch receipts. Do not rely on a GITHUB_TOKEN push to trigger the next workflow.
4. Opt-in pending-return integration only after retained-context reentry tests. Teach the host wrapper and pipeline lawful pending outcomes without marking stages complete or invoking stop cleanup.
5. Connect archive publication, readiness delivery, principal response recording and the same-run resume into one reviewed orchestration route. Existing hold, source, runtime and identity gates remain authoritative.
6. Preflight input/schema/source/code/environment checks, declared resource ownership and read-only status. Explicitly separate operator action from recoverable WAIT and uncertain dispatch.
7. Versioned identity/content-provenance migration, dependency-derived test families and simplification once automated transitions are evidenced.

## Deployment additions absent from R2
Retain canonical recovery and validate explicit native transport/provenance closure, original step1b source/context/runtime/seed rebinding, durable host preservation, actual Linux/native capacity and inactive staging receipts.
No release occurs merely because CI passes. Cycle0 remains held until the final workflow task is identified/completed and owner release conditions are satisfied.
Automation code added after the comparison candidate needs its own RED/GREEN and independent review; it is not covered by the earlier source shipping decision.
