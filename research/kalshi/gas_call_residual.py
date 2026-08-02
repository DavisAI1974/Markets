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


# ===========================================================================================
# S110 step 5: --winter-store mode (ADDITIVE - nothing above this line changed).
#
# WHY: the S109 run above covers only WARM blocks (g20-g23, mean gw_hdd 0.12-0.72), and the
# claim under test lives in COLD ("Residual is only going to drive it in cold or getting cold
# times" - Greg S109; S109_MERGE_PROPOSAL_G22.md P0.8: UNTESTED IN ITS CLAIMED REGIME). The
# winter states grp7..grp13 were staged BEFORE feed Q existed and carry no grid_stack blocks,
# so the state-harvest path above can never see winter. But the feed Q store itself
# (data/grid_stack/grid_stack.json.gz) spans 2019-01-01..2026-07-20 - every walked-winter day
# is present. This mode harvests the G7-G13 windows DIRECTLY from that store.
#
# HONESTY CONSTRAINT (stated in the output too): the store is a RETRIEVAL-dated snapshot
# (retrieved 2026-07-20). This winter run is therefore the MECHANISM (contemporaneous) view
# ONLY - it tests whether the subtractor is real, and is NOT a forecast. A true decision-time
# view needs restaged states with proper knowable_from walls. As a labeled APPROXIMATION we
# add a second residual column with the feed's wall applied (grid period = latest <= X - 2
# calendar days, mirroring grid_stack_asof): the ALIGNMENT is decision-time-correct, but the
# VINTAGE is not (EIA revises early prints at the margin, so what the store holds today for
# period X-2 can differ from what a forecaster was actually served on day X). No forecast
# degree-days exist in this path, so the approx column is residual-only.
#
# SOURCES (measured, not the task sheet's nominal paths): day-moves come from the SCORED
# blind files renders/ng_refine_s95/g{7..13}_score.json field actual_day_move_usd - the
# forecasts/grp{7..13}.json files predate that field, and group_config.GROUPS no longer
# carries the winter groups (g17+ only), so the score files' own day lists are the day
# source. g11_score.json is the older per-day format (gap_actual + net_actual); the identity
# actual_day_move_usd == actual_gap_usd + actual_net_usd was verified exact on g7/g9/g12
# before using the sum for g11. Weather = realized gw_hdd/gw_cdd from
# weather/nws_temp/gw_degree_days.json (complete on all seven windows). Field mapping and the
# burn estimate REUSE grid_stack._ba_read - identical to the staged blocks by construction.
# ===========================================================================================

GRID_STORE_GZ = os.path.join(HERE, "..", "..", "data", "grid_stack", "grid_stack.json.gz")
GW_DD_PATH = os.path.join(HERE, "..", "..", "weather", "nws_temp", "gw_degree_days.json")
WINTER_GIDS = ["g7", "g8", "g9", "g10", "g11", "g12", "g13"]


def _iso(d: str) -> str:
    return d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _winter_days(gid: str) -> list[dict]:
    """Scored blind day list for a winter group: date (ISO) + actual day move (gap-inclusive)."""
    j = json.load(open(os.path.join(RD, f"{gid}_score.json"), encoding="utf-8"))
    out = []
    for r in j["days"]:
        mv = r.get("actual_day_move_usd")
        if mv is None and None not in (r.get("gap_actual"), r.get("net_actual")):
            mv = r["gap_actual"] + r["net_actual"]      # g11's older format; identity verified
        if mv is not None:
            out.append({"date": _iso(r["date"]), "move": mv})
    return out


