import bisect,gzip,hashlib,json,pathlib,sys
import numpy as np
import pyarrow.parquet as pq
root=pathlib.Path(sys.argv[1])
manifest=json.loads((root/"MANIFEST.json").read_text())
for item in manifest["files"]:
    b=(root/item["path"]).read_bytes()
    assert len(b)==item["bytes"] and hashlib.sha256(b).hexdigest()==item["sha256"]
with np.load(root/"external/external-contexts.npz",allow_pickle=False) as z:
    pub=z["publication_ns"];prev=z["previous_original_index"]
source=json.loads(gzip.decompress((root/"external/original-external-series.json.gz").read_bytes()))["series"]
for col,s in enumerate(source):
    ordered=sorted(enumerate(s["known"]),key=lambda x:(int(x[1]["published_ns"]),x[0]))
    ts=[int(x[1]["published_ns"]) for x in ordered]
    for row,t in enumerate(pub,1):
        j=bisect.bisect_right(ts,int(t))-1
        assert int(prev[row,col])==(ordered[j][0] if j>=0 else -1)
def bound(clocks,ctx):
    ok=ctx>=0
    cs=clocks[ok];ix=ctx[ok]
    assert np.all((ix==0)|(pub[np.maximum(ix-1,0)]<=cs))
    assert np.all((ix==len(pub))|(pub[np.minimum(ix,len(pub)-1)]>cs))
allids=set();total=0
for day in ("20231002","20231003","20231017","20231018"):
    d=root/day;pins=json.loads(gzip.decompress((d/"instance-pins.json.gz").read_bytes()))
    for p in pins:
        assert p["parent_id"]==day+":"+p["candidate_id"]+":candidate"
        assert p["parent_id"] not in allids;allids.add(p["parent_id"])
        assert p["native_parent_record"]["anchor_label_ns"]==p["claude_original_index"]["birth_ns"]
        for c in p["clocks"]:assert c["external_context_index"]==bisect.bisect_right(pub,int(c["ns"]))
    byrow={p["claude_original_index"]["input_row"]:p for p in pins}
    with np.load(d/"sample-clock-pins.npz",allow_pickle=False) as z:
        cuts=z["sample_cut_ns"];ctx=z["external_at_sample_cut"];bound(cuts,ctx)
        for j,r in enumerate(z["input_row"]):
            p=byrow[int(r)]
            assert not p["claude_original_index"]["missing_array"]
            assert np.array_equal(cuts[j],p["claude_original_index"]["pre_cutoff_ns"]+z["ks"]*10**9)
        assert np.all(z["native_second_label_ns"]==cuts+1)
        bound(z["native_second_known_by_ns"],z["external_at_native_second_known_by"])
    for file in ("signal-links.parquet","trade-links.parquet"):
        table=pq.read_table(d/file)
        for field in table.column_names:
            if field.endswith("_external_context"):
                clockfield=field.removesuffix("_external_context")
                clocks=np.array([x if x is not None else -1 for x in table[clockfield].to_pylist()],np.int64)
                ctx=table[field].to_numpy()
                assert np.all((clocks>=0)==(ctx>=0));bound(clocks,ctx)
    total+=len(pins)
assert total==3178
assert len(json.loads((root/"99-layer-attachments.json").read_text()))==99
assert len(json.loads((root/"external/all-13-input-bindings.json").read_text())["points"])==13
(root/"VERIFICATION.json").write_text(json.dumps(dict(candidate_pins=total,source_and_output_hashes_checked=True,integer_clock_joins_checked=True,
    publication_contexts_checked=True,missing_clock_sentinels_checked=True),indent=2))
print("VERIFIED",total,"candidate pins")
