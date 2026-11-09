"""Reconcile registry/bindings and remove byte-identical input aliases. No market analysis."""
import collections,hashlib,json,pathlib,time,urllib.request
M="DavisAI1974/Markets";D="DavisAI1974/markets-data"
BASE="artifacts/sqlite-triage/20261022/families"
CODE_OLD="4cf6e85de5de2a9fb479c90b7afb8dd50f1748cb"
CODE_CLAUDE="59f92066984935ada5693ba91a9f04fa4f2248ef"
CODE_CURRENT="c93895e22a2388112404f0122e37eee4947c5c45"
DATA_CURRENT="67b7a6afaaaa7bf77bb4048011b1da28af2875b1"
LINK_REV="2f1c3c72f9e3f15916135bca37ffcad87477e1d6"
LINK="tasks/family-research-20261022/lifecycle-data-links/run-42583801329-1"
BULK_REV="9bfffd6d0b0679cccbbc7a1115ecd8d81d589a0d"
BULK="tasks/family-research-20261022/all-row-clock-pins/run-42584823565-1"
PIN="tasks/family-research-20261022/claude-code-pins"
READS=[]
def fetch(repo,rev,path):
    url=f"https://raw.githubusercontent.com/{repo}/{rev}/{path}"
    for i in range(4):
        try:
            with urllib.request.urlopen(url,timeout=180) as r:b=r.read()
            break
        except Exception:
            if i==3:raise
            time.sleep(2**i)
    READS.append(dict(repository=repo,revision=rev,path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return b
def read(repo,rev,path):return json.loads(fetch(repo,rev,path))
def write(out,name,data):(out/name).write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
def coord(e):return (e["repository"],e["revision"],e["path"])
def group_sources(sources):
    by=collections.defaultdict(list)
    for e in sources:by[(e["sha256"],e["bytes"])].append(e)
    groups=[]
    for (sha,size),aliases in sorted(by.items()):
        # Prefer a source in the dedicated data repository; retain every original scope as an alias.
        aliases=sorted(aliases,key=lambda e:(e["repository"]!=D,e["revision"]!=DATA_CURRENT,e["path"],e["revision"]))
        groups.append(dict(content_id="sha256:"+sha,sha256=sha,bytes=size,canonical=aliases[0],aliases=aliases[1:],
            scope_rule="reuse content; retain each alias's population/day/source-row coordinates; no event multiplicities erased"))
    assert sum(1+len(g["aliases"]) for g in groups)==len(sources)
    assert len({g["content_id"] for g in groups})==len(groups)
    return groups
def main(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    definitions={}
    for name,original in [("registry",BASE+"/full-context-audit/canonical-99-registry.json"),
                          ("bindings",BASE+"/trade-lifecycle-targeted-v1/all-13-input-bindings.json")]:
        versions=[];objects=[]
        for rev in (CODE_OLD,CODE_CLAUDE,CODE_CURRENT):
            objects.append(read(M,rev,original));versions.append(dict(READS[-1]))
        objects.append(read(D,LINK_REV,LINK+"/external/"+original.split("/")[-1]));versions.append(dict(READS[-1]))
        assert len({v["sha256"] for v in versions})==1,(name,versions)
        definitions[name]=dict(canonical=versions[2],equivalent_copies=[versions[i] for i in (0,1,3)],
            byte_identical=True,embedded_registry_sha256=objects[0].get("registry_sha256"))
        if name=="registry":registry=objects[0]
        else:bindings=objects[0]
    layers=[e for g in registry["groups"] for e in g["entries"]];assert len(layers)==99
    assert len(bindings["points"])==13
    pinmap=read(D,DATA_CURRENT,PIN+"/ninety-nine-pin-map.json");pinmap_source=dict(READS[-1])
    tier=read(D,DATA_CURRENT,PIN+"/ninety-nine-pins-tier1-summary.json");tier_source=dict(READS[-1])
    declared=definitions["registry"]["canonical"]["sha256"]
    assert pinmap["registry_sha256"]==tier["registry_sha256"]==declared
    for item in pinmap["field_map"]+tier["field_map_added"]:
        for l in item.get("layers") or []:assert layers[l["index"]-1]["layer_id"]==l["layer_id"]
    definitions["unassigned_field_patterns"]=[item["pattern"] for item in pinmap["field_map"]+tier["field_map_added"] if not item.get("layers")]
    definitions["pin_map"]=pinmap_source;definitions["tier1_pin_summary"]=tier_source
    definitions["pin_map_hash_matches_registry_file_bytes"]=True
    definitions["hash_note"]="The registry's embedded registry_sha256 is a separate declared digest, not its complete-file byte SHA256. Ledger pin maps are checked against the complete-file digest."
    sources={};catalogs=[]
    for day in ("20231002","20231003","20231017","20231018","cross"):
        cat=read(D,BULK_REV,BULK+"/"+day+"/CATALOG.json");catalogs+=cat
        for t in cat:
            e=dict(t["source"]);e["sha256"]=t["source_sha256"]
            e["checksum_evidence"]="measured and blob-verified by completed source-clock run"
            e["role"]="pin_annotations_with_embedded_rows" if e["collection"]=="ccode_existing_pins" else "source_data"
            e["clock_sidecar"]=dict(repository=D,revision=BULK_REV,path=BULK+"/"+day+"/rows/"+t["table_id"]+"/TABLE.json",counts=t["counts"])
            sources[coord(e)]=e
    assert len(catalogs)==553
    manifest=read(D,DATA_CURRENT,"MANIFEST.json")
    unavailable=[]
    for original_entry in manifest["entries"]:
        entry=dict(original_entry)
        if entry["path"].endswith("/"):
            unavailable.append(dict(source_manifest_entry=entry,status="historical_archive_reference_not_an_available_file",action="do not fetch prohibited external storage; resolve from GitHub final handoff"))
            continue
        path=entry.get("markets_data_path") or entry["path"]
        if not entry.get("sha256") or entry.get("bytes") is None:
            fetch(D,DATA_CURRENT,path);entry["sha256"]=READS[-1]["sha256"];entry["bytes"]=READS[-1]["bytes"]
        e=dict(repository=D,revision=DATA_CURRENT,path=path,sha256=entry["sha256"],bytes=entry["bytes"],
               collection="data_repository_manifest",day=entry.get("session") or entry.get("utc_day"),
               checksum_evidence="declared in immutable source MANIFEST.json; not newly rehashed here",
               source_manifest_entry=entry,
               role="pin_annotations_with_embedded_rows" if "/claude-code-pins/" in path and ".jsonl" in path else "source_data",
               clock_status="requires final handoff reconciliation unless an existing clock sidecar alias is present")
        if coord(e) not in sources:sources[coord(e)]=e
    groups=group_sources(list(sources.values()))
    duplicates=[dict(content_id=g["content_id"],canonical=g["canonical"],removed_from_independent_input_list=g["aliases"]) for g in groups if g["aliases"]]
    for g in groups:
        variants=[g["canonical"]]+g["aliases"]
        g["clock_attachments"]=[e["clock_sidecar"] for e in variants if "clock_sidecar" in e]
        g["annotation_not_independent_sample"]=any(e["role"]=="pin_annotations_with_embedded_rows" for e in variants)
    # A duplicate file must not appear twice in the active list; distinct bytes stay distinct.
    assert len(groups)==len({(s["sha256"],s["bytes"]) for s in sources.values()})
    overlaps=[dict(content_id=g["content_id"],source=g["canonical"],
        treatment="attach layer/clock annotations; embedded row is not an additional independent observation when its source row exists; unmatched embedded rows remain available",
        exact_row_aliases_verified=False) for g in groups if g["annotation_not_independent_sample"]]
    summary=dict(status="PREPARATION_ONLY_AWAIT_EXPLICIT_USER_START",analysis_authorized=False,evidence_frozen=False,
        registry_match=True,bindings_match=True,pin_map_match=True,registry_layers=99,bound_points=13,
        prior_clock_inventory_files=len(catalogs),source_coordinates=len(sources),unique_file_contents=len(groups),
        duplicate_file_aliases_removed=len(sources)-len(groups),duplicate_groups=len(duplicates),
        annotation_ledger_contents=len(overlaps),physical_source_deletions=0,unavailable_archive_references=len(unavailable),
        remaining=["Ccode final completion handoff and changed-file list","Refresh this manifest against final revisions",
        "Resolve remaining row-level overlap from exact source coordinates before counting pooled observations",
        "Check clocks on new timed files","Explicit user instruction to begin reanalysis"],
        dedup_scope="byte-identical file copies only; repeated equal-valued rows are not assumed the same event; related projections remain distinct views")
    packet=dict(schema="markets.shared_reanalysis_inputs.v1",**summary,definitions=definitions,active_inputs=groups,
        supporting_packets=[dict(repository=D,revision=LINK_REV,path=LINK,role="lifecycle and event links, original renders, informational material and external histories"),
                            dict(repository=D,revision=BULK_REV,path=BULK,role="clock/layer annotations; not a second market-event population")],
        row_identity_rule="source-defined population + whole-parent/event identity + own clock + source ordinal; source views and ledgers are joined, never concatenated as independent evidence",
        correction_precedence="use verified corrected horizon clocks from the bulk sidecars for the older Ccode inputs; original known-wrong stamps are not competing active definitions")
    write(out,"CANONICAL_INPUTS.json",packet);write(out,"DEFINITION_CHECK.json",definitions)
    write(out,"DUPLICATE_ALIASES.json",duplicates);write(out,"ANNOTATION_OVERLAPS.json",overlaps)
    write(out,"UNAVAILABLE_REFERENCES.json",unavailable)
    write(out,"SUMMARY.json",summary);write(out,"SOURCES.json",READS)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":
    import sys
    # Unit checks: identical bytes alias; different content never aliases; every scope retained.
    a=dict(repository=M,revision="a",path="x",sha256="x",bytes=1)
    b=dict(a,path="y",day="20231003");c=dict(a,path="z",sha256="z")
    q=group_sources([a,b,c]);assert len(q)==2 and sum(len(x["aliases"]) for x in q)==1
    main(sys.argv[1])
