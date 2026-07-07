"""_s68_fp_kraken.py — S68 distinctive FINGERPRINTS on Kraken data, PER COIN (never pooled).

Three classes fingerprinted per coin:
  (1) LEGS   — winning vs losing legs of the LIVE stack (grade_coin_kraken::run_side path).
  (2) SLIDES — sustained DOWN price moves (price-zigzag down-swings >= theta).
  (3) HILLS  — sustained UP price moves (price-zigzag up-swings >= theta).

For every feature we separate CAUSAL (computed strictly from data <= the decision index — a real
pre-entry / at-onset signal, deployable) from DESCRIPTIVE (post-hoc, realized). Causal features are
gated by odcore.leakage.assert_no_leakage. Predictive claims get a circular-shift null.

Compute-judicious: cheap causal features are cumsum-vectorized; the heavy dipole/MI features slice a
600s window per event. No live-code edits, no commits.
"""
from __future__ import annotations
import argparse, os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odcore.io import load_bins                                    # noqa: E402
from odcore.flip_detector import lean_series, detect_flips        # noqa: E402
from odcore.platform import run_stream, WFLIP                     # noqa: E402
from odcore.info_dipole import signed_flow_features, divergence   # noqa: E402
from odcore.leakage import assert_no_leakage                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REALBINS = os.path.join(ROOT, "realbins")
CAP = 5000.0
WDIP = 600          # pre-event window for dipole/MI features
WPRE = 600          # pre-event window for cheap flow/price features
WVOLL = 3600        # long baseline for volume z-score
MAKER_FEE, TAKER_FEE = 0.0, 5.0

# per-coin deployed-ish config (side, rev). base = forward rev0.10 where unknown.
CFG = {"eth": (+1, 0.10), "btc": (+1, 0.10), "sol": (+1, 0.10),
       "doge": (+1, 0.30), "xrp": (+1, 0.20),
       "ada": (+1, 0.10), "sui": (+1, 0.10), "ltc": (-1, 0.30), "avax": (+1, 0.10)}


def load_coin(coin):
    p = os.path.join(REALBINS, f"{coin}_kraken_bins.json")
    if not os.path.exists(p):
        return None
    s = load_bins(p)
    mid = np.asarray(s.mid, float); buy = np.asarray(s.buy, float); sell = np.asarray(s.sell, float)
    hs = float(np.median((s.spread[mid > 0] / mid[mid > 0]) / 2.0) * 1e4) if np.any(mid > 0) else 0.0
    return dict(coin=coin, mid=mid, buy=buy, sell=sell, hs=hs, n=len(mid), hours=len(mid) / 3600.0,
                ts=np.asarray(s.ts, float))


# ---------------- fast AUC (Mann-Whitney) + Cohen d ----------------
def auc(x, y):
    """AUC of feature x separating y==1 (pos) from y==0. NaN-safe. Returns AUC in [0,1]."""
    x = np.asarray(x, float); y = np.asarray(y, int)
    m = np.isfinite(x)
    x, y = x[m], y[m]
    npos = int((y == 1).sum()); nneg = int((y == 0).sum())
    if npos == 0 or nneg == 0:
        return np.nan
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x)); ranks[order] = np.arange(1, len(x) + 1)
    # average ties
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    sr = np.zeros(len(cnt)); np.add.at(sr, inv, ranks); avg = sr / cnt
    ranks = avg[inv]
    sum_pos = ranks[y == 1].sum()
    return float((sum_pos - npos * (npos + 1) / 2.0) / (npos * nneg))


