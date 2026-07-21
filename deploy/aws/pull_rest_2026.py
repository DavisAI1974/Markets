"""pull_rest_2026.py - DURABLE box job (S101): backfill the rest-of-year Databento layers, Mar 2026 -> present.

Greg 2026-07-21: "set up downloads for the rest of the data that we're going to need for the rest of
the year and start it... in background and not tethered to one session." Runs on the us-east-2 box
under nohup; resumable (skip-if-on-S3); logs stream to S3; cost-guarded (est. $0.00 - all inside the
Bento Standard included window; hard-aborts if the running estimate exceeds $25).

JOBS (data that exists today; forward accrual is the live collectors' job):
  A. NG.n.0 + NG.n.1 continuous TRADES, 2026-03-14 -> today-1, per-UTC-day jsonl.gz matching the
     walk-store record format exactly ({ts s-float, symbol, src, instrument_id, action:"T", side,
     price $, size}) -> s3 nymex/nymex_cont_n0/ and nymex_cont_n1/. (Mar 1-13 already materialized
     in-session from the raw year store, verified single-instrument.)
  B. NG.FUT parent STATISTICS + DEFINITION, 2026-03-01 -> present, monthly raw .dbn.zst ->
     s3 nymex/contract_structure/raw_2026ext/   (contract_structure store build = session work)
  C. ON.OPT + LNE.OPT parent STATISTICS + DEFINITION, 2026-03-01 -> present, monthly raw .dbn.zst ->
     s3 options_ng/raw/ext_2026/                (options surface build = session work)

git = CODE, S3 = DATA. Raw kept raw. Zero synthetic anything. MOS/weather stays session-side
(free IEM pulls via the existing builders; nothing to pre-download beyond realtime).
"""
import datetime as dt
import gzip
import json
import os
import time

import boto3
import databento as dbn

BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"
COST_ABORT_USD = 25.0
LOG_KEY = "logs/pull_rest_2026.log"
DONE_KEY = "logs/pull_rest_2026.DONE"

s3 = boto3.client("s3", region_name=REGION)
hist = dbn.Historical()          # DATABENTO_API_KEY from env
_log_lines = []
_cost_running = 0.0


def log(msg):
    line = f"{dt.datetime.utcnow().isoformat()}Z {msg}"
    print(line, flush=True)
    _log_lines.append(line)
    if len(_log_lines) % 10 == 0:
        _flush_log()


def _flush_log():
    s3.put_object(Bucket=BUCKET, Key=LOG_KEY, Body="\n".join(_log_lines).encode())


def _exists(key):
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except Exception:
        return False


def _guard(desc, **kw):
    global _cost_running
    est = hist.metadata.get_cost(dataset="GLBX.MDP3", **kw)
    _cost_running += est
    log(f"cost {desc}: ${est:.2f} (running ${_cost_running:.2f})")
    if _cost_running > COST_ABORT_USD:
        log(f"ABORT: running cost estimate ${_cost_running:.2f} > guard ${COST_ABORT_USD}")
        _flush_log()
        raise SystemExit(2)


def job_a_trades():
    end = dt.date.today() - dt.timedelta(days=1)
    day = dt.date(2026, 3, 1)      # S101 audit fix: n1 Mar 1-13 was never pulled and the in-session
                                   # n0 March copies never reached S3 - start at Mar 1, skip-if-exists dedups
    while day <= end:
        if day.weekday() == 5:                     # Saturday: no UTC-day file in the store
            day += dt.timedelta(days=1)
            continue
        for sym, prefix in (("NG.n.0", "nymex/nymex_cont_n0"), ("NG.n.1", "nymex/nymex_cont_n1")):
            d8 = day.strftime("%Y%m%d")
            key = f"{prefix}/NG_{d8}.jsonl.gz"
            if _exists(key):
                continue
            start = f"{day.isoformat()}T00:00:00+00:00"
            stop = f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00+00:00"
            try:
                _guard(f"trades {sym} {d8}", schema="trades", symbols=[sym],
                       stype_in="continuous", start=start, end=stop)
                store = hist.timeseries.get_range(dataset="GLBX.MDP3", schema="trades",
                                                  symbols=[sym], stype_in="continuous",
                                                  start=start, end=stop)
                n = 0
                local = f"/tmp/NG_{d8}_{sym.replace('.', '_')}.jsonl.gz"
                with gzip.open(local, "wt") as fh:
                    for r in store:
                        fh.write(json.dumps({
                            "ts": r.ts_event * 1e-9, "symbol": sym, "src": "databento_trades",
                            "instrument_id": r.instrument_id, "action": "T",
                            "side": str(r.side), "price": r.price * 1e-9, "size": r.size}) + "\n")
                        n += 1
                if n == 0:
                    os.remove(local)
                    log(f"A {sym} {d8}: 0 records (holiday/empty) - no file written")
                    continue
                s3.upload_file(local, BUCKET, key)
                os.remove(local)
                log(f"A {sym} {d8}: {n} trades -> s3://{BUCKET}/{key}")
            except SystemExit:
                raise
            except Exception as e:
                log(f"A {sym} {d8}: ERROR {type(e).__name__}: {str(e)[:150]}")
                time.sleep(5)
        day += dt.timedelta(days=1)


