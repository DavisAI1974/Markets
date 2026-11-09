"""Link preserved event populations and summarize their joint conditions."""
import collections,json
import numpy as np
import pyarrow.parquet as pq
from event_common import NS,records

def side_relation(sign,direction):
    return "flat" if sign==0 else "aligned" if sign==direction else "opposed"

def run(ctx):
    root=ctx.out
    signals=pq.read_table(root/"b-signals.parquet").to_pylist()
    outcomes=pq.read_table(root/"b-delayed-outcomes.parquet").to_pylist()
    dipoles=pq.read_table(root/"a-dipole-clocks.parquet").to_pylist()
    trades=pq.read_table(root/"a-trades.parquet").to_pylist()
    import pandas as pd
    occurrences=pd.read_csv(root/"a-all-family-occurrences.csv.gz",dtype={"family_id":str})
    assert occurrences.source_ordinal.tolist()==list(range(len(ctx.g)))
    family_ids=occurrences.family_id.tolist()
    prior_counts=collections.Counter();occurrence_number=[]
    for fid in family_ids:prior_counts[fid]+=1;occurrence_number.append(prior_counts[fid])
    available=sorted([d for d in dipoles if d["live_recognition"]],key=lambda d:(d["recognition_ns"],d["recognition_clocks"]["close_cursor"]))
    clocks=np.array([d["recognition_ns"] for d in available],np.int64)
    cursors=np.array([d["recognition_clocks"]["close_cursor"] for d in available],np.int64)
    trade_known=np.array([t["available_ns"] for t in trades],np.int64)
    trade_cursors=np.array([t["group_close_input_cursor"] for t in trades],np.int64)
    linked=[];byid={}
    for s in signals:
        j=s["signal_group"];t=int(ctx.t[j]);cursor=int(ctx.c[j]);direction=1 if s["side"]=="A" else -1
        k=min(int(np.searchsorted(clocks,t,side="right"))-1,int(np.searchsorted(cursors,cursor,side="right"))-1)
        d=available[k] if k>=0 else None
        tx=min(int(np.searchsorted(trade_known,t,side="right"))-1,int(np.searchsorted(trade_cursors,cursor,side="right"))-1)
        b=int(ctx.g.bid_size.iloc[j]);a=int(ctx.g.ask_size.iloc[j]);book_sign=int(np.sign(b-a))
        fresh=s["flow1_buy_lots"]-s["flow1_sell_lots"]
        total=s["flow1_buy_lots"]+s["flow1_sell_lots"]
        flow=side_relation(int(np.sign(fresh)),direction) if s["flow1_complete_history"] and total else "undefined"
        row=dict(event_id=s["event_id"],event_type=s["event_type"],side=s["side"],group=j,
            signal_event_ns=s["signal_clocks"]["event_ns"],signal_receive_ns=s["signal_clocks"]["receive_ns"],
            signal_known_by_ns=t,signal_cursor=cursor,
            structural_family_at_group=family_ids[j],observed_family_occurrence_number=occurrence_number[j],
            latest_recognized_dipole_id=d["candidate_id"] if d else None,
            latest_dipole_recognition_ns=d["recognition_ns"] if d else None,
            latest_dipole_recognition_cursor=d["recognition_clocks"]["close_cursor"] if d else None,
            dipole_recognition_age_ns=t-d["recognition_ns"] if d else None,
            dipole_selection="latest actually recognized by signal; no future lifetime filter",
            latest_known_trade_ordinal=tx if tx>=0 else None,
            retrospective_print_leg_ids=trades[tx]["overlapping_leg_ids"] if tx>=0 else [],
            leg_ids_use="retrospective navigation only; final leg endpoints are not signal inputs",
            fresh_wire_flow_vs_signal=flow,displayed_touch_vs_signal=side_relation(book_sign,direction),
            prior_print_gap_trend=s["all_gap_trend"],
            fresh_buy_lots=s["flow1_buy_lots"],fresh_sell_lots=s["flow1_sell_lots"],fresh_unknown_lots=s["flow1_unknown_lots"],
            rolling20_buy_lots=s["flow20_buy_lots"],rolling20_sell_lots=s["flow20_sell_lots"],
            current_group_no_print=not s["fresh_group_print_count"])
        if d:assert d["recognition_ns"]<=t and d["recognition_clocks"]["close_cursor"]<=cursor
        linked.append(row);byid[s["event_id"]]=row
    counts=collections.defaultdict(collections.Counter)
    keys=("event_type","side","fresh_wire_flow_vs_signal","displayed_touch_vs_signal","prior_print_gap_trend")
    for o in outcomes:
        s=byid[o["event_id"]];key=tuple(s[k] for k in keys)+(o["horizon_s"],)
        c=counts[key];c["scenarios"]+=1;c[o["disposition"]]+=1
        if o["disposition"]=="observed":
            for field in ("signed_midpoint_change_twice_raw","spread_crossing_raw"):
                v=o[field];c[field+("_positive" if v>0 else "_negative" if v<0 else "_flat")]+=1
    cells=[dict(zip(keys+("horizon_s",),key),**c) for key,c in sorted(counts.items())]
    assert sum(r["scenarios"] for r in cells)==len(outcomes)==3*len(signals)
    records(root/"cross-study-event-links.parquet",linked)
    records(root/"cross-study-condition-outcomes.parquet",cells)
    return dict(linked_signals=len(linked),condition_cells=len(cells),
        conditioned_outcomes=len(outcomes),denominator_conservation="passed",
        meaning="Descriptive joint cells on separate event populations; counts retain failed/flat/censored cases, no causal or independent-trial claim")
