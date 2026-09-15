# Live Sunday launch handoff — model switch to Sol

Updated 2026-09-15, approximately 14:06 UTC. This supersedes the stale process and launch status in the original handoff. User clarified **Sol**, not Opus. Continue in the same task; preserve running work.

## Current state — do not restart

- All19 prefixes are COMPLETE and archived to Git. Builder59772 and publisher56344 finished normally.
- Final manifest: E:/Codex/Frankie-BOSS-20260915/actual-prefixes/full19-prefix-witnesses.json
- Manifest SHA256: 44992e75ab0c821aac87559d4713bc84dd2f72424e2d904ebe81039def1ce416
- Batch SHA256 remains 0d700fc3be75e42b88c579d7158aca44e9acb0f5322a0bee3a481c035facffdf.
- Actual Python host **PID63112**, unified exec **session48894**. It has finished source inventory and retained preparation recovery, assembled the actual request, and passed admission. It is waiting on the existing stdin readiness trigger.
- CWD E:/Codex/Frankie-BOSS-20260915/sunday-launch-20260915/Markets
- Config E:/Codex/Frankie-BOSS-20260915/sunday-launch-20260915/actual-host-final-configuration.json
- Logs in the staging root: actual-host-resume02.stdout.log and actual-host-resume02.stderr.log.
- Run directory E:/Codex/Frankie-BOSS-20260915/actual-feedback-run
- Console input echo is disabled. Preserve the process/cache and use its existing secure stdin.
- Actual model inference has NOT started. No learning updates yet.

## Actual first request — use these live pins

Request ID frankie-boss-own-source-sunday-20260915-cycle-00
Request SHA256 **ec1bd4c34cd27a654b05e2811f892f4d2fe1aa44e6b5dc919cd972709cea92e2**
Request bytes151132; input92428, output38644, total131072.
Path actual-feedback-run/execution/cycle-00/actual-critic-request.json.
Host instance **4ab1d69ce40f4dd5b1792467954cc524**
Admitted at **1789481076.2855203**
Ready file execution/cycle-00/host-ready-4ab1d69ce40f4dd5b1792467954cc524.c15.json.
Checkpoint20b9d99d6c59998a0109427c92bd04110f293a8d80d8cfdc6491a6af23fd91d2.
Load C15 records using sunday_execution._load, not naive JSON field access.
The earlier retained example request07cc305a... and92427/38645 is NOT this live admission. An early staging-only job for that example succeeded but was not used for inference or Pod start.

## Applied retained Pod configuration

Pod jvs75m56w8f73q remains EXITED; retained L40S32vCPU, previously observed running compute1.09/hour.
The authorized environment rollout is APPLIED and every value compared:
- RUNPOD_GRANITE_LIFETIME_SECONDS = **none**
- GRANITE_MAX_MODEL_LEN =131072
- GRANITE_TRANSPORT_PROTOCOL =jobs_v1
- RUNPOD_BUNDLE_SHA256 =67affdb2de76a3cb36f17d326b223b148c0c363794f727421bd38a5470afea39
- RUNPOD_SUPERVISOR_COMMAND_SHA256 =391963397aed83cba895b0bc2e996b4d73d81887bfc93197f2e674256c12dbfd
- SUPERVISOR_PROGRAM__APP_COMMAND from final-v4 package receipt.
- RP_BOOTSTRAP_URLS from completed pinned bootstrap staging.
All other environment values, including existing private service key, preserved. No start/resize/reset/weight action performed.
Encrypted full pre-rollout record: staging/retained-pod-before-rollout.encrypted.json, SHA d2857a4c05a151d3e06b430505ad8d075c257d04a6ad8a1ce9cfd66094599cd9; also in Git compact-sunday-launch folder.

## GitHub staging completed

Operational workflow branch codex/full-frankie-boss-connection-20260915.
Publication branch codex/journal-reduction-stack-20260915. Never pull either into live runtime.
Relevant operational workflows/modules were checked blob-identical to runtime9a8f3f46.

Bootstrap:
- Marker commit55e88d7dfe841fe81cded101c7311b56a173b5ea.
- Successful run34978258747.
- Encrypted artifact downloaded to staging/bootstrap-stage-34978258747/bootstrap-stage.encrypted.json.
- Receipt validated against final-v4 source/bundle/file roster.
- **Presigned bootstrap URLs expire2026-09-15T14:12:12.070Z.** If insufficient remaining validity before start, refresh staging via the existing workflow, then update only the URL set while preserving all env. Expired staging capabilities are not inference retries.

Exact live request:
- Marker .github/frankie-request-stage-request.json updated to liveec1bd4c... SHA and151132bytes.
- Marker commitc357d154d39d04b5139e77031bcd1027b7ed6c64; marker blob7788a6e8373d8d3111671e2ef6a8ff5ea29b681e.
- Successful run**34979334781**.
- Encrypted artifact downloaded to staging/request-stage-34979334781/request-stage.encrypted.json.
- **Next: decrypt this receipt locally, inspect status, and if put_required upload the exact live admitted request using its conditional/checksummed S3 PUT. No upload for the live request has been performed yet.**
- The older example stage run34979066064 is not the actual request stage.

## Next launch actions

