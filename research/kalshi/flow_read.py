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
    # S108 THE B_SHARE NORMALIZATION DEFECT. Every *_b_share below divides by TOTAL volume, but the
    # tape carries a third side value ('N', neither B nor A) worth 13.49% of volume across the 223
    # sessions on disk. Unsided volume lands in the DENOMINATOR and can never land in the numerator, so
    # every b_share is biased LOW - and not by a constant: unsided_frac runs 3.7% to 48.6%, the shift
    # is +0.092 mean on sd 0.045, and corr(as-computed, two-sided) is only 0.532. It is a noisy
    # downward-biased proxy, not a shifted coordinate.
    #
    # Measured consequence: as computed, session_b_share means 0.408 and clears 0.50 on 5 of 223
    # sessions (2.2%). Two-sided it means 0.4999 - dead on the 50/50 the physics requires - and clears
    # 0.50 on 107 of 223 (48.0%). The two disagree about which side of 0.50 a session sits on 45.7% of
    # the time. Any play gated on an ABSOLUTE 0.50 ('more buying than selling') is therefore reading a
    # bar that essentially never fires.
    #
    # ADDITIVE FIX, deliberately not a replacement: the *_two_sided series are served ALONGSIDE the
    # originals. Bars fitted EMPIRICALLY on the old series (0.463, 0.817, 0.55, 0.436, the thin-tape
    # quartile bars) were fitted where they are used and must keep reading the old field - silently
    # re-normalizing underneath them would break every one. Only THEORETICALLY-motivated bars, where
    # 0.50 is meant to mean 'balance', should move, and that is a brain proposal, not a code change.
    # session_signed_flow is NOT affected: (sd*sz).sum() with sd in {-1,0,+1} gives unsided trades zero
    # weight and has no denominator, so the blind's signed-flow channel was always clean.
    sides = sz[sd != 0].sum()
    unsided = float(tot - sides)
    _two = lambda num, den: (round(float(num) / den, 3) if den > 0 else None)
    big_sides = sz[bigs & (sd != 0)].sum()
    t0, t1 = ts[0], ts[-1]; span = max(t1 - t0, 1.0)
    ph_sf, ph_bs, ph_bs2 = [], [], []
    for k in range(3):
        m = (ts >= t0 + span * k / 3) & (ts < t0 + span * (k + 1) / 3) if k < 2 else (ts >= t0 + span * 2 / 3)
        v = sz[m].sum() or 1.0
        ph_sf.append(int(round(float((sd[m] * sz[m]).sum()))))
        ph_bs.append(round(float(sz[m & (sd > 0)].sum()) / v, 3))
        ph_bs2.append(_two(sz[m & (sd > 0)].sum(), sz[m & (sd != 0)].sum()))
    return {"n_trades": int(n), "volume_lots": int(tot), "trades_per_min": round(n / (span / 60), 1),
            "session_signed_flow": int(round(float((sd * sz).sum()))),
            "session_b_share": round(float(buys) / tot, 3),
            "phase_signed_flow": ph_sf, "phase_b_share": ph_bs,     # UNBALANCED SIDES by phase (open/mid/close)
            "big_prints_n": int(bigs.sum()),
            "big_print_b_share": round(float(big_b) / big_tot, 3) if bigs.any() else None,
            # S108 additive two-sided series - see the normalization note above. Same measurements with
            # unsided volume removed from the denominator, so 0.50 means balance and nothing else moves.
            "session_b_share_two_sided": _two(buys, sides),
            "phase_b_share_two_sided": ph_bs2,
            "big_print_b_share_two_sided": (_two(big_b, big_sides) if bigs.any() else None),
            "unsided_volume_frac": round(unsided / tot, 3),
            "b_share_basis_note": ("*_b_share divide by TOTAL volume and are biased LOW by the unsided "
                                   "share (13.49% of volume across 223 sessions, range 3.7-48.6%). "
                                   "*_two_sided divide by B+A only. An ABSOLUTE 0.50 bar is only "
                                   "meaningful on the two-sided series; bars fitted empirically on the "
                                   "original series must keep reading the original series."),
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
