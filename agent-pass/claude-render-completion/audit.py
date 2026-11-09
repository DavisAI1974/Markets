"""Independently reconcile saved candidates/arrays with all published render pages."""
import csv,gzip,hashlib,io,json,pathlib,sys,zipfile,shutil
import numpy as np
from PIL import Image
ROOT=pathlib.Path(sys.argv[1])
reports=[];preview=[]
for day in ("20231002","20231003","20231017","20231018"):
    d=ROOT/day;src=d/"sources"
    rows=[json.loads(l) for l in gzip.decompress((src/"candidate-inputs.jsonl.gz").read_bytes()).splitlines()]
    z=np.load(src/"x13_life_paths.npz",allow_pickle=False)
    coverage={int(r["row"]):r for r in csv.DictReader((src/"coverage.csv").open())}
    records=sum([json.loads(p.read_text()) for p in sorted(d.glob("index-*.json"))],[])
    records.sort(key=lambda r:r["ordinal"])
    counts=sum([json.loads(p.read_text()) for p in sorted(d.glob("reconciliation-*.json"))],[])
    assert len(records)==len(rows)
    assert [r["ordinal"] for r in records]==list(range(1,len(rows)+1))
    assert sorted(r["input_row"] for r in records)==list(range(len(rows)))
    assert len({r["candidate_id"] for r in records})==len(rows)
    assert len(list(d.glob("*.png")))==len(rows)
    byid={r["candidate_id"]:r for r in records}
    for r in records:
        assert r["candidate_id"]==rows[r["input_row"]]["candidate_id"]
        if r["array_row"] is not None:
            assert int(z["row"][r["array_row"]])==r["input_row"]
            assert int(coverage[r["input_row"]]["rec_ns"])==r["recognition_ns"]
        assert r["pre_cutoff_ns"]==r["birth_ns"]-1
        b=(d/r["file"]).read_bytes()
        assert hashlib.sha256(b).hexdigest()==r["sha256"]
        im=Image.open(io.BytesIO(b));assert im.size==(1400,1500);im.verify()
    for c in counts:
        assert c["finite_cells"]+c["missing_cells"]==c["source_cells"]
        assert c["finite_cells"]==c["rendered_cells"]
        if c["variable"] in z:
            r=byid[c["candidate_id"]];n=r["array_row"]
            v=np.full(c["source_cells"],np.nan) if n is None else z[c["variable"]][n,:c["source_cells"]]
            assert int(np.isfinite(v).sum())==c["finite_cells"]
    longest=max((r for r in records if r["array_row"] is not None),key=lambda r:max(r["markers"]["first_flip_s"] or 0,r["markers"]["first_empty_s"] or 0))
    picks=[records[0],longest]
    missing=[r for r in records if r["missing_array"]]
    picks+=missing[:1]
    for r in picks:
        p=ROOT/"previews"/day;p.mkdir(parents=True,exist_ok=True)
        shutil.copy2(d/r["file"],p/r["file"])
        preview.append(dict(day=day,kind="missing_saved_array" if r["missing_array"] else "long_lifecycle" if r is longest else "first",file=f"previews/{day}/{r['file']}",candidate_id=r["candidate_id"],markers=r["markers"]))
    (d/"INDEX.json").write_text(json.dumps(records,indent=1))
    lines=[f"# {day} individual lifecycle renders","",f"{len(rows)} candidate pages; {len(z['row'])} saved array rows; {len(missing)} pages identify absent saved arrays.","","Full-resolution PNGs and exact clock/source records are in this folder.","","| Page | Candidate | Saved array |","|---:|---|---|"]
    lines += [f"| {r['ordinal']} | [{r['candidate_id']}]({r['file']}) | {'absent' if r['missing_array'] else 'present'} |" for r in records]
    (d/"README.md").write_text("\n".join(lines)+"\n")
    reports.append(dict(day=day,input_candidates=len(rows),saved_array_rows=len(z["row"]),rendered=len(records),missing_array_pages=len(missing),reconciled_variable_rows=len(counts),finite_cells=sum(c["finite_cells"] for c in counts),missing_cells=sum(c["missing_cells"] for c in counts)))
(ROOT/"AUDIT.json").write_text(json.dumps(reports,indent=2))
(ROOT/"PREVIEWS.json").write_text(json.dumps(preview,indent=2))
manifest=[]
for p in sorted(ROOT.rglob("*")):
    if p.is_file():manifest.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(ROOT/"MANIFEST.json").write_text(json.dumps(dict(source_revision="beb2104c079045c24832f2279eac5e8e69bc576e",files=manifest),indent=1))
print(json.dumps(reports,indent=2))
