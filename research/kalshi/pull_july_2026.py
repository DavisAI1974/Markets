#!/usr/bin/env python3
"""One-off ops (S100): pull the never-pulled July 1-18 2026 NG tape (year-pull boundary gap) into
nymex_cont/ for feed M's KXNATGASD life coverage. Mirrors redownload_mondays.py conventions
exactly: databento_backfill.batch_pull (no recreated logic), per-day verify (>=1MB gz, >=10k
rows), dow-named upload, idempotent (skips days already fat on S3). Range [2026-07-01,
2026-07-19) so Jul 18 is interior. Cost measured at submit time: $0.00 (inside the Standard
subscription's included historical window, checked 2026-07-20)."""
import sys, os, glob, datetime, boto3, gzip, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import databento_backfill as dbf

B = "bento-568968024170-us-east-2-an"; PFX = "nymex/nymex_cont/"
SCRATCH = os.environ.get("JUL_SCRATCH", "/tmp/jul_scratch")
os.makedirs(SCRATCH, exist_ok=True)
s3 = boto3.client("s3", "us-east-2")
DOW = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
START, END = "2026-07-01", "2026-07-19"

def log(m): print(f"[jul-pull] {m}", flush=True)

def existing_fat_days():
    out = set()
    r = s3.list_objects_v2(Bucket=B, Prefix=PFX + "NG_202607", MaxKeys=1000)
    for o in r.get("Contents", []):
        m = re.search(r"_(\d{8})", o["Key"])
        if m and o["Size"] >= 1_000_000:
            out.add(m.group(1))
    return out

def main():
    have = existing_fat_days()
    if have:
        log(f"already fat on S3 (skipped by upload step): {sorted(have)}")
    client = dbf._client()
    dbf.batch_pull(client, "NG", START, END, "mbp-10", max_cost=25.0,
                   out_dir=SCRATCH, flush_dir=SCRATCH)
    ok = fail = skip = 0
    for gz in sorted(glob.glob(os.path.join(SCRATCH, "NG_*.jsonl.gz"))):
        m = re.search(r"NG_(\d{8})", os.path.basename(gz))
        if not m:
            continue
        day = m.group(1)
        if day in have:
            skip += 1
            continue
        sz = os.path.getsize(gz)
        with gzip.open(gz, "rt") as fh:
            n = sum(1 for _ in fh)
        if sz < 1_000_000 or n < 10000:
            log(f"FAIL {day}: small ({sz}B, {n} rows) - NOT uploaded (holiday-thin days land here; verify by eye)")
            fail += 1
            continue
        d = datetime.date(int(day[:4]), int(day[4:6]), int(day[6:]))
        key = PFX + f"NG_{day}_{DOW[d.weekday()]}.jsonl.gz"
        s3.upload_file(gz, B, key)
        log(f"OK   {day}: {sz/1e6:.1f}MB, {n} rows -> s3://{key}")
        ok += 1
    log(f"DONE: {ok} uploaded, {fail} failed-verify, {skip} already-present")

if __name__ == "__main__":
    main()
