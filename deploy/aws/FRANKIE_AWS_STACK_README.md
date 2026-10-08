# frankie_aws_stack.py -- the Frankie account stack (SOURCE-BUILT / RUNTIME-UNVERIFIED, 2026-10-08)

Research and every number: `research/kalshi/frankie_boss/AWS_TOOLS_STACK_20261008.md`.

## What it is
One boto3 script, ten idempotent steps, dry-run by default. Every step reads the account first (Describe/Get/List),
compares with what it wants, and either reports `present` or plans the exact write calls. Nothing is written unless
`--apply --confirm GREG_GO_AWS_STACK` is given. One JSON receipt per step lands in `--receipt-dir`
(default `./aws_stack_receipts/`), schema `FRANKIE_AWS_STACK_V1`:
`step, status (planned | present | applied | needs_input | refused), actions [service, region, operation, params],
checked, cost, reason, mode`.

Run from a shell holding the Claude IAM credentials (the box via SSM, or a session with `~/.config/markets/env`).
The script touches no box module; it only calls AWS APIs.

## Steps, in run order, with cost
| Step | Writes it plans | Cost |
|---|---|---|
| ebs-status | none (read-only: volumes + modification state, the 4-per-24 h / ~6 h-per-TiB rule) | $0 |
| s3-gateway-endpoint | CreateVpcEndpoint only if the S3 gateway endpoint is missing from the box's VPC (vpce-0472311a451e2cedf exists) | $0 |
| s3-lifecycle | PutBucketLifecycleConfiguration: abort incomplete multipart uploads after 7 d (always) + a prefix transition when `--archive-class` is given; existing rules kept by ID | $0 to set; Glacier Flexible $0.0036/GB-mo, Deep Archive $0.00099, GIR $0.004 |
| cw-agent | PutParameter `AmazonCloudWatch-frankie-box` + CreateAssociation `AmazonCloudWatch-ManageAgent` (configure, restart, daily re-apply) | ~$0.35/mo |
| cw-alarms | PutMetricAlarm: root disk 85%, archive disk 85%, mem 95%, StatusCheckFailed_System -> ec2:recover; `--idle-stop` adds CPU < 2% for 60 min -> ec2:stop | $0.10/alarm-mo ($0.40-0.50) |
| detailed-monitoring | MonitorInstances (1-min EC2 metrics) | $2.10/instance-mo |
| scheduler-stop | CreateSchedule (EventBridge Scheduler, universal target ec2:stopInstances); needs `--stop-cron` and `--scheduler-role-arn` | $0 |
| launch-template | CreateLaunchTemplate `frankie-day-box` (IMDSv2, profile Ssm, monitoring, terminate-on-shutdown, root gp3 + optional scratch gp3 volumes, user-data stripes NVMe/scratch into /mnt/scratch); needs `--image-id` | $0; instances cost the type price |
| compute-optimizer | UpdateEnrollmentStatus Active for Compute Optimizer and Cost Optimization Hub | $0 |
| snapshot-archive | CreateSnapshot of the archive volume; with `--archive-tier` on a later run, ModifySnapshotTier archive once completed | $0.05/GB-mo; Archive $0.0125/GB-mo, 90-day minimum |

## The idle-stop alarm and the HOLD
`--idle-stop` is opt-in on purpose. CloudWatch cannot read the `KeepRunning` tag or the queue's HOLD. Before the
alarm goes live, the hold path must call `cloudwatch DisableAlarmActions --alarm-names frankie-box-cpu-idle-stop`
and the release path `EnableAlarmActions`; until then the existing runner-side idle guard stays the only guard.
`TreatMissingData=notBreaching` keeps a stopped box from re-triggering.

## Examples
```
python3 deploy/aws/frankie_aws_stack.py                                   # plan everything, write receipts
python3 deploy/aws/frankie_aws_stack.py --steps ebs-status,cw-agent,cw-alarms
python3 deploy/aws/frankie_aws_stack.py --steps s3-lifecycle --archive-class GLACIER --archive-after-days 30
python3 deploy/aws/frankie_aws_stack.py --steps cw-agent,cw-alarms --apply --confirm GREG_GO_AWS_STACK
python3 deploy/aws/frankie_aws_stack.py --steps launch-template --image-id ami-xxxx --instance-type r8id.8xlarge
```

## Verification done here
`python3 -m py_compile`, `ast.parse`, `--help`, and a dry run with a fake account (the scratchpad toy test); no AWS
call was made from this session. Each step's write calls are recorded on its receipt before they run, so an apply
run leaves the exact call list even if a later call fails.

## Fleet steps (session 8, added slice f) and the review's NITs
- Steps: `day-box-role` (the fleet boxes' IAM role + instance profile; apply as root), `golden-ami` (image a CLEAN
  stopped staged box; refuses a root over --max-root-gib), `launch-template` (`frankie-day-box`: r7i.16xlarge, IMDSv2,
  Ssm, KeepRunning=true, the account CMK, user-data that PREPARES the box + installs the reboot-resume unit; it needs
  `--run` or `--fleet-day-list` to form the day-list location and the `frankie-day-box` instance profile to exist),
  `fleet-launch` (`--days`/`--count`/`--spot`; refuses over-quota, a day overflow, `--spot` for day boxes without
  `--allow-spot-days`, and a day-list prefix outside `fleet/` without `--allow-any-prefix`; pins the template version).
- N5: a full-stack `--apply` stops at `launch-template` with needs_input when `--run`/`--fleet-day-list` is absent --
  that is intentional and loud; pass them (or run only the earlier steps).
- N4: the fleet user-data assumes `git` and the `aws` CLI are on the golden AMI (it installs nothing); the clone is
  `--depth 1` (not a full-history clone).
- Fresh day-start is driven per instance by `frankie_box_run.yml` (stage + start with the full dispatch set + the
  presign); the user-data only prepares the box and resumes its saved days on each boot (review B1).
