"""Study B: arrival, quote endings and early signals keep distinct populations."""
import collections,gzip,io,json
import numpy as np
import pandas as pd
from event_common import NS,TICK,BASE,DREV,MREV,source_file
from finish_family_replication import get

def first_changed_state(prices,sizes,segments):
    end=np.full(len(prices),-1,np.int64)
    for j in range(len(prices)-2,-1,-1):
        if segments[j]>=0 and segments[j]==segments[j+1]:
            end[j]=j+1 if prices[j]!=prices[j+1] or sizes[j]!=sizes[j+1] else end[j+1]
    return end

def signal_indices(price,size,seg,start=0,stop=None):
    stop=len(price) if stop is None else stop
    thin=[];early=[];was=False
    for j in range(start,stop):
        pair=j>start and seg[j]>=0 and seg[j]==seg[j-1]
        if pair and size[j]==1 and (price[j]!=price[j-1] or size[j-1]!=1):thin.append(j)
        eligible=j>=start+2 and seg[j]>=0 and seg[j]==seg[j-2] and price[j]==price[j-1]==price[j-2] and size[j-2]>=size[j-1]>=size[j]>1 and size[j-2]>size[j]
        if eligible and not was:early.append(j)
        was=eligible
    return thin,early

def tests():
    p=np.array([100]*6);s=np.array([5,4,3,2,1,2]);seg=np.array([0]*6)
    assert signal_indices(p,s,seg)==([4],[2])
    assert first_changed_state(p,s,seg)[4]==5
    assert signal_indices(p,s,np.array([0,0,1,1,1,1]))==([4],[])
    print("PASS: early candidates do not require future thinness; no boundary bridge",flush=True)

