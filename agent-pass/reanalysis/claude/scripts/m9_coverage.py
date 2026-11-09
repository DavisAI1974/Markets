"""M9: COVERAGE.csv from the frozen final manifest (markets-data e7b1c4a, final-42593665910-1 CANONICAL_INPUTS.json) joined to the row-clock
CATALOG field lists (9bfffd6d). One row per distinct content (1,296) plus the three unavailable archive references. Interpretation category and the
analysis module that read it are assigned by path pattern; files not read by any module are marked 'inventoried_not_separately_analyzed'."""
import json, pathlib, re, csv, glob, os
from common import *
SP = pathlib.Path(os.environ.get("REANALYSIS_PACKET", "/tmp/claude-0/-home-user-Markets/9d08bbd8-e004-5d31-9253-a2d3c0d0bcc4/scratchpad/packet_final"))
packet = json.load(open(SP / "CANONICAL_INPUTS.json"))
unavail = json.load(open(SP / "UNAVAILABLE_REFERENCES.json"))
# field lists from row-clock catalogs
fields = {}
for cat in glob.glob(str(ROWCLOCK / "*/CATALOG.json")):
    for e in json.load(open(cat)):
        fields[e["source_sha256"]] = dict(fields=e["source_fields"], rows=e["counts"].get("rows"), clocks=e["counts"].get("clocks"), unclocked=e["counts"].get("aggregate_or_unclocked_retained"), layers=sorted({l for v in e["field_layer_ids"].values() for l in v}))
