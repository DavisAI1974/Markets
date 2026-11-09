"""Codex source/field review inventory from the frozen packet; no producer reruns."""
import collections, concurrent.futures, csv, gzip, hashlib, io, json, math, os, pathlib, re, tempfile, time, urllib.request
import numpy as np
import pyarrow.parquet as pq
import openpyxl

REV="e7b1c4acac2e37205cdb9ce1c53829b6ca30f4ee"
PACKET="tasks/family-research-20261022/shared-reanalysis-inputs/final-42593665910-1"
D="DavisAI1974/markets-data"
def fetch(repo,rev,path):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{rev}/{path}",timeout=180) as r:return r.read()
        except Exception:
            if attempt==3:raise
            time.sleep(2**attempt)
def numeric(v):
    if isinstance(v,bool):return None
    if isinstance(v,(int,float)):return v if math.isfinite(v) else None
    if not isinstance(v,str) or not v:return None
    if re.fullmatch(r"[+-]?\d+",v):return int(v)
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except ValueError:return None
def flatten(obj,prefix=""):
    if isinstance(obj,dict):
        for k,v in obj.items():yield from flatten(v,prefix+"."+str(k) if prefix else str(k))
    elif isinstance(obj,(list,tuple)):
        if not obj:yield prefix+"[]",None
        for v in obj:yield from flatten(v,prefix+"[]")
    else:yield prefix,obj

def inspect(group):
    source=group["canonical"]; path=source["path"]
    result=dict(content_id=group["content_id"],source=source,aliases=group["aliases"],format="",
                status="reviewed",rows=0,fields=0,role=source["role"],clock_attachments=group.get("clock_attachments",[]))
    stats={}; samples=[]; tail=None
    def add(row,ordinal):
        nonlocal tail
        result["rows"]+=1
        if len(samples)<3:samples.append(dict(ordinal=ordinal,row=row))
        tail=dict(ordinal=ordinal,row=row)
        for field,v in flatten(row):
            f=stats.setdefault(field,dict(field=field,observations=0,missing=0,types=collections.Counter(),numeric_count=0,min=None,max=None,examples=[]))
            f["observations"]+=1;f["types"][type(v).__name__]+=1
            if v is None or v=="":f["missing"]+=1;continue
            if len(f["examples"])<3 and v not in f["examples"]:f["examples"].append(v)
            x=numeric(v)
            if x is not None:
                f["numeric_count"]+=1
                if f["min"] is None or x<f["min"]:f["min"]=x
                if f["max"] is None or x>f["max"]:f["max"]=x
    try:
        data=fetch(source["repository"],source["revision"],path)
        assert len(data)==group["bytes"],"byte-size mismatch"
        assert hashlib.sha256(data).hexdigest()==group["sha256"],"SHA256 mismatch"
        result["bytes_verified"]=True
        raw=gzip.decompress(data) if path.endswith(".gz") else data
        ext=path[:-3] if path.endswith(".gz") else path
        if ext.endswith(".csv"):
            result["format"]="csv"
            for i,row in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))):add(row,i)
        elif ext.endswith((".jsonl",".ndjson")):
            result["format"]="jsonl"
            for i,line in enumerate(io.BytesIO(raw)):
                if line.strip():
                    obj=json.loads(line)
                    # Pin fields are annotation views of embedded observations.
                    # Preserve each layer/clock mapping as fields; do not count each pin as an event.
                    if group.get("annotation_not_independent_sample"):
                        obj={k:v for k,v in obj.items() if k!="pins"}
                        mapping={}
                        original=json.loads(line)
                        for pin in original.get("pins",[]):
                            mapping[pin.get("field","unknown")]=dict(layers=pin.get("layers"),clock_kind=pin.get("clock_kind"))
                        obj["pin_definitions"]=mapping
                    add(obj,i)
        elif ext.endswith(".parquet"):
            result["format"]="parquet"
            table=pq.ParquetFile(io.BytesIO(raw));idx=0
            for batch in table.iter_batches(batch_size=4096):
                for row in batch.to_pylist():add(row,idx);idx+=1
        elif ext.endswith(".json"):
            result["format"]="json";obj=json.loads(raw)
            if isinstance(obj,list):
                for i,row in enumerate(obj):add(row,i)
            else:add(obj,0)
        elif ext.endswith(".npz"):
            result["format"]="npz"
            with np.load(io.BytesIO(raw),allow_pickle=False) as arrays:
                result["arrays"]=[]
                for key in arrays.files:
                    arr=arrays[key]
                    result["arrays"].append(dict(name=key,shape=list(arr.shape),dtype=str(arr.dtype),values=int(arr.size)))
                    f=dict(field=key,observations=int(arr.size),missing=0,types={str(arr.dtype):int(arr.size)},numeric_count=0,min=None,max=None,examples=[])
                    if np.issubdtype(arr.dtype,np.number):
                        valid=arr[np.isfinite(arr)]
                        f.update(missing=int(arr.size-valid.size),numeric_count=int(valid.size),
                                 min=valid.min().item() if valid.size else None,max=valid.max().item() if valid.size else None,
                                 examples=valid.reshape(-1)[:3].tolist())
                    else:f["examples"]=arr.reshape(-1)[:3].tolist()
                    stats[key]=f
                result["rows"]=None
                result["status"]="array_values_accounted_for; behavioral interpretation requires source-defined axes"
        elif ext.endswith(".xlsx"):
            result["format"]="xlsx";workbook=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            result["sheets"]=[]
            for sheet in workbook:
                result["sheets"].append(dict(name=sheet.title,rows=sheet.max_row,columns=sheet.max_column))
                rows=sheet.iter_rows(values_only=True);header=next(rows,())
                for i,values in enumerate(rows):
                    add({sheet.title+"."+str(k):v for k,v in zip(header,values)},i)
            workbook.close()
        elif ext.endswith((".md",".txt",".py",".sh",".yml")):
            result["format"]="text";text=raw.decode("utf-8-sig")
            result["lines"]=len(text.splitlines())
            result["headings"]=[line for line in text.splitlines() if line.startswith("#")][:300]
            result["rows"]=None
        elif ext.endswith(".png"):
            import struct
            result["format"]="png"
            assert raw[:8]==b"\x89PNG\r\n\x1a\n"
            result["width"],result["height"]=struct.unpack(">II",raw[16:24])
            result["rows"]=None
            result["status"]="image_bytes_verified; visual interpretation and source-table linkage required"
        else:
            result["format"]=ext.rsplit(".",1)[-1];result["status"]="bytes_verified; format review pending";result["rows"]=None
        result["fields"]=len(stats)
        result["clock_fields"]=[key for key in stats if re.search(r"(time|clock|_ns|_utc|known_by|recognition|cutoff|cursor|ordinal)",key,re.I)]
        if tail and tail not in samples:samples.append(tail)
        return result,list(stats.values()),samples
    except Exception as exc:
        result["status"]="unassessed";result["reason"]=type(exc).__name__+": "+str(exc)
        return result,list(stats.values()),samples

