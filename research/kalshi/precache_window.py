"""precache_window.py — pre-decode every NG continuous day in a date window to npz (via fast_tape), so the
continuous-curve render/score is instant. Lists the S3 nymex_cont NG files, filters to [start,end], and
caches each. Run in the background once per window. S95."""
import sys, os, time
import boto3
import fast_tape, event_move_baseline as emb

START, END = sys.argv[1], sys.argv[2]          # bare YYYYMMDD inclusive


def window_days(start, end):
    s3 = boto3.client("s3")
    pfx = f"{emb.S3_PREFIX + '/' if emb.S3_PREFIX else ''}nymex_cont/"
    days = set()
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=emb.S3_BUCKET, Prefix=pfx + "NG_"):
        for o in pg.get("Contents", []):
            stem = o["Key"].split("/")[-1].replace("NG_", "").split(".")[0]  # e.g. 20250908_mon -> 20250908
            d = stem.split("_")[0]
            if len(d) == 8 and start <= d <= end:
                days.add(d)
    return sorted(days)


if __name__ == "__main__":
    days = window_days(START, END)
    print(f"[precache] {len(days)} NG days in {START}..{END}", flush=True)
    t0 = time.time()
    for i, d in enumerate(days, 1):
        try:
            ts, px = fast_tape.fast_load_day("NG", d)
            tag = f"open={px[0]:.3f} close={px[-1]:.3f} n={len(px)}" if len(px) else "EMPTY"
            print(f"[{i:2d}/{len(days)}] {d}  {tag}  ({time.time()-t0:.0f}s elapsed)", flush=True)
        except Exception as e:
            print(f"[{i:2d}/{len(days)}] {d}  ERROR {type(e).__name__}: {str(e)[:80]}", flush=True)
    print(f"[precache] done in {time.time()-t0:.0f}s", flush=True)
