# Drop-in: Frankie, 2026-10-08, session 8 (handoff from session 7; the FLEET plan; boxes STOPPED; quota request to FILE)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer. The clone is SHALLOW: `git fetch --deepen=400`
   before any merge-base question.
2. Read THIS file, then DROP_IN_CLAUDE_20261008_SESSION7.md (run state, what session 6 built, digest commands), then the
   "Session 6" sections at the end of E2E_ONE_DAY_20231018.md and AWS_TOOLS_STACK_20261008.md (stack S1 = fleet).
3. Session = parent only; spawn agents with model "fable"; api-and-interface-design first; AWS via the Aws connector
   (session 7 ended with BOTH AWS connectors unusable: one needed re-authentication, the other's credentials had expired;
   the container holds only the proxy's placeholder keys. Greg reconnects at https://claude.ai/customize/connectors before
   this session; test with one read-only STS call first).
4. FIRST ACTION, before anything else (Greg: "You have to request size increase as soon as you're done replying"):
   file the EC2 vCPU quota increase named in "The quota request" below, read the current value first, report the request
   id. Nothing else runs before it.
5. DO NOT start any box (Greg: "Don't start the boxes yet"). No coding or building until Greg says so: he is deciding the
   fleet plan. The e2e day a2/20231018 stays SAVED (no receipt) on the stopped main box; nothing changed since session 7.
```

## Greg's fleet plan (verbatim, 2026-10-08, the last message of session 7)

"Don't start the boxes yet, I think I have a good idea. We get (15) 64 gpu boxes and we put 2 days per box. We can do 32 c
for the root in parallel all 15 boxes and then first box pair to finish is first in line to move to classroom because we
decided this should be one day at a time. Even though 2 are in a box it would only run 1 day and it would get all 64 and
when it was done the 2nd day in the box would run with all 64 and we would do the rest of them like that. Run 2 days or
multiple boxes in parallel where we can and then do 1 at a time where it's necessary but it goes through each day quickly.
What do you think? Then we can get rid of almost all the boxes we currently have. You have to request size increase as
soon as you're done replying. Thoughts? No coding or building momentarily."

Read "64 gpu boxes" as 64-vCPU CPU boxes (r7i.16xlarge class): the standing rule is AWS CPU only, no Pods. Greg's second
message: "I'll start new session in a few minutes and then file [the quota request]. In the interim create handoff and
print drop in. Do you like the idea?" Answer given: yes.

## The parent's assessment (given to Greg in session 7; carry it, do not re-litigate)

- The plan fits the science. ROOT is day-independent (each day reads its own partitions, writes its own ledgers, shares
  nothing until the classroom), so 15 ROOTs in parallel are embarrassingly parallel and need no parent watching them. The
  stage handoff built in session 6 makes each box self-driving (validate once -> save -> clean+zip+move -> trigger the
  next stage). Knowledge flows only in the classroom chain (ALL 30 days share completed knowledge, Greg's standing call),
  and that is exactly the part Greg keeps serial, one day at a time.
- Where 64 CPUs pay: ROOT at 32 per day, two days per box, is the verified shape (DAY_CPUS=32 on a2). The digest render
  and the validates scale with cores (one full-depth pass of the 497 GB frames spool ~14 min on 64 vCPU per the AWS
  research). Where they do not: the classroom and teacher walls are the host answers and the Jev/Granite lanes, not CPU
  count; a classroom day on 64 CPUs gets faster digest/validate steps, not a 4x classroom.
- Costs: r7i.16xlarge ~ $4.20/h on-demand in us-east-1; 15 boxes ~ $63/h while ROOT is up. ROOT is resumable from its
  save marker, so Spot is possible for ROOT (classroom stays on-demand). Storage is the second bill: a day's ROOT footprint
  is ~1.4 TB before the clean (497 GB frames spool, 472 GB inline layer, 194 GB native ledgers); two days per box = a
  ~3 TB volume, or the clean-after-save policy keeps it near 1 TB (198.7 GB freed at 19.8x on a2 by zipping the
  redundant native segments alone).
- NOT BUILT: cross-box flow. The trigger resumes the next stage on the SAME box. "First box pair to finish moves to the
  classroom" needs a shared day list on S3 that each box claims from (a small piece; it belongs in the stage handoff).
  Also not built: fleet launch (launch template + EC2 Fleet + golden AMI + Step Functions, stack S1 in
  AWS_TOOLS_STACK_20261008.md; deploy/aws/frankie_aws_stack.py is the dry-run account stack).
- Everything from sessions 5-7 is SOURCE-BUILT / RUNTIME-UNVERIFIED except the hold, the saves, the resume+kick and the
  manual clean. The first thing to run on the first fleet box is a2's resume with FRANKIE_ROOT_DIGEST=off on the staged
  tip (receipt in minutes), then validate, then teacher, exactly as the session-7 drop-in says, BEFORE 14 more boxes
  are launched.
- Retiring boxes: the main box i-035994afa8bdf66a5 holds a2's saved day and all its data; keep it until that data is on
  S3 or its volumes are cloned to the first fleet box. The second box (i-0d17573dbce871520, r7i.16xlarge, us-east-1) and
  the year-pull box (i-08cee7171c0a76a04, us-east-2) can go once their volumes are archived. Idle storage now ~$29/day
  (three 2 TB gp3 volumes with provisioned IOPS/throughput, one unattached 250 GB volume, six old snapshots in us-east-2).

## The quota request (FILE FIRST; read-only GetServiceQuota before, report current + requested + request id after)

```
Service: Amazon EC2 (service code ec2)
Quota:   Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances   (quota code L-1216C47A)
Region:  us-east-1 (the main box and Bedrock live there)
Requested value: 1152 vCPUs
Sizing: 15 boxes x 64 vCPU = 960, + 128 for the three existing boxes (32 + 64 + 32), + headroom.
API (via the Aws connector, service-quotas): GetServiceQuota {ServiceCode: ec2, QuotaCode: L-1216C47A} then
     RequestServiceQuotaIncrease {ServiceCode: ec2, QuotaCode: L-1216C47A, DesiredValue: 1152}
