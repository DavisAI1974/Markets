"""_s60_absorption_wall.py — S60: RESOLVE the absorption/spoof candidate (dive chapter §3.5).

The first probe (_s60_absorption_probe.py) found the "no-response deep lean" class does NOT
reverse (absorption-exhaustion, the hypothesis) — it CONTINUES: SOL absorbed +5.81bp/300s,
z=+24 vs circular-shift null, real only on SOL (the one cell with a real 0.68bp spread; the
tickless BTC/ETH z's are divide-by-~0; DOGE/XRP null). So the class is DELAYED PRICE
DISCOVERY, not absorption. Two controls decide what it actually is:

CONTROL 1 — LATENCY (kill or confirm cross-venue lag): does a Binance lean/return at the SAME
  wall-clock second already explain the Coinbase "continuation"? If Binance has already moved in
  the leaned direction, the Coinbase forward move is a CATCH-UP (a maker-quoting lead on the slow
  venue), NOT a taker edge and NOT absorption. Regress the Coinbase no-response forward move on
  the contemporaneous Binance signed trailing return; report R^2 / beta.

CONTROL 2 — THE WALL (the real absorption test; needs book depth trades cannot give): true
  absorption = deep lean diving INTO large resting depth on the RESISTING side (bid depth for a
  sell-lean, ask depth for a buy-lean). Split deep-lean events by resisting-side depth (deep wall
  vs thin) and test whether the DEEP-WALL class REVERSES (absorption exhausts) while the THIN class
  CONTINUES (latency/discovery). This is the mechanism-distinct test; a circular-shift null on each.

VERDICT + WIRE-IN at the bottom: if the deep-wall class reverses beyond latency, a clean detector
is emitted with its deploy spec; if not, the honest finding (latency lead) is recorded with its
own maker-quoting spec. Leakage note: every read is trailing/contemporaneous or forward-only; the
event mask uses data <= t and the forward return uses data > t (no look-ahead into the decision).
"""
import gzip
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                    # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps         # noqa: E402
from odcore.flip_detector import lean_series                          # noqa: E402

W_SEC = 300          # trailing lean window, wall-clock seconds
L = 0.5              # deep-lean threshold
R_LO = 0.25          # |trailing response| < R_LO half-spreads = "no response" (absorption candidate)
H_SEC = 300          # forward horizon, wall-clock seconds (the +5.81bp claim's horizon)
N_SHUF = 200         # circular-shift null replicas
RNG = np.random.default_rng(11)

BIN_SYM = {"sol": "SOLUSDT", "eth": "ETHUSDT", "btc": "BTCUSDT",
           "doge": "DOGEUSDT", "xrp": "XRPUSDT"}


