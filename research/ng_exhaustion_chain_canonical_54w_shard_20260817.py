#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

import ng_exhaustion_chain_canonical_table_20260817 as base


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
    ap.add_argument("--weeks", required=True, help="comma-separated week Sunday YYYYMMDD values")
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("--pre-family-classifier", default="research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json")
    ap.add_argument("--a-classifier", default="research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json")
    ap.add_argument("raw_days", nargs="+")
    a = ap.parse_args()

    freeze = json.load(open(a.base_freeze))
    assert freeze["status"] == "FROZEN_BEFORE_54W_BASE_RUN"
    requested = [x for x in a.weeks.split(",") if x]
    allowed = set(freeze["base_weeks"])
    if not requested or len(requested) != len(set(requested)):
        raise SystemExit("invalid requested week list")
    if any(w not in allowed for w in requested):
        raise SystemExit(f"requested week outside frozen 54-week base: {requested}")
    if "20260329" in requested:
        raise SystemExit("repair week 20260329 is insert-only and forbidden in the 54-week base shard")

    by_week = {}
    for p in a.raw_days:
        d = base.parse_day(p)
        ws = base.ymds(base.sunday_of(base.ymd(d)))
        by_week.setdefault(ws, []).append(p)
    if set(by_week) != set(requested):
        raise SystemExit(f"raw week mismatch requested={requested} got={sorted(by_week)}")

    pre_classifier = base.FrozenPreFamilyClassifier.load(a.pre_family_classifier)
    a_classifier = base.FrozenAClassifier.load(a.a_classifier)
    raw_path = Path(a.out_prefix + "_EVENT_TABLE.jsonl")
    h = hashlib.sha256()
    total = 0
    week_summary = {}
    event_ids = set()

    with raw_path.open("wb") as out:
        for ws in requested:
            sunday = base.ymd(ws)
            expected = [base.ymds(sunday + timedelta(days=i)) for i in range(6)]
            got = sorted(base.parse_day(p) for p in by_week[ws])
            if got != expected:
                raise SystemExit(f"week {ws} must have exact Sunday-Friday raw files expected={expected} got={got}")
            streams = base.load_week_stream(sorted(by_week[ws]))
            if list(streams) != [ws]:
                raise SystemExit(f"single-week loader drift for {ws}: {list(streams)}")
            stream = streams[ws]
            rows, det = base.event_rows_for_week(stream, pre_classifier, a_classifier)
            base.attach_links(rows)
            rows.sort(key=lambda r: r["t0_idx"])
            cross = []
            for x, y in zip(rows, rows[1:]):
                if x["source_utc_day"] != y["source_utc_day"]:
                    cross.append(y["t0_idx"] - x["t0_idx"])
            for r in rows:
                eid = r["event_id"]
                if eid in event_ids:
                    raise SystemExit(f"duplicate event id {eid}")
                event_ids.add(eid)
                line = (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
                out.write(line)
                h.update(line)
            first_dt = base.dt_from_idx(stream["first_date"], stream["first_trade_idx"])
            last_dt = base.dt_from_idx(stream["first_date"], stream["last_trade_idx"])
            week_summary[ws] = {
                "event_n": len(rows),
                "candidate_n": det["candidate_count"],
                "first_actual_trade_utc": first_dt.isoformat(),
                "last_actual_trade_utc": last_dt.isoformat(),
                "raw_rows": stream["rows"],
                "trades": stream["trades"],
                "classified_aggressor_trades": stream["classified"],
                "events_by_day": dict(Counter(r["source_utc_day"] for r in rows)),
                "cross_utc_date_links": len(cross),
                "cross_utc_date_link_gap_s_min": None if not cross else min(cross),
                "cross_utc_date_link_gap_s_median": None if not cross else base.median(cross),
            }
            total += len(rows)
            del streams, stream, rows

    gz_path = Path(a.out_prefix + "_EVENT_TABLE.jsonl.gz")
    gz_sha = deterministic_gzip(raw_path, gz_path)
    raw_path.unlink()
    summary = {
        "status": "CHAIN_CANONICAL_54W_SHARD_COMPLETE",
        "base_freeze": a.base_freeze,
        "weeks": requested,
        "week_count": len(requested),
        "event_count": total,
        "week_summary": week_summary,
        "table": {
            "path": str(gz_path),
            "uncompressed_jsonl_sha256": h.hexdigest(),
            "gzip_sha256": gz_sha,
        },
        "detector_source": "research/ng_exhaustion_chain_canonical_table_20260817.py",
        "calendar_day_chain_reset": False,
        "time_of_day_is_gate": False,
        "repair_week_included": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out_prefix + "_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": summary["status"], "weeks": requested, "event_count": total, "gzip_sha256": gz_sha}, indent=2))


if __name__ == "__main__":
    main()
