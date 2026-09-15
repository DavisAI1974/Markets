# Final transport audit — code only

Frozen commit: `553f447d9d04804442399ecf3049a1d0cba37c8c`.
Repository: `C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie`.
Method: read-only `git show COMMIT:path` and `git grep COMMIT`; inspected source, specifications and relevant synthetic test definitions. No tests, model calls, cloud/account calls or source database reads. Used using-agent-skills and code-review-and-quality. No repository edits.

## Ranked finding

### P2 — Cleanup setup failure masks the required typed outcome alert

**Locations at the frozen commit:**
- `research/kalshi/frankie_boss/operations/run_actual_sunday.py`, `ActualHost.publish_completion`, line 581: `directory.mkdir(exist_ok=True)` executes before the `try` beginning at line 583.
- `research/kalshi/frankie_boss/granite_durable_job_client.py`, `DurableJobRunpodService._durable_transport`, lines 247–254 and 278–281: terminal-failure and incomplete-output cleanup handling catches only `JobAttention`.
- `research/kalshi/frankie_boss/granite_shadow.py`, `_serve_request`, lines 189–195: any other exception becomes a generic `transport_error` receipt.

**Concrete trigger and result:** A permission/I/O failure creating `completion-publication`, or an existing regular file at that name, raises `OSError` before the callback converts publication failures into `JobAttention`. For a `finish_reason=length` outcome, raw `outcome.json` and `output-incomplete.json` are already persisted, but the caller loses `IncompleteModelOutput` and its visible capacity-exhausted message. For remote `state=failed`, persisted terminal control likewise remains but `REMOTE_JOB_TERMINAL_FAILURE` is masked. Normal scoring is bypassed, yet the required visible typed alert is not preserved. This is a code-proven conditional failure, not a claim that the launch directory currently has a problem.

**Required correction:** Put all publication setup inside the callback's guarded path and/or make the durable transport preserve its primary typed outcome across every ordinary callback exception. Retain safe cleanup-pending evidence. The existing test only injects `JobAttention`, so it does not establish behavior for this actual unwrapped filesystem seam. A new focused regression should exercise the real callback setup failure; this audit did not run one.

**Verdict:** Request changes for this explicitly required failure behavior before declaring the transport audit clear. No other concrete blocker found in the inspected scope.

## Code findings supporting the remaining transport contract

- `granite_runpod_jobs.py`, `JobStore.submit`, `_db`, `_work`: SQLite FULL/WAL acceptance commits before worker scheduling and before proxy 202. Dispatch intent commits before entering backend execution. Running/ambiguous/completed identities are not resubmitted; exact bytes and hash are compared. Restart marks running ambiguous and accepted not_dispatched. Single-owner lock remains held for workers.
- `granite_runpod_proxy.py`, `_Handler._job_request`: authenticated bounded POST validates the model/body contract and supplied body hash before acceptance; `JobConflict` gives 409. GET result returns persisted raw bytes. jobs_v1 does not route to direct inference.
- `granite_durable_job_client.py`, `_durable_transport`: deterministic job ID binds attempt, request/config hashes and exact body hash. One local slot per attempt rejects changed bindings. Submission intent precedes network; acknowledged or uncertain submissions followed by 404 cannot recreate the job. Accepted/running poll, ambiguous stops for inspection. Proven server not_dispatched only resumes the same ID/body.
- `https_exchange_jobs`: local validation/setup/connect refusal occurs before request() and uses `RequestNotDispatched`; ambiguous errors after that boundary do not create new inference identity. Result transfer checks Content-Length; short reads and short result witnesses retry GET for the same job. Completed outcome replay skips HTTP and permits no credential. Hash/size mismatch remains pending.
- `LocalTokenizerAdmission._measure/with_remaining_output`: one full input tokenization selects `context - len(ids)`, rejects nonpositive remaining output and over-total requests, and binds the final body. Given 92,427 measured input and context 131,072, output is exactly 38,645. Proxy, tokenizer, Runpod service identity and `sunday_native_runtime.prepare_critic_request` use the explicit service context; 1,200 gates apply only to 4,096 context. Actual host forwards prepared admission output into service construction.
- `_final_text` raises typed incomplete output on length termination, using only present nonnegative integer usage fields. Durable client saves exact raw result and partial-output marker before cleanup. `_serve_request` propagates typed incomplete output and PendingTransport without scoring, subject to the finding above.
- Terminal failure persists canonical secret-free control with exact job/request binding and hash. Callback carries `outcome_kind=terminal_control`; actual publication validates that control separately from model-response bytes and binds request, startup, outcome, job and code identities.
- jobs_v1 requires timeout None. Backend loopback connect is finite, backend response socket timeout is removed, and durable client polls without an overall decode elapsed budget. Per-operation HTTP timers and bounded byte/framing checks remain. The finite legacy worker is selected separately.

## Assumptions and unverified evidence

This audit verifies control flow, not deployed behavior. It does not verify the actual prompt's live tokenizer count, vLLM template parity inside the retained process, available GPU/KV capacity, cloud routing/spool filesystem persistence, readiness authenticity, cloud cleanup execution, or exact current source data. The 92,427 count is supplied contract/spec evidence; arithmetic and code propagation are verified. Official-source/runtime evidence is a separate audit dependency and may still be pending. No passing tests were rerun or claimed from this review.


## Final disposition after correction

Reviewed only the frozen delta `553f447d9d04804442399ecf3049a1d0cba37c8c..eb510395a8a9e3f8502017de0dd3b0c7aaca04ae` using git diff. The original baseline review above remains historical evidence.

**P2 resolved at `eb510395a8a9e3f8502017de0dd3b0c7aaca04ae`.** `ActualHost.publish_completion` now creates its publication directory inside its guarded block. In addition, `DurableJobRunpodService._publish_saved_outcome` centrally converts ordinary callback exceptions into `JobAttention(RETAINED_COMPLETION_PUBLICATION_PENDING)` using the retained outcome path and exception type, without exception text. Existing `JobAttention` is preserved. Both model-response and terminal-control publication now use that boundary. Consequently, length termination retains its original `IncompleteModelOutput`, remote failed control retains `REMOTE_JOB_TERMINAL_FAILURE`, and normal completed output reports publication pending until cleanup publication succeeds. None of these branches dispatches inference again.

The delta includes three new parameterized regression cases for callback OSError with length, failed and normal-stop outcomes. I read the test definitions; I did not run tests or independently verify the parent-reported fail-before/pass-after results.

**Final code-review disposition: the reported transport finding is cleared. No remaining concrete code blocker identified within this audit's original scope plus this correction.** This is not a live-launch approval or a claim that separate source, runtime, tokenizer, readiness or cloud-cleanup evidence is complete. No model/cloud/account calls, source database reads, test execution or repository edits occurred during this follow-up; only this small E-drive report was appended.
