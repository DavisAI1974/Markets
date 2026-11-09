"""Independent checks on published combined studies and old bounded replay."""
import collections,json,pathlib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from event_common import Context,NS,BASE,MREV,records
from event_pressure import signal_indices
from finish_family_replication import get,jsonwrite

def run(ctx):
    root=ctx.out
    signals=pq.read_table(root/"b-signals.parquet").to_pylist()
    episodes=pq.read_table(root/"b-quote-episodes.parquet").to_pylist()
    for s in signals:
        j=s["signal_group"];cl=s["signal_clocks"]
        assert cl["known_by_ns"]==ctx.t[j] and cl["close_cursor"]==ctx.c[j]
        for p in s["previous_two_group_clocks"][:-1]:
            assert p["close_cursor"]<ctx.c[j] and p["known_by_ns"]<=ctx.t[j]
        for field in ("all_prior_print_groups","attacking_same_price_prior_print_groups"):
            assert all(k<j for k in s[field])
    for e in episodes:
        k=e["end_group"];j=e["onset_group"]
        if k is not None:
            assert k>j and ctx.seg[k]==ctx.seg[j]
            assert e["duration_known_by_ns"]==int(ctx.t[k]-ctx.t[j])
    outcomes=pq.read_table(root/"b-delayed-outcomes.parquet").to_pylist()
    byid={s["event_id"]:s for s in signals}
    assert len(outcomes)==3*len(signals)
    for r in outcomes:
        s=byid[r["event_id"]];en=r["entry_clocks"];ex=r["exit_clocks"]
        if en:
            assert en["known_by_ns"]>=s["signal_clocks"]["known_by_ns"]+1000000
            assert en["group"]==ctx.eligible_later(s["signal_group"],s["signal_clocks"]["known_by_ns"]+1000000)
        if ex:
            assert ex["group"]==ctx.eligible_later(en["group"],en["known_by_ns"]+r["horizon_s"]*NS)
    bad=[]
    def checkfield(f,prefix):
        if f.name.endswith("_ns") and not (pa.types.is_integer(f.type) or pa.types.is_null(f.type)):
            bad.append(prefix+f.name+":"+str(f.type))
        if pa.types.is_struct(f.type):
            for child in f.type:checkfield(child,prefix+f.name+".")
        if pa.types.is_list(f.type) and pa.types.is_struct(f.type.value_type):
            for child in f.type.value_type:checkfield(child,prefix+f.name+"[].")
    for p in root.glob("*.parquet"):
        for f in pq.read_schema(p):checkfield(f,p.name+":")
    assert not bad,bad
    result=dict(individual_signal_clocks="passed",prior_print_order="passed",episode_endings="passed",
        delayed_quote_clocks="passed",exact_integer_ns_schema="passed",signals=len(signals),
        historical_reference="not applicable on this date")
    if ctx.day=="20231018":
        prefix="artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/"
        ref=json.loads(get("Markets",MREV,prefix+"receipt.json"))
        early=json.loads(get("Markets",MREV,prefix+"early-falling-touch-replay-receipt.json"))
        lo,hi=229201,251395
        observed=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
        for side,label,direction in (("B","bid",-1),("A","ask",1)):
            p=ctx.g[label+"_price_raw"].to_numpy(np.int64);z=ctx.g[label+"_size"].to_numpy(np.int64)
            thin,falling=signal_indices(p,z,ctx.seg,lo,hi)
            retreat=[s["signal_group"] for s in signals if s["side"]==side and s["event_type"]=="retreat_previous_second" and lo<s["signal_group"]<hi]
            for kind,indices in (("size_one_touch_onset",thin),("retreat_to_previous_second",retreat),("early_"+side,falling)):
                for j in indices:
                    en=ctx.eligible_later(j,int(ctx.t[j])+1000000)
                    if en is not None and en>=hi:en=None
                    for h in (1,5,30):
                        ex=ctx.eligible_later(en,int(ctx.t[en])+h*NS) if en is not None else None
                        if ex is not None and ex>=hi:ex=None
                        c=observed[kind][str(h)]
                        c["ENTRY_CENSORED" if en is None else "EXIT_CENSORED" if ex is None else "OBSERVED"]+=1
                        if ex is not None:
                            mid=direction*int(ctx.mid[ex]-ctx.mid[en])
                            cross=int(ctx.g.bid_price_raw.iloc[ex]-ctx.g.ask_price_raw.iloc[en]) if direction>0 else int(ctx.g.bid_price_raw.iloc[en]-ctx.g.ask_price_raw.iloc[ex])
                            for field,value in (("signed_twice_midpoint_change_raw",mid),("cross_spread_pnl_raw",cross)):
                                sign=1 if value>0 else -1 if value<0 else 0
                                label2={1:"positive",-1:"negative",0:"flat"}[sign] if kind.startswith("early_") else str(sign)
                                c[field+"_"+label2]+=1
        for kind in ("size_one_touch_onset","retreat_to_previous_second"):
            for h,values in ref["outcomes"][kind].items():assert dict(observed[kind][h])==values,(kind,h,observed[kind][h],values)
        for side in ("B","A"):
            for h,values in early["results_by_side"][side]["outcomes"].items():assert dict(observed["early_"+side][h])==values,(side,h,observed["early_"+side][h],values)
        endcounts=collections.Counter();byentry=collections.Counter()
        for e in episodes:
            if lo<e["onset_group"]<hi:
                label={"retreated":"RETREATED","improved":"IMPROVED","recovered_same_price":"SIZE_RECOVERED_AT_SAME_PRICE"}[e["ending"]]
                endcounts[label]+=1
                if e["end_by_entry"]:byentry[label]+=1
        assert dict(endcounts)==ref["thin_episode_end_counts"]
        assert dict(byentry)==ref["thin_episode_end_by_entry"]
        result["historical_reference"]="All twelve side/rule x horizon outcome cells and thin-ending/by-entry counts reproduced"
        result["reference_outcomes"]={k:{h:dict(c) for h,c in d.items()} for k,d in observed.items()}
    jsonwrite(root/"verification.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="reference_outcomes"}),flush=True)
