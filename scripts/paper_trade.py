"""paper_trade.py — forward paper-trading harness for the maker-at-the-turn swing strategy + two-factor
conviction sizing, ALL cells (Greg S47: "bring them all into paper trades, see how they shake out").

CAUSAL by construction: trades come from the validated causal executor (odcore.swing_maker.simulate_swing_maker
over odcore.flip_detector.detect_flips); the conviction SIZE multiplier is normalized on a TRAILING window of
PRIOR trades only (no look-ahead). Net-of-fee with a configurable maker/taker model (S47: needs maker <= 0).

Appends to a persistent JSONL ledger, deduped by (cell, entry_ts), so repeated runs over the rolling book
window accumulate a genuine FORWARD record. Run on a schedule (the book cron rolls the window forward); over
time the ledger IS the multi-window out-of-sample test the one-window backtest could not give us.

DOES NOT trade real money. DOES NOT modify the executor. Per-cell; partial coverage is not failure — the
forward ledger decides which cells earn deployment.
"""
from __future__ import annotations
import sys, os, json, gzip, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.info_dipole import divergence
from odcore.swing_maker import simulate_swing_maker, size_legs

FLOW_W, TRAIN_FRAC, WFLIP, REV, DIVW = 20, 0.6, 600, 0.1, 600
CELLS = [("sol", 1), ("doge", 1), ("xrp", 1), ("eth", 1), ("btc", 10)]
# S48 cover-grace (cells, 0.1s grid): the smarter last-option that rests the maker cover before crossing as
# taker. Per cell (deploy rule): ~300=30s saturates sol/xrp/eth/btc; doge's longer falling-knife wants ~600.
GRACE = {"sol": 300, "doge": 600, "xrp": 300, "eth": 300, "btc": 300}
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper_ledger.jsonl")


def _z(x):
    x = np.asarray(x, float); s = x.std()
    return (x - x.mean()) / (s + 1e-12)


def cell_trades(coin, K, maker_fee, taker_fee, alpha, roll, grace,
                dipole_entry=False, dipole_exit=None):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return []
    raw = load_book(path)                                    # parse the gzip ONCE; reuse for every consumer
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    n = len(mid); hs = median_spread_bps(path, raw=raw) / 2.0
    t0 = float(raw["ts"][0])                                 # grid idx -> ts = t0 + idx*0.1
    vol = buy + sell; cvol = np.concatenate([[0.0], np.cumsum(vol)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    # S55 dipole DECISION modes (both opt-in, defaults OFF = bit-identical to the standing executor;
    # adoption per cell via this forward ledger + controls, never by flag-flipping in prod):
    #   dipole_entry  -> the swing_maker entry_gate socket, fed by the S36 divergence read at the
    #                    pivot (expect == "reversal"): flips whose turn the flow does NOT call real
    #                    are not acted on (prior position held per the executor's hold semantics).
    #   dipole_exit   -> (arm_hi, exit_lo) lean-collapse exit (S55 R8, the inverted graph).
    egate = None
    if dipole_entry:
        egate = np.zeros(n, bool)
        for (c, p, _s) in allf:
            c, p = int(c), int(p); plo = max(0, p - DIVW)
            if p - plo < 12:
                continue
            dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo]))
            egate[c] = bool(dv and dv["expect"] == "reversal")
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=maker_fee, taker_fee_bps=taker_fee, cover_grace=grace,
                               entry_gate=egate, lean=lean if dipole_exit else None,
                               lean_exit=dipole_exit)
    # per-leg causal features at the flip (decision) cell
    legs = res.legs
    clmx, size_score, dipole_desc = [], [], []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); lo = max(0, ci - DIVW)
        cx = vm(ci, 60) / (vm(ci, 600) + 1e-12)
        v60 = vm(ci, 60); vlt = float(np.std(sret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4; dp = abs(lean[p])
        clmx.append(cx); size_score.append(v60 + vlt + rnp + dp)   # crude SIZE proxy (predicts |move|)
        # S55 R1 dipole DESCRIPTORS — record-only, no trading decision reads these. Same causal
        # objects the sizing pass uses (lean/pivot) + the S36 divergence read into the pivot;
        # the forward ledger accrues the per-cell OOS validation of each (scale, descriptor) pair.
        plo = max(0, p - DIVW)
        dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo])) \
            if p - plo >= 12 else None
        ce = min(int(l.close_idx), len(lean) - 1)
        dipole_desc.append(dict(
            dive_depth=round(float(dp), 4),                       # |lean@pivot| — S40/S47 size input
            lean_flip=round(float(lean[ci]) * -int(l.side), 4),   # with-OLD-leg lean at the confirm
            lean_close=round(float(lean[ce]) * int(l.side), 4),   # with-ride lean at exit (S55 R8)
            dipole_class=dv["expect"] if dv else "n/a",
            rev_conv=float(dv["reversal_conviction"]) if dv else None))
    # two-factor conviction SIZING — extracted to odcore.swing_maker.size_legs (CAUSAL rolling rank+z;
    # leakage-clean per assert_no_leakage, S49). Sets leg.size in place; bit-identical to the old inline pass.
    size_legs(legs, clmx, size_score, alpha=alpha, roll=roll)
    out = []
    for i, l in enumerate(legs):
        ts = t0 + int(l.open_idx) * 0.1
        out.append(dict(cell=f"{coin}_coinbase", coin=coin, ts=round(ts, 3), side=int(l.side),
                        entry=round(float(l.open_px), 6), exit=round(float(l.close_px), 6),
                        net_bps=round(float(l.net_bps), 4), size_mult=round(l.size, 3),
                        sized_net=round(float(l.net_bps) * l.size, 4),
                        swing_bps=round(float(l.swing_bps), 3), maker_close=bool(l.close_maker),
                        grace=int(grace), lean_exit=bool(l.lean_exit),
                        mode=("de" if dipole_entry else "") + ("dx" if dipole_exit else ""),
                        **dipole_desc[i]))
    return out


