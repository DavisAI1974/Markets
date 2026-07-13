---
name: kalshi-session-start
description: Kalshi session-start ritual — verify you are on the real branch (not the stale S70 tip), read the current state docs in order, and materialize the accrued data branches (kalshi-bins, pyth-ticks) locally with an accrual check. Run at the start of every Kalshi work session before touching any code or data.
---

# Kalshi session start

Run these steps IN ORDER. Do not skip the branch check — the harness recurringly cuts fresh
session branches from a stale tip and work done there is stranded.

## 1. Branch check (the stale-tip trap)

```bash
git log --oneline -1
```

- If the tip is `3c70ff5` (S70) or anything dated before the latest `SESSION_HANDOFF_*.md`,
  you are on a stale branch. Get onto the canonical trunk:

```bash
git fetch origin claude/kalshi-s79-kickoff-ij8t9o
git checkout -B claude/kalshi-s79-kickoff-ij8t9o origin/claude/kalshi-s79-kickoff-ij8t9o
```

- The trunk is also where the GitHub Actions collectors auto-push, so ALWAYS
  `git pull origin claude/kalshi-s79-kickoff-ij8t9o` before pushing your own commits.

## 2. Read the state (in this order, nothing else first)

1. Latest `SESSION_HANDOFF_*.md` (highest S-number) — actual current state.
2. Latest `KICKOFF_*.md` — this session's priorities.
3. `KALSHI_TRADING.md` — the file index (current vs old pieces).

## 3. Materialize accrued data branches

Bins and ticks accrue GZIPPED on data branches; local files are raw JSONL (gitignored).

```bash
# Kalshi bins + consensus  ->  data/kalshi/
mkdir -p data/kalshi
git fetch origin data/kalshi-bins
for gz in $(git ls-tree -r --name-only origin/data/kalshi-bins | grep '\.jsonl\.gz$'); do
  base=$(basename "$gz" .gz)
  git show "origin/data/kalshi-bins:$gz" | gunzip > "data/kalshi/$base"
  echo "[restore] $base ($(wc -l < data/kalshi/$base) lines)"
done

# Pyth futures ticks  ->  data/pyth_ticks/
mkdir -p data/pyth_ticks
git fetch origin data/pyth-ticks
for gz in $(git ls-tree -r --name-only origin/data/pyth-ticks | grep '\.jsonl\.gz$'); do
  base=$(basename "$gz" .gz)
  git show "origin/data/pyth-ticks:$gz" | gunzip > "data/pyth_ticks/$base"
  echo "[restore] $base ($(wc -l < data/pyth_ticks/$base) lines)"
done

# NYMEX Databento tapes now live on AWS S3, NOT git (S90 move). Bucket bento-568968024170-us-east-2-an,
# prefix nymex/. Restore from S3 (needs AWS_* env creds + boto3). *.json baselines -> data/ ; tapes gunzip.
python3 - <<'PY'
import boto3, gzip, os
B="bento-568968024170-us-east-2-an"; s3=boto3.client("s3", region_name=os.environ.get("AWS_DEFAULT_REGION","us-east-2"))
plan=[("nymex/nymex_tape/","data/pyth_ticks"), ("nymex/nymex_mbp10/","data/nymex_mbp10")]  # S85 trades ; S86 depth
for pfx,dst in plan:
    os.makedirs(dst, exist_ok=True)
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix=pfx):
        for o in pg.get("Contents",[]):
            name=o["Key"].split("/")[-1]; raw=s3.get_object(Bucket=B,Key=o["Key"])["Body"].read()
            if name.endswith(".gz"):
                base=name[:-3]; out=("data/"+base) if base.endswith(".json") else f"{dst}/{base}"  # baselines->data/
                open(out,"wb").write(gzip.decompress(raw))
            else:
                out=("data/"+name) if name.endswith(".json") else f"{dst}/{name}"
                open(out,"wb").write(raw)
            print("[restore]", name)
PY
```

The **continuous MBP-10 YEAR corpus** (S89, the full-raw analog library) lives on S3 at
`nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz` — LARGE, do NOT blanket-restore. The scoring code streams days
on demand via `event_move_baseline.load_cont_day(root, day, source="s3")` (local gz cache). To pull one day
by hand: `aws s3 cp s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/CL_20260617.jsonl.gz - | zcat`.

## 4. VERIFY accrual before trusting the data

- Check the newest timestamp inside each restored file, not just its existence — a feed can be
  stuck while old data sits there looking healthy. If the latest bin/tick is older than the last
  6h collector cycle (both workflows run every 6h), the feed is stalled.
- If a workflow run sits `queued` and never executes: it is an ACCOUNT-level Actions problem
  (billing / minutes / runner cap), not the workflow file. Claude's token cannot dispatch runs —
  Greg clicks "Run workflow".
- Pyth note: energy futures trade ~Sun 18:00 ET through Fri; a weekend gap with only deduped
  frozen prices is normal, a weekday gap is not.

## 5. Only then start the session's work

Priorities come from the kickoff, not from this skill.
