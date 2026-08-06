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


def _api_key() -> str:
    # S115 (audit D1-04): creds.py is the one resolver - this file read ONLY scratchpad/aws.env,
    # while the bootstrap wrote the Databento key to bento.env, so the smoke test could never
    # find it on a fresh container by construction.
    import creds
    return creds.get("DATABENTO_API_KEY")


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
    lats = []
    deadline = time.time() + a.seconds
    try:
        for rec in client:
            now_ns = time.time_ns()
            # ONLY TradeMsg counts - the gateway sends SymbolMappingMsg for every child of the
            # parent on subscribe (dozens of records, ts_event set, price/size None); counting
            # those reports a working feed without ever seeing a trade (S100 lesson).
            if isinstance(rec, db.TradeMsg):
                lat_ms = (now_ns - rec.ts_event) / 1e6
                lats.append(lat_ms)
                print(f"  trade px={rec.price / 1e9:.3f} size={rec.size} "
                      f"latency={lat_ms:.1f}ms instrument={rec.instrument_id}")
                n += 1
            if time.time() > deadline or n >= 40:
                break
    finally:
        client.stop()
    if lats:
        lats.sort()
        print(f"[live-smoke] latency ms: min={lats[0]:.1f} med={lats[len(lats) // 2]:.1f} "
              f"p90={lats[int(len(lats) * 0.9)]:.1f} max={lats[-1]:.1f} over n={n}")
    print(f"[live-smoke] done: {n} trades seen. "
          f"{'LIVE PLAN WORKING' if n else 'no prints (market closed or thin) - subscribe succeeded'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
