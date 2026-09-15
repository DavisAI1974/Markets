# Frozen host and handoff code audit

Candidate: `553f447d9d04804442399ecf3049a1d0cba37c8c`.

## Conclusion

No blocking code finding identified in the requested host/principal handoff and completion-cleanup scope. This is a read-only code audit, not final source approval or permission to skip the actual operator gates. All inspected code came from the named commit through Git object reads. No tests, model calls, cloud actions, source database reads, or account actions were performed.

## Principal wait and exact recovery

`operations/run_actual_sunday.py` holds `actual-host-session.lock` for the host lifetime and a separate releasable `actual-host.lock`. Its observation-only session executor first finds the unique retained request, releases only the recorder lock, and waits for the response file. The recorder holds that lock through validation and immutable publication. The waiter reacquires it before reading and checking the response. A second actual host cannot enter while the original session lock remains held. The callback performs no session dispatch or inference.

`frankie_principal_adapter.execute` recognizes the response already written by the recorder, requires it to equal the callback return, validates attestation, and recovers it rather than performing a second exclusive-create write. Coordinator principal intent is durable before this boundary. Existing unresolved intent after a genuine process interruption still raises pending instead of invoking the callback again. The documented operator procedure is to record that same request before restarting. This prevents automatic duplicate principal execution, although a process interruption necessarily loses its in-memory cache.

The normal live wait does not unwind `SundayExecution.run_cycle`. Its runtime release occurs in the eventual `finally`; the host phase hook closes the cache at `checkpoint_readback`, after native learning and checkpoint application. `NativeForecastLearner.step` requests the original `as_of` and `through_cursor`, checks the prepared input and source hashes, and consumes the cached preparation. The advanced learning cutoff controls feedback availability, not the preparation cutoff. The actual training forward remains necessary learning work; there is no repeated native context preparation during the live handoff.

## Feedback before immutable publication

`operations/record_actual_frankie_response.py` requires independently hashed configuration, response, and host attestation, plus existing bound mapping, plan, export, and session request. Adapter recovery and verification run in a separate retained candidate directory before the final response is written. The helper also invokes the learner's pure `_validate` checks without constructing a learner/model or reading the source database. These checks cover chronological teacher forcing, ordered session roster, observation and availability times, future path coordinates, opening-gap restrictions, evidence digests, and STOP only after session close. A changed final response is refused; an exact response is recoverable.

These checks do not independently establish market truth or enforce every authored query-policy choice. Root must inspect the supplied causal evidence and contract when authoring the response. An evidence hash is a binding, not proof that its market interpretation is correct.

Censored final-tail feedback can honestly omit unobserved timing/path labels and use a null gap where required. It must not manufacture a STOP label. The learner explicitly supports no available supervised terms, recording `updated=false` and `loss=null`; completion of a cycle therefore does not require inventing a label or claiming an optimizer update occurred.

## Authentic session provenance

The adapter requires exact request and response hashes, actual session identity, model identity as reported by the session, all eighteen preserved section hashes, and an independently witnessed host record containing the same identities and a nonempty host authority. Root can produce this honestly by performing the actual authorized Frankie analysis, retaining the actual output and host observation, and binding those bytes. Neither the helper nor a model self-claim substitutes for this observation. Historical authorship and frozen Memory A remain separately checked.

## Completion writer and stop recovery

The completion workflow checks out `inputs.code_commit`, and its standalone Python entry point verifies actual checkout HEAD against that input. Later operational marker commits on the dispatch branch therefore do not change the executed frozen code. The standalone module imports only standard-library code until constructing its scoped boto3 journal; it does not require the native/model dependency stack. Push registration cannot run its publication job because that job requires `workflow_dispatch`.

The publisher matches the exact retained startup request, startup canonical hash, and retained Pod before writing immutable completion evidence and the startup-bound finished marker. The host supplies persisted raw outcome evidence, or explicitly distinguished terminal-control evidence. Workflow dispatch acceptance alone is not confirmation of successful publication or stopped hardware; root must observe the subsequent publication and cleanup receipts.

`granite_active_run.completion_cleanup` reserves stopping through conditional ownership before the provider stop. Acknowledgement persistence retries only the acknowledgement read/write, never the stop action. A later acknowledged stopping state performs GET-only confirmation. An unacknowledged ambiguous stop remains pending and retains ownership. A crash after storing confirmed cleanup but before ownership release can finish release from that exact receipt. No path examined authorizes an old startup to stop a newly owned run.

## Actual operator steps still required

1. Complete and independently pin final source, schedule, lineage, and prefix evidence; this audit did not inspect their bytes.
2. Keep the frozen code/config identities exact and use the committed host/helper under `research/kalshi/frankie_boss/operations`. The handoff document still mentions the older scratch helper location; use the committed helper for this candidate.
3. For each newly admitted cycle, provide the exact run/readiness witness and fresh credential through the existing private stdin boundary. Same-job recovery must retain the job and never start replacement inference.
4. Observe completion publication and run-bound cleanup before authorizing the next retained service run. An ambiguous unacknowledged stop requires reconciliation, not another stop or ownership override.
5. At the principal wait, read the exact current prompt, attachment, frozen knowledge and contract; author actual feedback and separate lessons; retain authentic host provenance; run the validating recorder with exact file hashes. The live host then continues without re-preparing the cached context.
6. Treat incomplete output and terminal-failure attention as stopping conditions. Do not score fragments, fabricate labels, or resume by creating a new inference.

No edits to the candidate were made. This report is the only audit artifact written, on E:.
