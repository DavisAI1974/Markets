"""Attach immutable per-instance records, clock grids and informational context."""
import argparse,collections,gzip,hashlib,io,json,os,pathlib
from decimal import Decimal
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from link_io import fetch,js,csvdata,parquet,writejson,selector,READS,parent_key
from external import build
D="DavisAI1974/markets-data";C="DavisAI1974/Markets"
ROOT="tasks/family-research-20261022"
RREV="b1123a72115a0fb65cdcde74ba5450e0d40adb68"
RP=ROOT+"/claude-lifecycle-renders/run-42581055248-1"
WREV="9e3365f76fb4d34d97eb193d35072aae5f51b709"
WP=ROOT+"/whole-lifecycles/run-42573465249-1"
NREV="0487d83b1ddb1abe5e4cfae12e8b88797801f428"
NP=ROOT+"/native-dipole/20261108-33693e180/agent-pass"
EREV="87dc338f2e74646eb731b3cd6f8968a5a0a653e2"
EP=ROOT+"/combined-events/run-42571551209-1"
BREV="25e13a8d204f0ce77acfbe22b303f290d7202d10"
BP=ROOT+"/dipole-render-books/run-42574533079-1"
CREV="2dd97a608f2429b7e5674c669674a9d8474a018c"
CP=ROOT+"/claude-pass-3day"
def integer(v):
    if v is None or v in ("","nan","NaN"):return None
    d=Decimal(str(v))
    assert d==d.to_integral_value(),v
    return int(d)
def grouped(rows,key):
    out=collections.defaultdict(list)
    for i,r in enumerate(rows):out[r.get(key)].append(dict(source_row=i,row=r))
    return out
def clock(pub,field,ns,role):
    assert isinstance(ns,int)
    return dict(field=field,ns=ns,role=role,external_context_index=int(np.searchsorted(pub,ns,side="right")))
