# AWS account upgrades applied - session 8, 2026-10-08 (via the Aws connector, account 568968024170, foreground by the parent)

Greg's go: "aws upgrades first so we don't have box runtime while it waits." Done in the parent session after two background
agents were lost to container resumes. No instance started, resized, stopped or terminated; no volume or snapshot touched;
no IAM, no quota request (Greg's 512 appeal is on support case 179140016900825); no email subscribed to SNS.

## Applied and read-back verified (~14:1xZ)
| Item | Call | Result | Monthly cost | Undo |
|---|---|---|---|---|
| Compute Optimizer | compute-optimizer UpdateEnrollmentStatus Active | status Active | $0 | UpdateEnrollmentStatus Inactive |
| Cost Optimization Hub | cost-optimization-hub UpdateEnrollmentStatus Active | Active | $0 | UpdateEnrollmentStatus Inactive |
| Monthly budget | budgets UpdateBudget DavisAI-Monthly-Cost-Guard 200 -> 3000 USD | BudgetLimit 3000.0 USD (was 200.0) | $0 | UpdateBudget back to 200 after the fleet month |
| Cost anomaly | ce CreateAnomalySubscription frankie-anomaly-20usd on the existing Default-Services-Monitor (SERVICE), SNS, IMMEDIATE, ANOMALY_TOTAL_IMPACT_ABSOLUTE >= 20 | subscription ...342d8695 | $0 | DeleteAnomalySubscription |
| SNS topic | sns CreateTopic frankie-alarms + policy (cloudwatch + costalerts publish) | arn:aws:sns:us-east-1:568968024170:frankie-alarms | $0 | DeleteTopic |
| CW agent config | ssm PutParameter AmazonCloudWatch-frankie-box (disk / and /opt/frankie-box/archive, mem, 60s) | version 1 | ~$0 | DeleteParameter |
| CW agent install | ssm CreateAssociation frankie-cw-agent (AmazonCloudWatch-ManageAgent, target tag Project=frankie, rate 30 min) | id 2df12036-8605-4fb4-b425-0a41051cae06 | ~$0 | DeleteAssociation |
| System-recover alarm | cloudwatch PutMetricAlarm frankie-box-system-recover (AWS/EC2 StatusCheckFailed_System, InstanceId i-035994afa8bdf66a5, notBreaching, SNS action) | created NOTIFY-ONLY | $0.10 | DeleteAlarms |
| Archive bucket | s3 CreateBucket frankie-archive-568968024170-us-east-1 + public-access-block all + SSE-S3 + tag Project=frankie | created | storage only | DeleteBucket when empty |
| Archive lifecycle | s3 PutBucketLifecycleConfiguration (abort incomplete MPU 7d; prefix frankie/ingest/ -> GLACIER 30d -> DEEP_ARCHIVE 120d) | rules abort-incomplete-mpu, frankie-ingest-archive | - | delete rules |
| Bento lifecycle | same two rules on bento-568968024170-us-east-2-an (us-east-2) | rules present (had none) | - | delete rules |
| S3 gateway endpoint | verified vpce-0472311a451e2cedf com.amazonaws.us-east-1.s3 available on rtb-095aab35cdfc7ec27 | nothing created | $0 | n/a |

## Refused / deferred (honest)
- ce CreateAnomalyMonitor frankie-anomaly REFUSED "Limit exceeded on dimensional spend monitor creation": the account already
  holds its one dimensional monitor (Default-Services-Monitor, SERVICE). The $20 subscription was attached to that existing
  monitor instead, which covers the same services. No loss.
- ce UpdateCostAllocationTagsStatus Project=Active REFUSED "Tag keys not found: Project": billing has not yet ingested the
  Project tag (set 12:0xZ; up to 24 h). DEFERRED to a check-in; retry daily until Active.
- The system-recover alarm's EC2 'Recover' action was REFUSED while the box is STOPPED ("not valid for the associated
  instance"). Created NOTIFY-ONLY. ADD arn:aws:automate:us-east-1:ec2:recover to its AlarmActions once the box is running.
- Disk-85 / archive-disk-85 / mem-95 alarms NOT created: a CWAgent metric alarm needs the agent's exact dimensions
  (InstanceId, path, device, fstype) which do not exist until the box boots and the agent (installed by the association
  above) reports once. CREATE THEM after first boot, reading the real dimensions from cloudwatch ListMetrics
  --namespace CWAgent. Recipe: used_percent >= 85 for / and /opt/frankie-box/archive; mem_used_percent >= 95; period 300,
  2 periods, TreatMissingData notBreaching, SNS action the frankie-alarms topic.

## Open for Greg
- SNS email: no subscriber on frankie-alarms. To get the alerts, sns Subscribe --protocol email <address> then confirm the mail.
- The anomaly subscription also publishes to SNS, so the same email covers it.
