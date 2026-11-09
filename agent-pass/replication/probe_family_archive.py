"""Inspect sealed ROOT archive schema on a hosted runner; no producer replay."""
import hashlib,io,json,os,pathlib,urllib.request,zstandard
REV="0408df44c4f106f7fda4ac4b92ae622d7d34cd7b"
BASE="tasks/family-research-20261022/replay-artifacts"
def get(path):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/DavisAI1974/Markets/{REV}/{path}",timeout=180) as r:return r.read()
def unpack(v):
    if not isinstance(v,list) or not v:return v
    if v[0]=="dict":return {k:unpack(x) for k,x in v[1]}
    if v[0] in ("list","tuple","set","frozenset"):return [unpack(x) for x in v[1]]
    if v[0]=="null":return None
    if len(v)==2 and v[0] in ("str","int","float","bool"):return v[1]
    return v
def shape(v,depth=0):
    if isinstance(v,dict):return {k:shape(x,depth+1) for k,x in v.items()} if depth<3 else list(v)
    if isinstance(v,list):return {"list_length":len(v),"first":shape(v[0],depth+1) if v else None}
    return v
out=pathlib.Path(os.environ["OUTPUT_PATH"]);out.mkdir(parents=True)
reports=[]
for day in ("20231002","20231003","20231017"):
    base=f"{BASE}/{day}/root-frames"
    sums=get(base+"/SHA256SUMS").decode().splitlines()
    digest,name=sums[0].split()
    payload=get(base+"/"+name)
    assert hashlib.sha256(payload).hexdigest()==digest
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(payload)) as stream:
        line=io.BufferedReader(stream).readline()
    row=unpack(json.loads(line))
    report=dict(day=day,source_revision=REV,source_path=base,part_count=len(sums),
                first_part_sha256=digest,first_part_bytes=len(payload),
                first_row_bytes=len(line),first_row_sha256=hashlib.sha256(line).hexdigest(),
                shape=shape(row))
    (out/f"{day}-schema.json").write_text(json.dumps(report,indent=2))
    reports.append({k:v for k,v in report.items() if k!="shape"})
    print(json.dumps(reports[-1]),flush=True)
(out/"receipt.json").write_text(json.dumps(reports,indent=2))
