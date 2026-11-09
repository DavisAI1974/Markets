"""Audit original individual records and add whole-parent lifecycle navigation."""
import argparse,collections,gzip,io,json,os,pathlib,tempfile
from decimal import Decimal
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from finish_family_replication import get,jsonwrite,seal,READS,NREV,SNAP,BASE
from event_common import Context,records,NS
AREV="87dc338f2e74646eb731b3cd6f8968a5a0a653e2"
AROOT=BASE+"/combined-events/run-42571551209-1"
def csvbytes(raw,gz=False):
    return pd.read_csv(io.BytesIO(gzip.decompress(raw) if gz else raw),dtype=str,keep_default_na=False)
def integer(x):
    return int(Decimal(str(x))) if str(x) not in ("","nan","None") else None
def parentid(day,cid,kind):return f"{day}:{cid}:{kind}"
class Inputs:
    def __init__(self,day):
        self.day=day
        self.man=json.loads(get("markets-data",NREV,SNAP+"/MANIFEST.json"))
        self.cache={}
    def raw(self,s):
        if s not in self.cache:
            e=next(e for e in self.man["entries"] if e["source"]==s)
            self.cache[s]=get("markets-data",NREV,e["path"],e["sha256"])
            assert len(self.cache[s])==e["bytes"]
        return self.cache[s]
    def table(self,suffix):
        return csvbytes(self.raw(f"agent-pass/tables/{self.day}-{suffix}"),suffix.endswith(".gz"))
    def combined(self,name):
        m=json.loads(get("markets-data",AREV,AROOT+f"/events-{self.day}/MANIFEST.json"))
        e=next(e for e in m["files"] if e["path"]==name+".parquet")
        return pq.read_table(io.BytesIO(get("markets-data",AREV,AROOT+f"/events-{self.day}/"+e["path"],e["sha256"]))).to_pylist()

