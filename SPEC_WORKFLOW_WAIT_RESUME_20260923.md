# Receipt-bound existing-run continuation — 2026-09-23

## Objective and scope
Continue the existing actual-host -> EC2/classroom entry point -> day_cycles.ps1 -> DayPipeline route after a durable WAIT. Retain exact request/job identity and prepared context. Connect archive publication, authenticated delivery and the same-run reentry through the existing workflows. Source implementation and isolated tests are authorized; no runtime activation is authorized.

Base: 237249ddd9c5449ddbbb2780d55215af291fab26 on codex/trading-day-readiness-20260922.
The current owner hold dominates every event. Monday rows/cutoff roster, original step1b and release conditions remain unresolved. No event constitutes release or new execution authority.

## Assumptions
Opt-in pending-return preserves the default polling path. Missing readiness or principal response is WAIT; uncertain job/dispatch outcome is ATTENTION and preserves the same identity. Existing readiness verification and principal host attestation remain admission authorities. A delivery acknowledgment is not scientific completion. No external model/provider/host action is needed to verify source behavior.

## Existing boundaries and implementation order
1. Runner receipt boundary: canonical create-only WAIT/ATTENTION records bind current configuration, run, cycle, request, retained plan/preparation/context, code and any existing job artifacts. Exact same receipt can replay; mutation, omission, substitution or ambiguous receipt state refuses.
2. Host/pipeline boundary: opt-in host returns pending with a verifiable retained receipt. DayPipeline stores pending separately from stage completion, stops the chain and resumes only for an exact pending receipt pin under the existing source go. No packaging/snapshot/stop follows pending. Same-run configuration/schedule/seed pins remain mandatory.
3. Existing delivery boundary: eliminate stale request/path defaults and unsafe duplicate shortcuts; explicit readiness/principal deliveries validate exact receipt/run/config identity and retain publication evidence. Replays compare exact admitted bytes.
4. Workflow boundary: reusable existing archive/delivery/recording actions called from explicit authenticated orchestration, with durable intent, exact source/receipt inputs and idempotent consumer. No push-triggered production work, no retained-granite startup/cleanup chaining and no replacement inference.

## Tasks and verification checkpoints
- [ ] Specify runner receipt/public outcome schema from actual caller fields and write independent failing tests.
- [ ] Persist WAIT/ATTENTION and verify retained-context same-run reentry through the actual entry point.
- [ ] Add host/pipeline pending handling with HOLD dominance and exact prepared-configuration binding.
- [ ] Harden delivery replay and connect reusable archive and explicit delivery/resume caller.
- [ ] Run focused remote RED/GREEN and all automatically triggered relevant regressions.
- [ ] Parallel code, security and test specialist review; resolve blockers and retain source/deployment decisions separately.

Each boundary lands incrementally; source/docs/tests only via GitHub APIs, executable checks only on isolated Linux Actions. Existing tasks/plan.md and tasks/todo.md stay intact under the inherited dated-spec convention.

## Commands and code conventions
Python 3.12/pytest and isolated pwsh match existing archive CI. Focused command:
python -B -m pytest test_workflow_wait.py test_day_pipeline_wait_resume.py -q --rootdir=. --confcutdir=. --noconftest -p no:cacheprovider
Run from tests with explicit repository import setup in the fixtures. Additional host/workflow tests are added to the same secret-free workflow as their contracts are finalized. Existing trading-day CI provides DayPipeline regression coverage.
Canonical metadata follows json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode(); persisted market JSON is handled by remote Python, never JavaScript numeric round trips. No new runtime dependency is planned.

## Acceptance criteria
- Missing delivery returns a durable pending outcome without completing a cycle or advancing the pipeline.
- Replay and lost acknowledgment retain one exact request/job, original code/config/source/seed pins and full context; reentry uses existing admission routines.
- Missing, changed, foreign and contradictory receipts fail closed; crash evidence is retained. Concurrent/duplicate delivery cannot overwrite retained state.
- A source go mismatch or owner hold admits no resume. ATTENTION/deadline never starts a replacement job or stops compute.
- The tests exercise actual callers and workflows, not an unused standalone planner.
- No production deployment/readiness claim is inferred from isolated CI.

## Restrictions and rollback
Retain all restrictions in CODEX_HANDOFF_20260923_WORKFLOW_AUTOMATION.md and its referenced handoffs. No local filesystem/shell/checkout/C:/E: operations; no Amazon Bedrock; Classroom complete, only narrow continuation entry-point plumbing may change. No ingestion restart/replay, canary, runtime/Pod/EC2 stop, pinned bootstrap modification, evidence deletion, key disclosure, or BOSS truncation/output caps.
Every commit includes Co-Authored-By: Codex <noreply@openai.com>. No assistant model IDs.
Cycle0/new run remains HELD. On source regression keep dispatch held and make a reviewed forward fix; preserve all pending, dispatch and recovery evidence. No runtime rollback or automatic restoration is authorized.