def cohen_d(x, y):
    x = np.asarray(x, float); y = np.asarray(y, int)
    m = np.isfinite(x); x, y = x[m], y[m]
    a, b = x[y == 1], x[y == 0]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    sp = np.sqrt(((len(a) - 1) * a.std(ddof=1) ** 2 + (len(b) - 1) * b.std(ddof=1) ** 2) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else np.nan


# ---------------- cumsum-vectorized cheap causal features ----------------
def cheap_features(bk):
    """Return dict of full-length causal arrays: imb_pre, pre_ret_bps, volz, lean, lean_slope."""
    buy, sell, mid = bk["buy"], bk["sell"], bk["mid"]
    n = bk["n"]; ix = np.arange(n)
    cb = np.concatenate([[0.0], np.cumsum(buy)]); cs = np.concatenate([[0.0], np.cumsum(sell)])
    lo = np.maximum(ix + 1 - WPRE, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    imb_pre = np.where(tot > 0, (B - S) / np.maximum(tot, 1e-9), 0.0)
    # price pre-return over WPRE (bps)
    j = np.maximum(ix - WPRE, 0)
    m0 = mid[j]; pre_ret = np.where((m0 > 0) & (mid > 0), np.log(np.maximum(mid, 1e-12) / np.maximum(m0, 1e-12)) * 1e4, 0.0)
    # volume z-score: short WPRE vol vs long WVOLL vol rate
    vol = buy + sell; cv = np.concatenate([[0.0], np.cumsum(vol)])
    loL = np.maximum(ix + 1 - WVOLL, 0)
    vshort = (cv[ix + 1] - cv[lo]) / WPRE
    vlong = (cv[ix + 1] - cv[loL]) / np.maximum(ix + 1 - loL, 1)
    volz = np.where(vlong > 0, vshort / np.maximum(vlong, 1e-12), 1.0)
    lean = lean_series(buy, sell, WFLIP)
    lean_slope = np.zeros(n); lean_slope[60:] = lean[60:] - lean[:-60]
    return dict(imb_pre=imb_pre, pre_ret=pre_ret, volz=volz, lean=lean, lean_slope=lean_slope)


def dipole_at(bk, i):
    """Heavy causal dipole/MI + divergence features at index i (window [i-WDIP,i])."""
    lo = max(0, i - WDIP)
    b = bk["buy"][lo:i]; s = bk["sell"][lo:i]
    out = {}
    ff = signed_flow_features(b, s)
    if ff:
        out.update({f"d_{k}": v for k, v in ff.items()})
    drift = bk["mid"][i] - bk["mid"][lo] if bk["mid"][lo] > 0 else 0.0
    dv = divergence(b, s, drift)
    if dv:
        out.update({"aligned_flow": dv["aligned_flow"], "opposing": float(dv["opposing"]),
                    "exhausting": float(dv["exhausting"]), "rev_conv": dv["reversal_conviction"]})
    return out


# ================= CLASS 1: winner vs loser legs =================
def run_legs(bk, side, rev):
    flips, _ = detect_flips(lean_series(bk["buy"], bk["sell"], WFLIP), rev)
    if side < 0:
        flips = [(c, p, -sg) for (c, p, sg) in flips]
    res, _ = run_stream(bk["mid"], bk["buy"], bk["sell"], flips, half_spread_bps=bk["hs"],
                        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, grace=300,
                        fill_model="front", close_improve_bps=0.5)
    return res.legs


def legs_fingerprint(bk):
    side, rev = CFG.get(bk["coin"], (+1, 0.10))
    legs = run_legs(bk, side, rev)
    legs = [l for l in legs if int(l.flip_idx) > WDIP + 61]
    if len(legs) < 60:
        return None
    ch = cheap_features(bk)
    y = np.array([1 if l.net_bps > 0 else 0 for l in legs], int)
    idx = np.array([int(l.flip_idx) for l in legs])
    sides = np.array([int(l.side) for l in legs])
    feats = {}
    feats["imb_pre_aligned"] = sides * ch["imb_pre"][idx]        # flow WITH the leg side, pre-entry
    feats["pre_ret_aligned"] = sides * ch["pre_ret"][idx]        # price move WITH the leg side (fade-a-run)
    feats["volz"] = ch["volz"][idx]
    feats["lean_aligned"] = sides * ch["lean"][idx]
    feats["lean_slope_aligned"] = sides * ch["lean_slope"][idx]
    # heavy dipole features (subsample if huge to stay compute-light)
    dfeats = {k: [] for k in ("d_mi_flow", "d_imb_flow", "d_ent_dipole", "d_C_signed",
                              "aligned_flow", "opposing", "exhausting", "rev_conv")}
    for i, sd in zip(idx, sides):
        d = dipole_at(bk, int(i))
        for k in dfeats:
            v = d.get(k, np.nan)
            if k in ("d_mi_flow", "d_imb_flow", "aligned_flow"):     # signed -> align to leg side
                v = sd * v if np.isfinite(v) else v
            dfeats[k].append(v)
    for k, v in dfeats.items():
        feats[k] = np.array(v, float)
    # DESCRIPTIVE (post-hoc) for contrast
    desc = {"swing_bps": np.array([abs(l.swing_bps) for l in legs]),
            "hold_s": np.array([int(l.close_idx) - int(l.open_idx) for l in legs])}
    rows = {}
    for k, v in feats.items():
        rows[k] = (auc(v, y), cohen_d(v, y), "causal")
    for k, v in desc.items():
        rows[k] = (auc(v, y), cohen_d(v, y), "descriptive")
    return dict(coin=bk["coin"], side=side, rev=rev, n=len(legs), winfrac=float(y.mean()),
                rows=rows, y=y, feats=feats)


# ================= CLASS 2/3: down-slides & up-hills =================
def price_zigzag(mid, theta_bps):
    """Zigzag pivots on price. Returns list of (pivot_idx, kind) kind='H'/'L' alternating."""
    n = len(mid); th = theta_bps / 1e4
    piv = []
    d = 0; ext = mid[0]; exti = 0
    for t in range(1, n):
        x = mid[t]
        if x <= 0:
            continue
        if d >= 0:
            if x > ext:
                ext = x; exti = t
            elif ext > 0 and x <= ext * (1 - th):
                piv.append((exti, "H")); d = -1; ext = x; exti = t
        if d <= 0:
            if x < ext or ext <= 0:
                ext = x; exti = t
            elif ext > 0 and x >= ext * (1 + th):
                piv.append((exti, "L")); d = 1; ext = x; exti = t
    return piv


def episodes_fingerprint(bk, theta_bps):
    mid = bk["mid"]
    piv = price_zigzag(mid, theta_bps)
    # swing = consecutive pivots; onset = the STARTING pivot
    slides, hills = [], []      # onset indices (H for slide, L for hill)
    for k in range(len(piv) - 1):
        (i0, k0), (i1, k1) = piv[k], piv[k + 1]
        if mid[i0] <= 0 or mid[i1] <= 0:
            continue
        mag = abs(np.log(mid[i1] / mid[i0]) * 1e4)
        if i0 <= WDIP + 61 or mag < theta_bps:
            continue
        if k0 == "H":
            slides.append(i0)
        else:
            hills.append(i0)
    if len(slides) < 40 or len(hills) < 40:
        return dict(coin=bk["coin"], theta=theta_bps, nslide=len(slides), nhill=len(hills), rows=None)
    ch = cheap_features(bk)
    n = bk["n"]
    rng = np.random.default_rng(7)
    ctrl = rng.integers(WDIP + 62, n - 1, size=max(len(slides), len(hills)) * 2)

    def collect(idxs):
        d = {"imb_pre": ch["imb_pre"][idxs], "pre_ret": ch["pre_ret"][idxs],
             "volz": ch["volz"][idxs], "lean": ch["lean"][idxs], "lean_slope": ch["lean_slope"][idxs]}
        dd = {k: [] for k in ("d_mi_flow", "d_imb_flow", "d_ent_dipole", "aligned_flow", "exhausting")}
        for i in idxs:
            dp = dipole_at(bk, int(i))
            for k in dd:
                dd[k].append(dp.get(k, np.nan))
        for k, v in dd.items():
            d[k] = np.array(v, float)
        return d
    S = collect(np.array(slides)); H = collect(np.array(hills)); C = collect(ctrl)
    # slide-vs-hill (directional fingerprint) and slide-vs-control (early-warning) AUCs
    rows = {}
    for k in S:
        xh = np.concatenate([S[k], H[k]]); yh = np.concatenate([np.ones(len(S[k])), np.zeros(len(H[k]))])
        xc = np.concatenate([S[k], C[k]]); yc = np.concatenate([np.ones(len(S[k])), np.zeros(len(C[k]))])
        rows[k] = dict(auc_slide_vs_hill=auc(xh, yh), auc_slide_vs_ctrl=auc(xc, yc),
                       slide_mean=float(np.nanmean(S[k])), hill_mean=float(np.nanmean(H[k])),
                       ctrl_mean=float(np.nanmean(C[k])))
    return dict(coin=bk["coin"], theta=theta_bps, nslide=len(slides), nhill=len(hills), rows=rows)


# ================= leakage + null =================
def leakage_check(bk):
    """Confirm the causal features are look-ahead free via odcore.leakage."""
    ch_feats = ["imb_pre", "pre_ret", "volz", "lean"]
    results = {}
    n = bk["n"]
    idxs = np.linspace(WVOLL + 5, n - 5, 30).astype(int)

    def mk(fname):
        def sig(i, ts, p, bv, sv):
            i = int(i)
            if i < WVOLL:
                return None
            b = np.asarray(bv[:i + 1], float); s = np.asarray(sv[:i + 1], float); m = np.asarray(p[:i + 1], float)
            if fname == "imb_pre":
                lo = max(0, i + 1 - WPRE); B = b[lo:].sum(); Sm = s[lo:].sum(); t = B + Sm
                return round((B - Sm) / t, 6) if t > 0 else 0.0
            if fname == "pre_ret":
                j = max(0, i - WPRE)
                return round(np.log(m[i] / m[j]) * 1e4, 4) if m[i] > 0 and m[j] > 0 else 0.0
            if fname == "volz":
                lo = max(0, i + 1 - WPRE); loL = max(0, i + 1 - WVOLL)
                vs = (b[lo:].sum() + s[lo:].sum()) / WPRE
                vl = (b[loL:].sum() + s[loL:].sum()) / max(i + 1 - loL, 1)
                return round(vs / vl, 6) if vl > 0 else 1.0
            if fname == "lean":
                lo = max(0, i + 1 - WFLIP); B = b[lo:].sum(); Sm = s[lo:].sum(); t = B + Sm
                return round((B - Sm) / t, 6) if t > 0 else 0.0
        return sig
    for f in ch_feats:
        ok, fails = assert_no_leakage(mk(f), bk["ts"], bk["mid"], bk["buy"], bk["sell"], idxs)
        results[f] = ok
    return results


def null_test(bk, feat_arr, y, nshift=25):
    """Circular-shift the flow-based feature's index alignment vs labels; AUC null band.
    We circularly rotate the label vector against the feature ranks -> destroys real pairing."""
    rng = np.random.default_rng(99)
    base = auc(feat_arr, y)
    null = []
    for _ in range(nshift):
        k = int(rng.integers(1, len(y) - 1))
        null.append(auc(feat_arr, np.roll(y, k)))
    null = np.array([abs(v - 0.5) for v in null])
    return base, float(0.5 + (null.mean() + 2 * null.std()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("coins", nargs="*", default=["btc", "eth", "sol", "xrp", "doge", "ada", "sui", "ltc", "avax"])
    ap.add_argument("--mode", choices=["legs", "episodes", "leak", "all"], default="all")
    ap.add_argument("--theta", type=float, default=None, help="episode zigzag threshold bps (auto if unset)")
    ap.add_argument("--out", default="/tmp/s68_fp_out.json")
    args = ap.parse_args()
    coins = args.coins

    allout = {}
    for c in coins:
        bk = load_coin(c)
        if bk is None:
            print(f"{c}: NO TAPE"); continue
        entry = {"coin": c, "hours": round(bk["hours"], 1), "n": bk["n"], "hs_bps": round(bk["hs"], 4)}
        if args.mode in ("leak", "all"):
            entry["leakage"] = leakage_check(bk)
            print(f"[{c}] leakage {entry['leakage']}")
        if args.mode in ("legs", "all"):
            lf = legs_fingerprint(bk)
            if lf:
                entry["legs"] = {"n": lf["n"], "winfrac": round(lf["winfrac"], 3),
                                 "side": lf["side"], "rev": lf["rev"],
                                 "rows": {k: [round(v[0], 4) if np.isfinite(v[0]) else None,
                                              round(v[1], 4) if np.isfinite(v[1]) else None, v[2]]
                                          for k, v in lf["rows"].items()}}
                # null on the best causal feature
                best = max((k for k, v in lf["rows"].items() if v[2] == "causal"),
                           key=lambda k: abs((lf["rows"][k][0] or 0.5) - 0.5))
                b, nb = null_test(bk, lf["feats"][best], lf["y"])
                entry["legs"]["null_best"] = {"feat": best, "auc": round(b, 4), "null_band": round(nb, 4)}
                print(f"[{c}] legs n={lf['n']} winfrac={lf['winfrac']:.3f} best_causal={best} "
                      f"auc={b:.3f} null<= {nb:.3f}")
        if args.mode in ("episodes", "all"):
            theta = args.theta
            if theta is None:
                # auto: 6x median |300s return| so episodes are 'sustained'
                m = bk["mid"]; r = np.abs(np.log(np.maximum(m[300:], 1e-12) / np.maximum(m[:-300], 1e-12)) * 1e4)
                theta = float(max(8.0, 6 * np.median(r[np.isfinite(r)])))
            ep = episodes_fingerprint(bk, theta)
            if ep["rows"]:
                entry["episodes"] = {"theta": round(theta, 1), "nslide": ep["nslide"], "nhill": ep["nhill"],
                                     "rows": {k: {kk: (round(vv, 4) if isinstance(vv, float) and np.isfinite(vv) else vv)
                                                  for kk, vv in v.items()} for k, v in ep["rows"].items()}}
                sh = {k: v["auc_slide_vs_hill"] for k, v in ep["rows"].items()}
                best = max(sh, key=lambda k: abs((sh[k] or 0.5) - 0.5))
                print(f"[{c}] episodes theta={theta:.1f} nslide={ep['nslide']} nhill={ep['nhill']} "
                      f"best_dir={best} auc_s_vs_h={sh[best]:.3f}")
            else:
                entry["episodes"] = {"theta": round(theta, 1), "nslide": ep["nslide"], "nhill": ep["nhill"],
                                     "rows": None}
                print(f"[{c}] episodes theta={theta:.1f} too few (slide={ep['nslide']} hill={ep['nhill']})")
        allout[c] = entry
    with open(args.out, "w") as f:
        json.dump(allout, f, indent=1, default=str)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
