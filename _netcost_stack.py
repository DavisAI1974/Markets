"""S35 Step-2 — net-of-cost tradeability test gating on the per-cell STACK score.

Extends _netcost_backtest.py (which gated on the dipole margin only and died at
MIN_TRAIN=40 for every lose-starved cell). Here the gate is the per-cell STACK:
a logistic on [dipole_margin, *micro] — micro as the base, the coeff dipole a
contributor (Greg S34: tools are complementary; the stack is the product).

The decisive question (the "5% net edge" bar): once you exit at a REALISTIC fixed
horizon (not the hindsight best-exit the labels used) and pay fees+slippage, does
GATING on the stack score produce positive PnL per cell, beating taking-all?

Two scoring paths (no look-ahead in either re: the scored trade):
  - mode=oof  : 5-fold stratified OOF (the _stack_deconfound scheme). Uses ALL
                trades, so it is viable on the current lose-starved universe — the
                HEAD-START read before the Direction-2 meat lands. Not strictly
                causal in time, but the de-confound universe is a 2-day window.
  - mode=wf   : strict walk-forward online centroids + a logistic refit each step,
                MIN_TRAIN wins AND loses required before scoring. The DECISIVE run
                once the balanced (meated) pools exist. Starves pre-meat by design.

Three gates compared per cell: 'dipole' (margin>0), 'micro' (proba>0.5),
'stack' (proba>0.5). Realistic single fixed-horizon exit; cost sweep RT bps.
A cell PROMOTES iff, at the realistic cost, gated mean net > 0 AND beats taking-all
AND enough trades are taken. Report PER CELL ("works on {X}"), never "failed".

Universe: 'chunkhash' (05-23/24 de-confounded; the head-start cells live here).
Coeffs from the cs2000_clean win index; labels/entry/horizon from the relabel;
micro from the rich win.clean buckets (keyed by source_id).
"""
from __future__ import annotations

import bisect
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, r"E:\refrag\adapters")
from markets_bar_loader import load_closes  # noqa: E402

SHARD_DIR = Path(r"E:\Markets\_cs2000_coeff_index")
RELABEL = Path(r"E:\Markets\_relabel_true_horizon_results.json")
CLEAN_BUCKETS = Path(r"E:\Markets\research\strategy_evolution\per_bucket\clean")
OUT = Path(r"E:\Markets\_netcost_stack_results.json")

MICRO = ["mean_dipole", "dipole_acl1", "volume_zscore", "trade_present_score",
         "trade_recent_2chunk_bps", "trade_from_onset_bps"]
COST_LEVELS = [0, 5, 10, 15, 20]   # round-trip bps (fees+slippage); audit fee = 10
PROMOTE_COST = 10                  # the realistic cost at which a cell must clear the bar
MIN_TAKEN = 10                     # need this many gated trades for a non-fluke read
GATES = ["dipole", "micro", "stack"]
K = 5
SEED = 1974
MIN_TRAIN = 40                     # wf mode: wins AND loses seen before scoring


def pair_of(sid):
    p = sid.split("|")
    return f"{p[0].lower()}_{p[1].lower()}_{p[-1].lower()}" if len(p) >= 4 else None


def folds_of(y, k, rng):
    pos = np.where(y == 1)[0]; neg = np.where(y == 0)[0]
    rng.shuffle(pos); rng.shuffle(neg)
    return [np.sort(np.concatenate([pos[i::k], neg[i::k]])) for i in range(k)]


def load_micro_features():
    """source_id -> {feat: float} from the rich win.clean buckets (chunkhash trades)."""
    feats = {}
    for fp in CLEAN_BUCKETS.glob("markets_*_win.clean.json"):
        d = json.loads(fp.read_text(encoding="utf-8"))
        for e in d.get("entries", []) or []:
            sid = e.get("source_id")
            if not sid:
                continue
            row = {}
            for k in MICRO:
                try:
                    row[k] = float(e.get(k))
                except (TypeError, ValueError):
                    row[k] = np.nan
            feats[sid] = row
    return feats


def margin_centroids(Ctr, ytr):
    tw = Ctr[ytr == 1]; tl = Ctr[ytr == 0]
    cw = tw.mean(0); cl = tl.mean(0)
    nw = np.linalg.norm(cw) or 1.0; nl = np.linalg.norm(cl) or 1.0
    return cw, cl, nw, nl


def oof_scores(C, M, y, folds):
    """OOF score per trade for each gate. sA=margin, sB=micro proba, sC=stack proba."""
    sA = np.zeros(len(y)); sB = np.full(len(y), 0.5); sC = np.full(len(y), 0.5)
    for fi in range(len(folds)):
        te = folds[fi]
        tr = np.concatenate([folds[f] for f in range(len(folds)) if f != fi])
        ytr = y[tr]
        if (ytr == 1).sum() == 0 or (ytr == 0).sum() == 0:
            continue
        cw, cl, nw, nl = margin_centroids(C[tr], ytr)
        mtr = C[tr] @ cw / nw - C[tr] @ cl / nl
        mte = C[te] @ cw / nw - C[te] @ cl / nl
        sA[te] = mte
        scl = StandardScaler().fit(M[tr])
        sB[te] = LogisticRegression(max_iter=1000).fit(
            scl.transform(M[tr]), ytr).predict_proba(scl.transform(M[te]))[:, 1]
        XtrC = np.column_stack([mtr, M[tr]]); XteC = np.column_stack([mte, M[te]])
        sclC = StandardScaler().fit(XtrC)
        sC[te] = LogisticRegression(max_iter=1000).fit(
            sclC.transform(XtrC), ytr).predict_proba(sclC.transform(XteC))[:, 1]
    return {"dipole": sA, "micro": sB, "stack": sC}