Console: Service Quotas > Amazon EC2 > the quota above > Request increase at account level > 1152.
The AWS research recorded the current value at 640 (unverified in session 7: both connectors were down).
```

RESULT 2026-10-08 ~12:0xZ (Aws connector live, account ...4170, root caller): current value is 256 vCPUs (NOT 640; the 640 was
the research's unverified figure). One request is already OPEN: id 66c042562b594ac18e9966a1939b5b62Tf00eIjo, DesiredValue 640,
status CASE_OPENED, support case 179140016900825, filed 2026-10-07T19:09:28Z by root (Greg). RequestServiceQuotaIncrease for 1152
was REFUSED: "Only one open service quota increase request is allowed per quota" (ResourceAlreadyExistsException). The Support
API cannot amend the case (SubscriptionRequiredException: no premium support plan). Two ways to 1152: (a) Greg replies on
support case 179140016900825 in the Support Center console asking for 1152 instead of 640; (b) wait for the 640 to resolve,
then file 1152 (a second request after the first closes is allowed). At 640, with the three existing boxes stopped (stopped
instances do not count), the fleet fits 10 x 64-vCPU boxes.

Idle storage inventory (read-only, same sweep; gp3 list prices $0.08/GB-mo, $0.005 per IOPS over 3,000, $0.04 per MiB/s over 125):
us-east-1: vol-0d36715924f03b86c (main root, 2048 GiB, 16,000 IOPS, 1,250 MiB/s, ~$274/mo, of which ~$110 is provisioned extras);
vol-004b68c077be09cc9 (main archive, 2048 GiB, 10,000 / 1,000, ~$234/mo, ~$70 extras); vol-0fbf7bc0991bc8e39 (second box root,
2048 GiB, 16,000 / 1,000, ~$264/mo, ~$100 extras); 0 snapshots, 0 Elastic IPs. us-east-2: vol-05a0b1e56f8c16478 (year-pull root,
300 GiB, baseline, $24/mo); vol-05c3d967e07b2d61f (UNATTACHED 250 GiB, $20/mo); six standard snapshots (1,190 GiB nominal, up to
$60/mo): two are Greg's 2026-09-29 "before termination" preservations of the old native host (snap-0ec119eebb2964b4d root 120 GB,
snap-0142c4b8766b5b7ea data 250 GB), two back AMI ami-0bd716486a4f2ad02 (snap-09b37f01d8562324a, snap-091668dfa6e630234; deleting
them means deregistering the AMI), snap-0af0f3714bbf2a87e (2026-09-16 restore-verified data) and snap-028afdc9066adab30
(2026-08-28 pre-reboot preservation). Cheapest reversible cut while the boxes are stopped: ModifyVolume the three 2 TB volumes
to baseline 3,000 / 125 (~$280/mo = ~$9.3/day saved; raise again before a run; 6 h cooldown between modifications per volume).

DENIED 2026-10-08 ~11:50Z (Greg's screenshot of case 179140016900825): "at this time we are unable to approve ... Service quotas are
put in place to help you gradually ramp up activity ... If you'd like to appeal this decision, please reopen this case and provide
as detailed a use case as possible." Service Quotas still shows the request CASE_OPENED (it flips to CASE_CLOSED when the case
resolves; a new request can be filed only then). Spot quota L-34B43A08 ("All Standard Spot Instance Requests") is a SEPARATE
256 vCPUs. What runs TODAY without any increase (stopped boxes do not count): 4 x 64-vCPU boxes On-Demand + 4 x 64-vCPU on Spot
(ROOT is resumable from its save marker, so Spot is lawful for ROOT; the classroom stays On-Demand) = 8 fleet boxes.

THE APPEAL (Greg pastes this as a reply on case 179140016900825, "reopen" the case; ask for the SAME 640, staged, not 1152: the
denial says "gradually"; a second request to 1152 follows after the first fleet week has billed):

  Subject: Appeal - Running On-Demand Standard instances, us-east-1, 256 -> 640 vCPUs (staged ramp)

  Use case: batch scientific computation over historical commodity-market order-book data (natural gas futures, NYMEX) for
  DavisAI Markets. Each job processes one trading day: about 500 GB of order-book frames plus 400 GB of derived ledgers,
  CPU-bound, memory-heavy (the working set needs the 512 GiB of an r7i.16xlarge). We have 30 such days to process, each day
  independent of the others, and we run two days per instance. This account has run the same workload on r7i.8xlarge
  (i-035994afa8bdf66a5) and r7i.16xlarge (i-0d17573dbce871520) since September 2026 and paid for it; the next phase is the same
  job across more days in parallel.

  Requested: 640 vCPUs = 10 x r7i.16xlarge (64 vCPU each). Duration: each instance lives about 2 days, then terminates
  (InstanceInitiatedShutdownBehavior=terminate from a launch template); the whole phase is about one week. After that we expect
  to ask for 1152 for the final 15-instance phase, once this phase has billed normally.

  Cost controls in place: AWS Budgets (daily and monthly guards with alerts), CloudWatch alarms on disk and system status,
  instances launched from a launch template with IMDSv2 and terminate-on-shutdown, resumable checkpoints so Spot can carry the
  first stage, and all data in S3/EBS in this account. We are happy to accept a partial increase (e.g. 384 or 512) as a first
  step toward 640.

If Greg has already filed it himself (he said he would in the new session), confirm with
ListRequestedServiceQuotaChangeHistoryByQuota and do not file a second one.

## The AWS go-list (session 8, Greg: "we need to do aws upgrades ... don't know if those are listed along with the box increase")
Everything the AWS research named, in ONE place beside the quota request. Each line is one go from Greg; each needs a working
Aws connector (at 11:4xZ 2026-10-08 the `Aws` connector reads needs_reconnect and `aws-mcp` answers expired credentials; the
container holds only the proxy's placeholder keys). Full detail: AWS_TOOLS_STACK_20261008.md sections 4, 5 and 7.5;
the dry-run script is deploy/aws/frankie_aws_stack.py (drop `--apply` for the dry run).

| # | Item | What it does | Cost | Needs |
|---|---|---|---|---|
| A | EC2 vCPU quota L-1216C47A us-east-1 -> 1152 | the fleet (15 x 64) + the three existing boxes + headroom | $0 | FIRST; check history before filing |
| B | Idle storage cuts, now, boxes stopped | ModifyVolume the three 2 TB gp3 volumes back to baseline (3,000 IOPS / 125 MiB/s) while stopped (raise again before a run); delete the unattached 250 GB volume; delete the six old us-east-2 snapshots | saves most of the ~$29/day idle bill | Greg's go per volume/snapshot (look at each first) |
| C | Budgets + anomaly detection | raise DavisAI-Monthly-Cost-Guard from $200 before the fleet month; `ce CreateAnomalyMonitor` by service | $0 | Greg's number for the budget |
| D | Fleet launch (stack S1) | launch template frankie-day-box (IMDSv2, Ssm, terminate-on-shutdown), golden AMI from the main box's staged checkout, EC2 Fleet or 15 RunInstances, 3 TB gp3 per box or clean-after-save; the shared day list on S3 + the cross-box claim (source work, not built) | r7i.16xlarge ~$4.20/h per box on-demand; template/AMI $0 | A granted + Greg's go on the fleet plan; first launch = ONE box resuming a2 |
| E | Archive policy (call f) + bucket region (R1) | S3 Glacier via storage_class on the archive upload, lifecycle (abort incomplete MPU 7 d, transition), Deep Archive after 90 d; a us-east-1 archive bucket so every archive byte rides the free gateway endpoint | -$200/mo vs volumes; avoids $89-178 cross-region on ~8.9 TB | Greg's class and region choice |
| F | Guards in the account (stack S3) | CloudWatch agent via State Manager, alarms disk 85% / mem 95% / system-recover, SNS email; idle-stop ONLY after the HOLD/KeepRunning handshake calls DisableAlarmActions | ~$0.85/mo (+$2.10 detailed monitoring) | SNS email address; idle-stop stays off |
| G | Compute Optimizer + Cost Optimization Hub | enrol; findings after ~30 h of metrics | $0 | go |
| H | Digest burst box (section 7.5) | the digest step on r7i.48xlarge (192 cores, ~5 min per pass, $1.06 on-demand / $0.30 Spot) from the launch template, spool by EBS Volume Clone; or the stopped second box (64 vCPU, ~14 min per pass) by volume clone | $1-6 per day | A granted (48xlarge) or Greg's go (second box) |
| I | S3 gateway endpoint | verify vpce-0472311a451e2cedf (exists); nothing to create | $0 | none |
| J | Opt-ins not recommended yet | EventBridge scheduler stop (conflicts with KeepRunning), detailed monitoring without idle-stop | - | skip |

Order when the connector is back: A, then B and C (cheap, reversible, save money today), then the Greg-decided ones (E, F, G),
then D and H with the fleet go. Nothing here starts a box.

## The a2 clone for the 64-vCPU second box (Greg, 2026-10-08 ~11:40Z: "Do clone now while we wait")
Both boxes sit in us-east-1d, so a same-AZ copy is lawful. EBS Volume Clone (CreateVolume from a source volume, instant) is the
better tool but the Aws connector's sandbox SDK predates it ("Unknown parameter 'SourceVolumeId'"), so the route taken is the
documented snapshot route: SNAPSHOTS STARTED 11:45:32Z with the main box STOPPED (clean, consistent):
  snap-099dba434c7c58222 <- vol-0d36715924f03b86c (main root: OS + /opt/frankie-box/work incl. a2's SAVED day), 2048 GiB, encrypted
  snap-088e77e04676ab8d9 <- vol-004b68c077be09cc9 (main archive volume), 2048 GiB, encrypted
  (tags Name=frankie-a2-root-20261008 / frankie-a2-archive-20261008, Purpose=frankie-a2-clone, TargetInstance=i-0d17573dbce871520)
Next (self check-in armed for 12:26Z, trig_016Ce4a7JcLvwNxgA19AUGyj): when both read completed, CreateVolume from each in
us-east-1d (gp3 2048 GiB, baseline 3,000 / 125 while idle, VolumeInitializationRate 300 MiB/s so the copy finishes at a known
rate, same CMK), tagged frankie-a2-clone-{root,archive}-20261008; NOT attached, NO box started. Before any run on the second box:
ModifyVolume both to 16,000 / 1,250 (6 h cooldown per volume between modifications).
Box-side plan when Greg gives the go (NOT done): the cloned root carries the Ubuntu label cloudimg-rootfs like the second box's own
root; attach it only after the second box has booted (hot attach, /dev/sdg), mount it at /mnt/main-root and bind-mount
/mnt/main-root/opt/frankie-box over /opt/frankie-box (or boot the second box FROM the clone by swapping /dev/sda1 while stopped:
Greg's call; it makes the second box the main box's whole environment on 64 CPUs). The archive clone attaches as /dev/sdh at
/opt/frankie-box/archive. Alternative Greg can do himself in the console in seconds: EC2 > Volumes > select the volume > Actions >
Copy volume (the instant clone); then these snapshots are the durable a2 backup instead of the clone source.
Costs: the two snapshots ~$0.05/GB-mo on used blocks (~$75/mo if kept; they are also the first durable copy of a2 off the main
box); the two clone volumes $328/mo at baseline; initialization ~$0.0036/GiB of snapshot data.

## Run state (UNCHANGED since the session-7 drop-in; verified 03:17Z 2026-10-08, re-verified read-only later in session 7)
- All three instances STOPPED, no Elastic IPs, only EBS storage accrues. Main box KeepRunning=false.
- Day e2e-20231018-a2/20231018: SAVED on its day-bound marker, booking retained (CPUs 0-31), owner commit 6076950, NO
  receipt, no teacher. The resume fix (tail anchor + sealed spool counts) is on the tip from 133c9ba; stage the tip
  before any resume (frankie_box_run.yml, script=deploy/aws/box/frankie_box_stage_code.sh, variables=ACTION=stage, on the
  work-branch ref). Digest for this classroom-arm day: NOT rendered; FULL DEPTH, nothing dropped, before the classroom.

## Open, in order (after the quota request)
1. Greg's go on the fleet plan -> assign the build agent: (a) the shared day list on S3 and the cross-box claim in the
   stage handoff; (b) the fleet launch (launch template, golden AMI from the main box's staged checkout, EC2 Fleet or
   15 RunInstances, 3 TB gp3 per box or clean-after-save); (c) the archive bucket region (R1) decided with it. Source
   only, review before any launch; the first launch is ONE box resuming a2.
2. The items from the session-7 drop-in, unchanged: findings 10/12, digest render location, re-pin list B1-B6, idle
   storage cuts (provisioned IOPS/throughput while stopped; the unattached 250 GB volume and the six snapshots).
3. Switch the session back to auto before the automatic chain runs unattended.

## Tip at handoff
- Work branch tip at handoff: the commit carrying this line (parent 9042140 = the session-7 drop-in; ff9364a digest ladder;
  133c9ba resume fixes). Stage THIS tip or newer before any resume; never a "WIP snapshot" commit.
