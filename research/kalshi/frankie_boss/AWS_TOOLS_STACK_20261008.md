# AWS tools stack for Frankie/BOSS, 2026-10-08 (research pass 2: "what did we miss, and stack it")

SOURCE-BUILT / RUNTIME-UNVERIFIED. Read-only on the account (Describe*/List*/Get* only); nothing created, modified,
started or stopped. Every account/box action below is an exact command with its cost for relay to Greg. Prices are
us-east-1/us-east-2 on-demand list prices from the AWS pricing pages or the Pricing API at the time of reading; the
Pricing API and the pricing pages disagree on one number (cross-region transfer), both values are given.

Greg's rule for this pass (verbatim): "stacking is good and we don't want just one option ... Get everything that's
applicable in any part of this to help." So: every tool that helps is listed; a verdict of USE NOW means it stacks
with what is already built, not that it replaces anything. "If they even reduce a little they're getting used."

Companion to `AWS_DEEP_DIVE_20261007.md` (pass 1; its stacked plan still stands) and to the session-4 applied items in
`E2E_ONE_DAY_20231018.md` (gp3 1250 MiB/s, the S3 gateway endpoint, awscrt, read-ahead 4096 KB, dirty bytes, THP).

## 0. What this pass built (DELIVERABLE 2, all additive, nothing executed)
| File | What |
|---|---|
| `deploy/aws/frankie_aws_stack.py` (new) | boto3 "account stack": idempotent steps, `--dry-run` default, JSON receipt per step; `--apply` needs `--confirm GREG_GO_AWS_STACK`. Steps: s3-gateway-endpoint, s3-lifecycle, cw-agent, cw-alarms, scheduler-stop, launch-template, compute-optimizer, snapshot-archive, ebs-status, detailed-monitoring. |
| `deploy/aws/FRANKIE_AWS_STACK_README.md` (new) | How to run it, the step list, the confirm token, what each step costs. |
| `deploy/aws/box/frankie_box_s3_transport.py` (additive) | `upload(..., storage_class=, checksum_algorithm=, part_bytes=, concurrency=)` and `download(..., part_bytes=, concurrency=)`; receipt gains the keys only when given; existing callers unchanged (FRANKIE_S3_TRANSPORT_V1 kept). |
| scratchpad `aws_stack/test_transport_options.py` | Toy test with a fake S3 client: options reach ExtraArgs/TransferConfig, conflicts refuse loudly, old call shapes unchanged. |

## 1. Registry inventory
Method: `mcp__Aws__aws___search_documentation` with `topics=["agent_skills"]` over ~20 varied queries (storage, compute,
cost, monitoring, orchestration, data, security, networking, AI, serverless, database, SDK ...), until two further
sweeps added nothing new; then `mcp__Aws__aws___retrieve_skill` for every applicable SKILL.md and each of its
`references/*.md`. Skill count: **113 distinct skill names enumerated**; **21 SKILL.md files read in full**, plus
**34 reference files**. Pass 1 had read 5 skills and 9 references.

Read in full (21): aws-storage, aws-compute, aws-billing-and-cost-management, aws-observability,
setting-up-cloudwatch-alarm-notifications, configuring-vpc-endpoints-for-private-aws-service-access,
aws-step-functions, aws-serverless, amazon-bedrock, aws-sdk-python-usage, querying-aws-s3, aws-iam,
setting-up-ec2-instance-profiles, launching-ec2-instance-with-best-practices, amazon-ec2-image-builder,
securing-s3-buckets, troubleshooting-s3-files, aws-cloudformation, querying-data-lake,
troubleshooting-application-failures, aws-well-architected-review.

References read (34): aws-storage/{ebs, s3-general-purpose, s3-express, s3-files, fsx-lustre, efs,
data-movement-and-protection}; aws-compute/{instance-selection, provisioning, systems-manager, ami-management,
auto-scaling, troubleshooting}; aws-billing-and-cost-management/{ebs-optimization, ec2-rightsizing, budgets,
pricing-lookup, service-optimization, cost-optimization-hub, cost-audit}; aws-sdk-python-usage/{s3, configuration};
amazon-bedrock/{prompt-caching, cost-tracking, model-invocation}; configuring-vpc-endpoints (procedure);
setting-up-cloudwatch-alarm-notifications (procedure); aws-observability/{cloudwatch-alarms, metrics};
aws-serverless/orchestration; aws-step-functions/service-integrations; securing-s3-buckets/encryption;
amazon-ec2-image-builder/creating-images; setting-up-ec2-instance-profiles/setup.

Seen, judged not applicable from their descriptions (92): amazon-aurora-mysql, amazon-aurora-postgresql,
amazon-braket, amazon-documentdb, amazon-dynamodb, amazon-elasticache, amazon-eventbridge-event-bus,
amazon-keyspaces, amazon-neptune, amazon-opensearch-service, amazon-ses, amazon-workspaces-agent-access, aurora-dsql,
authoring-mwaa-workflow, aws-ai-ml, aws-amplify, aws-auth, aws-blocks, aws-cdk, aws-cleanrooms, aws-containers,
aws-database, aws-deployment, aws-fault-injection-service, aws-lambda-durable-functions,
aws-lambda-managed-instances, aws-lambda-microvms, aws-marketplace-metering, aws-messaging-and-streaming,
aws-network-monitoring, aws-networking, aws-resilience-lifecycle, aws-sdk-js-v3-usage, aws-sdk-swift-usage,
aws-security, aws-sms-voice, aws-social-messaging, aws-transform, cloudfront, connecting-lambda-to-api-gateway,
connecting-lambda-to-dynamodb, connecting-to-data-source, connecting-vpcs-with-peering,
creating-amazon-aurora-db-cluster-with-instances, creating-api-gateway-stage, creating-data-lake-table,
creating-production-vpc-multi-az, creating-secrets-using-best-practices, debugging-lambda-timeouts,
debugging-mwaa-workflow, deploying-custom-domain-rest-api,
developing-applications-on-managed-service-for-apache-flink, directconnect, dms-schema-conversion,
enabling-lambda-vpc-internet-access, exploring-data-catalog, exporting-rds-to-s3, finding-data-lake-assets,
ingesting-into-data-lake, launch-with-aws, managing-amazon-kinesis-data-streams, managing-amazon-msk,
migrate-to-msk, migrating-to-amazon-redshift, processing-s3-uploads-with-step-functions, querying-aws-cloudwatch,
querying-aws-redshift, querying-aws-sagemaker-catalog, rds-db2, rds-oracle, rds-oss, rds-sqlserver,
recovery-controller-setup, redshift-guide, resilience-hub-failure-mode-assessment, resilience-hub-getting-started,
resilience-hub-multi-account, route53, routing-traffic-with-route53-and-cloudfront, setting-up-cloudtrail-multi-region,
setting-up-cloudwatch-observability, shieldadvanced, signing-in-to-aws, sitetositevpn, storing-and-querying-vectors,
testing-mwaa-workflow, timestream-influxdb, transitgateway, troubleshooting-efs, upgrading-mwaa-environments, waf.
(There is still no AWS Batch skill in the registry; Batch facts below come from `read_documentation`.)

Regional availability (`get_regional_availability`, exact catalog names): FSx for Lustre, DataSync, Step Functions,
EFS, Bedrock, Batch, Athena, Systems Manager, EventBridge, CloudWatch all `isAvailableIn` us-east-1 AND us-east-2.
Cost Optimization Hub is a us-east-1 (global) console/API. EventBridge Scheduler is a feature of EventBridge. S3
Express One Zone AZ IDs: use1-az4/az5/az6 and use2-az1/az2; the box's AZ us-east-1d maps to use1-az6 (eligible).