def winter_store_run(gids: list[str]) -> None:
    import datetime as _dt

    import grid_stack as _gs

    store = _gs.load_store()
    if not store:
        print(f"[winter-store] grid store missing at {GRID_STORE_GZ}")
        return
    raw = store["days"]
    wx = json.load(open(GW_DD_PATH, encoding="utf-8"))

    def us48(iso: str) -> dict | None:
        return _gs._ba_read(raw, iso, "US48")           # the feed's own mapping, verbatim

    def asof_period(iso: str) -> str | None:
        cut = (_dt.date.fromisoformat(iso) - _dt.timedelta(days=2)).isoformat()
        prior = [p for p in raw if p <= cut]
        return max(prior) if prior else None

    print("[winter-store] COLD-regime arm of the residual test (S110 step 5).")
    print("[winter-store] HONESTY: store reads are RETRIEVAL-vintage (snapshot "
          f"{store['meta'].get('retrieved_utc', '?')[:10]}). This is the MECHANISM view ONLY -")
    print("[winter-store] it tests whether the subtractor is real, NOT what a forecaster held.")
    print("[winter-store] a_res(+2d) is an APPROXIMATE decision-time column: wall-correct")
    print("[winter-store] alignment (period = latest <= X-2), retrieval-vintage values.\n")

    summary, cumrows = [], []
    for gid in gids:
        try:
            days = _winter_days(gid)
        except FileNotFoundError:
            print(f"=== {gid.upper()}  score file missing, skipped ===\n")
            continue
        rows = []
        for i, r in enumerate(days):
            if i == 0:
                continue                                # differencing needs a prior session
            p, d = days[i - 1]["date"], r["date"]
            row = {"date": d, "move": r["move"]}
            w0, w1, g0, g1 = wx.get(p), wx.get(d), us48(p), us48(d)
            # --- MECHANISM: contemporaneous (realized weather for X, grid period == X) ---
            if w0 and w1 and g0 and g1 and None not in (residual(g0), residual(g1)):
                dd0 = (w0.get("gw_hdd") or 0) + (w0.get("gw_cdd") or 0)
                dd1 = (w1.get("gw_hdd") or 0) + (w1.get("gw_cdd") or 0)
                row["d_dd"] = round(dd1 - dd0, 3)
                row["d_res"] = round((residual(g1) - residual(g0)) / 1000.0, 1)
                b0, b1 = g0.get("est_gas_burn_bcfd"), g1.get("est_gas_burn_bcfd")
                row["d_burn"] = round(b1 - b0, 2) if None not in (b0, b1) else None
            # --- APPROX decision-time: +2d wall alignment, retrieval vintage (labeled) ---
            ap, ad = asof_period(p), asof_period(d)
            s0 = us48(ap) if ap else None
            s1 = us48(ad) if ad else None
            if s0 and s1 and None not in (residual(s0), residual(s1)):
                row["a_res"] = round((residual(s1) - residual(s0)) / 1000.0, 1)
            if "d_res" in row or "a_res" in row:
                rows.append(row)
        if not rows:
            print(f"=== {gid.upper()}  no joinable rows ===\n")
            continue
        mech = [x for x in rows if "d_res" in x]
        appr = [x for x in rows if "a_res" in x]
        hdds = [wx[d["date"]].get("gw_hdd") or 0 for d in days if d["date"] in wx]
        cdds = [wx[d["date"]].get("gw_cdd") or 0 for d in days if d["date"] in wx]
        print(f"=== {gid.upper()}  (mechanism n={len(mech)}, approx-DT n={len(appr)} | "
              f"block mean gw_hdd {sum(hdds)/len(hdds):.1f} cdd {sum(cdds)/len(cdds):.1f}) ===")
        print(f"{'date':>11} {'move':>7} | {'d_degday':>9} {'d_resid':>9} {'d_burn':>7} | {'a_res(+2d)':>10}")
        for x in rows:
            g = lambda k: ("" if k not in x or x[k] is None else f"{x[k]}")
            print(f"{x['date']:>11} {x['move']:>7} | {g('d_dd'):>9} {g('d_res'):>9} {g('d_burn'):>7} | "
                  f"{g('a_res'):>10}")

        f = lambda c: "n/a" if c is None else f"{c:+.3f}"
        if mech:
            mv = [x["move"] for x in mech]
            cdd = pearson([x["d_dd"] for x in mech], mv)
            cre = pearson([x["d_res"] for x in mech], mv)
            hdd = sum(1 for x in mech if (x["d_dd"] > 0) == (x["move"] > 0))
            hre = sum(1 for x in mech if (x["d_res"] > 0) == (x["move"] > 0))
            warn = "  [POWER: n<10, corr not a result]" if len(mech) < 10 else ""
            print(f"  MECHANISM n={len(mech)}: sign dd {hdd}/{len(mech)} res {hre}/{len(mech)} | "
                  f"corr dd {f(cdd)} res {f(cre)}{warn}")
            summary.append((gid, len(mech), hdd, hre, cdd, cre))
        if appr:
            mv = [x["move"] for x in appr]
            care = pearson([x["a_res"] for x in appr], mv)
            hare = sum(1 for x in appr if (x["a_res"] > 0) == (x["move"] > 0))
            warn = "  [POWER: n<10, corr not a result]" if len(appr) < 10 else ""
            print(f"  APPROX-DT n={len(appr)}: sign res {hare}/{len(appr)} | corr res {f(care)}"
                  f"  [vintage caveat above]{warn}")
        # cumulative/slope view inputs for this block
        ds = [d["date"] for d in days]
        cum = sum(d["move"] for d in days)
        ddl = [((wx[d].get("gw_hdd") or 0) + (wx[d].get("gw_cdd") or 0)) for d in ds if d in wx]
        rsl = [residual(us48(d)) / 1000.0 for d in ds if us48(d) and residual(us48(d)) is not None]
        bl = [us48(d).get("est_gas_burn_bcfd") for d in ds if us48(d)]
        bl = [b for b in bl if b is not None]
        cumrows.append((gid, len(ds), ddl, cum, rsl, bl))
        print()

    print("=" * 96)
    print("MECHANISM (contemporaneous) VIEW, PER BLOCK - never pooled, each block is its own cell")
    print(f"{'grp':>5} {'n':>3} {'dd sign':>9} {'res sign':>10} {'corr dd':>9} {'corr res':>9}")
    for gid, n, hdd, hre, cdd, cre in summary:
        f = lambda c: "  n/a" if c is None else f"{c:+.3f}"
        print(f"{gid:>5} {n:>3} {hdd:>6}/{n:<2} {hre:>7}/{n:<2} {f(cdd):>9} {f(cre):>9}")
    print("\nPOWER WARNING: per-block n is 9-19; a block-level r on n<10 swings on one day. Read the")
    print("SIGN counts and the per-day rows first. Blocks are cells; never pool them as a conclusion.")

    print("\n" + "=" * 96)
    print("CUMULATIVE (slope-horizon) VIEW - the hill claim at the horizon it makes, one row per block")
    print(f"{'grp':>5} {'days':>5} {'dd first->last':>22} {'cum move':>9} {'resid first->last (kMWh)':>28} {'burn f->l (Bcf/d)':>19}")
    for gid, nd, ddl, cum, rsl, bl in cumrows:
        dds = f"{ddl[0]:.1f} -> {ddl[-1]:.1f} ({ddl[-1] - ddl[0]:+.1f})" if len(ddl) >= 2 else "n/a"
        rss = f"{rsl[0]:,.0f} -> {rsl[-1]:,.0f} ({rsl[-1] - rsl[0]:+,.0f})" if len(rsl) >= 2 else "n/a"
        bs = f"{bl[0]:.1f} -> {bl[-1]:.1f} ({bl[-1] - bl[0]:+.1f})" if len(bl) >= 2 else "n/a"
        print(f"{gid:>5} {nd:>5} {dds:>22} {cum:>+9} {rss:>28} {bs:>19}")
    print(f"\nn={len(cumrows)} blocks. Directional read only - seven points cannot support a coefficient.")


if __name__ == "__main__":
    if "--winter-store" in sys.argv[1:]:
        # S110 step 5: the COLD-regime arm. Runs INSTEAD of the default warm-block path; the
        # default behavior with no flag is untouched.
        _gids = [a for a in sys.argv[1:] if not a.startswith("-")]
        winter_store_run(_gids or list(WINTER_GIDS))
        sys.exit(0)
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
