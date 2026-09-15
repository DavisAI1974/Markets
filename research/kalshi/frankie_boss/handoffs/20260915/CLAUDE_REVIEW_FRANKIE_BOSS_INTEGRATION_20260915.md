# Claude review: Frankie-BOSS integration (feedback cycle, principal adapter, retained lifecycle, runtime)

Date: 2026-09-15. Read-only review; no edits, tests, cloud calls, principal invocation or broker actions.
Worktree: `Markets-full-frankie`, HEAD `ce1b5cd2`, all seven targets untracked.

Reviewed bytes (sha256 first 16 / lines): feedback_cycle.py 4b3bb6aa62fa5f7e/272; tests/test_feedback_cycle.py 8bc550d8476e118c/168;
frankie_principal_adapter.py 0c01155e81ce3204/382; tests/test_frankie_principal_adapter.py 8ae036b0d0b31484/175;
granite_retained_lifecycle.py 082686f2c4b15d5d/99; tests/test_granite_retained_lifecycle.py 0faeac13f321f8e9/83;
sunday_native_runtime.py 643da5d0b9d0bb91/148. The adapter, its test and the runtime changed mid-review; line numbers are against these hashes.

## HIGH

H1. Coordinator intent precedes the adapter's durable request; the gap is a permanent wedge for a call never made.
feedback_cycle.py:237-239 saves `principal_intent` then calls `principal.execute`; the adapter writes `session-request.json` only at
frankie_principal_adapter.py:327 after `_request()` re-validation (:295-305). A crash or transient validation failure between :237 and :327
leaves, on resume, intent present -> `recover` only (:230-235) -> None (no request file, :343-344) -> AmbiguousPrincipalCall forever,
although nothing was dispatched (executor runs only after :327). The same path mislabels the normal outbox-pending state as ambiguous.
Fix: `recover` distinguishes "no request file" (distinct signal) from "request without response" (PrincipalPending); coordinator calls
`execute` in the first case and re-raises PrincipalPending in the second; reserve AmbiguousPrincipalCall for an executor failure after the write.

H2. Next-controller identity is a static pre-training snapshot.
sunday_native_runtime.py:67-69 captures native_hash/optimizer_hash at initialize(); assemble_request (:99-100) checks only `config` and stamps
`arm_hash=evidence_hash(development_identity)` (:105). After apply_completed the weights change but the dict does not: the next request carries
the pre-training arm/native hash into the controller intent, export manifest `source.arm_hash` and receiver binding.
Fix: in assemble_request raise if `development_identity['native_hash'] != context._model_hash()` (and re-check optimizer_hash);
preferably bind arm_hash to `checkpoint.checkpoint_hash`.

## MEDIUM

M1. Pre-Sunday Memory A admission (`retained_knowledge`, :104-124) is enforced only on the retained-prompt branch (:242-243).
The emitter branch (:211-212) accepts any knowledge-receipt; the emitter validates bundle<->receipt but not pre-Sunday identity.
Fix: call retained_knowledge in prepare() before the branch split; require the two sha keys in __init__ (:148-149).

M2. validate_resume never verifies retained model bytes: granite_cloud_resume.py:236 checks the Pod env var GRANITE_MANIFEST_SHA256
(set at create time, survives a stop) and :45-46 the /opt/ml mount; /opt/ml/model is recorded (:215) but never listed/hashed.
resume_once then POSTs start (granite_retained_lifecycle.py:92-95) with no post-resume verification hook. Bounded by the lease.
Fix: resume_once returns requires_startup_verification=True; orchestrator re-runs the accepted 13-file/health verification before any critic request.

M3. Partial receiver output directory wedges prepare(): adapter guards on the receipt file only (:198-201); the receiver refuses an existing
--output-directory (prepare_boss_attachment.py:50-51) and writes three files after mkdir (:104-108). A crash mid-write is unrecoverable.
Fix: if `receiver/` exists without a receipt, rename to `receiver.partial-<uuid>` (retain) before rerunning, as _export_verified does (feedback_cycle.py:69-72).

