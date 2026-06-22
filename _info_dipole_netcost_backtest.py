"""_info_dipole_netcost_backtest.py — net-of-cost backtest of the flow divergence/exhaustion policy.

THE decisive S36 test (KICKOFF_2026-06-22_S36.md #1): the 64% reversal hit-rate is only an EDGE if
the moves beat fees+slippage. Per cell, walk-forward, real costs.

THE STRATEGY IS TREND-FOLLOWING (Greg, S36): "markets are mostly follow-the-leader until the leader
exhausts -> new leader, usually opposite." Following the trend IS following the flow. So this is a
BIDIRECTIONAL flow policy, NOT a pure fade — and we KEEP the trend's PnL (we do NOT detrend; the trend
is the money). The info dipole picks direction per onset on the strictly-pre-entry 30m order-flow window:

  aligned_flow = imb_level * sign(price_drift)        (>0 flow CONFIRMS trend; <0 flow OPPOSES)
  exhausting   = |late-half imbalance| < |early-half| (the leader weakening; dipole -> 0.5)

  FOLLOW the trend (dir = +sign(pre_drift)) when flow CONFIRMS;  FADE (dir = -sign(pre_drift)) when
  flow OPPOSES. Exhaustion + strong-divergence raise reversal conviction (sizing/sub-gating).

  gross_bps = dir * (P_exit/P_entry - 1) * 1e4
  net_bps   = gross_bps - 2*COST_PER_SIDE_BPS          (enter + exit)

Enter at the onset close; exit at the trade's OWN horizon (horizon_minutes; buys ~234-240m, sells ~25-27m).
The gate fires PRE-ENTRY; PnL is measured post-onset over the realistic hold -> no look-ahead in the decision.

Policies reported (per cell, net-of-cost):
  FLOW        — follow when confirms, fade when opposes (the deployable trend-following policy).
  FLOW_2F     — follow ONLY the healthy trend (confirms & strengthening); fade everything else.
  FADE_GATE   — the literal kickoff ask: trade ONLY expect=='reversal', always fade.
  FOLLOW_ALL  — always follow the trend (no flow gate) — baseline for "does the flow gate add value".

A cell CLEARS if its policy net_bps > 0 (the platform's net-of-cost bar). Walk-forward = per-cell
early/late temporal split (the rule is non-parametric — the honest robustness check is that the edge
is not concentrated in one time half).

CAVEAT (load-bearing): test_bars are THIN — 1-min, ~2 days (05-23/24), ONE trend regime, n<=1560.
First cut; real confirmation needs the local 1-sec multi-regime onset history (not in git).

Run: python _info_dipole_netcost_backtest.py
"""
from __future__ import annotations

import bisect
import glob
import json

import numpy as np

from odcore.info_dipole import divergence, DIVERGE_STRONG

WIN_S = 1800                 # pre-entry order-flow window for the gate (30 min, = validated signal)
COST_PER_SIDE_BPS = 5.0      # fees+slippage per side (audit convention); round-trip = 2x
DEFAULT_HORIZON_S = 1800     # fallback hold if a trade carries no horizon_minutes


def load_bars():
    bars = {}
    for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
        d = json.load(open(fp)); a, v = d["asset"].lower(), d["venue"].lower()
        B = sorted(d["bars"], key=lambda b: b["ts"])
        bars[(a, v)] = (np.array([b["ts"] for b in B]),
                        np.array([b.get("buy_vol", 0.) for b in B]),
                        np.array([b.get("sell_vol", 0.) for b in B]),
                        np.array([b["close"] for b in B]))
    return bars


