# AWS deep dive for Frankie/BOSS, 2026-10-07 night (read-only research)

Saved by the parent from the deep-dive agent's return (the agent had no file-write tool). Nothing was launched, changed
or installed. Every launch/start/stop/account change below needs Greg's explicit go. The Aws connector signed out
mid-pass, so these were NOT verified: r8i/r8id/r7iz/Graviton prices, the Spot snapshot, the us-east-2 quota, the
status of the 640-vCPU request, VPC endpoints, Compute Optimizer enrollment.

## Finding behind the plan
ROOT is bound by its serial Python replay (25 records/s on one CPU in the E2E), not by disk or network. AWS can add
per-core speed (~+20%), remove waits around ROOT, and cut cost; the real speed-up is the replay fix in code (9e7a7d90
onward). Disk CAPACITY is a new risk: 20231018 (771,787 records x ~525 KB) ~405 GB of spool; the biggest day (28.9 GB
journal, ~2.5M records by scaling) ~1.3 TB; two big days on one 2 TB box overflow it.

## Stacked plan
One-day run now (main box r7i.8xlarge; nothing new launched):
1. Hyperthread-aware pinning (free, lane config only): an 8xlarge is 16 cores x 2 threads; keep the serial replay's
   sibling thread idle. Confirm with `lscpu -e` at the next SSM read.
2. Main-box gp3 throughput 1000 -> 1250 MB/s (the instance EBS ceiling; `ec2 ModifyVolume`, about +$10/month). Helps
   the digest read-back. Account change: Greg's call.
3. Nothing else pays for the one-day run (ingest already local, box already sized).

30/31-day multi-box run, in order of impact:
1. r8id.8xlarge clones instead of r7i.8xlarge: 3.9 GHz all-core vs 3.2, AWS states +20% performance and +15%
   price-performance vs R7i, 1.9 TB local NVMe for spools; offered in all us-east-1 and us-east-2 AZs. Gate: 1-2 min
   canary of the same day on r7i and r8id comparing spool sha256 byte for byte. r8i (EBS only) is the fallback.
2. Disk capacity rule per lane: day records x measured bytes per record; never two big days on one 1.9 TB box (a disk
   check before the random lane assignment, not a scheduler). Alternatives: r8id.16xlarge (3.8 TB, 4 lanes) or gp3
   sized per box (up to 64 TiB, 2000 MiB/s).
3. Golden AMI + launch template: image the lean second box (97 GB used) after its pins pass the H-4 gate, not the
   700 GB main box; IMDSv2, profile Ssm, NVMe formatted at boot, multi-AZ subnets; warm granite/venv at boot (free);
   Fast Snapshot Restore optional ($0.75 per DSU-hour per AZ, minimum 1 h).
4. EC2 Fleet `instant`, On-Demand, several x86 types and AZs (r8id -> r8i -> r7i, prioritized), with
   InstanceInitiatedShutdownBehavior=terminate: each box archives to S3 then shuts down (Greg's "kill afterwards").
5. One region for compute and outputs: run clones in us-east-2 next to the bento bucket, or archive outputs to a
   us-east-1 bucket; archived spools would be ~19.7 TB (~$197 cross-region); add a free S3 gateway endpoint.
6. CRT transfer for every S3 pull and archive (preferred_transfer_client=crt), or parallel ranged presigned GETs per
   4 GiB piece.
7. Spool archive policy (Greg's call): spools are deterministic, so journal + commit regenerate them; archive only the
   digest, or archive spools with a lossless zstd stack proven by parse-back.

Optional later: Step Functions instead of the GitHub dispatch; S3 Express One Zone hot staging (use1-az4/5/6,
use2-az1/2); Mountpoint for read-only inputs; S3 Inventory/Metadata instead of large ListObjects sweeps.

Skipped, with reason: placement groups (lanes don't talk; capacity-error risk); Transfer Acceleration (no benefit
inter-region); FSx for Lustre and EFS (slower/costlier than local NVMe for single-owner spools); AWS Batch (needs
containers, no cpuset pinning, no Batch skill in the registry); Spot for ROOT (mid-replay interruption loses on-disk
state); Compute Optimizer (needs history killed clones never build); Athena/Glue/S3 Tables (DuckDB covers it);
Graviton now (x86 sha pins for llama.cpp; byte-identity risk).

## Rough 31 days, ROOT phase only (37.5M records, 16 x 8xlarge at once; replay rate after the fix unmeasured)
| Replay rate | Wall time | Compute r7i on-demand | EBS | With r8i (x1.2) |
|---|---|---|---|---|
| 100 records/s | ~7.0 h | ~$238 | +$41 | ~5.9 h, ~$200 |
| 250 records/s | ~2.8 h | ~$95 | +$16 | ~2.3 h, ~$80 |
Terminating each box when its own lanes finish brings cost toward lane-hours (~$44-110). Later stages not included.

## Instance facts checked (us-east-1, DescribeInstanceTypes)
| Type | vCPU | Clock | NVMe | EBS ceiling |
|---|---|---|---|---|
| r8id.8xlarge | 32 | 3.9 GHz | 1 x 1900 GB | 1250 MB/s |
| r8id.16xlarge | 64 | 3.9 GHz | 3800 GB | 2500 MB/s |
| m8id.8xlarge | 32 | 3.9 GHz | 1900 GB | n/a |
| c8id.8xlarge | 32 | 3.9 GHz | 1900 GB (64 GiB RAM) | n/a |
| r8gd.8xlarge/.16xlarge (Graviton4) | 32/64 | 2.8 GHz | 1900/3800 GB | n/a |
| i7i.8xlarge/.16xlarge | 32/64 | 3.2 GHz | 7.5/15 TB | n/a |
| z1d.12xlarge | 48 | 4.0 GHz | 1800 GB | n/a |
The r7i family has no `d` variant. All offered in all 5 us-east-1 and 3 us-east-2 AZs (z1d only us-east-2a/2b).

## Risks
Disk overflow with random lane assignment; byte identity across CPU generations (numpy kernels, llama.cpp; the sha256
canary is the gate); instance store loses data on stop (save/resume needs a running box; archive before terminate);
capacity (640-vCPU request pending; multi-AZ overrides); cross-region egress on TB-scale outputs.

## Skills read
Local: api-and-interface-design, performance-optimization. AWS: aws-compute (+ instance-selection, provisioning,
auto-scaling, ami-management), aws-storage (+ ebs, s3-express, fsx-lustre, s3-general-purpose, s3-files),
aws-billing-and-cost-management, configuring-vpc-endpoints-for-private-aws-service-access, aws-step-functions. Judged
not to fit from descriptions: launching-ec2-instance-with-best-practices, amazon-ec2-image-builder, aws-containers,
aws-serverless, aws-lambda-managed-instances, aws-lambda-microvms, aws-lambda-durable-functions,
processing-s3-uploads-with-step-functions, querying-aws-s3, ingesting-into-data-lake, querying-data-lake,
aws-messaging-and-streaming, aws-observability, aws-transform, troubleshooting-efs. No AWS Batch skill exists.

## Account calls (read-only)
ec2 DescribeInstanceTypes (us-east-1, 29 types); ec2 DescribeInstanceTypeOfferings (us-east-1 and us-east-2). A
second script (pricing GetProducts, DescribeSpotPriceHistory) failed when the connector signed out. No writes.
