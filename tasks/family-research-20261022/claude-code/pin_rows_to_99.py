"""Pin every per-event row of this work to the canonical 99-layer registry, by timestamp, keeping everything.

Input: the registry (artifacts/.../full-context-audit/canonical-99-registry.json, 99 layers in 18 groups) and
every row file in this directory for a session. Output: ninety-nine-pins-<tag>.jsonl.gz with one record per
row, carrying the original row verbatim (`row`), its natural ids, every absolute clock it has, its sources
(tape members with commits, export files with sha256 from data-manifest.json), and `pins`: one entry per
measured field that corresponds to registry layers, with the layer indices and ids, the field's value, the
clock kind (receive-second bin, receive nanoseconds, known-by, anchor, outcome) and the absolute clock the
measurement was taken at. Aggregates are never pinned: only row fields with a clock of their own. Nothing is
merged across rows or sessions. ninety-nine-pin-map.json records the field-to-layer map and the registry hash.
"""

import datetime as dt
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REG = ROOT / "artifacts/sqlite-triage/20261022/families/full-context-audit/canonical-99-registry.json"
NS = 1_000_000_000
DAY0 = {"oct02": 1696194000, "oct03": 1696280400, "oct17": 1697490000, "oct18": 1697576400}
MEMBERS = {"oct02": [("20231001", "603c4defcb28fbf66cb6afc8d7728b1d7b1ed268"), ("20231002", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202")],
           "oct03": [("20231002", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202"), ("20231003", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202")],
           "oct17": [("20231016", "603c4defcb28fbf66cb6afc8d7728b1d7b1ed268"), ("20231017", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202")],
           "oct18": [("20231017", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202"), ("20231018", "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202")]}
DAY = {"oct02": "20231002", "oct03": "20231003", "oct17": "20231017", "oct18": "20231018"}

# field pattern -> (registry layer indices, clock rule). Clock rules name which clock on the row the field was
# measured at: a session-second field (receive-second bin), a nanosecond field, or an offset from one.
L = dict(raw=29, adds=30, cancels=31, modifies=32, trades=34, fills=35, identity=37, depth=39, levels=40, queue_age=42,
         spread_imb=45, flow=48, depletion=49, recovery=50, path=52, legacy_price=54, legacy_flow=55, roll20=56, legacy_book=57,
         structure=58, dipole_state=59, family_geom=60, predecessor=61, paths=64, avail_ts=66, ev=72, recv=73, known_by=74,
         availability=75, confirm_clock=76, outcome=79, learned_dipoles=15, learned_families=14)
FIELD_MAP = [
    # exhaustion / detector rows (session seconds)
    (r"^t0$", [L["roll20"], L["dipole_state"], L["recv"]], "t0"),
    (r"^polarity$", [L["dipole_state"]], "t0"),
    (r"^(peak_abs|prominence|pre_arc_defined|zero_within_60)$", [L["dipole_state"], L["roll20"]], "t0"),
    (r"^onset$", [L["dipole_state"], L["confirm_clock"]], "onset"),
    (r"^confirm$", [L["confirm_clock"]], "confirm"),
    (r"^runway_s$", [L["dipole_state"], L["confirm_clock"]], "onset"),
    (r"^confirm_offset_s$", [L["confirm_clock"]], "confirm"),
    (r"^(seed_state|late_pressure_41_60|late_volume)$", [L["predecessor"], L["dipole_state"]], "seed_known_s"),
    (r"^(prev3_states|prev4_states|prev_gap_s|same_as_prev|next_starts_before_confirm)$", [L["predecessor"]], "t0"),
    (r"^info_horizon_local_s$", [L["availability"]], "info_horizon_local_s"),
    (r"^info_horizon_refractory_s$", [L["availability"]], "info_horizon_refractory_s"),
    (r"^archived_recognition_s$", [L["known_by"], L["structure"]], "archived_recognition_s"),
    (r"^archived_recognition_offset_s$", [L["known_by"]], "archived_recognition_s"),
    (r"^archived_flow_state$", [L["structure"], L["flow"]], "archived_recognition_s"),
    (r"^dip300_t0$|^dip300_vol_t0$", [L["flow"], L["legacy_flow"]], "t0"),
    (r"^dip300_info50$|^dip300_vol_info50$|^dip300_imb$|^dip300_vol$", [L["flow"], L["legacy_flow"]], "info50_or_anchor"),
    (r"^book_t0_aligned$", [L["spread_imb"], L["legacy_book"]], "t0"),
    (r"^(t10|t25|t50)$", [L["dipole_state"]], "t0"),
    (r"^move_|^mid_move_|^aftermath$", [L["path"], L["outcome"]], "outcome_from_t0"),
    (r"^(seed_known_s|remaining_runway_at_info50_s|confirmed_before_info50|confirmed_before_seed_known|censored)$", [L["availability"]], "t0"),
    # A classifier / runway duration / clock rows
    (r"^a_state$|^dist_fast$|^dist_persistent$|^proxy$", [L["learned_dipoles"], L["dipole_state"]], "anchor60"),
    (r"^pre_family|^arc_", [L["learned_families"], L["family_geom"]], "t0"),
    (r"^(price|mid)_(with|either)_\d+t(_censored)?$", [L["path"], L["outcome"]], "outcome_from_t0"),
    (r"^censor_time$", [L["outcome"]], "t0"),
    (r"^(day_scale|scale_v2a|scale_v2b|activity_tercile_loo|v1|v2a|v2b|v3|realised_with)$", [L["dipole_state"], L["avail_ts"]], "anchor60"),
    # beyond-direction / pre-birth rows
    (r"^pre(300|60)_", [L["flow"], L["path"]], "t0"),
    (r"^pre_book_", [L["spread_imb"]], "t0"),
    (r"^(plus60|known)_", [L["path"], L["flow"], L["spread_imb"], L["outcome"]], "anchor60"),
    (r"^(t0_|plus60_)?(spread|toward_depth|away_depth|toward_touch|away_touch|toward_share)", [L["depth"], L["levels"], L["spread_imb"]], "anchor60"),
    (r"^t0_to_60_", [L["depletion"], L["recovery"], L["depth"]], "anchor60"),
    (r"^next_", [L["predecessor"], L["outcome"]], "next_t0"),
    # stack / chain rows
    (r"^sources$", [L["flow"], L["spread_imb"], L["levels"], L["predecessor"]], "anchor60"),
    (r"^targets$|^return_ticks$", [L["outcome"]], "anchor60"),
    (r"^(eligible|reasons|prev4|is_play|expected_side|prev_seed|prev_a_state)$", [L["predecessor"]], "t0"),
    (r"^(flow_state|touch_relation|recognition_delay_s)$", [L["flow"], L["levels"], L["known_by"]], "recognition_receive_ns"),
    (r"^(recognition_receive_ns|recognition_cursor|recognition_group)$", [L["known_by"], L["recv"], L["structure"]], "recognition_receive_ns"),
    (r"^(candidate_id|birth_second|orientation|birth_classified_lots|last_window_classified_lots|prebirth_depth_state|quote_move_by_recognition|realised_by_recognition_ticks_in_birth_direction)$", [L["structure"], L["dipole_state"]], "birth_second"),
    (r"^recognition_touch_relation$", [L["levels"], L["spread_imb"]], "recognition_receive_ns"),
    (r"^move_ticks_after_recognition$|^moves$", [L["path"], L["outcome"]], "recognition_receive_ns"),
    # size-one episodes / tape / orders
    (r"^onset_ns$|^onset_group$|^onset_cursor$|^onset_first_cursor$", [L["recv"], L["raw"]], "onset_ns"),
    (r"^(side|original_price_raw|prior_touch|other_touch|new_best_is_better)$", [L["levels"], L["depletion"]], "onset_ns"),
    (r"^onset$", [L["levels"], L["depletion"]], "onset_ns"),
    (r"^(end_ns|end_group|end_cursor|ending_touch|outcome|end_vs_entry|entry_group|end_ms)$", [L["recovery"], L["outcome"], L["known_by"]], "end_ns"),
    (r"^(next_level|touch_check|next_gap_ticks|book_next|book_prior_orders)$", [L["depth"], L["levels"]], "onset_ns"),
    (r"^(additions|reprice_in|reprice_out|mutations_in_group)$", [L["adds"], L["modifies"], L["identity"]], "onset_ns"),
    (r"^reductions_fill_linked$", [L["fills"], L["cancels"], L["identity"], L["depletion"]], "onset_ns"),
    (r"^reductions_unlinked$", [L["cancels"], L["depletion"]], "onset_ns"),
    (r"^flow$", [L["fills"], L["cancels"], L["depletion"]], "onset_ns"),
    (r"^(order_id|origin|prior_onsets_by_order)$", [L["identity"], L["adds"], L["modifies"]], "onset_ns"),
    (r"^age_ms$", [L["queue_age"]], "onset_ns"),
    (r"^(fate|fate_delay_ms|fate_cursor)$", [L["cancels"], L["fills"], L["modifies"], L["outcome"]], "fate"),
    # first-family rows
    (r"^(family_id|instance|saved_match|chronological_quarter)$", [L["structure"], L["learned_families"]], "start_recv_ns"),
    (r"^(start_recv_ns|cutoff_ns|pre_close_cursor|pre_receive_ns|pre_cursor_agrees|pre_book_age_s)$", [L["known_by"], L["recv"], L["raw"]], "cutoff_ns"),
    (r"^(pre_bid_raw|pre_ask_raw|pre_bid_size|pre_ask_size|spread_ticks|touch_sign)$", [L["levels"], L["spread_imb"]], "cutoff_ns"),
    (r"^(buy|sell)(1|5|20|60)$|^d(1|5|20|60)$|^recent$", [L["flow"]], "cutoff_ns"),
    (r"^(bid_depth_full|ask_depth_full|depth_sign|near_depth_imbalance|near_sign)$", [L["depth"], L["spread_imb"]], "cutoff_ns"),
    (r"^(move_ticks|prior_move_ticks)$", [L["path"], L["outcome"]], "cutoff_ns"),
    # flow-only detector rows (Codex-captured per-second tables; clock = the row's own epoch second)
    (r"^second$", [L["recv"]], "row_default"),
    (r"^runway$|^burst_vol$|^dip300$", [L["dipole_state"], L["flow"]], "row_default"),
    # sweep cohort rows (post-family order sweep per first-family instance)
    (r"^counters$", [L["adds"], L["cancels"], L["levels"], L["depth"]], "cutoff_ns"),
    (r"^family_(print_lots_buy|print_lots_sell|print_lots_unknown|levels_printed|aggressor_orders)$", [L["trades"], L["fills"]], "cutoff_ns"),
    (r"^family_remainder_posted_lots$", [L["adds"], L["depth"]], "cutoff_ns"),
    (r"^hit_side$", [L["levels"], L["identity"]], "cutoff_ns"),
    (r"^post(1s|250)_(hit|opp)_side_.*fills", [L["fills"], L["trades"], L["outcome"]], "cutoff_ns"),
    (r"^post(1s|250)_(hit|opp)_side_.*cancels", [L["cancels"], L["depletion"], L["outcome"]], "cutoff_ns"),
    (r"^post(1s|250)_(hit|opp)_side_.*adds", [L["adds"], L["recovery"], L["outcome"]], "cutoff_ns"),
    (r"^(family_close_ns|family_cursors|has_tape)$", [L["known_by"], L["recv"], L["raw"]], "cutoff_ns"),
    # raw tape messages (instance traces, pair traces, case prints and touch snapshots)
    (r"^(ts_recv|ts_recv_ns|ts_event|cursor)$", [L["recv"], L["raw"]], "row_default"),
    (r"^action$|^before$|^after$", [L["adds"], L["cancels"], L["modifies"], L["identity"]], "row_default"),
    (r"^(linked_display_reduction|linked_fill_unchanged_display|linked_fill_reduction)$", [L["fills"], L["identity"]], "row_default"),
    (r"^flags$|^flags_last$", [L["raw"]], "row_default"),
    (r"^(price_raw|price|size)$", [L["levels"], L["trades"]], "row_default"),
    (r"^aggressor$", [L["trades"]], "row_default"),
    (r"^(near_best|far_touch|next_level|marker)$", [L["levels"], L["depth"]], "row_default"),
    (r"^t_ms$", [L["recv"]], "row_default"),
    (r"^(bid|ask)$", [L["levels"]], "row_default"),
    (r"^(bid|ask)_depth10$", [L["depth"]], "row_default"),
    (r"^spread_ticks$", [L["spread_imb"]], "row_default"),
    # case per-second rows
    (r"^(add|cancel|modify|fill)_[ABN](_lots)?$", [L["adds"], L["cancels"], L["modifies"], L["fills"]], "row_default"),
    (r"^aggr_(buy|sell|mid)_lots$|^print$|^print_lots$", [L["trades"]], "row_default"),
    (r"^mid$", [L["legacy_price"], L["path"]], "row_default"),
    (r"^roll20$", [L["roll20"]], "row_default"),
    (r"^(buy|sell)(_expiring)?$", [L["flow"]], "row_default"),
    (r"^(bid|ask)_depth$", [L["depth"]], "row_default"),
    (r"^(bid|ask)_touch$", [L["levels"]], "row_default"),
    (r"^spread$", [L["spread_imb"]], "row_default"),
    # pair rows
    (r"^kind$|^role$|^pair_index$", [L["identity"], L["depletion"], L["recovery"]], "row_default"),
    (r"^(retreated|recovered)$", [L["identity"], L["depletion"], L["recovery"], L["outcome"]], "row_default"),
    (r"^sec$|^epoch_s$|^seed$", None, None),
    (r"^hour_utc$|^hour_class$|^vol_tercile$|^tercile$|^session$|^day0_epoch_s$|^mode$|^file$", None, None),
]
SESSION_SECOND = {"t0", "onset", "confirm", "seed_known_s", "info_horizon_local_s", "info_horizon_refractory_s", "archived_recognition_s", "next_t0"}
FILES = ["exhaustion-clock-{t}-events.jsonl.gz", "runway-duration-{t}-events.jsonl.gz", "frozen-a-classifier-{t}-events.jsonl.gz",
         "a-state-direction-knowable-{t}-events.jsonl.gz", "beyond-direction-prebirth-{t}-events.jsonl.gz", "other-things-{t}-events.jsonl.gz",
         "stack-direction-sources-{t}-events.jsonl.gz", "next-burst-forecast-{t}-events.jsonl.gz", "runway-clock-v2-{t}-events.jsonl.gz",
         "chain-play-filter-{t}-rows.jsonl.gz", "dipole-post-recognition-{t}-rows.jsonl.gz", "first-family-four-arm-{t}-events.jsonl.gz",
         "size-one-episodes-{t}.jsonl.gz", "size-one-tape-{t}.jsonl.gz", "size-one-orders-{t}.jsonl.gz", "size-one-four-arm-{t}-rows.jsonl.gz"]
ID_FIELDS = ("t0", "candidate_id", "family_id", "instance", "onset_group", "side", "order_id", "mode")


def utc_s(e):
    return dt.datetime.fromtimestamp(e, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_ns(ns):
    return utc_s(ns // NS)[:-1] + f".{ns % NS:09d}Z"


def load_registry():
    raw = REG.read_bytes()
    reg = json.loads(raw)
    layers, n = {}, 0
    for g in reg["groups"]:
        items = g.get("layers") or g.get("entries") or g.get("items") or next((v for v in g.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
        for it in items:
            n += 1
            layers[n] = dict(index=n, layer_id=it.get("layer_id"), group_id=g["group_id"], policy=g["policy"])
    return layers, hashlib.sha256(raw).hexdigest()


def clock_for(rule, row, day0, default=None):
    """Return (clock_kind, epoch_s, ns, utc) for a rule, or None if the row lacks it. `default` is the row's own
    clock for sources whose rows carry one clock (tape messages, per-second rows, pair rows)."""
    if rule == "row_default":
        return default
    def sec(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        e = day0 + int(v); return ("receive_second_bin", e, None, utc_s(e))
    def nsc(v, kind):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        v = int(v); return (kind, v // NS, v, utc_ns(v))
    if rule in SESSION_SECOND:
        return sec(row.get(rule))
    if rule == "anchor60":
        v = row.get("t0"); return None if v is None else ("anchor_t0_plus_60", day0 + int(v) + 60, None, utc_s(day0 + int(v) + 60))
    if rule == "info50_or_anchor":
        v = row.get("t0"); return None if v is None else ("availability_t0_plus_50", day0 + int(v) + 50, None, utc_s(day0 + int(v) + 50))
    if rule == "outcome_from_t0":
        v = row.get("t0"); return None if v is None else ("outcome_window_from_t0", day0 + int(v), None, utc_s(day0 + int(v)))
    if rule == "onset_ns":
        return nsc(row.get("onset_ns"), "receive_ns")
    if rule == "end_ns":
        return nsc(row.get("end_ns"), "receive_ns") or nsc(row.get("onset_ns"), "receive_ns")
    if rule == "fate":
        if row.get("onset_ns") is not None and row.get("fate_delay_ms") is not None:
            v = int(row["onset_ns"] + row["fate_delay_ms"] * 1_000_000); return ("receive_ns", v // NS, v, utc_ns(v))
        return nsc(row.get("onset_ns"), "receive_ns")
    if rule == "recognition_receive_ns":
        return nsc(row.get("recognition_receive_ns"), "known_by_receive_ns")
    if rule == "birth_second":
        v = row.get("birth_second"); return None if v is None else ("receive_second_bin", int(v), None, utc_s(int(v)))
    if rule == "start_recv_ns":
        return nsc(row.get("start_recv_ns"), "receive_ns")
    if rule == "cutoff_ns":
        return nsc(row.get("cutoff_ns"), "known_by_cutoff_ns") or nsc(row.get("start_recv_ns"), "receive_ns")
    return default


CASES_DATA = "tasks/family-research-20261022/claude-code-cases"
FLOW_ONLY_TABLE = "tasks/family-research-20261022/flow-book-discovery-v1/date-tables/{d}/legacy_native_signed_flow.json.gz"


def ns_clock(ns, kind="receive_ns"):
    ns = int(ns); return (kind, ns // NS, ns, utc_ns(ns))


def s_clock(e, kind="receive_second_bin"):
    e = int(e); return (kind, e, None, utc_s(e))


def extra_sources(tag, day0, src):
    """The row sources outside FILES: yields (label, source_dict, rows) where rows yields (row, default_clock, day0_eff, extra_ids).
    Only this work's own rows: Codex's family-start and touch-print rows that the case context cites are not pinned here."""
    import data_locator
    # 1. flow-only detector runs on the Codex-captured per-second tables (October 2 and 17); t0 is relative to the table's first second
    p = HERE / f"exhaustion-clock-{DAY[tag]}-flow-only-events.jsonl.gz"
    if p.exists():
        fsrc = dict(per_second_table=FLOW_ONLY_TABLE.format(d=DAY[tag]), origin="Codex-captured box per-second table, not the tape", tape_members=None, exports=None)
        def rows_flow():
            for row in (json.loads(l) for l in gzip.open(p, "rt")):
                yield row, s_clock(row["second"]), row["second"] - row["t0"], {}
        yield p.name, fsrc, rows_flow()
    if tag == "oct18":
        # 2. the sweep cohort (post-family order sweep per first-family instance)
        p = HERE / "sweep-cohort-events.jsonl.gz"
        def rows_sweep():
            for row in (json.loads(l) for l in gzip.open(p, "rt")):
                yield row, ns_clock(row["start_recv_ns"]), day0, {}
        yield p.name, src, rows_sweep()
        # 3. the order-level traces of instances 375 and 391 (raw tape messages)
        tr = json.loads((HERE / "trace-events.json").read_text())
        for inst in (375, 391):
            p = HERE / f"trace-instance{inst}-messages.jsonl.gz"
            def rows_tr(p=p, inst=inst):
                for row in (json.loads(l) for l in gzip.open(p, "rt")):
                    yield row, ns_clock(row["ts_recv"]), day0, dict(instance=inst, family_id=tr[f"instance{inst}"]["family_id"])
            yield p.name, src, rows_tr()
    # 4. traced divergent pairs (October 2, 3, 17): one row per pair, one row per message of each role
    p = HERE / f"divergent-pairs-{tag}.json"
    if p.exists():
        d = json.loads(p.read_text())
        def rows_pairs():
            for k, pair in enumerate(d["pairs"]):
                roles = {r: dict(onset_group=pair[r]["episode"]["onset_group"], side=pair[r]["episode"]["side"], onset_ns=pair[r]["episode"]["onset_ns"],
                                 onset_cursor=pair[r]["episode"]["onset_cursor"], outcome=pair[r]["episode"]["outcome"], order_id=pair[r]["order"]["order_id"],
                                 fate=pair[r]["order"]["fate"], messages=len(pair[r]["messages"])) for r in ("retreated", "recovered")}
                yield dict(kind=pair["kind"], pair_index=k, **roles), ns_clock(roles["retreated"]["onset_ns"]), day0, dict(pair_index=k, kind=pair["kind"])
                for r in ("retreated", "recovered"):
                    ep = pair[r]["episode"]
                    for m in pair[r]["messages"]:
                        ns = int(ep["onset_ns"] + round(m["t_ms"] * 1_000_000))
                        yield dict(role=r, **m), ns_clock(ns, "receive_ns_from_t_ms"), day0, dict(pair_index=k, kind=pair["kind"], role=r, onset_group=ep["onset_group"], order_id=m.get("order_id"))
        yield p.name, src, rows_pairs()
    # 5. the five-view case rows (markets-data): context series, tape per-second, touch snapshots, prints
    try:
        ctx = json.loads(gzip.decompress(data_locator.read_bytes(f"{CASES_DATA}/case-context-{tag}.json.gz")))
        tape = json.loads(gzip.decompress(data_locator.read_bytes(f"{CASES_DATA}/case-tape-{tag}.json.gz")))
    except Exception as e:  # the case rows are optional inputs; say so rather than fail the ledger
        print(tag, "case rows not resolvable:", e); ctx = tape = None
    if ctx:
        csrc = dict(src, case_rows=[f"{CASES_DATA}/case-context-{tag}.json.gz", f"{CASES_DATA}/case-tape-{tag}.json.gz"])
        def rows_ctx():
            for key, c in ctx.items():
                ids = dict(case_t0=c["case"]["t0"], candidate_id=c["clocks"].get("candidate_id"))
                for row in c["series"]:
                    yield row, s_clock(row["epoch_s"]), day0, ids
        yield f"case-context-{tag}.json.gz#series", csrc, rows_ctx()
        def rows_tape():
            for key, c in tape.items():
                ids = dict(case_t0=c["case"]["t0"])
                for sec, row in c["per_second"].items():
                    yield dict(sec=int(sec), **row), s_clock(day0 + int(sec)), day0, ids
        yield f"case-tape-{tag}.json.gz#per_second", csrc, rows_tape()
        def rows_touch():
            for key, c in tape.items():
                ids = dict(case_t0=c["case"]["t0"])
                for sec, row in c["touch_by_second"].items():
                    yield dict(sec=int(sec), **row), ns_clock(row["ts_recv_ns"]), day0, ids
        yield f"case-tape-{tag}.json.gz#touch_by_second", csrc, rows_touch()
        def rows_prints():
            for key, c in tape.items():
                ids = dict(case_t0=c["case"]["t0"])
                for row in c["prints"]:
                    yield row, ns_clock(row["ts_recv_ns"]), day0, ids
        yield f"case-tape-{tag}.json.gz#prints", csrc, rows_prints()


def pin_row(row, day0, layers, default=None):
    pins, unknown = [], []
    for field, value in row.items():
        hit = False
        for pat_f, ls, rule in FIELD_MAP:
            if re.search(pat_f, field):
                hit = True
                if ls is None:
                    break
                c = clock_for(rule, row, day0, default)
                if c is None:
                    break
                kind, es, ns, u = c
                pins.append(dict(field=field, value=value, layers=[dict(index=i, layer_id=layers[i]["layer_id"], group_id=layers[i]["group_id"]) for i in ls],
                                 clock_kind=kind, clock_epoch_s=es, clock_ns=ns, clock_utc=u))
                break
        if not hit:
            unknown.append(field)
    return pins, unknown


def main():
    layers, reg_sha = load_registry()
    manifest = json.loads((HERE / "data-manifest.json").read_text())
    by_path = {e["path"]: e for e in manifest["entries"] if e.get("path")}
    pin_map = dict(registry_sha256=reg_sha, registry_path=str(REG.relative_to(ROOT)), layers_used=sorted({i for _, ls, _ in FIELD_MAP if ls for i in ls}),
                   field_map=[dict(pattern=p, layers=[dict(index=i, layer_id=layers[i]["layer_id"]) for i in ls] if ls else None, clock_rule=r) for p, ls, r in FIELD_MAP],
                   clock_kinds=["receive_second_bin (the replay's per-second bins are receive-clock seconds from the session origin)", "receive_ns", "known_by_receive_ns",
                                "known_by_cutoff_ns", "availability_t0_plus_50", "anchor_t0_plus_60", "outcome_window_from_t0"],
                   rule="only row fields with a clock of their own are pinned; aggregates are never pinned; rows are never merged")
    (HERE / "ninety-nine-pin-map.json").write_text(json.dumps(pin_map, indent=2) + "\n")
    grand = {}
    for tag, day0 in DAY0.items():
        src = dict(tape_members=[dict(utc_day=d, path=f"data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst", commit=c,
                                      sha256=by_path.get(f"data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst", {}).get("sha256")) for d, c in MEMBERS[tag]],
                   exports=[dict(path=e["path"], sha256=e.get("sha256"), markets_commit=e.get("markets_commit"), markets_data_commit=e.get("markets_data_commit"))
                            for e in manifest["entries"] if e.get("session") == DAY[tag] and e["tier"] == "export"])
        counts, per_file = Counter(), {}
        out = HERE / f"ninety-nine-pins-{tag}.jsonl.gz"
        with gzip.open(out, "wt") as fo:
            for pat in FILES:
                p = HERE / pat.format(t=tag)
                if not p.exists():
                    continue
                n_rows = n_pins = 0
                for ordinal, line in enumerate(gzip.open(p, "rt")):
                    row = json.loads(line)
                    ids = {k: row[k] for k in ID_FIELDS if k in row}
                    clocks = {k: v for k, v in row.items() if k.endswith("_ns") or k.endswith("_utc") or k.endswith("_epoch_s") or k in ("birth_second", "t0", "onset", "confirm")}
                    pins, _ = pin_row(row, day0, layers)
                    for pin in pins:
                        for l in pin["layers"]:
                            counts[l["index"]] += 1
                    rec = dict(session=tag, file=p.name, ordinal=ordinal, ids=ids, clocks=clocks, sources=src, pins=pins, row=row)
                    fo.write(json.dumps(rec, default=str) + "\n")
                    n_rows += 1; n_pins += len(pins)
                per_file[p.name] = dict(rows=n_rows, pins=n_pins)
            for label, esrc, rows in extra_sources(tag, day0, src):
                n_rows = n_pins = 0; unknown_fields = Counter()
                for ordinal, (row, default, day0_eff, extra_ids) in enumerate(rows):
                    ids = {k: row[k] for k in ID_FIELDS if k in row}; ids.update(extra_ids)
                    kind, es, ns, u = default
                    clocks = {k: v for k, v in row.items() if k.endswith("_ns") or k in ("ts_recv", "ts_event", "second", "epoch_s", "start_recv_ns", "family_close_ns")}
                    clocks["row_clock"] = dict(kind=kind, epoch_s=es, ns=ns, utc=u)
                    pins, unknown = pin_row(row, day0_eff, layers, default)
                    unknown_fields.update(unknown)
                    for pin in pins:
                        for l in pin["layers"]:
                            counts[l["index"]] += 1
                    rec = dict(session=tag, file=label, ordinal=ordinal, ids=ids, clocks=clocks, sources=esrc, pins=pins, row=row)
                    fo.write(json.dumps(rec, default=str) + "\n")
                    n_rows += 1; n_pins += len(pins)
                per_file[label] = dict(rows=n_rows, pins=n_pins, fields_without_layer=sorted(unknown_fields))
        grand[tag] = dict(files=per_file, not_pinned_here=["family_starts and touch_print_decisions cited in the case context are Codex's rows, pinned by their owner",
                                                            "other_detector_events and size_one_onsets in the case context are already pinned from their own files"],
                          identical_predecessor_copies=(["dipole-post-recognition-rows.jsonl.gz = dipole-post-recognition-oct18-rows.jsonl.gz", "first-family-four-arm-events.jsonl.gz = first-family-four-arm-oct18-events.jsonl.gz"] if tag == "oct18" else []), pins_by_layer={f"{i:02d} {layers[i]['layer_id']}": n for i, n in sorted(counts.items())},
                          rows=sum(v["rows"] for v in per_file.values()), pins=sum(v["pins"] for v in per_file.values()))
        print(tag, "rows", grand[tag]["rows"], "pins", grand[tag]["pins"], "layers touched", len(counts))
    (HERE / "ninety-nine-pins-summary.json").write_text(json.dumps(grand, indent=2) + "\n")
    print(json.dumps(grand["oct18"]["pins_by_layer"], indent=1))


if __name__ == "__main__":
    main()
