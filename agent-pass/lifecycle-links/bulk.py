"""Row-preserving source-clock attachment. No market signal is recomputed."""
import argparse,bisect,collections,csv,gzip,hashlib,io,json,pathlib,re,urllib.request,time
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np
from pin_core import extract_clocks,layer_fields,utc_ns,exact_int,flatten
from link_io import fetch,writejson,READS
ROOT="tasks/family-research-20261022"
D="DavisAI1974/markets-data"
LINK_REV="2f1c3c72f9e3f15916135bca37ffcad87477e1d6"
LINK_ROOT=ROOT+"/lifecycle-data-links/run-42583801329-1"
WHOLE_REV="9e3365f76fb4d34d97eb193d35072aae5f51b709"
DAY0={"20231002":1696194000,"20231003":1696280400,"20231017":1697490000,"20231018":1697576400}
SCHEMA=pa.schema([
 ("row_ordinal",pa.int64()),("record_id",pa.string()),("source_ids_json",pa.string()),
 ("parent_refs",pa.list_(pa.string())),("clock_fields",pa.list_(pa.string())),("clock_ns",pa.list_(pa.int64())),
 ("clock_utc",pa.list_(pa.string())),("clock_roles",pa.list_(pa.string())),("clock_derivations",pa.list_(pa.string())),
 ("external_context_indices",pa.list_(pa.int32())),("disposition",pa.string()),("clock_corrections_json",pa.string())])
def source_rows(b,path):
    if path.endswith(".parquet"):
        p=pq.ParquetFile(io.BytesIO(b))
        for batch in p.iter_batches(batch_size=4096):
            yield from batch.to_pylist()
    else:
        if path.endswith(".gz"):b=gzip.decompress(b)
        if ".jsonl" in path:
            for line in b.splitlines():
                if line:yield json.loads(line)
        else:yield from csv.DictReader(io.StringIO(b.decode("utf-8-sig")))
def ident(e):return hashlib.sha256((e["repository"]+"@"+e["revision"]+":"+e["path"]).encode()).hexdigest()[:20]
def parent_refs(row,day,parents):
    refs=set()
    if row.get("parent_id") in parents:refs.add(row["parent_id"])
    kind=str(row.get("kind","candidate"));kind=kind if kind in ("candidate","control1","control2") else "candidate"
    for field,value in flatten(row):
        if not isinstance(value,str):continue
        if "candidate_id" in field or field.split(".")[-1] in ("left","right","id_a","id_b"):
            p=f"{day}:{value}:{kind}"
            if p in parents:refs.add(p)
    return sorted(refs)
