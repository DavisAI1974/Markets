"""Box-side: 1 year of NG MBO (market-by-order, RAW DBN) history - S103.
Greg (S103): NG historical MBO only for now (defer CL + the $1,500/mo live-tier upgrade). MBO gives the
order-level events (add/modify/cancel/trade, queue position) that sharpen the under-used turn/far-side-
recruitment direction signal (see NG_FORECASTER_PROBLEM_MEMO_S103.md).

Same proven pattern as pull_l1_year.py: NG.n.0 continuation per-day, 2025-07-22..2026-07-20, skip-if-
exists, cost-guarded, UNTETHERED (nohup/detached, survives the SSM command + session). Stores RAW .dbn.zst
(lossless, all MBO fields; matches the live collector's DBN archives + the S88 raw-capture doctrine) to
s3 nymex/ng_mbo/. Historical MBO list cost ~$23 for the year (~$1.80/GB x ~14GB); GUARD hard-stops runaway.
"""
import datetime as dt, os
import boto3
import databento as db

B = "bento-568968024170-us-east-2-an"
PFX = "nymex/ng_mbo"
GUARD = 40.0  # $ hard stop (year ~ $23; margin over that, stops a runaway)
s3 = boto3.client("s3", region_name="us-east-2")
key = os.environ.get("DATABENTO_API_KEY") or open("/etc/markets/coach.env").read().split("DATABENTO_API_KEY=")[1].split()[0]
cli = db.Historical(key)
spent = 0.0
log = []


def put_log():
    s3.put_object(Bucket=B, Key="logs/ng_mbo_pull.log", Body="\n".join(log).encode())


day = dt.date(2025, 7, 22)
END = dt.date(2026, 7, 20)
while day <= END:
    if day.weekday() == 5:  # Saturday - no session
        day += dt.timedelta(days=1); continue
    d = day.strftime("%Y%m%d")
    out_key = f"{PFX}/NG_{d}.dbn.zst"
    try:
        s3.head_object(Bucket=B, Key=out_key)  # skip-if-exists = clean resume
        day += dt.timedelta(days=1); continue
    except Exception:
        pass
    nxt = (day + dt.timedelta(days=1)).isoformat()
    try:
        cost = cli.metadata.get_cost(dataset="GLBX.MDP3", symbols=["NG.n.0"], stype_in="continuous",
                                     schema="mbo", start=day.isoformat(), end=nxt)
        if spent + cost > GUARD:
            log.append(f"{d}: cost {cost:.2f} would breach guard ({spent:.2f} spent) - STOP"); put_log(); break
        data = cli.timeseries.get_range(dataset="GLBX.MDP3", schema="mbo", symbols=["NG.n.0"],
                                        stype_in="continuous", start=day.isoformat(), end=nxt)
        spent += cost
    except Exception as e:
        log.append(f"{d} ERR {e}"); put_log(); day += dt.timedelta(days=1); continue
    tmp = f"/tmp/ng_mbo_{d}.dbn.zst"
    try:
        data.to_file(tmp)                      # RAW DBN, lossless
        sz = os.path.getsize(tmp)
        if sz <= 40:                            # empty/holiday day (DBN header only)
            log.append(f"{d} empty ({spent:.2f})")
        else:
            s3.upload_file(tmp, B, out_key)
            log.append(f"{d}: {sz} bytes -> {out_key} (cost {cost:.4f}, running {spent:.2f})")
    except Exception as e:
        log.append(f"{d} WRITE ERR {e}"); put_log()
    finally:
        try: os.remove(tmp)
        except Exception: pass
    if len(log) % 10 == 0:
        put_log()
    day += dt.timedelta(days=1)
log.append(f"DONE spent {spent:.2f}")
put_log()
s3.put_object(Bucket=B, Key=f"{PFX}/_DONE", Body=b"done")
