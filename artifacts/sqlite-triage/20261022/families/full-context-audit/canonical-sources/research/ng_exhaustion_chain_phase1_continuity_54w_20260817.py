#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import boto3

BUCKET = "bento-568968024170-us-east-2-an"
PREFIX = "nymex/nymex_cont/NG_"
DAY_RE = re.compile(r"NG_(20\d{6})(?:_[A-Za-z]{3})?\.jsonl\.gz$")


def dfrom(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def ymd(d):
    return d.strftime("%Y%m%d")


def list_all(s3, prefix):
    out = []
    token = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        out.extend(r.get("Contents", []))
        if not r.get("IsTruncated"):
            return out
        token = r["NextContinuationToken"]


def main():
    coverage = json.load(open("research/NG_EXHAUSTION_FULL_HISTORY_COVERAGE_FREEZE_20260817.json"))
    base = json.load(open("research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json"))
    assert coverage["status"] == "FROZEN_FULL_HISTORY_COVERAGE_READY_FOR_PHASE1"
    assert coverage["postrepair_inventory"]["trading_week_count"] == 55
    assert coverage["postrepair_inventory"]["usable_complete_week_count"] == 55
    assert base["base_week_count"] == 54
    assert base["temporarily_excluded_weeks"] == ["20260329"]

    s3 = boto3.client("s3", region_name="us-east-2")
    objects = list_all(s3, PREFIX)
    by_day = defaultdict(list)
    ignored = []
    for obj in objects:
        m = DAY_RE.search(obj["Key"])
        if not m:
            ignored.append(obj["Key"])
            continue
        by_day[m.group(1)].append({"key": obj["Key"], "size": int(obj["Size"]), "etag": obj.get("ETag")})

    week_records = []
    failures = []
    for ws in base["base_weeks"]:
        sunday = dfrom(ws)
        expected = [ymd(sunday + timedelta(days=i)) for i in range(6)]
        missing = [d for d in expected if d not in by_day]
        duplicates = {d: by_day[d] for d in expected if len(by_day.get(d, [])) != 1}
        empty = {d: by_day[d][0] for d in expected if len(by_day.get(d, [])) == 1 and by_day[d][0]["size"] <= 0}
        rec = {"week_sunday": ws, "expected_dates": expected, "missing_dates": missing, "duplicates": duplicates, "empty_objects": empty}
        if missing or duplicates or empty:
            failures.append(rec)
        week_records.append(rec)

    repair = coverage["repair_20250629"]
    repair_key = repair["s3_key"]
    repair_obj = next((o for o in objects if o["Key"] == repair_key), None)
    if repair_obj is None:
        failures.append({"repair_provenance": "missing repaired 20250629 object", "key": repair_key})
    elif int(repair_obj["Size"]) != int(repair["gzip_bytes"]):
        failures.append({"repair_provenance": "size mismatch", "expected": repair["gzip_bytes"], "got": int(repair_obj["Size"])})

    held = "20260329"
    held_sunday = dfrom(held)
    held_expected = [ymd(held_sunday + timedelta(days=i)) for i in range(6)]
    held_present = {d: by_day.get(d, []) for d in held_expected}

    result = {
        "status": "PHASE1_54W_CONTINUITY_AUDIT_PASS" if not failures else "PHASE1_54W_CONTINUITY_AUDIT_FAIL",
        "base_week_count": 54,
        "audited_weeks": base["base_weeks"],
        "temporarily_excluded_week": held,
        "held_week_snapshot": {"expected_dates": held_expected, "objects_by_date": held_present},
        "repair_20250629_provenance": {
            "key": repair_key,
            "manifest_gzip_sha256": repair["gzip_sha256"],
            "manifest_bytes": repair["gzip_bytes"],
            "s3_object_present": repair_obj is not None,
        },
        "failures": failures,
        "week_records": week_records,
        "calendar_midnight_reset_allowed": False,
        "silent_week_exclusion_allowed": False,
        "only_authorized_exclusion": held,
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path("NG_EXHAUSTION_CHAIN_PHASE1_CONTINUITY_54W_20260817.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "failures": len(failures), "base_week_count": 54, "held_week": held}, indent=2))
    if failures:
        raise SystemExit("54-week continuity audit failed")


if __name__ == "__main__":
    main()
