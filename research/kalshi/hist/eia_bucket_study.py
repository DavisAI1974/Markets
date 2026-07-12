#!/usr/bin/env python3
"""CONDITIONAL per-bucket event study (founder methodology correction).
NEVER pool |move|. Bucket every historical EIA release by signed SURPRISE x signed
REACTION and report per-bucket SIGNED stats, hit-rate, distinctiveness.

SURPRISE PROXY (honest): actual weekly storage/stock CHANGE minus the 5-YEAR-AVERAGE
change for the SAME ISO calendar week (seasonal expectation). This is a PROXY for
street consensus -- it captures the SEASONAL surprise, not the exact desk number.
Real consensus-conditioned version comes forward via ForexFactory polling.

Convention (both natgas & crude): storage BUILD bigger than seasonal => more supply
=> BEARISH => expect price DOWN. So define bull = -surprise (positive bull = tighter
than expected = bullish). Directional edge exists iff reaction aligns with bull sign.
REACTION = signed release-hour futures move (Yahoo 60m, ~730d) [primary, clean window]
           + signed release-day close-to-close (Yahoo 1d, ~10y) [deeper N robustness].
"""
import csv, json, math, datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
DATA = "/home/user/Markets/data/kalshi_hist"

def load_eia(fn, scale=1.0):
    d = json.load(open(f"{DATA}/{fn}"))
    rows = []
    for r in d["response"]["data"]:
        try: rows.append((dt.date.fromisoformat(r["period"]), float(r["value"])*scale))
        except: pass
    rows.sort()
    return rows

def weekly_changes(levels):
    """[(period_date, change)] weekly net change of the level series."""
    out = []
    for i in range(1, len(levels)):
        d, v = levels[i]; dp, vp = levels[i-1]
        # only if ~7 days apart (skip gaps)
        if 5 <= (d-dp).days <= 10:
            out.append((d, v-vp))
    return out

def seasonal_surprise(changes, yrs=5):
    """surprise = change - mean(change over same ISO week, prior `yrs` years)."""
    by_week = defaultdict(list)  # (isoweek) -> list of (year, change)
    for d, ch in changes:
        by_week[d.isocalendar()[1]].append((d.year, ch))
    out = []
    for d, ch in changes:
        wk = d.isocalendar()[1]
        prior = [c for (yr, c) in by_week[wk] if d.year-yrs <= yr < d.year]
        if len(prior) >= 3:  # need a few years to form a seasonal expectation
            exp = sum(prior)/len(prior)
            out.append((d, ch, exp, ch-exp))  # date, actual, seasonal_exp, surprise
    return out

def next_weekday_after(d, wd):
    """first date strictly after d with weekday()==wd."""
    n = d + dt.timedelta(days=1)
    while n.weekday() != wd: n += dt.timedelta(days=1)
    return n

# ---- reaction maps ----
def load_60m(fn):
    bars = []
    for ts, c in list(csv.reader(open(f"{DATA}/{fn}")))[1:]:
        if c in ("", "."): continue
        t = int(float(ts)); bars.append((t, dt.datetime.fromtimestamp(t, ET), float(c)))
    bars.sort(); return bars

def release_hour_map(fn, hour=10):
    """date -> signed log-return(%) of the ET `hour` bar (contains 10:30 release)."""
    bars = load_60m(fn); m = {}
    for i in range(1, len(bars)):
        t, et, c = bars[i]; tp, _, cp = bars[i-1]
        if cp <= 0 or c <= 0 or t-tp > 2*3600+300: continue
        if et.hour == hour:
            m[et.date()] = math.log(c/cp)*100.0
    return m

def load_1d(fn):
    rows = []
    for d, c in list(csv.reader(open(f"{DATA}/{fn}")))[1:]:  # 1d files store "YYYY-MM-DD",close
        if c in ("", "."): continue
        try: rows.append((dt.date.fromisoformat(d), float(c)))
        except ValueError: continue
    rows.sort(); return rows

def release_day_map(fn):
    """date -> signed close-to-close(%) that day."""
    rows = load_1d(fn); m = {}
    for i in range(1, len(rows)):
        d, v = rows[i]; dp, vp = rows[i-1]
        if vp > 0 and v > 0: m[d] = math.log(v/vp)*100.0
    return m

