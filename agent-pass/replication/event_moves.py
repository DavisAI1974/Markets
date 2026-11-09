"""Study C: original order evidence, large moves, first recovery and joint context."""
import collections,json
import numpy as np
import pandas as pd
from event_common import NS,TICK,BASE,MREV,source_file,records
from finish_family_replication import get

def first_recovery(times,mid,start,end,direction):
    baseline=int(mid[start-1]);limit=min(end,int(np.searchsorted(times,int(times[start])+5*NS,side="right"))-1)
    x=direction*(mid[start:limit+1]-baseline)
    extreme=start+int(np.argmax(x));distance=int(direction*(mid[extreme]-baseline))
    rest=direction*(mid[extreme:end+1]-baseline)
    half=np.flatnonzero(2*rest<=distance);full=np.flatnonzero(rest<=0)
    return extreme,(extreme+int(half[0]) if len(half) else None),(extreme+int(full[0]) if len(full) else None)

def tests():
    t=np.array([0,1,2,3,4,5])*NS;m=np.array([100,96,94,97,100,101])
    assert first_recovery(t,m,1,5,-1)==(2,3,4)
    assert first_recovery(t,m,1,2,-1)==(2,None,None)
    print("PASS: first extreme, half/full recovery, censored recovery",flush=True)

def study(ctx):
    tests();g=ctx.g;n=len(g)
    moves=[j for j in range(1,n) if ctx.valid[j] and ctx.seg[j]==ctx.seg[j-1] and abs(int(ctx.mid[j]-ctx.mid[j-1]))>=4*TICK]
    events=[];links=[];selected=set();counts=collections.Counter()
    signals=ctx.b_signals;episodes=ctx.b_episodes
    signal_times=np.array([int(r["signal_clocks"]["known_by_ns"]) for r in signals],np.int64)
    order=np.argsort(signal_times,kind="stable");signal_times=signal_times[order]
    last_disjoint=-10**30
    for j in moves:
        t=int(ctx.t[j]);direction=int(np.sign(ctx.mid[j]-ctx.mid[j-1]));ident=f"{ctx.day}:large_quote:{j}"
        disjoint=t>=last_disjoint+20*NS
        if disjoint:last_disjoint=t
        row=dict(event_id=ident,event_type="large_quote_move",prior_clocks=ctx.point(j-1),move_clocks=ctx.point(j),
            direction=direction,move_half_ticks=int((ctx.mid[j]-ctx.mid[j-1])//TICK),
            first_disjoint_20s=disjoint,print_count=int(g.print_count.iloc[j]),responses=[])
        for h in (1,5,20):
            k,valid=ctx.endpoint(j,t+h*NS);age=t+h*NS-int(ctx.t[k]) if k>=0 else None
            valid=valid and age<=NS
            delta=int(direction*(ctx.mid[k]-ctx.mid[j])) if valid else None
            row["responses"].append(dict(horizon_s=h,target_ns=t+h*NS,endpoint_clocks=ctx.point(k),
                endpoint_age_ns=age,available=bool(valid),signed_change_twice_raw=delta,
                response="with" if delta and delta>0 else "against" if delta and delta<0 else "flat" if valid else "unavailable",
                full_retrace=bool(delta is not None and delta<=-abs(int(ctx.mid[j]-ctx.mid[j-1])))))
            if valid:selected.add(k)
        k=min(int(ctx.end[j]),int(np.searchsorted(ctx.t,t+600*NS,side="right"))-1)
        extreme,half,full=first_recovery(ctx.t,ctx.mid,j,k,direction)
        row.update(extreme_first5s_clocks=ctx.point(extreme),extreme_midpoint_twice_raw=int(ctx.mid[extreme]),
            half_recovery_clocks=ctx.point(half) if half is not None else None,
            full_recovery_clocks=ctx.point(full) if full is not None else None,
            half_recovery_elapsed_ns=int(ctx.t[half]-t) if half is not None else None,
            full_recovery_elapsed_ns=int(ctx.t[full]-t) if full is not None else None,
            recovery_observation_end=ctx.point(k),recovery_window_complete=bool(ctx.t[ctx.end[j]]>=t+600*NS),
            half_not_observed=half is None,full_not_observed=full is None)
        selected.update([j-1,j,extreme,k])
        if half is not None:selected.add(half)
        if full is not None:selected.add(full)
        # Link all prior signals in the 20s window, preserving kinds, sides and lag.
        lo=int(np.searchsorted(signal_times,t-20*NS));hi=int(np.searchsorted(signal_times,t,side="left"))
        for ix in order[lo:hi]:
            s=signals[int(ix)];sj=s["signal_group"]
            if ctx.seg[sj]==ctx.seg[j]:
                links.append(dict(later_event_id=ident,earlier_event_id=s["event_id"],earlier_type=s["event_type"],
                    earlier_side=s["side"],earlier_group=sj,later_group=j,
                    lag_known_by_ns=t-int(ctx.t[sj]),cursor_difference=int(ctx.c[j]-ctx.c[sj]),
                    earlier_signal_direction_agrees=bool((1 if s["side"]=="A" else -1)==direction)))
        events.append(row)
    # Every thin episode's onset/end is included, irrespective of its outcome.
    for e in episodes:
        selected.add(e["onset_group"])
        if e["end_group"] is not None:selected.add(e["end_group"])
    selected_records={};rank_counts=collections.Counter();partcount=0
    for path in ctx.group_files:
        part=pd.read_parquet(path)
        projected=[]
        for r in part.to_dict("records"):
            j=int(r["group_ordinal"])
            if j>0 and ctx.valid[j] and ctx.seg[j]==ctx.seg[j-1]:
                for side,label in (("B","bid"),("A","ask")):
                    rank=json.loads(r[label+"_rank_change_json"])
                    rank_counts[label+"_rank_increase"]+=rank["delta"]>0
                    rank_counts[label+"_rank_increase_without_shared_add"]+=rank["delta"]>0 and rank["shared_price_delta"]<=0
            if j in selected:
                selected_records[j]=r;projected.append(r)
        if projected:records(ctx.out/f"c-selected-book-context-{partcount:02d}.parquet",projected);partcount+=1
    mechanism=[]
    for e in episodes:
        j=e["onset_group"];k=e["end_group"];label="bid" if e["side"]=="B" else "ask"
        start=selected_records[j];end=selected_records.get(k)
        effect=json.loads(end[label+"_old_touch_effect_json"]) if end else None
        mechanism.append(dict(event_id=e["event_id"],side=e["side"],ending=e["ending"],
            onset_group=j,end_group=k,onset_known_by_ns=int(ctx.t[j]),end_known_by_ns=int(ctx.t[k]) if k is not None else None,
            onset_effect=json.loads(start[label+"_new_touch_effect_json"]),ending_old_touch_effect=effect,
            ending_new_touch_effect=json.loads(end[label+"_new_touch_effect_json"]) if end else None,
            ending_fill_linked=bool(effect and effect["fill_linked"]>0),
            ending_unlinked_reduction=bool(effect and effect["unlinked"]>0),
            evidence_scope="source-group actions; terminal mechanism is not a pre-event signal"))
    for event in events:
        j=event["move_clocks"]["group"];start=selected_records[j]
        event["book_context_group"]=j
        event["source_action_group"]=j
        event["side_effects"]={label:{role:json.loads(start[f"{label}_{role}_touch_effect_json"]) for role in ("old","new")} for label in ("bid","ask")}
        event["rank_changes"]={label:json.loads(start[f"{label}_rank_change_json"]) for label in ("bid","ask")}
    # Preserve exact individual action rows for every selected group, without duplicating by event.
    action_count=0
    names=sorted(e["path"] for e in ctx.manifest["files"] if e["path"].startswith("actions-"))
    for i,name in enumerate(names):
        part=pd.read_parquet(source_file(ctx,name));part=part[part.group_ordinal.isin(selected)]
        if len(part):part.to_parquet(ctx.out/f"c-selected-actions-{i:02d}.parquet",index=False);action_count+=len(part)
    ctx.save("c-large-quote-events",events);ctx.save("c-prior-signal-to-large-move",links);ctx.save("c-quote-ending-mechanisms",mechanism)
    if ctx.day=="20231018":assert len(events)==64
    ctx.summary["C"]=dict(large_moves=len(events),prior_signal_links=len(links),quote_ending_mechanisms=len(mechanism),
        selected_book_groups=len(selected_records),individual_selected_actions=action_count,rank_counts=dict(rank_counts),
        full_recoveries_observed=sum(not r["full_not_observed"] for r in events),
        reference_large_move_count="passed" if ctx.day=="20231018" else "same threshold and clock rules",
        scope="All eligible retained groups; historical 375/391 bounded window is not silently substituted for whole-day scope",
        recovery_definition="First5s most displaced midpoint from pre-move quote, then first half/full return within600s; first passage is not event death")
