# Durable outcome completion publication

The actual host publishes completion only after the raw backend outcome has
been durably saved, including a length-truncated outcome. Publication is also
recoverable from the existing outcome without another inference. The dedicated
GitHub workflow receives only exact request, startup, job, outcome and code
hashes. Its code commit must match the host's reviewed commit. It writes the
outcome witness before `retained-finished.json`, both immutable and bound to the
same request's persisted startup. It never calls a Pod or model API.

The existing independent watchdog consumes that marker and uses the Pod-level
active-run conditional record. A late completion for A cannot stop B. The
completion workflow has its own concurrency group so it cannot wait behind the
long-running observer it is notifying. A code-only push registers the workflow
with its cloud job skipped; publication requires the actual host's later
explicit dispatch. Workflow registration must be verified before launch.

Stop acknowledgement persistence retries the journal operation once, accepting
an identical record if a previous write succeeded but its readback failed.
There is no second stop POST. Persistent acknowledgement-storage failure or
process death before any acknowledgement survives still leaves the stop
ambiguous and ownership held. A bare EXITED snapshot cannot rule out a delayed
stop, so it cannot release ownership for another paid run. This residual
uncertainty requires provider-side evidence; it is not silently retried.

New focused checks cover a transient acknowledgement write and a lost readback,
exact completion/startup binding, witness-before-marker ordering, idempotent
publication, and changed-outcome refusal. Existing passing checks are not rerun.
