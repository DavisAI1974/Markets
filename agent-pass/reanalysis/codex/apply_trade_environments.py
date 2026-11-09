"""Apply frozen findings to every saved trade environment. Read completed outputs only.
No producer, detector, model fitting, input normalization, or execution is run.
"""
import bisect, collections, csv, gc, gzip, hashlib, io, json, math, os, pathlib, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from source_review import fetch
D="DavisAI1974/markets-data"; M="DavisAI1974/Markets"
ROOT="tasks/family-research-20261022/"
EREV="87dc338f2e74646eb731b3cd6f8968a5a0a653e2"; EP=ROOT+"combined-events/run-42571551209-1"
GREV="2fd55ea1276d00530f8cdbd1caf5918910494f19"; GP=ROOT+"combined-events/run-42569937357-1"
LREV="2f1c3c72f9e3f15916135bca37ffcad87477e1d6"; LP=ROOT+"lifecycle-data-links/run-42583801329-1"
SREV="e2731854a42bcce04a8cf89e249603dc18d3b0f7"; SP=ROOT+"codex-independent-review/run-42594360842-1"
CODE=os.environ["CODE_REV"]; NS=10**9; TICK=10**6
READS=[]; EXPECTED={"20231002":37670,"20231003":41410,"20231017":33451,"20231018":30739}
def get(repo,rev,path,entry=None):
    b=fetch(repo,rev,path)
    h=hashlib.sha256(b).hexdigest()
    if entry:
        assert h==entry["sha256"],path
        assert len(b)==entry["bytes"],path
    READS.append(dict(repository=repo,revision=rev,path=path,bytes=len(b),sha256=h))
    return b