## 2. Account facts used (read-only, 2026-10-08)
- Box i-035994afa8bdf66a5: r7i.8xlarge, us-east-1d, profile Ssm, IMDSv2 required (hop limit 2), detailed Monitoring
  disabled, EbsOptimized reported false (Nitro: EBS-optimized by default, nothing to enable), AMI
  ami-025d99823a4caad37, launched 2026-10-07T18:17:49Z. Instance EBS ceiling 1,250 MB/s and 40,000 IOPS (baseline =
  max on r7i.8xlarge). 12.5 Gb/s network.
- Root volume: gp3 2,048 GiB, 16,000 IOPS, 1,250 MiB/s, encrypted with CMK key/77551067-fa8c-412c-87a5-490d85ae2e79,
  DeleteOnTermination true. Modification 1000 -> 1250 MiB/s `completed` 2026-10-07T22:12:21Z.
- Archive volume vol-004b68c077be09cc9: gp3 2,048 GiB, 10,000 IOPS, 1,000 MiB/s, DeleteOnTermination false.
- S3 gateway endpoint vpce-0472311a451e2cedf exists in vpc-0be74ac7faf7e965e on rtb-095aab35cdfc7ec27 (us-east-1).
- Buckets: bento-568968024170-us-east-2-an (data, us-east-2) and frankie-granite42-568968024170-us-east-1 (leases,
  pod-root). bento: no lifecycle configuration, no Intelligent-Tiering configuration, no Metadata configuration,
  versioning off. ListDirectoryBuckets: AccessDenied for the connector role.
- 0 snapshots, 0 launch templates, 0 CloudWatch alarms, 0 SSM associations, 0 EventBridge schedules, 0 DLM
  policies, 0 SNS topics, 1 KMS CMK; EBS encryption-by-default off. Budgets present: DavisAI-Daily-Cost-Guard $10,
  DavisAI-Monthly-Cost-Guard $200. Compute Optimizer enrollment Inactive; Cost Optimization Hub not enrolled.
- Workflow numbers (probe 2026-10-08): one day's ROOT = 497 GB frame spool + 472 GB inline layer + 404 GB native
  ledgers (~1.37 TB); layer write 8.1 GB/min; sequential reads 1.09-1.25 GB/s on the root volume (= the instance
  ceiling); Monday archive 427 GB -> 297 GB tar.zst (0.70); MBO fetch 15 x 16 MiB ranged GETs; CRT 128 MiB x 16.

## 3. The tool table
Columns: what / which piece and how (numbers) / stacks with / cost / regions / runtime or source-only / verdict.
"Box" = needs the running box or the account; "source" = code or config only.

### 3.1 EBS
| Tool | What, which piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| gp3 provisioning (done 1250) | Root volume at the instance ceiling: 1,250 MiB/s and 16,000 IOPS. Reads measured 1.09-1.25 GB/s. gp3 limits now 80,000 IOPS (500 IOPS/GiB, max at >= 160 GiB) and 2,000 MiB/s (0.25 MiB/s per IOPS, max at >= 8,000 IOPS). | Everything on the root volume | $0.08/GiB-mo; $0.005/IOPS-mo above 3,000; $0.04/MiB/s-mo above 125. Root: 2,048 x 0.08 = $163.84 + 13,000 x 0.005 = $65 + 1,125 x 0.04 = $45 = $273.84/mo. Archive: $163.84 + $35 + $35 = $233.84/mo. | both | box | USE NOW (applied) |
| The modification rule | Elastic Volumes: up to 4 modifications per rolling 24 h per volume; each must reach `completed` (DescribeVolumesModifications); a fully used 1 TiB volume takes ~6 h to optimize (2 TiB ~12 h); performance during `optimizing` is between old and new, never below old. The 1000->1250 change completed 22:12Z on 10-07, so the next change is allowed now. | ebs-status step in frankie_aws_stack.py | free | both | box | USE NOW (the step reports it) |
| gp3 vs io2 | io2 Block Express: $0.125/GB-mo + $0.065/IOPS-mo (first 32,000), 256,000 IOPS/4,000 MB/s per volume, 99.999% durability. The box's ceiling is 1,250 MB/s / 40,000 IOPS, which gp3 already reaches at $273.84/mo; io2 at 16,000 IOPS = $256 + $1,040 = $1,296/mo for the same ceiling. | - | see left | both | box | NOT APPLICABLE on r7i.8xlarge (ceiling-bound; 4.7x the price for nothing) |
| RAID0 striping (multi-volume) | Linux mdadm across gp3 volumes sums per-volume IOPS/throughput; the instance ceiling caps the sum. r7i.8xlarge: 1,250 MB/s total, so root (1,250) + archive (1,000) already exceed it when both are busy; a stripe cannot exceed 1,250 either. r7i.16xlarge: 2,500 MB/s / 80,000 IOPS, where two gp3 at 1,250 striped reach the ceiling. | launch-template step: `--scratch-volumes N` builds the stripe in user-data (mdadm --level=0 --chunk=256) | volume price x N | both | box | USE WHEN a 16xlarge or a clone needs > 1,250 MB/s (AWS_DEEP_DIVE item: second box is a 16xlarge); NOT on the 8xlarge |
| st1 / sc1 | st1 $0.045/GB-mo, 500 MB/s per volume max, baseline 40 MB/s per TB (2 TB = 80 MB/s baseline, bursts to 250); sc1 $0.015. The layer write runs at 8.1 GB/min = 135 MB/s sustained, above st1 2 TB baseline; the digest read-back at 1.09-1.25 GB/s is 2.5x the st1 per-volume max. | archive volume only after the write phase | st1 2 TB = $92/mo vs gp3 $233.84 | both | box | USE WHEN the archive volume is a cold spool parking lot only (saves $141.84/mo); NOT for ROOT's live spool |
| Snapshot of the archive volume + Archive tier | Snapshot $0.05/GB-mo (incremental, only written blocks); Archive tier $0.0125/GB-mo, full copy, 90-day minimum, restore 24-72 h, $0.03/GB on restore. 297 GB Monday tar.zst: Standard snapshot $14.85/mo, Archive $3.71/mo. | snapshot-archive step; S3 Glacier below is cheaper per GB for the same bytes | see left | both | box | USE WHEN Greg picks snapshots over S3 for the 30-day archive; S3 Glacier Flexible beats it ($1.07/mo for 297 GB) |
| Fast Snapshot Restore | $0.75 per DSU-hour per snapshot per AZ, 1 h minimum (a 2 TiB snapshot = 2 DSU = $1.50/h = $1,080/mo if left on). Only matters when a clone must read a restored volume at full speed in its first minutes. | golden AMI for clones | $0.75/DSU-h | both | box | USE WHEN a 30-day clone fleet boots from one AMI and the first stage reads > 100 GB from it; enable for the launch hour only, then disable |
| Provisioned Rate for Volume Initialization | 100-300 MiB/s per volume from a snapshot (region cap 5,000 MiB/s total); replaces the per-block lazy load. | launch template BlockDeviceMappings (VolumeInitializationRate) | $0.0017/GiB per restore (region-priced) | both | box | USE WHEN clones restore from a snapshot (the AMI with granite + venv): 100 GB at 300 MiB/s = 6 min instead of lazy-load stalls |
| EBS Volume Clones | Instant copy of a volume in the same AZ; the clone is readable while hydrating. Lets a second box start on the a2 ROOT output while the main box keeps running. | multi-box ROOT | new volume price | both | box | USE WHEN a second box needs the saved ROOT state in us-east-1d without an S3 round-trip |
| DeleteOnTermination | Root true, archive false on the box (verified). Clones: root true (nothing durable there), scratch true, nothing to leak. | launch template | 0 | both | source | USE NOW (encoded in the template) |
| Encryption-by-default | Off; the root volume uses the CMK. EBS uses one data key per volume; KMS $1/CMK-mo, 20,000 free requests then $0.03/10k. A clone fleet of 16 boxes adds ~32 GenerateDataKey calls, inside the free tier. | - | ~$0 | both | box | USE WHEN the fleet launches (`EnableEbsEncryptionByDefault`, free); not needed for the one box |

