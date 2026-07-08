"""S75 BALANCE-EXIT test (LIVE executor).

Hypothesis (from S74 whole-leg imbalance): the LOSER's post-onset signed TRADE imbalance decays
THROUGH zero into strong negative (exh ~ -0.3) — the flow reverses mid-tail and THAT reversal IS the
loss; the WINNER's holds >= 0 to close. So exit EACH leg EARLIER — when its with-ride flow-lean decays
back to balance (<= exit_lo) — to cut the loser's flip at the zero-cross while keeping winners (who end
~= 0 anyway).

Implementation: opt-in `balance_exit=(arm_hi, exit_lo)` in odcore.swing_maker, walked in the LIVE
executor (run_kraken_cell -> run_stream -> simulate_swing_maker), maker-preferred cover machinery
unchanged (only the CLOSE TRIGGER is new), coexisting with the deep-bail (earliest cell wins). Firing
(direction/side/rev/eps/deep-bail/cover-grace/entry) is LOCKED.

Reports per coin: BASELINE (current exit) vs each balance-exit threshold x lean-window: $/hr @ $5k,
win%, loser-exit-flow (does it move from ~-0.3 toward 0?), winners-kept. Train/test (early 60 / late 40)
split for the best threshold. CAP = $5000/leg. PROVISIONAL: one book window per coin, in-sample.
"""
import os, sys, importlib.util
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import load_raw, rolling_imb, build_channels, median_spread_bps, CPS
from odcore.platform import run_kraken_cell, KRAKEN, WFLIP
from odcore.flip_detector import lean_series

CAP = 5000.0
COINS = ["sol", "btc", "eth", "xrp"]
ARM_HI = 0.15
THRESHOLDS = [0.10, 0.05, 0.0, -0.05, -0.10]
LEAN_WINDOWS = [200, 600]          # cells: 20s (S74 characterization) and 60s (executor WFLIP)
CHAR_W = 200                       # measurement lens for exit-flow: 20s, matches S74


