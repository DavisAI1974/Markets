"""Study A: separate trade, family and dipole clocks linked by source coordinates."""
import gzip,io,json
from decimal import Decimal
import numpy as np
from finish_family_replication import get,jsonwrite,selected_source
from event_common import NS,BASE,MREV,FREV,FROOT,native_table

def study(ctx):
    source=get("Markets",MREV,BASE+"/continue_trade_chronology.py")
    funcs=selected_source(source,{"price_stretches","print_legs"},{})
    stretches,member=funcs["price_stretches"](ctx.tp.tolist())
    legs,legmember=funcs["print_legs"](stretches)
    ts=ctx.trades
    def clock(i):
        r=ts[i]
        return {k:int(r[k]) for k in ("event_ns","receive_ns","available_ns","trade_input_cursor","group_close_input_cursor","group_ordinal")}
    for s in stretches:
        lo,hi=s["first_trade_ordinal"],s["last_trade_ordinal"]
        s.update(day=ctx.day,first_clocks=clock(lo),last_clocks=clock(hi),
            duration_receive_ns=int(ctx.tt[hi]-ctx.tt[lo]),duration_event_ns=int(ts[hi]["event_ns"]-ts[lo]["event_ns"]),
            next_different_trade=hi+1 if hi+1<len(ts) else None,
            overlapping_leg_ids=legmember[s["stretch_ordinal"]])
    for l in legs:
        lo=stretches[l["first_stretch_ordinal"]]["first_trade_ordinal"]
        hi=stretches[l["last_stretch_ordinal"]]["last_trade_ordinal"]
        l.update(day=ctx.day,first_trade=lo,last_trade=hi,first_clocks=clock(lo),last_clocks=clock(hi),
                 duration_receive_ns=int(ctx.tt[hi]-ctx.tt[lo]),
                 duration_event_ns=int(ts[hi]["event_ns"]-ts[lo]["event_ns"]),
                 raw_price_change=int(ctx.tp[hi]-ctx.tp[lo]),left_boundary=lo==0,right_boundary=hi==len(ts)-1,
                 endpoint="observed same-sign print-step leg; not natural event death")
    annotated=[]
    for i,t in enumerate(ts):
        j=ctx.prior(int(t["receive_ns"]),int(t["trade_input_cursor"])-1)
        s=member[i]
        annotated.append(dict(t,stretch_id=s,overlapping_leg_ids=legmember[s],
            strict_prior_group=j if j>=0 else None,strict_prior_clocks=ctx.point(j),
            print_step_raw=int(ctx.tp[i]-ctx.tp[i-1]) if i else None,
            receive_gap_ns=int(ctx.tt[i]-ctx.tt[i-1]) if i else None,
            event_gap_ns=int(t["event_ns"]-ts[i-1]["event_ns"]) if i else None))
    ctx.save("a-trades",annotated);ctx.save("a-price-stretches",stretches);ctx.save("a-print-legs",legs)
    if ctx.day=="20231018":
        assert (len(ts),len(stretches),len(legs))==(30739,9109,5120)
    families=json.loads(get("markets-data",FREV,FROOT+f"/{ctx.day}/family-starts.json"))
    ft=np.array([f["start_recv_ns"] for f in families],np.int64)
    neighbors=[];windows=[]
    horizons=(1,5,20,60,120,300,600,1800,3600)
    for ix,f in enumerate(families):
        t=f["start_recv_ns"];cap=f["cursor_cap"];j=ctx.prior(t,cap)
        for n in range(int(np.searchsorted(ft,t-3600*NS)),int(np.searchsorted(ft,t+3600*NS,side="right"))):
            if n!=ix:neighbors.append(dict(family_id=f["family_id"],neighbor_family_id=families[n]["family_id"],
                receive_delta_ns=int(ft[n]-t),within120=abs(int(ft[n]-t))<=120*NS,within600=abs(int(ft[n]-t))<=600*NS))
        for anchor_shift in (-600,0,600):
            at=t+anchor_shift*NS
            aj=ctx.prior(at,cap) if anchor_shift==0 else int(np.searchsorted(ctx.t,at,side="left"))-1
            tx=int(np.searchsorted(ctx.tt,at,side="left"))-1
            for h in horizons:
                end=at+h*NS;k,valid=ctx.endpoint(aj,end)
                te=int(np.searchsorted(ctx.tt,end,side="right"))-1
                trade_ok=tx>=0 and te>=tx and te<len(ts) and valid and ctx.seg[int(ts[tx]["group_ordinal"])]==ctx.seg[aj] and ctx.seg[int(ts[te]["group_ordinal"])]==ctx.seg[aj]
                windows.append(dict(family_id=f["family_id"],family_start_receive_ns=t,anchor_shift_s=anchor_shift,
                    anchor_ns=at,horizon_s=h,target_ns=end,anchor_group=aj,anchor_clocks=ctx.point(aj),
                    endpoint_group=k,endpoint_clocks=ctx.point(k),
                    midpoint_available=bool(valid),midpoint_change_twice_raw=int(ctx.mid[k]-ctx.mid[aj]) if valid else None,
                    anchor_quote_age_ns=at-int(ctx.t[aj]) if aj>=0 else None,
                    endpoint_quote_age_ns=end-int(ctx.t[k]) if k>=0 else None,
                    prior_trade=tx if tx>=0 else None,endpoint_trade=te if te>=0 else None,
                    transaction_available=bool(trade_ok),transaction_change_raw=int(ctx.tp[te]-ctx.tp[tx]) if trade_ok else None,
                    transaction_anchor_age_ns=at-int(ctx.tt[tx]) if tx>=0 else None,
                    transaction_endpoint_age_ns=end-int(ctx.tt[te]) if te>=0 else None,
                    trade_and_quote_fresh5s=bool(trade_ok and at-ctx.tt[tx]<=5*NS and end-ctx.tt[te]<=5*NS and at-ctx.t[aj]<=5*NS and end-ctx.t[k]<=5*NS)))
    pre=[]
    for f in families:
        t=f["start_recv_ns"];j=ctx.prior(t,f["cursor_cap"])
        for h in (120,300,600):
            k=ctx.prior(t-h*NS,f["cursor_cap"])
            valid=j>=0 and k>=0 and ctx.valid[j] and ctx.seg[k]==ctx.seg[j]
            pre.append(dict(family_id=f["family_id"],start_ns=t,lookback_s=h,prior_clocks=ctx.point(k),last_pre_clocks=ctx.point(j),
                available=bool(valid),midpoint_change_twice_raw=int(ctx.mid[j]-ctx.mid[k]) if valid else None))
    ctx.save("a-family-firsts",[{k:(None if k=="pre_input_cursor" and v=="" else v) for k,v in f.items() if k!="descriptor"} for f in families])
    ctx.save("a-family-neighbors",neighbors);ctx.save("a-family-windows",windows);ctx.save("a-family-prechanges",pre)
    # Full occurrence ledger is preserved as its own input, not collapsed to starts.
    raw=get("markets-data",FREV,FROOT+f"/{ctx.day}/all-family-occurrences.csv.gz")
    (ctx.out/"a-all-family-occurrences.csv.gz").write_bytes(raw)
    candidates=native_table(ctx.day,"candidate-operands.csv").to_dict("records")
    life={r["candidate_id"]:r for r in native_table(ctx.day,"life-measurements.csv").to_dict("records") if r["kind"]=="candidate"}
    path=BASE+("/october18-candidate-inputs.jsonl.gz" if ctx.day=="20231018" else f"/replay-comparison/{ctx.day}/candidate-inputs.jsonl.gz")
    archived={c["candidate_id"]:c for c in map(json.loads,gzip.decompress(get("Markets",MREV,path)).splitlines())}
    assert set(archived)=={r["candidate_id"] for r in candidates}
    dipoles=[];links=[]
    for r in candidates:
        cid=r["candidate_id"];birth=int(r["birth_second"])*NS
        c=archived[cid];rg=c["recognition_group"]
        recognition=c.get("recognition_receive_ns") if rg is not None else None
        live=rg is not None
        # Finalization-only is determined by original export, never by nominal clock.
        if cid in ("dip-19633-1696366763","dip-19647-1697576378"):recognition=None;live=False
        end=int(Decimal(life[cid]["life_end_second"])*NS) if life[cid]["life_end_second"] else None
        if live:assert rg<len(ctx.t) and ctx.t[rg]==recognition and ctx.c[rg]==c["recognition_cursor"]
        dipoles.append(dict(candidate_id=cid,birth_label_ns=birth,recognition_ns=recognition,
            recognition_clocks=ctx.point(rg) if live else None,live_recognition=live,
            lifetime_end_label_ns=end,lifetime_end_definition=life[cid]["disposition"],
            end_label_is_not_full_path_availability=True,orientation=r["orientation"],polarity=int(r["polarity"])))
        if end is not None:
            lo=int(np.searchsorted(ctx.tt,birth,side="left"));hi=int(np.searchsorted(ctx.tt,end,side="right"))
            for ti in range(lo,hi):
                t=ts[ti]
                links.append(dict(candidate_id=cid,trade_ordinal=int(t["source_ordinal"]),
                    trade_event_ns=int(t["event_ns"]),trade_receive_ns=int(t["receive_ns"]),
                    trade_known_by_ns=int(t["available_ns"]),trade_cursor=int(t["trade_input_cursor"]),
                    birth_label_ns=birth,recognition_ns=recognition,lifetime_end_label_ns=end,
                    recognition_before_trade=bool(live and recognition<t["receive_ns"] and ctx.c[rg]<t["trade_input_cursor"]),
                    overlap_basis="retrospective lifetime labels; not online selection"))
    ctx.save("a-dipole-clocks",dipoles);ctx.save("a-trade-dipole-overlaps",links)
    ctx.summary["A"]=dict(trades=len(ts),stretches=len(stretches),legs=len(legs),families=len(families),
        family_windows=len(windows),family_neighbor_links=len(neighbors),dipoles=len(dipoles),trade_dipole_links=len(links),
        reference_chronology_counts="passed" if ctx.day=="20231018" else "same original functions",
        external_layers="deferred",full_path_availability="not inferred from nominal lifetime endpoint")

def tests():
    source=b'def f():\n    return 1\n'
    assert selected_source(source,{"f"},{})["f"]()==1
