"""gefs_validate.py - does the GEFS forward forcing proxy TRACK realized US48 output? (S114, G-5.)

THE ONE QUESTION. gefs_ensemble.py turns GEFS members into FORCING PROXIES - a capacity-weighted
turbine-power-curve number for wind, mean downward shortwave for solar, accumulated precip. Those
are METEOROLOGICAL FIELDS, not MWh. Nothing built on them is legitimate until somebody measures
whether they move with realized generation. This module is that measurement and nothing else. It
does not fetch, it does not serve, and it does not decide what to do with the answer.

HOW IT REFUSES TO LIE, point by point, because each rule here was bought with a past failure:

1. PER EVENT, NEVER POOLED (D37). There is no R2 in this file, no pooled correlation, and no
   fitted slope reported as evidence - CLAUDE.md is explicit that all three ARE averages, and this
   desk has already shipped a pooled correlation whose sign was the opposite of every constituent
   seasonal cell. The primary result is a COUNT of days whose direction-of-change matched, with
   every day NAMED in a table, celled by month. The arithmetic total across cells is printed as a
   count of those named days and is labelled as not a verdict.

2. WIND AND SOLAR SEPARATELY, ALWAYS. They are seasonally ANTI-correlated (our own EIA-930: wind
   9.9 TWh/wk April vs 5.9 August; solar 3.5 June vs 1.4 December). A "renewables" term is a
   composite of two opposite annual cycles, so any number fitted on it is fitted on their ratio,
   which is a season proxy. This module never adds them. There is no code path that can.

3. MONTH CELLS, and the cell is YYYY-MM rather than month-of-year on purpose: the solar fleet GREW
   from ~1e5 MWh/day in 2019 to ~1.2e6 in 2026, so pooling the same calendar month across years
   measures capacity, not meteorology.

4. A NAMED BENCHMARK FOR EVERY NUMBER (A-1). Direction is scored against TWO: the 50% coin flip,
   and the cell's own MAJORITY-CLASS rate - because on a series that rises 70% of days, 70% is
   worthless. Level is scored against PERSISTENCE (tomorrow equals today) and the within-month
   LEAVE-ONE-OUT CLIMATOLOGICAL MEAN, both printed through per_event.report so the D4 set and the
   largest actual moves appear beside every error number.

5. n < 5 IS REFUSED, not reported. A cell below the floor is named, its n is stated, and it is
   excluded from every count.

THE ALIGNMENT TRAP, recorded because it already voided two validations in this session. The
forecast for day D must be compared to the realized value FOR PERIOD D. EIA-930 publishes with a
two-day lag, so the desk's blind-legal as-of view grid_stack_asof(D) returns period D-2, and
comparing against it scored 37% wind - BELOW the coin flip, because a two-day offset on an
autocorrelated series produces a wrong-sign result rather than a merely weak one. The same data
correctly aligned scored 84%. This module therefore joins PERIOD-KEYED realized values
(store/realized_forcings_us48.csv, written by build_realized_forcings.py from the period-keyed
store) to the proxy's own `day`, on the ISO date, and states that join in its output. It is a
scoring harness, not a serving path: the realized value is the answer key and is never blind-legal.

WHAT A PASS HERE DOES AND DOES NOT LICENSE. A direction result on the CHANGE is not a level claim.
The proxy's level is biased - a coarse grid, a generic power curve, and utility-scale-only realized
solar that misses every rooftop panel. The level section exists to size that bias against named
benchmarks, and it depends on a leave-one-out within-cell calibration ratio which is declared as a
NUISANCE PARAMETER, never as the finding.

USAGE
  python gefs_validate.py report --csv store/realized_forcings_us48.csv --proxy <series.json>
  python gefs_validate.py selftest

  from gefs_validate import validate, print_report
  res = validate(proxy_rows, "store/realized_forcings_us48.csv")

The proxy input is whatever `gefs_ensemble.py series --out X.json` wrote: a {day: record} map (a
list of records carrying `day` is accepted too). Records may carry the proxy as the ensemble
distribution dict, in which case p50 is read and the choice is declared in the output, or as a
plain number.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from per_event import report as per_event_report  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REALIZED_CSV = os.path.join(HERE, "store", "realized_forcings_us48.csv")

MIN_CELL_N = 5          # a cell below this is REFUSED, never reported
MAX_GAP_DAYS = 4        # Fri->Tue after a holiday; a wider gap is named and excluded
P_THRESHOLD = 0.10      # one-sided exact binomial vs the stronger of the two named benchmarks

# Field aliases. gefs_ensemble.py has renamed the wind field once already this session
# (wind_power_proxy -> wind_cf_proxy when the raw cube was replaced by a turbine power curve), and
# it is being edited by another process right now, so both names are accepted and the one actually
# found is REPORTED rather than assumed.
PROXY_FIELDS = {
    "wind": ("wind_cf_proxy", "wind_power_proxy", "wind_proxy"),
    "solar": ("solar_irradiance_proxy", "solar_proxy"),
}
REALIZED_COL = {"wind": "wind_mwh", "solar": "solar_mwh"}
FORCINGS = ("wind", "solar")   # deliberately a pair of independent lanes, never a sum

NEVER_SUMMED = ("wind and solar are scored in SEPARATE lanes and are never added. They are "
                "seasonally ANTI-correlated, so a combined renewables term is a composite of two "
                "opposite annual cycles and any number fitted on it is fitted on their ratio, "
                "which is a season proxy rather than a forcing (D37).")

ALIGNMENT_NOTE = ("forecast for day D is joined to REALIZED PERIOD D on the ISO date. The realized "
                  "CSV is period-keyed. Do NOT score against grid_stack_asof(D), which returns "
                  "period D-2 by design (EIA-930 publishes with a two-day lag); that misalignment "
                  "scored 37 percent wind - below the coin flip - on a proxy that scores 84 "
                  "percent when correctly aligned.")


class RealizedMissing(FileNotFoundError):
    pass


class ProxyMissing(FileNotFoundError):
    pass


class SyntheticDataRefused(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------
# small helpers - no scipy, no numpy, nothing that could quietly average something
# --------------------------------------------------------------------------------------------
def _iso(s):
    """Accept 20260629 / 2026-06-29 / a date object. Anything else is named, not guessed."""
    if isinstance(s, (dt.date, dt.datetime)):
        return s.strftime("%Y-%m-%d")
    t = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("gefs_validate: unparseable date %r" % (s,))


def _days_between(a, b):
    da = dt.datetime.strptime(a, "%Y-%m-%d").date()
    db = dt.datetime.strptime(b, "%Y-%m-%d").date()
    return (db - da).days


def _median(vals):
    v = sorted(vals)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def _q(vals, p):
    v = sorted(vals)
    return v[int(p * (len(v) - 1))] if v else None


def _binom_tail(m, n, p):
    """P(X >= m) for X ~ Binomial(n, p). Exact, integer binomials - a per-cell tail probability,
    not an average across cells, and never reported alone as a verdict."""
    if n <= 0:
        return 1.0
    m = max(0, min(m, n))
    return sum(math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(m, n + 1))


def _sign(x, eps=0.0):
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


# --------------------------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------------------------
def load_realized(path):
    """Period-keyed realized US48 wind/solar. Absence is DECLARED, never filled."""
    if not path or not os.path.exists(path):
        raise RealizedMissing(
            "gefs_validate: the realized target is NOT PRESENT at %s .\n"
            "  This harness will not invent it. That file is written by\n"
            "    python research/kalshi/build_realized_forcings.py --build\n"
            "  and must carry columns date,wind_mwh,solar_mwh (EIA-930 US48 daily, period-keyed).\n"
            "  Until it exists there is no answer key and no validation is possible."
            % path)
    out, bad = {}, []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rdr = csv.DictReader(fh)
        cols = rdr.fieldnames or []
        need = ["date"] + [REALIZED_COL[f] for f in FORCINGS]
        missing = [c for c in need if c not in cols]
        if missing:
            raise RealizedMissing(
                "gefs_validate: %s is present but missing column(s) %s - found %s. "
                "Presence is not correctness; refusing to score against a file whose columns "
                "do not match the contract date,wind_mwh,solar_mwh."
                % (path, ",".join(missing), ",".join(cols)))
        for row in rdr:
            try:
                d = _iso(row["date"])
            except ValueError:
                bad.append(str(row.get("date")))
                continue
            rec = {}
            for f in FORCINGS:
                raw = (row.get(REALIZED_COL[f]) or "").strip()
                try:
                    rec[f] = float(raw)
                except (TypeError, ValueError):
                    rec[f] = None
            out[d] = rec
    if not out:
        raise RealizedMissing("gefs_validate: %s parsed to ZERO rows." % path)
    return out, {"path": path, "rows": len(out), "unparseable_dates": bad,
                 "span": [min(out), max(out)]}


def normalize_proxy(proxy_rows):
    """{day: record} from either a map or a list. Records carrying an `error` key are DROPPED and
    named - a failed retrieval must never enter the sample as a silent gap."""
    if proxy_rows is None:
        return {}, []
    items = []
    if isinstance(proxy_rows, dict):
        items = list(proxy_rows.items())
    elif isinstance(proxy_rows, list):
        for r in proxy_rows:
            if not isinstance(r, dict):
                continue
            items.append((r.get("day"), r))
    else:
        raise TypeError("gefs_validate: proxy_rows must be a {day: record} map or a list of "
                        "records, got %s" % type(proxy_rows).__name__)
    out, dropped = {}, []
    for k, rec in items:
        if not isinstance(rec, dict):
            dropped.append("%s: not a record" % (k,))
            continue
        day = rec.get("day", k)
        try:
            day = _iso(day)
        except ValueError:
            dropped.append("%s: unparseable day" % (k,))
            continue
        if rec.get("error"):
            dropped.append("%s: retrieval error %s" % (day, str(rec["error"])[:60]))
            continue
        out[day] = rec
    return out, dropped


def _scalar(rec, names):
    """(value, field_name, statistic) or (None, None, None). A distribution dict is read at p50 and
    that choice is REPORTED, not buried."""
    for n in names:
        if n in rec and rec[n] is not None:
            v = rec[n]
            if isinstance(v, dict):
                if v.get("p50") is None:
                    continue
                return float(v["p50"]), n, "p50"
            try:
                return float(v), n, "value"
            except (TypeError, ValueError):
                continue
    return None, None, None


def _assert_not_synthetic(proxy, allow):
    """NC-3 guard. Its firing branch is executed by the selftest and its output is printed."""
    tagged = sorted(d for d, r in proxy.items() if r.get("synthetic") or r.get("SYNTHETIC"))
    if tagged and not allow:
        msg = ("gefs_validate GUARD FIRED - SYNTHETIC ROWS IN THE REPORT PATH. %d record(s) carry "
               "a `synthetic` tag (%s%s). Synthetic data is legal ONLY inside the selftest, which "
               "passes allow_synthetic=True explicitly. Refusing to produce a validation report."
               % (len(tagged), ", ".join(tagged[:4]), " ..." if len(tagged) > 4 else ""))
        print(msg)
        raise SyntheticDataRefused(msg)
    return tagged


# --------------------------------------------------------------------------------------------
# the measurement
# --------------------------------------------------------------------------------------------
def _events_for(forcing, proxy, realized, max_gap):
    """Consecutive-pair events on the INTERSECTION of the two series.

    Both sides use the SAME pair of dates, so a weekend gap is a legitimate three-day change on
    both - what would not be legitimate is comparing a one-day proxy change to a three-day realized
    change. Every exclusion is returned with its reason and its day named.
    """
    names = PROXY_FIELDS[forcing]
    have, field_used, stat_used, no_field = {}, None, None, []
    for d, rec in proxy.items():
        v, fname, stat = _scalar(rec, names)
        if v is None:
            no_field.append(d)
            continue
        have[d] = v
        field_used = field_used or fname
        stat_used = stat_used or stat
        if fname != field_used:
            raise ValueError("gefs_validate: the %s proxy is spelled %s on some days and %s on "
                             "others - refusing to mix two fields into one series."
                             % (forcing, field_used, fname))
    common = sorted(d for d in have if d in realized and realized[d].get(forcing) is not None)
    excluded = [{"day": d, "reason": "proxy has no %s field" % forcing} for d in sorted(no_field)]
    for d in sorted(have):
        if d not in realized:
            excluded.append({"day": d, "reason": "no realized row for that period"})
        elif realized[d].get(forcing) is None:
            excluded.append({"day": d, "reason": "realized %s is blank" % forcing})

    events = []
    for i in range(1, len(common)):
        prev, cur = common[i - 1], common[i]
        gap = _days_between(prev, cur)
        if gap > max_gap:
            excluded.append({"day": cur, "reason": "gap of %d days from %s exceeds the %d-day "
                                                   "limit" % (gap, prev, max_gap)})
            continue
        dp = have[cur] - have[prev]
        dr = realized[cur][forcing] - realized[prev][forcing]
        sp, sr = _sign(dp), _sign(dr)
        ev = {"day": cur, "prev": prev, "gap_days": gap,
              "proxy_prev": have[prev], "proxy": have[cur], "d_proxy": dp,
              "realized_prev": realized[prev][forcing], "realized": realized[cur][forcing],
              "d_realized": dr, "proxy_dir": sp, "realized_dir": sr,
              "tie": (sp == 0 or sr == 0),
              "match": (sp != 0 and sp == sr)}
        events.append(ev)
    return events, excluded, {"field": field_used, "statistic": stat_used,
                              "days_with_field": len(have), "days_joined": len(common)}


def _level_block(cell_events):
    """Proxy vs PERSISTENCE and vs the within-cell LEAVE-ONE-OUT CLIMATOLOGICAL MEAN.

    The proxy is meteorology, so it needs a scale to be comparable in MWh at all. That scale is a
    LEAVE-ONE-OUT median ratio inside the cell: a NUISANCE PARAMETER, declared, never the finding.
    Leave-one-out because a day must not help set the scale that predicts it.
    """
    usable = [e for e in cell_events if e["proxy"] and e["proxy"] > 0]
    if len(usable) < 4:
        return {"available": False,
                "why": "fewer than 4 days with a positive proxy value - no leave-one-out "
                       "calibration is possible without a day helping predict itself"}
    keys, actual, pers, clim, cal = [], [], [], [], []
    for i, e in enumerate(usable):
        others = [o for j, o in enumerate(usable) if j != i]
        ratio = _median([o["realized"] / o["proxy"] for o in others])
        keys.append(e["day"])
        actual.append(e["realized"])
        pers.append(e["realized_prev"])
        clim.append(sum(o["realized"] for o in others) / float(len(others)))
        cal.append(ratio * e["proxy"])

    def stats(pred):
        err = [a - p for a, p in zip(actual, pred)]
        return {"sum_abs_err": sum(abs(x) for x in err), "drift": sum(err),
                "abs_p50": _q([abs(x) for x in err], 0.5),
                "abs_p90": _q([abs(x) for x in err], 0.9),
                "abs_max": max(abs(x) for x in err)}

    sp, sc, sx = stats(pers), stats(clim), stats(cal)
    return {"available": True, "n": len(keys), "units": "MWh",
            "calibration": "leave-one-out within-cell median of realized/proxy - a NUISANCE "
                           "parameter, not the finding",
            "keys": keys, "actual": actual,
            "persistence": pers, "climatology_loo": clim, "proxy_calibrated": cal,
            "stats": {"persistence": sp, "climatology_loo": sc, "proxy_calibrated": sx},
            "beat_persistence": sum(1 for a, p, c in zip(actual, pers, cal)
                                    if abs(a - c) < abs(a - p)),
            "beat_climatology": sum(1 for a, p, c in zip(actual, clim, cal)
                                    if abs(a - c) < abs(a - p))}


def _cell_verdict(matched, n, coin, major, pval, p_threshold):
    bench = max(coin, major)
    rate = matched / float(n)
    if rate <= bench:
        return "NOT_TRACKING", bench
    if pval <= p_threshold:
        return "TRACKS", bench
    return "INCONCLUSIVE", bench


def validate(proxy_rows, realized_csv=REALIZED_CSV, *, min_cell_n=MIN_CELL_N,
             max_gap_days=MAX_GAP_DAYS, p_threshold=P_THRESHOLD, allow_synthetic=False):
    """Does the forward proxy track realized US48 output? Returns the whole record, per cell.

    Returns a dict; deliberately no scalar score exists anywhere in it that could be quoted out of
    context. Raises RealizedMissing if the answer key is absent, and SyntheticDataRefused if
    synthetic rows reach the report path.
    """
    realized, rmeta = load_realized(realized_csv)
    proxy, dropped = normalize_proxy(proxy_rows)
    synth = _assert_not_synthetic(proxy, allow_synthetic)

    res = {"generated_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "question": "does the GEFS forward forcing proxy track realized EIA-930 US48 output?",
           "realized": rmeta,
           "proxy_days": len(proxy),
           "proxy_span": [min(proxy), max(proxy)] if proxy else None,
           "proxy_dropped": dropped,
           "synthetic_rows": synth,
           "alignment": ALIGNMENT_NOTE,
           "never_summed": NEVER_SUMMED,
           "min_cell_n": min_cell_n,
           "max_gap_days": max_gap_days,
           "p_threshold": p_threshold,
           "method": ("primary result = a COUNT of days whose day-over-day direction matched, "
                      "celled by YYYY-MM, every day named. Benchmarks: the 50 percent coin flip "
                      "and the cell's own majority-class rate. No R2, no pooled correlation and "
                      "no fitted slope is reported anywhere - all three are averages (D37)."),
           "forcings": {}}

    if not proxy:
        res["verdict"] = ("REFUSED - the proxy series is EMPTY. Nothing was measured. Build it "
                          "with: python gefs_ensemble.py series --start YYYYMMDD --end YYYYMMDD "
                          "--members 1 --out <path>")
        for f in FORCINGS:
            res["forcings"][f] = {"verdict": "REFUSED - no proxy days", "cells": {},
                                  "refused_cells": {}, "excluded_events": []}
        return res

    for forcing in FORCINGS:
        events, excluded, prov = _events_for(forcing, proxy, realized, max_gap_days)
        cells = {}
        for e in events:
            cells.setdefault(e["day"][:7], []).append(e)

        scored, refused = {}, {}
        for cell in sorted(cells):
            evs = cells[cell]
            ties = [e for e in evs if e["tie"]]
            live = [e for e in evs if not e["tie"]]
            n = len(live)
            if n < min_cell_n:
                refused[cell] = {
                    "n_events": n, "n_ties_excluded": len(ties),
                    "days": [e["day"] for e in evs],
                    "refusal": ("REFUSED - n=%d is below the floor of %d. This cell is NOT scored "
                                "and contributes to no count." % (n, min_cell_n))}
                continue
            matched = sum(1 for e in live if e["match"])
            ups = sum(1 for e in live if e["realized_dir"] > 0)
            major = max(ups, n - ups) / float(n)
            bench = max(0.5, major)
            pval = _binom_tail(matched, n, bench)
            verdict, used_bench = _cell_verdict(matched, n, 0.5, major, pval, p_threshold)
            scored[cell] = {
                "n_events": n, "matched": matched, "missed": n - matched,
                "hit_count": "%d/%d" % (matched, n),
                "hit_rate": matched / float(n),
                "n_ties_excluded": len(ties),
                "tie_days": [e["day"] for e in ties],
                "benchmark_coin_flip": 0.5,
                "benchmark_majority_class": major,
                "majority_direction": "up" if ups >= n - ups else "down",
                "benchmark_used": used_bench,
                "p_one_sided_vs_benchmark": pval,
                "verdict": verdict,
                "matched_days": [e["day"] for e in live if e["match"]],
                "missed_days": [e["day"] for e in live if not e["match"]],
                "events": live,
                "level": _level_block(live),
            }

        tracks = [c for c in scored if scored[c]["verdict"] == "TRACKS"]
        nots = [c for c in scored if scored[c]["verdict"] == "NOT_TRACKING"]
        incs = [c for c in scored if scored[c]["verdict"] == "INCONCLUSIVE"]
        if not scored:
            verdict = ("REFUSED - no %s cell reached n=%d. %d cell(s) below the floor: %s"
                       % (forcing, min_cell_n, len(refused),
                          ", ".join("%s n=%d" % (c, refused[c]["n_events"])
                                    for c in sorted(refused)) or "none"))
        elif tracks and not nots and not incs:
            verdict = ("TRACKS on all %d qualifying cell(s): %s"
                       % (len(tracks), ", ".join(sorted(tracks))))
        elif not tracks:
            verdict = ("DOES NOT TRACK on any qualifying cell - not_tracking %s; inconclusive %s"
                       % (", ".join(sorted(nots)) or "none", ", ".join(sorted(incs)) or "none"))
        else:
            verdict = ("TRACKS ON %s; NOT ON %s; INCONCLUSIVE ON %s - a proxy that survives on a "
                       "SUBSET of cells is KEPT and used on those cells, never extended to the "
                       "rest" % (", ".join(sorted(tracks)),
                                 ", ".join(sorted(nots)) or "none",
                                 ", ".join(sorted(incs)) or "none"))

        res["forcings"][forcing] = {
            "provenance": prov,
            "verdict": verdict,
            "cells": scored,
            "refused_cells": refused,
            "excluded_events": excluded,
            "arithmetic_total": {
                "matched": sum(scored[c]["matched"] for c in scored),
                "n_events": sum(scored[c]["n_events"] for c in scored),
                "caveat": ("a COUNT of the named days in the qualifying cells above, NOT a "
                           "verdict - read the cells; a total can be carried by one cell while "
                           "another is wrong-signed")},
        }

    lanes = "; ".join("%s: %s" % (f.upper(), res["forcings"][f]["verdict"]) for f in FORCINGS)
    res["verdict"] = lanes + " -- " + NEVER_SUMMED
    return res


# --------------------------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------------------------
def print_report(res, show_events=True, level=True):
    print("=" * 100)
    print("GEFS FORCING PROXY VALIDATION - %s" % res["generated_utc"])
    print("QUESTION: %s" % res["question"])
    print("-" * 100)
    r = res["realized"]
    print("realized answer key : %s" % r["path"])
    print("                      %d rows, span %s .. %s" % (r["rows"], r["span"][0], r["span"][1]))
    print("proxy               : %d day(s)%s" % (res["proxy_days"],
          (", span %s .. %s" % tuple(res["proxy_span"])) if res.get("proxy_span") else ""))
    for d in res.get("proxy_dropped", [])[:10]:
        print("  DROPPED %s" % d)
    print("ALIGNMENT           : %s" % res["alignment"])
    print("METHOD              : %s" % res["method"])
    print("CELL FLOOR          : n >= %d, ties excluded and named" % res["min_cell_n"])
    print("=" * 100)

    for forcing in FORCINGS:
        blk = res["forcings"].get(forcing, {})
        print("")
        print("#" * 100)
        print("## %s -- realized column %s" % (forcing.upper(), REALIZED_COL[forcing]))
        prov = blk.get("provenance") or {}
        if prov:
            print("   proxy field %s read at %s ; %d day(s) carried it, %d joined to realized"
                  % (prov.get("field"), prov.get("statistic"), prov.get("days_with_field", 0),
                     prov.get("days_joined", 0)))
        print("#" * 100)
        for cell in sorted(blk.get("refused_cells", {})):
            c = blk["refused_cells"][cell]
            print("  CELL %s  %s  days: %s" % (cell, c["refusal"], ", ".join(c["days"])))
        for cell in sorted(blk.get("cells", {})):
            c = blk["cells"][cell]
            print("")
            print("  CELL %s   n=%d   MATCHED %s   verdict %s"
                  % (cell, c["n_events"], c["hit_count"], c["verdict"]))
            print("    benchmarks (A-1, both named): coin flip 0.500 | majority class %.3f (%s) "
                  "-> benchmark used %.3f ; one-sided exact binomial p=%.4f (threshold %.2f)"
                  % (c["benchmark_majority_class"], c["majority_direction"],
                     c["benchmark_used"], c["p_one_sided_vs_benchmark"], res["p_threshold"]))
            if c["n_ties_excluded"]:
                print("    ties excluded (a zero change calls nothing): %s"
                      % ", ".join(c["tie_days"]))
            if show_events:
                print("    %-12s %-12s %3s %14s %14s %14s %14s  %s"
                      % ("day", "prev", "gap", "proxy", "d_proxy", "realized", "d_realized", "dir"))
                for e in c["events"]:
                    print("    %-12s %-12s %3d %14.4f %+14.4f %14.1f %+14.1f  %s"
                          % (e["day"], e["prev"], e["gap_days"], e["proxy"], e["d_proxy"],
                             e["realized"], e["d_realized"], "MATCH" if e["match"] else "miss"))
            print("    matched days: %s" % (", ".join(c["matched_days"]) or "none"))
            print("    missed  days: %s" % (", ".join(c["missed_days"]) or "none"))
            lv = c.get("level") or {}
            if level and lv.get("available"):
                print("")
                print("    LEVEL, against TWO NAMED BENCHMARKS. calibration: %s" % lv["calibration"])
                per_event_report(
                    "%s %s level vs PERSISTENCE (tomorrow equals today)" % (forcing, cell),
                    lv["keys"], lv["actual"], lv["persistence"], lv["proxy_calibrated"],
                    units=" MWh",
                    explanation="the proxy is meteorology, not MWh; the level comparison rests on a "
                                "leave-one-out within-cell scale ratio and is NOT the direction "
                                "result above")
                per_event_report(
                    "%s %s level vs CLIMATOLOGY (leave-one-out within-month mean)" % (forcing, cell),
                    lv["keys"], lv["actual"], lv["climatology_loo"], lv["proxy_calibrated"],
                    units=" MWh")
                print("    proxy beat persistence on %d/%d days, climatology on %d/%d days"
                      % (lv["beat_persistence"], lv["n"], lv["beat_climatology"], lv["n"]))
            elif level:
                print("    LEVEL: not scored - %s" % lv.get("why", "no data"))
        ex = blk.get("excluded_events") or []
        if ex:
            print("")
            print("  EXCLUDED (declared, never filled): %d" % len(ex))
            for e in ex[:12]:
                print("    %s  %s" % (e["day"], e["reason"]))
            if len(ex) > 12:
                print("    ... %d more" % (len(ex) - 12))
        tot = blk.get("arithmetic_total")
        if tot and tot["n_events"]:
            print("")
            print("  ARITHMETIC TOTAL %d/%d -- %s"
                  % (tot["matched"], tot["n_events"], tot["caveat"]))
        print("")
        print("  %s VERDICT: %s" % (forcing.upper(), blk.get("verdict", "n/a")))

    print("")
    print("=" * 100)
    print("VERDICT: %s" % res["verdict"])
    print("=" * 100)
    return res


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------
def cmd_report(csv_path, proxy_path, min_cell_n=MIN_CELL_N, out=None, quiet_events=False):
    if not proxy_path or not os.path.exists(proxy_path):
        print("gefs_validate: the proxy series is NOT PRESENT at %s .\n"
              "  This harness will not invent it. Build it with:\n"
              "    python research/kalshi/gefs_ensemble.py series --start YYYYMMDD --end YYYYMMDD "
              "--members 1 --out %s\n"
              "  (validation needs many days and no spread, so the control member alone answers "
              "it - see the validation/production split in gefs_ensemble.forcing_series)"
              % (proxy_path, proxy_path or "<path>"))
        return 2
    with open(proxy_path, "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    try:
        res = validate(rows, csv_path, min_cell_n=min_cell_n)
    except RealizedMissing as e:
        print(str(e))
        return 2
    except SyntheticDataRefused:
        return 3
    print_report(res, show_events=not quiet_events)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
        print("written -> %s" % out)
    return 0


# --------------------------------------------------------------------------------------------
# SELFTEST - the ONLY place synthetic data is legal, and every row it makes is TAGGED
# --------------------------------------------------------------------------------------------
def _synthetic_days(n, start="2026-04-01"):
    d0 = dt.datetime.strptime(start, "%Y-%m-%d").date()
    return [(d0 + dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _synthetic_realized_csv(path, days, seed=11):
    """SYNTHETIC. An autocorrelated wind series and a smoother solar series, both clearly fake."""
    import random
    rng = random.Random(seed)
    w, s, rows = 700000.0, 900000.0, []
    for d in days:
        w = max(50000.0, 0.55 * w + 0.45 * 700000.0 + rng.gauss(0, 120000))
        s = max(50000.0, 0.70 * s + 0.30 * 900000.0 + rng.gauss(0, 60000))
        rows.append((d, w, s))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["date", "wind_mwh", "solar_mwh"])
        for d, a, b in rows:
            wr.writerow([d, "%.1f" % a, "%.1f" % b])
    return {d: {"wind": a, "solar": b} for d, a, b in rows}


def _synthetic_proxy(days, realized, mode, seed=23):
    """SYNTHETIC proxy records, TAGGED so the report path refuses them.

    mode 'tracking' - a scaled, noisy image of realized (the positive control)
    mode 'noise'    - pure noise, independent of realized (must be reported NOT tracking)
    mode 'shift2'   - the tracking proxy misaligned by two days (the recorded alignment trap)
    mode 'constant' - a flat line (every change is a tie)
    """
    import random
    rng = random.Random(seed)
    out = {}
    idx = {d: i for i, d in enumerate(days)}
    for d in days:
        if mode == "noise":
            wv, sv = rng.uniform(0.05, 0.55), rng.uniform(120.0, 320.0)
        elif mode == "constant":
            wv, sv = 0.30, 200.0
        else:
            src = d
            if mode == "shift2":
                j = idx[d] - 2
                if j < 0:
                    continue
                src = days[j]
            wv = realized[src]["wind"] / 2.2e6 + rng.gauss(0, 0.010)
            sv = realized[src]["solar"] / 4.0e3 + rng.gauss(0, 3.0)
        out[d] = {"day": d, "synthetic": True,
                  "wind_cf_proxy": {"n": 1, "p10": wv, "p50": wv, "p90": wv,
                                    "min": wv, "max": wv},
                  "solar_irradiance_proxy": {"n": 1, "p10": sv, "p50": sv, "p90": sv,
                                             "min": sv, "max": sv}}
    return out


def selftest():
    import shutil
    import tempfile
    fails = []

    def check(name, cond, detail=""):
        print("  %-4s %s%s" % ("PASS" if cond else "FAIL", name, ("  -- " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="gefs_validate_selftest_")
    csv_path = os.path.join(tmp, "SELFTEST_SYNTHETIC_realized_forcings_us48.csv")
    try:
        print("=" * 100)
        print("gefs_validate SELFTEST - ALL DATA BELOW IS SYNTHETIC AND TAGGED; the report path")
        print("refuses tagged rows, so nothing here can leak into a real validation.")
        print("=" * 100)
        days = _synthetic_days(75)
        realized = _synthetic_realized_csv(csv_path, days)

        # ---------------------------------------------------------------- 1 POSITIVE CONTROL
        print("")
        print("[1] POSITIVE CONTROL - a proxy that IS a noisy image of realized must be reported")
        print("    as tracking. Without this the 'not tracking' branch below proves nothing (NC-3:")
        print("    both branches must execute).")
        good = validate(_synthetic_proxy(days, realized, "tracking"), csv_path,
                        allow_synthetic=True)
        for f in FORCINGS:
            v = good["forcings"][f]["verdict"]
            t = good["forcings"][f]["arithmetic_total"]
            print("    GUARD OUTPUT %-5s %s" % (f, v))
            print("                 %-5s count %d/%d over %d scored cell(s)"
                  % (f, t["matched"], t["n_events"], len(good["forcings"][f]["cells"])))
            check("positive control: %s reported as tracking" % f, "TRACKS" in v, v[:70])

        # ---------------------------------------------------------------- 2 NEGATIVE: PURE NOISE
        print("")
        print("[2] NEGATIVE - PURE NOISE proxy. Must be reported as NOT tracking, in both lanes.")
        noise = validate(_synthetic_proxy(days, realized, "noise"), csv_path, allow_synthetic=True)
        for f in FORCINGS:
            v = noise["forcings"][f]["verdict"]
            t = noise["forcings"][f]["arithmetic_total"]
            print("    GUARD OUTPUT %-5s %s" % (f, v))
            print("                 %-5s count %d/%d ; per-cell: %s"
                  % (f, t["matched"], t["n_events"],
                     ", ".join("%s %s %s" % (c, noise["forcings"][f]["cells"][c]["hit_count"],
                                             noise["forcings"][f]["cells"][c]["verdict"])
                               for c in sorted(noise["forcings"][f]["cells"]))))
            check("noise: %s NOT reported as tracking" % f, "TRACKS ON" not in v and
                  not v.startswith("TRACKS"), v[:70])

        # ---------------------------------------------------------------- 3 NEGATIVE: MISALIGNED
        print("")
        print("[3] NEGATIVE - THE RECORDED ALIGNMENT TRAP. The SAME good proxy, shifted two days,")
        print("    must not come back clean. A two-day offset on an autocorrelated series scores")
        print("    BELOW the coin flip, which is how the real one was caught.")
        sh = validate(_synthetic_proxy(days, realized, "shift2"), csv_path, allow_synthetic=True)
        for f in FORCINGS:
            v = sh["forcings"][f]["verdict"]
            t = sh["forcings"][f]["arithmetic_total"]
            print("    GUARD OUTPUT %-5s count %d/%d -- %s" % (f, t["matched"], t["n_events"], v))
            check("misaligned: %s not clean on all cells" % f,
                  not v.startswith("TRACKS on all"), v[:70])

        # ---------------------------------------------------------------- 4 EMPTY SAMPLE
        print("")
        print("[4] REFUSAL - EMPTY proxy. Must refuse, not report.")
        empty = validate({}, csv_path, allow_synthetic=True)
        print("    GUARD OUTPUT %s" % empty["verdict"])
        check("empty sample refuses", empty["verdict"].startswith("REFUSED"))
        check("empty sample scores no cell",
              all(not empty["forcings"][f]["cells"] for f in FORCINGS))

        # ---------------------------------------------------------------- 5 SHORT SAMPLE
        print("")
        print("[5] REFUSAL - SHORT sample (4 usable days -> 3 events, floor is %d)." % MIN_CELL_N)
        short_days = days[:4]
        short = validate(_synthetic_proxy(short_days, realized, "tracking"), csv_path,
                         allow_synthetic=True)
        for f in FORCINGS:
            blk = short["forcings"][f]
            for cell in sorted(blk["refused_cells"]):
                print("    GUARD OUTPUT %-5s CELL %s %s"
                      % (f, cell, blk["refused_cells"][cell]["refusal"]))
            print("    GUARD OUTPUT %-5s %s" % (f, blk["verdict"]))
            check("short sample: %s refuses rather than reports" % f,
                  not blk["cells"] and blk["verdict"].startswith("REFUSED"))

        # ---------------------------------------------------------------- 6 MISSING ANSWER KEY
        print("")
        print("[6] REFUSAL - MISSING realized CSV. Must name the file, not invent data.")
        missing = os.path.join(tmp, "store", "realized_forcings_us48.csv")
        try:
            validate(_synthetic_proxy(days, realized, "tracking"), missing, allow_synthetic=True)
            check("missing realized csv raises", False, "no exception raised")
        except RealizedMissing as e:
            print("    GUARD OUTPUT %s" % str(e).replace("\n", "\n    "))
            check("missing realized csv raises RealizedMissing", True)
            check("the message names the file", "realized_forcings_us48.csv" in str(e))
            check("the message names the builder", "build_realized_forcings.py" in str(e))

        # ---------------------------------------------------------------- 7 SYNTHETIC GUARD
        print("")
        print("[7] GUARD - tagged synthetic rows must be REFUSED on the report path (the default).")
        try:
            validate(_synthetic_proxy(days, realized, "tracking"), csv_path)
            check("synthetic guard fires on the report path", False, "no exception raised")
        except SyntheticDataRefused as e:
            check("synthetic guard fires on the report path", True, str(e)[:60])

        # ---------------------------------------------------------------- 8 NEVER SUMMED
        print("")
        print("[8] STRUCTURE - wind and solar are separate lanes; no combined renewables term.")
        keys = set(good["forcings"].keys())
        print("    GUARD OUTPUT forcing lanes present: %s" % ", ".join(sorted(keys)))
        check("exactly two lanes, wind and solar", keys == {"wind", "solar"})
        blob = json.dumps({f: good["forcings"][f]["cells"] for f in FORCINGS})
        check("no combined renewables field anywhere in the cell records",
              "renewab" not in blob.lower())
        check("the two lanes hold different numbers",
              good["forcings"]["wind"]["arithmetic_total"] is not
              good["forcings"]["solar"]["arithmetic_total"])

        # ---------------------------------------------------------------- 9 TIES
        print("")
        print("[9] REFUSAL - a CONSTANT proxy calls no direction. Every event is a tie, so the")
        print("    cell must be refused rather than scored 0/0 or, worse, 100 percent.")
        flat = validate(_synthetic_proxy(days, realized, "constant"), csv_path,
                        allow_synthetic=True)
        for f in FORCINGS:
            blk = flat["forcings"][f]
            for cell in sorted(blk["refused_cells"]):
                rc = blk["refused_cells"][cell]
                print("    GUARD OUTPUT %-5s CELL %s n=%d ties_excluded=%d  %s"
                      % (f, cell, rc["n_events"], rc["n_ties_excluded"], rc["refusal"]))
            check("constant proxy: %s scores no cell" % f, not blk["cells"], blk["verdict"][:60])

        # ------------------------------------------------------- 10 MIXED FIELD SPELLING / GAPS
        print("")
        print("[10] GUARD - a series spelled wind_cf_proxy on some days and wind_power_proxy on")
        print("     others must RAISE. The two are different quantities (raw cube vs turbine power")
        print("     curve); silently concatenating them is the wrong-but-well-formed class. And a")
        print("     day missing the solar field must be DECLARED as excluded, never interpolated.")
        mixed = _synthetic_proxy(days, realized, "tracking")
        for i, d in enumerate(sorted(mixed)):
            if i % 2:
                mixed[d]["wind_power_proxy"] = mixed[d].pop("wind_cf_proxy")
            if i in (3, 4):
                mixed[d].pop("solar_irradiance_proxy")
        try:
            validate(mixed, csv_path, allow_synthetic=True)
            check("mixed field spelling raises", False, "no exception raised")
        except ValueError as e:
            print("    GUARD OUTPUT %s" % e)
            check("mixed field spelling raises", "refusing to mix two fields" in str(e))
        gapped = _synthetic_proxy(days, realized, "tracking")
        for d in sorted(gapped)[3:5]:
            gapped[d].pop("solar_irradiance_proxy")
        gp = validate(gapped, csv_path, allow_synthetic=True)
        gex = [e for e in gp["forcings"]["solar"]["excluded_events"] if "no solar" in e["reason"]]
        for e in gex:
            print("    GUARD OUTPUT excluded %s -- %s" % (e["day"], e["reason"]))
        check("a missing solar field is declared and the day named", len(gex) == 2)
        check("the missing days do not silently enter the wind lane",
              not [e for e in gp["forcings"]["wind"]["excluded_events"]
                   if "no wind" in e["reason"]])

        # --------------------------------------------------------------- 11 PER-EVENT PRINT PATH
        print("")
        print("[11] PRINT PATH - the day-by-day table and both level benchmarks must render.")
        print("     (printing one wind cell of the positive control, abbreviated by cell)")
        one = {k: v for k, v in good.items()}
        one["forcings"] = {"wind": dict(good["forcings"]["wind"]), "solar": {"verdict": "(omitted "
                           "from this print check only - solar is scored in full above)",
                           "cells": {}, "refused_cells": {}, "excluded_events": []}}
        first = sorted(one["forcings"]["wind"]["cells"])[:1]
        one["forcings"]["wind"]["cells"] = {c: one["forcings"]["wind"]["cells"][c] for c in first}
        try:
            print_report(one)
            check("print_report renders", True)
        except Exception as e:  # noqa: BLE001 - a print failure is a real failure
            check("print_report renders", False, "%s: %s" % (type(e).__name__, e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("")
    print("=" * 100)
    print("SELFTEST %s%s" % ("PASS" if not fails else "FAIL", "" if not fails else
                             " -- " + ", ".join(fails)))
    print("=" * 100)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description="validate the GEFS forcing proxies against realized "
                                             "EIA-930 US48 output",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--csv", default=REALIZED_CSV, help="realized answer key (date,wind_mwh,solar_mwh)")
    r.add_argument("--proxy", default="", help="JSON written by gefs_ensemble.py series --out")
    r.add_argument("--min-cell-n", type=int, default=MIN_CELL_N)
    r.add_argument("--out", default="", help="write the full result dict here")
    r.add_argument("--quiet-events", action="store_true",
                   help="suppress the per-day table (the counts and named days still print)")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    return cmd_report(a.csv, a.proxy, min_cell_n=a.min_cell_n, out=a.out or None,
                      quiet_events=a.quiet_events)


if __name__ == "__main__":
    sys.exit(main())
