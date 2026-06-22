"""S35 Step-2 (BALANCED) — net-of-cost tradeability test on the MEATED per-cell pools.

Same decisive question as _netcost_stack.py (does gating on the per-cell stack beat
cost net, per cell), but on the Direction-2 BALANCED universe: existing 1240 same-period
win coeffs + the ~1669 new cand_sp coeffs, candidates relabeled by true-horizon. Reuses
_balanced_rerun's VALIDATED loaders (load_coeffs/load_labels/load_micro) so the trade set
matches the balanced AUC run exactly, and _netcost_stack's exit + gating engine.

Per cell: realistic single fixed-horizon exit, cost sweep 0/5/10/15/20 bps RT, three gates
(dipole margin / micro logistic / stack logistic). Modes: oof (uses all trades) and wf
(strict walk-forward, now viable with the meat). A cell shows a SIGNAL edge iff a SELECTIVE
gate (not taking ~everything) nets >0 at the promote cost AND beats taking-all.
"""
from __future__ import annotations

import bisect
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, r"E:\refrag\adapters")
sys.path.insert(0, r"E:\Markets")
from markets_bar_loader import load_closes  # noqa: E402

import _balanced_rerun as BR  # noqa: E402
import _netcost_stack as NC   # noqa: E402

OUT = Path(r"E:\Markets\_netcost_stack_balanced_results.json")
MICRO = BR.MICRO
CAND_DIR = BR.CAND_DIR
RELABEL = BR.EXIST_RELABEL


