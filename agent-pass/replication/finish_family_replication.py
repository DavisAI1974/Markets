"""Recover structural-family inputs from sealed Git evidence and apply archived analyses."""
from __future__ import annotations
import argparse,ast,csv,gc,gzip,hashlib,io,json,os,pathlib,struct,subprocess,sys,tempfile,time,types,urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import zstandard

MREV="0408df44c4f106f7fda4ac4b92ae622d7d34cd7b"
DREV="968fa11324f66b70cd318140c51bf19e23f9ee4e"
NREV="0487d83b1ddb1abe5e4cfae12e8b88797801f428"
PROD="2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134"
BASE="tasks/family-research-20261022"
SNAP=BASE+"/native-dipole/20261108-33693e180"
FAM="artifacts/sqlite-triage/20261022/families"
NS=10**9
READS=[]
DESCRIBE=None
UNPACK=None

def get(repo,ref,path,digest=None):
    url=f"https://raw.githubusercontent.com/DavisAI1974/{repo}/{ref}/{path}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=240) as r:raw=r.read()
            break
        except Exception:
            if attempt==3:raise
            time.sleep(2**attempt)
    sha=hashlib.sha256(raw).hexdigest()
    if digest is not None:assert sha==digest,(path,sha,digest)
    READS.append(dict(repository=repo,revision=ref,path=path,bytes=len(raw),sha256=sha))
    return raw

def jsonwrite(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+"\n")

def writecsv(path,frame):
    path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(path,index=False,**({"compression":{"method":"gzip","mtime":0}} if str(path).endswith(".gz") else {}))

def table(raw,gz=False,**kw):
    return pd.read_csv(io.BytesIO(raw),compression="gzip" if gz else None,**kw)

def selected_source(source,names,environment):
    tree=ast.parse(source)
    nodes=[]
    for n in tree.body:
        assigned=[t.id for t in n.targets if isinstance(t,ast.Name)] if isinstance(n,ast.Assign) else []
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names or any(x in names for x in assigned):
            nodes.append(n)
    exec("from __future__ import annotations\n"+ast.unparse(ast.Module(body=nodes,type_ignores=[])),environment)
    return environment

def operators():
    global DESCRIBE,UNPACK
    prefix="research/kalshi/frankie_raw_mbo_benchmark/"
    raw=get("Markets",PROD,prefix+"a_memory_member_first_recalculation_20260828.py",
            "04194df484a69bb8d91a296e67145d34ada1a24ed1cf2aa1b4529565808369bb")
    mirror=get("Markets",PROD,prefix+"native_mirror.py",
               "397bdc142d0939913990e5b3afd388bc906a7c49cfcd4c08d1b07057a45827a6")
    env=selected_source(mirror,{"_SIDE_SWAP","CANONICAL","MIRROR","mirror_identity"},{})
    env=selected_source(raw,{"CARRIED_NATIVE_ACTION_FAMILIES","canonical_hash","action_string","side_string",
                            "mirror_identity","fill_disposition","describe_structure"},
                        dict(Counter=Counter,json=json,hashlib=hashlib,native_mirror_identity=env["mirror_identity"]))
    DESCRIBE=env["describe_structure"]
    journal=get("Markets","db96f24f3260bf0d70c763b297c2ba9b84f571a6","research/kalshi/frankie_boss/c15_journal.py")
    UNPACK=selected_source(journal,{"unpack"},dict(struct=struct))["unpack"]

def inputs(day,raw_required=False):
    manifest=json.loads(get("markets-data",DREV,"MANIFEST.json"))
    e=next(x for x in manifest["entries"] if x.get("session")==day and x["path"].endswith("/groups.jsonl.gz"))
    payload=get("markets-data",DREV,e["markets_data_path"],e["sha256"])
    groups=[json.loads(s) for s in gzip.decompress(payload).splitlines()]
    if not raw_required:return groups
    manifest=json.loads(get("markets-data",NREV,SNAP+"/MANIFEST.json"))
    e=next(x for x in manifest["entries"] if x["source"]==f"agent-pass/cache/raw-{day}.parquet")
    raw=pd.read_parquet(io.BytesIO(get("markets-data",NREV,e["path"],e["sha256"])))
    return groups,raw

