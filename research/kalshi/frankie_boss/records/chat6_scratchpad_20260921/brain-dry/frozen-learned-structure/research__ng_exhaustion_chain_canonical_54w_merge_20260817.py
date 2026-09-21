#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import ng_exhaustion_chain_canonical_table_20260817 as base


def flatten_paths(obj, prefix=""):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.add(p)
            out |= flatten_paths(v, p)
    elif isinstance(obj, list):
        out.add(prefix + "[]")
        if obj:
            out |= flatten_paths(obj[0], prefix + "[]")
    return out


def deterministic_gzip(src: Path, dst: Path) -> str:
    with src.open("rb") as inp, dst.open("wb") as out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0) as gz:
            while True:
                b = inp.read(1024 * 1024)
                if not b:
                    break
                gz.write(b)
    return hashlib.sha256(dst.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-freeze", default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json")
    ap.add_argument("--reveal-records", required=True)
    ap.add_argument("--holdout-records", required=True)
    ap.add_argument("--out-prefix", default="NG_EXHAUSTION_CHAIN_CANONICAL_54W_BASE_20260817")
    ap.add_argument("--summaries", nargs="+", required=True)
    ap.add_argument("--tables", nargs="+", required=True)
    a = ap.parse_args()

    freeze = json.load(open(a.base_freeze))
    expected = list(freeze["base_weeks"])
    expected_set = set(expected)
    if len(expected) != 54 or "20260329" in expected_set:
        raise SystemExit("54-week base freeze invariant failed")

    summaries = [json.load(open(p)) for p in a.summaries]
    weeks_from_summaries = []
    week_summary = {}
    total_summary_events = 0
    for s in summaries:
        if s.get("status") != "CHAIN_CANONICAL_54W_SHARD_COMPLETE":
            raise SystemExit(f"bad shard summary status {s.get('status')}")
        if s.get("repair_week_included"):
            raise SystemExit("repair week leaked into base shard")
        weeks_from_summaries.extend(s["weeks"])
        total_summary_events += int(s["event_count"])
        for w, rec in s["week_summary"].items():
            if w in week_summary:
                raise SystemExit(f"duplicate summary week {w}")
            week_summary[w] = rec
    if set(weeks_from_summaries) != expected_set or len(weeks_from_summaries) != 54:
        raise SystemExit(f"shard coverage mismatch got={sorted(weeks_from_summaries)}")

    frozen, blind_a = base.load_frozen_roster(a.reveal_records, a.holdout_records)
    target_days = {k[0] for k in frozen}
    target_rows = []
    seen_events = set()
    seen_weeks = []
    schema_paths = set()
    raw = Path(a.out_prefix + "_EVENT_TABLE.jsonl")
    raw_hash = hashlib.sha256()
    count = 0
    last_key = None

    with raw.open("wb") as out:
        for table in a.tables:
            with gzip.open(table, "rt") as f:
                for line in f:
                    r = json.loads(line)
                    w = r["week_sunday"]
                    if w not in expected_set or w == "20260329":
                        raise SystemExit(f"unexpected week in merged table: {w}")
                    key = (expected.index(w), int(r["sequence_index"]))
                    if last_key is not None and key <= last_key:
                        raise SystemExit(f"non-monotone merge order prev={last_key} cur={key}")
                    last_key = key
                    eid = r["event_id"]
                    if eid in seen_events:
                        raise SystemExit(f"duplicate event id {eid}")
                    seen_events.add(eid)
                    if not seen_weeks or seen_weeks[-1] != w:
                        seen_weeks.append(w)
                    schema_paths |= flatten_paths(r)
                    if r["source_utc_day"] in target_days:
                        target_rows.append(r)
                    b = (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    out.write(b)
                    raw_hash.update(b)
                    count += 1

    if seen_weeks != expected:
        raise SystemExit(f"merged week order mismatch got={seen_weeks}")
    if count != total_summary_events:
        raise SystemExit(f"event-count mismatch merged={count} summaries={total_summary_events}")
    equivalence = base.compare_target_roster(target_rows, frozen, blind_a)
    if equivalence["frozen_events_recovered"] != 3429:
        raise SystemExit("pilot target equivalence did not recover all 3429 frozen events")

    gz = Path(a.out_prefix + "_EVENT_TABLE.jsonl.gz")
    gz_sha = deterministic_gzip(raw, gz)
    raw.unlink()
    schema_list = sorted(schema_paths)
    schema_sha = hashlib.sha256((json.dumps(schema_list, separators=(",", ":")) + "\n").encode()).hexdigest()
    summary = {
        "status": "CHAIN_CANONICAL_54W_BASE_FROZEN_PROVISIONAL",
        "base_freeze": a.base_freeze,
        "event_count": count,
        "week_count": 54,
        "weeks": expected,
        "temporarily_excluded_weeks": ["20260329"],
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "target_equivalence": equivalence,
        "week_summary": {w: week_summary[w] for w in expected},
        "table": {
            "path": str(gz),
            "uncompressed_jsonl_sha256": raw_hash.hexdigest(),
            "gzip_sha256": gz_sha,
            "schema_sha256": schema_sha,
            "schema_paths": schema_list,
        },
        "insert_only_repair_policy": freeze["immutability_after_base_freeze"],
        "detector_source": "research/ng_exhaustion_chain_canonical_table_20260817.py",
        "feature_outcome_separation": True,
        "event_detection_price_used": False,
        "calendar_day_chain_reset": False,
        "time_of_day_is_gate": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out_prefix + "_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": summary["status"],
        "week_count": 54,
        "event_count": count,
        "pilot_equivalence": equivalence,
        "gzip_sha256": gz_sha,
        "schema_sha256": schema_sha,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
