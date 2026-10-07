# Box sizing, 2026-10-07 night (box-sizing agent, Greg's go)

Main box `i-035994afa8bdf66a5` was not touched: no stop, start, tag or resize, and no image was made from it. It is still
`running` as r7i.8xlarge (32 vCPU; NOT 16xlarge), with root 2048 GiB gp3 16000/1000. Nothing was installed on any box.

## Part 1: second box expanded (DONE)

`i-0d17573dbce871520` (us-east-1d, Ubuntu, `frankie-linux-r7i4xl`; the Name tag is now stale):

- Type: r7i.4xlarge became **r7i.16xlarge** (64 vCPU, 512 GiB, 4 lanes). The quota allowed it.
- Root `vol-0fbf7bc0991bc8e39`: 120 GiB gp3 3000/125 became **2048 GiB gp3, 16000 IOPS, 1000 MB/s**. 2048 was chosen because
  it is the main box's exact size. The modification state is `optimizing`; the full size is already usable.
- Partition and filesystem: cloud-init grew them at boot. `growpart` reported NOCHANGE, and `resize2fs` (ext4) had
  nothing left to do.
- Verified over SSM: `df -hT /` = ext4 2.0T, 97G used, 1.9T free (2,025,398,300,672 bytes available); `nproc` = 64;
  `free -g` total = 495. SSM status: Online, agent 3.3.4793.0. Instance profile `Ssm` is still attached.
- End state: KeepRunning=false (with a reason), **stopped**.

Account calls (all us-east-1):

| Service | Operation | Changed |
|---|---|---|
| service-quotas | GetServiceQuota L-1216C47A, L-34B43A08 | read only |
| ec2 | DescribeInstances / DescribeVolumes / DescribeInstanceTypes / DescribeInstanceTypeOfferings / DescribeVolumesModifications | read only |
| ec2 | ModifyInstanceAttribute InstanceType=r7i.16xlarge | second box type |
| ec2 | ModifyVolume 2048 GiB gp3 16000/1000 | second box root volume |
| ec2 | CreateTags KeepRunning=true + KeepRunningReason | second box tags |
| ec2 | StartInstances | started |
| ssm | DescribeInstanceInformation, SendCommand AWS-RunShellScript (df/lsblk/growpart/resize2fs/nproc), GetCommandInvocation | no software change |
| ec2 | CreateTags KeepRunning=false + KeepRunningReason | second box tags |
| ec2 | StopInstances | stopped |
| pricing | GetProducts (EC2 r7i, gp3, AWSDataTransfer) | read only |
| ec2 | DescribeSpotPriceHistory, DescribeSnapshots/Images/LaunchTemplates (none exist) | read only |
| s3 | ListBuckets, GetBucketLocation, ListObjectsV2 `frankie/ingest/` (us-east-2) | read only |

## Part 2: running every day's ROOT at once (read only; nothing launched or filed)

Greg's design: clone the full box. Number every 16-CPU lane across all boxes from 1 to N, assign each day a random lane
number, and each lane runs its day. There is no new scheduler. N lanes equals the number of days.

**Quota:** On-Demand Standard (L-1216C47A) = **256 vCPU**. Spot Standard (L-34B43A08) = 256 vCPU, a separate pool. The
main box uses 32 while it is running.

- With the main box running, 224 vCPU are free: **12 lanes** (3 x 16xl, 2 x 24xl or 1 x 48xl; 7 x 8xl gives 14).
- With the main box stopped, 256 are free: **16 lanes** (4 x 16xl). That covers the 13 ingested days.
- **31 lanes need 496 vCPU of lanes.** On 8 x 16xl plus the main box that is 544. Request: `service-quotas
  request-service-quota-increase --service-code ec2 --quota-code L-1216C47A --desired-value 640 --region us-east-1`
  (that is 544 plus headroom; NOT filed).

**Prices:** us-east-1 Linux, Pricing API GetProducts, plus a DescribeSpotPriceHistory snapshot taken 2026-10-07 ~19:05Z.

