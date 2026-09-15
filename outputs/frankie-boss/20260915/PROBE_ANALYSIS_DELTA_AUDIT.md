# Probe and printed-analysis delta audit

## Scope and disposition

**No concrete blocker found in the reviewed stable delta.** Baseline is local commit `c29328d784a62b7eeb93542aca1d14d583950502` (the report-only descendant of transport correction `eb510395a8a9e3f8502017de0dd3b0c7aaca04ae`). This review binds the uncommitted final file hashes below rather than asserting a new commit exists.

Reviewed source and diff only, using using-agent-skills and code-review-and-quality. No Python execution, tests, model calls, source database reads, cloud/account calls, or operational actions. No repository edits. The earlier transport audit is unchanged.

## Reviewed SHA256 identities

Paths are relative to the frozen Markets repository used in the earlier audit.

| File | SHA256 |
| --- | --- |
| `research/kalshi/frankie_boss/operations/run_actual_sunday.py` | `761eecae29297184b55cadb1ee5a4310ff19de9901d40e19a4f50e0d9a5a8ce0` |
| `research/kalshi/frankie_boss/frankie_principal_adapter.py` | `5e40026dc8d9b29a8ea65b3bd7df067fcd3516397ea32a529b5269388f9b26d5` |
| `research/kalshi/frankie_boss/operations/ACTUAL_PRINCIPAL_RESPONSE_HANDOFF.md` | `9d4c7d7d086289b788d00df3bdff0e6169133a8b737c3071ff59619c47249024` |
| `research/kalshi/frankie_boss/tests/test_actual_host_probe_wiring.py` | `1d2f7b34fbed8b2ae5bc7d65c695794cfaacab371be9d0398d54840a77cd5887` |
| Existing `research/kalshi/frankie_boss/full_run_progress.py`, read as wiring context | `37f578037be54fa668fa7d8b387e54fc37a8ce689a6b520491407ab9381e5676` |

## Probe control-flow findings

- `main` acquires the host lifetime and recorder locks, constructs and enters HostProbe/RunProbe, and only then constructs ActualHost or calls its run method. Initial diagnostic attachment errors therefore stop before host execution. This implements the requested prerequisite.
- `HostProbe.call` catches ordinary telemetry exceptions and attempts one secret-free HOST_DIAGNOSTICS_UNAVAILABLE notice. `HostProbe.__exit__` also uses this guard and returns false. Later persistence/heartbeat/exit errors cannot replace typed model outcome exceptions or turn successful work into another inference request. The already reviewed primary cleanup fix remains in place.
- Preparation, controller, principal-wait, learning, readback and saved-completion boundaries are connected. The `SundayRuntime.controller_event` field passes through SundayExecution to the real controller, and durable service `event` receives HostProbe.job. Reviewed event names against frankie_controller.py and feedback_cycle.py.
- Coordinator phase mappings and explicit units are accepted by RunProbe. Preparation records switch to completed outputs; subsequent coordinator steps and controller outputs change unit/phase before resetting counts. Principal wait is distinct and marks one received envelope only after reading it; existing host attestation validation still follows.
- Controller fields are allowlisted to phase plus nonnegative integer cursor/count. Job events allowlist phase and lowercase SHA256 values; prompt, body, credentials and exception text are not forwarded. Job event stdout distinguishes same-job states. Durable critic spool observations remain authoritative.
- Job notifications call sample(), not advance(): polling and liveness do not reset the actual progress clock. Existing possible_stall uses time solely to emit an advisory warning. No new timeout, model call, source read, restart, retry, body mutation or dispatch authorization is introduced by this delta.
- Principal waiter retains the existing release/reacquire lock protocol and remains observation-only. Probe additions do not invoke a principal session or fabricate its response.

## Printed-analysis and immutable-evidence findings

- `RUN_ANALYSIS_INSTRUCTION` is added to the current prefix and session request. Manual syntax inspection found the string expression valid: adjacent literals after `+ RUN_ANALYSIS_INSTRUCTION +` concatenate normally. No interpreter compile/import was performed by this audit.
- `_render_retained` still verifies historical prompt hash, retains an exact historical copy, and writes the old prompt bytes unchanged between current instructions and the verified attachment. No historical section or frozen Memory A is rewritten. Existing saved request/response identities remain checked and are not silently upgraded to new instruction text.
- The new request requires Frankie's own Markdown analysis in session output and the same text in a separate lessons entry. It asks for measured results, current run evidence and section hashes, separates observation from interpretation, requires missing evidence and uncertainty to be named, prohibits invented later completion, and explicitly reuses calculations rather than rerunning them.
- The handoff keeps causal cutoff rules explicit: end-of-day delivery does not grant earlier availability. It requires pending/incomplete labeling and reserves final learning claims until evidence exists. Existing feedback and immutable response validation are unchanged.
- Printing and semantic quality remain obligations of the actual authorized session/root workflow. These instructions do not mechanically prove authorship or that text was printed; the existing host-attested response and retained output evidence must establish that during execution.

## Verification limits

The four new portable host wiring test definitions were read but not executed. The implementation agent separately reported one successful run; this audit does not independently certify that result. Review covers source wiring, not active telemetry attachment, actual progress, current source readiness, live vLLM tokenization, final nineteen-cycle results, learning outcomes, or cloud cleanup. Those require the separately authorized run and retained evidence. Old audit findings and their correction evidence are preserved in FINAL_TRANSPORT_AUDIT.md.

External launch copy independently hash-verified: C:/Users/A/Documents/Codex/2026-09-15/continue-from-c-users-a-documents/work/run_actual_sunday.py has SHA256 761eecae29297184b55cadb1ee5a4310ff19de9901d40e19a4f50e0d9a5a8ce0, identical to the reviewed repository host. Report is final for the identities above.
