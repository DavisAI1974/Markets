# Drop-in for the next chat - Frankie/BOSS recovery, 2026-09-16

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first.

## Branches and tips

| branch | tip | what |
|---|---|---|
| `ccode/frankie-lawful-recovery-review-20260915` | `22abf3d4` | THE working branch: on top of ChatGPT's `58d6c023`; restore module fixed and proven, six unreproducible files captured, host runners, upload/restore/presign tools, consolidated sheet |
| `chatgpt/frankie-lawful-recovery-direct-benchmark-20260916` | `58d6c023` | ChatGPT's last; fast-forward the ccode branch into it |
| `ccode/frankie-dipole-classroom-review-20260916` | `f6f3787f` | classroom review (separate project) |
| `ccode/aws-idle-instance-guard-20260916` | PR #10 to default `claude/kalshi-s79-kickoff-ij8t9o` | idle EC2 guard, six-hourly; merge it |

Read first: `research/kalshi/frankie_boss/CCODE_CONSOLIDATED_RECOVERY_AND_CONDENSATION_20260915.md`
(sections 1.6 and 1.7 are the newest facts).

## Live state (costs money)

- **Native host** `i-0e90ee6110ef609aa`, r7i.4xlarge Windows Server 2022, us-east-2b, RUNNING,
  about $1.80/h. Tag `KeepRunning=false`. Environment verified: Python 3.13.7 at `C:\Python313`
  (sys.version identical to the failed run's binding), Git 2.47.1 autocrlf+longpaths, AWS CLI,
  `E:` 250 GB, tools checkout at `C:\tools\Markets` (fetch the ccode branch tip before use).
  **Stop it when not actively restoring or benchmarking** (`ec2 stop-instances`).
- **Old box** `i-08cee7171c0a76a04` STOPPED by Greg's order (was idle since Sep 2); its 300 GB
  volume kept on purpose.
- **Restore set in S3**: `s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/`
  complete: 27 bulk files (18.35 GB) + 6 tars + `UPLOAD_MANIFEST.json`. Every object sha256-pinned.

## Where it stopped

The on-host restore failed at its first download: the host's `Ssm` role has NO S3 rights on the
bucket (AccessDenied on ListBucket and GetObject, measured with `deploy/aws/frankie_host_s3_diag.ps1`).
Two prepared ways forward, nothing run yet:

1. **Durable (needs Greg in the IAM console):** attach `deploy/aws/frankie-native-host/SSM_ROLE_S3_READ_POLICY.json`
   (ListBucket on prefix `frankie/*`, GetObject on `frankie/*`) to role `Ssm`. Then run
   `python deploy/aws/ssm_run_ps1.py --instance i-0e90ee6110ef609aa --script deploy/aws/frankie_host_restore.ps1 --env-file scratchpad/aws.env --timeout 5400`.
2. **Immediate (no IAM change):** presigned GET links, 4 h, generated with the workstation key:
   `python deploy/aws/presign_restore_set.py --bucket bento-568968024170-us-east-2-an --prefix frankie/sunday_20260915_restore --hours 4 --out-ps1 deploy/aws/_frankie_host_restore_presigned.ps1`
   then `python deploy/aws/ssm_run_ps1.py --instance i-0e90ee6110ef609aa --script deploy/aws/_frankie_host_restore_presigned.ps1 --env-file scratchpad/aws.env --timeout 5400`.
   The links appear in SSM command history until they expire; do not commit the generated `.ps1`.

The restore writes `E:\Codex\RESTORE_RECEIPT_20260916.json` after: bulk audit 27/27, working-tree
audit 161/161 byte-exact at `050c5056`, venv answering `3.13.7 2.9.1+cpu 2.3.5`.

## Then, in order

1. Benchmark: `python deploy/aws/ssm_run_ps1.py --instance i-0e90ee6110ef609aa --script deploy/aws/frankie_host_benchmark_8_16.ps1 --env-file scratchpad/aws.env --timeout 7200`.
   Direct learner harness, fresh checkpoint, 8 then 16 threads, scratch clones under `E:\bench`.
   Read `E:\bench\direct_8t.jsonl` and `direct_16t.jsonl`: wall, peak RSS, last substage.
   Expectation from this box: prepare ~9 min single-threaded regardless of threads; forward needs
   >10 GB and OOMed at 16 GB; 128 GB host will show the real step. Pick threads from that.
2. Stop the host.
3. Report to Greg. 19-cycle run stays behind his explicit go; the host must carry
   `KeepRunning=true` for its duration and be started/stopped by hand.

## Build item Greg asked for ("matters for every day after today")

Make the compact journal (570 MB) authoritative for source verification so the raw 11.7 GB
journal is no longer needed by the host. Facts gathered, not yet written up as a spec:
- raw-journal touches in the lawful host: `source()` keys `source_origins` by the raw path;
  `source_lineage()` re-hashes the 4.4 GB lineage parent every start and reads tails/anchors of
  both raw journals; `prefix()` reads one row digest at ordinal `journal_count-1` from the raw
  origin per cycle.
- compact container: `blocks(start,count,body gzip,sha256,previous,head)` + `seal(format,count,head)`;
  `CompactReader.rows()` verifies block sha and continuity; `verified_partition` verifies row
  chain. A digest at ordinal N = decode the one block with `start<=N<start+count`.
- compact prefix receipts already carry `compact_parent {path,sha256,bytes}` and
  `parent {count,head_hash}`; cycle-0 prefix is still a raw snapshot (463 MB).
- ingestion receipt binds `journal_sha256` (raw) and `record_count 57027`; completion binds
  `journal_count 114054` and `journal_hash d8de0394...`; the compact seal must equal those.
Design: new host subclass (`operations/run_actual_sunday_compact_source.py`) overriding
`source()` and `prefix()`: verify the compact container's sha and seal against the completion
receipt, key `source_origins` by both raw and compact paths, take the prefix anchor digest from
the compact block, verify the closed-lineage RECEIPT chain instead of re-hashing the 4.4 GB
parent. Lawful `run_actual_sunday.py` untouched. Tests: build a small raw journal, compact it
with `CompactWriter`, snapshot, verify; negative: tampered block, wrong seal, wrong ordinal.
Future days: all 19 prefixes compact; raw journal archived cold. This is Part 2 item (2)/(3).

## Also open

- TLS: multipart uploads with `max_concurrency>=2` on one boto3 client raced botocore's
  per-request `cert_reqs` mutation into urllib3 InsecureRequestWarning; fixed to one worker with
  a guard test (`test_upload_sunday_restore_set.py`). Verification was never off.
- Classroom (other project): four design findings in `CCODE_REVIEW_DIPOLE_CLASSROOM_20260916.md`,
  chiefly that the correction turn hands the full answer key back one turn later.
- ChatGPT's next-chat docs on `d550c05e`: `CHAT.md`, `NEXT_CHAT_HANDOFF_20260915.md` (predate all of this).

## Do not

Run Frankie, Granite, the Pod, or any result-bearing cycle. Modify anything under
`E:\Codex\Frankie-BOSS-20260915` on the workstation. Leave the host running idle.
