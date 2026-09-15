# Active continuation

## Latest build state: exact reducers and open-ended runtime

Runtime candidate `96b86abc` removes elapsed startup/run/decode deadlines in explicit open-ended mode and retains durable dispatch/outcome evidence. Process-loss with no retained provider outcome remains ambiguous; it never authorizes a duplicate POST. These changes are committed but have not been deployed to the retained Pod.

Candidate `76f9d179` configures the pinned model's 131,072-token context with 2,048-token chunked prefill, preserving one request and its attention state. Legacy finite 4,096-token behavior retains its prior config hash. The shared service and new context-route integration are still being completed; do not claim the Pod's old 4,096 setting has changed. Retained runtime evidence reports one NVIDIA L40S with 47,665,709,056 bytes of GPU memory. A BF16 KV-cache calculation leaves approximately 3.83 GB after the conservative model-file size and full context cache within the 90% allocation. Actual startup cache capacity remains unverified.

The first exact request measured 929,730 input tokens. Existing Frankie JSON minifiers produced no additional savings because its JSON was already minified. A cumulative offline lossless prototype now measures 91,914 input plus 1,200 output tokens, or 93,114 total. It combines typed columns/deltas, exact wire reconstruction, exact adapter-field derivation, reversible hash encoding, and reconstruction of every per-record packet hash from the complete contiguous normalized source prefix. All 3,262 rows, wire bytes, metadata and packet hashes reconstruct exactly. Production codec/route wiring is in progress. Later windows require a trusted preceding prefix seed and all intervening records; missing inputs require a literal fallback, never guessed hashes. No model comprehension or inference result is claimed by the codec measurements.

Prepared-context cache fixes support the verified reader's private connection, exact tensor bits and device identity. The host restores original preparation before learning and cycle changes. Source ancestry is recorded in a separately pinned closed-lineage sidecar, preserving failed-fork history and historical rehydration boundaries.

The prior source-recovery worker failed after 26,000 completed records when progress persistence failed. Its journal and evidence remain unchanged. The active continuation is now `E:/Codex/Frankie-BOSS-20260915/source-recovery-resume-20260915`, PID 59604 at this checkpoint. It verifies/reconstructs the retained 26,000 records before continuing the full 57,027-record day. Inspect progress before acting; never open its active journal through an independent reader. The one-shot schedule waiter is PID 59792, output `full-causal-schedule-resumed-20260915`; the closed-lineage waiter is PID 59432, output `closed-source-lineage-20260915`. Both await final successful ingestion. PIDs are observational historical identifiers, not authorization to terminate anything.

The separate bootstrap staging workflow exports committed LF bytes, pins the exact eight-file bundle, conditionally uploads and verifies its bytes, and encrypts temporary download capabilities to the local recipient. It never operates a Pod. The local package from `76f9d1797d69e6938c0cc5a53f437b892d59ae1d` has bundle SHA256 `f4f42e28520fd88996d9a608d18926f6d4129a2b6ab72878a5a655351133acb3`; it has not been staged or applied. Repackage if any roster member changes after review.

Remaining before actual execution: complete and pin source/schedule/lineage; integrate the versioned exact codec for every scheduled window; admit the final actual request; finish Claude's independent runtime review; stage and apply the reviewed bootstrap/environment to the same retained stopped Pod; start once and verify actual readiness; execute the real feedback/learning cycles with progress probes. No actual Granite inference, BOSS forward, new principal feedback or training update has occurred.

The older chronological notes below are retained as history; this section supersedes their paths and completion status.

## Current user override: progress governs run duration

The user explicitly removed fixed startup AND execution runtime budgets. Keep the
same retained Pod and run going while probes demonstrate meaningful progress.
Do not stop or restart a progressing run because an elapsed-time budget expires.
Health responsiveness alone is not proof of work progress. A stall or failure
requires diagnosis of the retained run, not an automatic start or inference retry.
Explicit user stop and confirmed fatal-failure handling remain available. A hosting
observer's platform time limit must preserve resumable run state; it is not a Pod
runtime deadline. The earlier 30-minute startup/execution lease assumptions below
are superseded. Lifecycle and host implementation are being updated accordingly.

The accompanying handoff and code-state files preserve the preceding task's exact
checkpoint. They are historical evidence, not a claim that the unfinished cycle ran.

The user subsequently directed that the supplied single dataset is its own source.
There is no source-day requirement, four-date prerequisite, or warmup prerequisite.
`selected_source_scope` binds its complete 973,355 bytes and 57,027 records to the
known SHA256. Existing Sunday principal evidence remains reusable.

Full physical mapping has now completed locally for all 57,027 records. GitHub run
34933373944 preserved the complete source/delivery artifact, but its mapping step
failed before reading records because NumPy was absent. The workflow dependency
is corrected; staging was not repeated. Local mapping and source ingestion use the
same pinned Windows extraction runtime. Mapping index SHA256 is
`f62c522dcc00a4d3e1caeac7a8e1e4e534a437ef53be200e991508236c027ca6`.

All full plaintext ledgers and five original delivery objects were rehashed in
`E:/Codex/Frankie-BOSS-20260915/delivery-plain`. The new local delivery receipt has
self-hash `8df1ff9a5f006a4e48246d31335d525859a2bb372d35dca53e1afa914243b542`.
Original receipt and compressed objects are preserved separately.

A concurrent capacity snapshot blocked SQLite ingestion after 3,512 completed
records and one pending INPUT. The reader now closes paged reads before decoding.
Explicit recovery preserves the original journal, verifies exact retained
INPUT/APPLIED bytes, and continues in a separate WAL journal. Recovery is still
running in `E:/Codex/Frankie-BOSS-20260915/source-recovery-20260915`; inspect its
progress and final receipts before treating source ingestion as complete.

An actual authorized Frankie principal session authored the own-source contract at
`E:/Codex/Frankie-BOSS-20260915/principal-source-contract/source-contract.json`, SHA256
`359e369cbc43b48ef33280dc64a44200e53d1d3612ed1e10fe26988e7e2baefd`.
Its development price numeraire is explicit; it does not fabricate a prior exchange
close or a true contract multiplier. Runtime prefix bindings are applied separately.
The first actual source cutoff is being measured for Granite capacity. No BOSS
critic call, new feedback, or training update has occurred yet.

New checks only: single-source scope 4 passed; ingestion progress 1 passed. The
workflow YAML and embedded Python compile. Previous passing suites were not rerun.
Feedback coordinator, principal adapter and retained-Pod runtime are being implemented
in parallel under the user's explicit instruction. Granite stays stopped until the
actual request has been admitted and a bounded retained-stop lifecycle is installed.

Claude's supplied review is preserved alongside this file. The separate coordinator
fix assignment uses published base `ae0102d8c28ed0589c86bb6f733e13b3914dea01`;
Claude owns coordinator H1/M5/L1 and checkpoint L3 in his own worktree. Codex workers
own adapter, runtime identity, tokenizer, startup and watchdog findings. Do not edit
the same files concurrently or claim the review findings resolved before integration.
