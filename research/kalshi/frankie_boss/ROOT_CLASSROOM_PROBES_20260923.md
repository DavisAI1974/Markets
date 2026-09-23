# Root / classroom probes — 2026-09-23

## Highlights

- Root source traversal reports consumed records / verified source count, separately for legacy and native stages. Every record still reaches the same producer unchanged.
- Classroom reports completed tasks / planned tasks and in-flight / failed tasks. A failed task is not counted as completed. Source-reading parts, observation pages, component answers and the summary remain required.
- Percentages are stage-local work counts, not elapsed-time forecasts or whole-run completion. Digest, projection and other stages without a known work denominator report unknown.
- The existing heartbeat now includes the work snapshot and a short highlight. Worker liveness checks Linux boot/process-start identity, not merely whether the heartbeat process exists. Progress age is reported separately; an alive worker is not proof that it is advancing.
- Cache saves, verified reads, rejected reads and completed-publication reuse are exposed without prompts, model responses or credentials. The existing request/prompt/payload and artifact-witness checks remain in force.

## Read-only checks

The session writes progress.json and checkpoints.json at its session root. Monday-read writes progress.json at its fresh output root. Read them with the staged module:

    python3 -B <exact-code-root>/deploy/aws/box/frankie_box_progress.py --directory <exact-session-or-monday-read-root>

The existing frankie_box_heartbeat.py publishes the session snapshot to the existing Git/S3 progress route. Its short note is visible in the existing cycle-status workflow.

## Save points and boundaries

Classroom parsed calls, staged reading parts, raw provider exchanges and final ledgers already have retained, identity-bound cache files. Interrupted classroom work reuses only checkpoints accepted by those existing validators. The new probe does not authorize retries or alter those validators.

Root partial row spools and native ledgers are retained evidence, NOT mid-traversal resume checkpoints. The box native wrapper explicitly omits the producer launcher's PeriodicCheckpointer. No synthetic root resume cursor was added: an exact restart checkpoint would need the producer's complete state, not just a record count. Finished derivations continue through the existing pin/schema checks.

No checkpoint, source evidence, ingestion state or active checkout is removed. Progress snapshots are replaceable telemetry, not scientific evidence. Probe writes introduce no model calls.

## Launch distinction

frankie_box_monday_read.py reads the whole 23-hour Monday, both source members, without a cutoff or row window. It computes the legacy layers and DIGEST_V6; it makes no model calls and declares the absence of a Monday calculation pin.

The separate existing native training/classroom launch uses prepare_trading_day and trading_day_schedule, which currently require authored pre-terminal cutoffs, a row context, a source contract and schedule. These are executable dependencies, not merely null placeholders. Do not insert rejected Sunday numbers, bypass validators or represent the legacy Monday-read job as that full native cycle.

## Review and rollback

Serial review: counters occur after consumption, failures remain failures, unknown denominators remain unknown, payloads are excluded from telemetry, and producer inputs/order are unchanged. Verification uses remote synthetic tests, not a Monday canary or comparison run. Production liveness/progress are unmeasured until an authorized matching runtime starts.

Rollback is a reviewed Git revert followed by a fresh inactive staging checkout. Preserve all output and checkpoint evidence; do not stop a Pod/instance or alter the pinned bootstrap to roll back telemetry.
