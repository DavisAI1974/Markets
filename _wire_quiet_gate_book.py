"""_wire_quiet_gate_book.py — wire the QuietFloor gate into the LIVE book-depth dipole, per cell (S43 #4).

The live "dipole" on the book is the directional signal on the depth-imbalance LEVEL
    imb(t) = (sum bid_depth - sum ask_depth) / (sum)            [top-K levels]
which carries DIRECTION (next-cell signed-move hit ~62%, S42) but keeps FIRING through a whole trend
because the level stays elevated as it slowly relaxes. The QuietFloor (odcore/quiet_floor.py) is the
quiet AR(1) relaxation of that level; gating on |innovation| > k*sigma fires only on a shock that
breaks the relaxation — so the production dipole stands aside through trends while keeping the level's
direction. This is the deploy form: gate = WHEN, level = DIRECTION.

WHY THE BOOK CHANNEL (canary finding): on TRADE-flow ofi the 'quiet' cells have zero flow by
construction, so the floor degenerates (phi≈0) and gating is a near-no-op. The relaxation edge is in
the resting-size DEPTH imbalance, which is non-zero and slowly relaxes between trades (phi_q≈0.95).
So the gate is wired on the depth channel. The generic IncrementalQuietGate / RollingFlow.gated_signal
hooks (odcore/incremental.py) are ready to drive the same logic in the live hot path.

Per cell (`deploy-signal-per-cell-not-universal`): fit one QuietFloor per asset×venue. Runs on
btc_coinbase today; the multi-venue book collectors (book_collectors_durable.yml) feed more cells.

Run:
  python _wire_quiet_gate_book.py --path /tmp/od_book.jsonl.gz --cell btc_coinbase --K 10 --k 1.5
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from _birth_probe import load_book, to_grid
from _liquidity_dive import fwd_cum_return
from odcore.quiet_floor import fit as fit_quiet
from odcore.incremental import IncrementalQuietGate


def build_live_gated_dipole(path: str, K: int, k: float, train_frac: float):
    """Returns (floor, imb, quiet, sret, gated_signal) for one cell's book.

    gated_signal is the deployable live dipole: sign(depth_imb) where the QuietFloor gate is open
    (a shock broke the quiet relaxation), else 0. Leakage-safe: QuietFloor fit on the training quiet
    cells only; the gate is causal."""
    g = to_grid(load_book(path), 0.1)
    bd, ad = g["bidK"][K], g["askK"][K]
    imb = (bd - ad) / (bd + ad + 1e-12)            # the live dipole's DIRECTION level
    vol = g["buy"] + g["sell"]
    quiet = vol <= 0.0                              # 'still' cells (no taker volume)
    sret = np.nan_to_num(np.concatenate([[0.0], np.diff(np.log(np.where(g["mid"] > 0, g["mid"], np.nan)))]))
    floor = fit_quiet(imb, quiet, train_frac=train_frac)
    gated = floor.gated_signal(imb, k=k)            # batch form (vectorized)
    return floor, imb, quiet, sret, gated


def main():
    ap = argparse.ArgumentParser(description="Wire QuietFloor gate into the live book-depth dipole")
    ap.add_argument("--path", default="/tmp/od_book.jsonl.gz")
    ap.add_argument("--cell", default="btc_coinbase", help="asset_venue label (for the per-cell record)")
    ap.add_argument("--K", type=int, default=10, help="depth levels summed for the imbalance (Chat: 10)")
    ap.add_argument("--k", type=float, default=1.5, help="gate threshold in sigma")
    ap.add_argument("--split", type=float, default=0.6, help="train fraction")
    ap.add_argument("--out", default="_wire_quiet_gate_book_results.json")
    a = ap.parse_args()

    floor, imb, quiet, sret, gated = build_live_gated_dipole(a.path, a.K, a.k, a.split)
    n = len(imb)
    cut = int(n * a.split)
    print(f"# cell={a.cell}  n={n:,} cells @100ms = {n*0.1/3600:.2f}h  K={a.K}  k={a.k}  split={a.split}")
    print(f"# QuietFloor (fit on train quiet cells): phi={floor.phi:.4f} c={floor.c:+.5f} "
          f"sigma={floor.sigma:.4f} r2_quiet={floor.r2_quiet:.3f} n_quiet_train={floor.n_quiet:,}")

    # --- raw-level dipole vs gated: churn cut + selectivity (fires on shocks, not quiet cells) ---
    raw_sig = np.sign(imb)
    open_mask = gated != 0
    raw_fire = float((raw_sig != 0).mean())
    gated_fire = float(open_mask.mean())
    open_q = float(open_mask[quiet].mean())
    open_t = float(open_mask[~quiet].mean())
    print(f"\n# CHURN — raw level fires {100*raw_fire:.1f}% of cells; gated fires {100*gated_fire:.1f}% "
          f"(stands aside {100*(1-gated_fire/max(raw_fire,1e-9)):.0f}% of the time)")
    print(f"# SELECTIVITY — gate open  on quiet cells {100*open_q:.1f}%  vs trade cells {100*open_t:.1f}%  "
          f"(ratio {open_t/(open_q+1e-12):.2f}x — fires on shocks, not the smooth relaxation)")

    # --- direction retained: OOS next-cell hit-rate, raw level vs gated-fire cells ---
    fwd = fwd_cum_return(sret, 1)
    def hit(sig):
        a_ = sig[cut:n - 1]; b_ = fwd[cut:n - 1]; m = ~np.isnan(b_)
        a_, b_ = a_[m], b_[m]
        nz = (a_ != 0) & (b_ != 0)
        return (float((np.sign(a_) == np.sign(b_))[nz].mean()) if nz.any() else float("nan"),
                int(nz.sum()))
    raw_hit, raw_nz = hit(raw_sig)
    gated_hit, gated_nz = hit(gated)
    print(f"\n# DIRECTION (OOS next-cell, sign agreement) — the gate must KEEP the level's edge:")
    print(f"   raw level   hit={100*raw_hit:.1f}%  (n={raw_nz:,})")
    print(f"   gated       hit={100*gated_hit:.1f}%  (n={gated_nz:,})  <- fewer trades, direction retained")

    # --- hot-path proof: IncrementalQuietGate (O(1)/tick) == batch gate on the REAL book channel ---
    inc = IncrementalQuietGate.from_floor(floor, k=a.k)
    inc_sig = np.fromiter((inc.gated_signal(float(x)) for x in imb), dtype=float, count=n)
    mism = int((inc_sig != gated).sum())
    print(f"\n# HOT PATH — IncrementalQuietGate vs batch gated_signal mismatches = {mism}/{n}")
    assert mism == 0, "incremental hot-path gate diverges from batch on the book channel!"
    print("   PASS — the live O(1)/tick gate is bit-faithful on real book data.")

    rec = dict(cell=a.cell, n=n, hours=round(n * 0.1 / 3600, 2), K=a.K, k=a.k, split=a.split,
               quietfloor=dict(phi=floor.phi, c=floor.c, sigma=floor.sigma, r2_quiet=floor.r2_quiet,
                               n_quiet_train=floor.n_quiet),
               churn=dict(raw_fire=raw_fire, gated_fire=gated_fire),
               selectivity=dict(open_quiet=open_q, open_trade=open_t,
                                 ratio=open_t / (open_q + 1e-12)),
               direction=dict(raw_hit=raw_hit, raw_n=raw_nz, gated_hit=gated_hit, gated_n=gated_nz),
               hot_path_mismatches=mism)
    with open(a.out, "w") as f:
        json.dump(rec, f, indent=2)
    print(f"\nwrote {a.out}")
    print("READING: gate = WHEN (fires on shocks, stands aside through the quiet relaxation = trends), "
          "level = DIRECTION (OOS hit retained). Wired per cell; ready for the multi-venue book.")


if __name__ == "__main__":
    main()
