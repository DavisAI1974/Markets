"""Inspect saved schemas for before/during/after application; no producer execution."""
import gzip, hashlib, io, json, pathlib, sys, urllib.request
import numpy as np
import pyarrow.parquet as pq
from source_review import fetch
D="DavisAI1974/markets-data"; ROOT="tasks/family-research-20261022/"
SREV="e2731854a42bcce04a8cf89e249603dc18d3b0f7"; SP=ROOT+"codex-independent-review/run-42594360842-1"
LREV="2f1c3c72f9e3f15916135bca37ffcad87477e1d6"; LP=ROOT+"lifecycle-data-links/run-42583801329-1"
def trim(x):
    if isinstance(x,dict):return {k:trim(v) for k,v in x.items()}
    if isinstance(x,list):return [trim(v) for v in x[:2]]+([{"remaining":len(x)-2}] if len(x)>2 else [])
    return x
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
result={}
for line in gzip.decompress(fetch(D,SREV,SP+"/TABLE_SAMPLES.jsonl.gz")).splitlines():
    x=json.loads(line);p=x["source"]["path"]
    if any(t in p for t in ["events-20231018/","20231018-life-","20231018-candidate-operands","/20231018/t1_family_master.csv","/20231018/t2_state","/dipole/20231018/instances/"]):
        result[p]={"source":x["source"],"samples":trim(x["samples"])}
for name in ["20231018/trade-links.parquet","20231018/signal-links.parquet","99-layer-attachments.json","external/external-context-contract.json","external/all-13-input-bindings.json","external/canonical-99-registry.json","external/original-external-series.json.gz","external/external-contexts.npz"]:
    b=fetch(D,LREV,LP+"/"+name)
    if name.endswith(".parquet"):
        p=pq.ParquetFile(io.BytesIO(b));v={"schema":str(p.schema_arrow),"rows":p.metadata.num_rows,"samples":next(p.iter_batches(batch_size=1)).to_pylist()}
    elif name.endswith(".npz"):
        with np.load(io.BytesIO(b),allow_pickle=False) as a:v={k:{"shape":list(a[k].shape),"dtype":str(a[k].dtype),"sample":a[k].reshape(-1)[:3].tolist()} for k in a.files}
    else:v=trim(json.loads(gzip.decompress(b) if name.endswith(".gz") else b))
    result[name]=v
(out/"SCHEMAS.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"sources":len(result),"bytes":(out/"SCHEMAS.json").stat().st_size}))
