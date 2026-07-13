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


# ---- day-of-week labeling + trading-calendar-aware stub detection (Greg S92) -----------------------
# Files are named {ROOT}_{YYYYMMDD}_{Ddd}.jsonl.gz so the day of week is IN the name. A <5KB gz is a
# flush-bug STUB only on a day that SHOULD carry a full session; weekends (Sat closed / Sun evening-only)
# and full-closure CME energy holidays are legitimately tiny and must NOT block a week/month from being
# marked done. (The S91 bug: every 7-day span contains a Saturday, so `any stub` meant NO week ever got a
# marker -> resume defeated + JOB-1's "53 markers" unreachable.)
import datetime as _dt
import re as _re

_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# CME Globex ENERGY (NYMEX CL/NG) FULL-closure dates (no session at all) for the 2025-07..2026-07 window.
# Half-days (Thanksgiving-eve/-after, Christmas-eve, etc.) still produce full-size files, so only complete
# closures are listed. MLK/Presidents/Columbus/Veterans are shortened, not closed -> not listed.
CME_FULL_CLOSED = {
    "20250704", "20250901", "20251127", "20251225",                          # 2025 H2
    "20260101", "20260403", "20260525", "20260619", "20260703",              # 2026 H1 (Jul4 obs Fri Jul3)
}


def _dow(day: str) -> str:
    """YYYYMMDD -> lowercase 3-letter day of week, e.g. 20260112 -> 'mon'."""
    d = _dt.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    return _DOW[d.weekday()].lower()


def _day_from_name(fname: str):
    """{ROOT}_{YYYYMMDD}[_dow].jsonl.gz -> 'YYYYMMDD' (or None). Accepts both the S92 dow-labeled name and
    the legacy date-only name, so the reader/skip logic works across the transition."""
    m = _re.match(r"^[A-Za-z0-9]+_(\d{8})(?:_[a-z]{3})?\.jsonl\.gz$", os.path.basename(fname), _re.IGNORECASE)
    return m.group(1) if m else None


def _dow_name(fname: str) -> str:
    """{ROOT}_{YYYYMMDD}.jsonl.gz -> {ROOT}_{YYYYMMDD}_{dow}.jsonl.gz (date + day-of-week, both present;
    sortable; idempotent; dow derived from the date). e.g. CL_20260112.jsonl.gz -> CL_20260112_mon.jsonl.gz."""
    base = os.path.basename(fname)
    day = _day_from_name(base)
    if not day:
        return base
    root = base.split("_", 1)[0]
    return f"{root}_{day}_{_dow(day)}.jsonl.gz"


def _expected_full(day: str) -> bool:
    """True iff this UTC day should carry a full trading session (a <5KB file on it => a flush stub).
    Sat = closed; Sun = evening-only (not required-full); weekday full-closure holiday = legitimately ~empty."""
    d = _dt.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    if d.weekday() >= 5:            # Sat(5) / Sun(6)
        return False
    return day not in CME_FULL_CLOSED


def _days_in_span(ws: str, we: str):
    """UTC 'YYYYMMDD' day strings in [ws, we) (ws/we are ISO 'YYYY-MM-DD')."""
    a = _dt.date.fromisoformat(ws); b = _dt.date.fromisoformat(we)
    out = []
    while a < b:
        out.append(a.strftime("%Y%m%d")); a += _dt.timedelta(days=1)
    return out


def _selftest():
    # naming carries BOTH the date and the day of week; idempotent; parseable back to YYYYMMDD
    assert _dow_name("CL_20260112.jsonl.gz") == "CL_20260112_mon.jsonl.gz", _dow_name("CL_20260112.jsonl.gz")
    assert _dow_name("NG_20250705.jsonl.gz") == "NG_20250705_sat.jsonl.gz"
    assert _dow_name("CL_20260112_mon.jsonl.gz") == "CL_20260112_mon.jsonl.gz"   # idempotent
    assert _day_from_name("CL_20260112_mon.jsonl.gz") == "20260112"
    assert _day_from_name("CL_20260112.jsonl.gz") == "20260112"                  # legacy still parses
    # trading calendar: weekdays required-full; weekends + full-closure holidays not
    assert _expected_full("20250707") and _expected_full("20250711")            # Mon, Fri
    assert not _expected_full("20250705") and not _expected_full("20250706")    # Sat, Sun
    assert not _expected_full("20250704") and not _expected_full("20251225")    # Jul4, Christmas (closed)
    # the S91-bug week: 07-01..07-08 contained Sat 07-05 -> old code saw '1 stub' and NEVER marked it.
    exp = [d for d in _days_in_span("2025-07-01", "2025-07-08") if _expected_full(d)]
    assert exp == ["20250701", "20250702", "20250703", "20250707"], exp        # Jul4 Fri + weekend excluded
    print("[selftest] PASS  date+dow naming + trading-calendar stub/marker logic")
    print("  example names:", _dow_name("CL_20260112.jsonl.gz"), "|", _dow_name("NG_20250705.jsonl.gz"))
    print("  week 2025-07-01..08 required-full weekdays (weekend/Jul4 excluded):", exp)


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
    """CLEAN-present only: every EXPECTED-FULL trading day of the month is present and >= STUB_BYTES.
    Weekends + full-closure holidays are not required (they are legitimately tiny). A month that is empty,
    missing a weekday, or stub-corrupt on a weekday (the S90 flush bug) is treated as ABSENT so it is
    RE-PULLED, never silently skipped. Names may be DOW-labeled or legacy date-only."""
    import calendar
    objs = _s3_days_present(s3, bucket, prefix, f"{root}_{y}{m:02d}")   # YYYYMMDD intact -> month-prefix works
    if not objs:
        return False
    have = {}
    for key, sz in objs:
        d = _day_from_name(key)
        if d:
            have[d] = sz
    exp = [f"{y}{m:02d}{dd:02d}" for dd in range(1, calendar.monthrange(y, m)[1] + 1)]
    exp = [d for d in exp if _expected_full(d)]
    if not exp:
        return False
    return all(d in have and have[d] >= STUB_BYTES for d in exp)


