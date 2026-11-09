"""Inspect immutable inputs remotely before implementing timestamp joins."""
import csv,gzip,hashlib,io,json,os,pathlib,tarfile,urllib.request
import pyarrow.parquet as pq
BASE="tasks/family-research-20261022"
MREV="4cf6e85de5de2a9fb479c90b7afb8dd50f1748cb"
DREV="a7149ba09b7260020d7e7c208dd319162417c323"
CCREV="24da8788a3e05f851a266086a82d7315c1df5974"
OUT=pathlib.Path(os.environ["OUTPUT_DIR"]);OUT.mkdir(parents=True,exist_ok=True)
def get(repo,rev,path):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/DavisAI1974/{repo}/{rev}/{path}",timeout=240) as r:return r.read()
def inspect(repo,rev,path):
    raw=get(repo,rev,path)
    if path.endswith(".parquet"):
        f=pq.ParquetFile(io.BytesIO(raw)); batch=next(f.iter_batches(batch_size=1),None)
        return dict(path=path,bytes=len(raw),rows=f.metadata.num_rows,schema=str(f.schema_arrow),sample=batch.to_pylist() if batch else [])
    plain=gzip.decompress(raw) if path.endswith(".gz") else raw
    if ".csv" in path:
        reader=csv.DictReader(io.StringIO(plain.decode()));return dict(path=path,columns=reader.fieldnames,sample=next(reader,None))
    if ".jsonl" in path:return dict(path=path,sample=json.loads(plain.splitlines()[0]))
    return dict(path=path,sample=json.loads(plain))
paths=[
BASE+"/whole-lifecycles/run-42573465249-1/audit-20231002/"+n for n in
["whole-lifecycles.parquet","whole-lifecycle-points.parquet","component-windows.parquet","native-flow-source-clocks.parquet","individual-table-catalog.json"]]
paths += [BASE+"/combined-events/run-42571551209-1/events-20231002/"+n for n in
["a-trades.parquet","a-print-legs.parquet","b-signals.parquet","cross-study-event-links.parquet"]]
paths += [BASE+"/native-dipole/20261108-33693e180/agent-pass/tables/"+n for n in
["20231002-paths.csv.gz","20231002-candidate-operands.csv","20231002-life-paths.csv.gz","20231002-first-footprint-events.csv","shape-form-residuals.csv"]]
result=[]
for p in paths:
    try:result.append(inspect("markets-data",DREV,p))
    except Exception as e:result.append(dict(path=p,error=str(e)))
result.append(inspect("markets-data","ae25b947139bbd0744a4139dc01da0ae66fab093",BASE+"/claude-code-pins/ninety-nine-pins-oct02.jsonl.gz"))
archive=get("Markets",MREV,"artifacts/sqlite-triage/20261022/families/external-classroom-audit-v1.tar.gz")
with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as tf:
    names=[m.name for m in tf.getmembers()]
    result.append(dict(archive_members=names))
    for member in tf.getmembers():
        if member.name.endswith("original_series_known_values.json"):
            raw=tf.extractfile(member).read(); data=json.loads(raw)
            (OUT/"external-source-shape.json").write_text(json.dumps(dict(keys=list(data),series=[dict(name=s["name"],keys=list(s),count=len(s["known"]),first=s["known"][:1],last=s["known"][-1:]) for s in data["series"]]),indent=2))
(OUT/"input-probe.json").write_text(json.dumps(result,indent=2,default=str))
print(json.dumps([dict(path=r.get("path"),rows=r.get("rows"),error=r.get("error")) for r in result]))
