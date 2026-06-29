"""_od_book_run.py — S41: dump the book data (all 3 layers) into OD and let it find the operator.

Greg: "this is its happy place -- finding an operator in this data." Stop hand-picking features;
feed the channels to the OD engine and let the windowed-null + coupling discriminator + PySR
symbolic regression DISCOVER the structure.

Channels from the 5.8h Coinbase book file (100ms grid):
  buy, sell           -- executed taker flow halves (the dipole)
  bid_dep, ask_dep    -- top-K resting liquidity halves (the supply/demand curve)
  |ret|               -- price activity

OD does three things per channel pair (a,b):
  1. windowed_operator_matrix -> basis [H_a,H_b,H_a^2,H_b^2,H_a*H_b,MI]
  2. analyze_coupling -> null direction + {equal-entropy / MI / residual} decomposition
     (MI ENTERING the null = structured, law-like coupling; the project's core discriminator)
  3. symbolic.discover (PySR) -> the governing equation MI ~ f(H_a,H_b) and H_a^2 ~ f(...)
"""
from __future__ import annotations
import argparse, json
import numpy as np
from _birth_probe import load_book, to_grid
from odcore.operators import windowed_operator_matrix
from odcore.null_extract import analyze_coupling
from odcore import symbolic

BASIS = ["H_a", "H_b", "H_a^2", "H_b^2", "H_a*H_b", "MI"]


def channels(path):
    g = to_grid(load_book(path), 0.1)
    K = 5
    ret = np.abs(np.concatenate([[0.], np.diff(np.log(np.where(g["mid"] > 0, g["mid"], np.nan)))]))
    ret = np.nan_to_num(ret)
    return dict(buy=g["buy"], sell=g["sell"],
                bid_dep=g["bidK"][K], ask_dep=g["askK"][K], absret=ret), g["n"]


def run(path, window, stride, do_pysr, niter):
    ch, n = channels(path)
    print(f"# OD run on {n:,} cells (100ms); window={window} ({window*0.1:.1f}s) stride={stride}\n")
    pairs = [("buy", "sell", "EXECUTED FLOW dipole"),
             ("bid_dep", "ask_dep", "LIQUIDITY dipole (the curve)"),
             ("bid_dep", "buy", "liquidity vs head pressure"),
             ("buy", "absret", "flow vs price activity")]
    out = {}
    for a, b, label in pairs:
        M = windowed_operator_matrix(ch[a], ch[b], window=window, stride=stride)
        v = analyze_coupling(M)
        # analyze_coupling returns a verdict object; pull its fields generically
        d = {k: (round(float(x), 4) if isinstance(x, (int, float, np.floating)) else x)
             for k, x in vars(v).items()} if hasattr(v, "__dict__") else {"verdict": str(v)}
        print(f"== {label}  ({a} vs {b}) ==")
        for k, val in d.items():
            if isinstance(val, np.ndarray):
                val = np.round(val, 3).tolist()
            print(f"   {k}: {val}")
        eqs = {}
        if do_pysr and symbolic.pysr_available():
            for tgt in ("MI", "H_a^2"):
                feats = [c for c in BASIS if c != tgt]
                try:
                    eq = symbolic.discover(M, target=tgt, features=feats, niterations=niter, seed=0)
                    eqs[tgt] = getattr(eq, "equation", str(eq))
                    print(f"   PySR  {tgt} = {eqs[tgt]}")
                except Exception as e:
                    print(f"   PySR  {tgt} FAILED: {e}")
        print()
        out[label] = dict(pair=[a, b], coupling=d, equations=eqs, rows=int(M.shape[0]))
    with open("_od_book_run_results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("[saved] _od_book_run_results.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--pysr", action="store_true", help="also run PySR symbolic discovery (slow first fit)")
    ap.add_argument("--niter", type=int, default=40)
    a = ap.parse_args()
    run(a.path, a.window, a.stride, a.pysr, a.niter)
