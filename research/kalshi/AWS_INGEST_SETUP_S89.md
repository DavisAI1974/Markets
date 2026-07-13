# AWS ingest setup — full-raw MBP-10 year to an S3 bucket (S89)

Runbook to pull the continuous full-raw MBP-10 year (CL+NG, 2025-07..2026-07) straight to an AWS S3
bucket. The driver + writer are done and pushed to the trunk `claude/kalshi-s79-kickoff-ij8t9o`.

## LIVE TARGET (set up S89)
- Bucket: **`bento-568968024170-us-east-2-an`**, region **us-east-2**, prefix **`nymex/`**
  (objects land at `nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz`).
- IAM user **`Claude`** (AmazonS3FullAccess). Its access key + secret and the `DATABENTO_API_KEY` are
  SECRETS -- they are pasted per session and NOT stored in git. A new session needs them re-pasted.
- Split in flight: my container ran **Jan-Jun 2026** to the bucket; Greg's machine runs **Jul-Dec 2025**
  to the same bucket (disjoint months -> no double Databento charge). Resume = list the bucket, pull the
  missing months.

## What's already built (trunk)
- `research/kalshi/databento_backfill.py` — RAW MBP-10 writer, ZERO filtering (every message + every
  column), streams row-by-row (OOM-safe on heavy 2-3M-message days).
- `research/kalshi/pull_year_mbp10.py` — month-at-a-time batch pull, gzip each day as it lands, delete
  raw (local never holds > 1 day), resumable. Two destinations via `--dest`:
    * `--dest git`  (default) -> worktree of data/nymex-ticks, nymex_cont/
    * `--dest s3://BUCKET/PREFIX` -> uploads each gz to PREFIX/nymex_cont/ (boto3; standard AWS auth)

## One-time AWS setup
1. Lightsail console -> Storage -> Create bucket -> pick the $3/mo (100 GB) tier -> name it
   (e.g. `davisai-nymex`). Note the REGION (e.g. us-east-1).
2. Bucket -> "Access keys" (or an IAM user) -> create -> copy the **Access Key ID** + **Secret**.
   (Lightsail bucket keys are scoped to that bucket = low blast radius.)

## Credentials needed by whoever runs it
- `DATABENTO_API_KEY`  (db-... , the Databento secret)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`  (the bucket's region)
- (optional) `AWS_S3_ENDPOINT` if using a custom/Lightsail endpoint; standard S3 needs none.

## Run it — option A: on a durable box (Lightsail instance etc.; keys stay local, RECOMMENDED)
```bash
# one-time on the box
sudo apt-get update && sudo apt-get install -y git python3-pip
pip install databento boto3 pandas
git clone <the Markets repo> Markets && cd Markets
git checkout claude/kalshi-s79-kickoff-ij8t9o && git pull

# creds (secrets - paste the real values)
export DATABENTO_API_KEY=db-...
export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  AWS_DEFAULT_REGION=us-east-2

# resume the whole year -> the bucket (resumable; safe to re-run; skips months already in the bucket)
nohup python research/kalshi/pull_year_mbp10.py \
    --start 2025-07 --end 2026-07 --dest s3://bento-568968024170-us-east-2-an/nymex \
    --scratch /tmp/nymex_scratch > pull.log 2>&1 &
tail -f pull.log
```
The instance survives restarts, so one run finishes the year unattended. `--dest s3` needs NO git
worktree; the repo checkout is only for the code.

## Run it — option B: in a new Claude session (container)
Paste Claude the bucket keys + Databento key and have it run the SAME command. Works, but the
container can be reclaimed mid-run; it's resumable (re-run picks up months not yet in the bucket),
so that's just a restart, not lost data.

## Split across two machines for ~2x speed (optional)
Disjoint month ranges -> no month pulled twice -> no double Databento charge. Same `--dest` bucket.
- machine 1:  --start 2025-07 --end 2026-01
- machine 2:  --start 2026-01 --end 2026-07

## Resume / cost / verify
- Resume: the s3 run skips a month if any `{root}_{yyyymm}*.jsonl.gz` already exists under the prefix.
- Cost: ~$7.5 per (month, contract) => ~$150 for the full CL+NG year (Databento, one-time, pre-agreed).
  Bucket storage ~$3/mo (year gz ~= 25 GB). One CL day ~= 61 MB gz / ~975k-3M messages.
- Verify a sample: `aws s3 cp s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/CL_20260514.jsonl.gz - | zcat | head -1`
  -> a JSON row with all 10 bid+ask levels (bid_px_00..09, ask_*, *_sz_*, *_ct_*), action/side/depth/
  flags/sequence/ts_event/ts_recv (76 fields). That confirms full-raw.

## Note on the git-branch stopgap
A git-branch half (Jan-Jun 2026 -> data/nymex-ticks:nymex_cont/) was running in the S89 container to
make progress while AWS was being set up. It stops when that container is reclaimed. Simplest clean
end-state: pull ALL 12 months fresh to the bucket (uniform corpus); the couple of months the git half
may have landed can be ignored or `aws s3 cp`-migrated to the bucket later. Do NOT run a git-dest and an
s3-dest over the SAME months at once (that double-pays Databento).
