"""build_realized_forcings.py - the VALIDATION TARGET for the GEFS forcing proxies (S114).

WHY THIS EXISTS
---------------
gefs_ensemble.py turns GEFS members into forcing proxies: wind_power_proxy (mean |V10|^3 over a
CONUS grid), solar_irradiance_proxy (mean DSWRF), precip_proxy (accumulated APCP). Those are
METEOROLOGICAL FIELDS, not MWh. A wind-speed-cubed average is not generation: it ignores the
fleet's spatial distribution, its power curve (cut-in ~3 m/s, rated ~12 m/s, cut-out ~25 m/s -
the cube law holds only between cut-in and rated), hub height vs 10 m, curtailment, and outages.
The proxy is only usable if it TRACKS realized generation, and that has to be measured, not
assumed. This module builds the thing it must be measured against.

THE TARGET: EIA-930 US48 daily WND and SUN, via grid_stack.load_store() - imported, never
reimplemented, so the target and the desk's served grid stack are the same numbers by
construction.

WIND AND SOLAR ARE NEVER SUMMED. They are seasonally ANTI-CORRELATED (measured on this very
series: see --dist). A "renewables" term is a composite of two opposite annual cycles and any
coefficient fitted on it is fitted on their ratio, which is a season proxy, not a forcing.

WHAT THIS SERIES IS NOT
-----------------------
1. NOT total solar. EIA-930 counts UTILITY-SCALE solar only; behind-the-meter (rooftop) solar is
   invisible to it. DSWRF over the grid sees all of it. So the solar proxy is being validated
   against a strict subset of the physical response, and the subset's share of total PV changes
   over time.
2. NOT a stationary series. The fleet GREW: US48 daily solar runs ~1e5 MWh in Jan 2019 and ~1.2e6
   MWh in Aug 2026. Any level relation fitted across years is fitting capacity growth, not
   meteorology. Validation must be per-cell (month, and a recent-capacity window), never pooled
   across the span - see --dist, which prints per-month distributions AND the per-year drift that
   would otherwise be laundered into them.
3. NOT a blind-legal read as written. This is the REALIZED value, for scoring. Serving it forward
   goes through grid_stack_asof(), which enforces knowable_from = period + 2.

USAGE
-----
  python research/kalshi/build_realized_forcings.py --build        # write the CSV
  python research/kalshi/build_realized_forcings.py --verify       # reconcile vs live EIA + guard
  python research/kalshi/build_realized_forcings.py --dist         # per-month distributions
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grid_stack  # noqa: E402  - the target must come from the desk's own store, not a re-pull

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store",
                        "realized_forcings_us48.csv")
BA = "US48"
RECON_TOL_PCT = 0.01   # store-vs-live: EIA-930 revises, but a faithful snapshot should be exact


# ----------------------------------------------------------------------------- extract

def extract() -> tuple[list[tuple[str, float, float]], list[str]]:
    """(rows, absent) - rows sorted by date; absent = day keys present in the store whose US48
    WND or SUN is missing. Absent days are DECLARED and DROPPED, never interpolated."""
    store = grid_stack.load_store()
    if not store:
        raise RuntimeError(
            "grid_stack store absent. data/ is disposable (D34): run restore_substrate.py, or "
            "python research/kalshi/grid_stack.py --build")
    days = store["days"]
    rows, absent = [], []
    for period in sorted(days):
        gen = days[period].get(BA, {}).get("gen_mwh", {})
        w, s = gen.get("WND"), gen.get("SUN")
        if w is None or s is None:
            absent.append(period)
            continue
        rows.append((period, float(w), float(s)))
    return rows, absent


def build() -> int:
    rows, absent = extract()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    # newline="" + explicit lineterminator: byte-identical output on any platform, so a rebuild
    # that changes nothing produces no diff.
    with open(OUT_PATH, "w", newline="", encoding="ascii") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "wind_mwh", "solar_mwh"])
        for d, wi, so in rows:
            w.writerow([d, f"{wi:.1f}", f"{so:.1f}"])
    print(f"[forcings] wrote {OUT_PATH}")
    print(f"[forcings] {len(rows)} rows  {rows[0][0]}..{rows[-1][0]}")
    _gaps(rows, absent)
    return 0


def _gaps(rows, absent) -> None:
    have = {d for d, _, _ in rows}
    d0 = datetime.date.fromisoformat(rows[0][0])
    d1 = datetime.date.fromisoformat(rows[-1][0])
    missing, d = [], d0
    while d <= d1:
        if d.isoformat() not in have:
            missing.append(d.isoformat())
        d += datetime.timedelta(days=1)
    span = (d1 - d0).days + 1
    print(f"[forcings] calendar span {span} days; rows {len(rows)}; "
          f"interior gaps {len(missing)}")
    if missing:
        print(f"[forcings] MISSING (declared, not filled): {missing}")
    if absent:
        print(f"[forcings] store day-keys with US48 WND/SUN absent: {absent}")


# ----------------------------------------------------------------------------- reconcile

def _live(start: str, end: str) -> dict:
    """Fresh EIA v2 retrieval - independent of the local snapshot. Presence in the store is not
    correctness, and the store agreeing with itself is not evidence; only a separate retrieval
    settles whether the snapshot is faithful."""
    import creds
    import requests
    r = requests.get(
        "https://api.eia.gov/v2/electricity/rto/daily-fuel-type-data/data",
        params={"api_key": creds.get("EIA_API_KEY"), "data[]": ["value"],
                "start": start, "end": end,
                "facets[respondent][]": BA, "facets[timezone][]": grid_stack.TZ,
                "facets[fueltype][]": ["WND", "SUN"], "length": 5000,
                "sort[0][column]": "period", "sort[0][direction]": "asc"},
        timeout=120)
    r.raise_for_status()
    out = {}
    for row in r.json()["response"]["data"]:
        out.setdefault(row["period"], {})[row["fueltype"]] = float(row["value"])
    return out


def reconcile(windows, rows, tol_pct: float = RECON_TOL_PCT) -> int:
    """Returns the number of BREACHES. Prints every comparison window and every breach."""
    idx = {d: (w, s) for d, w, s in rows}
    breaches = 0
    for start, end in windows:
        live = _live(start, end)
        n, worst, absent = 0, 0.0, 0
        for period, fuels in sorted(live.items()):
            if period not in idx:
                absent += 1
                continue
            mine = {"WND": idx[period][0], "SUN": idx[period][1]}
            for fuel, lv in fuels.items():
                sv = mine[fuel]
                pct = abs(sv - lv) / lv * 100.0 if lv else 0.0
                n += 1
                worst = max(worst, pct)
                if pct > tol_pct:
                    breaches += 1
                    print(f"  BREACH {period} {fuel}: csv={sv:.1f} live={lv:.1f} "
                          f"dev={pct:.4f}% > tol {tol_pct}%")
        print(f"  {start}..{end}: compared {n} values, absent-from-csv {absent}, "
              f"worst dev {worst:.4f}%")
    print(f"[reconcile] breaches: {breaches}")
    return breaches


def verify() -> int:
    """Reconcile against live EIA, then NEGATIVE-TEST the breach branch by corrupting a value.

    NC-3: a guard whose firing branch never executed has not been tested. The positive pass below
    prints 'breaches: 0', which proves nothing about the branch that reports a breach - so the
    second block deliberately corrupts one row and requires the guard to catch it.
    """
    rows, _ = extract()
    windows = [("2019-03-01", "2019-03-07"), ("2021-08-10", "2021-08-16"),
               ("2023-01-15", "2023-01-21"), ("2025-12-20", "2025-12-26"),
               ("2026-06-24", "2026-06-30")]
    print("=== POSITIVE: csv vs fresh EIA retrieval ===")
    clean = reconcile(windows, rows)

    print("=== NEGATIVE: corrupt one value, the guard MUST fire ===")
    bad = list(rows)
    for i, (d, w, s) in enumerate(bad):
        if d == "2026-06-29":
            bad[i] = (d, w * 1.05, s)   # +5% on the 0629 wind day
            print(f"  corrupted {d} wind_mwh {w:.1f} -> {w * 1.05:.1f}")
            break
    fired = reconcile([("2026-06-24", "2026-06-30")], bad)

    ok = (clean == 0 and fired >= 1)
    print(f"=== verify {'PASS' if ok else 'FAIL'} "
          f"(clean breaches={clean} expect 0; corrupted breaches={fired} expect >=1) ===")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- distribution

def _pct(sorted_vals, q: float) -> float:
    """Nearest-rank percentile on the sorted sample. No interpolation, no fitted anything."""
    if not sorted_vals:
        return float("nan")
    k = max(0, min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def _month_table(rows, col: int, label: str, lo_year: int | None = None) -> None:
    buckets: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for r in rows:
        y = int(r[0][:4])
        if lo_year is not None and y < lo_year:
            continue
        buckets[int(r[0][5:7])].append(r[col])
    scope = f"{lo_year}+" if lo_year else "full span"
    print(f"\n--- {label} MWh/day by calendar month ({scope}) ---")
    print(f"{'mon':>4} {'n':>5} {'min':>10} {'p10':>10} {'p50':>10} {'p90':>10} {'max':>10} "
          f"{'p90/p10':>8}")
    for m in range(1, 13):
        v = sorted(buckets[m])
        if not v:
            print(f"{m:>4} {0:>5}   (no data)")
            continue
        p10, p50, p90 = _pct(v, .10), _pct(v, .50), _pct(v, .90)
        print(f"{m:>4} {len(v):>5} {v[0]:>10.0f} {p10:>10.0f} {p50:>10.0f} {p90:>10.0f} "
              f"{v[-1]:>10.0f} {(p90/p10 if p10 else float('nan')):>8.2f}")


def _year_drift(rows, col: int, label: str, month: int) -> None:
    """The capacity confound, shown rather than argued: the same calendar month, year by year."""
    by_year: dict[int, list[float]] = {}
    for r in rows:
        if int(r[0][5:7]) == month:
            by_year.setdefault(int(r[0][:4]), []).append(r[col])
    print(f"\n--- {label}: month {month:02d} p50 by YEAR (capacity drift, not weather) ---")
    for y in sorted(by_year):
        v = sorted(by_year[y])
        print(f"  {y}  n={len(v):>3}  p50 {_pct(v, .50):>10.0f}")


def _episodes(rows, col: int, label: str, lo_year: int) -> None:
    """How many INDEPENDENT draws does a day count actually represent?

    Wind and solar anomalies persist on the synoptic timescale, so N days is not N observations
    and a validation's real sample size is the number of weather EPISODES, not rows. Measured
    without averaging anything: inside each (year, month) cell take that cell's own median, mark
    each day above/below it, and report the RUN-LENGTH DISTRIBUTION. Runs are the episodes. Cells
    are never pooled and no autocorrelation coefficient is computed - a correlation is an average
    (D37) and would hide exactly the cell-to-cell variation this is meant to expose.
    """
    cells: dict[tuple[int, int], list[tuple[str, float]]] = {}
    for r in rows:
        y, m = int(r[0][:4]), int(r[0][5:7])
        if y >= lo_year:
            cells.setdefault((y, m), []).append((r[0], r[col]))
    runs: list[int] = []
    for key in sorted(cells):
        seq = sorted(cells[key])
        med = _pct(sorted(v for _, v in seq), .50)
        cur, prev = 0, None
        for _, v in seq:
            side = v >= med
            if side == prev:
                cur += 1
            else:
                if cur:
                    runs.append(cur)
                cur, prev = 1, side
        if cur:
            runs.append(cur)
    hist: dict[str, int] = {}
    for r_ in runs:
        hist[str(r_) if r_ < 5 else "5+"] = hist.get(str(r_) if r_ < 5 else "5+", 0) + 1
    ndays = sum(len(v) for v in cells.values())
    print(f"\n--- {label} episode count ({lo_year}+, {len(cells)} year-month cells) ---")
    print(f"  days {ndays}   runs (episodes) {len(runs)}   days per episode "
          f"{ndays / len(runs):.2f}")
    print("  run-length histogram: " +
          "  ".join(f"len {k}: {hist[k]}" for k in sorted(hist, key=lambda x: (x == "5+", x))))


def dist() -> int:
    rows, _ = extract()
    print(f"[dist] {len(rows)} days {rows[0][0]}..{rows[-1][0]}")
    _month_table(rows, 1, "WIND")
    _month_table(rows, 2, "SOLAR")
    _month_table(rows, 1, "WIND", lo_year=2025)
    _month_table(rows, 2, "SOLAR", lo_year=2025)
    _year_drift(rows, 2, "SOLAR", 7)
    _year_drift(rows, 1, "WIND", 4)
    _episodes(rows, 1, "WIND", 2025)
    _episodes(rows, 2, "SOLAR", 2025)
    _episodes(rows, 1, "WIND", 2019)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="US48 realized wind/solar - the GEFS proxy target")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dist", action="store_true")
    a = ap.parse_args()
    if a.build:
        return build()
    if a.verify:
        return verify()
    if a.dist:
        return dist()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
