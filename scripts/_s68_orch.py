"""Sequentially grade a list of coins, each when its tape reaches >=27d and is size-stable."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odcore.io import load_bins
import scripts._s68_drive as D
import scripts._s68_tune_kraken as T

def ready(coin, min_days=27.0):
    f = os.path.join(T.REALBINS, f"{coin}_kraken_bins.json")
    if not os.path.exists(f):
        return False
    try:
        s1 = os.path.getsize(f); n = len(load_bins(f))
    except Exception:
        return False
    if n / 86400.0 < min_days:
        return False
    time.sleep(25)
    return os.path.getsize(f) == s1

def main():
    coins = sys.argv[1:]
    done = set()
    t_start = time.time()
    while len(done) < len(coins):
        progressed = False
        for c in coins:
            if c in done:
                continue
            if ready(c):
                print(f"=== grading {c} ===", flush=True)
                r = D.drive(c)
                with open(os.path.join(T.ROOT, "scripts", "_s68_results.json"), "a") as f:
                    f.write(json.dumps(r, default=str) + "\n")
                done.add(c); progressed = True
        if not progressed:
            if time.time() - t_start > 7200:
                print("ORCH TIMEOUT; done=", done); break
            time.sleep(30)
    print("ORCHDONE", sorted(done))

if __name__ == "__main__":
    main()
