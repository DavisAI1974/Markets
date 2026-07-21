"""flow_read.py - the full NON-PRICE microstructure flow read for a session (S105 data doctrine).
Gives the blind the KITCHEN SINK of order-flow FORCES, masked only on price:
  - MBO trade-flow (from the nymex_cont trade tape): signed-flow imbalance + UNBALANCED SIDES by phase,
    buy-share, big-print imbalance, trade intensity, leg count. NON-PRICE (no net/close/levels).
  - L1 book (from ng_l1 quotes): quote imbalance (bid_sz vs ask_sz = resting-liquidity lean, a DIFFERENT
    unbalanced-sides than aggressor flow), spread in ticks (relative), quote intensity. NON-PRICE
    (no absolute bid/ask LEVELS).

DELIBERATELY NOT here: the absorption/divergence VERDICT (= signed flow vs PRICE change) - that needs the
price and is refine-only. The blind gets the raw flow and combines it with its OWN price forecast to
detect divergence itself (that is the sharpening - it learns to read the forces, not the answer).
"""
import os, gzip, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CONT_DIRS = (os.path.join(REPO, "data", "nymex_cont_n0"), os.path.join(REPO, "data", "nymex_cont_n1"))
L1_DIR = os.path.join(REPO, "data", "ng_l1")
TICK = 0.001


def _load_trades(ymd):
    best = None
    for d in CONT_DIRS:
        p = os.path.join(d, f"NG_{ymd}.jsonl.gz")
        if not os.path.exists(p):
            continue
        ts, sz, sd = [], [], []
        with gzip.open(p, "rt") as fh:
            for line in fh:
                if '"action": "T"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("action") != "T" or r.get("price") is None:
                    continue
                t = float(r["ts"]); t = t / 1e9 if t > 1e15 else t
                ts.append(t); sz.append(float(r.get("size") or 0))
                sd.append(1 if r.get("side") == "B" else (-1 if r.get("side") == "A" else 0))
        if ts and (best is None or len(ts) > best[0]):
            best = (len(ts), np.array(ts), np.array(sz), np.array(sd))
    return best


def mbo_flow(ymd):
    """NON-PRICE trade-flow read: signed-flow imbalance + unbalanced sides by phase (thirds)."""
    b = _load_trades(ymd)
    if b is None:
        return None
    n, ts, sz, sd = b
    tot = sz.sum() or 1.0
    buys = sz[sd > 0].sum()
    bigs = sz >= 25
    big_b = sz[bigs & (sd > 0)].sum(); big_tot = sz[bigs].sum() or 1.0
    t0, t1 = ts[0], ts[-1]; span = max(t1 - t0, 1.0)
    ph_sf, ph_bs = [], []
    for k in range(3):
        m = (ts >= t0 + span * k / 3) & (ts < t0 + span * (k + 1) / 3) if k < 2 else (ts >= t0 + span * 2 / 3)
        v = sz[m].sum() or 1.0
        ph_sf.append(int(round(float((sd[m] * sz[m]).sum()))))
        ph_bs.append(round(float(sz[m & (sd > 0)].sum()) / v, 3))
    return {"n_trades": int(n), "volume_lots": int(tot), "trades_per_min": round(n / (span / 60), 1),
            "session_signed_flow": int(round(float((sd * sz).sum()))),
            "session_b_share": round(float(buys) / tot, 3),
            "phase_signed_flow": ph_sf, "phase_b_share": ph_bs,     # UNBALANCED SIDES by phase (open/mid/close)
            "big_prints_n": int(bigs.sum()),
            "big_print_b_share": round(float(big_b) / big_tot, 3) if bigs.any() else None,
            "note": "NON-PRICE trade-flow forces; no net/close/level. Unbalanced sides = phase_signed_flow/b_share."}


def l1_flow(ymd):
    """NON-PRICE L1 book read: quote imbalance (bid_sz vs ask_sz) + spread in ticks. No absolute levels."""
    p = os.path.join(L1_DIR, f"NG_{ymd}.jsonl.gz")
    if not os.path.exists(p):
        return None
    bimb, spr = [], []
    with gzip.open(p, "rt") as fh:
        for line in fh:
            if '"bid_sz"' not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            bs, as_ = r.get("bid_sz"), r.get("ask_sz")
            bp, ap = r.get("bid_px"), r.get("ask_px")
            if bs is None or as_ is None or (bs + as_) == 0:
                continue
            bimb.append(bs / (bs + as_))
            if bp and ap and ap > bp:
                spr.append(round((ap - bp) / TICK))
    if not bimb:
        return None
    bimb = np.array(bimb); spr = np.array(spr) if spr else np.array([np.nan])
    return {"quote_bid_share": round(float(bimb.mean()), 3),          # >0.5 = book leans BID (resting buyers)
            "quote_bid_share_p25_p75": [round(float(np.percentile(bimb, 25)), 3), round(float(np.percentile(bimb, 75)), 3)],
            "spread_ticks_med": round(float(np.nanmedian(spr)), 1),
            "quote_updates": int(len(bimb)),
            "note": "NON-PRICE L1 book forces; quote_bid_share = resting-liquidity lean (distinct from aggressor flow); spread relative (ticks), no absolute levels."}


def session_flow(ymd):
    m = mbo_flow(ymd); l = l1_flow(ymd)
    if m is None and l is None:
        return None
    out = {"session": ymd, "never_masked": True}
    if m:
        out.update(m)
    if l:
        out["l1_book"] = l
    return out


if __name__ == "__main__":
    import sys
    for ymd in sys.argv[1:]:
        f = session_flow(ymd)
        print(ymd, json.dumps(f, indent=1) if f else "NO DATA")
