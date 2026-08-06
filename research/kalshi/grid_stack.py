"""
grid_stack.py - FEED Q (family D/power): EIA-930 grid stack - daily demand, day-ahead demand
forecast, and generation by fuel, per balancing authority (S99).

WHY THIS EXISTS
---------------
Feed P (solar calendar) gives the solar ramp's CLOCK; this gives its QUANTITY, plus the load side
Greg asked for outright ("should we be tracking electricity loads too?"). EIA-930 publishes daily
ACTUAL generation BY FUEL BY BALANCING AUTHORITY plus demand AND the BA's own DAY-AHEAD DEMAND
FORECAST - free, ~1-2 day lag, 2019->present. Gas-displaced-by-solar becomes a measured state
variable; the gas share of the stack is the power-burn nowcast the weekly NGWU only averages; and
the S98 sweep demonstrated the payoff on the squeeze: US48 gas generation 3.71M MWh (Jan 10) ->
5.39M (Jan 20) -> 5.60M (Jan 25) - the freeze's +14 Bcf/d power-burn ramp visible daily while
every other demand read was weekly-or-slower. Per-BA always, never a national pool as a
conclusion (US48 is carried as its own respondent row, not a pool we compute).

SOURCE ROUTES (verified live 2026-07-20)
----------------------------------------
- electricity/rto/daily-fuel-type-data  (daily gen by fuel; facets respondent/fueltype/timezone)
- electricity/rto/daily-region-data     (daily demand D + day-ahead forecast DF + net gen NG +
  interchange TI; facets respondent/type/timezone)
Scope: the gas-relevant BAs first per the gate - ERCO, CISO, MISO, PJM, SWPP, SOCO - plus US48.
TIMEZONE FRAMING: all rows pulled in EASTERN so day boundaries align with the desk's ET clock and
with the S98 sweep's demonstration values (a per-BA local-timezone variant is a possible later
refinement, noted not built).

PUBLICATION MECHANICS / BLIND WALL (measured)
---------------------------------------------
The S98 sweep observed T+2 availability on the daily fuel route; today the same route shows T+1
(gen through 07-19 on 07-20) and the demand route a nominal T+0 tail. Daily aggregates firm up
progressively and EIA revises early hours. WALL (conservative, from the measured worst case):
    knowable_from = period + 2 calendar days;  asof(iso) serves the latest period <= iso - 2.
Age is exposed per read. Revision risk: the store is a retrieval-dated snapshot; early-day values
revise at the margin (named; feed-K-class question if it ever matters for a print-sized claim).

EIA v2 TRAP (from feed R): numerics arrive as STRINGS - coerced at store time.

THE POWER-BURN ESTIMATE (labeled, method stated): est_gas_burn_bcfd = gas_MWh x 7,900 Btu/kWh
/ 1.035e9 - the fleet heat rate EIA's own STEO pair implies (measured stable ~7,900 across
Jul 2025 - Jul 2026 in the S98 sweep). An ESTIMATE with a stated method, never a measurement.

STORE: data/grid_stack/grid_stack.json.gz. No commits by this module; S3 push is the
orchestrator's step (prefix grid_stack/).

USAGE
-----
  python research/kalshi/grid_stack.py --build
  python research/kalshi/grid_stack.py --selftest
  python research/kalshi/grid_stack.py --show 2026-01-22
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(_ROOT, "data", "grid_stack")
STORE_PATH = os.path.join(STORE_DIR, "grid_stack.json.gz")
ENV_PATH = os.path.join(_ROOT, "scratchpad", "aws.env")
API = "https://api.eia.gov/v2/electricity/rto"

RESPONDENTS = ["US48", "ERCO", "CISO", "MISO", "PJM", "SWPP", "SOCO"]
TZ = "Eastern"
START = "2019-01-01"
HEAT_RATE_BTU_PER_KWH = 7900.0  # STEO-implied fleet heat rate, measured stable (S98 sweep sec 5)


def _api_key() -> str:
    """S113: resolved by creds.py - environment, then ~/.config/markets/env, then the legacy
    scratchpad path with a warning. Greg: "no more scratchpad. It's in the sop." A credential is
    neither code nor data, so it lives outside the repo tree entirely (D33/D34)."""
    import creds
    return creds.get("EIA_API_KEY")


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _paged(url: str, params: dict) -> list[dict]:
    import requests
    rows, offset = [], 0
    while True:
        p = dict(params, length=5000, offset=offset)
        r = requests.get(url, params=p, timeout=120)
        r.raise_for_status()
        resp = r.json()["response"]
        batch = resp["data"]
        rows.extend(batch)
        offset += len(batch)
        if offset >= int(resp["total"]) or not batch:
            return rows


def build() -> dict:
    key = _api_key()
    days: dict[str, dict] = {}

    def slot(period: str, ba: str) -> dict:
        return days.setdefault(period, {}).setdefault(ba, {"gen_mwh": {}})

    for ba in RESPONDENTS:
        rows = _paged(f"{API}/daily-fuel-type-data/data", {
            "api_key": key, "data[]": ["value"], "start": START,
            "facets[respondent][]": ba, "facets[timezone][]": TZ,
            "sort[0][column]": "period", "sort[0][direction]": "asc"})
        for r in rows:
            v = _f(r.get("value"))
            if v is not None:
                slot(r["period"], ba)["gen_mwh"][r["fueltype"]] = v
        drows = _paged(f"{API}/daily-region-data/data", {
            "api_key": key, "data[]": ["value"], "start": START,
            "facets[respondent][]": ba, "facets[timezone][]": TZ,
            # S113 (A-32): TI added. The route's own docstring above already named "interchange TI"
            # and the facet filter excluded it, so unlike hydro/battery/wind - fetched then dropped at
            # a serving list - interchange was never even REQUESTED. It is the observable that says
            # whether the cheap route to reliability is still open: when every neighbour is tight
            # simultaneously nobody has surplus to sell, interchange collapses toward zero, and the BA
            # must self-serve - which lands on gas, because gas owns the fast timescales (A-31).
            "facets[type][]": ["D", "DF", "TI"],
            "sort[0][column]": "period", "sort[0][direction]": "asc"})
        for r in drows:
            v = _f(r.get("value"))
            k = {"D": "demand_mwh", "DF": "demand_forecast_mwh",
                 "TI": "interchange_mwh"}.get(r["type"])
            if v is not None and k:
                slot(r["period"], ba)[k] = v
        print(f"[grid_stack] {ba}: {len(rows)} fuel rows + {len(drows)} demand rows")

    os.makedirs(STORE_DIR, exist_ok=True)
    store = {
        "meta": {
            "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "routes": [f"{API}/daily-fuel-type-data", f"{API}/daily-region-data"],
            "respondents": RESPONDENTS, "timezone_framing": TZ, "start": START,
            "wall": "knowable_from = period + 2 calendar days (measured worst case, S98 sweep T+2)",
            "revision_note": "retrieval-dated snapshot; EIA revises early days at the margin",
            "n_days": len(days), "first": min(days) if days else None, "last": max(days) if days else None,
        },
        "days": days,
    }
    with gzip.open(STORE_PATH, "wt", encoding="utf-8") as f:
        json.dump(store, f)
    print(f"[grid_stack] store written: {len(days)} days {store['meta']['first']}..{store['meta']['last']}")
    return store


_CACHE: dict | None = None


def load_store() -> dict | None:
    global _CACHE
    if _CACHE is None and os.path.exists(STORE_PATH):
        with gzip.open(STORE_PATH, "rt", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def _ba_read(days: dict, period: str, ba: str) -> dict | None:
    d = days.get(period, {}).get(ba)
    if not d:
        return None
    gen = d.get("gen_mwh", {})
    total = sum(v for v in gen.values() if v is not None) or None
    gas, sun, wnd = gen.get("NG"), gen.get("SUN"), gen.get("WND")
    # S113 (A-16 / G-19): the pull sets NO fueltype facet, so gen_mwh already holds EVERY fuel EIA
    # reports and this read hand-picked five of them. Hydro has therefore been on disk since
    # START=2019-01-01 and served to nobody - the stack's third forcing, and per Greg an INVERTED U
    # whose BOTH TAILS ARE BULLISH GAS (flood spill past a river stage bypasses the turbines; drought
    # drawdown starves them), so it needs a STATE, not a level, and a single bar on it will be wrong
    # in one tail. Measured on the restored store, US48 2026-07-15: WAT 675,777 MWh = 4.6% of
    # generation, against a weekly storage change of +/-67-91 Bcf.
    # PUMPED STORAGE AND BATTERY ARE SEPARATE CODES HERE, WHICH MATTERS AND WAS NOT ASSUMED: PS and
    # BAT come back as their own fuels for US48 and SOCO. A-20 warned that EIA-930 folds pumped
    # storage into WAT "wherever a BA cannot separate it" and told us to check per BA rather than
    # assume - checked: PJM returns no PS key at all, so separability IS per-BA and wat_is_separable
    # declares it per row instead of leaving a reader to guess. Pumped storage follows price and load
    # shape, not water, so a BA where it is folded in has a different quantity under the same name.
    # G-19: battery became its own EIA-930 category in Q1 2025 and is the reason a hot evening no
    # longer produces the peaker burn the temperature implies - the evening ramp is exactly where gas
    # used to be the only answer.
    wat, ps, bat = gen.get("WAT"), gen.get("PS"), gen.get("BAT")
    named = ("NG", "SUN", "WND", "COL", "NUC", "WAT", "PS", "BAT")
    unnamed = sum(v for k, v in gen.items() if k not in named and v is not None) or None

    def ref(k: int, fuel: str):
        rp = (datetime.date.fromisoformat(period) - datetime.timedelta(days=k)).isoformat()
        rg = days.get(rp, {}).get(ba, {}).get("gen_mwh", {})
        return rg.get(fuel)

    def chg(cur, prev):
        return round(cur - prev, 1) if (cur is not None and prev is not None) else None

    out = {
        "demand_mwh": d.get("demand_mwh"),
        "demand_forecast_mwh": d.get("demand_forecast_mwh"),
        # A-32: NET total interchange. POSITIVE = net EXPORTER (surplus to sell), NEGATIVE = net
        # IMPORTER (leaning on neighbours). Toward zero across many BAs at once = nobody has surplus,
        # the import route to reliability has closed, and load must be self-served.
        "interchange_mwh": d.get("interchange_mwh"),
        "gas_mwh": gas, "solar_mwh": sun, "wind_mwh": wnd,
        "coal_mwh": gen.get("COL"), "nuclear_mwh": gen.get("NUC"),
        "hydro_mwh": wat,
        "pumped_storage_mwh": ps,
        "battery_mwh": bat,
        # DECLARED PER ROW, never inferred: True = this BA reports PS separately, so hydro_mwh is
        # water-driven conventional hydro. False = no PS key, so any pumped storage this BA runs is
        # folded into WAT and hydro_mwh is a MIXTURE of a water-driven forcing and a price-driven
        # arbitrage. Same name, different quantity - which is exactly how a coefficient fitted on one
        # BA fails silently on another (A-20).
        "wat_is_separable_from_pumped_storage": ps is not None,
        "unnamed_gen_mwh": round(unnamed, 1) if unnamed else None,
        "total_gen_mwh": round(total, 1) if total else None,
        "hydro_share": round(wat / total, 4) if (wat is not None and total) else None,
        "hydro_chg_7d_mwh": chg(wat, ref(7, "WAT")),
        "gas_share": round(gas / total, 4) if (gas is not None and total) else None,
        "solar_share": round(sun / total, 4) if (sun is not None and total) else None,
        "gas_chg_7d_mwh": chg(gas, ref(7, "NG")),
        "solar_chg_7d_mwh": chg(sun, ref(7, "SUN")),
    }
    if ba == "US48" and gas is not None:
        # the sweep's stated method verbatim: burn_bcfd ~= MWh_per_day x 7900 / 1.035e9
        out["est_gas_burn_bcfd"] = round(gas * HEAT_RATE_BTU_PER_KWH / 1.035e9, 1)
    return out


def grid_stack_asof(iso: str) -> dict | None:
    """Latest EIA-930 daily read knowable at iso (wall: knowable_from = period + 2). Per-BA blocks,
    never pooled; US48 is its own respondent row and carries the labeled power-burn estimate.
    None before coverage."""
    store = load_store()
    if not store:
        return None
    days = store["days"]
    cutoff = (datetime.date.fromisoformat(iso) - datetime.timedelta(days=2)).isoformat()
    prior = [p for p in days if p <= cutoff]
    if not prior:
        return None
    p = max(prior)
    bas = {ba: _ba_read(days, p, ba) for ba in RESPONDENTS}
    return {
        "period": p,
        "age_days": (datetime.date.fromisoformat(iso) - datetime.date.fromisoformat(p)).days,
        "bas": bas,
        "note": "EIA-930 daily, Eastern framing, wall period+2; est_gas_burn_bcfd is an ESTIMATE "
                "(gas MWh x 7,900 Btu/kWh STEO-implied heat rate - stated method, not a "
                "measurement); demand_forecast_mwh is the BA's own day-ahead forecast as "
                "republished by EIA; per-BA always, US48 is a respondent not a pool. "
                "PARK NOTE (D12, S113): hydro_mwh, pumped_storage_mwh, battery_mwh and "
                "unnamed_gen_mwh are served as CONTEXT CHANNELS with no play consuming them yet - "
                "the play-side work is A-15 (the thermal stack has zero readers) and A-20 (the "
                "hydro carry), both of which touch the brain and are Greg's adjudication, not a "
                "staging change. Declared rather than left to be discovered, because served-and-"
                "unread is this desk's recurring defect and a fifth silent field would repeat it. "
                "READ hydro_mwh AS A STATE, NOT A LEVEL: the water-to-output curve is an INVERTED U "
                "and both tails are bullish gas - past a river stage the Army Corps has the gates "
                "opened and water goes through the SPILLWAY INSTEAD OF THE TURBINES, while drought "
                "drawdown starves the same turbines - so one low reading comes from two opposite "
                "states and a single bar on it is wrong in one tail. "
                "AND CHECK wat_is_separable_from_pumped_storage BEFORE COMPARING TWO BAs: measured "
                "2026-07-15, only US48 and SOCO report PS as its own fuel; PJM, MISO, ERCO, SWPP "
                "and CISO do not, so for those five hydro_mwh MIXES a water-driven forcing with a "
                "price-driven arbitrage under one name. CISO is the sharpest case at 10.7% hydro "
                "share with no separation. battery_mwh is NET and goes NEGATIVE while charging "
                "(SOCO -103 on that date), so it is not a generation term to sum naively",
    }


def _t(cond, msg, fails):
    print(("  PASS " if cond else "  FAIL ") + msg)
    return fails + (0 if cond else 1)


def _selftest() -> int:
    print("=== grid_stack --selftest ===")
    fails = 0
    store = load_store()
    fails = _t(store is not None, "store present", fails)
    if store is None:
        return 1
    days = store["days"]
    fails = _t(min(days) == "2019-01-01" and len(days) > 2700, f"coverage {min(days)}..{max(days)} ({len(days)} days)", fails)
    # sweep demonstration pins (S98 EIA_BALANCE_OPTIONS sec 5): US48 gas gen through the freeze
    for period, exp_mwh, exp_bcfd in [("2026-01-10", 3.71e6, 28.3), ("2026-01-20", 5.39e6, 41.1),
                                      ("2026-01-25", 5.60e6, 42.8), ("2026-01-28", 5.46e6, 41.7)]:
        g = days.get(period, {}).get("US48", {}).get("gen_mwh", {}).get("NG")
        ok = g is not None and abs(g - exp_mwh) / exp_mwh < 0.015
        fails = _t(ok, f"US48 gas {period}: {g and round(g/1e6,2)}M MWh (sweep ~{exp_mwh/1e6:.2f}M)", fails)
        if ok:
            est = round(g * HEAT_RATE_BTU_PER_KWH / 1.035e9, 1)
            fails = _t(abs(est - exp_bcfd) < 0.7, f"  est burn {est} Bcf/d (sweep ~{exp_bcfd})", fails)
    # per-BA presence + solar displacement readable (CISO solar is the duck curve's home)
    j20 = days.get("2026-01-20", {})
    fails = _t(all(ba in j20 for ba in RESPONDENTS), "all 7 respondents present on 2026-01-20", fails)
    fails = _t((j20.get("CISO", {}).get("gen_mwh", {}).get("SUN") or 0) > 0, "CISO solar nonzero on 2026-01-20", fails)
    # demand + forecast populated
    fails = _t(j20.get("ERCO", {}).get("demand_mwh") is not None, "ERCO demand present", fails)
    fails = _t(j20.get("ERCO", {}).get("demand_forecast_mwh") is not None, "ERCO day-ahead forecast present", fails)
    # blind wall: on iso the newest visible period is <= iso-2
    a = grid_stack_asof("2026-01-22")
    fails = _t(a is not None and a["period"] == "2026-01-20" and a["age_days"] == 2,
               f"asof 2026-01-22 -> period {a and a['period']} age {a and a['age_days']}", fails)
    fails = _t(grid_stack_asof("2019-01-01") is None, "pre-coverage -> None", fails)
    # blind-wall walk over the walked window
    d = datetime.date(2025, 11, 3)
    bad = 0
    while d <= datetime.date(2026, 2, 27):
        if d.weekday() < 5 or d.weekday() == 6:
            r = grid_stack_asof(d.isoformat())
            if r is None or not (r["period"] <= (d - datetime.timedelta(days=2)).isoformat()):
                bad += 1
        d += datetime.timedelta(days=1)
    fails = _t(bad == 0, f"blind-wall walk Nov 3 - Feb 27: {bad} violations (expect 0)", fails)
    print(f"=== selftest {'PASS' if fails == 0 else f'FAIL ({fails})'} ===")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="EIA-930 daily grid stack feed (feed Q)")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show", metavar="DATE")
    a = ap.parse_args()
    if a.build:
        build()
        return 0
    if a.selftest:
        return _selftest()
    if a.show:
        print(json.dumps(grid_stack_asof(a.show), indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
