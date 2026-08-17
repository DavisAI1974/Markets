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

HELD_WEEK = "20260329"
CLOSURE_DAY = "20260403"


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


def load_held_week(paths, witness):
    w = json.load(open(witness))
    if w.get("status") != "FROZEN_EXCHANGE_CLOSURE_WITNESS":
        raise SystemExit("held-week closure witness is not frozen")
    if w.get("held_week_sunday") != HELD_WEEK or w.get("missing_utc_date") != CLOSURE_DAY:
        raise SystemExit("held-week closure witness identity drift")
    if w["canonicalization_rule"].get("synthetic_empty_raw_file_allowed") is not False:
        raise SystemExit("synthetic closure-day raw files are forbidden")

    sunday = base.ymd(HELD_WEEK)
    expected = [base.ymds(sunday + timedelta(days=i)) for i in range(6)]
    present_expected = [d for d in expected if d != CLOSURE_DAY]
    paths_by_day = {}
    for p in paths:
        d = base.parse_day(p)
        if d in paths_by_day:
            raise SystemExit(f"duplicate raw path for {d}")
        paths_by_day[d] = p
    if sorted(paths_by_day) != sorted(present_expected):
        raise SystemExit(f"held week must contain the five real raw dates {present_expected}; got {sorted(paths_by_day)}")

    n = 6 * base.DAY_SECONDS
    buy = [0.0] * n
    sell = [0.0] * n
    raw_price = [float("nan")] * n
    bsum = [0.0] * n
    bn = [0] * n
    blast = [float("nan")] * n
    rows = trades = classified = midpoint_skipped = invalid_trade = 0
    actual_trade_idx = []

    for d in present_expected:
        di = (base.ymd(d) - sunday).days
        with gzip.open(paths_by_day[d], "rt") as f:
            for line in f:
                r = json.loads(line)
                rows += 1
                ts = float(r.get("ts_event", r.get("ts", 0.0)))
                sec = int(ts) % base.DAY_SECONDS
                idx = di * base.DAY_SECONDS + sec
                bid_sz = sum(float(r.get(f"bid_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
                ask_sz = sum(float(r.get(f"ask_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
                tot = bid_sz + ask_sz
                if tot > 0:
                    imb = (bid_sz - ask_sz) / tot
                    bsum[idx] += imb
                    bn[idx] += 1
                    blast[idx] = imb
                if r.get("action") != "T":
                    continue
                trades += 1
                px = float(r.get("price", 0.0) or 0.0)
                if px > 0:
                    raw_price[idx] = px
                    actual_trade_idx.append(idx)
                sz = float(r.get("size", r.get("qty", 0.0)) or 0.0)
                bid0 = float(r.get("bid_px_00", 0.0) or 0.0)
                ask0 = float(r.get("ask_px_00", 0.0) or 0.0)
                if not (px > 0 and sz > 0 and bid0 > 0 and ask0 > 0 and ask0 >= bid0):
                    invalid_trade += 1
                    continue
                mid = 0.5 * (bid0 + ask0)
                if px > mid:
                    buy[idx] += sz
                    classified += 1
                elif px < mid:
                    sell[idx] += sz
                    classified += 1
                else:
                    midpoint_skipped += 1

    if not actual_trade_idx:
        raise SystemExit("held week contains no NG trades")
    first_trade = min(actual_trade_idx)
    last_trade = max(actual_trade_idx)

    price = [float("nan")] * n
    book = [float("nan")] * n
    lp = li = float("nan")
    for i in range(n):
        if base.finite(raw_price[i]):
            lp = float(raw_price[i])
        price[i] = lp
        if base.finite(blast[i]):
            li = float(blast[i])
        book[i] = (bsum[i] / bn[i]) if bn[i] else li

    cb = [0.0] * (n + 1)
    cs = [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + buy[i]
        cs[i + 1] = cs[i] + sell[i]
    roll20 = [float("nan")] * n
    for i in range(n):
        lo = max(0, i - base.ROLL + 1)
        b = cb[i + 1] - cb[lo]
        s = cs[i + 1] - cs[lo]
        z = b + s
        if z > 0:
            roll20[i] = (b - s) / z

    day_thresholds = {}
    for d in expected:
        di = (base.ymd(d) - sunday).days
        vals = [abs(v) for v in roll20[di * base.DAY_SECONDS:(di + 1) * base.DAY_SECONDS] if base.finite(v)]
        day_thresholds[d] = base.quantile(vals, base.PEAK_Q)

    return {
        "week_sunday": sunday,
        "first_date": sunday,
        "required_days": expected,
        "buy": buy,
        "sell": sell,
        "price": price,
        "book": book,
        "roll20": roll20,
        "first_trade_idx": first_trade,
        "last_trade_idx": last_trade,
        "day_thresholds": day_thresholds,
        "rows": rows,
        "trades": trades,
        "classified": classified,
        "midpoint_skipped": midpoint_skipped,
        "invalid_trade": invalid_trade,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--closure-witness", default="research/NG_EXHAUSTION_20260403_CME_CLOSURE_WITNESS_20260817.json")
    ap.add_argument("--pre-family-classifier", default="research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json")
    ap.add_argument("--a-classifier", default="research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json")
    ap.add_argument("--out-prefix", default="NG_EXHAUSTION_CHAIN_CANONICAL_HELD_WEEK_20260329")
    ap.add_argument("raw_days", nargs="+")
    a = ap.parse_args()

    stream = load_held_week(a.raw_days, a.closure_witness)
    pre = base.FrozenPreFamilyClassifier.load(a.pre_family_classifier)
    acl = base.FrozenAClassifier.load(a.a_classifier)
    event_rows, det = base.event_rows_for_week(stream, pre, acl)
    base.attach_links(event_rows)
    event_rows.sort(key=lambda r: r["t0_idx"])

    if any(r["source_utc_day"] == CLOSURE_DAY for r in event_rows):
        raise SystemExit("event detected on witnessed closure day")

    table = Path(a.out_prefix + "_EVENT_TABLE.jsonl.gz")
    raw_sha, gz_sha = base.deterministic_gzip_jsonl(table, event_rows)
    schema_paths = sorted(set().union(*(flatten_paths(r) for r in event_rows))) if event_rows else []
    schema_sha = hashlib.sha256((json.dumps(schema_paths, separators=(",", ":")) + "\n").encode()).hexdigest()
    first_dt = base.dt_from_idx(stream["first_date"], stream["first_trade_idx"])
    last_dt = base.dt_from_idx(stream["first_date"], stream["last_trade_idx"])
    witness_sha = hashlib.sha256(Path(a.closure_witness).read_bytes()).hexdigest()

    summary = {
        "status": "CHAIN_CANONICAL_HELD_WEEK_20260329_FROZEN",
        "week_sunday": HELD_WEEK,
        "event_count": len(event_rows),
        "candidate_count": det["candidate_count"],
        "first_actual_trade_utc": first_dt.isoformat(),
        "last_actual_trade_utc": last_dt.isoformat(),
        "events_by_day": dict(Counter(r["source_utc_day"] for r in event_rows)),
        "explicit_closure_dates": [CLOSURE_DAY],
        "closure_witness": a.closure_witness,
        "closure_witness_sha256": witness_sha,
        "synthetic_empty_raw_file_created": False,
        "detector_source": "research/ng_exhaustion_chain_canonical_table_20260817.py",
        "table": {
            "path": str(table),
            "uncompressed_jsonl_sha256": raw_sha,
            "gzip_sha256": gz_sha,
            "schema_sha256": schema_sha,
            "schema_paths": schema_paths,
        },
        "calendar_day_chain_reset": False,
        "time_of_day_is_gate": False,
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out_prefix + "_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