def run(day,out):
    out.mkdir(parents=True,exist_ok=True);I=Inputs(day)
    C=I.table("candidate-operands.csv");M=I.table("path-members.csv")
    L=I.table("life-measurements.csv");LP=I.table("life-paths.csv.gz");X=I.table("paths.csv.gz")
    F=csvbytes(I.raw(f"agent-pass/cache/native-flow-{day}.csv.gz"),True)
    sec=F.second.astype("int64").to_numpy()
    assert np.all(np.diff(sec)==1)
    ratio=pd.to_numeric(F.ratio,errors="coerce").to_numpy()
    ids=set(C.candidate_id);assert len(ids)==len(C)
    candidates={r["candidate_id"]:r for r in C.to_dict("records")}
    members={(r["candidate_id"],r["kind"]):r for r in M.to_dict("records")}
    measures={(r["candidate_id"],r["kind"]):r for r in L.to_dict("records")}
    assert len(members)==len(M) and len(measures)==len(L)
    assert set(measures)==set(members)
    lpgroup={k:g for k,g in LP.groupby(["candidate_id","kind"],sort=False)}
    xgroup={k:g for k,g in X.groupby(["candidate_id","kind"],sort=False)}
    assert set(xgroup)==set(members) and set(lpgroup)<=set(measures)
    for cid,kind in members:assert cid in ids and kind in ("candidate","control1","control2")
    for cid in ids:
        assert (cid,"control1") in members if (cid,"candidate") in members else (cid,"control1") not in members
        assert (cid,"control2") in members if (cid,"candidate") in members else (cid,"control2") not in members
    catalog=[]
    for e in I.man["entries"]:
        if not e["source"].startswith(f"agent-pass/tables/{day}-"):continue
        frame=csvbytes(I.raw(e["source"]),e["source"].endswith(".gz"))
        n=0
        for col in ("candidate_id","left_candidate","right_candidate"):
            if col in frame:
                values=set(frame[col])-{""}
                assert values<=ids,(e["source"],col,values-ids)
                n+=int((frame[col]!="").sum())
        catalog.append(dict(source_revision=NREV,source_path=e["path"],sha256=e["sha256"],bytes=e["bytes"],rows=len(frame),
            candidate_references_checked=n,original_fields=list(frame.columns)))
    dip=I.combined("a-dipole-clocks");dmap={r["candidate_id"]:r for r in dip}
    assert set(dmap)==ids
    whole=[];points=[];windows=[];exceptions=[]
    with tempfile.TemporaryDirectory() as tmp:
        ctx=Context(day,out,pathlib.Path(tmp))
        flow=[]
        for i,r in enumerate(F.to_dict("records")):
            s=int(r["second"]);a=int(np.searchsorted(ctx.t,s*NS));b=int(np.searchsorted(ctx.t,(s+1)*NS))
            k=b if b<len(ctx.t) else None
            flow.append(dict(second=s,label_ns=s*NS,
                native_buy=float(r["buy"]),native_sell=float(r["sell"]),native_unknown=float(r["unknown"]),
                native_roll_buy=float(r["roll_buy"]),native_roll_sell=float(r["roll_sell"]),
                native_total=float(r["total"]),native_ratio=float(r["ratio"]) if r["ratio"] else None,
                first_source_group=a if a<b else None,last_source_group=b-1 if a<b else None,
                first_source_cursor=int(ctx.g.first_cursor.iloc[a]) if a<b else None,
                last_source_cursor=int(ctx.c[b-1]) if a<b else None,
                completed_second_known_by_ns=int(ctx.t[k]) if k is not None else None,
                completion_group=k,completion_cursor=int(ctx.c[k]) if k is not None else None))
        keys=list(members)+[(cid,"candidate") for cid in C.candidate_id if (cid,"candidate") not in members]
        for cid,kind in keys:
            m=members.get((cid,kind));d=dmap[cid];c=candidates[cid]
            anchor=integer(m["anchor_ns"]) if m else int(c["birth_second"])*NS
            i=anchor//NS-int(sec[0]);inrange=0<=i<len(sec)
            p=np.sign(ratio[i]) if inrange and np.isfinite(ratio[i]) else 0
            stop=None;disp="outside_native_flow_coverage"
            if inrange:
                opposite=np.isfinite(ratio[i+1:])&(np.sign(ratio[i+1:])==-p) if p else np.zeros(len(sec)-i-1,bool)
                hits=np.flatnonzero(opposite[:-2]&opposite[1:-1]&opposite[2:]) if len(opposite)>=3 else []
                stop=i if not p else i+int(hits[0])+3 if len(hits) else len(sec)-1
                disp="undefined_anchor_direction" if not p else "opposite_hold3" if len(hits) else "right_censored"
            lr=measures.get((cid,kind))
            if lr:
                assert lr["disposition"]==disp
                assert integer(lr["life_end_second"])==(int(sec[stop]) if stop is not None else None)
                g=lpgroup.get((cid,kind))
                expected=0 if stop is None else stop-i
                assert (len(g) if g is not None else 0)==expected
                if g is not None:
                    assert g.second.astype("int64").tolist()==sec[i+1:stop+1].tolist()
                    for field,array in (("ratio",ratio),("net",pd.to_numeric(F.roll_buy).to_numpy()-pd.to_numeric(F.roll_sell).to_numpy()),("total",pd.to_numeric(F.total).to_numpy())):
                        assert np.allclose(pd.to_numeric(g[field],errors="coerce"),array[i+1:stop+1],equal_nan=True,rtol=0,atol=1e-12)
            else:
                assert kind=="candidate" and not d["live_recognition"]
                exceptions.append(dict(parent_id=parentid(day,cid,kind),correction="Added full original-flow path for finalization-only candidate; no live recognition invented."))
            pid=parentid(day,cid,kind)
            end=int(sec[stop])*NS if stop is not None else None
            rec=d["recognition_ns"] if kind=="candidate" else None
            whole.append(dict(parent_id=pid,day=day,candidate_id=cid,kind=kind,orientation=c["orientation"],polarity=int(c["polarity"]),
                anchor_label_ns=anchor,lifecycle_start_second=int(sec[i]) if inrange else None,
                lifecycle_end_label_ns=end,endpoint_definition=disp,
                lifetime_rule="First third consecutive opposite native-flow second; observational convention, not natural death",
                recognition_ns=rec,recognition_clocks=d["recognition_clocks"] if kind=="candidate" else None,
                candidate_recognition_reference_ns=d["recognition_ns"],live_recognition=d["live_recognition"] if kind=="candidate" else None,
                lifecycle_end_known_by_ns=flow[stop]["completed_second_known_by_ns"] if stop is not None else None,
                lifecycle_start_known_by_ns=flow[i]["completed_second_known_by_ns"] if inrange else None,
                point_count=stop-i+1 if stop is not None else 0,complete_original_second_sequence=True,
                source_revision=NREV,flow_source=f"{SNAP}/agent-pass/cache/native-flow-{day}.csv.gz",
                clock_source_revision=ctx.source_rev,clock_source_path=ctx.source_path,
                missing_live_recognition=kind=="candidate" and not d["live_recognition"],
                original_lifecycle_present=lr is not None))
            if stop is not None:
                for j in range(i,stop+1):
                    points.append(dict(parent_id=pid,candidate_id=cid,kind=kind,point_ordinal=j-i,
                        relative_second=j-i,**flow[j]))
            if m:
                x=xgroup[(cid,kind)];cuts=x.cut_ns.map(integer).tolist()
                assert len(x)==int(m["path_rows"]) and len(cuts)==len(set(cuts))
                assert cuts==sorted(cuts)
                # Every original sampled point retains its own source cursor; validate against source groups.
                for row,cut in zip(x.to_dict("records"),cuts):
                    gi=int(np.searchsorted(ctx.t,cut,side="right"))-1
                    assert gi>=0 and int(row["cursor"])==ctx.c[gi]
                assert 0.0 in x.relative_s.astype(float).tolist()
                windows.append(dict(parent_id=pid,candidate_id=cid,kind=kind,
                    component="original_birth_context_to_recognition_sample_window",
                    first_cut_ns=cuts[0],last_cut_ns=cuts[-1],anchor_ns=anchor,
                    source_rows=len(x),source_revision=NREV,source_path=f"{SNAP}/agent-pass/tables/{day}-paths.csv.gz",
                    row_selector=f"candidate_id={cid};kind={kind}",
                    starts_before_lifecycle=cuts[0]<anchor,extends_beyond_lifecycle=end is not None and cuts[-1]>end,
                    whole_parent_kept=True,clock_semantics="cut_ns sampling cut; cursor selects completed source group; ratio uses previous completed group-classified second"))
        # Whole trade legs and quote episodes must retain all their own members and endpoints.
        trades=I.combined("a-trades");stretches=I.combined("a-price-stretches");legs=I.combined("a-print-legs")
        assert len(trades)==len(ctx.trades)
        assert [r["source_ordinal"] for r in trades]==list(range(len(trades)))
        covered=[]
        for s in stretches:
            lo,hi=s["first_trade_ordinal"],s["last_trade_ordinal"]
            covered.extend(range(lo,hi+1))
            assert all(trades[j]["stretch_id"]==s["stretch_ordinal"] for j in range(lo,hi+1))
        assert covered==list(range(len(trades)))
        for l in legs:
            lo,hi=l["first_trade"],l["last_trade"]
            assert l["first_clocks"]["trade_input_cursor"]==trades[lo]["trade_input_cursor"]
            assert l["last_clocks"]["trade_input_cursor"]==trades[hi]["trade_input_cursor"]
            assert l["duration_receive_ns"]==trades[hi]["receive_ns"]-trades[lo]["receive_ns"]
        signals=I.combined("b-signals");episodes=I.combined("b-quote-episodes");outcomes=I.combined("b-delayed-outcomes")
        sids={r["event_id"] for r in signals};assert len(sids)==len(signals)
        assert all(r["event_id"] in sids for r in episodes+outcomes)
        counts=collections.Counter(r["event_id"] for r in outcomes)
        assert set(counts)==sids and set(counts.values())=={3}
        overlaps=I.combined("a-trade-dipole-overlaps")
        assert all(r["candidate_id"] in ids and 0<=r["trade_ordinal"]<len(trades) for r in overlaps)
        for r in overlaps:
            t=trades[r["trade_ordinal"]]
            assert (r["trade_cursor"],r["trade_event_ns"],r["trade_receive_ns"],r["trade_known_by_ns"])==(t["trade_input_cursor"],t["event_ns"],t["receive_ns"],t["available_ns"])
        records(out/"whole-lifecycles.parquet",whole);records(out/"whole-lifecycle-points.parquet",points)
        records(out/"component-windows.parquet",windows);records(out/"native-flow-source-clocks.parquet",flow)
        jsonwrite(out/"individual-table-catalog.json",catalog)
        jsonwrite(out/"audit.json",dict(day=day,status="passed",candidates=len(C),whole_parents=len(whole),
            candidate_parents=sum(r["kind"]=="candidate" for r in whole),control_parents=sum(r["kind"]!="candidate" for r in whole),
            whole_path_points=len(points),component_windows=len(windows),individual_tables_checked=len(catalog),
            candidate_table_references_checked=sum(r["candidate_references_checked"] for r in catalog),
            trades=len(trades),stretches=len(stretches),legs=len(legs),pressure_signals=len(signals),
            quote_episodes=len(episodes),outcome_children=len(outcomes),trade_dipole_links=len(overlaps),
            corrections=exceptions,anchor_points_added=sum(r["point_count"]>0 for r in whole),
            checks=["Original life endpoints reproduced","Every original lifecycle second retained in order",
            "Original values verified; undefined seconds kept","Anchor points included in whole path",
            "Every sampled window retains parent ID and original cut/cursor",
            "All candidate table references resolve","Trade/stretch/leg membership and whole endpoints verified",
            "Pressure outcomes resolve to their signal parents","Trade/dipole IDs and four source clocks agree"],
            limits=["The three-opposite-second rule is an explicit research endpoint, not established natural death.",
            "Control instances are separate parents tied to their candidate; no invented control detector recognition.",
            "Sample windows can extend outside a lifecycle and are labelled context, never replacements for the whole.",
            "Finalization-only candidate lifecycles recovered from original flow; actual recognition stays absent."]))
    jsonwrite(out/"input-manifest.json",READS);seal(out)
    print((out/"audit.json").read_text(),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",required=True,type=pathlib.Path);a=p.parse_args();run(a.day,a.output)
