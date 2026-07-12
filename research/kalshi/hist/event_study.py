#!/usr/bin/env python3
"""Event-weight study: measure how much recurring scheduled releases move the
underlying market, vs a placebo baseline. Uses FRED daily close-to-close data.

Weekly energy reports have a FIXED release weekday, so we use a day-of-week
release proxy: the release IS on that weekday (with rare holiday shifts), so the
excess move on that weekday vs other weekdays measures the event's weight.
Macro events use explicit historical release-date lists.
"""
import csv, json, math, datetime as dt
from collections import defaultdict

DATA = "/home/user/Markets/data/kalshi_hist"

def load_fred(fid):
    rows = []
    with open(f"{DATA}/fred_{fid}.csv") as f:
        r = csv.reader(f); next(r)
        for d, v in r:
            if v in (".", "", "NaN"): continue
            try: rows.append((dt.date.fromisoformat(d), float(v)))
            except ValueError: continue
    rows.sort()
    return rows

def log_returns(rows):
    """List of (date, weekday, r1, r2, r3) where r1=close-to-close log ret that day,
    r2 = 2-trading-day fwd (this close to +1), r3 = this close to +2 (persistence)."""
    out = []
    for i in range(1, len(rows)):
        d, v = rows[i]; dp, vp = rows[i-1]
        if vp <= 0 or v <= 0: continue
        r1 = math.log(v/vp)
        r_fwd1 = math.log(rows[i+1][1]/v) if i+1 < len(rows) and rows[i+1][1] > 0 else None
        r_fwd2 = math.log(rows[i+2][1]/v) if i+2 < len(rows) and rows[i+2][1] > 0 else None
        out.append((d, d.weekday(), r1, r_fwd1, r_fwd2))
    return out

def stats(xs):
    n = len(xs)
    if n == 0: return dict(n=0)
    m = sum(xs)/n
    var = sum((x-m)**2 for x in xs)/(n-1) if n > 1 else 0.0
    sd = math.sqrt(var)
    absx = sorted(abs(x) for x in xs)
    def pct(p):
        if not absx: return None
        k = min(len(absx)-1, int(p*len(absx)))
        return absx[k]
    return dict(n=n, mean=m, sd=sd, mean_abs=sum(abs(x) for x in xs)/n,
                p50_abs=pct(.50), p90_abs=pct(.90), p95_abs=pct(.95))

def cohens_d_absmove(event_abs, placebo_abs):
    """Effect size on |move|: (mean_ev - mean_pl)/pooled_sd, plus welch z."""
    ne, npl = len(event_abs), len(placebo_abs)
    if ne < 2 or npl < 2: return None
    me, mpl = sum(event_abs)/ne, sum(placebo_abs)/npl
    ve = sum((x-me)**2 for x in event_abs)/(ne-1)
    vpl = sum((x-mpl)**2 for x in placebo_abs)/(npl-1)
    pooled = math.sqrt(((ne-1)*ve+(npl-1)*vpl)/(ne+npl-2))
    d = (me-mpl)/pooled if pooled > 0 else 0.0
    se = math.sqrt(ve/ne + vpl/npl)
    z = (me-mpl)/se if se > 0 else 0.0
    return dict(mean_abs_event=me, mean_abs_placebo=mpl,
                ratio=me/mpl if mpl > 0 else None, cohens_d=d, welch_z=z)

WD = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def dow_event_study(series_id, event_wd, label, contract):
    rows = load_fred(series_id)
    lr = log_returns(rows)
    # same-day move grouped by weekday
    by_wd = defaultdict(list)
    fwd2_by_wd = defaultdict(list)
    for d, wd, r1, rf1, rf2 in lr:
        by_wd[wd].append(r1)
        if rf2 is not None: fwd2_by_wd[wd].append(rf2)
    event_abs = [abs(x) for x in by_wd[event_wd]]
    placebo_abs = [abs(x) for x in (v for w in by_wd if w != event_wd for v in by_wd[w])]
    eff = cohens_d_absmove(event_abs, placebo_abs)
    # persistence: does the day-of + next2 keep moving same direction? measure mean_abs of fwd2
    res = dict(
        event_type=label, kalshi_contract=contract, underlying=series_id,
        proxy="day-of-week release proxy (release weekday=%s)" % WD[event_wd],
        date_range=[str(rows[0][0]), str(rows[-1][0])],
        event=stats(by_wd[event_wd]),
        placebo_other_weekdays=stats([v for w in by_wd if w != event_wd for v in by_wd[w]]),
        effect_vs_placebo=eff,
        persistence_fwd2_mean_abs=stats(fwd2_by_wd[event_wd]).get("mean_abs"),
        dow_mean_abs={WD[w]: round(stats(by_wd[w])["mean_abs"],5) for w in range(5)},
    )
    return res

if __name__ == "__main__":
    results = {}
    # ENERGY (weekly, fixed weekday)
    # EIA Weekly Petroleum Status Report: Wed ~10:30 ET -> WTI, Brent, (RBOB via proxy)
    results["EIA_petroleum_status_WTI"] = dow_event_study(
        "DCOILWTICO", 2, "EIA Weekly Petroleum Status Report (crude inventories)", "KXWTI")
    results["EIA_petroleum_status_Brent"] = dow_event_study(
        "DCOILBRENTEU", 2, "EIA Weekly Petroleum Status Report (spillover to Brent)", "KXBRENTD")
    # EIA Weekly Natural Gas Storage Report: Thu ~10:30 ET -> Henry Hub
    results["EIA_natgas_storage"] = dow_event_study(
        "DHHNGSP", 3, "EIA Weekly Natural Gas Storage Report", "KXNATGASD")
    # propane weekly (in petroleum report) as breadth
    results["EIA_propane_weekly"] = dow_event_study(
        "DPROPANEMBTX", 2, "EIA Weekly propane stocks (petroleum report)", "(energy breadth)")
    print(json.dumps(results, indent=2, default=str))
    with open("/home/user/Markets/research/kalshi/hist/energy_dow_results.json","w") as f:
        json.dump(results, f, indent=2, default=str)
