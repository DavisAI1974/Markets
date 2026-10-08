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