def wf_scores(C, M, y, ts_order):
    """Strict walk-forward: trades in ts order; refit each step after MIN_TRAIN
    wins+loses. Scored trade is always out-of-sample. NaN where not yet scorable."""
    n = len(y)
    out = {g: np.full(n, np.nan) for g in GATES}
    idx = np.argsort(ts_order, kind="mergesort")
    for rank, i in enumerate(idx):
        tr = idx[:rank]
        if len(tr) == 0:
            continue
        ytr = y[tr]
        if (ytr == 1).sum() < MIN_TRAIN or (ytr == 0).sum() < MIN_TRAIN:
            continue
        cw, cl, nw, nl = margin_centroids(C[tr], ytr)
        mtr = C[tr] @ cw / nw - C[tr] @ cl / nl
        mi = C[i] @ cw / nw - C[i] @ cl / nl
        out["dipole"][i] = mi
        scl = StandardScaler().fit(M[tr])
        out["micro"][i] = LogisticRegression(max_iter=1000).fit(
            scl.transform(M[tr]), ytr).predict_proba(scl.transform(M[[i]]))[:, 1][0]
        XtrC = np.column_stack([mtr, M[tr]]); XiC = np.column_stack([[mi], M[[i]]])
        sclC = StandardScaler().fit(XtrC)
        out["stack"][i] = LogisticRegression(max_iter=1000).fit(
            sclC.transform(XtrC), ytr).predict_proba(sclC.transform(XiC))[:, 1][0]
    return out


def gate_threshold(gate):
    return 0.0 if gate == "dipole" else 0.5


