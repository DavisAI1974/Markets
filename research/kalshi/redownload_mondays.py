#!/usr/bin/env python3
"""One-off ops: re-download every corrupt Monday stub in nymex_cont/ (all Mondays were truncated to
455-byte stubs by the Tue->Tue weekly-batch last-day clobber). Pull each Monday as a 2-day batch
[Mon, Wed) so Monday is an INTERIOR day, verify it's full, upload over the stub with the dow name.
Uses existing databento_backfill.batch_pull (no recreated logic). Run in background."""
import sys, os, glob, datetime, boto3, gzip, re
sys.path.insert(0, "/home/user/Markets/research/kalshi")
import databento_backfill as dbf

B = "bento-568968024170-us-east-2-an"; PFX = "nymex/nymex_cont/"
SCRATCH = os.environ.get("MON_SCRATCH", "/tmp/mon_scratch")
os.makedirs(SCRATCH, exist_ok=True)
s3 = boto3.client("s3", "us-east-2")
DOW = ("mon","tue","wed","thu","fri","sat","sun")

def log(m): print(f"[redl-mon] {m}", flush=True)

def corrupt_mondays():
    out = {}
    for root in ("NG", "CL"):
        ks, tok = [], None
        while True:
            kw = dict(Bucket=B, Prefix=PFX + f"{root}_", MaxKeys=1000)
            if tok: kw["ContinuationToken"] = tok
            r = s3.list_objects_v2(**kw); ks += [(o["Key"], o["Size"]) for o in r.get("Contents", [])]
            if r.get("IsTruncated"): tok = r["NextContinuationToken"]
            else: break
        days = []
        for k, sz in ks:
            m = re.search(r"_(\d{8})", k)
            if not m: continue
            d = m.group(1); dow = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday()
            if dow == 0 and sz < 5000:                       # Monday stub
                days.append(d)
        out[root] = sorted(set(days))
    return out

def repull(root, day):
    d = datetime.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    start = d.isoformat(); end = (d + datetime.timedelta(days=2)).isoformat()   # [Mon, Wed): Monday interior
    for g in glob.glob(os.path.join(SCRATCH, f"{root}_*.jsonl*")): os.remove(g)
    client = dbf._client()
    dbf.batch_pull(client, root, start, end, "mbp-10", max_cost=50.0, out_dir=SCRATCH, flush_dir=SCRATCH)
    gz = os.path.join(SCRATCH, f"{root}_{day}.jsonl.gz")
    if not os.path.exists(gz):
        log(f"FAIL {root} {day}: no Monday gz produced"); return False
    sz = os.path.getsize(gz)
    # sanity: count lines
    with gzip.open(gz, "rt") as fh:
        n = sum(1 for _ in fh)
    if sz < 1_000_000 or n < 10000:
        log(f"FAIL {root} {day}: still small ({sz}B, {n} rows) - NOT uploaded"); return False
    key = PFX + f"{root}_{day}_{DOW[0]}.jsonl.gz"
    s3.upload_file(gz, B, key)
    # remove the old date-only stub if it exists (legacy name)
    for legacy in (PFX + f"{root}_{day}.jsonl.gz",):
        try: s3.delete_object(Bucket=B, Key=legacy)
        except Exception: pass
    log(f"OK   {root} {day}: {sz/1e6:.1f}MB, {n} rows -> s3://{key}")
    for g in glob.glob(os.path.join(SCRATCH, f"{root}_*.jsonl*")): os.remove(g)
    return True

def main():
    cm = corrupt_mondays()
    tot = sum(len(v) for v in cm.values())
    log(f"corrupt Mondays: NG={len(cm['NG'])} CL={len(cm['CL'])} (total {tot}) -> {cm}")
    ok = 0
    for root in ("NG", "CL"):
        for day in cm[root]:
            try:
                if repull(root, day): ok += 1
            except Exception as e:
                log(f"ERR  {root} {day}: {e}")
    log(f"DONE re-download: {ok}/{tot} Mondays repaired")

if __name__ == "__main__":
    main()
