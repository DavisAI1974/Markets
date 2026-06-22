"""_coupling_scan.py — agnostic OD coupling scan over the book channels.

Feed the raw channels to the 5-step coupler (odcore.coupling_scanner.score_pair runs all five
steps in order + the circular-shift tautology null) for every pair, and rank by structured
coupling that survives the null. No direction or expectation imposed — the scan reports what
couples and the lead/lag it finds.
"""
from __future__ import annotations
import argparse, json
import numpy as np
from _birth_probe import load_book, to_grid
from odcore.coupling_scanner import score_pair


def build_channels(path, K):
    g = to_grid(load_book(path), 0.1)
    lm = np.log(np.where(g["mid"] > 0, g["mid"], np.nan))
    absret = np.nan_to_num(np.abs(np.concatenate([[0.], np.diff(lm)])))
    return {
        "bid_depth": g["bidK"][K],
        "ask_depth": g["askK"][K],
        "taker_buy": g["buy"],
        "taker_sell": g["sell"],
        "abs_return": absret,
        "volume": g["buy"] + g["sell"],
    }


def run(path, K, window, stride, render, part=0, nparts=1):
    ch = build_channels(path, K)
    names = list(ch)
    # break the DATA into nparts equal time-slices; run the FULL pair set on this slice
    L = len(next(iter(ch.values())))
    lo, hi = part * L // nparts, (part + 1) * L // nparts
    ch = {k: v[lo:hi] for k, v in ch.items()}
    print(f"# data part {part+1}/{nparts}: samples [{lo}:{hi}] ({(hi-lo)*0.1/3600:.2f}h); full pair set")
    scores = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ps = score_pair(ch[a], ch[b], f"{a}~{b}", "scan", window=window, stride=stride)
            if ps is not None:
                scores.append(ps)
    scores.sort(key=lambda p: p.rank_score, reverse=True)
    print(f"# agnostic 5-step coupling scan: {len(scores)} pairs "
          f"(window={window} stride={stride}, tautology-null on)\n")
    hdr = f"{'pair':24} {'rank':>7} {'struct_z':>8} {'mi_frac':>8} {'chem':>7} {'dip_r2':>7} {'leadlag':>8} {'ll_z':>7}"
    print(hdr); print("-" * len(hdr))
    out = []
    for p in scores:
        print(f"{p.name:24} {p.rank_score:7.3f} {p.structure_z:8.2f} {p.mi_frac:8.3f} "
              f"{p.chem_frac:7.3f} {p.dipole_r2:7.3f} {p.leadlag:8d} {p.coupling_z:7.2f}")
        out.append(dict(pair=p.name, rank=p.rank_score, structured=p.structured,
                        structure_z=p.structure_z, mi_frac=p.mi_frac, chem_frac=p.chem_frac,
                        dipole_r2=p.dipole_r2, leadlag=p.leadlag, leadlag_cc=p.leadlag_cc,
                        coupling_z=p.coupling_z))
    fn = f"_coupling_scan_results_part{part}of{nparts}.json" if nparts > 1 else "_coupling_scan_results.json"
    json.dump(out, open(fn, "w"), indent=2)
    print(f"\n[saved] {fn}")
    if render and nparts == 1:
        _render(out)


def _render(out):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    out = out[::-1]
    labels = [o["pair"] for o in out]
    y = np.arange(len(out))
    fig, ax = plt.subplots(1, 2, figsize=(14, max(4, 0.4 * len(out))))
    ax[0].barh(y, [o["structure_z"] for o in out], color="#0050b3")
    ax[0].set_yticks(y); ax[0].set_yticklabels(labels, fontsize=8)
    ax[0].axvline(2, color="r", ls="--", lw=0.8, label="z=2")
    ax[0].set_xlabel("structure_z (survives tautology null)"); ax[0].legend(fontsize=8)
    ax[0].set_title("coupling structure vs circular-shift null")
    ax[1].barh(y, [o["leadlag"] for o in out], color="#722ed1")
    ax[1].set_yticks(y); ax[1].set_yticklabels([]); ax[1].axvline(0, color="k", lw=0.6)
    ax[1].set_xlabel("lead-lag (cells; sign = which channel leads)")
    ax[1].set_title("discovered lead/lag")
    fig.tight_layout(); fig.savefig("_coupling_scan.png", dpi=110); plt.close(fig)
    print("[render] _coupling_scan.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=20)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    run(a.path, a.K, a.window, a.stride, not a.no_render, a.part, a.nparts)
