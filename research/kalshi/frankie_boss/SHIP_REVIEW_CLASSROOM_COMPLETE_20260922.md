# Classroom implementation review — 2026-09-22 continuation

Reviewed source/test revision: 834d5b2345fe98b03d1c8a914c85ae0b2f400a0a on codex/trading-day-readiness-20260922.

## Decision

Classroom repair and the owner's classroom research/conversation additions are implemented and pass remote software checks. Production launch remains held: Root/Granite implementation and deployment requirements, followed by the owner's final workflow task, remain. No new runtime model call, production deployment, ingestion restart or cycle 0 was performed.

## Resulting behavior

- Completed and partial classroom caches bind request, teaching, prompt, relevant code, route and model identity. Mismatched evidence is preserved with durable intent and completion receipts.
- Publication resumes from verified retained answers; a ledger alone is not completion. The final receipt binds the output artifacts.
- The original TEACH -> GUIDED -> SOCRATIC -> VERIFY progression and regression remain, with mode-appropriate evidence and hidden teacher-key boundaries.
- The classroom host shares validated cumulative-learning and Granite priming initialization with the base host. Priming lineage remains bound to prepared requests, training configuration and checkpoint admission.
- Every completed earlier cycle's ordinary observations, unsuccessful ideas, corrections, disagreement and uncertainty remains available to later cycles. Research access is not gated to novelty or the replay's earlier market cutoff; explicit knowledge-primed replay labeling preserves that distinction.
- Both scientific teaching roles receive the complete shared Dipole research corpus. The classroom teacher reviews Frankie's whole run and each finding; the added BOSS scientific role responds, the classroom teacher replies, and Frankie answers both. Each actual retained call binds the request, role, item and prior turn.
- The original BOSS governed representation teaching, mathematical targets, masks, controls and training responsibilities remain unchanged. The conversation adds research and proposed experiments; it does not silently modify governed targets.
- Dipole-derived trading-signal discovery is an important research objective alongside the others. Scoped scientific or mathematical validation need not await a second occurrence. Scientific agreement remains distinct from predictive and economic proof.
- All current source material is staged in full with exact retrieval. Only repeated source bodies in history delivery prompts become lossless references. All learned content and model outputs remain verbatim, and the original attested artifacts remain available.
- Evidence checks must cite an actually delivered source.

## Verification

At source implementation 0041540888c9326449de87cd319cbb93246ecede, classroom workflow [35813377809](https://github.com/DavisAI1974/Markets/actions/runs/35813377809) passed:
- Host job 107029592160: 330 tests and 22 subtests; compileall passed.
- Box job 107029592288: 71 tests and 17 subtests.
- All 127 immutable shared sources verified, totaling 3,519,892 bytes; snapshot 7e0da7ebf7945ced5796621fc4b0bbc921f0914d91b3288120366058cfd27549.

The full host test completes two cycles through the real coordinator, attestation, classroom completion and cumulative-history loader with a synthetic model boundary. Both complete scientific conversations reconstruct exactly from their learning views; reopening completed state dispatches no new model work. This caught and drove repairs for mapping-order-sensitive evidence hashes.

The Root immutable-checkout tests use isolated temporary Git repositories. They prove the exact dispatched commit wins over a moving branch, with pre-checkout intent and resulting receipt, and refusal for dirty source, active Frankie services and invalid/missing/unavailable commits.

A broader test still asserted the old branch-based checkout error text. Revision 834d5b2345fe98b03d1c8a914c85ae0b2f400a0a updates it to verify that the shared immutable checkout guard precedes derivation. All three workflows then passed:
- [Classroom 35813600725](https://github.com/DavisAI1974/Markets/actions/runs/35813600725)
- [Codec 35813600836](https://github.com/DavisAI1974/Markets/actions/runs/35813600836)
- [Readiness 35813600796](https://github.com/DavisAI1974/Markets/actions/runs/35813600796)

Suites overlap; counts must not be added as unique coverage. Tests and retained provider witnesses do not prove production scientific correctness, model comprehension, market prediction or profitability.

## Review limits and remaining work

Earlier independent specialist findings were incorporated. The reviewers subsequently exhausted their account allowance; the final additions received direct review, not a new independent three-agent clearance. No dependency/CVE audit or native Windows execution is claimed.

See CODEX_HANDOFF_20260922_CHAT15.md for the remaining Root/Granite tasks: bounded-memory digest implementation, actual Monday roster/configuration, host preservation intents, coherent source/request/seed/anchor pins, actual brain/reading/priming receipts and derive-only measurement. The S3 helper route remains intended. The final workflow task must be completed before the new run.

All original operating restrictions remain: remote-only access; no local filesystem/shell; no ingestion restart or source replay; no canary; no native runner/Pod/EC2 stop; pinned Pod bootstrap unchanged; exact market integer preservation; no evidence deletion, key exposure or BOSS output truncation.
