#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import boto3

BUCKET = "bento-568968024170-us-east-2-an"
RAW_PREFIX = "nymex/nymex_cont/NG_"
EXH_PREFIX = "nymex/ng_exhaustion/v0/"
DAY_RE = re.compile(r"NG_(20\d{6})(?:_[A-Za-z]{3})?\.jsonl\.gz$")
STUB_BYTES = 5000

# Existing project calendar list. Missing dates outside this set remain fail-closed
# until explicitly classified; we do not silently excuse absent history.
FULL_CLOSURES = {
    "20250704", "20250901", "20251127", "20251225",
    "20260101", "20260403", "20260525", "20260619", "20260703",
}


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def dfrom(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def sunday_of(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def list_all(s3, prefix: str):
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
    s3 = boto3.client("s3", region_name="us-east-2")
    raw_objects = list_all(s3, RAW_PREFIX)
    exhaustion_objects = list_all(s3, EXH_PREFIX)

    by_day = defaultdict(list)
    ignored_raw = []
    for obj in raw_objects:
        key = obj["Key"]
        m = DAY_RE.search(key)
        if not m:
            ignored_raw.append(key)
            continue
        by_day[m.group(1)].append({"key": key, "size": int(obj["Size"]), "etag": obj.get("ETag")})

    if not by_day:
        raise SystemExit("no NG raw daily objects found")

    days = sorted(by_day)
    first_day, last_day = days[0], days[-1]
    week_keys = sorted({ymd(sunday_of(dfrom(d))) for d in days})
    weeks = []
    usable = []
    repair = []

    for ws_s in week_keys:
        ws = dfrom(ws_s)
        expected = [ymd(ws + timedelta(days=i)) for i in range(6)]  # Sun..Fri
        present = [d for d in expected if d in by_day]
        missing = [d for d in expected if d not in by_day]
        duplicates = {d: by_day[d] for d in present if len(by_day[d]) != 1}
        weekday_stubs = {}
        sunday_issue = None

        if expected[0] not in by_day:
            sunday_issue = "missing_sunday_reopen_file"
        elif len(by_day[expected[0]]) != 1:
            sunday_issue = "duplicate_sunday_objects"
        elif by_day[expected[0]][0]["size"] <= 0:
            sunday_issue = "empty_sunday_reopen_file"

        for d in expected[1:]:
            if d in by_day and d not in FULL_CLOSURES:
                # Multiple keys are already separately fatal. Only inspect the sole object here.
                if len(by_day[d]) == 1 and by_day[d][0]["size"] < STUB_BYTES:
                    weekday_stubs[d] = by_day[d][0]

        unexplained_missing = [d for d in missing if d not in FULL_CLOSURES]
        closure_missing = [d for d in missing if d in FULL_CLOSURES]

        # Do not call the current tail week complete until its Friday is in the historical corpus.
        truncated_tail = dfrom(last_day) < ws + timedelta(days=5)
        status = "USABLE_COMPLETE"
        reasons = []
        if truncated_tail:
            status = "OPEN_OR_TRUNCATED_TAIL"
            reasons.append("latest raw date precedes this week Friday")
        if sunday_issue:
            status = "REPAIR_REQUIRED"
            reasons.append(sunday_issue)
        if unexplained_missing:
            status = "REPAIR_REQUIRED"
            reasons.append(f"unexplained missing dates: {','.join(unexplained_missing)}")
        if duplicates:
            status = "REPAIR_REQUIRED"
            reasons.append("duplicate date objects")
        if weekday_stubs:
            status = "REPAIR_REQUIRED"
            reasons.append("sub-5KB expected-full weekday object")

        rec = {
            "week_sunday": ws_s,
            "expected_sun_fri": expected,
            "present_dates": present,
            "missing_dates": missing,
            "closure_missing_dates": closure_missing,
            "unexplained_missing_dates": unexplained_missing,
            "sunday": None if expected[0] not in by_day else by_day[expected[0]],
            "sunday_issue": sunday_issue,
            "duplicates": duplicates,
            "weekday_stubs": weekday_stubs,
            "truncated_tail": truncated_tail,
            "status": status,
            "reasons": reasons,
        }
        weeks.append(rec)
        if status == "USABLE_COMPLETE":
            usable.append(ws_s)
        elif status == "REPAIR_REQUIRED":
            repair.append(ws_s)

    manifest = {
        "status": "FULL_HISTORY_NG_CORPUS_INVENTORIED",
        "bucket": BUCKET,
        "raw_prefix": RAW_PREFIX,
        "exhaustion_prefix": EXH_PREFIX,
        "raw_object_count": len(raw_objects),
        "parsed_unique_raw_dates": len(days),
        "first_raw_date": first_day,
        "last_raw_date": last_day,
        "ignored_raw_keys": ignored_raw,
        "duplicate_raw_dates": {d: by_day[d] for d in days if len(by_day[d]) != 1},
        "week_count": len(weeks),
        "usable_complete_week_count": len(usable),
        "repair_required_week_count": len(repair),
        "usable_complete_weeks": usable,
        "repair_required_weeks": repair,
        "exhaustion_v0_object_count": len(exhaustion_objects),
        "exhaustion_v0_key_sample": [x["Key"] for x in exhaustion_objects[:100]],
        "week_semantics": {
            "sunday_required": True,
            "sun_to_fri_continuity": True,
            "calendar_midnight_reset": False,
            "silent_exclusion": False,
        },
        "weeks": weeks,
    }
    Path("NG_EXHAUSTION_FULL_HISTORY_CORPUS_INVENTORY_20260817.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "status": manifest["status"],
        "first_raw_date": first_day,
        "last_raw_date": last_day,
        "unique_dates": len(days),
        "weeks": len(weeks),
        "usable_complete_weeks": len(usable),
        "repair_required_weeks": len(repair),
        "repair_weeks": repair,
        "exhaustion_v0_objects": len(exhaustion_objects),
    }, indent=2))


if __name__ == "__main__":
    main()