def main(mode="wf") -> int:
    coefs = BR.load_coeffs()
    lab = BR.load_labels(set(coefs))
    micro = BR.load_micro()
    rel = {t["source_id"]: t for t in json.loads(Path(RELABEL).read_text())["trades"]}
    cand = {}
    for p in BR.PAIRS:
        fp = CAND_DIR / f"markets_{p}_cand.json"
        if fp.exists():
            for e in json.loads(fp.read_text()).get("entries", []):
                cand[e["source_id"]] = e
    print(f"mode={mode}  coeffs={len(coefs)}  labels={len(lab)}  micro={len(micro)}  "
          f"rel={len(rel)}  cand={len(cand)}")

    # entry info per trade: existing from relabel, candidate from cand bucket (+bar entry px)
    recs = defaultdict(list)
    n_nomicro = n_noentry = 0
    for sid, c in coefs.items():
        l = lab.get(sid); p = BR.pair_of(sid); m = micro.get(sid)
        if l not in ("win", "lose") or p not in {pp: 1 for pp in BR.PAIRS}:
            continue
        if m is None or any(np.isnan(m[k]) if isinstance(m[k], float) else False for k in MICRO):
            n_nomicro += 1; continue
        if sid in rel and rel[sid].get("entry_price") and rel[sid].get("entry_ts_utc") and rel[sid].get("horizon_minutes"):
            t = rel[sid]
            rec = {"sid": sid, "asset": t["asset"], "venue": t["venue"], "side": t["side"],
                   "ts": float(t["entry_ts_utc"]), "H": float(t["horizon_minutes"]),
                   "entry": float(t["entry_price"]), "entry_known": True}
        elif sid in cand and cand[sid].get("entry_ts_utc") and cand[sid].get("horizon_minutes"):
            e = cand[sid]
            rec = {"sid": sid, "asset": e["asset"], "venue": e["venue"], "side": e["side"],
                   "ts": float(e["entry_ts_utc"]), "H": float(e["horizon_minutes"]),
                   "entry": None, "entry_known": False}
        else:
            n_noentry += 1; continue
        rec["coef"] = np.array(c, float)
        rec["micro"] = [float(m[k]) for k in MICRO]
        rec["y"] = 1 if l == "win" else 0
        recs[p].append(rec)
    print(f"dropped: no/NaN micro={n_nomicro}  no entry info={n_noentry}")

    # preload bar series; fill candidate entry prices + realistic fixed-horizon exit
    series = {}
    allrec = [r for rs in recs.values() for r in rs]
    for a, v in {(r["asset"], r["venue"]) for r in allrec}:
        ts = [r["ts"] for r in allrec if r["asset"] == a and r["venue"] == v]
        H = [r["H"] for r in allrec if r["asset"] == a and r["venue"] == v]
        cl = load_closes(asset=a, venue=v, t_min=min(ts) - 3600, t_max=max(ts) + max(H) * 60 + 120)
        series[(a, v)] = ([c.ts for c in cl], [c.close for c in cl])
    n_noexit = n_noentrypx = 0
    for r in allrec:
        tsl, csl = series[(r["asset"], r["venue"])]
        if r["entry"] is None:  # candidate: nearest bar to entry_ts (mirror BR.load_labels)
            i = bisect.bisect_left(tsl, r["ts"])
            cands = [j for j in (i - 1, i) if 0 <= j < len(tsl)]
            if not cands:
                r["gross"] = None; n_noentrypx += 1; continue
            r["entry"] = csl[min(cands, key=lambda k: abs(tsl[k] - r["ts"]))]
        if not r["entry"] or r["entry"] <= 0:
            r["gross"] = None; n_noentrypx += 1; continue
        j = bisect.bisect_left(tsl, r["ts"] + r["H"] * 60)
        if j >= len(tsl):
            r["gross"] = None; n_noexit += 1; continue
        sgn = 1.0 if str(r["side"]).lower() == "buy" else -1.0
        r["gross"] = sgn * (csl[j] / r["entry"] - 1) * 1e4
    print(f"trades w/o entry px={n_noentrypx}  w/o realistic exit bar={n_noexit}\n")

    hdr = (f"{'pair':18s} {'gate':>6s} {'N':>4s} {'taken':>5s} "
           + " ".join(f"{'g'+str(c):>7s}" for c in NC.COST_LEVELS)
           + f"  {'all@'+str(NC.PROMOTE_COST):>8s} {'edge':>6s} F")
    print(hdr); print("-" * len(hdr))
    res = {}
    for pair, rs in sorted(recs.items()):
        rs = [r for r in rs if r.get("gross") is not None]
        y = np.array([r["y"] for r in rs], int)
        nw = int((y == 1).sum()); nl = int((y == 0).sum())
        if nw < 8 or nl < 8:
            print(f"{pair:18s} {'-':>6s} {len(rs):>4d}   (too few: {nw}w/{nl}l)")
            res[pair] = {"n": len(rs), "n_win": nw, "n_lose": nl, "note": "too_few"}; continue
        C = np.array([r["coef"] for r in rs], float)
        M = np.array([r["micro"] for r in rs], float)
        gross = np.array([r["gross"] for r in rs], float)
        if mode == "oof":
            rng = np.random.default_rng(NC.SEED)
            scores = NC.oof_scores(C, M, y, NC.folds_of(y, NC.K, rng))
            scorable = np.ones(len(y), bool)
        else:
            scores = NC.wf_scores(C, M, y, np.array([r["ts"] for r in rs], float))
            scorable = ~np.isnan(scores["stack"])
        res[pair] = {"n": len(rs), "n_win": nw, "n_lose": nl,
                     "n_scorable": int(scorable.sum()), "base_rate_net": None, "gates": {}}
        for gate in NC.GATES:
            sc = scores[gate]
            valid = scorable & ~np.isnan(sc)
            take = valid & (sc > NC.gate_threshold(gate))
            n_valid = int(valid.sum())
            cells = []; row = {"n_taken": int(take.sum()), "n_valid": n_valid, "cost": {}}
            for c in NC.COST_LEVELS:
                ng = float((gross[take] - c).mean()) if take.any() else float("nan")
                na = float((gross[valid] - c).mean()) if valid.any() else float("nan")
                hit = float((gross[take] > c).mean()) if take.any() else float("nan")
                row["cost"][str(c)] = {"gated_net": ng, "all_net": na, "hit": hit}
                cells.append(f"{ng:>+7.1f}")
            pc = row["cost"][str(NC.PROMOTE_COST)]
            edge = pc["gated_net"] - pc["all_net"]
            selective = (row["n_taken"] >= NC.MIN_TAKEN and row["n_taken"] < 0.9 * max(n_valid, 1))
            signal_edge = bool(selective and pc["gated_net"] > 0 and edge > 0)
            row.update({"selective": bool(selective), "edge_at_promote_cost": edge, "signal_edge": signal_edge})
            res[pair]["gates"][gate] = row
            flag = "S" if signal_edge else ("." if selective else "~")
            print(f"{pair:18s} {gate:>6s} {len(rs):>4d} {row['n_taken']:>5d} "
                  + " ".join(cells) + f"  {pc['all_net']:>+8.1f} {edge:>+6.1f} {flag}")
        res[pair]["base_rate_net"] = next(iter(res[pair]["gates"].values()))["cost"][str(NC.PROMOTE_COST)]["all_net"]
        print()

    print("=" * len(hdr))
    print("F: S=selective+net>0+beats all (signal edge) | .=selective not net-pos | ~=non-selective(base rate)")
    sig = sorted({p for p, r in res.items() for g in r.get("gates", {}).values() if g.get("signal_edge")})
    print(f"\nSIGNAL-EDGE cells (selective gate clears {NC.PROMOTE_COST}bps RT net AND beats all):  "
          + (", ".join(sig) if sig else "(none)"))
    for p in sig:
        for g, gr in res[p]["gates"].items():
            if gr["signal_edge"]:
                pc = gr["cost"][str(NC.PROMOTE_COST)]
                print(f"  {p:18s} via {g:>6s}: taken {gr['n_taken']}/{gr['n_valid']}  "
                      f"net {pc['gated_net']:+.1f}bps  edge {gr['edge_at_promote_cost']:+.1f}  (all {pc['all_net']:+.1f}, hit {pc['hit']:.0%})")
    OUT.write_text(json.dumps({"schema": "netcost_stack_balanced_v1", "mode": mode,
                               "promote_cost": NC.PROMOTE_COST, "min_taken": NC.MIN_TAKEN,
                               "cost_levels": NC.COST_LEVELS, "micro": MICRO, "results": res}, indent=2),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "wf"))
