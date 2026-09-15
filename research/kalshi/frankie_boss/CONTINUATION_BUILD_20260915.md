# Frankie build continuation — September 15, 2026, round 2


Read this round-2 handoff before older continuation reports. Run using-agent-skills
first when resuming. Unless a repository path is explicitly named, `work/` and
`outputs/` below are rooted at:
`C:/Users/A/Documents/Codex/2026-09-14/continue-the-frankie-build-in-parallel`.

## Current direction

Continue the build in parallel. Sunday remains held until readiness is established. The initial current handoff was read before older reports, and using-agent-skills ran first. This report follows FRANKIE_BUILD_HANDOFF_20260914_CONTINUATION.md and preserves its source, teacher, receiver and historical verification records.

The build is still incomplete. No actual Frankie session, training, held-out reveal, new market-data acquisition, venue order or new hosted GPU attempt ran. Round 2 did run a separately reviewed read-only AWS diagnostic collector.

## Final reviewed code and verification

The reviewed software tip is `398d1db347d308eac87e9df2d9f2c6561b24c372` in
`work/Markets-integration`, branch `codex/frankie-continuation-20260914`.
This identifies the tested code; documentation closeout may have a later commit.
Integration ownership remains with the root task. No new commit or push is claimed
by this handoff publication.

Root selected every `test_execution*.py` file in the BOSS test directory on that
code tip: **401 passed in 74.49 seconds**, with no failures or skips. Exact console
output is retained at `work/round2-execution-tests.log`. Root inspected the full
implementation diff and found only the intended changes.

The final three composed cancellation tests connect the real cancellation
controller, existing ledger and authenticated DELETE preparation with generated
keys and fake HTTP. A separate read-only SQLite connection proves the exact
CANCEL_ATTEMPT wire was committed before the HTTP callback. The tests verify RSA
signing, retained reservations, changed-ID refusal after restart and zero request
transmission after a slow connect consumes the controller-derived target-age
lease. Independent review passed all three in 7.51 seconds. All software changes
were reviewed; these are local/synthetic acceptance results, not venue operation.

## Reconciled workbook closeout

The new derivative is
`outputs/combined-build-round2/Frankie_BOSS_Combined_Build_Round2_20260915.xlsx`.
Its SHA256 is
`9a22b8fb79c4920ca8a1d56b19a8adaba67b1d7b5e0ba0ea2d0a98f7bc1f9cac`.
The original workbook and prior derivative remain preserved.

Only 12 cells in Current Snapshot and Source Crosswalk changed. Reimport verified
all 12 values. Byte comparison preserved 39 unrelated archive parts, all eight
original worksheets, 11 tables and one chart. The workbook still includes its
additional status/crosswalk sheets; eight is the preserved original-sheet count.
Formula-error search matched zero entries. Six changed views were rendered and
inspected by root. The derivative's `preservation-audit.json` and `verification.txt`
retain the structural/byte witnesses and validation summary beside the workbook.
The workbook points to this handoff and the historical Granite recovery report.

## Completed software

### Primary Kalshi account observations

Worker 68b0722368e9f10949243d8cc1f7c1a879a9e36d integrated as 466e8bc9. Adds a separate immutable GET-only capability and collector for explicit primary-account balance and the full declared resting-order cursor chain. It reuses existing secret resolution, RSA signing and HTTPS exchange. Each attempted HTTP request retains frozen nonsecret request/response evidence before proceeding. Cancellation retains the attempt before propagating. Wrong identities, malformed or repeated cursors, incomplete pages, time/byte limits, unsafe echoes and storage failures cannot produce a complete result.

Complete describes the requested cursor chain. It does not establish an atomic account snapshot, positions, fills, valuation, P&L, ownership or reflection. No account query was sent. Final worker execution suite: 319 passed in 32.05s. Independent reviewer: 35 focused passes. Root combined observation/provider/transport selection: 104 passed in 9.72s.

### Execution supervision

Worker d32b8b5f226e18c780fd873fb557b1a1109050cc integrated as 812b3968. Adds a host-invoked check of independently pinned session heartbeat and signed clock-offset evidence. Missing, stale, future or drifting samples and unavailable verification/storage latch the existing durable local kill before receipt persistence. Healthy telemetry cannot clear the latch or authorize dispatch. The monitor does not acquire ledger checkpoints during in-flight I/O.

The host supplies a trusted clock, cadence and nonsecret witnesses. This snapshot check does not establish a persistent clock rollback or sample replay frontier, provider connectivity, deployment monitoring or account truth. Final author focused tests: 21 passed. Independent reviewer: 20 passed before the final negative-duration case. Root supervision/controller/ledger selection: 87 passed in 25.66s.

### Historical Granite recovery

Worker b9de4d6c45cac8f4609fa8b5a8697b20bdb4959f integrated as 2bcb966872fd0c9ba8a0b186ec6cb8c8f5609f9c. New workflow collects only scoped read-only evidence, with no resource mutation. Root independently ran 29 recovery/inventory tests in 0.20s and reviewed the executable workflow before push.

