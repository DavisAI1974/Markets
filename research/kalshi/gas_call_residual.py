#!/usr/bin/env python3
"""S109 P0.7: the GAS CALL RESIDUAL - weather-driven load net of what renewables and baseload absorb.

THE CLAIM UNDER TEST (from the G22 blind post-mortem). Weather is THE driver of the demand term, but
its TRANSMISSION to gas price runs through subtractors that no weather play references:

    gas call  =  weather-driven load  -  renewables (solar + wind)  -  baseload that must run

G22 0629 is the motivating instance. Across the 0626 -> 0629 seam gw_cdd rose 10.0 -> 14.8 exactly as
forecast, and gas burn FELL 4.2 Bcf/d (38.6 -> 34.4), because wind rose 62% (+660,219 MWh) and total
demand declined. The blind, reasoning from degree-day LEVELS, forecast +325; actual was -1,110. Every
input needed to see it was already served in grid_stack.

THE RESIDUAL, and why it is defined this way:

    gas_call_residual = demand_mwh - solar_mwh - wind_mwh - nuclear_mwh

Subtracting realized COAL would be circular: gas_mwh is what remains after every other fuel, so a
residual net of coal reproduces gas_mwh by construction and proves nothing. Nuclear is subtracted
because it is effectively must-run baseload rather than price-responsive. What is left is the call that
gas and coal compete to serve - the economically meaningful object, and non-circular with respect to
both.

THE LAG, measured not assumed: grid_stack under day X carries period X-2 on every day of every group
checked. So the CONTEMPORANEOUS grid state for session X lives in the block for X+2. This script
harvests a global period-keyed map across all staged groups, so block-edge days are not lost.

TWO TESTS, REPORTED SEPARATELY, because they answer different questions:
  MECHANISM  - contemporaneous: does session X's own residual explain session X's move? This tests
               whether the subtractor is real. It is NOT a forecast and must never be read as one.
  USABILITY  - decision-time: does the residual as SERVED on day X (period X-2) associate with X's
               move? This is what a forecaster actually holds at the open.

Reported per block and per day, never as a single pooled number (standing rule: each event
individually; a mean is a dashboard number, never a diagnosis).
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "renders", "ng_refine_s95")


def harvest_grid() -> dict:
    """period_date -> US48 grid stack, pooled across every staged group (periods are unique dates)."""
    out = {}
    for f in glob.glob(os.path.join(RD, "grp*_state.json")):
        st = json.load(open(f, encoding="utf-8"))
        for k, v in st.items():
            if not k[:1].isdigit():
                continue
            gs = (v or {}).get("grid_stack") or {}
            us = (gs.get("bas") or {}).get("US48")
            per = gs.get("period")
            if us and per and us.get("gas_mwh") is not None:
                out[per.replace("-", "")] = us
    return out


def harvest_weather() -> dict:
    """session_date -> realized weather. weather under day D is D's OWN realized value."""
    out = {}
    for f in glob.glob(os.path.join(RD, "grp*_state.json")):
        st = json.load(open(f, encoding="utf-8"))
        for k, v in st.items():
            if not k[:1].isdigit():
                continue
            w = (v or {}).get("weather") or {}
            if w.get("gw_cdd") is not None or w.get("gw_hdd") is not None:
                out[k] = w
    return out


