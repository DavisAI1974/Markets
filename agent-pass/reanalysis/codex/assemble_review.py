"""Assemble independent interpretation ledgers from completed saved studies. No producer rerun."""
import collections, csv, gzip, hashlib, io, json, os, pathlib, re, sys
from decimal import Decimal
import source_review as sr

M="DavisAI1974/Markets"; D="DavisAI1974/markets-data"
REV=sr.REV; PACKET=sr.PACKET
SURVEY_REV="e2731854a42bcce04a8cf89e249603dc18d3b0f7"
SURVEY="tasks/family-research-20261022/codex-independent-review/run-42594360842-1"
ROOT="tasks/family-research-20261022/"
CODE_REV=os.environ["CODE_REV"]
def get(repo,rev,path):return sr.fetch(repo,rev,path)
def js(repo,rev,path):return json.loads(get(repo,rev,path))
def url(s):return f"https://github.com/{s['repository']}/blob/{s['revision']}/{s['path']}"
def writecsv(path,rows,keys=None):
    rows=list(rows)
    if not keys:keys=list(dict.fromkeys(k for r in rows for k in r))
    opener=gzip.open if str(path).endswith(".gz") else open
    with opener(path,"wt",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def section(path):
    p=path.lower()
    for names,title in [
        (["external","t7_","primer-eia","bindings"],"external-context-historical-sources-and-scale"),
        (["clock","detector","reconciliation","receipt","manifest","source"],"clock-and-measurement-rules"),
        (["size-one","divergent","refill","t1_","t1x","family-","order"],"liquidity-order-identities-and-short-horizons"),
        (["large","recovery","pressure","cross-study","case-tape","case-context","prior"],"price-and-market-behavior-in-both-directions"),
        (["coupling","t2","t3","t4","stack","metrics","watchlist"],"direction-regimes-and-combinations"),
        (["duration","runway","exhaustion","seed","chain","prebirth","precursor","continuous"],"duration-exhaustion-and-remaining-opportunity"),
        (["flow","dipole","shape","life"],"flow-dipoles-and-weakening")]:
        if any(n in p for n in names):return title
    return "sources-and-populations"
def fieldmeaning(field,path):
    f=field.lower();leaf=f.rsplit(".",1)[-1].replace("[]","")
    if re.search(r"(^|_)(ns|receive_ns|event_ns|cutoff_ns)$",leaf) or leaf.endswith("_ns"):
        return "Source nanosecond clock; distinguish event, receive, known-by and cutoff by original field","integer ns","clock-and-measurement-rules","defined by field; never float or interchangeable"
    if "cursor" in leaf or "ordinal" in leaf or leaf.endswith("_id") or "sha256" in leaf or leaf in ("row","row_index"):
        return "Identity, lineage, source order or checksum; not numeric predictive magnitude","identifier/index","sources-and-populations","navigation/provenance; not a forecast"
    if leaf.endswith("_utc") or leaf in ("epoch_s","t0_epoch_s"):
        return "Absolute source clock in its stated UTC/epoch representation","UTC or epoch seconds","clock-and-measurement-rules","source-specific availability"
    if leaf in ("t0","onset","confirm","recognition_s","next_t0","seed_known"):
        return "Source event coordinate; session-relative where declared; retain origin and separate event/availability","source seconds","clock-and-measurement-rules","retrospective t0/onset is not prospective recognition"
    if re.fullmatch(r"(prior|dm|am|dbid|dask|dspr)_\d+",leaf) and ("claude-pass" in path):
        return "Prior displacement or forward quote response as named; c12_tier2_build defines operands","ticks","price-and-market-behavior-in-both-directions","prior_* at cutoff; other listed fields are outcomes"
    if re.fullmatch(r"qchg_\d+",leaf) and "claude-pass" in path:
        return "Count of best-bid or best-ask price changes in prior named window","quote-change count","price-and-market-behavior-in-both-directions","prior closed groups"
    if leaf in ("tch_imb","tchn_imb") and "claude-pass" in path:
        return "Bid-minus-ask over sum, touch displayed size or order count respectively","dimensionless","direction-regimes-and-combinations","as-of last completed group"
    if re.fullmatch(r"(f_)?(buy|sell|net|fill|addt|addn|addf|cxt|cxn|cxf|rmf|sup|supdiff|add|cx)_(?:[ab]_)?\d+",leaf) and "claude-pass" in path:
        return "Side-specific executed/displayed lots from c04/c12; fill-linked reductions separated from unlinked removals","lots","price-and-market-behavior-in-both-directions","F_* is forward outcome; others prior window"
    if re.fullmatch(r"(refill|cxshare|imb)_(?:[ab]_)?\d+",leaf) and "claude-pass" in path:
        return "Ratio from original positive-denominator operands; missing is not zero","dimensionless","liquidity-order-identities-and-short-horizons","prior window; per-day terciles retrospective"
    if any(k in leaf for k in ("rho","auc","correlation","mae","mse","median","quantile","pvalue")):
        return "Saved aggregate/model diagnostic; not a per-event available signal","source diagnostic units; rho/AUC dimensionless, errors target-dependent","direction-regimes-and-combinations","retrospective aggregate"
    if leaf in ("pol","polarity","seed","seed_state","a_state","outcome","mode","status"):
        return "Source-defined state/category; birth, current state and later outcome must remain separate","category","flow-dipoles-and-weakening","consult source availability; outcome/state can be retrospective"
    if any(k in f for k in ("pin_definitions","sha","repository","revision","path","source","manifest","hash","reason","label","schema","version")):
        return "Provenance, annotation or descriptive metadata; retains origin and limits","metadata","sources-and-populations","not an independent market observation"
    return "Retained source field; detailed semantics/units must be read from its producer and linked definitions","not independently resolved here",section(path),"not certified decision-time solely by inventory"

def main(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    packet=js(D,REV,PACKET+"/CANONICAL_INPUTS.json")
    catalog=js(D,SURVEY_REV,SURVEY+"/SOURCE_CATALOG.json")
    groups=packet["active_inputs"];byid={g["content_id"]:g for g in groups}
    assert len(catalog)==len(groups)==1296
    # Reference inventories are not a second canonical input manifest.
    coverage=[];aliases=[]
    for s in catalog:
        g=byid[s["content_id"]];src=s["source"]
        coverage.append(dict(content_id=s["content_id"],source=url(src),population=src.get("day",src.get("collection","source-defined")),
          role=s["role"],bytes_verified=s.get("bytes_verified",False),rows=s["rows"],field_paths=s["fields"],
          individual_review=section(src["path"]),group_review=section(src["path"]),whole_review="REPORT.md#interpretation",
          clock=src.get("clock_status","See source clock fields and attached sidecar"),clock_fields=s.get("clock_fields",[]),
          field_ledger="coverage-fields-*.csv.gz keyed by content_id",
          status=s["status"],limitations="Semantic grouping is not visual inspection or certification of every field; unresolved fields retained.",
          duplicate_alias_count=len(g["aliases"]),clock_attachment=g.get("clock_attachments",[])))
        for a in g["aliases"]:aliases.append(dict(content_id=g["content_id"],alias=url(a),canonical=url(src),role="same bytes; preserve distinct source coordinates, never count copy as independent sample"))
    writecsv(out/"COVERAGE.csv",coverage)
    writecsv(out/"SOURCE_ALIASES.csv",aliases)
    fieldcounts=collections.Counter();batch=[];shard=0;fieldtotal=0
    for line in gzip.decompress(get(D,SURVEY_REV,SURVEY+"/FIELD_INVENTORY.jsonl.gz")).splitlines():
        r=json.loads(line);g=byid[r["content_id"]];meaning,units,sec,avail=fieldmeaning(r["field"],g["canonical"]["path"])
        row=dict(content_id=r["content_id"],field=r["field"],meaning=meaning,units=units,availability=avail,
                 individual_review="REPORT.md#"+sec,group_review="REPORT.md#"+sec,whole_review="REPORT.md#interpretation",
                 semantic_status="pending detailed field interpretation" if units=="not independently resolved here" else "class-level interpretation; source definition authoritative",
                 observations=r["observations"],missing_recorded=r["missing"],numeric_count=r["numeric_count"],
                 minimum=r["min"],maximum=r["max"],examples=r["examples"])
        batch.append(row);fieldcounts[row["semantic_status"]]+=1;fieldtotal+=1
        if len(batch)>=20000:
            shard+=1;writecsv(out/f"coverage-fields-{shard:03}.csv.gz",batch);batch=[]
    if batch:shard+=1;writecsv(out/f"coverage-fields-{shard:03}.csv.gz",batch)
    assert fieldtotal==sum(x["fields"] for x in catalog)
    # Structural stats count supplied scalar paths; absent dictionary keys are not observed.
    # NaN-like string values remain examples/non-numeric; missing_recorded is not exhaustive NA classification.
    texts={}
    def read(g):
        k=g["content_id"]
        if k not in texts:
            b=get(g["canonical"]["repository"],g["canonical"]["revision"],g["canonical"]["path"])
            assert hashlib.sha256(b).hexdigest()==g["sha256"]
            texts[k]=gzip.decompress(b).decode("utf-8-sig") if g["canonical"]["path"].endswith(".gz") else b.decode("utf-8-sig")
        return texts[k]
    def matching(substr):
        return [g for g in groups if substr in g["canonical"]["path"]]
    # Full existing relationship rows, including weak, undefined and adverse rows; no ranking filter.
    relcount=0;rel_sources=[]
    keys=["relationship_id","content_id","source","source_row_zero_based","interpretation_scope","record_json","limitations"]
    with gzip.open(out/"RELATIONSHIP_ROWS.csv.gz","wt",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for g in groups:
            p=g["canonical"]["path"]
            if not re.search(r"\.csv(?:\.gz)?$",p):continue
            if not re.search(r"coupling|crossday|metrics|summary|cells|correlation|redundancy|contribution|sensitivity|cohort-outcomes|setup-crosstabs|leadlag|fourarm|four-arm|refill|stack-variants",p,re.I):continue
            n=0
            for i,row in enumerate(csv.DictReader(io.StringIO(read(g)))):
                w.writerow(dict(relationship_id=f"{g['content_id']}:{i}",content_id=g["content_id"],source=url(g["canonical"]),
                  source_row_zero_based=i,interpretation_scope=section(p),record_json=json.dumps(row,ensure_ascii=False),
                  limitations="Original saved comparison. Source denominators, clocks and endpoints apply. No independent significance, causal or execution claim."));n+=1
            relcount+=n;rel_sources.append(dict(content_id=g["content_id"],source=url(g["canonical"]),rows=n))
    writecsv(out/"RELATIONSHIP_SOURCE_INDEX.csv",rel_sources)
    core=js(M,CODE_REV,"agent-pass/reanalysis/codex/core_claims.json")
    for c in core:
        refs=matching(c["source_match"]);c["source_references"]=[url(x["canonical"]) for x in refs]
        if not refs:c["source_references"]=["REPORT.md source index; historical source described there"]
        c["complete_comparison_ledger"]="RELATIONSHIP_ROWS.csv.gz; source field counts and limits remain in COVERAGE.csv"
    writecsv(out/"CLAIMS.csv",core)
    # Re-read direct evidence for corrected prose and the user's feedback question.
    coupling=matching("/crossday/t2x_coupling_crossday.csv")[0]
    cr=list(csv.DictReader(io.StringIO(read(coupling))))
    signed=collections.Counter(int(r["days_beyond_line"]) for r in cr if r["family"]=="signed move")
    assert signed[3]==5 and signed[2]==1 and signed[1]==4 and signed[4]==0, signed
    price=[dict(source=url(coupling["canonical"]),**r) for r in cr if r["x"].startswith(("prior_","qchg_"))]
    writecsv(out/"PRICE_RESPONSE_RELATIONSHIPS.csv",price)
    dump(out/"DIRECTIONAL_PROSE_CORRECTION.json",dict(source=url(coupling["canonical"]),signed_pairs_by_days_beyond_line=dict(signed),
      correction="Five signed pairs exceed the saved line on three dates, one on two, four on one, none on four. The prose 'not more than one day' is false."))
    # Exact case identities and original integer clocks; no JS number conversion.
    cases=[]
    ten=matching("claude-code-cases/cases-10.json") or matching("/claude-code/cases-10.json")
    t=ten[0]
    for i,r in enumerate(json.loads(read(t))):
        corrected_rule=r["rule"]
        if r["tag"]=="oct17" and r["t0"]==59992:corrected_rule="Largest absolute oriented +300s move in the 13:00 hour (selection code uses abs; source prose omits absolute)."
        cases.append(dict(case_id="selected-"+str(i+1),source=url(t["canonical"]),source_row=i,parent_id=r["candidate_id"],
          day=r["tag"],population="Frozen research detector matched to archived Native recognition",
          selection_rule=corrected_rule,observation_clock=r["t0_epoch_s"],known_by_clock="Original detector/seed availability; t0 is retrospective",
          recognition_receive_ns=str(r["recognition_receive_ns"]),recognition_cursor=r["recognition_cursor"],
          outcome_clock="move_seed_known_plus300 and confirm definitions in exhaustion_clock.py; preserve source row",
          interpretation="State/path example; selection uses later outcomes and cannot estimate prevalence.",
          limitations="Keep original parent and complete context/tape files; no intent or executable advantage inferred.",
          original_record_json=r))
    for tag in ("oct02","oct03","oct17"):
        g=matching("divergent-pairs-"+tag+".json")[0];obj=json.loads(read(g))
        for i,pair in enumerate(obj["pairs"]):
            for outcome in ("retreated","recovered"):
                if outcome not in pair:continue
                r=pair[outcome];e=r["episode"]
                cases.append(dict(case_id=f"{tag}-pair-{i}-{outcome}",source=url(g["canonical"]),source_row=f"pairs[{i}].{outcome}",
                  parent_id=f"{tag}:G{e['onset_group']}:{e['side']}",day=tag,population="Selected divergent size-one pairs",
                  selection_rule="Retain every supplied pair, both outcomes; original matched selection is illustrative",
                  observation_clock=str(e["onset_ns"]),known_by_clock=str(e["onset_ns"]),recognition_receive_ns="",recognition_cursor=e.get("onset_cursor"),
                  outcome_clock=str(e["end_ns"]),interpretation="Separate queue depletion, subsequent refill, same-price recovery and later fate",
                  limitations="Relative message offsets are rounded ms; do not fabricate exact ns from them. Original onset/end ns and cursors exact.",
                  original_record_json=r))
    writecsv(out/"CASES.csv",cases)
    # All registry roles plus source-defined dipole aspects; a mapping is not proof of measurement.
    definition=packet["definitions"]["registry"]["canonical"];registry=js(definition["repository"],definition["revision"],definition["path"])
    maps=[]
    for group in registry["groups"]:
        for e in group["entries"]:
            market=group["group_id"] in ("order_lifecycle","full_book_fifo_queue","microstructure_mechanics","legacy_observable_crosswalk","derived_geometry","prebirth_opportunity")
            maps.append(dict(layer_id=e["layer_id"],group=group["group_id"],definition=e["description"],source=url(definition),
             source_paths=e["source_paths"],units="Source-defined; registry is not a numerical observation",
             availability=group["activation_stage"],individual_role="Market/derived aspect" if market else "Context, provenance, control or outcome role",
             interactions="REPORT.md#price-and-market-behavior-in-both-directions; REPORT.md#dipole-sufficiency" if market else "Preserve lineage and availability; no independent confirming vote",
             decision_coverage="Conditional descriptive coverage; no universal direction/duration/execution sufficiency" if market else "Supports integrity/interpretation, not a trade signal by itself",
             incremental_evidence="Existing ablations/conditional tables only; complete layer-specific increment not measured",
             conflicts="Same input may underlie multiple layers; follow canonical names and actual measured fields",
             gaps="Membership does not establish measurement of every layer or runtime activation."))
    aspects=[
      ("Native trailing20 flow","Signed buy/sell operands and expiring contributions","lots and ratio","completed source seconds; action versus group attribution"),
      ("Native birth and recognition","Selected peak and actual observable emission","epoch seconds and integer ns","birth retrospective; recognition after group dispatch"),
      ("Five inherited operator outputs","Imbalance, entropy asymmetry, signed coupling, MI change, imbalance change","source operator units","after all window operands exist; empty halves explicit"),
      ("Family A state","Original 61-sample classifier","category","after full completed sample window; exact lineage required"),
      ("P/O/S/X seed and ancestry","Source-defined late-window predecessor state","category and source IDs","seed-known clock; no future predecessor membership"),
      ("Operational exhaustion endpoint","Third opposite-sign second convention","source seconds","confirmation after required observations; not natural market death"),
      ("Remaining distance clock","Frozen total less elapsed, separately calibrated versions","seconds to declared absolute tick distance","only after state/calibration known; no directional assertion"),
      ("Price/book path response","Exact price changes and later fixed-price liquidity/flow","ticks, raw prices, lots, orders","same-group mechanics versus subsequent known-by clocks"),
      ("Whole parent and component legs","Linked lifecycle, quote episode, print legs and observation windows","IDs and clocks","retrospective membership used only for navigation")]
    for name,meaning,units,clock in aspects:
        maps.append(dict(layer_id=name,group="source-defined dipole aspects (not new registry layers)",definition=meaning,source="REPORT.md source index",
          source_paths="See canonical catalog and original code; no renamed layer indices",units=units,availability=clock,
          individual_role=meaning,interactions="Fresh/expiring flow, liquidity and bidirectional price response",decision_coverage="See REPORT.md#dipole-sufficiency",
          incremental_evidence="Mixed/incomplete; no percent knowledge claim",conflicts="Separate populations and clocks",gaps="Execution, causal effects and natural endpoints unresolved"))
    writecsv(out/"DIPOLE_LAYER_MAP.csv",maps)
    # Supporting lifecycle packet: inspect every manifested file, preserving exact original external histories.
    support=packet["supporting_packets"][0];sm=js(support["repository"],support["revision"],support["path"]+"/MANIFEST.json")
    support_rows=[];extra_fields=[]
    for f in sm["files"]:
        src=dict(repository=support["repository"],revision=support["revision"],path=support["path"]+"/"+f["path"],role="supporting lifecycle/external/context")
        g=dict(content_id="support:"+f["sha256"],canonical=src,aliases=[],bytes=f["bytes"],sha256=f["sha256"])
        result,fields,samples=sr.inspect(g)
        support_rows.append(dict(source=url(src),content_id=g["content_id"],status=result["status"],rows=result["rows"],fields=result["fields"],
          bytes_verified=result.get("bytes_verified",False),reason=result.get("reason",""),interpretation=section(src["path"])))
        for r in fields:extra_fields.append(dict(source=url(src),field=r["field"],meaning=fieldmeaning(r["field"],src["path"])[0],
          availability="Original publication/known-by/row clock; histories cannot be shifted to another target date",
          observations=r["observations"],minimum=r["min"],maximum=r["max"],missing_recorded=r["missing"]))
    writecsv(out/"SUPPORTING_PACKET_COVERAGE.csv",support_rows)
    writecsv(out/"supporting-fields.csv.gz",extra_fields)
    # Bulk annotations already verified in original hosted run: inventory manifest pointers without pretending this is new raw data.
    support2=packet["supporting_packets"][1]
    bulk={}
    try:bulk=js(support2["repository"],support2["revision"],support2["path"]+"/MANIFEST.json")
    except Exception as exc:bulk={"unavailable_manifest":str(exc)}
    dump(out/"BULK_CLOCK_ANNOTATION_REFERENCE.json",dict(source=support2,manifest=bulk,interpretation="Completed clock annotation packet, not independent market samples. Individual source sidecars remain in COVERAGE.csv; not rerun."))
    dump(out/"UNAVAILABLE_REFERENCES.json",packet["unavailable_archive_references"])
    # Conflicts are authored against exact sources, never a cross-report reconciliation.
    conflicts=js(M,CODE_REV,"agent-pass/reanalysis/codex/conflicts.json")
    writecsv(out/"CONFLICTS.csv",conflicts)
    summary=dict(analyst="Codex",brief_revision=os.environ["BRIEF_REV"],evidence_revision=REV,
      source_contents=len(catalog),source_aliases=len(aliases),flattened_field_paths=fieldtotal,
      field_semantic_status_counts=dict(fieldcounts),relationship_rows=relcount,relationship_source_tables=len(rel_sources),
      core_claims=len(core),price_response_comparisons=len(price),cases=len(cases),registry_layers=len(maps)-len(aspects),
      source_defined_additional_aspects=len(aspects),supporting_files=len(support_rows),supporting_fields=len(extra_fields),
      supporting_unassessed=[r for r in support_rows if r["status"]=="unassessed"],
      limitations=["Field paths include metadata and nested keys, not independent features.",
        "Missing count includes explicit None/empty values; absent keys and all NaN-like strings are not a complete missingness census.",
        "Class-level field interpretations and structural parsing do not certify full semantic resolution.",
        "Images/PDFs retain source links; not every render visually inspected.",
        "Raw DBN bytes verified; completed reconstruction receipts reused, no producer rerun.",
        "No causal effect, net strategy performance or paper deployment claimed.",
        "Separate final reports; no reconciliation or joint synthesis."])
    assert summary["registry_layers"]==99 and len(cases)>=20
    assert all(r.get("bytes_verified") for r in support_rows), "support bytes failed"
    dump(out/"SUMMARY.json",summary)
    dump(out/"VERIFICATION.json",dict(source_count=True,all_field_paths_conserved=True,corrected_signed_pair_counts=True,registry_count=True,
          source_hashes_checked_for_reread_tables=True,source_integer_clocks_preserved=True,independent_report=True))
    manifest=[]
    for file in sorted(out.iterdir()):
        if file.is_file():
            b=file.read_bytes();manifest.append(dict(path=file.name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    dump(out/"MANIFEST.json",manifest)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main(sys.argv[1])