### 3.2 Instance store families (for the clones; the main box has no NVMe: r7i has no `d` variant)
| Type | Local NVMe | vCPU/RAM | EBS ceiling | On-demand $/h | Spot (first price per AZ seen) | Verdict |
|---|---|---|---|---|---|---|
| r8id.8xlarge | 1 x 1,900 GB | 32 / 256 GiB | 1,250 MB/s | $2.66112 | ~$0.62-0.88 (r8i) | USE WHEN the one-box-per-day fleet runs: one day fits (1.37 TB) with 0.5 TB spare; two do not |
| i7i.8xlarge | 2 x 3,750 GB | 32 / 256 GiB | 1,250 MB/s | $3.0202 | ~$1.07-1.71 | USE WHEN two big days share a box: 7.5 TB local, stripe the two |
| i7ie.6xlarge | 2 x 7,500 GB | 24 / 192 GiB | 937.5 MB/s | $3.1188 | ~$1.05-1.27 | USE WHEN disk matters more than cores (3 lanes of 8 CPUs, 15 TB) |
| i7ie.12xlarge | 4 x 7,500 GB | 48 / 384 GiB | 1,875 MB/s | ~$6.24 | - | USE WHEN 3 days per box: 30 TB, 48 CPUs |
| i4i.8xlarge | 2 x 3,750 GB | 32 / 256 GiB | 1,250 MB/s | $2.746 | ~$0.9-1.4 | fallback for i7i capacity errors |
Instance store is lost on stop and terminate: archive (clean+zip to S3) BEFORE the terminate, which is the stage
handoff's existing order. Byte identity across CPU generations stays the gate (sha256 canary from pass 1).