def build_trades(bars, onsets):
    """One record per onset where the gate is evaluable AND a horizon-exit bar exists.

    Each record carries the signed forward return and the flow read; a policy then picks a
    direction (+1 follow / -1 fade) from the flow, and PnL = dir * ret_bps - cost.
    """
    out = []
    for w in onsets:
        a, v = w["asset"].lower(), w["venue"].lower()
        key = (a, v)
        if key not in bars:
            continue
        ts, bv, sv, cl = bars[key]
        ot = w["true_onset_ts_utc"]
        lo = bisect.bisect_left(ts, ot - WIN_S)
        hi = bisect.bisect_right(ts, ot)              # onset bar index = hi-1 (last bar <= onset)
        if hi == 0 or hi - lo < 6:
            continue
        hold_s = float(w.get("horizon_minutes") or 0) * 60.0 or DEFAULT_HORIZON_S
        xi = bisect.bisect_left(ts, ot + hold_s)      # first bar at/after onset+horizon
        if xi >= len(ts) or xi <= hi - 1:
            continue
        p_entry = cl[hi - 1]; p_exit = cl[xi]
        pre_drift = cl[hi - 1] - cl[lo]
        if pre_drift == 0 or p_entry <= 0:
            continue
        dv = divergence(bv[lo:hi], sv[lo:hi], pre_drift)
        if dv is None:
            continue
        ret_bps = (p_exit / p_entry - 1.0) * 1e4      # signed forward return over the hold
        pre_sign = 1.0 if pre_drift > 0 else -1.0
        out.append({
            "cell": w["cell"], "ts": ot, "side": w["side"],
            "confirms": dv["confirms"], "opposing": dv["opposing"], "exhausting": dv["exhausting"],
            "expect": dv["expect"], "strong": (dv["aligned_flow"] <= DIVERGE_STRONG),
            "aligned": dv["aligned_flow"], "conviction": dv["reversal_conviction"],
            "pre_sign": pre_sign, "ret_bps": ret_bps,
            "reversal": (np.sign(ret_bps) != pre_sign and ret_bps != 0),
            "hold_min": hold_s / 60.0,
        })
    return out


# ---- policies: each maps a record -> (traded?, direction) -----------------------------------
def pol_flow(r):           # follow when flow confirms, fade when flow opposes (deployable)
    return True, (r["pre_sign"] if r["confirms"] else -r["pre_sign"])

def pol_flow_2f(r):        # follow ONLY healthy trend (confirms & strengthening); else fade
    follow = r["confirms"] and not r["exhausting"]
    return True, (r["pre_sign"] if follow else -r["pre_sign"])

def pol_fade_gate(r):      # literal kickoff: trade only expect=='reversal', always fade
    return (r["expect"] == "reversal"), -r["pre_sign"]

def pol_follow_all(r):     # baseline: always follow the trend, no flow gate
    return True, r["pre_sign"]


def apply(records, policy, rt_cost):
    g = []
    for r in records:
        traded, d = policy(r)
        if traded:
            g.append(d * r["ret_bps"] - rt_cost)
    return np.array(g)


def summ(g):
    if g.size == 0:
        return None
    return {"n": int(g.size), "net_bps": round(float(g.mean()), 2),
            "net_med_bps": round(float(np.median(g)), 2),
            "win_rate": round(100 * float((g > 0).mean()), 1),
            "net_total_bps": round(float(g.sum()), 1),
            "se": round(float(g.std(ddof=1) / np.sqrt(g.size)) if g.size > 1 else 0.0, 2)}


def fmt(label, s):
    if s is None:
        return f"{label:22s}  (no trades)"
    star = "  <-- CLEARS" if s["net_bps"] > 0 else ""
    t = s["net_bps"] / s["se"] if s["se"] > 0 else 0.0
    return (f"{label:22s} n={s['n']:>4d}  net={s['net_bps']:>+7.2f} (+-{s['se']:>5.2f}, t={t:>+4.1f})  "
            f"win%={s['win_rate']:>4.1f}  total={s['net_total_bps']:>+9.1f}{star}")


