#!/usr/bin/env python3
"""(2) WEATHER-DRIVER CHAIN: weather -> heating/cooling demand -> storage draw/build -> price.
Establish empirically in two links, per season:
  LINK A: does the weather ANOMALY (weekly gas-wtd HDD / pop-wtd CDD vs 5yr same-week normal)
          predict the SIGN+SIZE of the storage surprise?   [weather -> storage number]
  LINK B: does the weather anomaly (or storage surprise) predict the release-window PRICE move?
Payoff: if LINK A holds, a degree-day FORECAST is upstream of the natgas price -> the OD-weather
forecaster becomes a natgas-price forecaster. Quantify honestly; report if weaker than desk lore.
Data: NOAA CPC gas-wtd HDD (UtilityGas.Heating) + pop-wtd CDD (Population.Cooling), 2010-2026,
national = equal-wt mean of 9 census divisions (PROXY for gas-customer-weighted national).
"""
import json, datetime as dt, math
from collections import defaultdict
import sys; sys.path.insert(0,"/home/user/Markets/research/kalshi/hist")
from eia_bucket_study import (load_eia, weekly_changes, seasonal_surprise,
    next_weekday_after, release_hour_map, release_day_map, get_reaction, mean, sd)
from natgas_season_study import regime, REGIMES, wksum

HDD={dt.date.fromisoformat(k):v for k,v in json.load(open("/home/user/Markets/data/kalshi_hist/cpc_HDD.json")).items()}
CDD={dt.date.fromisoformat(k):v for k,v in json.load(open("/home/user/Markets/data/kalshi_hist/cpc_CDD.json")).items()}

def week_sum(mp, end_date):
    tot=0; got=0
    for i in range(7):
        v=mp.get(end_date-dt.timedelta(days=i))
        if v is not None: tot+=v; got+=1
    return tot if got>=5 else None

def corr(xs,ys):
    n=len(xs); mx,my=mean(xs),mean(ys)
    cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(n-1) if n>1 else 0
    sx,sy=sd(xs),sd(ys)
    return cov/(sx*sy) if sx*sy>0 else 0

def build():
    levels=load_eia("eia_ng_storage.json",1.0)
    surp=seasonal_surprise(weekly_changes(levels))  # (date, actual_change, exp, surprise)
    rhr=release_hour_map("yh_NG_60m.csv",10); rdy=release_day_map("yh_NG_1d.csv")
    # demand driver PER DISCOVERED REGIME: HDD in winter-withdrawal, CDD in summer-withdrawal,
    # dominant DD in shoulders (the double-hump uses the right thermometer in each regime)
    wk_weather={}
    for d,_,_,_ in surp:
        reg=regime(d); h=week_sum(HDD,d); c=week_sum(CDD,d)
        if reg==REGIMES[0]:   w=h            # winter-withdrawal -> HDD
        elif reg==REGIMES[1]: w=c            # summer-withdrawal -> CDD
        else:                 w=(h if (h or 0)>=(c or 0) else c)  # shoulder -> dominant DD
        wk_weather[d]=w
    by_wk=defaultdict(list)
    for d,w in wk_weather.items():
        if w is not None: by_wk[d.isocalendar()[1]].append((d.year,w))
    recs=[]
    for d,actual,exp,s in surp:
        w=wk_weather.get(d)
        if w is None: continue
        prior=[x for (yr,x) in by_wk[d.isocalendar()[1]] if d.year-5<=yr<d.year]
        if len(prior)<3: continue
        w_anom=w-sum(prior)/len(prior)
        rel=next_weekday_after(d,3)
        recs.append(dict(period=d,regime=regime(d),storage_change=actual,
            surprise=s,bull=-s,w_anom=w_anom,
            r_hour=get_reaction(rhr,rel),r_day=get_reaction(rdy,rel)))
    return recs

def link_report(recs):
    out={}
    for seas in REGIMES+["ALL"]:
        sub=[x for x in recs if seas=="ALL" or x["regime"]==seas]
        if len(sub)<15: out[seas]=dict(N=len(sub),note="too few"); continue
        wa=[x["w_anom"] for x in sub]
        # LINK A: weather anomaly -> storage change, and -> storage surprise
        chg=[x["storage_change"] for x in sub]; sur=[x["surprise"] for x in sub]
        cA_change=corr(wa,chg); cA_surprise=corr(wa,sur)
        # directional: does weather anomaly predict the surprise SIGN? (colder/hotter -> tighter -> bull)
        # convention: high HDD/CDD anomaly => more demand => bigger draw => negative surprise => bull>0
        hitA=sum(1 for x in sub if (x["w_anom"]>0)==((-x["surprise"])>0))/len(sub)
        # LINK B: weather anomaly -> price; storage surprise -> price (release DAY, deeper N)
        subd=[x for x in sub if x["r_day"] is not None]
        cB_weather=corr([x["w_anom"] for x in subd],[x["r_day"] for x in subd]) if len(subd)>2 else None
        cB_surprise=corr([x["bull"] for x in subd],[x["r_day"] for x in subd]) if len(subd)>2 else None
        # weather-implied directional price hit-rate (colder/hotter -> price up)
        hitB=sum(1 for x in subd if (x["w_anom"]>0)==(x["r_day"]>0))/len(subd) if subd else None
        out[seas]=dict(N=len(sub),
            LINK_A_weather_to_storage=dict(
                corr_wanom_storage_change=round(cA_change,3),
                R2_change=round(cA_change**2,3),
                corr_wanom_surprise=round(cA_surprise,3),
                R2_surprise=round(cA_surprise**2,3),
                surprise_sign_hitrate=round(hitA,3)),
            LINK_B_to_price=dict(N_day=len(subd),
                corr_wanom_price=round(cB_weather,3) if cB_weather is not None else None,
                corr_surprise_price=round(cB_surprise,3) if cB_surprise is not None else None,
                weather_implied_price_dir_hitrate=round(hitB,3) if hitB else None))
    return out

if __name__=="__main__":
    recs=build()
    rep=link_report(recs)
    out=dict(study="natgas weather-driver chain (weather -> storage -> price)",
        weather_source="NOAA CPC gas-wtd HDD (UtilityGas.Heating) + pop-wtd CDD (Population.Cooling), 2010-2026; national=equal-wt of 9 census divisions (PROXY)",
        n_matched=len(recs),
        convention="high HDD/CDD anomaly => more demand => bigger draw => tighter (bullish) => expect price UP",
        per_season=rep)
    json.dump(out,open("/home/user/Markets/research/kalshi/hist/natgas_weather_results.json","w"),indent=2,default=str)
    print(f"n_matched={len(recs)}")
    for seas,r in rep.items():
        if "LINK_A_weather_to_storage" not in r: print(f"{seas}: {r}"); continue
        a=r["LINK_A_weather_to_storage"]; b=r["LINK_B_to_price"]
        print(f"\n{seas} (N={r['N']}):")
        print(f"  LINK A weather->storage: corr(wanom,change)={a['corr_wanom_storage_change']} (R2={a['R2_change']})  "
              f"corr(wanom,surprise)={a['corr_wanom_surprise']} (R2={a['R2_surprise']})  surprise-sign hit={a['surprise_sign_hitrate']}")
        print(f"  LINK B ->price (day,N={b['N_day']}): corr(wanom,price)={b['corr_wanom_price']}  "
              f"corr(surprise,price)={b['corr_surprise_price']}  weather-dir price hit={b['weather_implied_price_dir_hitrate']}")
