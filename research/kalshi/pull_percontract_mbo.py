#!/usr/bin/env python3
"""pull_percontract_mbo.py - pull RAW per-contract MBO (.dbn.zst, one file/day) for a specific NG monthly
contract and publish to s3://BUCKET/nymex/ng_mbo_<contract>/, matching the existing ng_mbo / ng_mbo_ngj26
stores byte-format-exactly (raw DBN zstd, NG_<YYYYMMDD>.dbn.zst, no decode).

Why raw (not batch_pull's decoded JSONL): the MBO stores keep ALL raw per the S88/S89 doctrine; the
per-contract legs (ng_mbo_ngj26) are raw .dbn.zst. The year-pull (ng_mbo) is NG.n.0 continuation - the
WRONG leg near a Kalshi roll; this tool pulls the true per-contract leg (raw_symbol) so seam groups get a
clean leg (G15 pattern: NGJ26 pre-roll + NGK26 post-roll).

Idempotent: a day already fat on S3 is skipped. Cost-gated: estimate_cost vs --max-cost before submit.
Per-day upload + size log. _DONE marker on full success.

Usage:
    DATABENTO_API_KEY=db-... AWS_...  python research/kalshi/pull_percontract_mbo.py \
        --symbol NGK26 --start 2026-03-13 --end 2026-04-29 --max-cost 5.0
"""
import argparse, glob, os, re, sys, tempfile, shutil
import boto3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import databento_backfill as dbf

BUCKET = "bento-568968024170-us-east-2-an"
MIN_FAT = 50_000  # bytes; a real MBO day is >>50KB. deferred-month early days are smaller but non-empty.


def log(m): print(f"[pc-mbo] {m}", flush=True)


def s3c():
    return boto3.client("s3", "us-east-2")


def existing_fat_days(s3, prefix):
    out = set()
    tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=prefix)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            m = re.search(r"_(\d{8})\.dbn\.zst$", o["Key"])
            if m and o["Size"] >= MIN_FAT:
                out.add(m.group(1))
        if r.get("IsTruncated"):
            tok = r["NextContinuationToken"]
        else:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="raw contract, e.g. NGK26")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD exclusive-ish (interior last day)")
    ap.add_argument("--max-cost", type=float, default=5.0)
    ap.add_argument("--poll-s", type=float, default=20.0)
    ap.add_argument("--timeout-s", type=float, default=5400.0)
    ap.add_argument("--resume-job", default=None,
                    help="existing batch job id to resume (skip submit; avoids a duplicate charge)")
    a = ap.parse_args()

    sym = a.symbol.upper()
    prefix = f"nymex/ng_mbo_{sym.lower()}/"
    s3 = s3c()
    have = existing_fat_days(s3, prefix)
    if have:
        log(f"already fat on S3 ({len(have)} days): will skip {sorted(have)}")

    client = dbf._client()
    import time

    if a.resume_job:
        jid = a.resume_job
        st = "queued"
        log(f"RESUME job id={jid} (no submit, no new charge)")
    else:
        # cost gate
        cost = client.metadata.get_cost(dataset=dbf.DATASET, symbols=[sym], stype_in="raw_symbol",
                                        schema="mbo", start=a.start, end=a.end)
        log(f"est cost {sym} mbo {a.start}..{a.end}: ${cost:.4f} (max ${a.max_cost:.2f})")
        if cost > a.max_cost:
            raise SystemExit(f"[pc-mbo] ABORT: est ${cost:.4f} exceeds --max-cost ${a.max_cost:.2f}")

        # submit batch job, raw_symbol, per-day split, raw dbn/zstd (no decode)
        job = dbf._retry(lambda: client.batch.submit_job(
            dataset=dbf.DATASET, symbols=[sym], stype_in="raw_symbol", schema="mbo",
            start=a.start, end=a.end, encoding="dbn", compression="zstd", split_duration="day"))
        jid = job.get("id")
        st = job.get("state")
        log(f"batch job submitted id={jid} state={st}")
    waited = 0.0
    while waited < a.timeout_s:
        det = dbf._retry(lambda: client.batch.get_job_details(jid))
        st = det.get("state")
        if st == "done":
            break
        if st in ("expired", "failed"):
            raise SystemExit(f"[pc-mbo] batch job {jid} {st}")
        time.sleep(a.poll_s); waited += a.poll_s
    if st != "done":
        raise SystemExit(f"[pc-mbo] batch job {jid} not done after {int(waited)}s (state {st})")
    log(f"job done; downloading raw .dbn.zst")

    tmp = tempfile.mkdtemp(prefix="pcmbo_")
    up = skip = empty = 0
    try:
        dbf._retry(lambda: client.batch.download(jid, output_dir=tmp))
        files = sorted(glob.glob(os.path.join(tmp, "**", "*.dbn.zst"), recursive=True))
        log(f"downloaded {len(files)} raw day-files")
        for p in files:
            m = re.search(r"(\d{8})", os.path.basename(p))
            if not m:
                log(f"  SKIP (no date in name): {os.path.basename(p)}")
                continue
            day = m.group(1)
            sz = os.path.getsize(p)
            if day in have:
                skip += 1
                continue
            if sz < 1000:  # truly empty non-trading artifact
                empty += 1
                log(f"  {day}: {sz}B empty/no-trade -> not uploaded")
                continue
            key = f"{prefix}NG_{day}.dbn.zst"
            s3.upload_file(p, BUCKET, key)
            up += 1
            log(f"  {day}: {sz/1e6:.2f} MB -> s3://{BUCKET}/{key}")
        # _DONE marker
        s3.put_object(Bucket=BUCKET, Key=f"{prefix}_DONE", Body=b"")
        log(f"DONE {sym}: uploaded {up}, skipped {skip}, empty {empty}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
