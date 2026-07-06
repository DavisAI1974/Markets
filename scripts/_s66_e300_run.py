"""_s66_e300_run.py — drive the S62 E300 3-piece death-selector on a chosen bins dir /
coin subset, WITHOUT modifying the live research script (sim=live-code rule). Reports the
same AUC / base / 3piece / per-week grade for DOGE + XRP only (Greg S66).

Usage:
  python scripts/_s66_e300_run.py binance   # /tmp/backfill  DOGEUSDT/XRPUSDT, cross BTCUSDT
  python scripts/_s66_e300_run.py kraken    # /tmp/ktape     XDGUSD/XRPUSD,   cross XBTUSD
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _s62_e300_3piece as E  # noqa: E402

venue = sys.argv[1] if len(sys.argv) > 1 else "binance"
if venue == "binance":
    E.BINS = "/tmp/backfill"
    E.CELLS = [("doge", "DOGEUSDT", "BTCUSDT", 100.0), ("xrp", "XRPUSDT", "BTCUSDT", 80.0)]
elif venue == "kraken":
    E.BINS = "/tmp/ktape"
    E.CELLS = [("doge", "XDGUSD", "XBTUSD", 100.0), ("xrp", "XRPUSD", "XBTUSD", 80.0)]
else:
    raise SystemExit("venue must be binance|kraken")

print(f"# E300 death-selector — venue={venue}  bins={E.BINS}")
E.main()
