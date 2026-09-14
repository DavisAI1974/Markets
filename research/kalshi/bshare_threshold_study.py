"""Does the 0.55 big_print_b_share threshold need to float?

Reads every available session's SIZE-WEIGHTED big_print_b_share (the corrected series) and asks
whether a FIXED 0.55 bar means the same thing across season / activity regime. A fixed absolute bar
is only defensible if the series' DISPERSION is stable; if dispersion moves, 0.55 is a different
percentile in different regimes and the bar is silently re-calibrating itself.
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import flow_read

DIR = os.path.join(REPO, "data", "nymex_cont_n0")
days = sorted(f[3:11] for f in os.listdir(DIR) if f.startswith("NG_") and f.endswith(".jsonl.gz"))

rows = []
for ymd in days:
    try:
        m = flow_read.mbo_flow(ymd)
    except Exception:
        m = None
    if not m:
        continue
    bs = m.get("big_print_b_share")
    if bs is None:
        continue
    rows.append({"ymd": ymd, "month": ymd[:6], "mo": int(ymd[4:6]),
                 "bshare": bs, "sess_b": m.get("session_b_share"),
                 "n_trades": m.get("n_trades"), "vol": m.get("volume_lots"),
                 "bigs": m.get("big_prints_n")})

print(f"sessions with a usable big-print read: {len(rows)} of {len(days)}\n")

arr = np.array([r["bshare"] for r in rows])
print("=== POOLED (context only - never the final word) ===")
print(f"n={len(arr)}  mean={arr.mean():.3f}  sd={arr.std(ddof=1):.3f}  "
      f"p25={np.percentile(arr,25):.3f}  p50={np.percentile(arr,50):.3f}  p75={np.percentile(arr,75):.3f}")
print(f"share of sessions >= 0.55: {(arr>=0.55).mean()*100:.1f}%")
print(f"0.55 sits at the {(arr<0.55).mean()*100:.1f}th percentile pooled\n")

# --- season / month cells: each reported individually, per the per-cell doctrine ---
SEASON = {11: "winter", 12: "winter", 1: "winter", 2: "winter",
          3: "shoulder", 4: "shoulder", 5: "shoulder",
          6: "summer", 7: "summer", 8: "summer",
          9: "shoulder", 10: "shoulder"}

print("=== BY MONTH (the cell that matters for a seasonal bar) ===")
print(f"{'month':8} {'n':>4} {'mean':>7} {'sd':>7} {'p50':>7} {'p90':>7} {'>=0.55':>8} {'pctile of 0.55':>16}")
for mth in sorted({r['month'] for r in rows}):
    v = np.array([r["bshare"] for r in rows if r["month"] == mth])
    if len(v) < 3:
        continue
    pct = (v < 0.55).mean() * 100
    print(f"{mth:8} {len(v):>4} {v.mean():>7.3f} {v.std(ddof=1):>7.3f} {np.percentile(v,50):>7.3f} "
          f"{np.percentile(v,90):>7.3f} {(v>=0.55).mean()*100:>7.1f}% {pct:>15.1f}th")

print("\n=== BY SEASON ===")
print(f"{'season':10} {'n':>4} {'mean':>7} {'sd':>7} {'IQR':>7} {'>=0.55':>8} {'pctile of 0.55':>16}")
for s in ("winter", "shoulder", "summer"):
    v = np.array([r["bshare"] for r in rows if SEASON.get(r["mo"]) == s])
    if len(v) < 3:
        continue
    iqr = np.percentile(v, 75) - np.percentile(v, 25)
    print(f"{s:10} {len(v):>4} {v.mean():>7.3f} {v.std(ddof=1):>7.3f} {iqr:>7.3f} "
          f"{(v>=0.55).mean()*100:>7.1f}% {(v<0.55).mean()*100:>15.1f}th")

# --- does dispersion track ACTIVITY rather than calendar? big-print count is the sample size
#     behind the ratio, so a thin tape mechanically produces a wider b_share. ---
print("\n=== BY BIG-PRINT COUNT (the sample size behind the ratio) ===")
bigs = np.array([r["bigs"] for r in rows], float)
qs = np.percentile(bigs, [25, 50, 75])
print(f"big_prints_n quartile cuts: {qs.round(0)}")
print(f"{'bucket':22} {'n':>4} {'mean':>7} {'sd':>7} {'>=0.55':>8}")
buckets = [("q1 thinnest", bigs <= qs[0]), ("q2", (bigs > qs[0]) & (bigs <= qs[1])),
           ("q3", (bigs > qs[1]) & (bigs <= qs[2])), ("q4 thickest", bigs > qs[2])]
for name, m in buckets:
    v = arr[m]
    print(f"{name:22} {len(v):>4} {v.mean():>7.3f} {v.std(ddof=1):>7.3f} {(v>=0.55).mean()*100:>7.1f}%")

# correlation of |b_share - 0.5| with sample size: the pure-noise prediction
dev = np.abs(arr - 0.5)
r_bigs = np.corrcoef(dev, np.log(bigs + 1))[0, 1]
print(f"\ncorr( |b_share-0.5| , log big_prints_n ) = {r_bigs:+.3f}")
print("  (a strongly NEGATIVE value means extremity is largely a thin-sample artifact)")

# what a fixed 0.55 costs vs a per-season equal-rate bar
print("\n=== WHAT A FIXED 0.55 IMPLIES PER SEASON (fire rate) ===")
for s in ("winter", "shoulder", "summer"):
    v = np.array([r["bshare"] for r in rows if SEASON.get(r["mo"]) == s])
    if len(v) < 3:
        continue
    # bar that would fire on the same fraction as 0.55 does pooled
    target = (arr >= 0.55).mean()
    eq = np.percentile(v, 100 * (1 - target))
    print(f"  {s:10} fixed 0.55 fires {(v>=0.55).mean()*100:5.1f}%   "
          f"| an equal-rate bar would sit at {eq:.3f}")

json.dump(rows, open(os.path.join(HERE, "renders", "ng_refine_s95", "bshare_rows.json"), "w"))
print(f"\nrows -> bshare_rows.json ({len(rows)} sessions)")
