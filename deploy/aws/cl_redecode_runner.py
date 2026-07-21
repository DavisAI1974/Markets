#!/usr/bin/env python3
"""S101 ops: CL Mondays FREE REDECODE (Greg S100: "CL Mondays = FREE REDECODE, window closes
~Aug 12-14"). The S99 Monday-stub find: 51 CL Mondays in s3://bento-.../nymex/nymex_cont/ are
~455-byte flush-bug stubs (the pre-S92 'wb' clobber). The paid data is intact inside Databento's
ALREADY-DONE batch jobs (verified: 69 done CL.v.0 mbp-10 jobs, expirations 2026-08-12..14, every
stub Monday covered by a weekly job) - so the repair is $0: re-download the done job's DBN file(s)
for the Monday, re-decode with the S90/S92-fixed writer, verify, upload over the stub.

Runs DETACHED on box i-08cee7171c0a76a04 (nohup; does not touch the running pull_rest_2026 job -
distinct scratch under /opt/cl_redecode/). Needs databento_backfill.py alongside and the env from
/etc/markets/pull.env (DATABENTO_API_KEY + AWS creds).

Guards:
  * $0 only - never submits a batch job; only list_jobs/list_files/download of DONE jobs.
  * CL only - never touches NG keys.
  * Resumable - a Monday whose S3 object is already >= 5KB is skipped (re-run safe).
  * Never overwrites a good file - re-checks the S3 size immediately before upload; uploads only
    if the current object is still a <5KB stub AND the rebuilt gz is >= 1MB and >= 10k rows.
  * A Monday with no covering done job is HELD (logged NOJOB) - paid re-pull is Greg's decision.

Log: local /opt/cl_redecode/cl_redecode.log, pushed to s3://<bucket>/logs/cl_redecode.log after
every Monday.
"""
import datetime
import glob
import gzip
import os
import re
import shutil
import sys
import tempfile
import traceback

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import databento_backfill as dbf                                   # noqa: E402

B = "bento-568968024170-us-east-2-an"
PFX = "nymex/nymex_cont/"
LOG_KEY = "logs/cl_redecode.log"
BASE = os.environ.get("CLRD_BASE", "/opt/cl_redecode")
SCRATCH = os.path.join(BASE, "scratch")
LOG_PATH = os.path.join(BASE, "cl_redecode.log")                   # nohup redirects here too
STUB = 5000                                                        # <5KB = the flush-bug stub
MIN_BYTES = 1_000_000                                              # repaired gz must clear these
MIN_ROWS = 10_000

s3 = boto3.client("s3", "us-east-2")


def log(m):
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    print(f"[cl-redecode] {ts} {m}", flush=True)


def push_log():
    try:
        s3.upload_file(LOG_PATH, B, LOG_KEY)
    except Exception as e:                                         # noqa: BLE001
        print(f"[cl-redecode] log upload failed: {e}", flush=True)