Actual diagnostic run 34914225798 completed successfully on that exact source. The receipt itself is incomplete: cloudtrail:LookupEvents was denied, the expected log group was absent, and historical endpoint/config/model were all explicitly absent. Current owned endpoint inventory was complete and empty. The selected instance quota was 2.0 and compute price was $2.8026000000/hour. Quota is not guaranteed capacity. Startup cause, actual spend and remaining budget are unknown. Original compute cap remains $2.10195. No new endpoint was created.

The raw receipt and SHA audit are preserved under outputs/granite-recovery-34914225798-1. Receipt SHA256 is 964df1cee4f6573417ff88967f828013595bf97ff72d21e312d89a19e48350cc. GRANITE_RECOVERY_20260915.md describes the exact access gap and proposed-only read permission. No IAM policy was applied. A green diagnostic job does not establish hosted model/controller acceptance.

### Explicit Kalshi cancellation

Shared contract worker a65bc8d integrated as a97e58c3, authenticated DELETE transport d5e630ec as eec82134, and controller/ledger d309e021 as 9486c6f9. The controller uses the original submitted wire, independently pinned target response, explicit cancellation authority, exact account/provider/client/ticker and a bounded lifetime. A separate DELETE capability keeps the existing POST submission interface closed.

The existing ledger durably records CANCEL_ATTEMPT before network I/O, under the same writer lease and operation lock. Another control ID cannot bypass a consumed original order or account/provider target. Cancellation returns and errors do not change order state or release reserved exposure. Timeout, interruption, malformed acknowledgement and uncertain journal/receipt writes retain uncertainty and stop new exposure. Explicit cancellation may proceed while the ordinary exposure kill is latched.

Review corrected target freshness outliving the request lease, standalone preparation failures not latching the stop, and a preparation clock rollback boundary. Target age, control expiry and ready lifetime now constrain transmission. A concrete HTTPS test proves a delayed connect cannot send after expiry. The official response schema is retained and byte-pinned, with a narrowly scoped Git attribute preserving those exact bytes on Windows; root verified the normal integration checkout hash.

The final author transport selection recorded 377 execution passes, including 28 new transport and nine shared contract tests. Controller author selection recorded 96 passes, with 21 final controller tests independently rerun after the last code change. Independent reviews covered controller/ledger and transport/contracts. Final combined root verification and composed tests are recorded in the verification section above; these counts describe overlapping selections and must not be summed as distinct tests.

## Deployment alternative question

The user asked whether a paid GitHub subscription could replace AWS tonight. Official GitHub documentation lists GPU runners for Team/Enterprise organizations, separately billed at $0.052/minute for Linux, with one T4 and 16 GB VRAM. Markets currently belongs to a personal account. The pinned Granite BF16 weight shards total 17,583,228,032 bytes before runtime memory, so this runner does not fit the current all-GPU configuration. Personal Pro alone does not unlock that GPU runner. Quantization, offloading or a different host would require a separately verified runtime configuration. No subscription or service was purchased.

GRANITE_HOST_OPTIONS_20260915.md compares Runpod L40S 48 GB and Lambda A6000 48 GB, both publicly listed at $1.09/hour when checked. The user then authorized an availability check. Both live console paths required sign-in; no signed-in account was available in the connected browser. The sign-in pages were left ready. The user subsequently selected Runpod through the setup request below; sign-in remains pending. No stock, reservation or guaranteed capacity was established, and no account, payment or launch was performed. The existing SageMaker path requires portability work before either host is an accepted substitute.

## Runpod setup is a separate current task

After the host comparison and sign-in limitation, the user explicitly requested
Runpod setup using `https://docs.runpod.io/agent-setup.md`. Root is handling that
setup in parallel with this build closeout. Installation/configuration is in
progress at this snapshot. No authenticated GPU availability, reservation or
launch has been established by the setup request or this report. No accepted
Runpod runtime/controller inference or production promotion is claimed. Record
any later setup outcome separately; Sunday remains on hold.

## Preserved readiness gaps

- Dipole teacher software remains built, with the prior fresh 119-pass/one-CUDA-skip receipt. Fitted native/decoder/scorer/calibration artifacts and D0-D5 empirical acceptance remain open.
- Authentic source mapping, actual QSV masks/session configuration and causal population metadata admission remain open. No invented field authority or source-equivalence mapping was added.
- Actual Granite runtime/controller inference, required context capacity, repeatability, latency and combined attributed agent operation remain open.
- Authentic account positions/fills/history, valuation/reflection, deployed secret governance and real recovery/venue drills remain open. A page-chain receipt or cancel response must not be promoted into these facts.
- Flattening requires separately approved reduce-only intent against reconciled positions. It remains outside automatic emergency inference.
- C3/C4/O7/O9 remain deferred under the initial-sheet sequence.

## Preservation

Separate BOSS and receiver histories remain separate. Receiver tip remains b4f364f0812cd964c68faf3cef948b28d4603c90. No receiver files were changed this round. Protected prompts, Memory A, OPEN_ITEMS terminal states, prior 44 findings, E:/Markets and the deferred predecessor checkout remain untouched.

Eventual Sunday is 2021-10-03, anchor 33746436209, frozen prior 166,700 bytes, SHA256 4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a. October 1 remains waived. When ready, use the frozen fetch_frankie_ledgers -> emit_frankie_spawn -> actual agent session flow in a separate evidence worktree. Sunday is not scheduled.
