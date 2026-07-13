"""
pull_year_mbp10.py — pull a YEAR (or any month range) of continuous MBP-10 for CL+NG, month by month,
gzip each day AS IT LANDS, publish to a durable store, delete local. Bounded disk (never more than one
day of raw). RESUMABLE: a month already in the store is skipped.

Two destinations (--dest):
  * git (default): push the gz into a worktree of the data/nymex-ticks branch under nymex_cont/.
      Setup once:  git worktree add --force /tmp/nymexdata data/nymex-ticks
  * s3://BUCKET/PREFIX : upload the gz to an S3 / AWS-Lightsail bucket under PREFIX/nymex_cont/.
      Auth from the standard AWS env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
      (Lightsail bucket keys work). Optional AWS_S3_ENDPOINT for a custom/Lightsail endpoint.

Keeps ALL RAW DATA — databento_backfill._write_mbp10_df writes every message + every column, zero
filtering (no row is ever dropped). This driver only moves/compresses the files; it never touches content.

Usage:
    # git branch (default)
    DATABENTO_API_KEY=db-... python research/kalshi/pull_year_mbp10.py --start 2025-07 --end 2026-07

    # S3 / Lightsail bucket
    DATABENTO_API_KEY=db-... AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-1 \
      python research/kalshi/pull_year_mbp10.py --start 2025-07 --end 2026-07 --dest s3://my-bucket/nymex
"""
from __future__ import annotations

import argparse
import glob
import gzip
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import databento_backfill as dbf                              # noqa: E402

WT = "/tmp/nymexdata"                                          # worktree of data/nymex-ticks (git dest)
OUT = "data/nymex_cont"                                        # local scratch for decoded JSONL
BRANCH_DIR = os.path.join(WT, "nymex_cont")                   # where gz land locally before publish


def _months(start, end):
    """[start, end) as (year, month), start/end are 'YYYY-MM'."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    y, m = sy, sm
    while (y, m) < (ey, em):
        out.append((y, m))
        m += 1
        if m > 12:
            y += 1; m = 1
    return out


def _first_of_next(y, m):
    return f"{y+1}-01-01" if m == 12 else f"{y}-{m+1:02d}-01"


def _week_spans(start, end):
    """[start,end) 'YYYY-MM' month range -> list of (ws,we) 7-day [ws,we) date strings covering it.
    Week-at-a-time: smaller Databento batch jobs -> faster to reach 'done' + finer resume + per-week
    S3 publish (Greg S91: 'do a week at a time')."""
    import datetime as _dt
    sy, sm = map(int, start.split("-")); ey, em = map(int, end.split("-"))
    d = _dt.date(sy, sm, 1)
    last = _dt.date(ey, em, 1)
    out = []
    while d < last:
        we = min(d + _dt.timedelta(days=7), last)
        out.append((d.isoformat(), we.isoformat()))
        d = we
    return out


def _git(*args):
    return subprocess.run(["git", "-C", WT, *args], capture_output=True, text=True)


# ---- S3 / Lightsail-bucket destination -------------------------------------------------------------

def _s3_parse(dest):
    """s3://bucket/prefix -> (bucket, prefix). prefix may be empty."""
    bucket, _, prefix = dest[len("s3://"):].partition("/")
    return bucket, prefix.strip("/")


def _s3_client():
    import boto3
    kw = {}
    ep = os.environ.get("AWS_S3_ENDPOINT")                    # optional (Lightsail / custom endpoint)
    if ep:
        kw["endpoint_url"] = ep
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    if region:
        kw["region_name"] = region
    return boto3.client("s3", **kw)


def _s3_key(prefix, name):
    return (f"{prefix}/" if prefix else "") + f"nymex_cont/{name}"


STUB_BYTES = 5000            # a real trading day of MBP-10 gz is tens of MB; <5KB = the S90 flush-bug stub
MIN_DAYS = 15                # a full trading month has ~20-23 UTC days; fewer = incomplete, re-pull


