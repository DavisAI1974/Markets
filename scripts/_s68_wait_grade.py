"""Wait until a coin tape is ready (>=27d and size-stable) then grade it via _s68_drive."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odcore.io import load_bins
import scripts._s68_drive as D
import scripts._s68_tune_kraken as T
import json

def ready(coin, min_days=27.0):
    f = os.path.join(T.REALBINS, f"{coin}_kraken_bins.json")
    if not os.path.exists(f):
        return False
    try:
        s1 = os.path.getsize(f)
        n = len(load_bins(f))
    except Exception:
        return False
    if n / 86400.0 < min_days:
        return False
    time.sleep(25)
    return os.path.getsize(f) == s1  # size stable => done writing

def main():
    coin = sys.argv[1]
    waited = 0
    while not ready(coin):
        time.sleep(20); waited += 45
        if waited > 3000:
            print(f"[{coin}] TIMEOUT waiting for tape"); return
    r = D.drive(coin)
    with open(os.path.join(T.ROOT, "scripts", "_s68_results.json"), "a") as f:
        f.write(json.dumps(r, default=str) + "\n")
    print("READYDONE", coin)

if __name__ == "__main__":
    main()