def main(mode="oof", universe="chunkhash") -> int:
    scheme = "win" if universe == "chunkhash" else "lose"
    coefs = {}
    for shp in glob.glob(str(SHARD_DIR / f"*_{scheme}_preentry_cs2000_clean.json")):
        for _u, r in json.loads(Path(shp).read_text()).items():
            coefs[r["source_id"]] = r["coef"]
    rel = {t["source_id"]: t for t in json.loads(RELABEL.read_text())["trades"]}
    micro = load_micro_features()
    print(f"mode={mode}  universe={universe}  coeffs={len(coefs)}  micro={len(micro)}")

    # assemble per-pair records
    recs = defaultdict(list)
    miss_micro = 0
    for sid, c in coefs.items():
        t = rel.get(sid)
        if not t or t.get("new_label") not in ("win", "lose"):
            continue
        if not t.get("entry_ts_utc") or not t.get("horizon_minutes") or not t.get("entry_price"):
            continue
        m = micro.get(sid)
        if m is None or any(np.isnan(m[k]) for k in MICRO):
            miss_micro += 1
            continue
        recs[pair_of(sid)].append({
            "sid": sid, "coef": np.array(c, float), "micro": [m[k] for k in MICRO],
            "asset": t["asset"], "venue": t["venue"], "side": t["side"],
            "ts": float(t["entry_ts_utc"]), "H": float(t["horizon_minutes"]),
            "entry": float(t["entry_price"]),
            "y": 1 if t["new_label"] == "win" else 0,
        })
    print(f"dropped (no/NaN micro): {miss_micro}")

    # realistic fixed-horizon exit gross bps per trade
    series = {}
    allrec = [r for rs in recs.values() for r in rs]
    for a, v in {(r["asset"], r["venue"]) for r in allrec}:
        ts = [r["ts"] for r in allrec if r["asset"] == a and r["venue"] == v]
        H = [r["H"] for r in allrec if r["asset"] == a and r["venue"] == v]
        cl = load_closes(asset=a, venue=v, t_min=min(ts) - 120, t_max=max(ts) + max(H) * 60 + 120)
        series[(a, v)] = ([c.ts for c in cl], [c.close for c in cl])
    n_noexit = 0
    for r in allrec:
        tsl, csl = series[(r["asset"], r["venue"])]
        j = bisect.bisect_left(tsl, r["ts"] + r["H"] * 60)
        if j >= len(tsl):
            r["gross"] = None; n_noexit += 1; continue
        sgn = 1.0 if r["side"] == "buy" else -1.0
        r["gross"] = sgn * (csl[j] / r["entry"] - 1) * 1e4
    print(f"trades w/o realistic exit bar: {n_noexit}\n")

    hdr = f"{'pair':18s} {'gate':>6s} {'N':>4s} {'taken':>5s} " + " ".join(f"{'g'+str(c):>7s}" for c in COST_LEVELS) + f"  {'all@'+str(PROMOTE_COST):>8s} {'edge':>6s} P"
    print(hdr); print("-" * len(hdr))
    res = {}
    for pair, rs in sorted(recs.items()):
        rs = [r for r in rs if r.get("gross") is not None]
        y = np.array([r["y"] for r in rs], int)
        nw = int((y == 1).sum()); nl = int((y == 0).sum())
        if nw < 8 or nl < 8:
            print(f"{pair:18s} {'-':>6s} {len(rs):>4d}   (too few: {nw}w/{nl}l)")
            res[pair] = {"n": len(rs), "n_win": nw, "n_lose": nl, "note": "too_few"}
            continue
        C = np.array([r["coef"] for r in rs], float)
        M = np.array([r["micro"] for r in rs], float)
        gross = np.array([r["gross"] for r in rs], float)
        if mode == "oof":
            rng = np.random.default_rng(SEED)
            scores = oof_scores(C, M, y, folds_of(y, K, rng))
            scorable = np.ones(len(y), bool)
        else:
            ts_order = np.array([r["ts"] for r in rs], float)
            scores = wf_scores(C, M, y, ts_order)
            scorable = ~np.isnan(scores["stack"])
        res[pair] = {"n": len(rs), "n_win": nw, "n_lose": nl,
                     "n_scorable": int(scorable.sum()), "gates": {}}
        for gate in GATES:
            sc = scores[gate]
            valid = scorable & ~np.isnan(sc)
            take = valid & (sc > gate_threshold(gate))
            cells = []
            row = {"n_taken": int(take.sum()), "cost": {}}
            for c in COST_LEVELS:
                ng = float((gross[take] - c).mean()) if take.any() else float("nan")
                na = float((gross[valid] - c).mean()) if valid.any() else float("nan")
                hit = float((gross[take] > c).mean()) if take.any() else float("nan")
                row["cost"][str(c)] = {"gated_net": ng, "all_net": na, "hit": hit}
                cells.append(f"{ng:>+7.1f}")
            pc = row["cost"][str(PROMOTE_COST)]
            edge = pc["gated_net"] - pc["all_net"]
            n_valid = int(valid.sum())
            # SELECTIVE = the gate actually filters (not taking ~everything); only then is
            # a positive net attributable to the SIGNAL rather than the cell's base rate.
            selective = (row["n_taken"] >= MIN_TAKEN and row["n_taken"] < 0.9 * max(n_valid, 1))
            signal_edge = bool(selective and pc["gated_net"] > 0 and edge > 0)
            row["n_valid"] = n_valid
            row["selective"] = bool(selective)
            row["edge_at_promote_cost"] = edge
            row["signal_edge"] = signal_edge          # selective + net-positive + beats all
            res[pair]["gates"][gate] = row
            flag = "S" if signal_edge else ("." if selective else "~")  # ~ = non-selective
            print(f"{pair:18s} {gate:>6s} {len(rs):>4d} {row['n_taken']:>5d} "
                  + " ".join(cells) + f"  {pc['all_net']:>+8.1f} {edge:>+6.1f} {flag}")
        # cell-level base-rate profitability (taking everything, at promote cost)
        any_gate = next(iter(res[pair]["gates"].values()))
        res[pair]["base_rate_net"] = any_gate["cost"][str(PROMOTE_COST)]["all_net"]
        print()

    print("=" * len(hdr))
    print("flags: S = selective gate, net>0, beats all (real signal edge) | "
          ". = selective but not net-positive edge | ~ = non-selective (net = base rate)")
    sig_cells = sorted({p for p, r in res.items()
                        for g in r.get("gates", {}).values() if g.get("signal_edge")})
    print(f"\nSIGNAL-EDGE cells (selective gate clears {PROMOTE_COST}bps RT net AND beats all): "
          + (", ".join(sig_cells) if sig_cells else "(none yet)"))
    for p in sig_cells:
        for g, gr in res[p]["gates"].items():
            if gr["signal_edge"]:
                pc = gr["cost"][str(PROMOTE_COST)]
                print(f"  {p:18s} via {g:>6s}: taken {gr['n_taken']}/{gr['n_valid']}  "
                      f"net {pc['gated_net']:+.1f}bps  edge {gr['edge_at_promote_cost']:+.1f}  (all {pc['all_net']:+.1f})")
    base_cells = sorted(p for p, r in res.items() if r.get("base_rate_net", -1) > 0)
    print(f"\nBASE-RATE-profitable cells (taking ALL nets >0 at {PROMOTE_COST}bps; window-direction "
          f"caveat applies): " + (", ".join(base_cells) if base_cells else "(none)"))
    OUT.write_text(json.dumps({"schema": "netcost_stack_v1", "mode": mode, "universe": universe,
                               "min_train_wf": MIN_TRAIN, "promote_cost": PROMOTE_COST,
                               "min_taken": MIN_TAKEN, "cost_levels": COST_LEVELS,
                               "micro": MICRO, "results": res}, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    md = sys.argv[1] if len(sys.argv) > 1 else "oof"
    uni = sys.argv[2] if len(sys.argv) > 2 else "chunkhash"
    raise SystemExit(main(md, uni))