def prior(times,cursors,t,cap):
    return min(int(np.searchsorted(times,t,side="left"))-1,
               int(np.searchsorted(cursors,cap,side="right"))-1)

def tests():
    assert UNPACK(["float64","3ff0000000000000"])==1.0
    assert prior(np.array([10,20,20,30]),np.array([1,2,3,4]),20,3)==0
    assert prior(np.array([10,20,20,30]),np.array([1,2,3,4]),31,2)==1
    a=[dict(action="A",side="B",order_id=1,price_raw=100,size=1)]
    b=[dict(action="A",side="B",order_id=99,price_raw=200,size=500)]
    assert DESCRIBE(a)["candidate_family_id"]==DESCRIBE(b)["candidate_family_id"]
    assert DESCRIBE(a)["candidate_family_id"]!=DESCRIBE([dict(a[0],side="A")])["candidate_family_id"]
    print("PASS: packed floats, strict-time/cursor cutoffs, structural identity invariance and side distinction",flush=True)

def derive(day,out):
    groups,raw=inputs(day,True)
    raw=raw.sort_values("cursor")
    cursors=raw.cursor.to_numpy(dtype=np.int64)
    assert len(np.unique(cursors))==len(cursors)
    records=raw[["action","side","price","size","order_id"]].rename(columns={"price":"price_raw"}).to_dict("records")
    times=np.array([g["receive_ns"] for g in groups],dtype=np.int64)
    closes=np.array([g["close_cursor"] for g in groups],dtype=np.int64)
    starts=np.searchsorted(cursors,[g["first_cursor"] for g in groups])
    ends=np.searchsorted(cursors,closes,side="right")
    firsts={};counts=Counter();occurrences=[]
    for j,(g,lo,hi) in enumerate(zip(groups,starts,ends)):
        assert hi>lo and cursors[lo]==g["first_cursor"] and cursors[hi-1]==g["close_cursor"]
        assert hi-lo==g["close_cursor"]-g["first_cursor"]+1
        d=DESCRIBE(records[lo:hi]);fid=d["candidate_family_id"]
        counts[fid]+=1
        occurrences.append((j,int(g["close_cursor"]),int(g["receive_ns"]),fid))
        if fid not in firsts:
            k=prior(times,closes,g["receive_ns"],g["first_cursor"]-1)
            firsts[fid]=dict(family_id=fid,start_recv_ns=g["receive_ns"],input_cursor=g["close_cursor"],
                first_cursor=g["first_cursor"],source_ordinal=j,pre_source_ordinal=k,
                pre_input_cursor=groups[k]["close_cursor"] if k>=0 else "",
                cursor_cap=g["close_cursor"]-1,start_basis="FIRST_OBSERVED_STRUCTURAL_FAMILY",
                snapshot_member=g["snapshot_member"],reset_member=g["reset_member"],
                bad_receive_clock_member=g["bad_receive_clock_member"],
                descriptor=d)
    # Historical cap is first family's close cursor minus one; same-time exclusion is stricter.
    for f in firsts.values():
        k=prior(times,closes,f["start_recv_ns"],f["cursor_cap"])
        f["pre_source_ordinal"]=k
        f["pre_input_cursor"]=int(closes[k]) if k>=0 else ""
        f["occurrence_count"]=counts[f["family_id"]]
    ordered=sorted(firsts.values(),key=lambda f:(f["start_recv_ns"],f["input_cursor"]))
    for i,f in enumerate(ordered,1):
        f.update(instance=str(i),sample_id=f"{i}:before_start",
                 start_utc=datetime.fromtimestamp(f["start_recv_ns"]//NS,timezone.utc).isoformat())
    jsonwrite(out/day/"family-starts.json",ordered)
    writecsv(out/day/"all-family-occurrences.csv.gz",pd.DataFrame(occurrences,columns=["source_ordinal","input_cursor","receive_ns","family_id"]))
    receipt=dict(day=day,groups=len(groups),families=len(ordered),occurrences=sum(counts.values()),
                 no_prior_group=sum(f["pre_source_ordinal"]<0 for f in ordered),
                 source_revision=MREV,descriptor_revision=PROD,
                 definition="First structural family in source order. All IDs retained; no Search catalog filter.")
    if day=="20231018":
        expected=table(get("Markets",MREV,FAM+"/descriptive-v1/family_master.csv"),dtype=str)
        for r in expected.to_dict("records"):
            f=firsts[r["family_id"]]
            for key in ("source_ordinal","input_cursor","start_recv_ns","occurrence_count"):
                assert int(r[key])==int(f[key]),(r["family_id"],key,r[key],f[key])
        receipt["original_749_identity_clock_count_checks"]="passed"
        receipt["original_catalog_ids"]=len(expected)
        receipt["additional_open_world_ids"]=len(firsts)-len(expected)
    jsonwrite(out/day/"population-receipt.json",receipt)
    print(json.dumps(receipt),flush=True)
    return receipt

def install_modules(work):
    sys.path.insert(0,str(work))
    for name in ("flow_book_discovery.py","research_atlas.py","research_atlas_prebirth.py"):
        (work/name).write_bytes(get("Markets",MREV,BASE+"/"+name))
    (work/"research_atlas_primer.py").write_bytes(get("Markets","c4ca63f2816a50e051f70f6219f2378bd9530777",
                                                    "agent-pass/replication/research_atlas_primer.py"))

def primer_input(frame):
    # CSV blanks represent absent history; preserve those cases in the full study.
    result=frame.copy()
    result["pre_group"]=result["pre_group"].map(lambda v: np.nan if v=="" else v)
    return result

def apply_family(groups,index,out,day,reference=False):
    import flow_book_discovery as fb
    import research_atlas as atlas
    import research_atlas_prebirth as prebirth
    import research_atlas_primer as primer
    folder=out/"flow-book-discovery-v1";folder.mkdir(parents=True)
    atlas_folder=out/"research-atlas-v2";atlas_folder.mkdir()
    def rows(path):
        if path==fb.GROUPS:return groups
        if path==fb.REVIEW+"chronological-instance-index.csv":return index
        raise ValueError("Unexpected historical input "+path)
    fb.rows=rows;fb.OUT=folder
    a=fb.load_groups()
    frame,ends=fb.opportunities(a)
    metrics=fb.fit_arms(frame,ends)
    fb.save("opportunities.csv.gz",frame);fb.save("outcomes.csv.gz",ends)
    fb.cohort_tables(frame,ends)
    if reference:
        checked=[]
        for name in ("opportunities.csv.gz","outcomes.csv.gz","arm-predictions.csv.gz","arm-metrics.csv",
                     "chronological-splits.csv","cohort-outcomes.csv","activity-controls.csv","activity-control-outcomes.csv"):
            expected=table(get("Markets",MREV,BASE+"/flow-book-discovery-v1/"+name),name.endswith(".gz"))
            actual=pd.read_csv(folder/name)
            pd.testing.assert_frame_equal(actual,expected,check_dtype=False,rtol=1e-10,atol=1e-12)
            checked.append(name)
        jsonwrite(out/"reference-reproduction.json",dict(tables=checked,passed=True))
    midnight=int(datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
    atlas.OPEN=(midnight if day in ("20231002","20231017") else midnight-7200)*NS
    atlas.CLOSE=(midnight+21*3600)*NS
    atlas.OUT=atlas_folder
    prebirth.rows=rows;prebirth.GROUPS=fb.GROUPS
    prebirth.OPEN=atlas.OPEN;prebirth.CLOSE=atlas.CLOSE
    prebirth.OUT=atlas_folder
    # The current date adapter supports explicit populations. All families remain.
    prebirth.main({"family_start":[(str(r.instance),int(r.anchor_ns)) for r in frame.itertuples()]})
    primer.OUT=atlas_folder;primer.HERE=out;primer.rows=rows;primer.GROUPS=fb.GROUPS
    path=BASE+("/research-atlas-v2/" if day=="20231018" else f"/replay-comparison/{day}/research-atlas-v2/")
    (atlas_folder/"aggression-to-rest-events.csv").write_bytes(get("Markets",MREV,path+"aggression-to-rest-events.csv"))
    primer_frame=primer_input(frame)
    assert len(primer_frame)==len(frame)
    primer.main(family=primer_frame,sensitivity_populations=[("family_start","total1")])
    writecsv(atlas_folder/"primer-family-anchor-dispositions.csv",pd.DataFrame({
        "instance":frame.instance,"family_id":frame.family_id,
        "disposition":["no_strict_pre_group" if pd.isna(v) else "anchor_available" for v in primer_frame.pre_group]}))
    (atlas_folder/"aggression-to-rest-events.csv").unlink()
    for name in ("prebirth-method.json","primer-application-method.json"):
        p=atlas_folder/name;m=json.loads(p.read_text())
        m.update(trade_date=day,source_revision=MREV,scope="original 749 reference" if reference else "all observed structural families on the retained date span",
                 source_family="chronological-instance-index.csv in this immutable publication",
                 populations=["family_start"])
        jsonwrite(p,m)
    assert len(frame)==len(index)
    assert frame.family_id.is_unique
    for r in frame[frame.input_disposition.eq("available")].itertuples():
        assert int(r.pre_receive_ns)<int(r.anchor_ns)
        assert int(r.pre_cursor)<=int(r.cursor_cap)
    assert metrics.groupby(["horizon_s","target","fold"]).arm.nunique().eq(4).all()
    assert metrics.groupby(["horizon_s","target","fold"]).n_train.nunique().eq(1).all()
    assert metrics.groupby(["horizon_s","target","fold"]).n_test.nunique().eq(1).all()
    splits=pd.read_csv(folder/"chronological-splits.csv")
    assert (splits.last_train_label_target_ns+600*NS<splits.test_start_ns).all()
    cases=pd.read_csv(atlas_folder/"prebirth-cases.csv.gz")
    assert cases.groupby("lead_s").case_id.nunique().eq(len(index)).all()
    available=cases[cases.input_disposition.eq("available")]
    # Read exact nullable clocks as strings for nanosecond checks.
    exact=pd.read_csv(atlas_folder/"prebirth-cases.csv.gz",dtype=str,keep_default_na=False)
    for r in exact[exact.input_disposition.eq("available")].itertuples():
        assert int(r.source_known_by_ns)<int(r.decision_ns)<int(r.birth_ns)
    receipt=dict(day=day,families=len(frame),four_arm_eligible=int(frame.four_arm_eligible.sum()),
                 model_fits=len(metrics),prebirth_case_rows=len(cases),checks="passed",
                 primer_missing_prior=int(primer_frame.pre_group.isna().sum()),
                 cohorts=frame.cohort.value_counts().to_dict(),scope="reference749" if reference else "all observed date-specific structural families")
    jsonwrite(out/"analysis-receipt.json",receipt)
    print(json.dumps(receipt),flush=True)

class Parts(io.RawIOBase):
    def __init__(self,day):
        base=BASE+f"/replay-artifacts/{day}/root-frames"
        self.base=base
        self.source=json.loads(get("Markets",MREV,base+"/source.json"))
        self.sums=[s.split() for s in get("Markets",MREV,base+"/SHA256SUMS").decode().splitlines()]
        assert [n for d,n in self.sums]==[f"frames.jsonl.zst.part-{i:06d}" for i in range(len(self.sums))]
        self.pool=ThreadPoolExecutor(max_workers=2);self.future={};self.i=0;self.current=None
        for k in range(min(2,len(self.sums))):self.schedule(k)
    def schedule(self,k):
        digest,name=self.sums[k]
        self.future[k]=self.pool.submit(get,"Markets",MREV,self.base+"/"+name,digest)
    def readable(self):return True
    def readinto(self,b):
        while True:
            if self.current is None:
                if self.i>=len(self.sums):return 0
                self.current=io.BytesIO(self.future.pop(self.i).result())
                if self.i+2<len(self.sums):self.schedule(self.i+2)
                self.i+=1
                if self.i%10==0:print(f"verified archive parts {self.i}/{len(self.sums)}",flush=True)
            n=self.current.readinto(b)
            if n:return n
            self.current.close();self.current=None
    def close(self):
        self.pool.shutdown(wait=True)
        if self.current:self.current.close()
        super().close()

def extract(day,populations,out):
    operators();tests()
    groups=inputs(day)
    families=json.loads((populations/day/"family-starts.json").read_text())
    current={f["source_ordinal"]:f for f in families}
    pre={f["pre_source_ordinal"] for f in families if f["pre_source_ordinal"]>=0}
    wanted=set(current)|pre
    snapshots={};checksum=hashlib.sha256();size=0;count=0;offset=0;started=time.monotonic()
    with Parts(day) as parts,zstandard.ZstdDecompressor().stream_reader(parts) as decompressed,io.BufferedReader(decompressed,buffer_size=4<<20) as stream:
        source=parts.source
        for ordinal,line in enumerate(stream):
            checksum.update(line);size+=len(line);count+=1
            if ordinal in wanted:
                packed=dict(json.loads(line)[1])
                g=groups[ordinal]
                t=UNPACK(packed["ts_recv_ns"]);cursor=UNPACK(packed["input_cursor"])
                assert (t,cursor)==(g["receive_ns"],g["close_cursor"])
                if ordinal in current:
                    native=UNPACK(packed["native_frame"])
                    assert DESCRIBE(native["raw_actions"])["candidate_family_id"]==current[ordinal]["family_id"]
                if ordinal in pre:
                    book=UNPACK(packed["book"])
                    assert book["bid_depth_full"]==sum(x["size"] for x in book["bid_levels_full"])
                    assert book["ask_depth_full"]==sum(x["size"] for x in book["ask_levels_full"])
                    for side,levels in (("bid",book["bid_levels"]),("ask",book["ask_levels"])):
                        if g[side]:
                            assert (levels[0]["price_raw"],levels[0]["size"])==tuple(g[side][:2])
                    fields={f"root.{key}":UNPACK(packed[key]) for key in
                            ("best_bid","best_ask","mid","spread","depth_imbalance_n","depth_imbalance_full","bid_depth_full","ask_depth_full")}
                    activity=UNPACK(packed["activity"])
                    for h in (1,5,20,60,300):
                        for key in ("trade_buy_aggressor_qty","trade_sell_aggressor_qty","trade_aggressor_imbalance","event_count","top_level_cancel_qty_derived"):
                            fields[f"root.activity.{h}.{key}"]=activity[str(h)][key]
                    snapshots[ordinal]=dict(fields=fields,source_receive_ns=t,source_cursor=cursor,
                        source_ordinal=ordinal,uncompressed_byte_offset=offset,source_row_bytes=len(line),
                        source_row_sha256=hashlib.sha256(line).hexdigest())
            offset+=len(line)
            if count%100000==0:print(json.dumps(dict(day=day,rows=count,bytes=size,seconds=round(time.monotonic()-started))),flush=True)
        assert (size,count,checksum.hexdigest())==(source["bytes"],source["count"],source["sha256"])
    assert set(snapshots)==pre
    index=[]
    keys=list(next(iter(snapshots.values()))["fields"])
    for f in families:
        r={k:v for k,v in f.items() if k!="descriptor"}
        r.update({k:"" for k in keys})
        k=f["pre_source_ordinal"]
        if k>=0:
            s=snapshots[k]
            assert s["source_receive_ns"]<f["start_recv_ns"] and s["source_cursor"]<=f["cursor_cap"]
            r.update(s["fields"])
        # Preserve historical CSV zero semantics: "0" is observed, "" is missing.
        index.append({k:("" if v is None else str(v)) for k,v in r.items()})
    out.mkdir(parents=True)
    writecsv(out/"chronological-instance-index.csv",pd.DataFrame(index))
    jsonwrite(out/"strict-pre-root-source-coordinates.json",list(snapshots.values()))
    jsonwrite(out/"source-receipt.json",dict(day=day,source=source,observed_uncompressed_sha256=checksum.hexdigest(),
        observed_bytes=size,observed_rows=count,source_revision=MREV,verified_parts=len(parts.sums),
        extracted_strict_pre_groups=len(snapshots),verified_first_family_descriptors=len(current),
        all_families_retained=len(families),seconds=round(time.monotonic()-started,3)))
    with tempfile.TemporaryDirectory() as tmp:
        install_modules(pathlib.Path(tmp));apply_family(groups,index,out,day)
    jsonwrite(out/"input-manifest.json",READS)
    seal(out)

def seal(out):
    files=[]
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="MANIFEST.json":
            raw=p.read_bytes();files.append(dict(path=str(p.relative_to(out)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    jsonwrite(out/"MANIFEST.json",dict(code_revision=os.environ.get("CODE_REV"),files=files))

def preflight(out):
    operators();tests();out.mkdir(parents=True)
    for day in ("20231018","20231002","20231003","20231017"):
        derive(day,out);gc.collect()
    # Reproduce the original 749-family four-arm study before extracting new dates.
    groups=inputs("20231018")
    index=table(get("Markets",MREV,FAM+"/instance-market-review-20261023/chronological-instance-index.csv"),
                dtype=str,keep_default_na=False).to_dict("records")
    with tempfile.TemporaryDirectory() as tmp:
        install_modules(pathlib.Path(tmp))
        apply_family(groups,index,out/"20231018-reference","20231018",reference=True)
    jsonwrite(out/"input-manifest.json",READS);seal(out)


RECOVERY_REV="54e1b1be98ae6defff25ccfe7e1c3498e8f569f9"
RECOVERY_PATH=BASE+"/family-replication/run-42564821790-1"

def resume(day,out):
    operators();tests()
    sample=pd.DataFrame({"pre_group":["",0,12,np.nan]})
    converted=primer_input(sample)
    assert converted.pre_group.isna().tolist()==[True,False,False,True]
    assert converted.pre_group.iloc[1:3].tolist()==[0,12]
    assert sample.pre_group.iloc[0]==""
    groups=inputs(day)
    out.mkdir(parents=True)
    reference=day=="20231018"
    if reference:
        raw=get("Markets",MREV,FAM+"/instance-market-review-20261023/chronological-instance-index.csv")
        (out/"chronological-instance-index.csv").write_bytes(raw)
    else:
        for name in ("chronological-instance-index.csv","strict-pre-root-source-coordinates.json","source-receipt.json"):
            (out/name).write_bytes(get("markets-data",RECOVERY_REV,RECOVERY_PATH+f"/family-{day}/"+name))
        receipt=json.loads((out/"source-receipt.json").read_text())
        original=json.loads(get("Markets",MREV,BASE+f"/replay-artifacts/{day}/root-frames/source.json"))
        assert receipt["source"]==original
        assert receipt["observed_uncompressed_sha256"]==original["sha256"]
        assert receipt["observed_bytes"]==original["bytes"]
        assert receipt["observed_rows"]==original["count"]==len(groups)
        sums=get("Markets",MREV,BASE+f"/replay-artifacts/{day}/root-frames/SHA256SUMS").decode().splitlines()
        assert receipt["verified_parts"]==len(sums)
    index=pd.read_csv(out/"chronological-instance-index.csv",dtype=str,keep_default_na=False).to_dict("records")
    if not reference:assert len(index)==receipt["all_families_retained"]
    with tempfile.TemporaryDirectory() as tmp:
        install_modules(pathlib.Path(tmp));apply_family(groups,index,out,day,reference=reference)
    if reference:
        for name in ("primer-spread-event-outcomes.csv.gz","primer-spread-event-summary.csv","primer-prebirth-sensitivity.csv"):
            expected=table(get("markets-data",RECOVERY_REV,RECOVERY_PATH+"/family-preflight/20231018-reference/research-atlas-v2/"+name),name.endswith(".gz"))
            actual=pd.read_csv(out/"research-atlas-v2"/name)
            pd.testing.assert_frame_equal(actual,expected,check_dtype=False,rtol=1e-10,atol=1e-12)
        jsonwrite(out/"primer-reference-reproduction.json",dict(passed=True,tables=3))
    jsonwrite(out/"recovery-provenance.json",dict(prior_run=42564821790,prior_data_revision=RECOVERY_REV,
        reason="Primer expected NaN for absent pre_group; CSV adapter supplied empty string. Preserve missing cases and explicitly record primer disposition.",
        full_archive_reused=not reference,all_prior_extraction_receipts_preserved=not reference))
    jsonwrite(out/"input-manifest.json",READS);seal(out)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["preflight","extract","resume"])
    p.add_argument("--day");p.add_argument("--populations",type=pathlib.Path)
    p.add_argument("--output",required=True,type=pathlib.Path);a=p.parse_args()
    if a.mode=="preflight":preflight(a.output)
    elif a.mode=="extract":extract(a.day,a.populations,a.output)
    else:resume(a.day,a.output)
