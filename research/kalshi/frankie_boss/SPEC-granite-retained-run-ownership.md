# Retained run ownership and immutable startup configuration

The explicit open Sunday run uses `stacked_v1`, context 131072 and `jobs_v1`.
The request journal stores the original nonsecret runtime configuration: bootstrap
file rows and bundle hash, supervisor command hash, source commit, directory,
codec, context and protocol. Replacement observers load these pins rather than
rebuilding runtime identity from their current checkout. Initial starts additionally
verify their checked-out bootstrap bytes and generated command against the pins.

All signed bootstrap file and bundle URLs must have at least 60 seconds remaining
before start intent is consumed. This permits the actual 900-second issued
capabilities after staging, and is a credential freshness check, not a runtime
deadline. Expired capabilities require refresh before any start action.

One S3 Pod-level conditional record binds a startup digest through `active`,
`stopping` and `closed`. Claim happens before request-scoped start intent and the
single start action. The action's result or sanitized error type is retained.
An ambiguous action is observed; it never authorizes another start.

Only the active→stopping CAS winner can call stop. A successful provider stop
acknowledgement is journaled before readback. A later observer with that exact
acknowledgement may GET-confirm EXITED; it cannot POST again. Without an ack,
stopping stays pending even if an isolated read appears stopped. Confirmed retained
stop is memoized before closing ownership; a crash between memo and close is
recoverable. Old completion or fatal cleanup cannot stop a new owner.

Malformed telemetry increments a counter and is skipped. Observer expiration,
network/storage failures and elapsed model time are not stop reasons. Only actual
completion or confirmed fatal runtime/model evidence invokes run-bound cleanup.

Verification: new targeted checks cover old A/new B, competing claims/observers,
unknown stop, confirmed memo release, acknowledgement-before-readback and later
GET-only release, immutable replacement configuration, actual staging URL shape,
start intent/action failure ordering, malformed frames, and explicit long context.
Existing successful suites were not repeated. These checks do not claim an actual
Pod start, inference, feedback or training completion.