def _monthly_raw(symbols, schema, out_prefix, tag, first=dt.date(2026, 3, 1)):
    today = dt.date.today()
    m_start = first
    while m_start < today:
        nxt = (m_start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        m_end = min(nxt, today)
        mm = m_start.strftime("%Y%m")
        key = f"{out_prefix}/{tag}_{schema}_{mm}.dbn.zst"
        if _exists(key):
            m_start = nxt
            continue
        try:
            _guard(f"{tag} {schema} {mm}", schema=schema, symbols=symbols,
                   stype_in="parent", start=m_start.isoformat(), end=m_end.isoformat())
            local = f"/tmp/{tag}_{schema}_{mm}.dbn.zst"
            hist.timeseries.get_range(dataset="GLBX.MDP3", schema=schema, symbols=symbols,
                                      stype_in="parent", start=m_start.isoformat(),
                                      end=m_end.isoformat(), path=local)
            s3.upload_file(local, BUCKET, key)
            sz = os.path.getsize(local)
            os.remove(local)
            log(f"{tag} {schema} {mm}: {sz/1e6:.1f}MB -> s3://{BUCKET}/{key}")
        except SystemExit:
            raise
        except Exception as e:
            log(f"{tag} {schema} {mm}: ERROR {type(e).__name__}: {str(e)[:150]}")
            time.sleep(5)
        m_start = nxt


def job_cl_trades():
    """S101 (Greg: free as long as we can): the CL walk-basis layer never existed - CL.n.0/n.1
    continuous trades, full year Jul 2025 -> present ($1.10 measured; pre-March outside the
    included window). Same store format as NG, new prefixes."""
    end = dt.date.today() - dt.timedelta(days=1)
    day = dt.date(2025, 7, 1)
    while day <= end:
        if day.weekday() == 5:
            day += dt.timedelta(days=1)
            continue
        for sym, prefix in (("CL.n.0", "nymex/cl_cont_n0"), ("CL.n.1", "nymex/cl_cont_n1")):
            d8 = day.strftime("%Y%m%d")
            key = f"{prefix}/CL_{d8}.jsonl.gz"
            if _exists(key):
                continue
            start = f"{day.isoformat()}T00:00:00+00:00"
            stop = f"{(day + dt.timedelta(days=1)).isoformat()}T00:00:00+00:00"
            try:
                _guard(f"trades {sym} {d8}", schema="trades", symbols=[sym],
                       stype_in="continuous", start=start, end=stop)
                store = hist.timeseries.get_range(dataset="GLBX.MDP3", schema="trades",
                                                  symbols=[sym], stype_in="continuous",
                                                  start=start, end=stop)
                n = 0
                local = f"/tmp/CL_{d8}_{sym.replace('.', '_')}.jsonl.gz"
                with gzip.open(local, "wt") as fh:
                    for r in store:
                        fh.write(json.dumps({
                            "ts": r.ts_event * 1e-9, "symbol": sym, "src": "databento_trades",
                            "instrument_id": r.instrument_id, "action": "T",
                            "side": str(r.side), "price": r.price * 1e-9, "size": r.size}) + "\n")
                        n += 1
                if n == 0:
                    os.remove(local)
                    log(f"CL {sym} {d8}: 0 records (holiday/empty)")
                    continue
                s3.upload_file(local, BUCKET, key)
                os.remove(local)
                log(f"CL {sym} {d8}: {n} trades -> s3://{BUCKET}/{key}")
            except SystemExit:
                raise
            except Exception as e:
                log(f"CL {sym} {d8}: ERROR {type(e).__name__}: {str(e)[:150]}")
                time.sleep(5)
        day += dt.timedelta(days=1)


def main():
    log("pull_rest_2026 START")
    job_a_trades()
    for schema in ("statistics", "definition"):
        _monthly_raw(["NG.FUT"], schema, "nymex/contract_structure/raw_2026ext", "ngfut")
    for schema in ("statistics", "definition"):
        _monthly_raw(["ON.OPT"], schema, "options_ng/raw/ext_2026", "on")
        _monthly_raw(["LNE.OPT"], schema, "options_ng/raw/ext_2026", "lne")
    # CL layers (S101, Greg: grab everything free-while-free; $1.10 measured total)
    job_cl_trades()
    for schema in ("statistics", "definition"):
        _monthly_raw(["CL.FUT"], schema, "nymex/contract_structure_cl/raw", "clfut", first=dt.date(2025, 7, 1))
        _monthly_raw(["LO.OPT"], schema, "options_cl/raw", "lo", first=dt.date(2025, 7, 1))
    log(f"pull_rest_2026 DONE (total est. cost ${_cost_running:.2f})")
    _flush_log()
    s3.put_object(Bucket=BUCKET, Key=DONE_KEY, Body=b"done")


if __name__ == "__main__":
    main()