# ----------------------------------------------------------------- loaders
def load_bin(path):
    """Binance 1-sec bins -> (t0, mid, lean-ready buy/sell) on a dense 1s grid."""
    with open(path) as f:
        d = json.load(f)
    ts = np.array(sorted(float(k) for k in d.keys()))
    t0, t1 = ts[0], ts[-1]
    n = int(t1 - t0) + 1
    mid = np.zeros(n); buy = np.zeros(n); sell = np.zeros(n); have = np.zeros(n, bool)
    for k, v in d.items():
        i = int(float(k) - t0)
        mid[i] = v["mid"]; buy[i] = v["buy"]; sell[i] = v["sell"]; have[i] = True
    idx = np.where(have, np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    mid = mid[idx]
    first = np.argmax(have)
    mid[:first] = mid[first]
    return t0, mid, buy, sell


def cb_events(coin):
    """Coinbase book -> the absorbed (no-response deep-lean) events + all deep events, with the
    resisting-side depth at each event and the forward H return signed by the lean."""
    p = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    raw = load_book(p)
    _, g = build_channels(p, 1, 20, raw=raw)          # K=1 top-of-book depth in bidK[1]/askK[1]
    mid = np.asarray(g["mid"], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    bid1 = np.asarray(g["bidK"][1], float); ask1 = np.asarray(g["askK"][1], float)
    n = len(mid)
    t0_cb = float(raw["ts"][0])
    grid = (float(raw["ts"][-1]) - t0_cb) / max(n - 1, 1)     # sec/cell (~0.1)
    Wc = max(1, int(round(W_SEC / grid)))
    Hc = max(1, int(round(H_SEC / grid)))
    hs = median_spread_bps(p, raw=raw) / 2.0
    lean = lean_series(buy, sell, Wc)
    sgn = np.sign(lean)

    trail = np.full(n, np.nan); trail[Wc:] = (mid[Wc:] - mid[:-Wc]) / mid[:-Wc] * 1e4
    resp = sgn * trail / hs                                   # trailing response in half-spreads
    fwd = np.full(n, np.nan)
    fwd[:n - Hc] = sgn[:n - Hc] * (mid[Hc:] - mid[:n - Hc]) / mid[:n - Hc] * 1e4  # forward, lean-signed

    deep = (np.abs(lean) >= L) & ~np.isnan(resp) & ~np.isnan(fwd)
    absorbed = deep & (np.abs(resp) < R_LO)
    # resisting-side depth: sellers (lean<0) fight the BID wall; buyers (lean>0) fight the ASK wall
    resist = np.where(lean < 0, bid1, ask1)

    idx = np.flatnonzero(absorbed)
    return dict(coin=coin, n=n, t0=t0_cb, grid=grid, Wc=Wc, Hc=Hc, hs=hs,
                lean=lean, sgn=sgn, fwd=fwd, resist=resist, trail=trail,
                absorbed_idx=idx, deep=int(deep.sum()), absorbed=int(absorbed.sum()))


# ----------------------------------------------------------------- nulls
def shift_null(mask_idx, fwd, n):
    """Circular-shift the forward series under a fixed event mask -> null mean + z of the real mean."""
    real = np.nanmean(fwd[mask_idx])
    nulls = np.empty(N_SHUF)
    for j in range(N_SHUF):
        s = int(RNG.integers(n // 8, 7 * n // 8))
        fs = np.roll(fwd, s)
        nulls[j] = np.nanmean(fs[mask_idx])
    z = (real - nulls.mean()) / (nulls.std() + 1e-9)
    return float(real), float(nulls.mean()), float(z)


# ----------------------------------------------------------------- CONTROL 1: latency
def control_latency(coin, ev):
    """Regress the Coinbase absorbed forward move on the CONTEMPORANEOUS Binance signed trailing
    return (both signed by the Coinbase lean). High R^2 => the 'continuation' is Binance catch-up."""
    bpath = f"/tmp/backfill/{BIN_SYM[coin]}_30d_bins.json"
    if not os.path.exists(bpath):
        return None
    bt0, bmid, bbuy, bsell = load_bin(bpath)
    blean = lean_series(bbuy, bsell, W_SEC)                   # 1s grid -> W_SEC cells = W_SEC s
    nb = len(bmid)
    btrail = np.full(nb, np.nan); btrail[W_SEC:] = (bmid[W_SEC:] - bmid[:-W_SEC]) / bmid[:-W_SEC] * 1e4

    idx = ev["absorbed_idx"]
    # each CB event -> wall-clock time -> Binance 1s bin
    t_ev = ev["t0"] + idx * ev["grid"]
    bi = np.round(t_ev - bt0).astype(int)
    ok = (bi >= 0) & (bi < nb)
    idx = idx[ok]; bi = bi[ok]
    cb_sgn = ev["sgn"][idx]
    cb_fwd = ev["fwd"][idx]
    # Binance signals signed by the CB lean direction
    bin_trail_signed = cb_sgn * btrail[bi]                    # has Binance already moved our way?
    bin_lean_signed = cb_sgn * blean[bi]                     # is Binance leaning our way now?
    m = ~np.isnan(cb_fwd) & ~np.isnan(bin_trail_signed)
    cb_fwd = cb_fwd[m]; bin_trail_signed = bin_trail_signed[m]; bin_lean_signed = bin_lean_signed[m]
    if len(cb_fwd) < 50:
        return dict(n=len(cb_fwd), note="too few aligned")
    # OLS: cb_fwd ~ a + b * bin_trail_signed
    X = np.column_stack([np.ones(len(cb_fwd)), bin_trail_signed])
    beta, *_ = np.linalg.lstsq(X, cb_fwd, rcond=None)
    pred = X @ beta
    ss_res = np.sum((cb_fwd - pred) ** 2); ss_tot = np.sum((cb_fwd - cb_fwd.mean()) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-12)
    # residual intercept = CB forward move NOT explained by Binance-already-moved
    resid_mean = float(np.mean(cb_fwd - beta[1] * bin_trail_signed))
    return dict(n=len(cb_fwd), r2=float(r2), beta_trail=float(beta[1]), intercept=float(beta[0]),
                resid_mean=resid_mean, cb_fwd_mean=float(cb_fwd.mean()),
                bin_trail_signed_mean=float(bin_trail_signed.mean()),
                bin_lean_signed_mean=float(bin_lean_signed.mean()),
                corr_binlean=float(np.corrcoef(bin_lean_signed, cb_fwd)[0, 1]))


# ----------------------------------------------------------------- CONTROL 2: the wall
def control_wall(coin, ev):
    """Split absorbed events by resisting-side depth (deep wall vs thin). Absorption -> deep-wall
    reverses (fwd<0); latency/discovery -> both continue (fwd>0), deep-wall no different."""
    idx = ev["absorbed_idx"]
    if len(idx) < 100:
        return dict(n=len(idx), note="too few absorbed")
    resist = ev["resist"][idx]
    fwd = ev["fwd"]
    med = np.median(resist)
    deep_wall = idx[resist >= med]
    thin = idx[resist < med]
    rw, nw, zw = shift_null(deep_wall, fwd, ev["n"])
    rt, nt, zt = shift_null(thin, fwd, ev["n"])
    # depth quartiles for the trend
    q = np.quantile(resist, [0.25, 0.5, 0.75])
    quart = []
    edges = [-np.inf, q[0], q[1], q[2], np.inf]
    for a, b in zip(edges[:-1], edges[1:]):
        sub = idx[(resist >= a) & (resist < b)]
        if len(sub) > 20:
            quart.append((len(sub), float(np.nanmean(fwd[sub]))))
    return dict(n=len(idx), med_depth=float(med),
                deep_wall=dict(n=len(deep_wall), fwd=rw, null=nw, z=zw),
                thin=dict(n=len(thin), fwd=rt, null=nt, z=zt),
                quartiles=quart)


# ----------------------------------------------------------------- deploy detector (emitted if it survives)
def absorption_wall_signal(mid, buy, sell, bid1, ask1, hs, grid,
                           W_sec=W_SEC, L_=L, r_lo=R_LO, wall_pct=75.0):
    """CAUSAL per-cell detector (data <= t only). Returns pos in {-1,0,+1}: fire the REVERSAL side
    (-sign(lean)) when a deep no-response lean dives into a resisting wall above the wall_pct-ile.
    Emitted ONLY as a spec; deploy is gated on control_wall clearing the latency control (see VERDICT)."""
    Wc = max(1, int(round(W_sec / grid)))
    n = len(mid)
    lean = lean_series(np.asarray(buy, float), np.asarray(sell, float), Wc)
    sgn = np.sign(lean)
    trail = np.full(n, np.nan); trail[Wc:] = (mid[Wc:] - mid[:-Wc]) / mid[:-Wc] * 1e4
    resp = sgn * trail / hs
    resist = np.where(lean < 0, bid1, ask1)
    # causal running wall threshold (expanding percentile) to avoid look-ahead
    pos = np.zeros(n, np.int8)
    thr = np.nan
    for t in range(Wc, n):
        if t % 500 == 0 and t > Wc:
            thr = np.nanpercentile(resist[Wc:t], wall_pct)   # expanding, past-only
        if np.isnan(thr):
            continue
        if abs(lean[t]) >= L_ and not np.isnan(resp[t]) and abs(resp[t]) < r_lo and resist[t] >= thr:
            pos[t] = -int(sgn[t])                            # reversal side (absorption exhausts)
    return pos


def main():
    print("=== S60 ABSORPTION/WALL RESOLUTION — Coinbase books + Binance latency control ===")
    print(f"W={W_SEC}s deep|lean|>={L}  no-response |resp|<{R_LO}hs  fwd horizon {H_SEC}s (lean-signed)\n")
    out = {}
    for coin in ("sol", "doge", "xrp", "eth", "btc"):
        if not os.path.exists(f"/tmp/{coin}_coinbase_book.jsonl.gz"):
            continue
        ev = cb_events(coin)
        print(f"[{coin}] n={ev['n']} grid={ev['grid']:.3f}s hs={ev['hs']:.3f}bp "
              f"deep={ev['deep']} absorbed={ev['absorbed']}")
        lat = control_latency(coin, ev)
        wall = control_wall(coin, ev)
        out[coin] = dict(hs=ev["hs"], absorbed=ev["absorbed"], latency=lat, wall=wall)
        if lat and "r2" in lat:
            print(f"  C1 LATENCY: CB absorbed fwd mean {lat['cb_fwd_mean']:+.2f}bp | "
                  f"Binance explains R^2={lat['r2']:.3f} (beta_trail {lat['beta_trail']:+.3f}); "
                  f"residual (Binance-removed) {lat['resid_mean']:+.2f}bp | "
                  f"corr(bin_lean, cb_fwd) {lat['corr_binlean']:+.3f}")
            print(f"             Binance already-moved-our-way (trailing signed) {lat['bin_trail_signed_mean']:+.2f}bp; "
                  f"leaning-our-way {lat['bin_lean_signed_mean']:+.3f}")
        elif lat:
            print(f"  C1 LATENCY: {lat.get('note')}")
        if wall and "deep_wall" in wall:
            dw, th = wall["deep_wall"], wall["thin"]
            print(f"  C2 WALL: DEEP-wall fwd {dw['fwd']:+.2f}bp (null {dw['null']:+.2f} z={dw['z']:+.1f}, n={dw['n']})  "
                  f"| THIN fwd {th['fwd']:+.2f}bp (null {th['null']:+.2f} z={th['z']:+.1f}, n={th['n']})")
            qs = "  ".join(f"{n}:{v:+.1f}" for n, v in wall["quartiles"])
            print(f"           depth quartiles (n:fwd bp): {qs}")
        elif wall:
            print(f"  C2 WALL: {wall.get('note')}")
        print()
    # results go to the session scratchpad, never the repo tree
    scratch = "/tmp/claude-0/-home-user-Markets/d39da483-99f1-5e95-bee0-9f382094f1ac/scratchpad/dive_lab"
    outp = os.path.join(scratch if os.path.isdir(scratch) else ".", "absorption_wall_results.json")
    with open(outp, "w") as f:
        json.dump(out, f, indent=1, default=float)
    return out


if __name__ == "__main__":
    main()
