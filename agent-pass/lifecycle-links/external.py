import gzip,io,json,pathlib,tarfile
import numpy as np
from link_io import fetch,writejson
CODE="4cf6e85de5de2a9fb479c90b7afb8dd50f1748cb"
BASE="artifacts/sqlite-triage/20261022/families"
def build(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    registry_bytes=fetch("DavisAI1974/Markets",CODE,BASE+"/full-context-audit/canonical-99-registry.json")
    bindings_bytes=fetch("DavisAI1974/Markets",CODE,BASE+"/trade-lifecycle-targeted-v1/all-13-input-bindings.json")
    (out/"canonical-99-registry.json").write_bytes(registry_bytes)
    (out/"all-13-input-bindings.json").write_bytes(bindings_bytes)
    layers=[e for g in json.loads(registry_bytes)["groups"] for e in g["entries"]]
    bindings=json.loads(bindings_bytes)["points"]
    b=fetch("DavisAI1974/Markets",CODE,BASE+"/external-classroom-audit-v1.tar.gz")
    with tarfile.open(fileobj=io.BytesIO(b),mode="r:gz") as archive:
        original=archive.extractfile("external-classroom-audit-v1/original_series_known_values.json").read()
    (out/"original-external-series.json.gz").write_bytes(gzip.compress(original,mtime=0))
    series=json.loads(original)["series"];assert len(layers)==99 and len(bindings)==13 and len(series)==48
    names=[s["name"] for s in series]
    assert all(b["series"] in names for point in bindings for b in point["series"])
    pub=np.array(sorted({int(k["published_ns"]) for s in series for k in s["known"]}),dtype=np.int64)
    # Context 0 precedes every original publication; context j+1 begins at pub[j].
    previous=np.full((len(pub)+1,len(series)),-1,np.int32);following=previous.copy()
    for col,s in enumerate(series):
        ordered=sorted(enumerate(s["known"]),key=lambda pair:(int(pair[1]["published_ns"]),pair[0]))
        ts=np.array([int(k["published_ns"]) for _,k in ordered],np.int64)
        ids=np.array([i for i,_ in ordered],np.int32)
        ix=np.searchsorted(ts,pub,side="right")
        if len(ids):
            previous[1:,col]=np.where(ix>0,ids[np.maximum(ix-1,0)],-1)
            following[0,col]=ids[0]
            following[1:,col]=np.where(ix<len(ids),ids[np.minimum(ix,len(ids)-1)],-1)
            for j,p in enumerate(pub,1):
                k=previous[j,col];n=following[j,col]
                assert k<0 or int(s["known"][k]["published_ns"])<=int(p)
                assert n<0 or int(s["known"][n]["published_ns"])>int(p)
    np.savez_compressed(out/"external-contexts.npz",publication_ns=pub,previous_original_index=previous,next_original_index=following)
    writejson(out/"external-context-contract.json",dict(series_order=names,context_index_rule="searchsorted(publication_ns,clock_ns,side='right')",
        chosen="previous_original_index[context_index,series_index] points into original series.known; -1 means no published observation",
        ties="last original row at tied publication wins",state_policy="original numeric state/value/reason unchanged; never fall back to older PRESENT",
        scope="original stored targets and publication confidence retained; D/D1/D3 are not retargeted to another day; declared publication is not proof of live ingestion",
        sample_clocks="plot cuts and second labels are not asserted to be information-availability clocks"))
    return pub,layers