M4. Host attestation is filesystem trust on both model-facing seams: record_session_response (:334-339) accepts any dict and the receipt (:356-361)
re-hashes the response's self-reported session identity; resume_once accepts a hand-built admission dict (granite_retained_lifecycle.py:79-85)
because LocalTokenizerAdmission drops evidence_class from its return (granite_runpod_tokenizer.py:103-104).
Fix: record_session_response(response, *, host_attestation) binding the host's own session record/witness; include evidence_class in the admission
dict and require ACTUAL_TOKENIZER in resume_once. Until then requirements 4/9 hold only up to host write access.

M5. Feedback persisted before roster validation: feedback_cycle.py:251 saves feedback, then apply_completed sets mutated=True before update()
(boss_training_checkpoint.py:296-297); learner._validate failures inside update() poison the checkpoint with zero gradient taken.
Fix: before _save('feedback'), assert feedback session ids == learning_kwargs['sessions'] ids in order.

M6. Watchdog liveness proven only at start (arm <= 20 s, :86-91); a runner that dies after start leaves no provider-side stop until lease expiry.
Fix: record runner identity (run id + job timeout >= deadline+30) in retained-armed.json and require it in resume_once.

## LOW

L1. feedback_cycle.py:223 silently overrides a caller-supplied export_kwargs['request_id']; reject if different.
L2. Emitter-branch config consistency: render['result']/['delivery-receipt'] never checked against preparation['result_path']/['delivery_receipt']
(emitter re-verifies against render, emit_frankie_spawn.py:741-748, fail-closed but late); --result/--delivery-receipt are receiver-required
and never injected; knowledge-*-sha256 keys without retained-prompt become unknown emitter flags. Validate render per branch in __init__.
L3. checkpoint.identities is a mutable dict embedded by reference (boss_training_checkpoint.py:128, 210); wrap in MappingProxyType.

## Test-evidence gaps

prepare() is never executed by any test; _check_preparation/_code/_receiver_input_block are stubbed; retained-lifecycle tests stub validate_resume;
6/7 coordinator tests stub _export_verified and all stub the principal. Receiver flag surface verified STATICALLY: prepare_boss_attachment accepts
exactly the seven flags the adapter emits (:113-117); receipt keys/self-hash (:90-103) match _check_preparation; attachment-request.json matches load_request.
Receiver preconditions: canonical 13-key pins JSON with mode='attributed_input' (:55-57); no hardlinks/symlinks; clean receiver tree incl. untracked
under research/; handoff dir contains exactly the manifest members; KNOWLEDGE_BUNDLE.md must be pre-placed beside the pinned receipt
(emitter never creates it when --knowledge-receipt is given, emit_frankie_spawn.py:770-785).

## Confirmed sound

1 completed replay precedes any factory (:205-206 < :212). 2 real exporter: manifest carries every key _export_verified reads, manifest.json last,
existing destination refused, state.c15.json.result == controller result. 3/6 intent-before-execute on the adapter; interrupted starts never
resubmit; weights change only inside apply_completed after a durable controller result. 5 lazy learner; fresh and replay receipts share one
constructor (boss_training_checkpoint.py:250-259). 7 Memory A hashed at init/binding/learning/lessons; lessons separate, cutoff-gated; JSON lists
round-trip as lists (c15_journal.py:56-57, 73-75). 8 stop_owned_once issues only {'action':'stop'}, verifies name+image digest+nonce three times,
never treats absence as success. 9 prepare_critic_request builds the full compact prompt with no forward (context_session.py:151-198) and no
truncation; LocalTokenizerAdmission tokenizes exact bytes, truncation=False, fails closed.

## Runtime facts unchanged

Full mapping, actual BOSS source journal, request admission, principal feedback and training not complete; Pod stopped with /opt/ml retained.
Nothing was started, called, tested or edited by this review.