RULES = [

 (r"claude-pass-3day/figures/.*t5_chart_reconciliation\.csv$", "chart reconciliation (plotted counts = table rows)", "provenance", "COVERAGE"),
 (r"claude-pass-3day/run/.*\.sh$", "suite run scripts", "producer_code_context", "not_data"),
 (r"combined-events/.*a-all-family-occurrences\.csv\.gz$", "all structural family occurrences (not only firsts)", "population_definition", "M4,REPORT"),
 (r"claude-code/(data-manifest|ninety-nine-pin-map|trace-events)\.json$", "Ccode data manifest / pin map / trace events", "provenance", "COVERAGE"),
 (r"claude-pass-3day/crossday/.*\.xlsx$", "three-day tables workbook", "informational_context", "REPORT"),
 (r"claude-code/market-fundamentals-primer\.(pdf|md)$", "market fundamentals primer (reference text)", "informational_context", "REPORT"),
 (r"claude-code/\.gitignore$", "ignore file", "not_data", "not_data"),
 (r"replay-artifacts/.*candidate-input-summary\.json$", "candidate input summary", "provenance", "COVERAGE"),
 (r"agent-pass/scripts/.*\.mjs$", "Codex workbook script", "producer_code_context", "not_data"),
 (r"native-dipole/.*-paths\.csv\.gz$", "native per-second book/flow paths -60 s..recognition (candidate+2 controls)", "decision_time_inputs_and_outcomes", "M1,M8"),
 (r"native-dipole/.*-life-paths\.csv\.gz$", "native rolling-20s flow life path after anchor (fresh/expired buy/sell, ratio)", "decision_time_inputs_and_outcomes", "M1,M10"),
 (r"native-dipole/.*-life-measurements\.csv$", "operational lifetime (opposite_hold3) per candidate/control", "endpoint_convention", "M1"),
 (r"native-dipole/.*-lag-measurements\.csv$", "nominal/recognition/dispatch lag per candidate", "clock_decomposition", "M1"),
 (r"native-dipole/.*-candidate-operands\.csv$", "recorded detector operands at birth", "decision_time_inputs", "M1,M10"),
 (r"native-dipole/.*-path-members\.csv$", "path membership, regime/activity buckets, controls", "population_definition", "M1"),
 (r"native-dipole/.*-(detector|detected|birth-differences|seconds-disposition).*", "detector recovery (native_action vs completed_group)", "detector_audit", "CONFLICTS"),
 (r"native-dipole/.*-(first-footprint|lag-footprints|footprint-endpoint|cross-side|moonshot|detector-free|inclusive-legacy).*", "M1/M2 structural events and within-lag footprints", "retrospective_footprints", "M10,REPORT"),
 (r"native-dipole/.*-(pair-distances|all-hierarchy|grouping|operator|figure-reconciliation|cases|case-raw|matching-audit|part2|part3).*", "shape structure / governing-form residuals / reconciliation", "informational_structure", "REPORT"),
 (r"native-dipole/.*figures/.*\.png$", "native figure (collection view)", "informational_render", "not_measured_input"),
 (r"native-dipole/.*(xlsx|MANIFEST|receipt|json)$", "workbook / manifest / receipt", "provenance", "COVERAGE"),
 (r"combined-events/.*a-trades\.parquet$", "all prints with event/receive/available clocks", "raw_timed_records", "M1,M0"),
 (r"combined-events/.*a-(print-legs|price-stretches)\.parquet$", "print legs / equal-price stretches (retrospective spans)", "retrospective_navigation", "M0"),
 (r"combined-events/.*a-family.*", "structural family firsts/windows/prechanges/neighbors/occurrences", "population_definition", "M4,REPORT"),
 (r"combined-events/.*a-(dipole-clocks|trade-dipole-overlaps)\.parquet$", "archived recognition clocks; trade overlaps", "clock_decomposition", "M1"),
 (r"combined-events/.*b-signals\.parquet$", "pressure signals (size-one, early-falling, retreat) with prior flow", "decision_time_inputs", "M3"),
 (r"combined-events/.*b-quote-episodes\.parquet$", "thin-touch quote episodes: onset, ending, duration", "decision_time_inputs_and_outcomes", "M3"),
 (r"combined-events/.*b-delayed-outcomes\.parquet$", "1/5/30 s hypothetical quote observations after signals", "outcomes", "M3"),
 (r"combined-events/.*b-next-group-arrival\.parquet$", "per completed group: next print arrival, mid direction", "price_to_behavior", "M8,M0"),
 (r"combined-events/.*c-large-quote-events\.parquet$", "midpoint jumps >=2 ticks with responses and recovery", "price_to_behavior_and_outcomes", "M2"),
 (r"combined-events/.*c-prior-signal-to-large-move\.parquet$", "signals preceding large moves", "behavior_to_price", "M2"),
 (r"combined-events/.*c-quote-ending-mechanisms\.parquet$", "adds/cancels/fills at episode endings", "price_to_behavior_mechanics", "M8"),
 (r"combined-events/.*c-selected-(actions|book-context).*", "individual order actions / book context around large moves", "raw_timed_records", "inventoried_not_separately_analyzed"),
 (r"combined-events/.*cross-study-(event-links|condition-outcomes).*", "joint condition/outcome links across studies", "joint_context", "M3"),
 (r"combined-events/.*(analysis-summary|verification|input-manifest|MANIFEST|RUN_STATUS).*", "study receipts", "provenance", "COVERAGE"),
 (r"family-replication/.*chronological-instance-index\.csv$", "first-observed family starts with strict-pre root operands", "decision_time_inputs", "M4"),
 (r"family-replication/.*flow-book-discovery-v1/(opportunities|outcomes).*", "family opportunities and outcomes at 1/5/20/60/300 s", "decision_time_inputs_and_outcomes", "M8b"),
 (r"family-replication/.*flow-book-discovery-v1/(arm-metrics|arm-predictions|cohort-outcomes|chronological-splits|activity-control.*)", "four-arm ridge arms, cohorts, controls", "model_comparison", "M8b"),
 (r"family-replication/.*prebirth.*", "family prebirth matched contrasts", "behavior_to_price", "M8b"),
 (r"family-replication/.*primer.*", "primer next-price-change responses and sensitivities", "behavior_to_price", "M8b"),
 (r"family-replication/.*(receipt|manifest|MANIFEST|RUN_STATUS|provenance|reproduction|coordinates).*", "receipts and provenance", "provenance", "COVERAGE"),
 (r"four-day-extensions/.*continuous-prebirth-v1/(onsets|active-events|observations|onset-birth-labels|birth-links|outcomes|outcome-summary|summary).*", "continuous weakening-onset scan (10 predicates)", "behavior_to_price_and_dipole_decay", "M6"),
 (r"four-day-extensions/.*primer.*", "primer diagnostics (dipole population)", "behavior_to_price", "M8b"),
 (r"four-day-extensions/.*(verification|input-manifest|MANIFEST|README|method|png|summary\.csv).*", "receipts, method, chart", "provenance", "COVERAGE"),
 (r"whole-lifecycles/.*whole-lifecycles\.parquet$", "one whole parent per candidate/control with endpoint and clocks", "population_definition", "M1"),
 (r"whole-lifecycles/.*whole-lifecycle-points\.parquet$", "every original lifecycle second (native flow) with known-by clocks", "decision_time_inputs", "M1,M10"),
 (r"whole-lifecycles/.*(native-flow-source-clocks|component-windows).*", "native-flow completion clocks; component window links", "clock_decomposition", "M10"),
 (r"whole-lifecycles/.*(audit|catalog|manifest|MANIFEST|RUN_STATUS).*", "audit receipts", "provenance", "COVERAGE"),
 (r"claude-code-pins/.*tier1.*\.jsonl\.gz$", "Tier 1 family-master rows pinned to 99 layers (corrected ns clocks)", "annotation_ledger_embedded_rows", "M4,COVERAGE"),
 (r"claude-code-pins/.*ninety-nine-pins-oct..\.jsonl\.gz$", "Ccode per-event rows pinned to 99 layers", "annotation_ledger_embedded_rows", "M7,COVERAGE"),
 (r"claude-code-pins/.*", "pin summaries / verification", "provenance", "COVERAGE"),
 (r"claude-code-cases/.*", "ten NG dipole case views (context/tape)", "illustrative_cases", "CASES"),
 (r"claude-code-derived/.*", "Tier 2 shifted-Y null draws", "reference_distribution", "M5"),
 (r"replay-artifacts/.*candidate-inputs.*", "archived Native candidate inputs (recognition, operands)", "decision_time_inputs", "M1"),
 (r"replay-artifacts/.*(standalone-inputs|standalone-decisions|touch-print-decisions|size-one-mechanisms|large-quote-moves).*", "replay inputs/decisions (Oct 18 touch mechanisms)", "raw_timed_records", "inventoried_not_separately_analyzed"),
 (r"replay-artifacts/.*root-frames.*", "ROOT frame archive reference", "unavailable_archive", "COVERAGE"),
 (r"data/nymex_mbo/.*\.dbn\.zst$", "raw MBO tape (UTC day)", "raw_source_tape", "not_reprocessed"),
 (r"claude-code/.*(exhaustion-clock|runway|a-state|next-burst|chain-play|frozen-a|beyond-direction|stack-direction|other-things).*", "Ccode independent detector population per-event files", "decision_time_inputs_and_outcomes", "M7"),
 (r"claude-code/.*size-one.*", "Ccode size-one episodes / orders / tape / four-arm rows", "decision_time_inputs_and_outcomes", "M3(reference),COVERAGE"),
 (r"claude-code/.*(first-family-four-arm|sweep-cohort|dipole-post-recognition|divergent-pairs|cell-flip|trace-instance).*", "Ccode family/sweep/post-recognition rows and traces", "decision_time_inputs_and_outcomes", "M1,M4"),
 (r"claude-code/.*(renders|research-notes).*", "Ccode renders and notes", "informational_render", "not_measured_input"),
 (r"claude-code/.*\.py$", "Ccode producer code", "producer_code_context", "not_data"),
 (r"claude-code/.*summary\.json$", "Ccode per-file summaries", "informational_summary", "M7"),
 (r"claude-pass-3day/tables/.*/t1_.*", "Tier 1 chain tables (family master, cells, refill, four arms)", "decision_time_inputs_and_outcomes", "M4"),
 (r"claude-pass-3day/tables/.*/t2_.*", "Tier 2 grid couplings/state cells/lead-lag/forward stack per day", "measured_comparisons", "M5"),
 (r"claude-pass-3day/tables/.*/t3_.*", "regime scans", "measured_comparisons", "M5(reference)"),
 (r"claude-pass-3day/tables/dipole/.*", "dipole cohort tables (c24) and instance life paths", "decision_time_inputs_and_outcomes", "M1(reference)"),
 (r"claude-pass-3day/crossday/.*(t1x|t2x|pairs_full).*", "cross-day side-by-side tables", "measured_comparisons", "M4,M5"),
 (r"claude-pass-3day/crossday/.*(x0|es_|detector|crossday-).*", "event-study / detector ledgers / reconciliation", "measured_comparisons", "REPORT"),
 (r"claude-pass-3day/.*\.(md|png)$", "findings and figures", "informational_context", "REPORT"),
 (r"claude-pass-3day/.*\.py$", "suite code", "producer_code_context", "not_data"),
 (r"claude-pass-3day/.*(receipt|RECEIPT).*", "suite receipts", "provenance", "RECEIPT"),
 (r"claude-pass/tables/.*", "Oct 18 reference tables (Tier 1/2, crossday t4, crosswalk)", "measured_comparisons", "M4,M5(reference)"),
 (r"claude-pass/.*", "Oct 18 reference code/figures/workbook", "informational_context", "REPORT"),
 (r"lifecycle-data-links/.*(instance-pins|sample-clock-pins|signal-links|trade-links|detector-ledger-crosswalk|clock-differences|native-table-catalog).*", "lifecycle identity/clock joins", "clock_decomposition", "M10,COVERAGE"),
 (r"lifecycle-data-links/.*external/.*", "13 external points, 48 series, 99-layer registry", "external_context", "M10,COVERAGE"),
 (r"lifecycle-data-links/.*informational/.*", "informational copies of findings and renders", "informational_context", "REPORT"),
 (r"lifecycle-data-links/.*", "packet receipts", "provenance", "COVERAGE"),
 (r"agent-pass/.*\.md$", "Codex findings/handoffs", "informational_context", "REPORT"),
 (r"agent-pass/tables/.*", "Codex agent-pass tables (older copies)", "informational_structure", "COVERAGE"),
 (r"agent-pass/figures/.*", "Codex figures", "informational_render", "not_measured_input"),
 (r"agent-pass/.*\.(py|json|xlsx|txt|gitignore)$", "Codex code/receipts/workbook", "provenance_or_code", "COVERAGE"),
 (r"tasks/family-research-20261022/[^/]+\.md$", "discovery-era notes", "informational_context", "REPORT"),
 (r"MANIFEST\.json$", "markets-data manifest", "provenance", "COVERAGE"),
]
def classify(path):
    for pat, meaning, role, mod in RULES:
        if re.search(pat, path): return meaning, role, mod
    return "unclassified", "unclassified", "inventoried_not_separately_analyzed"
