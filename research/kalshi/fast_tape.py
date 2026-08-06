"""fast_tape.py — fast trade-price path loader for the continuous NG walk (S95 rebuild of the lost
scratchpad fast_score2). The full MBP-10 decode via event_move_baseline.load_cont_day is ~54s/day (it
json-parses every book update); the continuous curve only needs the TRADE (ts, price) path. This
prefilters raw lines by the trade marker ('"action": "T"') BEFORE json.loads, then caches the decoded
path as npz so repeat passes are instant.

  ts, price = fast_load_day("NG", "20250908")     # bare YYYYMMDD; _mon/dow S3 name resolved by emb

Persisted (committed) so it is never lost to an ephemeral scratchpad again. Raw S3 data is never mutated.
"""
import os, json, gzip
import numpy as np
import event_move_baseline as emb

_TRADE_MARK = '"action": "T"'


def _npz_path(root: str, day: str) -> str:
    return os.path.join(emb.CONT_DIR, f"{root}_{day}_tp.npz")


def fast_load_day(root: str, day: str, source: str = "s3"):
    """Return (ts, price) float arrays of the day's trade prints, strictly ts-advancing. npz-cached."""
    cache = _npz_path(root, day)
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        z = np.load(cache)
        return z["ts"], z["price"]
    gz = emb._s3_fetch_cont_gz(root, day) if source == "s3" else emb._cont_local_path(root, day)
    ts_l, px_l = [], []
    op = gzip.open if gz.endswith(".gz") else open
    with op(gz, "rt") as fh:
        for line in fh:
            if _TRADE_MARK not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("action") not in ("T", "Trade", "t"):
                continue
            p = r.get("price")
            t = r.get("ts")
            if p is None or t is None:
                continue
            ts_l.append(float(t)); px_l.append(float(p))
    if not ts_l:
        ts, px = np.array([]), np.array([])
    else:
        ts = np.asarray(ts_l, float); px = np.asarray(px_l, float)
        order = np.argsort(ts, kind="stable"); ts, px = ts[order], px[order]
        keep = np.concatenate([np.diff(ts) > 0, [True]])   # dedup exact-dup ts (keep last)
        ts, px = ts[keep], px[keep]
    np.savez(cache, ts=ts, price=px)
    return ts, px


if __name__ == "__main__":
    import sys, time
    root, day = sys.argv[1], sys.argv[2]
    t0 = time.time()
    ts, px = fast_load_day(root, day)
    print(f"{root} {day}: {len(px)} trades in {time.time()-t0:.1f}s  open={px[0]:.3f} close={px[-1]:.3f}"
          if len(px) else f"{root} {day}: EMPTY")