def _cl_keys():
    ks, tok = [], None
    while True:
        kw = dict(Bucket=B, Prefix=PFX + "CL_", MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        ks += [(o["Key"], o["Size"]) for o in r.get("Contents", [])]
        if r.get("IsTruncated"):
            tok = r["NextContinuationToken"]
        else:
            return ks


def stub_mondays():
    """Self-discovering: every CL Monday whose (largest) S3 object is < STUB bytes."""
    best = {}
    for k, sz in _cl_keys():
        m = re.search(r"CL_(\d{8})", k)
        if not m:
            continue
        d = m.group(1)
        if datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() == 0:
            best[d] = max(best.get(d, 0), sz)
    return sorted(d for d, sz in best.items() if sz < STUB)


def monday_size(day):
    r = s3.list_objects_v2(Bucket=B, Prefix=PFX + f"CL_{day}")
    szs = [o["Size"] for o in r.get("Contents", [])]
    return max(szs) if szs else 0


def cl_done_jobs(client):
    """(start, end, jid) spans of every DONE GLBX mbp-10 CL batch job. Metadata only, $0."""
    spans = []
    for j in client.batch.list_jobs():
        if (j.get("dataset") != "GLBX.MDP3" or j.get("schema") != "mbp-10"
                or j.get("state") != "done"):
            continue
        s = j.get("symbols")
        sym = str(s[0] if isinstance(s, (list, tuple)) else s).upper()
        if not sym.startswith("CL"):
            continue
        spans.append((str(j.get("start"))[:10], str(j.get("end"))[:10], j.get("id")))
    return spans


def job_for(day, spans):
    """Smallest-span done job containing the Monday (weekly preferred over monthly)."""
    iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    cov = [(st, en, jid) for st, en, jid in spans if st <= iso < en]
    if not cov:
        return None
    cov.sort(key=lambda t: (datetime.date.fromisoformat(t[1])
                            - datetime.date.fromisoformat(t[0])).days)
    return cov[0][2]


def repair(client, day, jid):
    """Rebuild one Monday from its done job. Fast path: download ONLY the DBN file(s) dated the
    Monday (+ the next day if the job has one, for the S90 boundary stragglers), decode, gzip.
    Fallback: whole-job re-decode via dbf._download_decode_flush (the S90/S92-fixed flush).
    Returns True iff a verified repaired file was uploaded."""
    import databento as db
    d = datetime.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    want = {day, (d + datetime.timedelta(days=1)).strftime("%Y%m%d")}
    jdir = tempfile.mkdtemp(prefix=f"clrd_{day}_", dir=SCRATCH)
    try:
        files = []
        try:
            for fobj in dbf._retry(lambda: client.batch.list_files(jid)):
                fn = fobj.get("filename", "")
                m = re.search(r"(\d{8})", fn)
                if fn.endswith(".dbn.zst") and m and m.group(1) in want:
                    files.append(fn)
        except Exception as e:                                     # noqa: BLE001
            log(f"list_files failed for {jid}: {type(e).__name__} {e}; whole-job fallback")

        gz = None
        if files:
            for fn in sorted(files):
                dbf._retry(lambda: client.batch.download(
                    job_id=jid, output_dir=jdir, filename_to_download=fn))
            n = 0
            for p in sorted(glob.glob(os.path.join(jdir, "**", "*.dbn.zst"), recursive=True)):
                df = db.DBNStore.from_file(p).to_df()
                if len(df):
                    n += dbf._write_mbp10_df(df, "CL", jdir)
                os.remove(p)
            raw = os.path.join(jdir, f"CL_{day}.jsonl")
            if os.path.exists(raw):
                gz = raw + ".gz"
                with open(raw, "rb") as src, gzip.open(gz, "wb", compresslevel=6) as dst:
                    shutil.copyfileobj(src, dst)
                os.remove(raw)
            log(f"{day}: per-file decode ({len(files)} dbn, {n} rows total)")
        if gz is None:
            # whole-job re-decode with the fixed flush; the Monday gz lands in gzdir
            gzdir = os.path.join(jdir, "gz")
            n = dbf._download_decode_flush(client, jid, "CL", "mbp-10",
                                           out_dir=jdir, flush_dir=gzdir)
            cand = os.path.join(gzdir, f"CL_{day}.jsonl.gz")
            gz = cand if os.path.exists(cand) else None
            log(f"{day}: whole-job decode job {jid} ({n} rows total)")
        if gz is None or not os.path.exists(gz):
            log(f"FAIL {day}: no Monday file produced from job {jid}")
            return False

        sz = os.path.getsize(gz)
        with gzip.open(gz, "rt") as fh:
            rows = sum(1 for _ in fh)
        if sz < MIN_BYTES or rows < MIN_ROWS:
            log(f"FAIL {day}: rebuilt file too small ({sz}B, {rows} rows) - NOT uploaded")
            return False
        cur = monday_size(day)                                     # never overwrite a good file
        if cur >= STUB:
            log(f"SKIP {day}: S3 object now {cur}B (>= {STUB}) - repaired elsewhere, NOT uploaded")
            return False
        key = PFX + f"CL_{day}_mon.jsonl.gz"
        s3.upload_file(gz, B, key)
        try:                                                       # drop the legacy date-only stub
            legacy = PFX + f"CL_{day}.jsonl.gz"
            r = s3.list_objects_v2(Bucket=B, Prefix=legacy, MaxKeys=1)
            if any(o["Key"] == legacy for o in r.get("Contents", [])):
                s3.delete_object(Bucket=B, Key=legacy)
        except Exception:                                          # noqa: BLE001
            pass
        log(f"OK   {day}: {sz / 1e6:.1f}MB, {rows} rows -> s3://{B}/{key} (was {cur}B stub)")
        return True
    finally:
        shutil.rmtree(jdir, ignore_errors=True)


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    log("START CL Monday free redecode (S101)")
    client = dbf._client()                                         # needs DATABENTO_API_KEY
    days = stub_mondays()
    log(f"stub Mondays (<{STUB}B) found: {len(days)}: {days}")
    spans = cl_done_jobs(client)
    log(f"done CL mbp-10 batch jobs available: {len(spans)}")
    push_log()
    ok = skip = held = fail = 0
    for day in days:
        if monday_size(day) >= STUB:
            log(f"SKIP {day}: already repaired on S3")
            skip += 1
            continue
        jid = job_for(day, spans)
        if jid is None:
            log(f"NOJOB {day}: no done job covers it - HELD (paid re-pull is Greg's call)")
            held += 1
            push_log()
            continue
        try:
            if repair(client, day, jid):
                ok += 1
            else:
                fail += 1
        except Exception as e:                                     # noqa: BLE001
            log(f"ERR  {day}: {type(e).__name__} {e}")
            log(traceback.format_exc(limit=5))
            fail += 1
        push_log()
    log(f"DONE: {ok} repaired, {skip} skipped, {held} held (no job), {fail} failed "
        f"of {len(days)} stub Mondays")
    push_log()


if __name__ == "__main__":
    main()
