"""coal_commitment.py - measure the COAL COMMITMENT CYCLE from EIA-930 (S113, registry item A-31).

WHY. Greg, S113, from operating experience: a cold coal boiler takes about 24 hours to heat, the ramp
costs only amortise over a week or two, and firing one up surfaces tube leaks and "all sorts of
things" - so you start early enough to shake the unit down. Then: "if the weather doesn't come in
like you thought but you scheduled those plants you just roll with it." And once up, "those old units
don't like to swing with the load... they are going to run at 100% until they get ramped down."

That is a physical account with a testable consequence, and it is the reason this file exists:

    A DECISION THAT IS NOT REVISED IS A DECISION WE CAN MODEL.

If operators re-optimised daily against the forecast, coal would be a behavioural series and we would
have to predict their revisions. If instead they commit on a week-ahead forecast, run the window and
roll with it, then OBSERVING A START TELLS YOU WHAT COAL WILL DO FOR THE NEXT ONE TO TWO WEEKS,
largely independent of what the weather does next. That is a DATED FORWARD SUPPLY QUANTITY - the one
information class the horizon research says survives past the 5-7 day boundary - derived from a feed
we already pull.

THIS FILE MEASURES WHETHER THAT IS TRUE. It does not serve a feature and does not propose a
threshold. Per D37 the story is a guess and the data is the finding, so the order is: characterise
the episodes, then check the model's predictions against them, and let it fail if it fails.

THE FOUR PREDICTIONS, each falsifiable:
  P1 DURATION   episodes run about 1-2 weeks, not 1-3 days. A fleet that cycled daily would refute
                the ramp-cost account outright.
  P2 ASYMMETRY  the rise is faster than the decay. Committed units come up to serve an event and are
                ramped down deliberately afterwards.
  P3 MILD TAIL  coal persists after the weather breaks - at the end of an episode, coal is a HIGHER
                fraction of its own peak than degree-days are of theirs. This is the sharpest one,
                because a purely weather-following fleet cannot produce it.
  P4 NON-MONOTONIC RISES  some episodes dip mid-ramp while demand is still climbing, which is the
                signature of a failed or tripped start (tube leaks are the largest single cause of
                coal forced outages). Not proof - a daily total cannot separate a trip from a
                dispatch decision, and the hourly series (A-28) would - but the rate is measurable.

METHOD, and it is deliberately parameter-light because D23/D28 say a bar sited away from the centre
of its own distribution will not transfer. Episodes are found from the series' OWN distribution: a
rise above the rolling median that persists, ending when it returns. No absolute MWh threshold, no
tuned lookback, and the sensitivity to the one free choice is printed rather than hidden.

Usage:
  python research/kalshi/coal_commitment.py            # measure, per BA, per episode
  python research/kalshi/coal_commitment.py --selftest # synthetic episodes with known answers
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import glob
import datetime as _dt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STORE = os.path.join(REPO, "data", "grid_stack", "grid_stack.json.gz")
BAS = ["US48", "PJM", "MISO", "SOCO", "SWPP", "ERCO"]
BASE_WIN = 45          # rolling window for the reference level, in days
MIN_EPISODE = 3        # an episode must last at least this many days to be one


def _load_days():
    if not os.path.exists(STORE):
        return None
    with gzip.open(STORE) as fh:
        return json.load(fh)["days"]


def _series(days, ba, fuel="COL"):
    out = []
    for d in sorted(days):
        b = days[d].get(ba)
        if not b:
            continue
        v = b.get("gen_mwh", {}).get(fuel)
        if v is not None:
            out.append((d, float(v)))
    return out


def _weather():
    """gas-weighted HDD per day, for the mild-tail test. Absent -> that test reports UNAVAILABLE."""
    wx = {}
    for p in glob.glob(os.path.join(REPO, "data", "nws_temp", "*.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        s = d.get("days") or d
        if isinstance(s, dict):
            for k, v in s.items():
                if isinstance(v, dict) and "gw_hdd" in v:
                    wx[k] = v["gw_hdd"]
    return wx


def _median(v):
    s = sorted(v)
    return s[len(s) // 2] if s else 0.0


def _seasonal_baseline(series, half_win=10):
    """Reference level per day = median of the SAME CALENDAR WINDOW IN OTHER YEARS.

    THE FIRST VERSION OF THIS USED A 45-DAY TRAILING MEDIAN AND IT WAS WRONG - recorded rather than
    quietly replaced, because the failure is instructive. Coal has a large seasonal cycle (cooling
    load lifts it every summer), and a trailing median tracks the level slowly enough that a whole
    summer sits above it. The finder returned "episodes" of 1025, 175, 137, 111 and 97 days, which
    are seasons, not commitments, and they swamped the duration and asymmetry tests.

    A seasonal baseline removes exactly that: an episode is now output above what THIS TIME OF YEAR
    normally looks like, which is the quantity the commitment story is actually about. Other years
    only - the current year is excluded so an episode cannot raise its own baseline.
    """
    by_doy = {}
    for d, v in series:
        doy = _dt.date.fromisoformat(d).timetuple().tm_yday
        by_doy.setdefault(doy, []).append((d[:4], v))
    ref = {}
    for d, _ in series:
        dd = _dt.date.fromisoformat(d)
        yr, doy = d[:4], dd.timetuple().tm_yday
        pool = []
        for off in range(-half_win, half_win + 1):
            for y, v in by_doy.get(((doy - 1 + off) % 365) + 1, []):
                if y != yr:
                    pool.append(v)
        ref[d] = _median(pool) if pool else None
    return ref


def episodes(series, base_win=BASE_WIN, min_len=MIN_EPISODE, seasonal=True):
    """Coal ramp episodes, found from the series' OWN distribution.

    An episode opens when output rises above its reference level and closes when it falls back. No
    absolute MWh bar - the reference is the fleet's own normal, so the same code works on a 3M MWh
    US48 series and a 200k MWh BA without retuning. `seasonal=False` restores the trailing-median
    behaviour and is kept ONLY so the selftest can exercise the finder on synthetic series that have
    no seasonal structure at all.
    """
    sref = _seasonal_baseline(series) if seasonal else None
    eps, i, n = [], base_win, len(series)
    while i < n:
        if sref is not None:
            ref = sref.get(series[i][0])
            if ref is None:
                i += 1
                continue
        else:
            ref = _median([v for _, v in series[i - base_win:i]])
        if series[i][1] <= ref:
            i += 1
            continue
        start = i
        j = i
        while j < n and series[j][1] > ref:
            j += 1
        if j - start >= min_len:
            seg = series[start:j]
            peak_i = max(range(len(seg)), key=lambda k: seg[k][1])
            eps.append({
                "start": seg[0][0], "end": seg[-1][0], "days": len(seg),
                "baseline": ref, "peak": seg[peak_i][1], "peak_date": seg[peak_i][0],
                "rise_days": peak_i + 1, "fall_days": len(seg) - peak_i - 1,
                "lift": seg[peak_i][1] - ref,
                "series": seg,
            })
        i = max(j, start + 1)
    return eps


def report(days=None, wx=None):
    days = days if days is not None else _load_days()
    if not days:
        print("grid_stack store absent - run restore_substrate.py first")
        return 1
    wx = wx if wx is not None else _weather()
    print("=" * 100)
    print("COAL COMMITMENT CYCLE (A-31) - is the commitment real, and is it un-revised?")
    print("=" * 100)
    print("Episodes are found from each series' OWN rolling median, never an absolute MWh bar (D28).")
    print("Every episode is listed individually; no episode-level average is reported as a verdict (D37).")
    for ba in BAS:
        s = _series(days, ba)
        if len(s) < BASE_WIN + 30:
            continue
        eps = episodes(s)
        if not eps:
            print(f"\n--- {ba}: no episodes found")
            continue
        print(f"\n--- {ba}   {len(eps)} episodes over {s[0][0]}..{s[-1][0]}")
        print(f"    {'start':<12}{'end':<12}{'days':>5}{'rise':>6}{'fall':>6}{'lift MWh':>12}"
              f"{'peak/base':>11}   mid-ramp dips")
        p1 = p2 = p4 = 0
        for e in eps:
            rises = [e["series"][k + 1][1] - e["series"][k][1] for k in range(e["rise_days"] - 1)]
            dips = sum(1 for r in rises if r < 0)
            p1 += 1 if 5 <= e["days"] <= 21 else 0
            p2 += 1 if e["fall_days"] >= e["rise_days"] else 0
            p4 += 1 if dips else 0
            print(f"    {e['start']:<12}{e['end']:<12}{e['days']:>5}{e['rise_days']:>6}"
                  f"{e['fall_days']:>6}{e['lift']:>12,.0f}{e['peak']/e['baseline']:>11.2f}"
                  f"   {dips if dips else '-':>3}")
        print(f"    P1 duration 5-21 days: {p1}/{len(eps)}   "
              f"P2 decay >= rise: {p2}/{len(eps)}   "
              f"P4 episodes with a mid-ramp dip: {p4}/{len(eps)}")

        # P3 - the mild tail. Coal should still be high when the weather has already let go.
        if ba == "US48" and wx:
            print(f"    P3 MILD TAIL - at each episode's END, coal as a share of ITS peak vs gw_HDD as a")
            print(f"       share of ITS peak over the same window. Coal HIGHER = it did not follow the")
            print(f"       weather down = committed. This is the prediction a weather-following fleet")
            print(f"       cannot produce.")
            held = tested = 0
            for e in eps:
                dts = [d for d, _ in e["series"]]
                hs = [wx[d] for d in dts if d in wx]
                if len(hs) < len(dts) * 0.8 or not hs:
                    continue
                hpk = max(hs)
                if hpk <= 0:
                    continue
                coal_end = e["series"][-1][1] / e["peak"]
                hdd_end = hs[-1] / hpk
                tested += 1
                ok = coal_end > hdd_end
                held += 1 if ok else 0
                print(f"       {e['start']}..{e['end']}  coal_end {100*coal_end:>5.0f}% of peak   "
                      f"HDD_end {100*hdd_end:>5.0f}% of peak   {'HELD' if ok else 'no'}")
            print(f"       P3 held in {held}/{tested} episodes with weather coverage")
        elif ba == "US48":
            print("    P3 MILD TAIL: UNAVAILABLE - no weather store restored (declared, not skipped)")
    print()
    print("READ THIS BEFORE USING ANY OF IT: these are DESCRIPTIONS of past episodes, not a feature and")
    print("not a threshold. The commitment model earns a forward role only if P1-P3 hold, and the")
    print("forward claim - that observing a start tells you the next 1-2 weeks - is a SEPARATE test")
    print("that needs the start detected in real time, not in hindsight.")
    return 0


def selftest():
    """Synthetic series with known answers. Tests the FINDER, not the market."""
    ok = True

    def chk(label, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))

    d0 = _dt.date(2020, 1, 1)
    def mk(vals):
        return [((d0 + _dt.timedelta(days=i)).isoformat(), float(v)) for i, v in enumerate(vals)]

    # seasonal=False throughout: synthetic series have ONE year, so a seasonal baseline has no other
    # year to draw on and every day returns None. The selftest exercises the FINDER, not the baseline.
    def eps(v):
        return episodes(v, seasonal=False)

    flat = mk([1000] * 120)
    chk("a flat series has no episodes", eps(flat) == [], f"{len(eps(flat))} found")

    # one clean episode: 60 flat, rise 5, plateau 5, decay 8, back to flat
    v = [1000] * 60 + [1200, 1500, 1800, 2000, 2100] + [2100] * 5 + \
        [1900, 1750, 1600, 1450, 1300, 1150, 1050, 1000] + [1000] * 40
    e = eps(mk(v))
    chk("one clean episode is found", len(e) == 1, f"{len(e)} found")
    if e:
        chk("peak located correctly", abs(e[0]["peak"] - 2100) < 1, f"peak={e[0]['peak']}")
        chk("rise is shorter than fall (P2 shape detected)",
            e[0]["fall_days"] > e[0]["rise_days"], f"rise={e[0]['rise_days']} fall={e[0]['fall_days']}")
        chk("lift measured against the baseline, not zero",
            900 < e[0]["lift"] < 1200, f"lift={e[0]['lift']:.0f}")

    # a mid-ramp dip must be COUNTED, not smoothed away - this is the P4 signature
    v2 = [1000] * 60 + [1300, 1600, 1400, 1900, 2200] + [2200] * 4 + [1800, 1500, 1200, 1000] + [1000] * 40
    e2 = eps(mk(v2))
    if e2:
        rises = [e2[0]["series"][k + 1][1] - e2[0]["series"][k][1] for k in range(e2[0]["rise_days"] - 1)]
        chk("a mid-ramp dip is detected", sum(1 for r in rises if r < 0) == 1,
            f"{sum(1 for r in rises if r < 0)} dips")

    # scale invariance: the finder must not carry a hidden absolute bar
    small = [(d, x / 20.0) for d, x in mk(v)]
    chk("scale-invariant: same episode found at 1/20 the level",
        len(eps(small)) == len(e), f"{len(eps(small))} vs {len(e)}")

    # a 2-day blip must NOT be an episode - that is the whole point of the duration test
    v3 = [1000] * 60 + [1500, 1500] + [1000] * 60
    chk("a 2-day blip is not an episode", eps(mk(v3)) == [], f"{len(eps(mk(v3)))} found")

    # AND the seasonal path must be exercised. NOTE - my first assertion here was WRONG and is
    # recorded rather than quietly replaced: I expected two identical years to cancel to ZERO
    # episodes. They do not, and should not - the baseline is a +/-10 day MEDIAN, so it smooths
    # a sharp peak and the peak still stands above it. The correct property is SYMMETRY: two
    # identical years must yield the same episode count in each.
    yr = [1000]*60 + [1400,1800,2000] + [2000]*4 + [1600,1300,1100] + [1000]*295
    two = mk((yr * 2)[:730])
    se = episodes(two)
    y1 = sum(1 for e in se if e['start'][:4] == two[0][0][:4])
    y2 = len(se) - y1
    chk("seasonal path runs and is symmetric across two identical years",
        len(se) > 0 and y1 == y2, f"{len(se)} episodes, {y1} in year 1 / {y2} in year 2")
    chk("seasonal baseline is non-null once a second year exists",
        _seasonal_baseline(two)[two[400][0]] is not None)

    print()
    print(f"  SELFTEST {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else report())
