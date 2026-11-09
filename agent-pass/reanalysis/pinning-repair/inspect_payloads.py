"""Read original saved payload schemas before joining layers. GitHub-hosted only."""
import gzip,hashlib,io,json,os,pathlib,sys
from source_review import fetch
P=["artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/every-trade-evidence-bundle.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/every-trade-original-second-set.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/every-trade-root-record-links.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/original-root-native-measurement-rows.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/completed-run-connections-v1/every-trade-completed-run-and-lineage-links.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1/native.member.chunk001.jsonl.gz","artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1/second_set.chunk001.jsonl.gz"]
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
def shape(x,depth=0):
    if depth>5:return {"type":type(x).__name__,"count":len(x) if isinstance(x,(dict,list,str)) else None}
    if isinstance(x,dict):return {k:shape(v,depth+1) for k,v in x.items()}
    if isinstance(x,list):return {"count":len(x),"first":shape(x[0],depth+1) if x else None}
    return x
result={}
for path in P:
    b=fetch("DavisAI1974/Markets",os.environ["CODE_REV"],path)
    with gzip.open(io.BytesIO(b),"rt") as f:
        first=json.loads(next(f))
        n=1+sum(1 for line in f if line.strip())
    result[path]={"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"rows":n,"first":shape(first)}
    print(path,n,flush=True)
(out/"PAYLOAD_SCHEMA_AUDIT.json").write_text(json.dumps(result,indent=2)+"\n")
