"""
databento_live_smoke.py - one-shot validation that the Databento LIVE plan is active (S99).

Run AFTER Greg activates the live plan on the Databento portal (Standard $179/mo). Uses the same
DATABENTO_API_KEY from scratchpad/aws.env that historical uses. Subscribes to GLBX.MDP3 NG futures
trades for ~20 seconds, prints each event with receive-side latency, then exits.

  python research/kalshi/databento_live_smoke.py            # NG parent, trades, 20s
  python research/kalshi/databento_live_smoke.py --seconds 60

Expected outcomes:
  - Plan ACTIVE + market open:   trade lines with sub-second gateway->here latency.
  - Plan ACTIVE + market closed: clean subscribe, no prints (run during RTH to see flow).
  - Plan INACTIVE:               an auth/entitlement error naming the live gateway - the check.
This is a smoke test, not a collector - the live collector design belongs to M5 (us-east-1 box).
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(_ROOT, "scratchpad", "aws.env")


def _api_key() -> str:
    for line in open(ENV_PATH):
        if line.startswith("DATABENTO_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABENTO_API_KEY not found in scratchpad/aws.env")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--symbols", default="NG.FUT", help="parent symbology (default NG.FUT)")
    a = ap.parse_args()
    import databento as db
    client = db.Live(key=_api_key())
    client.subscribe(dataset="GLBX.MDP3", schema="trades", stype_in="parent", symbols=a.symbols)
    print(f"[live-smoke] subscribed {a.symbols} trades on GLBX.MDP3 for {a.seconds}s "
          f"(utc {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')})")
    n = 0
    deadline = time.time() + a.seconds
    try:
        for rec in client:
            now_ns = time.time_ns()
            if hasattr(rec, "ts_event"):
                lat_ms = (now_ns - rec.ts_event) / 1e6
                px = getattr(rec, "price", None)
                print(f"  trade px={px / 1e9 if px else None} size={getattr(rec, 'size', None)} "
                      f"latency={lat_ms:.1f}ms instrument={getattr(rec, 'instrument_id', None)}")
                n += 1
            if time.time() > deadline or n >= 40:
                break
    finally:
        client.stop()
    print(f"[live-smoke] done: {n} trades seen. "
          f"{'LIVE PLAN WORKING' if n else 'no prints (market closed or thin) - subscribe succeeded'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