### 3.3 EC2 (compute)
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| Launch template (one box per day) | IMDSv2 required, hop limit 2, profile Ssm, detailed monitoring on, root gp3 with DeleteOnTermination, N scratch gp3 volumes (or instance-store NVMe) striped by user-data into /mnt/scratch, InstanceInitiatedShutdownBehavior=terminate, tags Project/KeepRunning/Day. | EC2 Fleet instant (pass 1), golden AMI, the stage handoff's "trigger next" | 0 for the template | both | box (create) / source (JSON) | USE NOW (built as the launch-template step; creation is Greg's go) |
| EC2 Fleet `instant`, On-Demand prioritized | One call launches N boxes across types/AZs (r8id -> r8i -> r7i); capacity errors fall through instead of failing the day. | launch template | 0 | both | box | USE WHEN the 30-day run starts (pass 1 item, still right) |
| Spot | r7i.8xlarge ~$0.53-0.64/h vs $2.1168 (-70 to -75%); r8i ~$0.62-0.88; i7i ~$1.07-1.71; i7ie.6xl ~$1.05-1.27. Interruption loses on-disk state; persistent requests are needed for stop/hibernate. | stage handoff save points (each stage saves to S3) | -70% | both | box | USE WHEN a stage is restartable from its S3 save (teacher, classroom, reports: yes); NOT for ROOT mid-replay (pass 1 stands) |
| Hibernation | Requires RAM < 150 GiB on Linux and enabling at launch; r7i.8xlarge has 256 GiB. | - | - | both | box | NOT APPLICABLE (RAM over the limit) |
| Placement groups | cluster/spread/partition; lanes don't talk to each other, and cluster groups raise capacity errors. | - | 0 | both | box | NOT APPLICABLE (no inter-box traffic) |
| ENA / EBS baselines | 12.5 Gb/s NIC = 1.56 GB/s; S3 pulls from us-east-2 are bounded by the NIC, not EBS (1.25 GB/s is the EBS write ceiling anyway). 16 x 128 MiB CRT parts keep the NIC busy. | CRT transport | 0 | both | source | USE NOW (already the transport's shape) |
| Detailed monitoring (1-min) | Gives 1-minute CPUUtilization for the idle alarm (5-min basic otherwise). | cw-alarms | $2.10/instance-mo (7 metrics x $0.30) | both | box | USE WHEN the idle-stop alarm is on (detailed-monitoring step) |
| Scheduling (start/stop) | EventBridge Scheduler universal target ec2:stopInstances / startInstances at a cron. 14M invocations/mo free. Replaces a cron on the GitHub runner for fixed windows. | the KeepRunning tag and the queue HOLD (a stop schedule must honor them: the step is opt-in) | 0 | both | box | USE WHEN Greg wants a hard nightly stop time; otherwise the alarm below |
| Compute Optimizer / Cost Optimization Hub | Free; 14-day lookback; recommends the type from measured CPU/mem/EBS/network. Enrollment Inactive today. Needs 30 h of metrics for a finding, so the main box (always on) will get one; killed clones won't (pass 1 reason, true for clones only). | ec2-rightsizing | 0 | COH us-east-1 | box | USE NOW (compute-optimizer step: two enrollment calls, free) |
| AMI golden image / Image Builder | Image Builder pipelines (free, pay for the build instance) can rebuild the lean image on a schedule with the venv/granite warm. The 2 TB root AMI is too big to image; image the lean second box (97 GB used). | launch template | build instance minutes | both | box | USE WHEN the clone fleet is real; Image Builder is the repeatable form of pass 1's "golden AMI" |

### 3.4 S3
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| Gateway endpoint | Exists for us-east-1 (vpce-0472311a451e2cedf). Same-Region only: the bento bucket is in us-east-2, so bento traffic goes over the public path (NAT/IGW) and pays cross-region transfer. The granite bucket (us-east-1) rides the endpoint free. | s3-gateway-endpoint step (verifies, creates only if absent) | 0 | same-Region | box | USE NOW (present); the cross-region half is Greg's region call below |
| Cross-region transfer | us-east-2 -> us-east-1: Pricing API $0.01/GB; the data-transfer page says $0.02/GB. 30 days x 297 GB archive = 8.9 TB: $89-178 if archived to us-east-2 from a us-east-1 box; a day-file pull of ~30 GB/day = $0.30-0.60/day. | archive policy | $0.01-0.02/GB | - | - | USE WHEN deciding the archive bucket: a us-east-1 bucket for outputs removes it entirely |
| CRT transfer client | boto3 `TransferConfig(preferred_transfer_client='crt')`; awscrt 0.31.2 installed on the box venv (absent in this container). Env AWS_CRT_S3_MEMORY_LIMIT_IN_GIB and AWS_CRT_S3_MAX_PARTS_PENDING_READ bound memory. | transport `_configs` (CRT first, classic fallback) | 0 | - | box | USE NOW (applied; part/concurrency now overridable per call) |
| Multipart thresholds | upload parts 128 MiB x 16 in flight = 2 GiB in flight per upload; 4 GiB pieces for archive_day. S3 maximum 10,000 parts, 5 GiB per part; a 297 GB tar.zst at 128 MiB = 2,376 parts (fine). | transport part_bytes/concurrency options | PUT $0.005/1000: 2,376 parts = $0.012 | both | source | USE NOW |
| Default integrity (CRC64NVME) | SDK sends trailing checksums by default (boto3 >= 1.36); full-object CRC64NVME is composable across multipart, so S3 verifies the whole object. Our sha256 metadata stays the proof; CRC catches corruption in flight for free. | transport `checksum_algorithm` option (ExtraArgs ChecksumAlgorithm) | 0 | both | source | USE NOW |
| Storage classes for the archive | Ohio: Standard $0.023/GB-mo; Standard-IA $0.0125 (30-day min, $0.01/GB retrieval); One Zone-IA $0.01; Glacier Instant $0.004 (90-day min, 128 KB min, $0.03/GB retrieval); Glacier Flexible $0.0036 (90-day min; bulk retrieval free, standard $0.01/GB, expedited $0.03/GB); Deep Archive $0.00099 (180-day min, 12-48 h). 30 days x 297 GB = 8.9 TB: Standard $205/mo, IA $111, GIR $36, Flexible $32, Deep $8.8. Versus the archive volume: $233.84/mo for 2 TB (which holds ~6 days). | transport `storage_class` option; s3-lifecycle step (transition by prefix after N days); archive_day/offload uploaders can pass StorageClass through extra_args today | see left | both | source + box | USE NOW for `StorageClass` on archive uploads once Greg picks the class (f); USE NOW for the lifecycle rule to Glacier Flexible on frankie/ingest/ after 30 days |
| Lifecycle rules | Transition by prefix + ObjectSizeGreaterThan (128 KB default minimum, waterfall only: Standard -> IA -> GIR -> Flexible -> Deep); AbortIncompleteMultipartUpload after 7 days (stops paying for dead 4 GiB pieces from killed boxes); Expiration for stale pod-root leases is NOT included (owner's call). | s3-lifecycle step | 0 (transition requests $0.05/1000 to Glacier) | both | box | USE NOW (abort-MPU rule has no downside; transitions after Greg's class choice) |
| Intelligent-Tiering | $0.0025 per 1,000 objects monitoring; objects < 128 KB not tiered. Our archive objects are 4 GiB pieces (few objects) so monitoring is ~$0, but it moves them to Archive Instant/Deep only after 90/180 days of no access; a lifecycle rule does the same on a date we choose. | lifecycle | ~$0 | both | box | USE WHEN access patterns are unknown; for 30 known days the lifecycle rule is the direct form |
| Express One Zone | $0.11/GB-mo; PUT $0.00113/1000, GET $0.00003/1000, upload $0.0032/GB, retrieval $0.0006/GB; single-digit ms, same-AZ (use1-az6 ok). For a 1.37 TB day staged for one teacher read: $150/mo pro-rated = $5/day, plus $4.38 upload + $0.82 read. Local gp3 at $0.08/GB already holds it at 1.25 GB/s; Express is for many readers in the AZ. | Mountpoint `--cache-xz` | see left | use1-az4/5/6, use2-az1/2 | box | USE WHEN several boxes in use1-az6 read one day's ROOT output (the multi-box teacher/classroom fan-out); NOT for the single box |
| Mountpoint for S3 | FUSE read of S3 as files, CRT-backed, sequential writes only, no in-place modify, cache on EBS/instance store or Express. Lets the teacher read the archived digest without a restore step. | Express cache | 0 | both | box | USE WHEN a stage reads archived outputs read-only (teacher on a prior day's digest) |
| S3 Files | NFS mount over S3 on EFS infrastructure, $0.30/GB-mo. 13x gp3. | - | $0.30/GB-mo | both | box | NOT APPLICABLE (gp3 at $0.08 and local NVMe are cheaper and faster) |
| Transfer Acceleration | $0.04/GB, edge-routed uploads from far clients; the box is in-Region. | - | - | - | - | NOT APPLICABLE (in-Region; pass 1 stands) |
| Batch Operations | $0.25/job + $1.00/million objects; copy/restore/tag whole prefixes from an inventory manifest. 30 days x ~75 pieces = 2,250 objects: $0.25 + $0.002. | lifecycle (restore-from-Glacier of a whole day in one job) | $0.25/job | both | box | USE WHEN restoring a whole day from Glacier Flexible (one job, bulk tier free) |
| S3 Inventory / Metadata tables / Storage Lens | Daily CSV/Parquet of the bucket (Inventory $0.0025/million objects) instead of ListObjects sweeps; Storage Lens free tier shows per-prefix bytes by class. | verify-after-archive | ~$0 | both | box | USE WHEN the 30-day archive is in place (the verify step reads one manifest instead of 30 LISTs) |
| Request costs | Standard PUT/LIST $0.005/1000, GET $0.0004/1000. MBO fetch of a 1.6 GB file at 16 MiB ranges = ~100 GETs = $0.00004. Not a cost driver anywhere in the workflow. | - | - | both | - | measured, no action |

### 3.5 Data movement and shared file systems
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| DataSync | Managed EBS/EFS/S3 -> S3 copies with verification; Enhanced mode $0.015/GB + $0.55 per task execution. 297 GB day archive = $5.01 vs $0 with the box's own CRT upload (which already verifies sha256). | - | $0.015/GB | both | box | USE WHEN a cross-region bulk move of the whole bento prefix is needed (e.g. 8.9 TB to a us-east-1 bucket: $134 + transfer); NOT for per-day archives |
| FSx for Lustre | SSD Persistent 2 at 125/250/500/1,000 MB/s per TiB; Intelligent-Tiering class; S3 data repository association with lazy load and file release. Shared POSIX scratch across N boxes: a 2 TiB Persistent-2 1000 file system ~$0.60/GiB-mo = $1,228/mo. | multi-box fan-out | ~$1,200/mo for 2 TiB | both | box | USE WHEN >= 4 boxes must read/write one day's spool concurrently (teacher + classroom + search on one ROOT output); NOT for single-owner spools (pass 1 stands) |
| EFS | Elastic throughput, Standard/IA/Archive classes; ~$0.30/GB-mo Standard, 3 GB/s max per file system by default. | - | $0.30/GB-mo | both | box | NOT APPLICABLE for TB spools (12x gp3 price, lower throughput) |

### 3.6 Systems Manager
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| Run Command (in use) | AWS-RunShellScript via deploy/aws/ssm_run_sh.py from frankie_box_run.yml. Priced $0.002 per invocation from 2026-09-30 (Advanced tier eliminated 2026-06-30). 500 dispatches/mo = $1. | the whole dispatch route | $0.002/invocation | both | box | USE NOW (in use) |
| Session Manager | Interactive shell without SSH; $0.05/session from 2026-09-30. Logs to S3/CloudWatch. | probes | $0.05/session | both | box | USE NOW for interactive probes (already the route, no SSH keys) |
| State Manager | Associations that re-apply on a schedule or on a change; free. `AmazonCloudWatch-ManageAgent` association installs/configures the CW agent from an SSM parameter and restarts it. Also fit: an association that re-asserts the box's sysctls (dirty bytes, THP, read-ahead) after every reboot, which today are hand-applied. | cw-agent step | 0 | both | box | USE NOW (cw-agent step builds the parameter + association) |
| Automation | Runbooks with approval steps (AWS-StopEC2Instance, AWS-CreateSnapshot, AWS-ResizeInstance); the pieces of a stage handoff that touch the account could be one runbook with a manual approval step for Greg's go. | Step Functions | 0 (first 100k steps free) | both | box | USE WHEN the stage handoff's "trigger next" needs an approval gate in the account instead of in chat |
| Parameter Store | Already used for the GitHub token (/markets/frankie/github-token, us-east-2). Standard parameters free. | - | 0 | both | - | in use |

### 3.7 CloudWatch, EventBridge, orchestration
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| CloudWatch agent metrics | disk_used_percent (per mount), mem_used_percent, diskio read/write bytes, with `aggregation_dimensions [[InstanceId, path]]` so the alarm dimensions are stable. 8 custom metrics = first 10 free; PutMetricData $0.01/1000 (1-min, 8 metrics = $0.35/mo). | cw-alarms; the probe (units/min) stays | ~$0.35/mo | both | box | USE NOW |
| Alarms replacing the cron guards | `disk_used_percent >= 85` on / and /mnt/archive (the disk guard that today is a box script); `StatusCheckFailed_System` with the `ec2:recover` action; `CPUUtilization < 2% for 60 min` with `ec2:stop` (the idle guard that today runs on the GitHub runner every 6 h: a 6-h gap at $2.1168/h = up to $12.70 per idle event; the alarm cuts it to 1 h = $2.12). Metric-math and composite alarms cannot take EC2 actions; a plain metric alarm can. KeepRunning=true and the queue HOLD must disable the stop alarm (`DisableAlarmActions`), so the idle-stop alarm is opt-in. | SNS topic (optional email), detailed monitoring | $0.10 per alarm-month standard, $0.30 high-res; 5 alarms = $0.50/mo | both | box | USE NOW for disk + system-recover alarms; USE WHEN the HOLD/KeepRunning handshake is wired for the idle-stop alarm |
| treatMissingData | `breaching` for the disk alarm (an agent that stops reporting is itself a fault); `notBreaching` for the idle alarm (a stopped box must not re-trigger). | cw-alarms | 0 | - | source | encoded in the step |
| SNS | Email/SMS from alarms; $2/100k notifications, email free. 0 topics today. | cw-alarms `--sns-topic-arn` | ~0 | both | box | USE WHEN Greg wants the alarm by email (one CreateTopic + Subscribe) |
| EventBridge Scheduler | cron/rate/one-time schedules, universal targets (any AWS API), 14M invocations/mo free then $1.00/M. Can stop the box at a fixed time, start it before a scheduled day, or fire the day's dispatch without GitHub. | scheduler-stop step; Step Functions | 0 | both | box | USE WHEN a fixed window is wanted; the idle alarm covers the variable case |
| Step Functions (Standard) | Runs up to 1 year; 4,000 free state transitions/mo then $0.025/1000; SDK integrations `arn:aws:states:::aws-sdk:ssm:sendCommand` + `.sync` wait, `ec2:runInstances`, `s3:headObject`; waitForTaskToken for Greg's go. A 30-day Map state (one branch per day, MaxConcurrency = boxes) = the "trigger next" chain across boxes with retries and a visible state. ~10 transitions per day x 30 = 300 (free). | launch template, SSM Run Command, the stage handoff's validate->save->clean->zip | ~0 | both | box | USE WHEN the one-box-per-day run starts; replaces the GitHub dispatch HTTP-500 retries (fix-after list) |
| AWS Batch | No charge; container jobs on EC2/Fargate; no cpuset pinning or hyperthread control inside a container; GPU/CPU queues. | - | 0 | both | box | NOT APPLICABLE (lane pinning by physical core is a hard requirement) |
| Athena + Glue | $5/TB scanned, 10 MB minimum per query; Glue catalog first 1M objects free. Could query the archived day manifests/receipts (JSON) across 30 days without a box. | S3 Inventory | $5/TB | both | box | USE WHEN the 30-day reports need cross-day queries over S3 manifests (KB-scale: cents); DuckDB on the box covers the TB-scale tables (pass 1 stands) |
| Lake Formation | Permissions layer for Glue tables. | - | - | - | - | NOT APPLICABLE (one account, one role) |

### 3.8 Bedrock (the teacher-logic helper; Granite stays on the box's CPU)
| Tool | What, piece, numbers | Stacks with | Cost | Regions | Where | Verdict |
|---|---|---|---|---|---|---|
| Prompt caching | Cache the fixed prefix (system prompt + digest grammar + the day's digest) across the classroom's repeated calls: cache reads cost 10% of input tokens; 5-min TTL writes +25%, 1-h TTL writes 2x; minimum cacheable prefix 1,024-4,096 tokens by model; break-even at 2 requests per TTL. Not combinable with batch inference. A 75,000-token digest read 10 times in 5 min: 75k x (1.25 + 9 x 0.10) = 161k billed vs 750k = -78.5%. | the token stacks (shrink first, then cache) | -78% on repeated reads | us-east-1 | source (cachePoint in the request) | USE WHEN a Bedrock stage sends the same prefix >= 2 times per TTL (classroom arm, scientific teacher on the same day) |
| Batch inference | 50% of on-demand; async JSONL in S3; no caching; hours of latency. Fits the end-of-day reports (not interactive). | - | -50% | us-east-1 | box | USE WHEN a report stage has > 100 independent prompts and no deadline |
| Provisioned throughput / service tiers | Model units by the hour/month; service tiers (priority/default/flex) trade latency for price; flex is cheaper for non-urgent calls. | - | varies | us-east-1 | - | USE WHEN a stage is throttled on on-demand; otherwise not |
| Inference profiles + cost allocation tags | Per-stage tags (teacher, classroom, reports) on application inference profiles make Cost Explorer show Bedrock spend per stage. | Budgets | 0 | us-east-1 | box | USE NOW when the first Bedrock stage runs (one CreateInferenceProfile per stage) |

### 3.9 Cost, IAM, KMS
| Tool | What, numbers | Cost | Verdict |
|---|---|---|---|
| Budgets (exist) | $10/day and $200/month guards. A 30-day fleet at 16 x r7i.8xlarge x 7 h = $237 compute blows the $200 monthly guard by design: raise it for the run month or it alerts on day 1. | 2 budgets free | USE NOW (note the $200 ceiling before the run) |
| Cost Explorer API | $0.01 per request; the cost-audit reference's daily/service grouping is the per-run cost receipt (one call per day = $0.30/mo). | $0.01/request | USE WHEN the 30-day run needs a per-day cost line in the end-of-day report |
| Cost anomaly detection | Free; alerts on a spend spike (a forgotten box). | 0 | USE NOW (one monitor, free) |
| IAM instance profile scopes | The box's profile Ssm; a launch-template fleet should carry a day-scoped profile: s3 Get on its day prefix, Put on its archive prefix, ssm:UpdateInstanceInformation, cloudwatch:PutMetricData, ec2:TerminateInstances on self (condition aws:ARN). `frankie_iam_policy.example.json` is the pattern. | 0 | USE WHEN the fleet launches |
| KMS | $1/CMK-mo; 20,000 free requests then $0.03/10k; EBS one data key per volume; S3 SSE-KMS adds a request per object (bucket keys reduce it ~99%). 2,250 archive objects = $0.007 without bucket keys. | ~$1/mo | in use; no action |

## 4. Stacks (combined effect, cost)
S1. **One-box-per-day fleet** = launch template (IMDSv2, Ssm, monitoring, scratch stripe) + EC2 Fleet instant
    (r8id -> r8i -> r7i) + golden AMI with Provisioned Initialization Rate 300 MiB/s + Step Functions Map over the 30
    days (`ssm:sendCommand.sync` per stage, waitForTaskToken for Greg's go) + per-box archive with `StorageClass`
    GLACIER (or the class Greg picks) + `InstanceInitiatedShutdownBehavior=terminate` + the lifecycle abort-MPU rule
    for killed boxes + a day-scoped instance profile. Effect: 30 days in one wall-clock day instead of 30; per-day
    cost r8id $2.66/h x hours; the orchestration, template, lifecycle and profile cost $0. Risk: the 640-vCPU quota
    (request pending) and byte identity across CPU generations (the sha256 canary).
S2. **Archive policy (Greg's call f)** = archive volume (st1 at $92/mo if kept as a parking lot, or dropped) + S3
    Glacier Flexible via `storage_class` on the archive upload ($32/mo for 8.9 TB vs $233.84/mo for a 2 TB volume
    that holds 6 days) + lifecycle Deep Archive after 90 days ($8.8/mo) + Batch Operations bulk restore (free tier,
    $0.25/job) + S3 Inventory for the verify step. A us-east-1 output bucket removes $89-178 of cross-region transfer.
    Effect: -$200/mo and no disk ceiling; restore latency 3-5 h (Flexible bulk) or 12-48 h (Deep).
S3. **Guards in the account instead of on the runner** = CloudWatch agent (disk/mem) + State Manager association
    (reinstalls after reboot) + alarms (disk 85%, system-recover, idle-stop opt-in) + SNS email + Cost anomaly
    detection. Effect: an idle box stops within 1 h instead of 6 (up to $10.58 saved per idle event), a full disk
    alerts before a stage dies; $0.85/mo plus $2.10/mo if detailed monitoring is on.
S4. **Every S3 byte** = gateway endpoint (granite bucket, free) + CRT 128 MiB x 16 + ranged presigned GETs 15 x 16
    MiB + CRC64NVME trailing checksums + sha256 metadata + 4 GiB pieces with If-None-Match + Express One Zone
    staging when boxes fan out in use1-az6 + Mountpoint for read-only archived digests. Effect: NIC-bound transfers
    (1.56 GB/s ceiling) with end-to-end integrity at $0 extra.
S5. **Bedrock stages** = token stacks first (lossless shrink) + prompt caching (-78% on 10 repeated reads of a 75k
    digest) + batch inference (-50%) for the reports + cost allocation tags per stage + the existing $10/day budget.
S6. **Right-sizing after the run** = Compute Optimizer + Cost Optimization Hub (free, two calls) + Cost Explorer
    daily grouping ($0.01/call) feeding the end-of-day report's cost line.

## 5. Relay list for Greg (exact commands; each is one go; costs stated)
All via `python3 deploy/aws/frankie_aws_stack.py --apply --confirm GREG_GO_AWS_STACK --steps <step>` from a shell
holding the Claude IAM credentials (dry run first: drop `--apply`). Equivalent raw calls listed for the record.
1. `--steps s3-gateway-endpoint`  -- verifies vpce-0472311a451e2cedf; creates nothing if present. $0.
2. `--steps s3-lifecycle --bucket bento-568968024170-us-east-2-an --archive-prefix frankie/ingest/ --archive-class GLACIER --archive-after-days 30`
   -- adds AbortIncompleteMultipartUpload(7 d) + transition rule (objects > 128 KB). $0 to set; saves ~$170/mo per
   8.9 TB once objects age. Raw: `s3 PutBucketLifecycleConfiguration`. Needs Greg's class choice (f).
3. `--steps cw-agent`  -- `ssm PutParameter AmazonCloudWatch-frankie-box` + `ssm CreateAssociation
   AmazonCloudWatch-ManageAgent` targeting i-035994afa8bdf66a5 (installs/configures the agent, restarts it). ~$0.35/mo.
4. `--steps cw-alarms [--sns-topic-arn arn:aws:sns:us-east-1:568968024170:frankie-alarms]`  -- frankie-box-root-disk-85,
   frankie-box-archive-disk-85, frankie-box-mem-95, frankie-box-system-recover. $0.40/mo. Add `--idle-stop` ONLY
   after the HOLD/KeepRunning handshake is wired (the hold must call DisableAlarmActions). SNS topic creation is a
   separate manual go: `sns CreateTopic frankie-alarms` + `sns Subscribe --protocol email`. $0.
5. `--steps detailed-monitoring`  -- `ec2 MonitorInstances`. $2.10/mo. Only with `--idle-stop`.
6. `--steps compute-optimizer`  -- `compute-optimizer UpdateEnrollmentStatus Active` + `cost-optimization-hub
   UpdateEnrollmentStatus Active`. $0. Findings after 30 h of metrics.
7. `--steps launch-template --image-id ami-025d99823a4caad37 --instance-type r8id.8xlarge --root-gib 200 --scratch-volumes 0`
   -- creates `frankie-day-box` (IMDSv2, Ssm, monitoring, terminate-on-shutdown, NVMe/scratch stripe in user-data).
   $0 to create; instances launched from it are the fleet's cost (r8id.8xlarge $2.66112/h). Needs the golden AMI
   first (the lean second box, after its H-4 gate) and the 640-vCPU quota.
8. `--steps snapshot-archive --volume-id vol-004b68c077be09cc9`  -- `ec2 CreateSnapshot` then (next run, once
   `completed`) `ec2 ModifySnapshotTier archive`. $0.05/GB-mo Standard, $0.0125/GB-mo Archive (90-day minimum,
   24-72 h restore). Only if Greg prefers snapshots to S3 Glacier ($0.0036) for (f).
9. `--steps scheduler-stop --stop-cron "cron(0 6 * * ? *)" --scheduler-role-arn <role>`  -- EventBridge Scheduler
   stopping the box at 06:00 UTC daily. $0. Needs a role with ec2:StopInstances; conflicts with KeepRunning: opt-in.
10. Budgets: raise DavisAI-Monthly-Cost-Guard from $200 before the 30-day run month (console or `budgets
    UpdateBudget`); otherwise it alerts on day 1 of the fleet. $0.
11. Cost anomaly detection: `ce CreateAnomalyMonitor --monitor-type DIMENSIONAL --monitor-dimension SERVICE`. $0.
12. Region call (f): a us-east-1 archive bucket (or the clones in us-east-2) removes $0.01-0.02/GB cross-region
    transfer on ~8.9 TB of archives ($89-178) and lets every archive byte ride the free gateway endpoint.

## 6. Sources (official documentation read through the connector)
- EBS: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html (gp3 limits),
  https://docs.aws.amazon.com/ebs/latest/userguide/modify-volume-requirements.html (4 per 24 h, 6 h),
  https://docs.aws.amazon.com/ebs/latest/userguide/raid-config.html (RAID0 and the instance ceiling),
  https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive.html (Archive tier, full copy, 90 days),
  https://docs.aws.amazon.com/ebs/latest/userguide/ebs-fast-snapshot-restore.html,
  https://docs.aws.amazon.com/ebs/latest/userguide/initalize-volume.html (Provisioned Rate),
  https://aws.amazon.com/ebs/pricing/.
- EC2: https://docs.aws.amazon.com/ec2/latest/instancetypes/mo.html (r7i/r8i/r8id EBS ceilings),
  https://docs.aws.amazon.com/ec2/latest/instancetypes/so.html (i7i/i7ie/i4i),
  https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/hibernating-prerequisites.html (RAM < 150 GiB),
  https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html,
  https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-fleet-allocation-strategy.html,
  https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-cloudwatch-new.html (detailed monitoring).
- S3: https://aws.amazon.com/s3/pricing/ (Ohio classes and requests),
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-express-one-zone.html (AZ IDs),
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html,
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html (CRC64NVME, trailing),
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/mountpoint.html,
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops.html,
  https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html (gateway endpoints same-Region),
  https://aws.amazon.com/ec2/pricing/on-demand/ (data transfer between Regions),
  https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html (TransferConfig, preferred_transfer_client).
- Movement/FS: https://aws.amazon.com/datasync/pricing/, https://aws.amazon.com/fsx/lustre/pricing/,
  https://aws.amazon.com/efs/pricing/.
- SSM: https://aws.amazon.com/systems-manager/pricing/ (Run Command $0.002, Session Manager $0.05),
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-on-EC2-Instance-fleet.html
  (AmazonCloudWatch-ManageAgent), https://docs.aws.amazon.com/systems-manager/latest/userguide/state-manager.html.
- CloudWatch/EventBridge/Step Functions: https://aws.amazon.com/cloudwatch/pricing/,
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/UsingAlarmActions.html (EC2 actions; not for
  metric-math or composite), https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html,
  https://aws.amazon.com/eventbridge/pricing/ (Scheduler free tier),
  https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html,
  https://aws.amazon.com/step-functions/pricing/, https://docs.aws.amazon.com/step-functions/latest/dg/supported-services-awssdk.html.
- Batch/Athena/KMS: https://aws.amazon.com/batch/pricing/, https://aws.amazon.com/athena/pricing/, https://aws.amazon.com/kms/pricing/.
- Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html,
  https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html, https://aws.amazon.com/bedrock/pricing/.
- Cost: https://docs.aws.amazon.com/compute-optimizer/latest/ug/getting-started.html,
  https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html,
  https://aws.amazon.com/aws-cost-management/pricing/.

## 7. Digest rendering services (Greg's follow-up, 2026-10-08: "are you 100% sure there is no AWS render skill?")
SOURCE-BUILT / RUNTIME-UNVERIFIED; read-only research via the Aws connector (search_documentation agent_skills +
general, retrieve_skill, read_documentation). No account call, no change.

The job: ROOT's digest decodes the day's frames spool (JSON lines, 496.7 GB, ~1.47M lines of full-depth order-book
frames, ~338 KB per line) and renders tables into the Markdown digest, plus 46 smaller tables from the native ledgers
(193.7 GB). Measured: our Python decode runs 9.25 MB/s per core; one pass on the box = 29 min on 32 CPUs
(496.7 GB / (32 x 9.25 MB/s) = 28.0 min computed; the EBS read floor is 496.7 GB / 1.25 GB/s = 6.6 min, so the pass is
CPU-bound); five passes on c9bf631 = 2.4 h. Greg's rule: nothing dropped, full depth, stream it, many CPUs.

### 7.1 The registry answer
**No AWS agent skill covers rendering or aggregating large JSONL into tables or documents.** This follow-up ran 14
more agent_skills sweeps at 6-10 results each with the exact terms Greg named (athena, glue, ETL, spark, EMR,
emr-serverless, data processing, analytics, lake, batch, HPC, step functions map, bedrock data automation,
quicksight, opensearch, sagemaker processing, render, markdown, report, JSONL aggregation). Every name returned was
already in the 113 of section 1; nothing new appeared. The certainty is bounded by the tool: the registry exposes
ranked search, not a catalog listing, so the statement is "no skill matched 25+ relevant terms across two passes",
not an exhaustive enumeration.

What the sweeps return instead, and what each actually covers (read in full this pass: querying-data-lake,
ingesting-into-data-lake; read in pass 1: aws-step-functions, querying-aws-s3, querying-data-lake):
| skill_name | Scope | Fits the digest? |
|---|---|---|
| querying-data-lake | Athena SQL execution (workgroup, statement classification, cost report); output CSV, or UNLOAD/CTAS to Parquet/ORC/Avro/JSON | Aggregation only, to files, not to a document; the renderer would not be ours |
| ingesting-into-data-lake | Glue 5.x PySpark job templates, Athena CTAS, S3 JSON/CSV/Parquet -> Iceberg/S3 Tables; its own troubleshooting row: "CTAS timeout: dataset too large for Athena -> switch to Glue ETL or batch with WHERE filters" | Converts JSONL into a table; does not render |
| aws-step-functions | Distributed Map: up to 10,000 child workflows (1,000 default), ItemReader InputType JSONL supported; `.sync` integrations | Orchestrates a sharded render; the renderer is still ours |
| redshift-guide | Redshift COPY/UNLOAD, Spectrum external tables | Warehouse, not a renderer; not costed here |
| amazon-opensearch-service | Indexing JSON for search/log analytics, PPL, dashboards | Search index, not a document |
| querying-aws-s3 / querying-aws-cloudwatch / querying-aws-sagemaker-catalog | Athena over S3 Metadata, CloudWatch and SageMaker system tables | Metadata only |
| aws-transform | Code transformations at scale via Batch/Fargate | Code, not data |
Absent from the registry: EMR, EMR Serverless, a standalone Glue job-authoring skill, AWS Batch, QuickSight,
Bedrock Data Automation, SageMaker Processing, ParallelCluster. Bedrock Data Automation is PDF/TIFF/JPEG/PNG/DOCX,
images and video (500 MB max per request, 3,000 pages with the splitter): not applicable to JSONL at all.

### 7.2 The invariant that decides the comparison
The 9.25 MB/s per core is our CPython decode+render. Athena SQL replaces it (SQL aggregation, a different rendering
path); Glue, EMR Serverless, Athena Spark, Batch and Lambda would run OUR decoder as-is (PySpark UDF, container or
function) at the same 9.25 MB/s per core. So one pass costs **496.7 GB / 9.25 MB/s = 53,700 core-seconds = 14.9
core-hours** on every service that keeps the renderer, and the services differ only in (a) price per core-hour,
(b) how many cores run at once (wall time), (c) data staging, (d) whether the output is still the byte-identical
digest. The native ledgers (193.7 GB, 46 tables) are the same arithmetic at 0.39x: 5.8 core-hours per pass.

Staging for any S3-reading service: upload 496.7 GB from the box at the 1.25 GB/s EBS read ceiling (NIC 1.56 GB/s)
= 6.6 min; $0 in-Region to a us-east-1 bucket (the granite bucket exists; the gateway endpoint carries it), or
$4.97-9.94 cross-Region to the bento bucket ($0.01-0.02/GB); PUTs at 128 MiB parts = 3,790 requests = $0.02;
S3 Standard us-east-1 $0.023/GB-mo = $11.43/month for 496.7 GB ($0.38/day pro-rated). Every Athena row fits: the
32 MB practical row limit vs ~338 KB per frame line; JSON SerDe needs one record per line (true of the spool).

### 7.3 One pass over 496.7 GB, per service (prices us-east-1 list, read 2026-10-08)
| Option | Price basis | One pass: cost | One pass: wall time | Byte-identical digest? | Gate / limit |
|---|---|---|---|---|---|
| The box as is (r7i.8xlarge, 32 CPUs) | $2.1168/h | $1.02 (29 min) | 29 min measured; 2.4 h for five passes | YES (it is the renderer) | EBS floor 6.6 min; CPU-bound |
| Bigger EC2 for the step: r7i.16xlarge (64 vCPU) | $4.2336/h | $0.99 (14 min) | 14.0 min computed (EBS 2,500 MB/s floor 3.3 min) | YES, same code | second box exists, stopped (resized to 16xlarge) |
| Bigger EC2 for the step: r7i.48xlarge (192 vCPU) | $12.7008/h on-demand; Spot ~$3.2-3.8/h (0.25-0.30x, from the measured r7i.8xlarge Spot ratio) | $0.99 on-demand, $0.25-0.30 Spot (4.7 min compute) | 4.7 min compute + data staging: EBS Volume Clone of the spool volume (instant, same AZ) or S3 pull at 50 Gbps NIC (6.25 GB/s, ~80 s if S3 parallelism delivers it); EBS ceiling 5,000 MB/s = 1.7 min floor | YES, same code, hyperthread-aware pinning as today | 192 vCPUs against the 640-vCPU request (pending); Spot interruption costs one 5-min pass, nothing stateful |
| AWS Batch on a large instance | Batch $0; EC2 price as above | same as the EC2 row + 2-4 min instance start per job | same + start-up | YES if the container carries our renderer; NO cpuset/hyperthread pinning inside the container | no Batch skill; containers only |
| Step Functions Distributed Map + Lambda | 4,000 free transitions then $0.025/1,000; Lambda $0.0000166667/GB-s, 1 vCPU per 1,769 MB, 15 min max, 10,240 MB max | 14.9 core-h = 53,700 s x 1.769 GB = 94,990 GB-s = $1.58 + ~$0.02 requests | 1,000 children (default) x 0.5 GB each at 9.25 MB/s = 54 s per pass; 10,000 children = 5.4 s (quota) | YES only with a sharded renderer and a deterministic, order-preserving merge (the existing parallel digest table bdc05a62 is that pattern on the box); Lambda container image up to 10 GB holds the renderer | code work: shard + merge; S3 staging first |
| AWS Glue (Spark, our decoder as a PySpark UDF) | $0.44/DPU-h, 1 DPU = 4 vCPU/16 GB, 1-min minimum; G.8X = 32 vCPU, G.16X = 64 vCPU per worker | 3.73 DPU-h x $0.44 = $1.64 | 48 G.1X workers (192 vCPU) ~4.7 min + 1-2 min start | NO as SQL; YES only via the UDF route with a deterministic merge; Spark's own output ordering is not deterministic without an ORDER BY (single-node final sort) | S3 staging; a Glue job to write and keep |
| EMR Serverless (Spark) | $0.052624/vCPU-h + $0.0057785/GB-h, 1-min minimum; workers up to 32 vCPU/244 GB | 14.9 vCPU-h x $0.052624 = $0.78 + 59.6 GB-h (4 GB/vCPU) x $0.0057785 = $0.34 = $1.13 | ~4.7 min on 192 vCPU + ~1 min start | same as Glue (UDF route only) | **default quota 16 concurrent vCPUs per account** (adjustable; auto-raises with use): at 16 vCPU one pass = 56 min until the increase lands |
| Athena for Apache Spark | $0.35/DPU-h (4 vCPU per DPU) | 3.73 DPU-h x $0.35 = $1.30 | ~4.7 min on 48 DPU + session start | same as Glue | notebook/session model; S3 staging |
| Athena SQL (CTAS / UNLOAD) | $5/TB scanned, 10 MB minimum; DDL free; capacity reservations $0.30/DPU-h (min 24 DPU = $7.20/h) | $2.48 per pass over the uncompressed JSON, whatever the split | not published per TB; the DML timeout is 30 min and a 497 GB single-query JSON scan risks it, so split the spool into N objects and run parallel queries (20 concurrent DML default) | **NO**: SQL aggregation is a new rendering path; UNLOAD writes from parallel workers in non-deterministic order, SELECT output is one CSV; floats re-formatted; the Markdown is not produced | S3 staging; Glue table definition for the nested frame schema |
| Athena SQL after a one-time Parquet conversion | CTAS to Parquet (Snappy) $2.48 once; then scans read only the referenced columns | later per-query scans ~$0.25-0.50 (columnar, compressed; the 3:1 and column-subset savings AWS documents) | minutes per query | NO (same as above) | USE WHEN cross-day SQL questions are asked of archived spools |
| Redshift Serverless / OpenSearch | not costed | - | - | NO | out of scope for a render |
| Bedrock Data Automation | per page/image/minute | - | - | - | NOT APPLICABLE: documents/images/video only |

### 7.4 Verdicts
- **USE NOW: a bigger EC2 for the digest step, same renderer.** r7i.16xlarge (exists, stopped): one pass 14 min,
  $0.99; r7i.48xlarge: one pass ~5 min, $1.06 on-demand ($0.25-0.30 Spot; a stateless pass can take Spot). Five
  passes: 70 min on the 16xlarge, ~25 min on the 48xlarge, versus 2.4 h today. Byte-identical by construction. Data
  reaches it by EBS Volume Clone (instant, us-east-1d) without an S3 round-trip. Launch via the launch-template step
  (`--instance-type r7i.48xlarge`); needs the vCPU quota (640 requested) and Greg's go.
- **USE WHEN the five passes must be minutes, not tens of minutes: Step Functions Distributed Map + Lambda** with a
  sharded renderer and a deterministic merge. $1.58 per pass, 54 s per pass at 1,000-way (the default), after a 6.6-min
  one-time S3 staging per day. It is the box's existing parallel-digest-table pattern at 30x the width; the merge must
  be proven byte-exact by parse-back before it replaces anything (Greg's lossless rule).
- **USE WHEN cross-day SQL is wanted over archived spools: Athena after one CTAS to Parquet** ($2.48 once per day's
  spool, cents per later query). Not a digest; a second way to ask questions of the same bytes. Pairs with S3 Glacier
  restores of archived days.
- **NOT APPLICABLE for the digest itself: Athena SQL, Glue, EMR Serverless, Athena Spark, AWS Batch, OpenSearch,
  Redshift, Bedrock Data Automation.** The SQL engines produce a new digest form with non-deterministic ordering and
  re-formatted values; the Spark engines only reach our decoder as a UDF at the same 9.25 MB/s per core, so they buy
  nothing over EC2 cores at $0.076-0.11 per vCPU-hour versus EC2's $0.066 on-demand / ~$0.018 Spot, and they add S3
  staging; EMR Serverless additionally starts at a 16-vCPU account quota; Batch loses CPU pinning.
- **The lever none of the services move: the 9.25 MB/s per core decode.** Every option above scales cores; only the
  decoder's own speed changes the 14.9 core-hours per pass. That is a code item (parser choice, pass fusion of the
  five passes into one streaming pass), not an AWS one, and it multiplies whatever AWS width is chosen.

### 7.5 The single best stack for "the digest in minutes with nothing dropped"
1. Fuse the five passes into as few streaming passes as the renderer allows (code; 2.4 h -> 29 min on the box alone).
2. Run the digest step on a burst box: r7i.48xlarge from the `frankie-day-box` launch template, Spot allowed for this
   stateless step, the spool reached by EBS Volume Clone (instant) or the archive's CRT pull; 192 cores, hyperthread
   map applied -> ~5 min per pass, $1.06 on-demand / $0.30 Spot; terminate on completion. Byte-identical digest.
3. Stack the width further only through Distributed Map + Lambda (54 s per pass, $1.58) once a sharded renderer with a
   parse-back-proven merge exists; the same shards also run on the box's 32 CPUs today.
4. Keep Athena + Parquet as the cross-day question engine over archived spools ($2.48 one-time per day), never as the
   digest.
Cost of the stack per day: ~$1-6 of burst compute for all passes + $0.38/day of S3 Standard if staged + $0 Step
Functions (inside the free tier) -- against the 2.4 h of main-box time ($5.08) it replaces.

### 7.6 Sources for section 7
https://aws.amazon.com/athena/pricing/ ($5/TB, 10 MB min, $0.30/DPU-h reservations, $0.35/DPU-h Spark);
https://repost.aws/knowledge-center/athena-service-quota-errors (30-min DML timeout, 262,144-byte query string);
https://docs.aws.amazon.com/athena/latest/ug/data-types-considerations.html (32 MB per row);
https://docs.aws.amazon.com/athena/latest/ug/unload.html and
https://docs.aws.amazon.com/athena/latest/ug/performance-tuning-query-optimization-techniques.html (UNLOAD parallel
writers; SELECT = one uncompressed CSV); https://aws.amazon.com/glue/pricing/ ($0.44/DPU-h);
https://aws.amazon.com/blogs/big-data/scale-your-aws-glue-for-apache-spark-jobs-with-r-type-g-12x-and-g-16x-workers/
(worker sizes); https://aws.amazon.com/emr/pricing/ ($0.052624/vCPU-h, $0.0057785/GB-h);
https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/app-behavior.html (worker sizes to 32 vCPU/244 GB);
https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/endpoints-quotas.html (16 concurrent vCPU default);
https://docs.aws.amazon.com/help-panel/step-functions/latest/console/map-max-concurrency-dist.html (1,000 default,
10,000 max); https://aws.amazon.com/blogs/compute/introducing-jsonl-support-with-step-functions-distributed-map/
(JSONL ItemReader); https://aws.amazon.com/bedrock/faqs/ and https://docs.aws.amazon.com/bedrock/latest/userguide/bda-limits.html
(BDA modalities and limits); https://aws.amazon.com/lambda/pricing/ (GB-s rate, from pass-1 reading).
