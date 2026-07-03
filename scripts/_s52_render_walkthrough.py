"""_s52_render_walkthrough.py — render 10 random WINNERS + 10 random LOSERS per coin for the walkthrough.

Two sets (Greg, S52 close):
  A. ONE-SHOT legs on the NEW Bybit venue books (sol_bybit, eth_bybit; deployed fine-scale detector;
     mk-1.25/tk5.5 = the MM3 target tier so the annotated P&L matches the deploy case).
  B. ACCUM legs (Greg's design) on SOL Coinbase — zigzag swing-scale stream + dipole gate, S_max=$5k,
     the arm that beat its controls. Marks: STARTER, CONFIRMATION, phase-2 ALL-IN, UNLOAD/DUMP.

Sampling: np.random.default_rng(52), reproducible. Renders in the S45 _render_trades.py style
(mid curve + context, POST/FILL/EXIT marks, swing label). PNGs -> docs/renders/s52/<set>/ (committed).
"""
import sys, os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker
from odcore.swing_accum import simulate_swing_accum
from _capacity_model import FLOW_W, WFLIP, REV
from importlib import import_module
_h2h = import_module("_s52_accum_vs_oneshot")   # reuse _price_zigzag / _dipole_gate — do not copy

RNG = np.random.default_rng(52)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "renders", "s52")


def _load(path, K):
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    return mid, bb, ba, buy, sell, hs


def _sample(idx_w, idx_l, k=10):
    w = list(RNG.choice(idx_w, min(k, len(idx_w)), replace=False)) if len(idx_w) else []
    l = list(RNG.choice(idx_l, min(k, len(idx_l)), replace=False)) if len(idx_l) else []
    return sorted(map(int, w)), sorted(map(int, l))


def _fig(mid, lo, hi, title):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    xs = np.arange(lo, hi)
    ax.plot(xs / 10.0, mid[lo:hi], lw=0.8, color="#334", alpha=0.9)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("t (s, cell/10)"); ax.set_ylabel("mid")
    return fig, ax


