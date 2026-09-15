# Open-ended Granite dispatch

## Explicit operational mode

`RunpodConfig(request_timeout=None)` selects `GRANITE_RUNPOD_OPEN_ENDED_V1`. Finite values retain the previous `GRANITE_RUNPOD_SERVICE_V1` configuration hash convention and behavior. JSON records use `null`, never infinity. `build_runpod_service` requires `spool_directory` for the new mode. It returns `OpenEndedRunpodService`, whose declared recovery capability and durable storage identity are retained in the controller configuration.

Connection establishment remains bounded to 80 seconds. After connecting, the operational client has no total decode/response timer. Request and response byte bounds, exact local token admission, startup/model/identity verification, authentication, output parsing and source guards remain in force. The retained Pod proxy and bootstrap must separately enable their matching operational mode; client changes cannot remove a provider or proxy deadline.

## Durable ordering

For each exact attempt ID, a deterministic local directory contains the request body, a fsynced dispatch record, and eventually a fsynced outcome. The dispatch binds attempt ID, shadow request hash, model identity, configuration, full body SHA and byte count, plus exact token admission. It is saved before thread creation and before the only POST. A changed body or identity for the same attempt is rejected.

The worker is independent of the caller's async task. It saves the raw HTTP result before notification. Caller cancellation can later reattach to the same worker; a completed result can be replayed by a new service instance directly from disk. No replay sends another POST. The parser still judges the saved response normally.

`recovery_only=True` permits construction without a credential. It can only recover an existing same-attempt outcome or live worker; a missing dispatch raises `PendingTransport`. It cannot create a dispatch or contact the provider. The actual host selects this mode when it finds retained dispatched work.

A process loss after dispatch but before outcome, a socket failure, or an upstream load-balancer disconnect is ambiguous. It raises `PendingTransport` without saving a terminal controller verdict and without sending another POST. This local spool has no provider result-by-ID API and cannot recover a response the local worker never received. Such an attempt needs explicit investigation. There is no automatic timeout-triggered restart or second inference.

## Controller seam

Only services advertising durable same-attempt recovery can use an open-ended timeout. When their controller intent already exists, recovery retains the original attempt ID and requires the complete original critic context to match. It writes no duplicate intent. Explicit replacement attempt IDs are rejected for this mode. Finite legacy recovery behavior remains unchanged.

## Validation

Five new focused synthetic tests cover finite hash preservation, cancellation followed by a late response and disk replay, process-loss ambiguity propagation, credential-free recovery refusing new dispatch, and controller readback requiring a durable binding for null timeout. Tests ran in three targeted invocations (3 passed, then each new case passed separately). No actual model or provider request was made. External proxy/bootstrap changes and the full actual source's capacity remain separate launch requirements.
