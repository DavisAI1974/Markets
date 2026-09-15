# Durable Granite client and actual host

Explicit `RunpodConfig.transport_protocol='jobs_v1'` selects this transport and
requires `request_timeout=None`. Default `direct_v1` omits the optional protocol
field from its historical config hash. Runtime startup must witness jobs_v1.

The local spool allocates one slot per controller attempt ID. Before HTTP, it
fsyncs immutable request/admission identity including config, model identity,
request and body SHA. Any changed body/config for the same attempt is refused.
The remote 64-hex job ID deterministically binds that whole intent. Replacement
callers load that identity and start with GET; they never issue direct inference.

Each HTTP exchange is at most 80 seconds. Polling has no total inference budget.
Unknown job (404) permits POST only to the same stable job ID with the same exact
body and `X-Granite-Request-SHA256`. Safe server `not_dispatched` permits the same
idempotent POST. Accepted/running states remain polls; ambiguous backend state
raises `PendingTransport` without dispatch. HTTP loss and transient proxy failure
return to GET for that job. Auth/control/witness errors remain pending inspection.
Validated remote acknowledgement is itself fsynced. A later 404 for a previously
acknowledged job cannot recreate it; it requires inspection of the missing spool
or routing. Every POST also has a fsynced submission intent before its network
boundary. A lost first acceptance response still queries the same stable ID, but
a subsequent 404 cannot cause another POST unless that submission was explicitly
recorded as RequestNotDispatched before request bytes could be sent. The server's
atomic idempotency remains defense against simultaneous callers and lost replies.

Completed controls bind raw result hash, size and original backend status. The
client retrieves those bytes, rejects credential echoes, and fsyncs the result
before delivering it. Result replay requires no credential or network. Remote
recovery requires a fresh in-memory credential and retained local intent. It does
not authorize another Pod start. Server atomic idempotency is essential if two
callers race after a 404 or a client dies with an acceptance response in flight.

The authoritative actual Sunday host selects jobs_v1 in readiness verification
and transport. Its exchange wrapper binds every POST to the independently
admitted exact body, permits empty GET only on the same job, and rejects direct
fallback. Initial credentials enter only through bounded stdin
`FRANKIE_ACTUAL_EXECUTE_V1`. Pending remote recovery uses
`FRANKIE_ACTUAL_RESUME_JOB_V1` with `service_key`, `request_id`, and the existing
`service_pins_sha256`; it retains historical readiness instead of starting again.

The host can recover the first native preparation using an independently pinned
`RETAINED_FIRST_PREPARATION_RECOVERY_V1` witness. It checks the initial training,
model and teacher identities, injects the exact-cutoff tuple only during normal
PreparedContextCache construction, and restores the original method in `finally`.
Normal cache pre/post identity checks still run; the same-cutoff cache remains
available through native learning and closes after checkpoint readback.

The host persists its logical instance identity and reuses immutable readiness
after a restart, including a restart before the first dispatch. Local validation,
TLS/connection setup, and host admission refusal before request transmission are
explicitly known-not-dispatched. Credential rejection raises actionable attention.
Repeated backend not-dispatched responses back off and then require attention;
short result transfers retry only GET on the existing job.

The selected output policy is `remaining_context`: tokenize the exact prompt once,
set output tokens to model context minus input tokens, and bind the final body and
admission receipt. Each later cycle measures its own prompt. Length termination
persists an incomplete-output marker and stops before scoring, feedback, or learning.

After durable outcome persistence, the host publishes a run-bound completion
workflow using request, startup, outcome, job, and frozen code identities. Local
publication intent and acceptance survive restart; publication failure preserves
the outcome and reports cleanup pending without another inference. Length alerts
are persisted before publication and remain visible if cleanup publication fails.
A failed remote job persists its exact secret-free terminal control and publishes
its canonical hash as `terminal_control`, then raises terminal-failure attention;
that evidence is never represented as a model response.

New synthetic verification covers lost acceptance, same-job process resume,
credential-free disk replay, no POST after ambiguous backend state, changed-body
refusal before HTTP, result witness mismatch, pre-dispatch connection failure,
transient proxy/protocol loss, and legacy config hash preservation. Separate host
seams cover admitted jobs-only operations, bounded stdin credential separation,
and restoring the preparation method after constructor refusal. No old passing
tests, smoke/model requests or cloud actions are part of these checks.