def main(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    packet=json.loads(fetch(D,REV,PACKET+"/CANONICAL_INPUTS.json"))
    groups=packet["active_inputs"];catalog=[]
    with gzip.open(out/"FIELD_INVENTORY.jsonl.gz","wt") as fields,gzip.open(out/"TABLE_SAMPLES.jsonl.gz","wt") as examples:
        # Two simultaneous expansions keep compressed pin ledgers within runner memory.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for result,stats,samples in pool.map(inspect,groups):
                catalog.append(result)
                for field in stats:fields.write(json.dumps(dict(content_id=result["content_id"],**field),default=str)+"\n")
                if samples:examples.write(json.dumps(dict(content_id=result["content_id"],source=result["source"],samples=samples),default=str)+"\n")
                print(result["status"],result["source"]["path"],flush=True)
    (out/"SOURCE_CATALOG.json").write_text(json.dumps(catalog,indent=2,default=str)+"\n")
    summary=dict(analyst="Codex",manifest_revision=REV,manifest_path=PACKET,source_contents=len(catalog),
                 fields=sum(x["fields"] for x in catalog),status_counts=dict(collections.Counter(x["status"] for x in catalog)),
                 unassessed=[dict(source=x["source"],reason=x.get("reason")) for x in catalog if x["status"]=="unassessed"],
                 interpretation="Structural inventory and whole-file summaries, not a substitute for the independent analytical report.",
                 sample_rule="First three and final records illustrate schema only. All records contribute to field statistics; samples never define the analysis population.")
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
    manifest=[]
    for file in out.iterdir():
        b=file.read_bytes();manifest.append(dict(path=file.name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    (out/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":
    import sys
    main(sys.argv[1])