def main():
    bars = load_bars()
    wo = json.load(open("fingerprint_dataset/onsets/winner_onsets.json"))
    trades = build_trades(bars, wo)
    rt = 2 * COST_PER_SIDE_BPS
    cells = sorted({r["cell"] for r in trades})

    print("Net-of-cost backtest of the FLOW divergence/exhaustion policy (TREND-FOLLOWING; no detrend).")
    print(f"Cost = {COST_PER_SIDE_BPS} bps/side (round-trip {rt}). Hold = each trade's own horizon "
          f"(buys ~4h, sells ~25m). Pre-entry gate window = {WIN_S//60}m.")
    print(f"Evaluable onsets: {len(trades)} / {len(wo)}\n")

    policies = [("FLOW (follow|fade)", pol_flow), ("FLOW_2F (healthy-only)", pol_flow_2f),
                ("FADE_GATE (reversal)", pol_fade_gate), ("FOLLOW_ALL (baseline)", pol_follow_all)]

    # ---- pooled, every policy -------------------------------------------------------------
    print("=" * 96)
    print("POOLED (all cells)")
    print("=" * 96)
    for name, p in policies:
        print(" ", fmt(name, summ(apply(trades, p, rt))))

    # ---- PER CELL, the deployable FLOW policy ---------------------------------------------
    print("\n" + "=" * 96)
    print("PER CELL — FLOW policy (follow when flow confirms trend, fade when flow opposes)")
    print("=" * 96)
    cleared = {}
    per_cell = {}
    for c in cells:
        recs = [r for r in trades if r["cell"] == c]
        s = summ(apply(recs, pol_flow, rt))
        per_cell[c] = s
        if s and s["n"] >= 5:
            print(" ", fmt(c, s))
            if s["net_bps"] > 0:
                cleared[c] = s["net_bps"]
    print(f"\n  Cells clearing net-of-cost (FLOW, mean net>0, n>=5): "
          f"{', '.join(f'{k} (+{v:.1f})' for k, v in sorted(cleared.items(), key=lambda x:-x[1])) or 'NONE'}")

    # ---- PER CELL, the literal FADE gate (kickoff ask) ------------------------------------
    print("\n" + "=" * 96)
    print("PER CELL — FADE_GATE (literal kickoff ask: fade only expect=='reversal')")
    print("=" * 96)
    fade_cleared = {}
    per_cell_fade = {}
    for c in cells:
        recs = [r for r in trades if r["cell"] == c]
        s = summ(apply(recs, pol_fade_gate, rt))
        per_cell_fade[c] = s
        if s and s["n"] >= 5:
            print(" ", fmt(c, s))
            if s["net_bps"] > 0:
                fade_cleared[c] = s["net_bps"]
    print(f"\n  Cells clearing net-of-cost (FADE_GATE, n>=5): "
          f"{', '.join(f'{k} (+{v:.1f})' for k, v in sorted(fade_cleared.items(), key=lambda x:-x[1])) or 'NONE'}")

    # ---- walk-forward: per-cell early/late on the FLOW policy ------------------------------
    print("\n" + "=" * 96)
    print("WALK-FORWARD (FLOW policy; temporal early/late split — rule is non-parametric)")
    print("=" * 96)
    for c in cells:
        cr = sorted([r for r in trades if r["cell"] == c], key=lambda r: r["ts"])
        if len(cr) < 16:
            continue
        h = len(cr) // 2
        se, sl = summ(apply(cr[:h], pol_flow, rt)), summ(apply(cr[h:], pol_flow, rt))
        both = "  BOTH+" if (se["net_bps"] > 0 and sl["net_bps"] > 0) else ""
        print(f"   {c:20s} early net={se['net_bps']:>+8.2f} (n={se['n']:>3d})   "
              f"late net={sl['net_bps']:>+8.2f} (n={sl['n']:>3d}){both}")

    # ---- cost sensitivity on the FLOW policy ----------------------------------------------
    print("\n" + "=" * 96)
    print("COST SENSITIVITY (round-trip bps) — FLOW policy pooled net bps/trade")
    print("=" * 96)
    for rt_c in [0, 5, 10, 15, 20, 30]:
        s = summ(apply(trades, pol_flow, rt_c))
        print(f"   round-trip {rt_c:>2d} bps:  net={s['net_bps']:>+7.2f} bps/trade   total={s['net_total_bps']:>+9.1f}")

    # ---- persist --------------------------------------------------------------------------
    out = {
        "config": {"cost_per_side_bps": COST_PER_SIDE_BPS, "round_trip_bps": rt, "pre_window_s": WIN_S,
                   "hold": "per-trade horizon_minutes", "evaluable": len(trades), "total_onsets": len(wo),
                   "strategy": "trend-following flow policy; no detrend; keep the trend"},
        "pooled": {name: summ(apply(trades, p, rt)) for name, p in policies},
        "per_cell_FLOW": per_cell,
        "per_cell_FADE_GATE": per_cell_fade,
        "cells_clearing_FLOW": cleared,
        "cells_clearing_FADE_GATE": fade_cleared,
        "cost_sweep_FLOW": {str(c): summ(apply(trades, pol_flow, c)) for c in [0, 5, 10, 15, 20, 30]},
        "caveat": "thin 1-min/2-day test_bars, single trend regime, n<=1560; first cut, not deploy-grade",
    }
    with open("_info_dipole_netcost_backtest_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote _info_dipole_netcost_backtest_results.json")


if __name__ == "__main__":
    main()