def _week_marker_key(prefix, root, ws):
    return (f"{prefix}/" if prefix else "") + f"nymex_cont/_done/{root}_{ws}.done"


def _week_done(s3, bucket, prefix, root, ws):
    """A week is DONE iff its marker exists (written only after a clean per-week upload). Bulletproof
    resume: a partial/failed week has no marker -> re-pulled."""
    r = s3.list_objects_v2(Bucket=bucket, Prefix=_week_marker_key(prefix, root, ws), MaxKeys=1)
    return r.get("KeyCount", 0) > 0


def _publish_all_s3(s3, bucket, prefix):
    """Upload every gz in BRANCH_DIR to nymex_cont/ under a DOW-LABELED key ({ROOT}_{YYYYMMDD}_{Ddd}.jsonl.gz),
    delete local. Returns {day: size} of what was uploaded (caller decides cleanliness by trading calendar)."""
    gz = sorted(glob.glob(os.path.join(BRANCH_DIR, "*.jsonl.gz")))
    uploaded = {}
    for g in gz:
        day = _day_from_name(g)
        key = _s3_key(prefix, _dow_name(g))
        sz = os.path.getsize(g)
        for attempt in range(4):
            try:
                s3.upload_file(g, bucket, key); break
            except Exception as e:
                print(f"[pull_year] s3 upload retry {attempt} {key}: {e}", flush=True)
        if day:
            uploaded[day] = sz
        os.remove(g)
    return uploaded


def _reconcile_names(s3, bucket, prefix, start, end):
    """One-time repair for a corpus written by pre-S92 code (date-only names, no/partial markers): rename
    every nymex_cont/{ROOT}_{YYYYMMDD}.jsonl.gz object to its DOW-labeled name, then write a week marker for
    every CLEAN week (all expected-full weekdays present & full). Idempotent + safe to re-run. No re-pull,
    no Databento cost. Run AFTER the box's pull has finished (avoid renaming files it is still writing)."""
    have, curkey = {}, {}
    for root in ("CL", "NG"):
        for key, sz in _s3_days_present(s3, bucket, prefix, f"{root}_"):
            day = _day_from_name(key)
            if not day:
                continue
            have[(root, day)] = sz
            curkey[(root, day)] = key
    renamed = 0
    for (root, day), key in list(curkey.items()):
        want = _s3_key(prefix, _dow_name(os.path.basename(key)))
        if key.endswith(os.path.basename(want)):
            continue                                          # already DOW-labeled
        s3.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=want)
        s3.delete_object(Bucket=bucket, Key=key)
        renamed += 1
    marked = 0
    for (ws, we) in _week_spans(start, end):
        for root in ("CL", "NG"):
            exp = [d for d in _days_in_span(ws, we) if _expected_full(d)]
            clean = bool(exp) and all((root, d) in have and have[(root, d)] >= STUB_BYTES for d in exp)
            if clean and not _week_done(s3, bucket, prefix, root, ws):
                s3.put_object(Bucket=bucket, Key=_week_marker_key(prefix, root, ws), Body=b"ok")
                marked += 1
    print(f"[reconcile] renamed {renamed} objects to DOW names, wrote {marked} new week markers", flush=True)
    return renamed, marked


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
    ap.add_argument("--reconcile-names", action="store_true",
                    help="One-time repair (S3 only, no re-pull / no Databento cost): rename existing date-only "
                         "nymex_cont/ objects to DOW-labeled names {ROOT}_{YYYYMMDD}_{Ddd}.jsonl.gz and write "
                         "week markers for every clean week. Run AFTER a pre-S92 box has finished its pull.")
    ap.add_argument("--selftest", action="store_true",
                    help="Validate the DOW-naming + trading-calendar stub logic (no network); print + exit.")
    args = ap.parse_args()

    if args.selftest:
        _selftest(); return

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

    if args.reconcile_names:
        if not is_s3:
            sys.exit("[pull_year] --reconcile-names requires an s3:// dest")
        _reconcile_names(s3, bucket, prefix, args.start, args.end)
        return

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
                uploaded = _publish_all_s3(s3, bucket, prefix)
                # CLEAN iff every expected-full weekday in [ws,we) is present and >= STUB_BYTES.
                # Weekends / full-closure holidays are not required (legitimately tiny), so they no longer
                # block the marker (the S91 bug). Mark done ONLY when clean.
                exp = [d for d in _days_in_span(ws, we) if _expected_full(d)]
                missing = [d for d in exp if d not in uploaded]
                stubs = [d for d in exp if d in uploaded and uploaded[d] < STUB_BYTES]
                if uploaded and not missing and not stubs:
                    s3.put_object(Bucket=bucket, Key=_week_marker_key(prefix, root, ws), Body=b"ok")
                    print(f"[pull_year] {root} week {ws} uploaded {len(uploaded)} gz, marked done "
                          f"(cum rows {total_rows})", flush=True)
                else:
                    print(f"[pull_year] {root} week {ws}: {len(uploaded)} gz, "
                          f"{len(stubs)} weekday-stubs {len(missing)} missing -> NOT marked (will re-pull)",
                          flush=True)
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
                key = _s3_key(prefix, _dow_name(g))           # DOW-labeled name (Greg S92)
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