def load_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER) as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    global LEDGER
    ap = argparse.ArgumentParser()
    ap.add_argument("--maker", type=float, default=0.0); ap.add_argument("--taker", type=float, default=5.0)
    ap.add_argument("--alpha", type=float, default=1.0); ap.add_argument("--roll", type=int, default=200)
    ap.add_argument("--grace", type=int, default=-1, help="cover-grace cells; -1 = per-cell GRACE map")
    ap.add_argument("--dipole-entry", action="store_true",
                    help="S55: gate flip actionability on the S36 divergence read at the pivot (opt-in)")
    ap.add_argument("--dipole-exit", type=str, default="",
                    help="S55 R8: 'arm_hi,exit_lo' lean-collapse exit, e.g. '0.10,0.0' (opt-in)")
    a = ap.parse_args()
    dx = tuple(float(x) for x in a.dipole_exit.split(",")) if a.dipole_exit else None
    if a.dipole_entry or dx:
        # SANDBOX ledger for variant runs — the standing forward ledger stays pure baseline
        # (S53 rule: sandbox before committing changes; adoption via controls, not flag drift).
        LEDGER = LEDGER.replace("paper_ledger.jsonl", "paper_ledger_sandbox.jsonl")
        print(f"# dipole variant run (entry={a.dipole_entry} exit={dx}) -> SANDBOX ledger {os.path.basename(LEDGER)}")
    existing = load_ledger()
    seen = {(r["cell"], r["ts"]) for r in existing}
    new = []
    for coin, K in CELLS:
        grace = a.grace if a.grace >= 0 else GRACE.get(coin, 300)
        try:
            for tr in cell_trades(coin, K, a.maker, a.taker, a.alpha, a.roll, grace,
                                  dipole_entry=a.dipole_entry, dipole_exit=dx):
                if (tr["cell"], tr["ts"]) not in seen:
                    new.append(tr); seen.add((tr["cell"], tr["ts"]))
        except Exception as e:
            print(f"# {coin} ERR {e}")
    with open(LEDGER, "a") as f:
        for tr in new:
            f.write(json.dumps(tr) + "\n")
    print(f"# paper_trade: +{len(new)} new trades (maker={a.maker} taker={a.taker} alpha={a.alpha})")
    ledger = existing + new
    print(f"# LEDGER TOTAL {len(ledger)} trades across all runs. per-cell shakeout (net-of-fee):")
    print(f"# {'cell':16s}{'n':>6}{'flat_net':>10}{'sized_net':>11}{'win%':>6}{'taker%':>8}{'mean_sz':>9}")
    for coin, _ in CELLS:
        rs = [r for r in ledger if r["coin"] == coin]
        if not rs:
            print(f"# {coin+'_coinbase':16s}{0:>6}"); continue
        fn = sum(r["net_bps"] for r in rs); sn = sum(r["sized_net"] for r in rs)
        win = 100 * np.mean([r["net_bps"] > 0 for r in rs]); tk = 100 * np.mean([not r["maker_close"] for r in rs])
        msz = float(np.mean([r["size_mult"] for r in rs]))
        print(f"# {coin+'_coinbase':16s}{len(rs):>6}{fn:>+10.1f}{sn:>+11.1f}{win:>6.0f}{tk:>8.0f}{msz:>9.2f}")


if __name__ == "__main__":
    main()