def residual(us: dict) -> float | None:
    try:
        return (us["demand_mwh"] - (us.get("solar_mwh") or 0.0)
                - (us.get("wind_mwh") or 0.0) - (us.get("nuclear_mwh") or 0.0))
    except Exception:
        return None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def run(gids):
    grid, wx = harvest_grid(), harvest_weather()
    print(f"[gas_call_residual] grid periods harvested: {len(grid)} | weather days: {len(wx)}\n")
    summary = []
    for gid in gids:
        ap = os.path.join(RD, f"{gid}_actual.json")
        if not os.path.exists(ap):
            continue
        act = json.load(open(ap, encoding="utf-8"))
        days = [r for r in act["days"]]
        # served-in-block view: block[X].grid_stack has period X-2, so differencing consecutive BLOCKS
        # gives a decision-time series available on every day but the first - far better coverage than
        # the contemporaneous alignment, which the D-2 lag strands at both block edges.
        st = json.load(open(os.path.join(RD, f"{gid.replace('g','grp')}_state.json"), encoding="utf-8"))
        served = {}
        for k, v in st.items():
            if k[:1].isdigit():
                us = ((v.get("grid_stack") or {}).get("bas") or {}).get("US48")
                wf = v.get("weather_forecast") or {}
                if us:
                    served[k] = (us, wf)
        rows = []
        for i, r in enumerate(days):
            if i == 0:
                continue                       # need a prior session to difference against
            d, p = r["date"], days[i - 1]["date"]
            row = {"date": d, "move": r["day_move_usd"]}
            # --- MECHANISM: contemporaneous (realized weather for X, grid period == X) ---
            w0, w1, g0c, g1c = wx.get(p), wx.get(d), grid.get(p), grid.get(d)
            if w0 and w1 and g0c and g1c and None not in (residual(g0c), residual(g1c)):
                dd0 = (w0.get("gw_hdd") or 0) + (w0.get("gw_cdd") or 0)
                dd1 = (w1.get("gw_hdd") or 0) + (w1.get("gw_cdd") or 0)
                row["d_dd"] = round(dd1 - dd0, 3)
                row["d_res"] = round((residual(g1c) - residual(g0c)) / 1000.0, 1)
                b0, b1 = g0c.get("est_gas_burn_bcfd"), g1c.get("est_gas_burn_bcfd")
                row["d_burn"] = round(b1 - b0, 2) if None not in (b0, b1) else None
            # --- SERVED: everything as a forecaster held it at X's open (grid period X-2) ---
            s0, s1 = served.get(p), served.get(d)
            if s0 and s1 and None not in (residual(s0[0]), residual(s1[0])):
                f0 = (s0[1].get("forecast_gw_hdd") or 0) + (s0[1].get("forecast_gw_cdd") or 0)
                f1 = (s1[1].get("forecast_gw_hdd") or 0) + (s1[1].get("forecast_gw_cdd") or 0)
                row["s_dd"] = round(f1 - f0, 3)
                row["s_res"] = round((residual(s1[0]) - residual(s0[0])) / 1000.0, 1)
            if "d_res" in row or "s_res" in row:
                rows.append(row)
        if not rows:
            continue
        mech = [x for x in rows if "d_res" in x]
        serv = [x for x in rows if "s_res" in x]
        print(f"=== {gid.upper()}  (mechanism n={len(mech)}, served n={len(serv)}) ===")
        print(f"{'date':>10} {'move':>7} | {'d_degday':>9} {'d_resid':>9} {'d_burn':>7} | {'s_degday':>9} {'s_resid':>9}")
        for x in rows:
            g = lambda k: ("" if k not in x or x[k] is None else f"{x[k]}")
            print(f"{x['date']:>10} {x['move']:>7} | {g('d_dd'):>9} {g('d_res'):>9} {g('d_burn'):>7} | "
                  f"{g('s_dd'):>9} {g('s_res'):>9}")

        def stats(sub, kdd, kres):
            mv = [x["move"] for x in sub]
            cdd = pearson([x[kdd] for x in sub], mv)
            cre = pearson([x[kres] for x in sub], mv)
            hdd = sum(1 for x in sub if (x[kdd] > 0) == (x["move"] > 0))
            hre = sum(1 for x in sub if (x[kres] > 0) == (x["move"] > 0))
            return cdd, cre, hdd, hre

        f = lambda c: "n/a" if c is None else f"{c:+.3f}"
        if mech:
            cdd, cre, hdd, hre = stats(mech, "d_dd", "d_res")
            print(f"  MECHANISM n={len(mech)}: sign dd {hdd}/{len(mech)} res {hre}/{len(mech)} | "
                  f"corr dd {f(cdd)} res {f(cre)}")
        if serv:
            scdd, scre, shdd, shre = stats(serv, "s_dd", "s_res")
            print(f"  SERVED    n={len(serv)}: sign dd {shdd}/{len(serv)} res {shre}/{len(serv)} | "
                  f"corr dd {f(scdd)} res {f(scre)}")
            summary.append((gid, len(serv), shdd, shre, scdd, scre))
        print()
    print("=" * 78)
    print("SERVED (decision-time) VIEW, PER BLOCK - never pooled, each block is its own cell")
    print(f"{'grp':>5} {'n':>3} {'dd sign':>9} {'res sign':>10} {'corr dd':>9} {'corr res':>9}")
    for gid, n, hdd, hre, cdd, cre in summary:
        f = lambda c: "  n/a" if c is None else f"{c:+.3f}"
        print(f"{gid:>5} {n:>3} {hdd:>6}/{n:<2} {hre:>7}/{n:<2} {f(cdd):>9} {f(cre):>9}")
    tot = sum(n for _, n, _, _, _, _ in summary)
    print(f"\nTotal differenced decision-time days across blocks: {tot}")
    print("POWER WARNING: with ~9 days per block, a per-block correlation is not a result. Read the")
    print("SIGN counts and the per-day rows; a block-level r on n<10 will swing on one day.")


if __name__ == "__main__":
    run(sys.argv[1:] or ["g20", "g21", "g22", "g23"])


def cumulative_test(gids):
    """THE HILL IS A SLOPE, SO TEST IT AT SLOPE HORIZON.

    Testing a gentle multi-day driver against single-day moves is the wrong horizon: a day-move is
    dominated by flow and positioning, and the hill contributes a small slow term to each one. Greg's
    framing - "it is THE driver but it's gentle changes over time" - is a statement about the CUMULATIVE
    path, so compare cumulative degree-days and cumulative residual against cumulative price.
    """
    grid, wx = harvest_grid(), harvest_weather()
    print("\n" + "=" * 78)
    print("CUMULATIVE (slope-horizon) TEST - the hill claim at the horizon it actually makes")
    print(f"{'grp':>5} {'days':>5} {'dd first->last':>16} {'cum move':>9} {'resid first->last':>19}")
    for gid in gids:
        ap = os.path.join(RD, f"{gid}_actual.json")
        if not os.path.exists(ap):
            continue
        act = json.load(open(ap, encoding="utf-8"))
        ds = [r["date"] for r in act["days"]]
        cum = sum(r["day_move_usd"] for r in act["days"])
        w = [wx.get(d) for d in ds]
        dd = [((x.get("gw_hdd") or 0) + (x.get("gw_cdd") or 0)) if x else None for x in w]
        dd = [x for x in dd if x is not None]
        gr = [grid.get(d) for d in ds]
        rs = [residual(g) / 1000.0 for g in gr if g and residual(g) is not None]
        dds = f"{dd[0]:.1f} -> {dd[-1]:.1f} ({dd[-1]-dd[0]:+.1f})" if len(dd) >= 2 else "n/a"
        rss = f"{rs[0]:,.0f} -> {rs[-1]:,.0f} ({rs[-1]-rs[0]:+,.0f})" if len(rs) >= 2 else "n/a"
        print(f"{gid:>5} {len(ds):>5} {dds:>16} {cum:>+9} {rss:>19}")
    print("\nn=4 blocks. Directional read only - four points cannot support a coefficient.")


if __name__ == "__main__":
    cumulative_test(sys.argv[1:] or ["g20", "g21", "g22", "g23"])