def study(ctx):
    tests();g=ctx.g;n=len(g);seg=ctx.seg
    pg=np.array(sorted({int(t["group_ordinal"]) for t in ctx.trades if ctx.valid[int(t["group_ordinal"])]}),np.int64)
    directed=collections.defaultdict(list)
    for t in ctx.trades:
        j=int(t["group_ordinal"]);key=(t["aggressor_side"],int(t["price_raw"]))
        if ctx.valid[j] and key[0] in ("A","B") and (not directed[key] or directed[key][-1]!=j):directed[key].append(j)
    directed={k:np.array(v,np.int64) for k,v in directed.items()}
    quantities={}
    for side in ("B","A","N"):
        a=np.zeros(n,np.int64)
        for t in ctx.trades:
            if (t["aggressor_side"] if t["aggressor_side"] in ("B","A") else "N")==side:
                a[int(t["group_ordinal"])]+=int(t["size"])
        quantities[side]=np.r_[0,np.cumsum(a)]
    segstart=np.full(n,-1,np.int64)
    for j in range(n):
        if ctx.valid[j]:segstart[j]=segstart[j-1] if j and seg[j]==seg[j-1] else j
    def context(j,side,price):
        result={}
        for label,indices in (("all",pg),("attacking_same_price",directed.get(("A" if side=="B" else "B",int(price)),np.array([],np.int64)))):
            pos=int(np.searchsorted(indices,j,side="left"));last=indices[max(0,pos-3):pos]
            valid=len(last)==3 and np.all(seg[last]==seg[j])
            result[label+"_prior_print_groups"]=last.tolist()
            result[label+"_gap_trend"]="insufficient_history"
            if valid:
                a,b,c=(int(ctx.t[x]) for x in last);old=b-a;new=c-b
                result.update({label+"_earlier_gap_ns":old,label+"_last_gap_ns":new,
                    label+"_gap_trend":"widening" if new>old else "narrowing" if new<old else "equal",
                    label+"_age_since_last_ns":int(ctx.t[j])-c})
        for h in (1,5,20,60):
            k=int(np.searchsorted(ctx.t,int(ctx.t[j])-h*NS,side="right"))
            result[f"flow{h}_complete_history"]=bool(k>segstart[j])
            for sidecode,label in (("B","buy"),("A","sell"),("N","unknown")):
                result[f"flow{h}_{label}_lots"]=int(quantities[sidecode][j+1]-quantities[sidecode][max(k,segstart[j])])
        result["fresh_group_print_count"]=int(g.print_count.iloc[j])
        return result
    def replay(j,direction,boundary):
        entry=ctx.eligible_later(j,int(ctx.t[j])+1000000)
        if entry is not None and entry>=boundary:entry=None
        outcomes=[]
        for h in (1,5,30):
            k=ctx.eligible_later(entry,int(ctx.t[entry])+h*NS) if entry is not None else None
            if k is not None and k>=boundary:k=None
            outcomes.append(dict(horizon_s=h,entry_clocks=ctx.point(entry) if entry is not None else None,
                exit_clocks=ctx.point(k) if k is not None else None,
                disposition="observed" if k is not None else "entry_censored" if entry is None else "exit_censored",
                signed_midpoint_change_twice_raw=int(direction*(ctx.mid[k]-ctx.mid[entry])) if k is not None else None,
                spread_crossing_raw=int(g.bid_price_raw.iloc[k]-g.ask_price_raw.iloc[entry]) if direction>0 and k is not None else int(g.bid_price_raw.iloc[entry]-g.ask_price_raw.iloc[k]) if k is not None else None))
        return entry,outcomes
    episodes=[];signals=[];outcomes=[];bytype=collections.Counter();reference={}
    # Pull prior second levels only where a price actually changes.
    second={}
    for path in ctx.group_files:
        part=pd.read_parquet(path,columns=["group_ordinal","bid_top10_json","ask_top10_json"])
        for r in part.itertuples(index=False):
            j=int(r.group_ordinal)
            if j+1>=n:continue
            for label,side in (("bid","B"),("ask","A")):
                if g[f"{label}_price_raw"].iloc[j]!=g[f"{label}_price_raw"].iloc[j+1]:
                    levels=json.loads(getattr(r,f"{label}_top10_json"))
                    second[(side,j)]=levels[1][0] if len(levels)>1 else None
    for side,label,direction in (("B","bid",-1),("A","ask",1)):
        prices=g[f"{label}_price_raw"].to_numpy(np.int64);sizes=g[f"{label}_size"].to_numpy(np.int64)
        ends=first_changed_state(prices,sizes,seg)
        thin,early=signal_indices(prices,sizes,seg)
        ret=[j for j in range(1,n) if ctx.valid[j] and seg[j]==seg[j-1] and direction*(prices[j]-prices[j-1])>0 and second.get((side,j-1))==prices[j]]
        for kind,indices in (("size_one",thin),("early_falling",early),("retreat_previous_second",ret)):
            bytype[kind]+=len(indices)
            for j in indices:
                ident=f"{ctx.day}:{kind}:{side}:{j}"
                entry,results=replay(j,direction,n)
                c=context(j,side,prices[j])
                signal=dict(event_id=ident,event_type=kind,side=side,signal_group=j,signal_clocks=ctx.point(j),
                    price_raw=int(prices[j]),size=int(sizes[j]),entry_group=entry,
                    previous_two_group_clocks=[ctx.point(k) for k in range(max(0,j-2),j)],
                    **c)
                signals.append(signal)
                for row in results:outcomes.append(dict(event_id=ident,event_type=kind,side=side,**row))
                if kind=="size_one":
                    e=int(ends[j]);status="right_censored" if e<0 else "recovered_same_price" if prices[e]==prices[j] else "retreated" if direction*(prices[e]-prices[j])>0 else "improved"
                    history="insufficient_history"
                    if j>=3 and seg[j-3]==seg[j]:
                        if np.all(prices[j-3:j]==prices[j]):
                            v=sizes[j-3:j];history="flat" if v[0]==v[1]==v[2] else "falling" if v[0]>=v[1]>=v[2] else "building" if v[0]<=v[1]<=v[2] else "mixed"
                        else:history="prior_best_changed"
                    episodes.append(dict(event_id=ident,side=side,onset_group=j,onset_clocks=ctx.point(j),
                        onset_type="new_best" if prices[j]!=prices[j-1] else "standing_best_shrank",
                        prior_three_close_history=history,onset_has_print=bool(g.print_count.iloc[j]),
                        ending=status,end_group=e if e>=0 else None,end_clocks=ctx.point(e),
                        duration_known_by_ns=int(ctx.t[e]-ctx.t[j]) if e>=0 else None,
                        end_by_entry=bool(e>=0 and entry is not None and e<=entry),
                        end_not_observed=e<0,**c))
        if ctx.day=="20231018":
            lo,hi=229201,251395
            rt,re=signal_indices(prices,sizes,seg,lo,hi)
            rr=[j for j in ret if lo<j<hi]
            reference[side]=dict(size_one=len(rt),early_falling=len(re),retreat_previous_second=len(rr))
    if ctx.day=="20231018":
        assert sum(x["size_one"] for x in reference.values())==1012,reference
        assert sum(x["early_falling"] for x in reference.values())==2850,reference
        assert sum(x["retreat_previous_second"] for x in reference.values())==698,reference
    ctx.save("b-signals",signals);ctx.save("b-quote-episodes",episodes);ctx.save("b-delayed-outcomes",outcomes)
    # The saved standalone detector is kept distinct from the early-falling rule.
    m=json.loads(get("markets-data",DREV,"MANIFEST.json"))
    e=next(e for e in m["entries"] if e.get("session")==ctx.day and e["path"].endswith("decisions.jsonl.gz"))
    falling=collections.defaultdict(set)
    for r in map(json.loads,gzip.decompress(get("markets-data",DREV,e["markets_data_path"],e["sha256"])).splitlines()):
        if r["rule"]=="falling-touch.v1" and r["disposition"]=="CANDIDATE":
            assert ctx.c[r["group"]]==r["cursor"] and ctx.t[r["group"]]==r["known_by_ns"]
            falling[r["group"]].add(r["side"])
    arrival=[];counts=collections.defaultdict(collections.Counter)
    firstprint={int(t["group_ordinal"]):int(t["receive_ns"]) for t in reversed(ctx.trades)}
    for j in range(n-1):
        if not ctx.valid[j] or seg[j]!=seg[j+1]:continue
        sides=falling.get(j,set());move=int(np.sign(ctx.mid[j+1]-ctx.mid[j]))
        queue=int(np.sign(g.bid_size.iloc[j]-g.ask_size.iloc[j]));call=(1 if "ask" in sides else -1) if len(sides)==1 else 0
        counts[bool(g.print_count.iloc[j]),bool(sides)]["opportunities"]+=1
        counts[bool(g.print_count.iloc[j]),bool(sides)]["next_print_group"]+=bool(g.print_count.iloc[j+1])
        arrival.append(dict(decision_group=j,decision_known_by_ns=int(ctx.t[j]),decision_cursor=int(ctx.c[j]),
            next_group=j+1,next_known_by_ns=int(ctx.t[j+1]),elapsed_known_by_ns=int(ctx.t[j+1]-ctx.t[j]),
            current_has_print=bool(g.print_count.iloc[j]),next_has_print=bool(g.print_count.iloc[j+1]),
            first_next_print_receive_ns=firstprint.get(j+1),
            next_print_lead_ns=firstprint[j+1]-int(ctx.t[j]) if j+1 in firstprint else None,
            standalone_falling_touch=bool(sides),falling_direction=call,queue_direction=queue,
            midpoint_direction=move,spread_raw=int(g.ask_price_raw.iloc[j]-g.bid_price_raw.iloc[j]),
            utc_hour=int(ctx.t[j]//(3600*NS))))
    ctx.save("b-next-group-arrival",arrival)
    if ctx.day=="20231018":
        expected=json.loads(get("Markets",MREV,BASE+"/october18-prebirth-research.json"))["close_pairs"]["unconditional"]
        for r in expected:assert dict(counts[r["current_group_has_print"],r["falling_touch"]])=={k:r[k] for k in ("opportunities","next_print_group")}
    ctx.summary["B"]=dict(signals=dict(bytype),quote_episodes=len(episodes),delayed_outcomes=len(outcomes),
        adjacent_opportunities=len(arrival),reference_window_counts=reference,
        endings=dict(collections.Counter(r["ending"] for r in episodes)),
        arrival_cells=[dict(current_has_print=k[0],standalone_falling_touch=k[1],**v) for k,v in sorted(counts.items())],
        definitions="historical 1ms entry and 1/5/30s exits; first later completed quote; observed spread only, no fees or fill claim")
    ctx.b_signals=signals;ctx.b_episodes=episodes