def pin(e,out,pub,parents):
    b=fetch(e["repository"],e["revision"],e["path"])
    assert len(b)==e["bytes"]
    assert hashlib.sha1(("blob "+str(len(b))+"\0").encode()+b).hexdigest()==e["git_blob"]
    table_id=ident(e);dest=out/"rows"/table_id;dest.mkdir(parents=True,exist_ok=True)
    fields=set();mapping={};parts=[];buffer=[];counts=collections.Counter();fix_examples=[]
    def flush():
        if not buffer:return
        path=dest/f"{len(parts):05d}.parquet"
        pq.write_table(pa.Table.from_pylist(buffer,schema=SCHEMA),path,compression="zstd")
        parts.append(dict(path=path.relative_to(out).as_posix(),rows=len(buffer),bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        buffer.clear()
    for ordinal,original in enumerate(source_rows(b,e["path"])):
        row=original.get("row",original) if e["collection"]=="ccode_existing_pins" else original
        if not isinstance(row,dict):row={"original_value":row}
        row=dict(row)
        day=str(row.get("day",e["day"]));day=day if day in DAY0 else e["day"]
        ccode=e["collection"].startswith("ccode")
        if ccode and day in DAY0 and "day0_epoch_s" not in row and any(k in row for k in ("t0","onset","confirm","next_t0","seed_known_s","archived_recognition_s")):
            row["day0_epoch_s"]=DAY0[day]
        # Only source-defined session-second relative fields are eligible for automatic expansion.
        t0=exact_int(row.get("t0"))
        if ccode and t0 is not None and abs(t0)>172800:
            ccode=False
        clocks,fixes=extract_clocks(row,ccode=ccode)
        for c in clocks:
            leaf=c["field"].split(".")[-1]
            if leaf in ("available_second","available_second_recorded","available_second_recovered"):
                c["role"]="nominal_available_second_label_not_live_recognition"
        refs=parent_refs(row,day,parents)
        if e["collection"].startswith("ccode"):
            # Same-looking identifiers across independent populations are insufficient.
            birth_clocks={c["ns"] for c in clocks if "birth" in c["field"] or c["field"] in ("t0_epoch_s","event_second")}
            recognition_clocks={c["ns"] for c in clocks if "recognition" in c["field"]}
            refs=[p for p in refs if parents[p]["anchor_label_ns"] in birth_clocks or
                  (parents[p].get("recognition_ns") is not None and parents[p]["recognition_ns"] in recognition_clocks)]
        disposition="direct_clocks"
        if not clocks and refs:
            disposition="explicit_parent_context_only"
            for p in refs:
                for field in ("anchor_label_ns","recognition_ns","lifecycle_start_known_by_ns","lifecycle_end_label_ns","lifecycle_end_known_by_ns"):
                    value=parents[p].get(field)
                    if value is not None:clocks.append(dict(field=f"parent_context[{p}].{field}",ns=int(value),utc=utc_ns(int(value)),
                        role="parent_context_not_row_observation",derivation="explicit_whole_parent_link"))
        elif not clocks:disposition="aggregate_or_unclocked_retained"
        # A source ledger's field-layer associations take precedence over inferred field-name roles.
        if e["collection"]=="ccode_existing_pins":
            for item in original.get("pins",[]):
                ids=[x.get("layer_id") for x in item.get("layers",[]) if x.get("layer_id")]
                if ids:mapping[item["field"]]=ids
        newfields={field for field,_ in flatten(row)}-fields
        if newfields:
            inferred=layer_fields(newfields)
            for k,v in inferred.items():mapping.setdefault(k,v)
            fields.update(newfields)
        sourceids={k:v for k,v in row.items() if k in ("day","session","candidate_id","parent_id","kind","event_id","family_id","trade_ordinal","leg_id","instance_id","id","t0","source","source_file")}
        if e["collection"]=="ccode_existing_pins":
            sourceids["existing_ledger_coordinates"]={k:v for k,v in original.items() if k not in ("row","pins")}
        record=dict(row_ordinal=ordinal,record_id=f"{table_id}:{ordinal}",source_ids_json=json.dumps(sourceids,separators=(",",":"),default=str),
            parent_refs=refs,clock_fields=[c["field"] for c in clocks],clock_ns=[c["ns"] for c in clocks],
            clock_utc=[c["utc"] for c in clocks],clock_roles=[c["role"] for c in clocks],
            clock_derivations=[c["derivation"] for c in clocks],
            external_context_indices=[bisect.bisect_right(pub,c["ns"]) for c in clocks],
            disposition=disposition,clock_corrections_json=json.dumps(fixes,separators=(",",":")))
        buffer.append(record);counts["rows"]+=1;counts[disposition]+=1;counts["clocks"]+=len(clocks);counts["corrections"]+=len(fixes)
        if fixes and len(fix_examples)<5:fix_examples.append(dict(row=ordinal,corrections=fixes))
        if len(buffer)>=20000:flush()
    flush()
    # Read all written row coordinates, clock vectors and exact UTC strings back.
    seen=0
    for part in parts:
        p=pq.ParquetFile(out/part["path"])
        for batch in p.iter_batches(batch_size=4096):
            for r in batch.to_pylist():
                assert r["row_ordinal"]==seen;seen+=1
                n=len(r["clock_ns"])
                assert all(len(r[k])==n for k in ("clock_fields","clock_utc","clock_roles","clock_derivations","external_context_indices"))
                for ns,stamp,ctx in zip(r["clock_ns"],r["clock_utc"],r["external_context_indices"]):
                    assert stamp==utc_ns(ns)
                    assert ctx==bisect.bisect_right(pub,ns)
                assert all(p in parents for p in r["parent_refs"])
    assert seen==counts["rows"]
    meta=dict(table_id=table_id,source=e,source_sha256=hashlib.sha256(b).hexdigest(),
        source_fields=sorted(fields),field_layer_ids=mapping,counts=dict(counts),parts=parts,correction_examples=fix_examples,
        row_values="original immutable source; no values rescaled or recomputed",scope="historical_no_prefix" if "/no-prefix" in e["path"] else "source_population_unchanged")
    writejson(dest/"TABLE.json",meta)
    print(e["collection"],pathlib.Path(e["path"]).name,dict(counts),flush=True)
    return meta
def run(shard,out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    with np.load(io.BytesIO(fetch(D,LINK_REV,LINK_ROOT+"/external/external-contexts.npz")),allow_pickle=False) as z:pub=z["publication_ns"].tolist()
    parents={}
    for day in DAY0:
        path=ROOT+f"/whole-lifecycles/run-42573465249-1/audit-{day}/whole-lifecycles.parquet"
        rows=pq.read_table(io.BytesIO(fetch(D,WHOLE_REV,path))).to_pylist()
        parents.update({r["parent_id"]:r for r in rows})
    inputs=json.loads((pathlib.Path(__file__).parent/"inputs.json").read_text())
    selected=[e for e in inputs if e["day"]==shard]
    catalog=[pin(e,out,pub,parents) for e in selected]
    writejson(out/"CATALOG.json",catalog)
    writejson(out/"SUMMARY.json",dict(shard=shard,files=len(catalog),rows=sum(x["counts"].get("rows",0) for x in catalog),
        clocks=sum(x["counts"].get("clocks",0) for x in catalog),corrections=sum(x["counts"].get("corrections",0) for x in catalog),
        direct_clock_rows=sum(x["counts"].get("direct_clocks",0) for x in catalog),
        parent_context_rows=sum(x["counts"].get("explicit_parent_context_only",0) for x in catalog),
        unclocked_rows_retained=sum(x["counts"].get("aggregate_or_unclocked_retained",0) for x in catalog),
        external_context_revision=LINK_REV,external_context_path=LINK_ROOT+"/external",all_rows_read_back=True))
    writejson(out/"SOURCES.json",READS)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--shard",required=True);p.add_argument("--output",required=True);a=p.parse_args();run(a.shard,a.output)