def js(repo,rev,path,entry=None):return json.loads(get(repo,rev,path,entry))
def readset(rev,base):
    manifest=js(D,rev,base+"/MANIFEST.json")
    entries={e["path"]:e for e in manifest["files"]}
    def read(name):return get(D,rev,base+"/"+name,entries[name])
    return entries,read
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def csvwrite(p,rows):
    rows=list(rows);keys=list(dict.fromkeys(k for r in rows for k in r))
    with open(p,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def writepq(p,df):
    # Nullable ns/index values are explicitly integer; no IEEE-754 clock intermediate.
    pq.write_table(pa.Table.from_pandas(df,preserve_index=False),p,compression="zstd")
def sg(x):return np.where(x>0,"positive",np.where(x<0,"negative","flat"))
def finite(x):
    if isinstance(x,dict):return {k:finite(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [finite(v) for v in x]
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def summarize(df,keys,values):
    rows=[]
    for k,g in df.groupby(keys,dropna=False,sort=True):
        if not isinstance(k,tuple):k=(k,)
        row=dict(zip(keys,k));row["n"]=len(g)
        for v in values:
            a=pd.to_numeric(g[v],errors="coerce");q=a.dropna()
            row[v+"_valid"]=len(q)
            row[v+"_mean"]=float(q.mean()) if len(q) else None
            row[v+"_median"]=float(q.median()) if len(q) else None
            row[v+"_positive"]=int((q>0).sum());row[v+"_negative"]=int((q<0).sum());row[v+"_flat"]=int((q==0).sum())
        rows.append(finite(row))
    return rows
def main(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    lm,lr=readset(LREV,LP)
    external=json.loads(gzip.decompress(lr("external/original-external-series.json.gz")))
    series=external["series"];bindings=json.loads(lr("external/all-13-input-bindings.json"))["points"]
    registry=json.loads(lr("external/canonical-99-registry.json"))
    layerlinks=json.loads(lr("99-layer-attachments.json"))
    with np.load(io.BytesIO(lr("external/external-contexts.npz")),allow_pickle=False) as z:
        pub=z["publication_ns"];prev=z["previous_original_index"]
    assert len(series)==48 and len(bindings)==13
    catalog=js(D,SREV,SP+"/SOURCE_CATALOG.json")
    def catalog_read(predicate):
        matches=[c for c in catalog if predicate(c["source"]["path"])]
        assert len(matches)==1,[c["source"]["path"] for c in matches]
        s=matches[0]["source"];return get(s["repository"],s["revision"],s["path"],s),s
    summaries=[];cells=[];cases=[];extrows=[];usedcontexts=set();family_summaries=[]
    for day in EXPECTED:
        print("READ",day,flush=True)
        em,er=readset(EREV,EP+"/events-"+day)
        gm,gr=readset(GREV,GP+"/events-"+day)
        parts=[]
        for name in sorted(n for n in gm if n.startswith("groups-")):
            parts.append(pq.read_table(io.BytesIO(gr(name))).to_pandas())
        g=pd.concat(parts,ignore_index=True);del parts
        assert g.group_ordinal.tolist()==list(range(len(g)))
        t=g.known_by_ns.to_numpy(np.int64);cursor=g.close_cursor.to_numpy(np.int64)
        assert np.all(t[1:]>=t[:-1]) and np.all(cursor[1:]>cursor[:-1])
        bid=g.bid_price_raw.to_numpy(np.int64);ask=g.ask_price_raw.to_numpy(np.int64);mid=bid+ask
        midnight=int(datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
        lo=(midnight if day in ("20231002","20231017") else midnight-7200)*NS;hi=(midnight+21*3600)*NS
        valid=(t>=lo)&(t<hi)&~g[["snapshot_member","reset_member","bad_receive_clock_member"]].any(axis=1).to_numpy()&(bid>0)&(ask>bid)
        connected=np.r_[False,(g.first_cursor.to_numpy()[1:]==cursor[:-1]+1)&(t[1:]>=t[:-1])]
        breaks=~valid|~np.r_[False,valid[:-1]]|~connected
        seg=np.cumsum(breaks);seg[~valid]=-1
        starts=np.maximum.accumulate(np.where(breaks,np.arange(len(g)),0))
        ends=np.minimum.accumulate(np.where(np.r_[breaks[1:],True],np.arange(len(g)),len(g)-1)[::-1])[::-1]
        tr=pq.read_table(io.BytesIO(er("a-trades.parquet"))).to_pylist()
        assert len(tr)==EXPECTED[day]
        tradegroup=np.array([r["group_ordinal"] for r in tr],np.int64)
        tc=np.array([r["trade_input_cursor"] for r in tr],np.int64)
        tt=np.array([r["receive_ns"] for r in tr],np.int64)
        avail=np.array([r["available_ns"] for r in tr],np.int64)
        prior=np.array([r["strict_prior_group"] if r["strict_prior_group"] is not None else -1 for r in tr],np.int64)
        okpre=prior>=0
        assert np.all(t[prior[okpre]]<tt[okpre]) and np.all(cursor[prior[okpre]]<tc[okpre])
        assert np.all(t[tradegroup]==avail)
        side=np.array([1 if r["aggressor_side"]=="B" else -1 if r["aggressor_side"]=="A" else 0 for r in tr])
        qty={}
        for code,label in [("B","buy"),("A","sell"),("N","unknown")]:
            q=np.zeros(len(g),np.int64)
            for r in tr:
                if (r["aggressor_side"] if r["aggressor_side"] in ("B","A") else "N")==code:q[r["group_ordinal"]]+=r["size"]
            qty[label]=np.r_[0,np.cumsum(q)]
        counts=np.zeros(len(g),np.int64);np.add.at(counts,tradegroup,1);qty["prints"]=np.r_[0,np.cumsum(counts)]
        # Flow and past prices are available by each original completed group.
        for h in [1,5,20,60]:
            ix=np.searchsorted(t,t-h*NS,side="right")
            begin=np.maximum(ix,starts)
            complete=(t-h*NS>=t[starts])&valid
            g["history_complete_"+str(h)]=complete
            for label,cs in qty.items():g[f"flow{h}_{label}"]=cs[np.arange(len(g))+1]-cs[begin]
            before=np.maximum(np.searchsorted(t,t-h*NS,side="right")-1,0)
            delta=(mid-mid[before])/(2*TICK)
            g[f"prior{h}_mid_ticks"]=np.where(complete,delta,np.nan)
        for side_name in ["bid","ask"]:
            # Preserve full-depth and local depth separately; fixed-price changes stay separate from moving rank.
            for kind in ["old_touch_effect","new_touch_effect","rank_change"]:
                objects=[json.loads(x) for x in g[side_name+"_"+kind+"_json"]]
                for field in objects[0]:
                    g[side_name+"_"+kind+"_"+field]=[x[field] for x in objects]
            top=[json.loads(x) for x in g[side_name+"_top10_json"]]
            g[side_name+"_near4_size"]=[sum(level[1] for level in levels if abs(level[0]-levels[0][0])<=4*TICK) if levels else 0 for levels in top]
            del top,objects
        g["spread_ticks"]=(ask-bid)/TICK
        g["touch_sign"]=np.sign(g.bid_size-g.ask_size).astype(int)
        g["touch_count_sign"]=np.sign(g.bid_orders-g.ask_orders).astype(int)
        g["full_depth_sign"]=np.sign(g.bid_full_size-g.ask_full_size).astype(int)
        g["near_depth_sign"]=np.sign(g.bid_near4_size-g.ask_near4_size).astype(int)
        # Native recognition is as observed. No future lifetime selection.
        ds=pq.read_table(io.BytesIO(er("a-dipole-clocks.parquet"))).to_pylist()
        ds=sorted([x for x in ds if x["live_recognition"]],key=lambda x:x["recognition_clocks"]["close_cursor"])
        dc=np.array([x["recognition_clocks"]["close_cursor"] for x in ds],np.int64)
        dt=np.array([x["recognition_ns"] for x in ds],np.int64)
        assert np.all(dt[1:]>=dt[:-1])
        indices=np.minimum(np.searchsorted(dc,tc,side="left")-1,np.searchsorted(dt,tt,side="left")-1)
        env=pd.DataFrame({"day":day,"trade_ordinal":np.arange(len(tr)),"trade_id":[day+":trade:"+str(i) for i in range(len(tr))],
            "receive_ns":tt,"event_ns":np.array([r["event_ns"] for r in tr],np.int64),"available_ns":avail,
            "trade_input_cursor":tc,"group_ordinal":tradegroup,"strict_prior_group":prior,"aggressor":side,
            "price_raw":np.array([r["price_raw"] for r in tr],np.int64),"lots":np.array([r["size"] for r in tr],np.int64),
            "stretch_id":[r["stretch_id"] for r in tr],"leg_ids_json":[json.dumps(r["overlapping_leg_ids"]) for r in tr]})
        env["latest_recognized_dipole"]=[ds[k]["candidate_id"] if k>=0 else None for k in indices]
        env["dipole_age_ns"]=pd.array([int(tt[i])-ds[k]["recognition_ns"] if k>=0 else None for i,k in enumerate(indices)],dtype="Int64")
        env["dipole_polarity"]=[ds[k]["polarity"] if k>=0 else None for k in indices]
        env["pre_available"]=okpre&valid[np.maximum(prior,0)]&(seg[np.maximum(prior,0)]==seg[tradegroup])
        env["source_segment_valid"]=valid[tradegroup]
        fields=["spread_ticks","bid_size","ask_size","bid_orders","ask_orders","bid_full_size","ask_full_size",
            "bid_near4_size","ask_near4_size","touch_sign","touch_count_sign","full_depth_sign","near_depth_sign",
            "history_complete_1","history_complete_5","history_complete_20","history_complete_60"]+[
            f"flow{h}_{q}" for h in [1,5,20,60] for q in qty]+[f"prior{h}_mid_ticks" for h in [1,5,20,60]]
        phases=[];after={}
        for phase,h in [("before",None),("during",0),("after_1s",1),("after_5s",5),("after_20s",20),("after_60s",60),("after_600s",600)]:
            target=tt-1 if h is None else avail+h*NS
            ix=prior.copy() if h is None else tradegroup.copy() if h==0 else np.searchsorted(t,target,side="right")-1
            ix_safe=np.maximum(ix,0)
            available=(ix>=0)&valid[ix_safe]&valid[tradegroup]&(seg[ix_safe]==seg[tradegroup])&(target<=t[ends[tradegroup]])
            if h is None:available &= okpre
            selected=g.iloc[ix_safe].reset_index(drop=True)
            ph=pd.DataFrame({"day":day,"trade_ordinal":np.arange(len(tr)),"phase":phase,"target_ns":target,
                "source_group":ix,"source_cursor":cursor[ix_safe],"source_known_by_ns":t[ix_safe],"available":available,
                "quote_age_ns":target-t[ix_safe],"context_index":np.searchsorted(pub,target,side="right").astype(np.int32)})
            usedcontexts.update(ph.context_index.tolist())
            for name in ["bid_price_raw","ask_price_raw","bid_top10_json","ask_top10_json"]+fields:ph[name]=selected[name]
            # After windows contain only groups after the trade's completed group, excluding its own mechanics.
            for label,cs in qty.items():
                ph["post_"+label]=cs[ix_safe+1]-cs[tradegroup+1] if h and h>0 else np.zeros(len(tr),np.int64)
            ph["post_window_defined"]=bool(h and h>0)
            ph["change_from_during_mid_ticks"]=(mid[ix_safe]-mid[tradegroup])/(2*TICK)
            ph["change_from_pre_mid_ticks"]=(mid[ix_safe]-mid[np.maximum(prior,0)])/(2*TICK)
            for name in selected.columns:
                if "_effect_" in name or "_rank_change_" in name:ph[name]=selected[name]
            phases.append(ph)
            if h is None:
                for name in fields:env["pre_"+name]=selected[name]
                env["pre_quote_age_ns"]=tt-t[ix_safe]
            elif h==0:
                env["during_mid_change_ticks"]=np.where(env.pre_available,(mid[tradegroup]-mid[np.maximum(prior,0)])/(2*TICK),np.nan)
                for name in ["spread_ticks","touch_sign","full_depth_sign","near_depth_sign"]:env["during_"+name]=selected[name]
                for s in ["bid","ask"]:
                    for field in ["added","removed","fill_linked","unlinked","unchanged_display_fill"]:
                        env["during_"+s+"_"+field]=selected[s+"_old_touch_effect_"+field]
            else:
                after[h]=ph
                env[f"after{h}_available"]=available
                env[f"after{h}_quote_age_ns"]=ph.quote_age_ns
                env[f"after{h}_mid_ticks"]=np.where(available,ph.change_from_during_mid_ticks,np.nan)
                env[f"after{h}_net_lots"]=np.where(available,ph.post_buy-ph.post_sell,np.nan)
                env[f"after{h}_prints"]=np.where(available,ph.post_prints,np.nan)
        phase_df=pd.concat(phases,ignore_index=True)
        assert len(phase_df)==7*len(tr)
        assert np.all(phase_df.loc[phase_df.available,"source_known_by_ns"]<=phase_df.loc[phase_df.available,"target_ns"])
        writepq(out/(day+"-trade-phases.parquet"),phase_df)
        env["pre_flow_sign"]=np.sign(env.pre_flow20_buy-env.pre_flow20_sell)
        env.loc[~env.pre_history_complete_20,"pre_flow_sign"]=np.nan
        env["pre_price_sign"]=np.sign(env.pre_prior20_mid_ticks)
        env["pre_spread_regime"]=np.where(env.pre_spread_ticks==1,"one",np.where(env.pre_spread_ticks==2,"two","other"))
        env["pre_flow_vs_aggressor"]=np.where(env.pre_flow_sign.isna(),"unavailable",np.where(env.aggressor==0,"unknown_aggressor",sg(env.pre_flow_sign*env.aggressor)))
        env["pre_touch_vs_aggressor"]=np.where(env.aggressor==0,"unknown_aggressor",sg(env.pre_touch_sign*env.aggressor))
        env["pre_full_vs_touch"]=np.where(env.pre_full_depth_sign*env.pre_touch_sign>0,"same",np.where(env.pre_full_depth_sign*env.pre_touch_sign<0,"opposed","flat_component"))
        env["during_price_response"]=np.where(env.during_mid_change_ticks.isna(),"unavailable",sg(env.during_mid_change_ticks))
        env["during_fill_depletion"]=(env.during_bid_fill_linked>0)|(env.during_ask_fill_linked>0)
        env["during_unlinked_removal"]=(env.during_bid_unlinked>0)|(env.during_ask_unlinked>0)
        env["during_addition"]=(env.during_bid_added>0)|(env.during_ask_added>0)
        env["pre_external_context"]=np.searchsorted(pub,tt-1,side="right").astype(np.int32)
        env["during_external_context"]=np.searchsorted(pub,avail,side="right").astype(np.int32)
        for h in [1,5,20,60,600]:
            env[f"after{h}_external_context"]=np.searchsorted(pub,avail+h*NS,side="right").astype(np.int32)
        writepq(out/(day+"-trade-environments.parquet"),env)
        # Every grouping uses the whole eligible population; cells retain zero, adverse and missing outcomes.
        groups=[["day"],["day","aggressor"],["day","pre_available","pre_flow_vs_aggressor","pre_touch_vs_aggressor"],
            ["day","pre_available","pre_spread_regime","pre_flow_vs_aggressor","pre_touch_vs_aggressor"],
            ["day","pre_available","pre_full_vs_touch","pre_touch_vs_aggressor"],
            ["day","pre_available","pre_price_sign","pre_flow_sign","pre_touch_sign"],
            ["day","during_price_response","during_fill_depletion","during_unlinked_removal","during_addition"]]
        for grouping in groups:
            for h in [1,5,20,60,600]:
                z=env.copy()
                z["oriented_future_mid_ticks"]=z[f"after{h}_mid_ticks"]*z.aggressor.replace(0,np.nan)
                z["oriented_post_net_lots"]=z[f"after{h}_net_lots"]*z.aggressor.replace(0,np.nan)
                z["after_price_sign"]=np.sign(z[f"after{h}_mid_ticks"])
                for row in summarize(z,grouping,["oriented_future_mid_ticks","oriented_post_net_lots",f"after{h}_mid_ticks",f"after{h}_prints"]):
                    row.update(grouping="|".join(grouping),horizon_s=h);cells.append(row)
        # Price feedback is conditioned on the move's contemporaneous mechanism; causal identification is not claimed.
        price_rows=[]
        for h in [1,5,20,60]:
            z=env.copy()
            z["post_flow_vs_move"]=np.sign(z.during_mid_change_ticks)*z[f"after{h}_net_lots"]
            z["future_price_vs_move"]=np.sign(z.during_mid_change_ticks)*z[f"after{h}_mid_ticks"]
            for row in summarize(z,["day","during_price_response","during_fill_depletion","during_unlinked_removal","during_addition"],
                ["post_flow_vs_move","future_price_vs_move",f"after{h}_prints"]):
                row["horizon_s"]=h;price_rows.append(row)
        csvwrite(out/(day+"-price-feedback-cells.csv"),price_rows)
        # Existing pressure event conditions, quote episodes and all delayed outcomes are joined by exact event identity.
        links=pq.read_table(io.BytesIO(er("cross-study-event-links.parquet"))).to_pandas()
        oo=pq.read_table(io.BytesIO(er("b-delayed-outcomes.parquet"))).to_pylist()
        episodes=pq.read_table(io.BytesIO(er("b-quote-episodes.parquet"))).to_pylist()
        epby={e["event_id"]:e for e in episodes}
        lk={r["event_id"]:r for r in links.to_dict("records")}
        pressure=[]
        for o in oo:
            l=lk[o["event_id"]];e=epby.get(o["event_id"])
            r={**l,**o,"day":day,"episode_ending":e["ending"] if e else "not_size_one",
               "episode_end_by_entry":e["end_by_entry"] if e else None,
               "episode_duration_ns":e["duration_known_by_ns"] if e else None}
            # pandas null integer columns above are not serialized: rec clocks restored from source integer records below.
            r["latest_dipole_recognition_ns"]=None
            r["latest_dipole_recognition_cursor"]=None
            r["latest_known_trade_ordinal"]=None
            pressure.append(r)
        # Re-read exact integer link objects to avoid nullable pandas float inference.
        exactlinks={x["event_id"]:x for x in pq.read_table(io.BytesIO(er("cross-study-event-links.parquet"))).to_pylist()}
        for r in pressure:
            for k in ["latest_dipole_recognition_ns","latest_dipole_recognition_cursor","latest_known_trade_ordinal","dipole_recognition_age_ns"]:r[k]=exactlinks[r["event_id"]][k]
        pq.write_table(pa.Table.from_pylist(pressure),out/(day+"-pressure-applications.parquet"),compression="zstd")
        assert len(pressure)==3*len(links)
        psummary=[]
        for k,rr in pd.DataFrame([{**{k:r[k] for k in ["event_type","side","fresh_wire_flow_vs_signal","displayed_touch_vs_signal","prior_print_gap_trend","horizon_s","disposition","episode_ending","episode_end_by_entry"]},
            "mid_ticks":r["signed_midpoint_change_twice_raw"]/(2*TICK) if r["signed_midpoint_change_twice_raw"] is not None else None,
            "crossing_ticks":r["spread_crossing_raw"]/TICK if r["spread_crossing_raw"] is not None else None} for r in pressure]).groupby(["event_type","side","horizon_s","episode_ending"],dropna=False):
            psummary.extend(summarize(rr,["event_type","side","horizon_s","episode_ending"],["mid_ticks","crossing_ticks"]))
        csvwrite(out/(day+"-pressure-summary.csv"),psummary)
        # Complete saved family operands and original forward responses, with no chosen-family filter.
        b,s=catalog_read(lambda p:p.endswith("/"+day+"/t1_family_master.csv"))
        family=pd.read_csv(io.BytesIO(b),dtype=str,keep_default_na=False)
        assert family.family_id.is_unique
        writepq(out/(day+"-family-environments.parquet"),family)
        family_summaries.append({"day":day,"families":len(family),"source":s})
        # Keep every original large-move/return path and chronological whole leg.
        for name in ["c-large-quote-events.parquet","c-prior-signal-to-large-move.parquet","a-print-legs.parquet","a-trade-dipole-overlaps.parquet"]:
            (out/(day+"-"+name)).write_bytes(er(name))
        # Illustrations are the earliest occurrence per declared sequence/outcome, never the population used for summaries.
        patterns={"depletion_then_continued":env.during_fill_depletion&(env.during_mid_change_ticks*env.after20_mid_ticks>0),
            "depletion_then_reversed":env.during_fill_depletion&(env.during_mid_change_ticks*env.after20_mid_ticks<0),
            "move_then_flat":env.during_mid_change_ticks.ne(0)&env.after20_mid_ticks.eq(0),
            "book_flow_opposed":env.pre_flow_vs_aggressor.eq("positive")&env.pre_touch_vs_aggressor.eq("negative"),
            "full_local_disagree":env.pre_full_vs_touch.eq("opposed"),
            "price_flow_feedback_opposed":env.during_mid_change_ticks*env.after20_net_lots<0}
        for label,mask in patterns.items():
            eligible=env[mask&env.pre_available&env.after20_available]
            if len(eligible):
                ix=int(eligible.index[0]);row=finite(env.iloc[ix].to_dict())
                row.update(selection=label,selection_rule="first source-order eligible trade matching declared condition; all trades included in population ledgers",
                    phase_reference=day+"-trade-phases.parquet",source_trade=tr[ix])
                cases.append(row)
        summaries.append(dict(day=day,trades=len(tr),trade_phases=len(phase_df),pre_available=int(env.pre_available.sum()),
            source_groups=len(g),eligible_groups=int(valid.sum()),pressure_signals=len(links),pressure_outcomes=len(pressure),
            dipoles=len(ds),recognized_before_trade=int((indices>=0).sum()),family_rows=len(family),
            after_available={str(h):int(env[f"after{h}_available"].sum()) for h in [1,5,20,60,600]},
            after_quote_older_than_1s={str(h):int((env[f"after{h}_available"]&(env[f"after{h}_quote_age_ns"]>NS)).sum()) for h in [1,5,20,60,600]}))
        print("DONE",json.dumps(summaries[-1]),flush=True)
        del g,tr,env,phases,phase_df,after,pressure,oo,exactlinks,links
        gc.collect()
    # The same 48 original series are resolvable for every phase through the context index.
    # Retain original records, state and target dates; publication is not live ingestion.
    selected_rows=set()
    for ci in sorted(usedcontexts):
        for col,s in enumerate(series):
            ri=int(prev[ci,col])
            if ri>=0:selected_rows.add((col,ri))
    for col,ri in sorted(selected_rows):
        original=series[col]["known"][ri]
        extrows.append(dict(series_index=col,series_name=series[col]["name"],original_index=ri,**original))
    with gzip.open(out/"EXTERNAL_ORIGINAL_ROWS.jsonl.gz","wt") as f:
        for row in extrows:f.write(json.dumps(row)+"\n")
    with open(out/"EXTERNAL_CONTEXT_INDEX.npz","wb") as f:
        ids=np.array(sorted(usedcontexts),np.int32);np.savez_compressed(f,context_id=ids,previous_original_index=prev[ids],publication_ns=pub)
    external_points=[]
    for point in bindings:
        names=[s["series"] for s in point["series"]]
        external_points.append(dict(point_id=point["point_id"],name=point["name"],series=names,
            before="Latest original publication at or before pre-trade clock, retaining state, vintage and target date",
            during="Changes only if an original publication boundary is crossed; no fabricated instantaneous effect",
            after="Follow new publications separately from endogenous price/book response",
            limits="Declared publication is not ingestion. D/D1/D3 remain original targets. Shared sources are not independent votes.",
            evidence="EXTERNAL_CONTEXT_INDEX.npz + EXTERNAL_ORIGINAL_ROWS.jsonl.gz + original source packet"))
    csvwrite(out/"EXTERNAL_POINT_APPLICATION.csv",external_points)
    dump(out/"EXTERNAL_SERIES_ORDER.json",[{"index":i,"name":s["name"],"table":s["table"],"column":s["column"],"where":s.get("where")} for i,s in enumerate(series)])
    csvwrite(out/"TRADE_CONDITION_CELLS.csv",cells)
    dump(out/"CASES.json",cases)
    dump(out/"SUMMARY.json",dict(days=summaries,total_trades=sum(x["trades"] for x in summaries),
        total_trade_phases=sum(x["trade_phases"] for x in summaries),external_series=len(series),external_points=len(bindings),
        external_contexts=len(usedcontexts),external_original_rows=len(extrows),case_selection_count=len(cases),
        input_freeze="e7b1c4acac2e37205cdb9ce1c53829b6ca30f4ee",code_revision=CODE,
        scope="All saved trades/pressure events/family rows from completed four-date studies. Existing full-path sources retained. No raw producer rerun.",
        limits=["Causal identification and executable profit not established.","Some dates have partial retained session coverage.",
                "Phase targets are evaluation coordinates, not an imposed predictor lock-time grid.",
                "Unavailable phases retain source pointers and availability=false; their values must not be treated as measured target-time states.",
                "No new FIFO reconstruction; full depth totals/near queues and existing order effects retained.",
                "External publication, observation target and ingestion remain distinct.","Broader field/visual interpretation backlog is not declared complete."]))
    dump(out/"FAMILY_SOURCES.json",family_summaries)
    # Verify every written clock/index column remains exact integer in Arrow, recursively.
    bad=[]
    def check(field,path):
        if (field.name.endswith("_ns") or field.name.endswith("_cursor")) and not(pa.types.is_integer(field.type) or pa.types.is_null(field.type)):
            bad.append(path+"."+field.name+":"+str(field.type))
        if pa.types.is_struct(field.type):
            for c in field.type:check(c,path+"."+field.name)
        if pa.types.is_list(field.type) and pa.types.is_struct(field.type.value_type):
            for c in field.type.value_type:check(c,path+"."+field.name+"[]")
    for p in out.glob("*.parquet"):
        if "family-environments" in p.name:continue # original CSV strings, deliberately preserved
        for field in pq.read_schema(p):check(field,p.name)
    assert not bad,bad
    dump(out/"VERIFICATION.json",dict(original_integer_clocks="passed",strict_pre_source_order="passed",
        per_trade_phase_conservation="passed",pressure_three_horizon_conservation="passed",source_hashes="passed",
        full_populations_not_selected_cases=True,no_producer_rerun=True,no_other_new_report_read=True))
    dump(out/"INPUT_READS.json",READS)
    manifest=[]
    for p in sorted(out.iterdir()):
        b=p.read_bytes();assert len(b)<95_000_000,(p.name,len(b))
        manifest.append(dict(path=p.name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    dump(out/"MANIFEST.json",manifest)
if __name__=="__main__":main(sys.argv[1])