1. Check PID63112 and latest logs; keep current host alive.
2. Finish actual-request S3 staging. Match ec1bd4c.../151132.
3. Confirm bootstrap capabilities remain fresh, final provider env/pins, and actual local admission.
4. Create the real retained lease marker (still absent at last read) .github/frankie-retained-lease-request.json on operational branch with:
   request_sha256=live hash;
   local_ready exactly {request_sha256,host_instance_id,admitted_at} using above values;
   runtime_configuration=final-v4/runtime-configuration.json.
   Existing watchdog/prepare workflow owns start_once. Do not independently start Pod.
5. Observe that exact marker workflow. Download retained-granite-ready-RUN artifact into fresh E directory. Validate readiness package/context/lifetime/jobs and exact admission.
6. Supply one JSON line to **session48894**:
   schema FRANKIE_ACTUAL_EXECUTE_V1, service_key from existing private provider env, readiness_directory, service_pins_sha256.
   Never place service credentials in CLI, env, logs or public artifacts.
7. Follow actual durable job and principal handoff. All19 cycles, genuine printed Frankie analysis, authored causal feedback, existing recorder and learning checkpoints remain required.
8. Completion workflow dispatch acceptance is not stopped/ownership-release confirmation; observe actual cleanup before subsequent retained starts.
9. Publish completed stages promptly; current prefix publisher has finished and does not archive actual run results.

## Recovery performed; preserve evidence

First automatic host63176/session28840 exited before inference due to empty SQLite WAL/SHM beside the closed older source. Original database SHA and tail matched; exclusive handles proved closure. Sidecars preserved under staging/closed-parent-sidecars-01 and02. Source database unchanged. Read-only SQLite opens can recreate empty sidecars: on any genuine future restart inspect before acting; do not blindly delete or repeat hashes.

Next host37128/session99200 exited before inference because two teacher files had newline-only physical differences. Native hash and normalizer matched; teacher identity did not.
Restored exact original bytes from frozen C checkout:
c15_teacher.py SHA40742bbdd0cf60c36aadf40cec3e81a22ed6c356f760279e77ce01b53a824f89
c15_teacher_r3.py SHA55b9487c47181ec2ac6de6f5ccb8012397a8bd906abc37158db2bc1d9a9e90e9
Both normalized sources match pinned Git blobs; git diff stays clean. Teacher binding now exactly17b047724ecdc66ec6ad6992113f5a38b09bf554874948b83730ab55cdc1d3ec.
Failed pre-inference state, including untrained genesis checkpoint, preserved at actual-feedback-run-pre-inference-byte-mismatch. No inference retry occurred.
Native rawSHA40ace66b... remains unchanged. **Do not normalize physical teacher/native source bytes.**

## Final seal / reviews / publication

Existing receipt-only sealer succeeded after restoration; no tests or database scans in seal.
staging/final-seal-restored-teacher/FINAL_PRELAUNCH_CANDIDATE.json
SHA83bd809390498e98b9feb0484e5bf20e8801762585f4ee6d03bafc77971e1db8.
Root scoped approval/recovery report: outputs/frankie-boss/20260915/compact-sunday-launch/FINAL_ACTUAL_HOST_LAUNCH_REVIEW.md, commit62ec27e3d72ab83126881619b391807fe1e85846.
Seal/current PID/teacher recovery/encrypted rollback publication commit5564fed232c228faf59553913a2d238f26accec5.
Applied Pod rollout report commitfc464fd5b378c856b0a9d643659ca2c66e94d901.
Completed prefix manifest/config/sidecar record commitc2d2864f969208b301f5ef82f4a6d9c64ab9574d.
No passing suites repeated; only failed-binding diagnosis and specific identity verification performed. No prefix/reducer rebuild.

## Same-task memory and credentials handling

functions stores retain actualHostSession48894, actualHostPid63112, actualAdmission, podObject (PRIVATE), finalPodEnvironment (PRIVATE), bootstrapCapabilities (PRIVATE), bootstrapStageMarker, actualRequestStageMarker, stageBridgePublic, bootstrapBridgeEnvelope.
Never text private stores.
Persistent Node REPL retains fs/crypto imports, stageBridgeKeys (ephemeral RSA private key), bootstrapStage (PRIVATE), decryptBridge(), and bootstrapConfig.
Direct Node access to original recipient-private.pem was denied. Existing escalated E Python CAN read it. Successful handling: Python decrypt_receipt with original key and re-encrypt via encrypt_receipt to stageBridgePublic; return only ciphertext; Node decryptBridge holds resulting URLs only in memory. Do not print private key/URLs.
Original private key remains only at C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/bootstrap-jobs/recipient-private.pem.
Existing recipient fingerprintb437c74b14c4b79183ba12cec80d8f21b05c890d0fd71a73238a8f9afb4bd1a5.
New model in same task can reuse persistent tools; another task must not assume unified exec/Node sessions transferable.

## Standing instructions

No runtime elapsed cutoff while meaningful progress continues. possible_stall is advisory; distinguish waiting for operator input from computing, and CPU/I/O progress from mere heartbeat.
No smoke, repeated passing tests, extra source day, account/reset actions, ambiguous inference retries, new task files on C, or resumed old heartbeat.
Reuse existing pipeline; day values belong in configuration. Keep every ingestion field and all original evidence.
Read original required handoff documents for unchanged detailed contracts, plus operations/ACTUAL_PRINCIPAL_RESPONSE_HANDOFF.md for genuine Frankie response/provenance.