def load_coin(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    N = len(mid); hours = N * 0.1 / 3600.0
    char_lean = lean_series(buy, sell, CHAR_W)      # 20s with-trade imbalance for measurement
    return cfg, mid, buy, sell, bb, ba, hs, N, hours, char_lean


def leg_metrics(legs, hours, N, char_lean, cut_cell):
    """Aggregate + loser/winner split + train/test on a run's legs."""
    if not legs:
        return None
    net = np.array([l.net_bps for l in legs])
    oidx = np.array([int(l.open_idx) for l in legs])
    cidx = np.array([int(l.close_idx) for l in legs])
    side = np.array([int(l.side) for l in legs])
    bal = np.array([bool(getattr(l, "bal_exit", False)) for l in legs])
    exitflow = side * char_lean[np.clip(cidx, 0, len(char_lean) - 1)]     # with-ride imb at close
    win = net > 0; los = net < 0
    dph = CAP / 1e4 / hours
    tr = oidx < cut_cell; te = ~tr
    htr = hours * cut_cell / N; hte = hours * (N - cut_cell) / N
    return dict(
        n=len(legs), n_bal=int(bal.sum()), win_pct=100 * win.mean(),
        net_sum=float(net.sum()), dph=float(net.sum() * dph),
        win_dph=float(net[win].sum() * dph), los_dph=float(net[los].sum() * dph),
        los_net_mean=float(net[los].mean()) if los.any() else float("nan"),
        los_exitflow=float(exitflow[los].mean()) if los.any() else float("nan"),
        win_exitflow=float(exitflow[win].mean()) if win.any() else float("nan"),
        n_win=int(win.sum()), n_los=int(los.sum()),
        tr_dph=float(net[tr].sum() * CAP / 1e4 / htr) if htr and tr.any() else float("nan"),
        te_dph=float(net[te].sum() * CAP / 1e4 / hte) if hte and te.any() else float("nan"),
        te_win=100 * (net[te] > 0).mean() if te.any() else float("nan"),
    )


def canary(coin, data):
    """Bit-identical: balance_exit=None must reproduce the pre-S75 executor exactly (deep-bail intact)."""
    spec = importlib.util.spec_from_file_location("swing_orig", "/tmp/swing_maker_orig.py")
    orig = importlib.util.module_from_spec(spec); sys.modules["swing_orig"] = orig
    spec.loader.exec_module(orig)
    import odcore.swing_maker as new
    from odcore.platform import kraken_flips
    cfg, mid, buy, sell, bb, ba, hs, N, hours, _ = data
    flips = kraken_flips(cfg, mid, buy, sell)
    exit_spec = {"kind": "price_stop", "x_bp": float(cfg.bail), "action": "flat", "side": 0} \
        if cfg.bail is not None else None
    lean = lean_series(buy, sell, WFLIP)
    lean_arg = lean if exit_spec is not None else None
    kw = dict(half_spread_bps=hs, maker_fee_bps=cfg.maker_fee, taker_fee_bps=cfg.taker_fee,
              cover_grace=cfg.grace, lean=lean_arg, exit_spec=exit_spec, fill_model="front",
              close_improve_bps=cfg.improve)
    ro = orig.simulate_swing_maker(mid, bb, ba, buy, sell, flips, **kw)
    rn = new.simulate_swing_maker(mid, bb, ba, buy, sell, flips, balance_exit=None, **kw)
    ok = len(ro.legs) == len(rn.legs) and all(
        (a.side, a.open_idx, a.close_idx, round(a.net_bps, 9), a.close_maker, a.stop_exit)
        == (b.side, b.open_idx, b.close_idx, round(b.net_bps, 9), b.close_maker, b.stop_exit)
        for a, b in zip(ro.legs, rn.legs))
    print(f"  CANARY {coin}: orig legs={len(ro.legs)} new legs={len(rn.legs)}  "
          f"exit_spec={'price_stop' if exit_spec else 'none'}  bit-identical={ok}", flush=True)
    return ok


def main():
    coins = sys.argv[1:] or COINS
    all_canary = True
    for coin in coins:
        print(f"\n===================== {coin.upper()}_kraken =====================", flush=True)
        data = load_coin(coin)
        cfg, mid, buy, sell, bb, ba, hs, N, hours, char_lean = data
        cut_cell = int(0.6 * N)
        all_canary &= canary(coin, data)

        # BASELINE (current live exit)
        base, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
        bm = leg_metrics(base.legs, hours, N, char_lean, cut_cell)
        print(f"  legs={bm['n']}  {hours:.1f}h  deep-bail={cfg.bail}  grace={cfg.grace}  side={cfg.side}", flush=True)
        print(f"  BASELINE: $/hr={bm['dph']:+.2f}  win%={bm['win_pct']:.1f}  "
              f"loser-exitflow={bm['los_exitflow']:+.3f}  winner-exitflow={bm['win_exitflow']:+.3f}  "
              f"win-$/hr={bm['win_dph']:+.2f}  los-$/hr={bm['los_dph']:+.2f}  nWin={bm['n_win']} nLos={bm['n_los']}", flush=True)
        print(f"    (baseline train $/hr={bm['tr_dph']:+.2f}  test $/hr={bm['te_dph']:+.2f}  test-win%={bm['te_win']:.1f})", flush=True)

        results = {}
        for W in LEAN_WINDOWS:
            print(f"\n  --- balance exit, lean window = {W} cells ({W//CPS}s), arm_hi={ARM_HI} ---", flush=True)
            print(f"    {'exit_lo':>8}{'$/hr':>9}{'dVSbase':>9}{'win%':>7}{'nBal':>6}{'losFlow':>9}"
                  f"{'losNet':>9}{'winFlow':>9}{'win$/hr':>9}{'los$/hr':>9}{'nW/nL':>10}", flush=True)
            for thr in THRESHOLDS:
                res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs,
                                         balance_exit=(ARM_HI, thr), bal_lean_w=W)
                m = leg_metrics(res.legs, hours, N, char_lean, cut_cell)
                results[(W, thr)] = m
                print(f"    {thr:>+8.2f}{m['dph']:>+9.2f}{m['dph']-bm['dph']:>+9.2f}{m['win_pct']:>7.1f}"
                      f"{m['n_bal']:>6}{m['los_exitflow']:>+9.3f}{m['los_net_mean']:>+9.2f}"
                      f"{m['win_exitflow']:>+9.3f}{m['win_dph']:>+9.2f}{m['los_dph']:>+9.2f}"
                      f"{m['n_win']:>5}/{m['n_los']:<4}", flush=True)

        # best threshold by IN-SAMPLE $/hr, then its train/test
        best = max(results, key=lambda k: results[k]["dph"])
        bmv = results[best]
        print(f"\n  BEST balance exit: window={best[0]}c exit_lo={best[1]:+.2f}  "
              f"$/hr={bmv['dph']:+.2f} (baseline {bm['dph']:+.2f}, delta {bmv['dph']-bm['dph']:+.2f})", flush=True)
        print(f"    TRAIN(60%) $/hr={bmv['tr_dph']:+.2f} (base {bm['tr_dph']:+.2f})  "
              f"TEST(40%) $/hr={bmv['te_dph']:+.2f} (base {bm['te_dph']:+.2f})  "
              f"TEST win%={bmv['te_win']:.1f} (base {bm['te_win']:.1f})", flush=True)
        beats = "BEATS" if bmv['dph'] > bm['dph'] else "does NOT beat"
        print(f"  VERDICT {coin}: balance exit {beats} current exit "
              f"(loser rescue {bm['los_exitflow']:+.3f}->{bmv['los_exitflow']:+.3f}, "
              f"loser $/hr {bm['los_dph']:+.2f}->{bmv['los_dph']:+.2f}, "
              f"winner $/hr {bm['win_dph']:+.2f}->{bmv['win_dph']:+.2f})", flush=True)
    print(f"\n=== ALL CANARIES bit-identical: {all_canary} ===", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
