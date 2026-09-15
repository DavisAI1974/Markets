# Launch Granite before the Sun run

The user requested service launch without another standalone smoke. The maximum
total Pod window is 30 minutes, including shutdown, within the existing $2 operating cap.
Start only Granite; the Sun run remains a subsequent user-directed operation.

Carry forward run 34924522636: both runners passed 70 focused Linux tests, private
AWS bootstrap staging/readback passed, and controller/watchdog independently
verified exact Pod absence. Reuse those tests and the existing staged objects.
Only changed launch behavior receives targeted tests. The first Pod and attached
disk were deleted, so a new allocation and possibly cold downloads are necessary.

One create attempt, fresh immutable nonce/intent and journal, and separate hosted
controller/watchdog runners. The watchdog acknowledges the intent before create.
It begins stopping compute at 28 minutes, leaving two minutes for exact-ID readback.
Pod, controller and Codex failure do not disable it; whole-workflow cancellation
and GitHub outage remain shared failure modes. No hard provider billing cap is
claimed. Requests, DNS and response-body reads are isolated in killable children.

Use one secure L40S at no more than $1.25/hour, the reviewed pinned image, model
revision, tokenizer versions, 4096 context, 100 GB container disk and 50 GB attached
disk at /opt/ml. Read back content-addressed private S3 bootstrap objects, writing
only missing objects, and compare them to the pinned bundle before issuing GET URLs. The bootstrap
checks hashes before import and removes URLs from the process environment.

The controller checks real startup model/tokenizer/runtime/disk evidence and an
authenticated GET /health. It sends no inference POST. Startup can use 27 minutes,
then reserves one minute for publication before cleanup begins. Once ready, save a secret-free service receipt to S3 and the controller
artifact, then leave the service running until the watchdog's cleanup threshold.
Failures trigger immediate exact-Pod stop with disk retention. A missing create response is
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
disks are retained with the stopped Pod; S3 bootstrap and receipts remain retained.

## Diagnostics and resumable files

GRANITE_PROGRESS reports every five seconds with the phase, elapsed phase time,
manifest bytes present, transfer rate and verified-file count. Percentage means
bytes on disk, not startup completion or verified bytes. Stalls emit a warning
after 30 seconds without advancement and repost every 30 seconds; advancement
reports recovery. Errors include only fixed categories and numeric HTTP/OS codes.
The controller validates the owner/manifest and bounds every telemetry record.

The controller saves pod-info.json locally and to the private S3 journal throughout
startup, including safe Pod configuration, model hashes, timing and diagnostics.
Stop requires fresh exact EXITED readback. Absence cannot count as retained success.
The model directory retains completed files and ETag-bound partial downloads.
Resume validation binds the prior capture to the same stopped Pod, owner, disk
configuration and model manifest. Before reuse, verify completed-file hashes and
resume partial files only with the required HTTP Range and immutable ETag checks.
GPU memory and host failure are not covered. No automatic second allocation occurs.

Stopped attached storage continues billing (50 GB at the documented $0.20/GB/month
is about $0.33/day); the 30-minute limit bounds the compute attempt, not indefinite
storage retention. The prior two Pods were deleted and have no resumable model files.
Source: https://docs.runpod.io/pods/storage/types and the live REST v2 OpenAPI contract.

New validation only: progress producer 16 passed/1 Windows symlink skip; consumer
21 passed; retention helper 22 passed; interrupted-download integration 3 passed;
cloud retention integration 8 passed; affected launch/roster/command checks 10 passed.
These are local software checks, not hosted Granite readiness or inference evidence.