| Type | vCPU | Lanes | On-demand $/h | Spot $/h, 1d (cheapest AZ) | EBS read MB/s max | Network |
|---|---|---|---|---|---|---|
| r7i.8xlarge | 32 | 2 | 2.1168 | 0.55 (0.53 1c) | 1250 | 12.5 Gb |
| r7i.16xlarge | 64 | 4 | 4.2336 | 1.68 (1.01 1a) | 2500 | 25 Gb |
| r7i.24xlarge | 96 | 6 | 6.3504 | 3.19 (3.16 1f) | 3750 | 37.5 Gb |
| r7i.48xlarge | 192 | 12 | 12.7008 | 3.84 (3.65 1a) | 5000 | 50 Gb |

Each clone's root volume (2048 GiB gp3 16000/1000) costs $0.361/h. That uses $0.08/GB-mo, $0.005/IOPS-mo above 3000 and
$0.04/MBps-mo above 125, all from the Pricing API.

**Boxes for N lanes, about 3 h, on-demand compute plus EBS:**

| Lanes | Type | Boxes | vCPU | Idle lanes | Quota OK now? | $/h compute | ~3 h total OD | ~3 h Spot (1d) |
|---|---|---|---|---|---|---|---|---|
| 13 | r7i.16xlarge | 4 | 256 | 3 | only with main stopped | 16.93 | $55 | $25 |
| 13 | r7i.8xlarge | 7 | 224 | 1 | yes, even with main running | 14.82 | $52 | $19 |
| 13 | r7i.48xlarge | 2 | 384 | 11 | no | 25.40 | $78 | $25 |
| 24 | 16xl / 24xl / 48xl | 6 / 4 / 2 | 384 | 0 | no | 25.40 | $83 / $81 / $78 | $37 / $43 / $25 |
| **31** | **r7i.16xlarge** | **8** | 512 | 1 | no (needs 544) | 33.87 | **$110** | $49 |
| 31 | r7i.24xlarge | 6 | 576 | 5 | no | 38.10 | $121 | $64 |
| 31 | r7i.48xlarge | 3 | 576 | 5 | no | 38.10 | $118 | $38 |

**Rough cost of 31 day-ROOTs at once for about 3 h:** about **$110-121 on-demand**, or about $38-64 on Spot (Spot carries
interruption risk mid-ROOT). The second box counts as one of the 8 x 16xl. Smaller per-box disks would only save cents
over 3 h.

**Cloning identical boxes (no AMI, snapshot or launch template exists yet):**

- **A. AMI plus launch template (recommended).** CreateImage from a stopped box gives a consistent image. Imaging the
  main box waits until its run ends; the second box can be imaged now, but its software was not compared with the main
  box's. The first snapshot covers about 100 GB of used blocks (main box usage was not read). Estimate: about 15-45 min,
  once. The launch template holds the AMI, the instance type, `Ssm` profile, 2048 GiB gp3 16000/1000, IMDSv2,
  KeepRunning tags and AZ/subnet. Then one RunInstances with MinCount=MaxCount=N brings all N to running in about 1-2
  min and SSM Online in about 2-3 min. **The time is flat in N.** Caveat: volumes restored from a snapshot lazy-load
  blocks from S3, so the first reads are slow unless Fast Snapshot Restore is enabled (an extra per-hour charge; price
  not looked up).
- **B. Launch template only** (base Ubuntu AMI plus user-data bootstrap from git/S3). No snapshot wait. Every box runs
  setup in parallel, so the total is one setup run, roughly 10-20 min by estimate. Risk: the environments may drift and
  not be identical.
- Capacity: 8 x 16xl in one AZ can hit InsufficientInstanceCapacity. Put subnets in two or three AZs in the template.
  The second box and the main box are both in 1d.

**S3 pull per box:** the sealed ingests are in `s3://bento-568968024170-us-east-2-an/frankie/ingest/` (**us-east-2**). The
boxes are in us-east-1, so this is a cross-region pull at $0.01/GB from the Pricing API. 24 day prefixes are present,
330.6 GB in total (8.8-28.9 GB per day, mean 13.8). Whether each prefix is sealed was not checked. That is about $3.31 to
pull them all.

At 4 days per 16xl box, a box pulls up to about 64-116 GB. The ceiling is the gp3 write rate (1000 MB/s); the network is
25 Gb. Estimated pull time per box:

| Transfer setup | 64 GB | 116 GB |
|---|---|---|
| Multi-stream (~500-1000 MB/s) | ~1-2 min | ~2-4 min |
| Single stream (~100 MB/s) | ~11 min | ~19 min |

The ingest step should use parallel transfers. The transfer rates are estimates, not measured.
