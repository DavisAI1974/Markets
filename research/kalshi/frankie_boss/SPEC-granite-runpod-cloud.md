# Launch Granite before the Sun run

The user requested service launch without another standalone smoke. The maximum
total Pod window is 20 minutes, including shutdown, within the existing $2 cap.
Start only Granite; the Sun run remains a subsequent user-directed operation.

Carry forward run 34924522636: both runners passed 70 focused Linux tests, private
AWS bootstrap staging/readback passed, and controller/watchdog independently
verified exact Pod absence. Reuse those tests and the existing staged objects.
Only changed launch behavior receives targeted tests. The first Pod and attached
disk were deleted, so a new allocation and possibly cold downloads are necessary.

One create attempt, fresh immutable nonce/intent and journal, and separate hosted
controller/watchdog runners. The watchdog acknowledges the intent before create.
It begins termination at 18 minutes, leaving two minutes for exact-ID readback.
Pod, controller and Codex failure do not disable it; whole-workflow cancellation
and GitHub outage remain shared failure modes. No hard provider billing cap is
claimed. Requests, DNS and response-body reads are isolated in killable children.

Use one secure L40S at no more than $1.25/hour, the reviewed pinned image, model
revision, tokenizer versions, 4096 context, 100 GB container disk and 50 GB attached
disk at /opt/ml. Read back the existing seven private S3 objects and compare them
to the pinned bundle before issuing short-lived GET URLs. The unchanged bootstrap
checks hashes before import and removes URLs from the process environment.

The controller checks real startup model/tokenizer/runtime/disk evidence and an
authenticated GET /health. It sends no inference POST. Startup has at most 15
minutes. Once ready, save a secret-free service receipt to S3 and the controller
artifact, then leave the service running until the watchdog's cleanup threshold.
Failures trigger immediate exact-Pod cleanup. A missing create response is
reconciled only by the watchdog so discovered identity cannot be lost.

The endpoint's generated credential stays in the Pod's private environment. A
later authorized Sun controller can retrieve it using the owned Pod's control
plane identity; do not publish it in logs or artifacts. Existing token admission
evidence covers the frozen smoke request only; it does not admit future Sun
prompts. Health readiness does not establish model-output quality or paper-trading
readiness. No market data, venue traffic or orders are part of this launch.

Acceptance: verified startup/runtime and authenticated health, with a retained
service-ready receipt carrying Pod ID, endpoint, model and exact expiry. Cleanup
remains scheduled independently after the controller exits successfully. Attached
disks are disposed with the Pod; prior S3 bootstrap and receipts remain retained.