def get_reaction(rmap, rel_date):
    for off in (0, 1, -1, 2):  # holiday shift tolerance
        r = rmap.get(rel_date + dt.timedelta(days=off))
        if r is not None: return r
    return None

def mean(xs): return sum(xs)/len(xs) if xs else 0.0
def sd(xs):
    if len(xs) < 2: return 0.0
    m = mean(xs); return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))

def analyze(name, levels_fn, scale, rel_wd, sym, rhour_fn, rday_fn, contract):
    levels = load_eia(levels_fn, scale)
    ch = weekly_changes(levels)
    surp = seasonal_surprise(ch)  # (date, actual, exp, surprise)
    rhr = release_hour_map(rhour_fn, 10)
    rdy = release_day_map(rday_fn)
    # assemble matched records where a reaction exists
    recs = []  # dict per release
    for d, actual, exp, s in surp:
        rel = next_weekday_after(d, rel_wd)
        r_hr = get_reaction(rhr, rel)
        r_dy = get_reaction(rdy, rel)
        if r_hr is None and r_dy is None: continue
        recs.append(dict(period=str(d), release=str(rel), actual=actual, seasonal_exp=exp,
                         surprise=s, bull=-s, r_hour=r_hr, r_day=r_dy,
                         season=("withdrawal" if d.month in (11,12,1,2,3) else "injection")))
    def bucketize(rkey):
        rr = [x for x in recs if x[rkey] is not None]
        surps = [x["surprise"] for x in rr]
        asurp = sorted(abs(s) for s in surps)
        # in-line = smallest tercile of |surprise|
        t1 = asurp[len(asurp)//3] if asurp else 0
        buckets = defaultdict(list)
        for x in rr:
            s = x["surprise"]; r = x[rkey]
            if abs(s) <= t1: b = "in-line / small-surprise (stand-aside)"
            elif s < 0 and r > 0: b = "bullish-surprise -> UP (confirmation)"
            elif s < 0 and r < 0: b = "bullish-surprise -> DOWN (sell-the-news)"
            elif s > 0 and r < 0: b = "bearish-surprise -> DOWN (confirmation)"
            else:                 b = "bearish-surprise -> UP (reversal)"
            buckets[b].append(x)
        # directional-edge core: correlation(bull, reaction) and sign-conditional hit-rates
        bulls = [x["bull"] for x in rr]; reacts = [x[rkey] for x in rr]
        n = len(rr)
        mb, mr = mean(bulls), mean(reacts)
        cov = sum((b-mb)*(r-mr) for b,r in zip(bulls,reacts))/(n-1) if n>1 else 0
        corr = cov/(sd(bulls)*sd(reacts)) if sd(bulls)*sd(reacts)>0 else 0
        # hit-rate of directional hypothesis on MEANINGFUL surprises (excl in-line)
        meaningful = [x for x in rr if abs(x["surprise"]) > t1]
        nm = len(meaningful)
        hit = sum(1 for x in meaningful if (x["bull"]>0) == (x[rkey]>0))/nm if nm else None
        # PLACEBO for direction = binomial null of 0.5; z = (hit-0.5)/sqrt(0.25/nm)
        hit_z = (hit-0.5)/math.sqrt(0.25/nm) if nm else None
        # DOSE-RESPONSE: hit-rate by |surprise| tercile (rising => the surprise really drives it)
        ms = sorted(meaningful, key=lambda x: abs(x["surprise"]))
        def hr(sub): return round(sum(1 for x in sub if (x["bull"]>0)==(x[rkey]>0))/len(sub),3) if sub else None
        dose = dict(small=hr(ms[:len(ms)//2]), large=hr(ms[len(ms)//2:]))
        # CONFIRMATION vs COUNTER-MOVE counts (does fundamental win more often than fade?)
        conf = sum(1 for x in meaningful if (x["bull"]>0)==(x[rkey]>0))
        counter = nm - conf
        # conditional WEIGHT: mean|reaction| on meaningful vs in-line surprises
        inl = [x[rkey] for x in rr if abs(x["surprise"])<=t1]
        magw = dict(mean_abs_meaningful=round(mean([abs(x[rkey]) for x in meaningful]),4) if meaningful else None,
                    mean_abs_inline=round(mean([abs(v) for v in inl]),4) if inl else None)
        # slope reaction ~ bull (bps reaction per unit surprise)
        var_b = sd(bulls)**2
        slope = cov/var_b if var_b>0 else 0
        bstats = {}
        for b, xs in buckets.items():
            rs = [x[rkey] for x in xs]
            bstats[b] = dict(N=len(xs), mean_signed=round(mean(rs),4), mean_abs=round(mean([abs(v) for v in rs]),4),
                             sd=round(sd(rs),4),
                             pct_up=round(sum(1 for v in rs if v>0)/len(rs),3),
                             mean_surprise=round(mean([x["surprise"] for x in xs]),2))
        return dict(n_total=n, corr_bull_reaction=round(corr,3),
                    directional_hitrate_meaningful=round(hit,3) if hit else None,
                    directional_hitrate_z_vs_placebo=round(hit_z,2) if hit_z is not None else None,
                    n_meaningful=nm,
                    confirmation_vs_countermove=f"{conf} vs {counter}",
                    dose_response_hitrate_small_vs_large=dose,
                    conditional_weight=magw,
                    slope_pct_per_unit=round(slope,4),
                    inline_threshold_abs_surprise=round(t1,2),
                    buckets=bstats)
    # regime split: big vs small surprise, and season
    def regime(rkey):
        rr = [x for x in recs if x[rkey] is not None]
        out = {}
        for seas in ("withdrawal","injection"):
            sub = [x for x in rr if x["season"]==seas]
            if len(sub) < 8: continue
            bulls=[x["bull"] for x in sub]; reacts=[x[rkey] for x in sub]
            mb,mr=mean(bulls),mean(reacts)
            cov=sum((b-mb)*(r-mr) for b,r in zip(bulls,reacts))/(len(sub)-1)
            corr=cov/(sd(bulls)*sd(reacts)) if sd(bulls)*sd(reacts)>0 else 0
            out[seas]=dict(N=len(sub), corr_bull_reaction=round(corr,3))
        # big-surprise tercile hit-rate
        asurp=sorted(rr,key=lambda x:abs(x["surprise"]))
        big=asurp[2*len(asurp)//3:]
        hit=sum(1 for x in big if (x["bull"]>0)==(x[rkey]>0))/len(big) if big else None
        out["big_surprise_tercile"]=dict(N=len(big), directional_hitrate=round(hit,3) if hit else None)
        return out
    return dict(event=name, contract=contract, symbol=sym,
                surprise_proxy="actual weekly change - 5yr same-ISO-week avg change (SEASONAL proxy for consensus)",
                n_releases_matched=len(recs),
                intraday_release_hour=bucketize("r_hour"),
                daily_release_day=bucketize("r_day"),
                regimes_intraday=regime("r_hour"),
                regimes_daily=regime("r_day"))

if __name__ == "__main__":
    out = {}
    # NatGas: storage Bcf, released Thu(3); reaction NG=F
    out["natgas_storage"] = analyze("EIA Natural Gas Storage", "eia_ng_storage.json", 1.0, 3,
        "NG=F", "yh_NG_60m.csv", "yh_NG_1d.csv", "KXNATGASD")
    # Crude: stocks thousand bbl -> million bbl, released Wed(2); reaction CL=F
    out["crude_stocks"] = analyze("EIA Weekly Crude Stocks", "eia_crude_stocks.json", 1/1000.0, 2,
        "CL=F", "yh_CL_60m.csv", "yh_CL_1d.csv", "KXWTI")
    json.dump(out, open("/home/user/Markets/research/kalshi/hist/eia_bucket_results.json","w"), indent=2, default=str)
    # console summary
    for k, v in out.items():
        print(f"\n===== {k}  (n_matched={v['n_releases_matched']}) =====")
        for lens in ("intraday_release_hour","daily_release_day"):
            b = v[lens]
            print(f"-- {lens}: n={b['n_total']} corr(bull,reaction)={b['corr_bull_reaction']} "
                  f"dir_hitrate(meaningful,n={b['n_meaningful']})={b['directional_hitrate_meaningful']} "
                  f"slope={b['slope_pct_per_unit']}")
            for name, s in sorted(b["buckets"].items()):
                print(f"     {name:<44} N={s['N']:<4} mean_signed={s['mean_signed']:+.3f}%  %up={s['pct_up']:.2f}  mean|r|={s['mean_abs']:.3f}")
        print("   regimes(intraday):", v["regimes_intraday"])
