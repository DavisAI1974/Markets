"""Freeze common source coordinates only; never produce an analyst's conclusions."""
import concurrent.futures, copy, hashlib, json, os, pathlib, time, urllib.error, urllib.request

M="DavisAI1974/Markets"; D="DavisAI1974/markets-data"
DISC="f1c7277d2d303cea190e710abc1589f597a1e31d"
SUITE="3d0b06aa29781d5e39cc3eb45c6d09e174f195a2"
OWN="43aa3ec3a925d27d805eb69320c8fdd68fe0e6d0"
DATA="c01caaf4f327e8fdff21e4e8b9c5153aba8604a8"
FIX="418462afeaf0f14aa8129f6f4d02c3867d772fd0"
PRIOR_REV="36658bb5f15cad3a0dfea0201bff2cfe4acbf47e"
PRIOR="tasks/family-research-20261022/shared-reanalysis-inputs/precision-fix-42592319662-1"
BASE="tasks/family-research-20261022"
READS=[]

def get(url):
    for attempt in range(4):
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"Markets-shared-input-freeze"})
            if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
                request.add_header("Authorization","Bearer "+os.environ["GITHUB_TOKEN"])
            with urllib.request.urlopen(request,timeout=180) as response:return response.read()
        except Exception:
            if attempt==3:raise
            time.sleep(2**attempt)
def fetch(repo,rev,path):return get(f"https://raw.githubusercontent.com/{repo}/{rev}/{path}")
def read(repo,rev,path):return json.loads(fetch(repo,rev,path))
def tree(repo,rev):
    value=json.loads(get(f"https://api.github.com/repos/{repo}/git/trees/{rev}?recursive=1"))
    assert not value["truncated"]
    return {x["path"]:x for x in value["tree"] if x["type"]=="blob"}
def write(out,name,value):
    (out/name).write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
def coord(e):return (e["repository"],e["revision"],e["path"])
def role(path):
    if path.endswith((".py",".sh",".yml")):return "producer_code_context"
    if path.endswith((".md",".png",".xlsx")):return "informational_context"
    if "receipt" in path.lower() or "manifest" in path.lower():return "provenance"
    return "source_data"