def run(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    pub,layers=build(out/"external")
    summaries=[];layer_fields=collections.defaultdict(set)
    for day in ("20231002","20231003","20231017","20231018"):
        print("link",day,flush=True)
        dest=out/day;dest.mkdir(exist_ok=True)
        renders=js(D,RREV,f"{RP}/{day}/INDEX.json")
        wp=f"{WP}/audit-{day}";ep=f"{EP}/events-{day}"
        parents=parquet(D,WREV,wp+"/whole-lifecycles.parquet").to_pylist()
        byparent={p["parent_id"]:p for p in parents};bycandidate=grouped(parents,"candidate_id")
        components=grouped(parquet(D,WREV,wp+"/component-windows.parquet").to_pylist(),"candidate_id")
        native_clocks=parquet(D,WREV,wp+"/native-flow-source-clocks.parquet")
        source_sec=native_clocks["second"].to_numpy()
        source_known=np.array([x if x is not None else -1 for x in native_clocks["completed_second_known_by_ns"].to_pylist()],dtype=np.int64)
        detector=grouped(csvdata(D,NREV,f"{NP}/tables/{day}-detector-all-comparisons.csv"),"candidate_id")
        ledgerpath=CP+f"/crossday/detector/ledger_recorded_births_{day}.csv"
        ledger=grouped(csvdata(C,CREV,ledgerpath),"candidate_id")
        firstpath=CP+f"/tables/dipole/{day}/x07_first_events.csv"
        first=grouped(csvdata(C,CREV,firstpath),"row")
        nearest=grouped(csvdata(D,NREV,f"{NP}/tables/{day}-detector-free-nearest.csv"),"candidate_id")
        catalog=js(D,WREV,wp+"/individual-table-catalog.json")
        books=js(D,BREV,f"{BP}/render-{day}/lifecycle-render-index.json")
        if isinstance(books,dict):books=books["pages"]
        bookby=grouped(books,"candidate_id")
        eventclocks=grouped(parquet(D,EREV,ep+"/a-dipole-clocks.parquet").to_pylist(),"candidate_id")
        signals=parquet(D,EREV,ep+"/cross-study-event-links.parquet")
        trades=parquet(D,EREV,ep+"/a-trade-dipole-overlaps.parquet")
        signal_counts=collections.Counter(signals["latest_recognized_dipole_id"].to_pylist())
        trade_counts=collections.Counter(trades["candidate_id"].to_pylist())
        # Every event carries its own original clocks and identifiers. Null/unmatched references stay null.
        for name,table,col in [("signal-links",signals,"latest_recognized_dipole_id"),("trade-links",trades,"candidate_id")]:
            ids=table[col].to_pylist()
            parent_ids=[parent_key(day,cid) if cid is not None and parent_key(day,cid) in byparent else None for cid in ids]
            table=table.append_column("whole_parent_id",pa.array(parent_ids,pa.string()))
            table=table.append_column("original_row_ordinal",pa.array(range(len(table)),pa.int64()))
            for field in list(table.column_names):
                if field.endswith("_ns") and ("event" in field or "receive" in field or "known_by" in field or "recognition" in field):
                    values=np.array([v if v is not None else -1 for v in table[field].to_pylist()],np.int64)
                    context=np.where(values>=0,np.searchsorted(pub,values,side="right"),-1).astype(np.int32)
                    table=table.append_column(field+"_external_context",pa.array(context,pa.int32()))
            pq.write_table(table,dest/(name+".parquet"),compression="zstd")
        zbytes=fetch(D,RREV,f"{RP}/{day}/sources/x13_life_paths.npz")
        with np.load(io.BytesIO(zbytes),allow_pickle=False) as z:
            arrayrows=z["row"].astype(np.int64);ks=z["ks"].astype(np.int64);variables=list(z.files)
        rbyrow={r["input_row"]:r for r in renders}
        cuts=np.array([rbyrow[int(i)]["pre_cutoff_ns"] for i in arrayrows],np.int64)[:,None]+ks[None,:]*10**9
        labels=cuts+1
        seconds=labels//10**9
        ix=np.searchsorted(source_sec,seconds)
        valid=(ix<len(source_sec))&(source_sec[np.minimum(ix,len(source_sec)-1)]==seconds)
        native_rows=np.where(valid,ix,-1).astype(np.int32)
        known=np.where(valid,source_known[np.minimum(ix,len(source_sec)-1)],-1)
        known_context=np.where(known>=0,np.searchsorted(pub,known,side="right"),-1).astype(np.int32)
        sample_context=np.searchsorted(pub,cuts,side="right").astype(np.int32)
        np.savez_compressed(dest/"sample-clock-pins.npz",input_row=arrayrows,ks=ks,sample_cut_ns=cuts,
            external_at_sample_cut=sample_context,native_second_label_ns=labels,native_source_row=native_rows,
            native_second_known_by_ns=known,external_at_native_second_known_by=known_context)
        assert cuts.shape==(len(arrayrows),1321)
        assert np.all(labels-cuts==1)
        assert np.all(sample_context==np.searchsorted(pub,cuts,side="right"))
        # Map original variable meanings to applicable canonical entries, never claiming full layer coverage.
        for v in variables:
            if v in ("row","ks","pol"):layer_fields["raw_source_identity_provenance_clocks_integrity"].add(v)
            if v in ("mid_o","spr"):layer_fields["price_and_book_path"].add(v)
            if v=="spr":layer_fields["spread_and_depth_imbalance"].add(v)
            if v in ("tgt_sz","own_sz","tgt_near5","own_near5"):layer_fields["full_bid_ask_depth"].add(v)
            if v in ("tgt_n","own_n"):layer_fields["price_level_and_order_counts"].add(v)
            if v in ("with_lots","against_lots","n_trades"):layer_fields["aggressor_and_native_signed_flow"].add(v)
            for token,layer in [("add_","order_lifecycle_adds"),("rm_cx","order_lifecycle_cancels"),("fill","order_lifecycle_fills"),("mod_","order_lifecycle_modifies")]:
                if token in v:layer_fields[layer].add(v)
        for name,fields in {
          "clock_event_time":["recognition_clocks.event_ns","signal_event_ns","trade_event_ns"],
          "clock_receive_time":["recognition_clocks.receive_ns","signal_receive_ns","trade_receive_ns"],
          "clock_event_known_by":["recognition_clocks.known_by_ns","native_second_known_by_ns","signal_known_by_ns","trade_known_by_ns"],
          "clock_prospective_discovery_confirmation":["claude.recognition_ns","native.recognition_ns"],
          "derived_feature_availability_timestamps":["sample_cut_ns (sampling only, not claimed availability)"],
          "derived_roll20_and_dipole_state":["companion ratio","native ratio","candidate operands"],
          "missingness_and_integrity_flags":["missing_array","coverage_disposition","missing_live_recognition"]}.items():layer_fields[name].update(fields)
        pins=[];mismatches=[];joins=[]
        for r in renders:
            cid=r["candidate_id"];pid=parent_key(day,cid);p=byparent[pid]
            assert p["kind"]=="candidate" and p["anchor_label_ns"]==r["birth_ns"]
            rows_native=[x for x in detector[cid] if x["row"]["variant"]=="native_action"]
            assert len(rows_native)==1,(day,cid)
            cs=[clock(pub,"claude.birth_ns",r["birth_ns"],"birth_label"),
                clock(pub,"claude.pre_cutoff_ns",r["pre_cutoff_ns"],"sampling_cut")]
            if r["recognition_ns"] is not None:cs.append(clock(pub,"claude.recognition_ns",r["recognition_ns"],"recognition"))
            if r["available_second"] is not None:cs.append(clock(pub,"claude.available_second",r["available_second"]*10**9,"nominal_available_second_label"))
            for field in ("recognition_ns","lifecycle_end_label_ns","lifecycle_end_known_by_ns","lifecycle_start_known_by_ns"):
                if p.get(field) is not None:cs.append(clock(pub,"native."+field,int(p[field]),"known_by" if "known_by" in field else "recognition" if field=="recognition_ns" else "operational_endpoint_label"))
            for field in ("event_ns","receive_ns","known_by_ns"):
                v=(p.get("recognition_clocks") or {}).get(field)
                if v is not None:cs.append(clock(pub,"native.recognition_clocks."+field,int(v),field))
            for field in ("run_onset_s","run_end_s","first_flip_s","first_empty_s"):
                v=r["markers"].get(field)
                if v is not None:cs.append(clock(pub,"claude."+field,r["birth_ns"]+int(v)*10**9,"companion_second_label_not_known_by"))
            for entry in first.get(str(r["input_row"]),[]):
                for field in ("k_aggressor_start","k_touch_size_change","k_quote_relocation"):
                    k=integer(entry["row"].get(field))
                    if k is not None and k>=0:
                        cs.append(clock(pub,"claude.first_events."+field,r["pre_cutoff_ns"]+k*10**9,"interval_left_boundary" if field=="k_aggressor_start" else "sampled_boundary"))
                        if field=="k_aggressor_start":cs.append(clock(pub,"claude.first_events.aggressor_interval_right",r["pre_cutoff_ns"]+(k+1)*10**9,"interval_right_boundary"))
            agreement=r["recognition_ns"]==p["recognition_ns"]
            if not agreement:mismatches.append(dict(candidate_id=cid,claude_ns=r["recognition_ns"],native_ns=p["recognition_ns"]))
            tablelinks=[]
            for cat in catalog:
                fields=cat["original_fields"]
                if "candidate_id" in fields:
                    tablelinks.append(dict(source_revision=cat["source_revision"],source_path=cat["source_path"],sha256=cat["sha256"],selector={"candidate_id":cid},scope="all matching kinds retained; kind field distinguishes candidate and controls"))
            row=dict(day=day,candidate_id=cid,parent_id=pid,join_basis="exact archived candidate identity within date; exact birth clock corroborates",
                claude_render=selector(RREV,f"{RP}/{day}/{r['file']}"),claude_original_index=r,
                native_whole=selector(WREV,wp+"/whole-lifecycles.parquet",parent_id=pid),
                native_parent_record=p,paired_control_parent_ids=[x["row"]["parent_id"] for x in bycandidate[cid] if x["row"]["kind"]!="candidate"],
                native_components=components[cid],native_points=selector(WREV,wp+"/whole-lifecycle-points.parquet",parent_id=pid),
                native_book_pages=bookby[cid],book_source=dict(revision=BREV,path=f"{BP}/render-{day}"),
                recognition_clock_agreement=agreement,clocks=cs,native_detector_rows=detector[cid],
                claude_detector_ledger=ledger[cid],claude_first_events=first.get(str(r["input_row"]),[]),
                native_first_structural_events=nearest[cid],event_clock_rows=eventclocks[cid],
                related_signal_count=signal_counts[cid],related_trade_count=trade_counts[cid],
                signal_rows=selector(EREV,ep+"/cross-study-event-links.parquet",latest_recognized_dipole_id=cid),
                trade_rows=selector(EREV,ep+"/a-trade-dipole-overlaps.parquet",candidate_id=cid),
                native_table_links=tablelinks,external_context_contract="../external/external-context-contract.json")
            pins.append(row)
            native=rows_native[0]["row"];cl=ledger[cid][0]["row"] if ledger[cid] else None
            joins.append(dict(day=day,candidate_id=cid,claude_input_row=r["input_row"],claude_array_present=not r["missing_array"],
                claude_emulated_as_birth=None if cl is None else cl.get("emulated_as_birth"),
                claude_disposition=None if cl is None else cl.get("disposition"),
                native_action_birth_disposition=native.get("birth_disposition"),
                native_nominal_available_second=native.get("available_second_recovered"),
                original_available_second=r["available_second"],recognition_clock_agreement=agreement))
        assert len(pins)==len(renders)==len({x["parent_id"] for x in pins})
        assert all(p["parent_id"] in byparent for p in pins)
        writejson(dest/"instance-pins.json.gz",pins)
        writejson(dest/"detector-ledger-crosswalk.json",joins)
        writejson(dest/"clock-differences.json",mismatches)
        writejson(dest/"native-table-catalog.json",catalog)
        summary=dict(day=day,candidate_pages=len(pins),whole_parent_matches=len(pins),
          controls_linked=sum(len(p["paired_control_parent_ids"]) for p in pins),missing_arrays=sum(p["claude_original_index"]["missing_array"] for p in pins),
          sample_boundary_clocks=int(cuts.size),timeline_clocks=sum(len(p["clocks"]) for p in pins),
          recognition_clock_differences=len(mismatches),signal_rows=len(signals),signals_with_parent=sum(signal_counts[cid] for cid in rbyid(renders)),
          trade_rows=len(trades),claude_ledger_rows=sum(bool(p["claude_detector_ledger"]) for p in pins))
        summaries.append(summary)
        print(summary,flush=True)
    assert sum(s["candidate_pages"] for s in summaries)==3178
    known_ids={l["layer_id"] for l in layers};assert set(layer_fields)<=known_ids
    writejson(out/"99-layer-attachments.json",[dict(layer_id=l["layer_id"],source_paths=l.get("source_paths",[]),linked_fields=sorted(layer_fields[l["layer_id"]]),
        disposition="linked_observed_fields_subset" if layer_fields[l["layer_id"]] else "registry_context_only_no_measured_render_field") for l in layers])
    info=out/"informational";info.mkdir()
    informational=[]
    for rev,path in [
      ("9efb19a82480ebc2d1e5ef06dc550f2f18fa1197","agent-pass/FINDINGS.md"),
      ("9efb19a82480ebc2d1e5ef06dc550f2f18fa1197","agent-pass/FOUR_DAY_REPLICATION.md"),
      ("9efb19a82480ebc2d1e5ef06dc550f2f18fa1197","agent-pass/FAMILY_REPLICATION.md")]+[
      (CREV,CP+"/"+n) for n in ["FINDINGS_EVENT_STUDY_20261108.md","FINDINGS_THREE_DAYS_20261108.md","FINDINGS_TIER2_CROSSDAY_20261109.md",
      "crossday/t2x-coupling-agreement-vs-shifted.png","crossday/t2x-coupling-day-vs-oct18.png","crossday/t2x-coupling-top-by-family.png",
      "crossday/t2x-forward-stack.png","crossday/t2x-leadlag.png","crossday/t2x-pair-couplings-top-by-outcome.png","crossday/t2x-state-cells.png"]]:
        b=fetch(C,rev,path);name=("codex-" if path.startswith("agent-pass") else "claude-")+pathlib.Path(path).name
        (info/name).write_bytes(b);informational.append(dict(repository=C,revision=rev,path=path,local_file=name,sha256=hashlib.sha256(b).hexdigest(),role="informational_context_not_time_available_signal"))
    for name in ["fig-beyond.png","fig-cells.png","fig-clock.png","fig-clocks.png","fig-duration.png","fig-nextburst.png",
                 "fig-prebirth.png","fig-recognition.png","fig-ssos.png","ng-dipole-renders.html","ng-dipole-renders.pdf"]:
        path=ROOT+"/claude-code/renders/"+name;rev="24da8788a3e05f851a266086a82d7315c1df5974"
        b=fetch(C,rev,path);(info/name).write_bytes(b)
        informational.append(dict(repository=C,revision=rev,path=path,local_file=name,sha256=hashlib.sha256(b).hexdigest(),role="informational_summary_original_values_preserved_no_single_event_clock"))
    original=js(D,BREV,BP+"/render-archive/original-render-index.json")
    writejson(info/"original-figure-index.json",original)
    writejson(info/"context-index.json",informational)
    writejson(out/"SUMMARY.json",summaries);writejson(out/"SOURCES.json",READS)
    writejson(out/"MANIFEST.json",dict(files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob("*")) if p.is_file()]))
def rbyid(rows):return [r["candidate_id"] for r in rows]
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",default="results");args=parser.parse_args();run(args.output)