def _s3_days_present(s3, bucket, prefix, day_pfx):
    """Return the list of (key, size) objects under nymex_cont/{day_pfx}* (a day/week/month prefix)."""
    pfx = _s3_key(prefix, day_pfx)
    objs, tok = [], None
    while True:
        kw = dict(Bucket=bucket, Prefix=pfx)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        objs += [(o["Key"], o["Size"]) for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            return objs
        tok = r["NextContinuationToken"]


def _s3_month_present(s3, bucket, prefix, root, y, m):
    """CLEAN-present only: has files, NO sub-5KB stubs, and a plausible day count. A month that is empty,
    stub-corrupt (the S90 flush bug), or thin is treated as ABSENT so it is RE-PULLED, never silently skipped."""
    objs = _s3_days_present(s3, bucket, prefix, f"{root}_{y}{m:02d}")
    if not objs:
        return False
    if any(sz < STUB_BYTES for _, sz in objs):    # any stub -> corrupt month, re-pull
        return False
    return len(objs) >= MIN_DAYS


def _week_marker_key(prefix, root, ws):
    return (f"{prefix}/" if prefix else "") + f"nymex_cont/_done/{root}_{ws}.done"


def _week_done(s3, bucket, prefix, root, ws):
    """A week is DONE iff its marker exists (written only after a clean per-week upload). Bulletproof
    resume: a partial/failed week has no marker -> re-pulled."""
    r = s3.list_objects_v2(Bucket=bucket, Prefix=_week_marker_key(prefix, root, ws), MaxKeys=1)
    return r.get("KeyCount", 0) > 0


def _publish_all_s3(s3, bucket, prefix):
    """Upload every gz currently in BRANCH_DIR to nymex_cont/, delete local. Returns (n, stub_count)."""
    gz = sorted(glob.glob(os.path.join(BRANCH_DIR, "*.jsonl.gz")))
    stubs = 0
    for g in gz:
        if os.path.getsize(g) < STUB_BYTES:
            stubs += 1
        key = _s3_key(prefix, os.path.basename(g))
        for attempt in range(4):
            try:
                s3.upload_file(g, bucket, key); break
            except Exception as e:
                print(f"[pull_year] s3 upload retry {attempt} {key}: {e}", flush=True)
        os.remove(g)
    return len(gz), stubs


# ---- main ------------------------------------------------------------------------------------------

def main():
    global WT, OUT, BRANCH_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM exclusive")
    ap.add_argument("--dest", default="git",
                    help="'git' (worktree of data/nymex-ticks, default) or 's3://BUCKET/PREFIX' "
                         "(S3 / Lightsail bucket; uses the standard AWS env vars).")
    ap.add_argument("--max-cost-per", type=float, default=1000.0,
                    help="per (month,contract) cost gate ($). Price is pre-agreed -> high by default; the "
                         "estimate is still printed so spend is logged.")
    ap.add_argument("--worktree", default=WT,
                    help="git dest only: path to a worktree of data/nymex-ticks (default /tmp/nymexdata). "
                         "Create once: git worktree add --force <path> data/nymex-ticks")
    ap.add_argument("--scratch", default=OUT, help="local scratch dir for decoded JSONL before gzip")
    ap.add_argument("--reuse-done-jobs", action="store_true",
                    help="RECOVERY mode: for each (month,root) with an ALREADY-DONE Databento batch job, "
                         "RE-DECODE it (free, ~30d re-serve) with the current writer/flush and OVERWRITE the "
                         "store, instead of submitting a new (paid) job or skipping. Months without a done "
                         "job are submitted normally. Use to rebuild months corrupted by the pre-S90 flush "
                         "bug without re-charging.")
    ap.add_argument("--weekly", action="store_true",
                    help="WEEK-AT-A-TIME (S3 only): submit each week as its own Databento batch job and "
                         "publish + mark it done as it lands (smaller jobs -> faster to 'done', finer resume, "
                         "per-week S3 progress). Fresh clean pull (no reuse); marker-based resume.")
    args = ap.parse_args()

    OUT = args.scratch
    is_s3 = args.dest.startswith("s3://")

    if is_s3:
        bucket, prefix = _s3_parse(args.dest)
        s3 = _s3_client()
        BRANCH_DIR = os.path.join(OUT, "_gz")                 # gz land here locally, uploaded then deleted
        os.makedirs(BRANCH_DIR, exist_ok=True)
        print(f"[pull_year] dest = s3://{bucket}/{prefix or ''} (nymex_cont/)", flush=True)
    else:
        WT = args.worktree
        BRANCH_DIR = os.path.join(WT, "nymex_cont")
        if not os.path.exists(os.path.join(WT, ".git")):
            sys.exit(f"[pull_year] worktree missing at {WT}; run: "
                     f"git worktree add --force {WT} data/nymex-ticks")
        os.makedirs(BRANCH_DIR, exist_ok=True)
        _git("config", "user.email", "noreply@anthropic.com")
        _git("config", "user.name", "Claude")

    os.makedirs(OUT, exist_ok=True)
    client = dbf._client()

    # RECOVERY: map every already-DONE whole-month GLBX mbp-10 batch job -> (root, 'YYYYMM') so we can
    # re-decode it free instead of re-submitting (fixes the pre-S90 flush corruption without re-charging).
    done_map = {}
    if args.reuse_done_jobs:
        for j in client.batch.list_jobs():
            if j.get("dataset") != "GLBX.MDP3" or j.get("schema") != "mbp-10" or j.get("state") != "done":
                continue
            syms = j.get("symbols") or []
            sym = str(syms[0] if isinstance(syms, (list, tuple)) else syms).upper()
            r = "NG" if sym.startswith("NG") else ("CL" if sym.startswith("CL") else None)
            st = str(j.get("start"))[:10]                          # YYYY-MM-DD
            if r and len(st) == 10 and st[8:10] == "01":           # whole-month jobs only
                done_map[(r, st[:4] + st[5:7])] = j.get("id")
        print(f"[pull_year] reuse-done-jobs: {len(done_map)} done monthly jobs available for free re-decode",
              flush=True)

    total_rows = 0

    # ---- WEEK-AT-A-TIME (S3 only): fresh per-week batch jobs, marker-based resume, per-week publish ----
    if args.weekly:
        if not is_s3:
            sys.exit("[pull_year] --weekly requires an s3:// dest")
        spans = _week_spans(args.start, args.end)
        print(f"[pull_year] WEEKLY: {len(spans)} weeks x 2 roots ({args.start}..{args.end})", flush=True)
        for (ws, we) in spans:
            for root in ("CL", "NG"):
                if _week_done(s3, bucket, prefix, root, ws):
                    print(f"[pull_year] skip {root} week {ws} (marker present)", flush=True)
                    continue
                try:
                    print(f"[pull_year] PULL {root} week {ws}..{we}", flush=True)
                    n = dbf.batch_pull(client, root, ws, we, "mbp-10", args.max_cost_per,
                                       out_dir=OUT, flush_dir=BRANCH_DIR)
                    total_rows += n
                except SystemExit as e:
                    print(f"[pull_year] SKIP {root} week {ws}: {e}", flush=True); continue
                except Exception as e:
                    print(f"[pull_year] ERROR {root} week {ws}: {e}", flush=True); continue
                # belt: gzip any straggler raw
                for f in sorted(glob.glob(os.path.join(OUT, "*.jsonl"))):
                    with open(f, "rb") as srcf, gzip.open(os.path.join(BRANCH_DIR,
                              os.path.basename(f) + ".gz"), "wb", compresslevel=6) as dst:
                        shutil.copyfileobj(srcf, dst)
                    os.remove(f)
                ngz, stubs = _publish_all_s3(s3, bucket, prefix)
                if ngz and not stubs:
                    s3.put_object(Bucket=bucket, Key=_week_marker_key(prefix, root, ws),
                                  Body=b"ok")                    # mark done ONLY when clean
                    print(f"[pull_year] {root} week {ws} uploaded {ngz} gz, marked done "
                          f"(cum rows {total_rows})", flush=True)
                else:
                    print(f"[pull_year] {root} week {ws}: {ngz} gz, {stubs} stubs -> NOT marked "
                          f"(will re-pull)", flush=True)
        print(f"[pull_year] DONE WEEKLY {args.start}..{args.end}: {total_rows} rows total", flush=True)
        return

    for (y, m) in _months(args.start, args.end):
        start, end = f"{y}-{m:02d}-01", _first_of_next(y, m)
        for root in ("CL", "NG"):
            reuse_jid = done_map.get((root, f"{y}{m:02d}")) if args.reuse_done_jobs else None
            present = (not reuse_jid) and (
                _s3_month_present(s3, bucket, prefix, root, y, m) if is_s3
                else bool(glob.glob(os.path.join(BRANCH_DIR, f"{root}_{y}{m:02d}*.jsonl.gz"))))
            if present:
                print(f"[pull_year] skip {root} {y}-{m:02d} (already in store)", flush=True)
                continue
            try:
                # flush_dir -> each per-day JSONL is gzipped into BRANCH_DIR AS IT LANDS and the raw is
                # deleted, so local never holds more than one day of raw even for a whole-month batch.
                if reuse_jid:
                    print(f"[pull_year] RE-DECODE {root} {y}-{m:02d} from done job {reuse_jid} (free)",
                          flush=True)
                    n = dbf.redecode_job(client, reuse_jid, root, "mbp-10",
                                         out_dir=OUT, flush_dir=BRANCH_DIR)
                else:
                    n = dbf.batch_pull(client, root, start, end, "mbp-10", args.max_cost_per,
                                       out_dir=OUT, flush_dir=BRANCH_DIR)
                total_rows += n
            except SystemExit as e:
                print(f"[pull_year] SKIP {root} {y}-{m:02d}: {e}", flush=True)
            except Exception as e:
                print(f"[pull_year] ERROR {root} {y}-{m:02d}: {e}", flush=True)
        # fallback: gzip any straggler raw JSONL not already flushed (belt-and-suspenders)
        for f in sorted(glob.glob(os.path.join(OUT, "*.jsonl"))):
            with open(f, "rb") as src, gzip.open(os.path.join(BRANCH_DIR, os.path.basename(f) + ".gz"),
                                                 "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            os.remove(f)

        # publish the month
        gz_files = sorted(glob.glob(os.path.join(BRANCH_DIR, f"*_{y}{m:02d}*.jsonl.gz")))
        if not gz_files:
            print(f"[pull_year] {y}-{m:02d} nothing new to publish", flush=True)
            continue
        if is_s3:
            for g in gz_files:
                key = _s3_key(prefix, os.path.basename(g))
                for attempt in range(4):
                    try:
                        s3.upload_file(g, bucket, key)
                        break
                    except Exception as e:
                        print(f"[pull_year] s3 upload retry {attempt} {key}: {e}", flush=True)
                os.remove(g)                                  # local gz not needed after upload
            print(f"[pull_year] {y}-{m:02d} uploaded {len(gz_files)} gz to s3://{bucket}/"
                  f"{(prefix + '/') if prefix else ''}nymex_cont/ (cum rows {total_rows})", flush=True)
        else:
            _git("add", "nymex_cont/")
            if _git("diff", "--cached", "--quiet").returncode != 0:
                _git("commit", "-q", "-m",
                     f"data: continuous MBP-10 nymex_cont/ {y}-{m:02d} (CL+NG), full-raw\n\n"
                     f"Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>")
                for _ in range(4):
                    _git("pull", "--rebase", "origin", "data/nymex-ticks")
                    if _git("push", "origin", "HEAD:data/nymex-ticks").returncode == 0:
                        break
                print(f"[pull_year] {y}-{m:02d} pushed (cum rows {total_rows})", flush=True)
    print(f"[pull_year] DONE {args.start}..{args.end}: {total_rows} rows total", flush=True)


if __name__ == "__main__":
    main()