def main(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    packet=read(D,PRIOR_REV,PRIOR+"/CANONICAL_INPUTS.json")
    definitions=read(D,PRIOR_REV,PRIOR+"/DEFINITION_CHECK.json")
    unavailable=read(D,PRIOR_REV,PRIOR+"/UNAVAILABLE_REFERENCES.json")
    overlaps=read(D,PRIOR_REV,PRIOR+"/ANNOTATION_OVERLAPS.json")
    correction=read(D,PRIOR_REV,PRIOR+"/PRECISION_CORRECTION.json")
    sources={}
    for group in packet["active_inputs"]:
        for e in [group["canonical"]]+group["aliases"]:
            e=copy.deepcopy(e)
            # These four manifest aliases were never present at the manifest commit;
            # retain the true immutable family-index coordinates already in the same group.
            if "/family-replication/" in e["path"] and e["revision"]=="67b7a6afaaaa7bf77bb4048011b1da28af2875b1":
                continue
            sources[coord(e)]=e
    specs=[(M,DISC,tree(M,DISC)),(M,SUITE,tree(M,SUITE)),(M,OWN,tree(M,OWN)),(D,DATA,tree(D,DATA))]
    requests=[]
    for repo,rev,files in specs:
        for path,item in files.items():
            selected=False
            if rev==DISC:
                selected=path.startswith(BASE+"/claude-code/") or (path.startswith(BASE+"/") and "/" not in path[len(BASE)+1:] and path.endswith(".md"))
            elif rev==SUITE:
                selected=path.startswith((BASE+"/claude-pass/",BASE+"/claude-pass-3day/"))
            elif rev==OWN:
                selected=path.startswith("agent-pass/") and not path.startswith("agent-pass/reanalysis/")
            elif rev==DATA:
                selected=path=="MANIFEST.json"
            if selected:requests.append((repo,rev,path,item))
    # The corrected generator is common source provenance; it supersedes only its broken code.
    fixed_tree=tree(M,FIX)
    requests.append((M,FIX,BASE+"/claude-code/pin_tier1_rows_to_99.py",fixed_tree[BASE+"/claude-code/pin_tier1_rows_to_99.py"]))
    def measured(item):
        repo,rev,path,meta=item
        data=fetch(repo,rev,path)
        assert len(data)==meta["size"],path
        git_blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        assert git_blob==meta["sha"],path
        return dict(repository=repo,revision=rev,path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                    git_blob=git_blob,role=role(path),collection="final_source_packet",
                    checksum_evidence="downloaded, SHA256 measured and Git blob verified during final freeze",
                    clock_status="preserve source clocks; aggregates and retrospective labels are not decision-time inputs")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for entry in pool.map(measured,requests):sources[coord(entry)]=entry
    # Incorporate the four final shifted-draw files and all final data-manifest references.
    manifest=read(D,DATA,"MANIFEST.json")
    superseded={x["path"] for rep in correction["replacements"] for x in rep["superseded_coordinates"]}
    data_tree=specs[-1][2]
    for original in manifest["entries"]:
        path=original.get("markets_data_path") or original["path"]
        if path.endswith("/") or path in superseded:continue
        if path in data_tree:rev=DATA;meta=data_tree[path]
        else:
            aliases=[e for e in sources.values() if e["repository"]==D and e["path"]==path and e["sha256"]==original.get("sha256")]
            assert aliases,("missing final reference",path)
            continue
        if original.get("bytes") is None or not original.get("sha256"):
            entry=measured((D,rev,path,meta));sources[coord(entry)]=entry
            continue
        e=dict(repository=D,revision=rev,path=path,bytes=meta["size"],git_blob=meta["sha"],
               sha256=original["sha256"],role="pin_annotations_with_embedded_rows" if "/claude-code-pins/" in path and ".jsonl" in path else "source_data",
               collection="final_data_manifest",day=original.get("session") or original.get("utc_day"),
               source_manifest_entry=original,checksum_evidence="SHA256 declared by immutable manifest; bytes and Git blob verified in tree")
        assert e["bytes"]==original["bytes"]
        sources[coord(e)]=e
    by={}
    for e in sources.values():by.setdefault((e["sha256"],e["bytes"]),[]).append(e)
    groups=[]
    for (sha,size),variants in sorted(by.items()):
        variants.sort(key=lambda e:(e["repository"]!=D,e["collection"]=="final_data_manifest",e["path"],e["revision"]))
        g=dict(content_id="sha256:"+sha,sha256=sha,bytes=size,canonical=variants[0],aliases=variants[1:],
               scope_rule="Reuse identical bytes; preserve each alias's original population, day, identities and clocks.",
               clock_attachments=[e["clock_sidecar"] for e in variants if "clock_sidecar" in e],
               annotation_not_independent_sample=any(e["role"]=="pin_annotations_with_embedded_rows" for e in variants))
        groups.append(g)
    old_shas={g["sha256"] for g in packet["active_inputs"]}
    assert old_shas.issubset({g["sha256"] for g in groups})
    receipts=[e for e in sources.values() if e["path"].endswith("CCODE_FINAL_SUITE_RECEIPT.json")]
    assert len(receipts)==1
    summary=dict(status="FROZEN_USER_START_AUTHORIZED",analysis_authorized=True,evidence_frozen=True,
                 authorization="User explicitly said Start on November 9, 2026",
                 shared_scope="Both analysts independently analyze the entire identical packet; no duty split.",
                 source_coordinates=len(sources),unique_file_contents=len(groups),
                 duplicate_file_aliases_removed=len(sources)-len(groups),
                 duplicate_groups=sum(bool(g["aliases"]) for g in groups),
                 annotation_ledger_contents=sum(g["annotation_not_independent_sample"] for g in groups),
                 final_source_files_measured=len(requests),prior_distinct_contents_preserved=len(old_shas),
                 unavailable_archive_references=len(unavailable),registry_match=True,bindings_match=True,
                 registry_layers=99,bound_points=13,physical_source_deletions=0,
                 limitations=["Three historical archive directory references remain unavailable; retain explicit coverage.",
                 "Byte-identical copies are aliases. Distinct source projections and embedded annotations are joined by source identities before pooled counting.",
                 "Final receipt lists a removed discovery HANDOFF_20261109.md: the user confirms there is no separate handoff.",
                 "The final receipt describes its pre-generation parent revision; authoritative receipt bytes are pinned at 3d0b06a.",
                 "Freezing inputs does not establish availability or execution validity for every observation; assess each claimed decision against its own clocks."])
    packet.update(summary);packet["active_inputs"]=groups;packet["definitions"]=definitions
    packet["remaining"]=["Independent full analysis and matching deliverables by each analyst","Compare only after both reports are saved"]
    packet["final_source_revisions"]=dict(discovery=DISC,suite=SUITE,data=DATA,own=OWN,precision_generator=FIX,prior_corrected_packet=PRIOR_REV)
    packet["final_suite_receipt"]=receipts[0]
    packet["precision_correction"]=correction["verification"]
    packet["new_analyses_excluded"]=True
    duplicates=[dict(content_id=g["content_id"],canonical=g["canonical"],removed_from_independent_input_list=g["aliases"]) for g in groups if g["aliases"]]
    write(out,"CANONICAL_INPUTS.json",packet);write(out,"SUMMARY.json",summary)
    write(out,"DEFINITION_CHECK.json",definitions);write(out,"DUPLICATE_ALIASES.json",duplicates)
    write(out,"UNAVAILABLE_REFERENCES.json",unavailable);write(out,"ANNOTATION_OVERLAPS.json",overlaps)
    write(out,"PRECISION_CORRECTION.json",correction)
    write(out,"SOURCES.json",list(sources.values()))
    print(json.dumps(summary,indent=2))
if __name__=="__main__":
    import sys
    main(sys.argv[1])
