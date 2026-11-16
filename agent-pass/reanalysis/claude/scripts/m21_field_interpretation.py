"""M21: FIELD_INTERPRETATION.csv: every distinct substantive field name across the 553 inventoried source files (1,775 names, 157 table types),
assigned to a measurement family with meaning, clock role, registry layers (from the pin catalogs), the module/claims that interpreted the family,
and an explicit status: interpreted / provenance_or_identity / outcome_label_or_reveal / model_output / uninterpreted_with_reason."""
import json, re, csv, collections
from common import *
inv = json.load(open(OUT / "m21_field_inventory.json")); fields = inv["fields"]; tables = inv["tables"]
field_tables = collections.defaultdict(set)
for t, fs in tables.items():
    for f in fs: field_tables[f].add(t)
layers = collections.defaultdict(set)
for cat in (ROWCLOCK).glob("*/CATALOG.json"):
    for e in json.load(open(cat)):
        for f, ls in e["field_layer_ids"].items():
            for l in ls: layers[f].add(l)
RULES = [  # (regex, family, meaning, clock_role, modules, status)
 (r"(_ns$|_ns_|^ts_|_utc$|epoch_s|known_by|receive|publication|published|timestamp|clock|cutoff|cursor|ordinal|group$|_group$|segment|sequence|record_index|input_cursor|first_cursor|close_cursor|window_open|anchor_ns|birth_second|t0$|t0_|second$|^second|relative_s|^k$|^ks$|horizon|lead_s|delay_s|age_s|age_ns|duration|elapsed|lag_s|lag_|_s$)", "clocks_and_ordering", "event / receive / known-by / decision clocks, cursors and ordinals; the decision-time boundary of every claim", "clock", "all modules (decision clocks); M1-5, LA-marks, M8-5", "provenance_or_identity"),
 (r"(sha256|hash|manifest|path$|file$|repository|revision|commit|git_blob|bytes$|receipt|branch|run$|source|session$|day$|^day|instrument|symbol|contract|tape|schema|version|role|disposition|coverage|matched|match$|status|reason|note|scope|kind$|population|variant|definition|label$|seed$|mode$|flags?$|snapshot|reset|bad_receive|member$|in_member|excluded|missing|undefined|censor|n_valid|available|complete_history|row$|instance$|sample_id|family_id|candidate_id|event_id|parent_id|order_id|^id$|_id$)", "identity_provenance_flags", "identities, source coordinates, completeness and censoring flags; join keys", "n/a", "COVERAGE, M9, M13 (joins)", "provenance_or_identity"),
 (r"(^bid|^ask|best_bid|best_ask|^mid|mid_|midpoint|price|quote|spread|spr|tick|dmid|dspr|q_|qchg|qage|touch|tgt_sz|own_sz|tgt_n|own_n|bsz|asz|an$|bn$|level|near|depth|imbalance|imb|full_|top10|rank|dbid|dask|ret_|dm_|am_|move|chg_|d60|d300|d600|d1$|d5$|d20$|tk_|realised|extreme|retrace|recover|return|displace|range|path|efficiency|disp$|net$|oriented|with_|against|first.*t$|either)", "price_book_and_response", "price level/path, quotes, spread, touch sizes and order counts, depth and imbalance, oriented moves and recoveries", "cutoff / completed second / fixed horizon", "M1, M2, M4, M5, M8, M8c, LA-*, M16, M17, M20", "interpreted"),
 (r"(add|cancel|cx|fill|modify|mod_|replace|clear|trade|print|aggress|lots?$|lots_|buy|sell|unknown|flow|net_|ratio|roll|fresh|expir|classified|supA|supB|timb|churn|F_|refill|repl|absor|withdraw|deplet|resil|recruit|sweep|order_|queue|fifo|ahead|burst|volume|vol_|activity|n_trades|event_count|count$)", "orders_flow_and_liquidity", "order lifecycle actions by side, fills vs cancels, aggressor lots, rolling windows and ratios, replenishment/withdrawal, activity", "completed second / group close", "M3, M4, M5, M6, M8, M8c, LA-*, M16, M17, M18, M20", "interpreted"),
 (r"(dipole|dip_|polarity|pol$|orientation|SAME|FLIP|prominence|baseline|threshold|magnitude|peak|competing|winning|recognition|recog|available_second|nominal|dispatch|life|runway|exhaust|confirm|onset|seed_state|a_state|state$|arc|pre_arc|zero_within|t50|t25|t10|late_pressure|info_horizon|aftermath|mfe|mae|cls$|flip|hold_share|same_as_prev|prev_gap|next_gap|next_|predecessor|ancestry|chain|family_proxy|pre_family|proxy)", "dipole_lifecycle_and_state", "detector operands, birth/recognition clocks, orientation, lifetime and exhaustion marks, seed/a-state classes, successor relations", "birth second / completed second / recognition", "M1, M6, M7, M12, M16, M17, M18, M20, LA-*", "interpreted"),
 (r"(mae$|mse|ridge|arm$|fold|train|test|alpha|coef|rho|corr|pearson|spearman|z_|z$|chunks|line|band|draw|shift|null|control|ctl_|p5$|p25|p50|p75|p95|median|mean|share|quantile|tercile|quartile|percentile|dist_|distance|merge|gap$|groups_before|largest|residual|form$|fit|predict|forecast|hit$|v1|v2a|v2b|v3|scale_|loo|score|support|cell|bucket|regime|hour|class)", "statistics_models_and_cells", "model arms, fits, correlations, reference draws, controls, quantiles and cell labels", "n/a (aggregate)", "M4, M5, M8b, M14, M17 (reused or recomputed per date)", "model_output"),
 (r"(cot|managed_money|storage|bcf|hdd|tmpf|wind|gas_burn|curve|slope|curvature|settled|traded|front|c1$|weather|mos\.|eia|calendar|prompt_expiry|external|series|point)", "external_context", "COT positioning, storage, weather forecasts/observations, power stack, futures curve; publication-clock aligned", "publication known-by", "M19, M19b", "interpreted"),
 (r"(root\.activity|root\.|ob_|sell\d|buy\d|total\d|flow\d|activity\d|mid_change\d|touch_change|touch_delta|same_price|display_change|prior_mid|lag\d)", "tier1_family_operands", "strict-pre root operands and order-level windows at family starts", "cutoff_ns", "M4, M8b", "interpreted"),
]
rows = []; stat = collections.Counter()
for f, n in sorted(fields.items(), key=lambda x: -x[1]):
    fam = meaning = clock = mods = status = None
    for pat, fa, me, cl, mo, st in RULES:
        if re.search(pat, f, flags=re.I): fam, meaning, clock, mods, status = fa, me, cl, mo, st; break
    if fam is None: fam, meaning, clock, mods, status = "unclassified", "field name not matched by any family rule; see its source table", "unknown", "", "uninterpreted_with_reason: no family rule; resolve from producer schema"
    stat[status] += 1
    rows.append(dict(field=f, occurrences_in_inventory=n, table_types="|".join(sorted(field_tables[f]))[:300], family=fam, meaning=meaning, clock_role=clock, registry_layers="|".join(sorted(layers.get(f, []))), interpreted_by=mods, status=status))
with open(OUT.parent / "FIELD_INTERPRETATION.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), dict(stat)); print(collections.Counter(r["family"] for r in rows).most_common())
print("unclassified sample:", [r["field"] for r in rows if r["family"] == "unclassified"][:60])
