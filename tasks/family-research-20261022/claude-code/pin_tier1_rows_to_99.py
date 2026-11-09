"""Pin the Tier 1 family-master rows of the four sessions (claude-pass-3day/tables/<session>/t1_family_master_flags.csv, one row per actual
first-observed family start, built by x18_tier1_days.py on branch claude/three-day-dipole-20261108) to the canonical 99-layer registry by timestamp.

Same ledger form as pin_rows_to_99.py (one record per row: the row verbatim, its ids, every absolute clock, its sources, and `pins` with layer
indices and ids, value, clock kind and the absolute clock of the measurement); the field map and clock rules are imported from there and
extended for this row file's fields: the retained ROOT operands and reference-group fields (measured as of the strict cutoff or at the
reference group's receive clock), the prior displacement and quote-change counts (cutoff), the order-level windows (cutoff, window ending at
start - 1 ns), and the outcomes at fixed horizons (outcome window from the start, named by horizon). Flags and context labels carry no clock
and are not pinned. Aggregates are never pinned; rows are never merged.
Usage: python3 -I pin_tier1_rows_to_99.py <path to the Markets worktree holding claude-pass-3day> <output dir>"""
import sys, re, json, gzip, csv, hashlib
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pin_rows_to_99 as P
TREE = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True); HERE = Path(__file__).resolve().parent
L = P.L; NS = P.NS
EXTRA = [
    (r"^root\.activity\.\d+\.(trade_buy_aggressor_qty|trade_sell_aggressor_qty|trade_aggressor_imbalance)$", [L["flow"], L["trades"]], "cutoff_ns"),
    (r"^root\.activity\.\d+\.event_count$", [L["raw"], L["flow"]], "cutoff_ns"),
    (r"^root\.activity\.\d+\.top_level_cancel_qty_derived$", [L["cancels"], L["depletion"]], "cutoff_ns"),
    (r"^root\.(bid_depth_full|ask_depth_full|depth_imbalance_full|depth_imbalance_n)$", [L["depth"], L["spread_imb"]], "cutoff_ns"),
    (r"^root\.(best_bid|best_ask|mid|spread)$", [L["levels"], L["spread_imb"]], "cutoff_ns"),
    (r"^(start_event_ns|window_start_ns|input_cursor|source_ordinal|cursor_cap|first_cursor|pre_source_ordinal|known_by_ns|pre_input_cursor|pre_book_age_s)$", [L["known_by"], L["recv"], L["raw"]], "cutoff_ns"),
    (r"^(price|price_age_s|pre120_change|pre_direction)$", [L["legacy_price"], L["path"]], "cutoff_ns"),
    (r"^(ref_group|ref_recv_ns)$", [L["known_by"], L["recv"]], "ref_recv_ns"),
    (r"^(ref_mid|ref_spread|ref_bid_sz|ref_ask_sz|ref_bid_n|ref_ask_n|touch_imb|touch_n_imb|spread_ticks)$", [L["levels"], L["spread_imb"]], "ref_recv_ns"),
    (r"^(chg|tk|grp)_(\d+)s$", [L["path"], L["outcome"]], "outcome_from_start_h"),
    (r"^(prior_tk|quote_changes|groups)_\d+s$", [L["path"], L["levels"]], "cutoff_ns"),
    (r"^ob_trade_(sell|buy)agg_\d+s$", [L["trades"], L["flow"]], "cutoff_ns"),
    (r"^ob_fill_[ab]_\d+s$", [L["fills"]], "cutoff_ns"),
    (r"^ob_rm_fill_[ab]_\d+s$", [L["fills"], L["cancels"], L["identity"], L["depletion"]], "cutoff_ns"),
    (r"^ob_rm_cx_(touch|near)_[ab]_\d+s$", [L["cancels"], L["depletion"]], "cutoff_ns"),
    (r"^ob_(n_)?add_(touch|near)_[ab]_\d+s$", [L["adds"], L["recovery"]], "cutoff_ns"),
    (r"^ob_mod_touch_[ab]_\d+s$", [L["modifies"]], "cutoff_ns"),
    (r"^ob_net_(bid|ask)_\d+s$", [L["adds"], L["cancels"], L["recovery"], L["depletion"]], "cutoff_ns"),
    (r"^(f60|f5|f1|pattern)$", [L["flow"]], "cutoff_ns"),
    (r"^(dsg|dsg_n)$", [L["depth"], L["spread_imb"]], "cutoff_ns"),
    (r"^(occurrence_count|start_basis|instrument_id|sample_id|start_utc|recorded_forecast_rows|forecast_disposition|continuous_book_replay|snapshot_member|reset_member|bad_receive_clock_member|in_member|utc_hour|settle_tag|chg_ticks)$", None, None),
]
FIELD_MAP = EXTRA + P.FIELD_MAP   # the specific patterns first; the shared map still covers family_id, instance, chronological_quarter, start_recv_ns, cutoff_ns
def clock_for(rule, row, day0, field=None):
    if rule == "ref_recv_ns":
        v = row.get("ref_recv_ns"); return None if v is None else ("known_by_receive_ns", int(v) // NS, int(v), P.utc_ns(int(v)))
    if rule == "outcome_from_start_h":
        h = int(re.search(r"_(\d+)s$", field).group(1)); v = row.get("start_recv_ns")
        if v is None: return None
        e = int(v) + h * NS; return (f"outcome_window_start_plus_{h}s", e // NS, e, P.utc_ns(e))
    return P.clock_for(rule, row, day0)
def num(v):
    if v in ("", None): return None
    if v in ("True", "False"): return v == "True"
    # Parse integer text before float: receive clocks exceed binary64 precision.
    if re.fullmatch(r"[+-]?\d+", v): return int(v)
    try:
        f = float(v); return int(f) if f.is_integer() and ("." not in v or v.endswith(".0")) and abs(f) < 1e18 else f
    except ValueError: return v
def pin_row(row, day0, layers):
    pins, unknown = [], []
    for field, value in row.items():
        hit = False
        for pat, ls, rule in FIELD_MAP:
            if re.search(pat, field):
                hit = True
                if ls is None: break
                c = clock_for(rule, row, day0, field)
                if c is None: break
                kind, es, ns, u = c
                pins.append(dict(field=field, value=value, layers=[dict(index=i, layer_id=layers[i]["layer_id"], group_id=layers[i]["group_id"]) for i in ls], clock_kind=kind, clock_epoch_s=es, clock_ns=ns, clock_utc=u))
                break
        if not hit: unknown.append(field)
    return pins, unknown
def main():
    layers, reg_sha = P.load_registry(); manifest = json.loads((HERE / "data-manifest.json").read_text()); by_path = {e["path"]: e for e in manifest["entries"] if e.get("path")}
    grand = {}
    for tag, day0 in P.DAY0.items():
        day = P.DAY[tag]; sess = TREE / f"tasks/family-research-20261022/claude-pass-3day/tables/{day}"
        rec = json.loads((sess / "t1_receipt.json").read_text()); idx_path = f"tasks/family-research-20261022/family-replication/run-42566535537-1/family-{day}/chronological-instance-index.csv"
        src = dict(tape_members=[dict(utc_day=d, path=f"data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst", commit=c, sha256=by_path.get(f"data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst", {}).get("sha256")) for d, c in P.MEMBERS[tag]],
                   family_index=dict(path=idx_path, markets_data_commit="7b50d634", sha256=rec["family_index_sha256"], run="42566535537"),
                   session_groups=dict(origin="rebuilt from the tape members (c00 -> c03 -> c01b), prior member from 21:00 UTC to the 21:00 UTC close", groups=rec["groups"]),
                   order_level_windows=dict(origin="reconstructed records of the date member (c03, c04 enrich/Windows), window ending at start_recv_ns - 1 ns; NaN where the window begins before the member"),
                   row_file=f"tasks/family-research-20261022/claude-pass-3day/tables/{day}/t1_family_master_flags.csv", branch="claude/three-day-dipole-20261108", excluded=rec["excluded_no_earlier_group"])
        counts = Counter(); unknown_fields = Counter(); n_rows = n_pins = 0; out = OUT / f"ninety-nine-pins-tier1-{tag}.jsonl.gz"
        with gzip.open(out, "wt") as fo, (sess / "t1_family_master_flags.csv").open() as fi:
            for ordinal, raw in enumerate(csv.DictReader(fi)):
                row = {k: num(v) for k, v in raw.items()}
                ids = dict(instance=row.get("instance"), family_id=row.get("family_id"))
                clocks = {k: v for k, v in row.items() if k.endswith("_ns") or k.endswith("_utc")}
                clocks.update(start_utc_ns=P.utc_ns(int(row["start_recv_ns"])), cutoff_utc=P.utc_ns(int(row["cutoff_ns"])), ref_recv_utc=P.utc_ns(int(row["ref_recv_ns"])))
                pins, unknown = pin_row(row, day0, layers); unknown_fields.update(unknown)
                for pin in pins:
                    for l in pin["layers"]: counts[l["index"]] += 1
                fo.write(json.dumps(dict(session=tag, file=out.name.replace("ninety-nine-pins-tier1-", "t1_family_master_flags-").replace(".jsonl.gz", ".csv"), ordinal=ordinal, ids=ids, clocks=clocks, sources=src, pins=pins, row=row), default=str) + "\n")
                n_rows += 1; n_pins += len(pins)
        grand[tag] = dict(rows=n_rows, pins=n_pins, fields_without_layer=sorted(unknown_fields), pins_by_layer={f"{i:02d} {layers[i]['layer_id']}": n for i, n in sorted(counts.items())}, output=out.name, bytes=out.stat().st_size, sha256=hashlib.sha256(out.read_bytes()).hexdigest())
        print(tag, "rows", n_rows, "pins", n_pins, "layers touched", len(counts), "fields without layer", sorted(unknown_fields), "bytes", out.stat().st_size)
    (OUT / "ninety-nine-pins-tier1-summary.json").write_text(json.dumps(dict(registry_sha256=reg_sha, field_map_added=[dict(pattern=p, layers=[dict(index=i, layer_id=layers[i]["layer_id"]) for i in ls] if ls else None, clock_rule=r) for p, ls, r in EXTRA],
                                                                               clock_kinds_added=["known_by_receive_ns (reference group at the cutoff)", "outcome_window_start_plus_<h>s"], sessions=grand), indent=2) + "\n")
if __name__ == "__main__":
    main()
