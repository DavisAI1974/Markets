# Shipping review — reusable request archive — 2026-09-23

Tested source: ca176dda82882a8cb48eb1452456f5aba5232376. This source-only slice follows the attachment assessment at ARCH_PLAN_R2_ASSESSMENT_20260923.md. It extends the existing request archive route; it does not yet automate the entire run.

## Result
- frankie_host_stage_critic_request.yml accepts workflow_call and manual dispatch with explicit required request/day/cycle/host/root/bucket/key-parameter inputs. No old day/cycle default can silently select a run.
- Credential-free validation precedes AWS/SSM. The native exporter requires the expected request hash, retains a unique create-only flushed preintent and completion, and omits signed capabilities from errors. Received bytes remain independently hash-checked by the caller.
- A reusable AES-GCM writer publishes exact bytes through durable retained files, refuses incomplete/foreign archives and authenticates unchanged replay. Replay re-syncs validated files and the directory before success. The reader's envelope schema is unchanged.
- Publication stages only the exact archive, skips unchanged commits, refuses stale source/rebase and reconciles ambiguous push success by the actual remote commit. Outputs distinguish source commit, archive commit and request SHA. Encrypted artifacts and publication intent survive failure.
- Branch-scoped noncancelling concurrency serializes active publishers. This is not a durable queue: GitHub can supersede pending jobs; future orchestration must reconcile pending events.

## Evidence
RED at 9a36948b179132415783cacfb5da763e157c0975: 28 failures and 51 missing-module setup errors in [run 35821092895](https://github.com/DavisAI1974/Markets/actions/runs/35821092895). Existing exporter tests reproduced overwritten/missing intents, accepted wrong hash and signed-capability disclosure.
GREEN at ca176dda82882a8cb48eb1452456f5aba5232376:
- 83 focused tests passed: 55 writer, 20 workflow validation/publication, 8 PowerShell export cases. [Run 35821195781](https://github.com/DavisAI1974/Markets/actions/runs/35821195781).
- Readiness: 84 +147 passed. [Run 35821195785](https://github.com/DavisAI1974/Markets/actions/runs/35821195785).
- Automatically triggered Classroom regression: host: 330 +22 subtests, box: 71 +17 subtests; compile and pinned shared-source verification passed. [Run 35821195765](https://github.com/DavisAI1974/Markets/actions/runs/35821195765). No separate Classroom investigation or live runtime was opened.

Independent code review covered root's workflow plus the security author's exporter. Independent security review covered the code author's writer plus root's workflow. Independent test review covered writer and exporter; root integrated and reviewed all scopes. New fault tests caught post-link directory-sync recovery before final integration. No reviewer is claimed independent for code they authored.

## Limits and next integration
No real dispatch, AWS/SSM export, archive publication, key access, Pod action or model call occurred. No host was started/stopped. Isolated tests use temporary Git/PowerShell files and test-only keys.
The existing transport key parameter must remain decryptable for retained archives. No key rotation or legacy two-file archive adoption was added; existing reader compatibility remains.
Rerunning the same GitHub run after its successful publication retains the old github.sha and safely refuses the advanced branch. A fresh invocation at the published commit verifies/no-ops. Lost acknowledgement whose actual remote ref equals the just-created commit is recognized in the same attempt. More general stale-branch reconciliation requires a separately reviewed identity rule.
Native Windows directory durability and live service behavior remain unverified. Hashes from the received object remain mandatory because file rechecks alone do not establish what was uploaded under concurrent source changes.
A workflow_call caller needs contents:write permission and the declared AWS secrets; this slice adds no live caller. The next automation step is receipt-bound lawful WAIT/event integration into the existing runner, host wrapper and day pipeline. Do not invent a competing unused event framework or wire the existing host_stop/stop_compute cleanup to waits. No WAIT authorizes a new inference or replacement job.
Cycle0/new run remains held until the final workflow task and owner release conditions are satisfied. The staged-source readiness report at 0b419436 remains valid for its unchanged earlier scope; the full live deployment gates remain.

## Rollback
No live rollback is needed. Preserve all intent, encrypted archive and publication artifacts. Do not delete failed exports, overwrite an archive, force-push/rebase scientific state, or revert to the prior unsafe error/receipt behavior.
