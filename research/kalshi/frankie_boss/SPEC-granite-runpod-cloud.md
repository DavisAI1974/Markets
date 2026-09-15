# Ten-minute hosted Granite smoke

Scope: one fixed non-market request using the existing admission and probe helpers.
User-authorized operating budget is $2, with a 600-second total Pod window.
No market-data access or paper session. No automatic allocation/inference retry.

Use two separate GitHub-hosted runners: controller and watchdog. Both keep a scoped
S3 journal in the already approved Granite bucket. Before allocation, the watchdog
must acknowledge the immutable launch intent. It starts cleanup after 480 seconds,
leaving 120 seconds for provider termination/readback. Controller success/failure
also triggers immediate cleanup. This survives Pod, controller-process, and Codex
failure; canceling the entire GitHub workflow or a GitHub outage remains a shared
failure mode. No hard provider billing guarantee is claimed.
Each Runpod request, S3 journal operation and startup-log read runs in a killable
Linux child with a total wall deadline, including DNS and response-body reads.
After the cleanup threshold the watchdog prioritizes termination over S3 updates.
Empty inventory after a lost create response remains unresolved; success requires
an exact recovered Pod ID returning 404. A completed inference with unresolved
controller cleanup is a failed/incomplete controller result.

Stage the unchanged six-file bootstrap plus manifest in private Amazon S3. Verify
readback before launch. Pass short-lived object-specific download URLs privately,
verify all bytes before import, and remove URLs from the launched process environment.
The new download preamble is pinned through the supervisor-command SHA256 binding.
Use a 100 GB container disk and a 50 GB attached disk mounted at /opt/ml. This is an
explicit change from a persistent network volume: Pod deletion releases both disks.
Retain receipts in AWS before destructive cleanup. The model remains pinned to the
reviewed image, revision, files, tokenizer, request, and 4096 context.

The watchdog may terminate only a Pod matching the durable random launch nonce,
exact image and generated name. Reconcile a lost create response using that same
nonce, never a loose name prefix. Preserve ambiguous outcomes. Refuse repeat workflow
attempts for the controller. Serialize and persist the probe's committed SQLite
journal to S3 before inference POST, then preserve the completed receipt/journal.

Acceptance: (1) watchdog arm/readback precedes one create; (2) real runtime and disk
receipts match local admission before one probe; (3) exact Pod absence is verified.
Verification includes negative identity/permission/late-creation tests and the real
hosted run. Local tests alone cannot mark hosted acceptance complete.
