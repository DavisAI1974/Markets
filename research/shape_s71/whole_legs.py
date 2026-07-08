"""S74-corrected WHOLE-LEG extractor. Reuses the LIVE decision path (run_kraken_cell via arc_gate).
Builds, per leg, TWO whole limbs split at the fire (onset t=0):
  PRE-FIRE  = natural-birth .. onset   (lookback to the leg's ignition, bounded by prior-leg close / book start)
  TAIL      = onset .. ACTUAL close_idx (variable length; NOT the +60s clip)
Time is normalized per limb (scale-free); AMPLITUDE is kept in NATIVE arc units [-1,1] so the born-depth
(start-y) tell is preserved. Caches to /tmp/kbook/{coin}_whole.npz. Extraction only; no fits here.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, CPS)
SMOOTH_SEC = 20
LOOKBACK = 150 * CPS          # up to 150s back to find natural birth (past the old 45s clip)
NRS = 100                     # resample points per limb over normalized time
COINS = ["sol", "btc", "eth", "xrp"]


def ignition_idx(seg):
    """seg = signed arc from birth-window..onset (onset last). Birth = bottom of the FINAL hole before
    the rise into onset. Same construction as natural_extent.py."""
    m = np.minimum.accumulate(seg[::-1])[::-1]     # m[i] = min(seg[i:])
    cand = np.where(seg <= m + 1e-9)[0]
    ig = cand[0] if len(cand) else 0
    ig = ig + int(np.argmin(seg[ig:]))
    return ig


def resample(limb, n=NRS):
    L = len(limb)
    xs = np.linspace(0, 1, n)
    return np.interp(xs, np.linspace(0, 1, L), limb)


def extract(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw)/2.0; N = len(mid); hours = N*0.1/3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    legs = sorted(res.legs, key=lambda z: int(z.open_idx))
    pre_arcs, tail_arcs = [], []
    pre_start, pre_end, tail_start, tail_end = [], [], [], []
    pre_ext, tail_ext, net, dur, side = [], [], [], [], []
    birth_clip = []
    prev_close = -1
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        if c <= o:
            continue
        lo = max(0, o - LOOKBACK, prev_close + 1)
        # PRE-FIRE limb: birth..onset
        seg = imb[lo:o+1] * s
        if len(seg) < 30:
            prev_close = c
            continue
        ig = ignition_idx(seg)
        pre = seg[ig:]
        if len(pre) < 12:
            pre = seg[-12:]; ig = len(seg) - 12
        # TAIL limb: onset..actual close
        tail = imb[o:c+1] * s
        if len(tail) < 4:
            prev_close = c
            continue
        prev_close = c
        pre_arcs.append(resample(pre)); tail_arcs.append(resample(tail))
        pre_start.append(float(pre[0])); pre_end.append(float(pre[-1]))
        tail_start.append(float(tail[0])); tail_end.append(float(tail[-1]))
        pre_ext.append((len(pre)-1)*0.1); tail_ext.append((len(tail)-1)*0.1)
        net.append(float(l.net_bps)); dur.append((c-o)*0.1); side.append(s)
        birth_clip.append(1 if (lo > 0 and ig == 0) else 0)
    return dict(pre_arcs=np.array(pre_arcs), tail_arcs=np.array(tail_arcs),
                pre_start=np.array(pre_start), pre_end=np.array(pre_end),
                tail_start=np.array(tail_start), tail_end=np.array(tail_end),
                pre_ext=np.array(pre_ext), tail_ext=np.array(tail_ext),
                net=np.array(net), dur=np.array(dur), side=np.array(side),
                birth_clip=np.array(birth_clip), hours=hours)


if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    for coin in coins:
        print(f"... loading+running {coin} (live executor) ...", flush=True)
        d = extract(coin)
        np.savez(f"/tmp/kbook/{coin}_whole.npz", **d)
        n = len(d["net"]); win = (d["net"] > 0)
        print(f"  {coin}: legs={n} hours={d['hours']:.1f} base-win%={win.mean()*100:.1f} "
              f"med-dur={np.median(d['dur']):.0f}s pre-ext-med={np.median(d['pre_ext']):.0f}s "
              f"tail-ext-med={np.median(d['tail_ext']):.0f}s birth-clip={d['birth_clip'].mean()*100:.0f}%", flush=True)
    print("DONE", flush=True)