rows = []
for g in packet["active_inputs"]:
    c = g["canonical"]; meaning, cat, mod = classify(c["path"])
    f = fields.get(g["sha256"], {})
    rows.append(dict(content_id=g["content_id"], repository=c["repository"], revision=c["revision"], path=c["path"], bytes=g["bytes"], day=c.get("day"), source_role=c.get("role"), collection=c.get("collection"),
                     alias_count=len(g.get("aliases", [])), alias_paths="; ".join(f"{a['repository']}@{a['revision'][:7]}:{a['path']}" for a in g.get("aliases", [])[:6]),
                     meaning=meaning, interpretation_category=cat, analysis_modules=mod, availability="frozen_in_final_packet",
                     clock_status=f"rows={f.get('rows')};clocks={f.get('clocks')};unclocked_retained={f.get('unclocked')}" if f else "no_row_clock_sidecar(not_in_553_inventory)",
                     field_count=len(f.get("fields", [])) if f else None, fields="|".join(f.get("fields", [])) if f else "", registry_layers="|".join(f.get("layers", [])) if f else "",
                     annotation_not_independent_sample=g.get("annotation_not_independent_sample", False), unassessable_reason=""))
for u in unavail:
    e = u["source_manifest_entry"]
    rows.append(dict(content_id="unavailable", repository="DavisAI1974/markets-data", revision="", path=e["path"], bytes=e.get("bytes_uncompressed"), day=e.get("session"), source_role="archive", collection="archive_reference",
                     alias_count=0, alias_paths="", meaning="ROOT frame spool (full action frames), referenced only", interpretation_category="unavailable_archive", analysis_modules="none",
                     availability="NOT AVAILABLE in GitHub; S3 target prohibited by brief", clock_status="", field_count=None, fields="", registry_layers="", annotation_not_independent_sample=False,
                     unassessable_reason=f"{e['parts']} parts, {e['rows']} rows, {e['bytes_uncompressed']} bytes; not in any git repository; verified via family replication strict-pre snapshots only"))
with open(OUT.parent / "COVERAGE.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
import collections
print(len(rows), collections.Counter(r["interpretation_category"] for r in rows).most_common()); print(collections.Counter(r["analysis_modules"] for r in rows).most_common(12))
print("unclassified:", [r["path"] for r in rows if r["interpretation_category"] == "unclassified"][:30])