def render_oneshot(cell, path, K, grace, mk, tk, outdir):
    mid, bb, ba, buy, sell, hs = _load(path, K)
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=mk, taker_fee_bps=tk, cover_grace=grace)
    legs = res.legs
    nets = np.asarray([l.net_bps for l in legs])
    wi, li = np.nonzero(nets > 0)[0], np.nonzero(nets <= 0)[0]
    sw, sl = _sample(wi, li)
    os.makedirs(outdir, exist_ok=True)
    index = []
    for tag, ids in (("W", sw), ("L", sl)):
        for r, i in enumerate(ids, 1):
            l = legs[i]
            fl, oi, ci = int(l.flip_idx), int(l.open_idx), int(l.close_idx)
            ctx = max(300, (ci - fl) // 5)
            lo, hi = max(0, fl - ctx), min(len(mid), ci + ctx)
            side = "LONG (bid @ valley)" if l.side > 0 else "SHORT (ask @ peak)"
            t = (f"{cell} one-shot #{tag}{r}  {side}  net {l.net_bps:+.1f}bps  swing {l.swing_bps:.1f}bps"
                 f"  hold {(ci-oi)/10:.0f}s  close={'maker' if l.close_maker else 'TAKER'}  [mk{mk:+g}]")
            fig, ax = _fig(mid, lo, hi, t)
            ax.axvline(fl / 10, color="#888", ls=":", lw=1)
            ax.annotate("POST (turn)", (fl / 10, mid[fl]), fontsize=7, color="#555")
            ax.plot(oi / 10, l.open_px, marker="^" if l.side > 0 else "v",
                    color="#0a0" if l.side > 0 else "#c00", ms=9)
            ax.annotate(f"FILL {l.open_px:.4g}", (oi / 10, l.open_px), fontsize=7,
                        xytext=(4, -12), textcoords="offset points")
            ax.plot(ci / 10, l.close_px, marker="x", color="#c00" if l.close_maker else "#f80", ms=9)
            ax.annotate(f"EXIT {l.close_px:.4g}", (ci / 10, l.close_px), fontsize=7,
                        xytext=(4, 6), textcoords="offset points")
            f = os.path.join(outdir, f"{cell}_{tag}{r:02d}.png")
            fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
            index.append(f"{cell} {tag}{r}: side={l.side:+d} net={l.net_bps:+.1f}bps "
                         f"swing={l.swing_bps:.1f} hold={(ci-oi)/10:.0f}s maker_close={l.close_maker}")
    return index


def render_accum(cell, path, K, grace, mk, tk, outdir, worst_losers=0):
    mid, bb, ba, buy, sell, hs = _load(path, K)
    theta = _h2h.ZIG_K * (hs + tk)
    allf = _h2h._price_zigzag(mid, theta)
    gdip = _h2h._dipole_gate(allf, mid, buy, sell)
    res = simulate_swing_accum(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=mk, taker_fee_bps=tk, S_max=5000.0,
                               unload_grace=grace, queue_frac=0.0, entry_ok=gdip)
    legs = res.legs
    nets = np.asarray([l.net_usd for l in legs])
    wi, li = np.nonzero(nets > 0)[0], np.nonzero(nets <= 0)[0]
    if worst_losers:
        # S53 walkthrough: the tails, not a draw — losers most-negative first, winners biggest first
        sw = [int(i) for i in np.argsort(nets)[::-1][:worst_losers]]
        sl = [int(i) for i in np.argsort(nets)[:worst_losers]]
    else:
        sw, sl = _sample(wi, li)
    os.makedirs(outdir, exist_ok=True)
    index = []
    for tag, ids in (("W", sw), ("L", sl)):
        for r, i in enumerate(ids, 1):
            l = legs[i]
            fl, ci = int(l.flip_idx), int(l.close_flip_idx)
            ctx = max(300, (ci - fl) // 5)
            lo, hi = max(0, fl - ctx), min(len(mid), ci + ctx)
            side = "LONG" if l.side > 0 else "SHORT"
            status = "DUMPED" if l.dumped else ("confirmed→ALL-IN" if l.confirmed else "starter only")
            t = (f"{cell} ACCUM #{tag}{r}  {side}  net ${l.net_usd:+.2f}  bought ${l.bought_usd:,.0f} "
                 f"(starter ${l.starter_usd:,.0f} + p2mk ${l.phase2_maker_usd:,.0f} + p2tk "
                 f"${l.phase2_taker_usd:,.0f})  {status}  [zigzag{theta:.0f}bp, mk{mk:+g}]")
            fig, ax = _fig(mid, lo, hi, t)
            ax.axvline(fl / 10, color="#888", ls=":", lw=1)
            ax.annotate("TURN/STARTER", (fl / 10, mid[fl]), fontsize=7, color="#555")
            ax.plot(fl / 10, mid[fl], marker="^" if l.side > 0 else "v",
                    color="#0a0" if l.side > 0 else "#c00", ms=9)
            if l.confirmed and l.confirm_idx > 0:
                cf = int(l.confirm_idx)
                ax.axvline(cf / 10, color="#08c", ls="--", lw=1)
                ax.annotate("CONFIRM → all-in", (cf / 10, mid[cf]), fontsize=7, color="#08c",
                            xytext=(4, 10), textcoords="offset points")
            ax.axvline(ci / 10, color="#c00" if l.dumped else "#666", ls=":", lw=1.2)
            lbl = "DUMP (taker)" if l.dumped else (
                f"UNLOAD mk ${l.unload_maker_usd:,.0f} / tk ${l.unload_taker_usd:,.0f}")
            ax.annotate(lbl, (ci / 10, mid[ci]), fontsize=7, color="#c00" if l.dumped else "#333",
                        xytext=(4, -14), textcoords="offset points")
            f = os.path.join(outdir, f"{cell}_accum_{tag}{r:02d}.png")
            fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
            index.append(f"{cell} ACCUM {tag}{r}: side={l.side:+d} net=${l.net_usd:+.2f} "
                         f"bought=${l.bought_usd:,.0f} {status}")
    return index


def main():
    if "--worst-accum" in sys.argv:
        # S53: render the 10 WORST accum losers (tail, ranked by net) — same window, same params as Set B
        out = os.path.join(os.path.dirname(OUT), "s53", "setB_sol_worst10")
        idx = render_accum("sol_coinbase", "/tmp/sol_coinbase_book.jsonl.gz", 1, 300, -1.0, 5.0,
                           out, worst_losers=10)
        print("\n".join(idx))
        with open(os.path.join(out, "INDEX.txt"), "w") as f:
            f.write("\n".join(idx) + "\n")
        print(f"\n{len(idx)} renders -> {out}")
        return
    idx = []
    print("=== Set A: one-shot on the Bybit venue books (mk-1.25/tk5.5 = MM3 target tier) ===")
    idx += render_oneshot("sol_bybit", "/tmp/sol_bybit_book.jsonl.gz", 1, 300, -1.25, 5.5,
                          os.path.join(OUT, "setA_sol"))
    idx += render_oneshot("eth_bybit", "/tmp/eth_bybit_book.jsonl.gz", 1, 300, -1.25, 5.5,
                          os.path.join(OUT, "setA_eth"))
    print("=== Set B: ACCUM (Greg's design) on SOL Coinbase, zigzag+dipole (mk-1/tk5) ===")
    idx += render_accum("sol_coinbase", "/tmp/sol_coinbase_book.jsonl.gz", 1, 300, -1.0, 5.0,
                        os.path.join(OUT, "setB_sol"))
    print("\n".join(idx))
    with open(os.path.join(OUT, "INDEX.txt"), "w") as f:
        f.write("\n".join(idx) + "\n")
    print(f"\n{len(idx)} renders -> {OUT}")


if __name__ == "__main__":
    main()
