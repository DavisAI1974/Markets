#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ng_dipole_native_shape_audit import fill_curve, first_persist_below, first_zero
from ng_dipole_runway_audit import TICK
from ng_exhaustion_live_clock import FrozenPreFamilyClassifier
from ng_exhaustion_runway_clock import FrozenAClassifier

DAY_SECONDS = 86400
PRE = 60
POST = 60
ROLL = 20
PEAK_Q = 0.85
LOCAL_RADIUS = 5
REFRACTORY = 45
HORIZONS = (5, 10, 20, 30, 60, 120, 300)
PERSIST = 3
MATERIAL_TICKS = 2.0
ET = ZoneInfo("America/New_York")


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def quantile(xs, q):
    a = sorted(float(x) for x in xs if finite(x))
    if not a:
        return float("nan")
    if len(a) == 1:
        return a[0]
    z = q * (len(a) - 1)
    i = int(math.floor(z))
    j = min(i + 1, len(a) - 1)
    w = z - i
    return a[i] * (1 - w) + a[j] * w


def median(xs):
    a = sorted(float(x) for x in xs if finite(x))
    if not a:
        return float("nan")
    m = len(a) // 2
    return a[m] if len(a) % 2 else 0.5 * (a[m - 1] + a[m])


def parse_day(path):
    m = re.search(r"(20\d{6})", Path(path).name)
    if not m:
        raise SystemExit(f"cannot parse day from {path}")
    return m.group(1)


def ymd(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def ymds(d):
    return d.strftime("%Y%m%d")


def sunday_of(d):
    return d - timedelta(days=(d.weekday() + 1) % 7)


def epoch_from_day_second(day, sec):
    dt = datetime.combine(ymd(day), time.min, tzinfo=timezone.utc) + timedelta(seconds=int(sec))
    return dt.timestamp()


def dt_from_idx(first_date, idx):
    return datetime.combine(first_date, time.min, tzinfo=timezone.utc) + timedelta(seconds=int(idx))


def side_pressure(buy, sell, lo, hi, pol):
    b = sum(float(buy[i]) for i in range(lo, hi))
    s = sum(float(sell[i]) for i in range(lo, hi))
    aligned = b if pol > 0 else s
    opposite = s if pol > 0 else b
    total = aligned + opposite
    return None if total <= 0 else (aligned - opposite) / total


def seed_state(zero_s, late_pressure):
    if zero_s is None:
        return "persistent_exhaustion"
    if late_pressure is None or abs(float(late_pressure)) < 1e-12:
        return "collapsed_sparse_indeterminate"
    return "collapsed_same_flow_reload" if late_pressure > 0 else "collapsed_opposite_flow_reversal"


def load_week_stream(paths):
    paths_by_day = {parse_day(p): p for p in paths}
    grouped = defaultdict(list)
    for d in paths_by_day:
        grouped[ymds(sunday_of(ymd(d)))].append(d)
    streams = {}
    for ws, days in sorted(grouped.items()):
        sunday = ymd(ws)
        required = [ymds(sunday + timedelta(days=i)) for i in range(6)]
        missing = [d for d in required if d not in paths_by_day]
        if missing:
            raise SystemExit(f"week {ws} missing Sunday-Friday raw days: {missing}")
        first_date = sunday
        n = 6 * DAY_SECONDS
        buy = [0.0] * n
        sell = [0.0] * n
        raw_price = [float("nan")] * n
        bsum = [0.0] * n
        bn = [0] * n
        blast = [float("nan")] * n
        rows = trades = classified = midpoint_skipped = invalid_trade = 0
        actual_trade_idx = []
        for d in required:
            di = (ymd(d) - first_date).days
            with gzip.open(paths_by_day[d], "rt") as f:
                for line in f:
                    r = json.loads(line)
                    rows += 1
                    ts = float(r.get("ts_event", r.get("ts", 0.0)))
                    sec = int(ts) % DAY_SECONDS
                    idx = di * DAY_SECONDS + sec
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
            raise SystemExit(f"week {ws} contains no NG trades")
        first_trade = min(actual_trade_idx)
        last_trade = max(actual_trade_idx)
        price = [float("nan")] * n
        book = [float("nan")] * n
        lp = li = float("nan")
        for i in range(n):
            if finite(raw_price[i]):
                lp = float(raw_price[i])
            price[i] = lp
            if finite(blast[i]):
                li = float(blast[i])
            book[i] = (bsum[i] / bn[i]) if bn[i] else li
        cb = [0.0] * (n + 1)
        cs = [0.0] * (n + 1)
        for i in range(n):
            cb[i + 1] = cb[i] + buy[i]
            cs[i + 1] = cs[i] + sell[i]
        roll20 = [float("nan")] * n
        for i in range(n):
            lo = max(0, i - ROLL + 1)
            b = cb[i + 1] - cb[lo]
            s = cs[i + 1] - cs[lo]
            z = b + s
            if z > 0:
                roll20[i] = (b - s) / z
        day_thresholds = {}
        for d in required:
            di = (ymd(d) - first_date).days
            vals = [abs(v) for v in roll20[di * DAY_SECONDS:(di + 1) * DAY_SECONDS] if finite(v)]
            day_thresholds[d] = quantile(vals, PEAK_Q)
        streams[ws] = {
            "week_sunday": sunday,
            "first_date": first_date,
            "required_days": required,
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
    return streams


def detect_week_events(stream):
    flow = stream["roll20"]
    first_trade = stream["first_trade_idx"]
    last_trade = stream["last_trade_idx"]
    first_date = stream["first_date"]
    cand = []
    for d in stream["required_days"]:
        di = (ymd(d) - first_date).days
        day_lo = di * DAY_SECONDS
        day_hi = (di + 1) * DAY_SECONDS - 1
        lo = max(day_lo, first_trade + PRE, LOCAL_RADIUS, 30)
        hi = min(day_hi, last_trade - POST, len(flow) - LOCAL_RADIUS - 1)
        thr = stream["day_thresholds"][d]
        for t in range(lo, hi + 1):
            v = flow[t]
            if not finite(v) or abs(v) < thr:
                continue
            local = [abs(flow[j]) for j in range(t - LOCAL_RADIUS, t + LOCAL_RADIUS + 1) if finite(flow[j])]
            if not local or abs(v) < max(local) - 1e-12:
                continue
            base = median(abs(flow[j]) for j in range(t - 30, t - 9) if finite(flow[j]))
            if not finite(base):
                base = 0.0
            cand.append((t, abs(v), abs(v) - base, d))
    cand.sort(key=lambda z: (z[2], z[1]), reverse=True)
    picked = []
    for row in cand:
        t = row[0]
        if any(abs(t - p[0]) < REFRACTORY for p in picked):
            continue
        picked.append(row)
    picked.sort(key=lambda z: z[0])
    return picked, cand


def endpoint(stream, t0, pol):
    flow = stream["roll20"]
    last = None
    run = 0
    for i in range(t0 + 1, stream["last_trade_idx"] + 1):
        if finite(flow[i]):
            last = float(flow[i])
        if last is None:
            continue
        run = run + 1 if pol * last <= 0 else 0
        if run >= PERSIST:
            return i - (PERSIST - 1), i
    return None, None


def price_at(stream, idx):
    if idx < 0 or idx >= len(stream["price"]):
        return None
    v = stream["price"][idx]
    return float(v) if finite(v) else None


def price_aftermath(stream, end, pol):
    if end is None:
        return None
    p0 = price_at(stream, end)
    if p0 is None:
        return None
    out = {"endpoint_price": p0, "horizons": {}}
    for h in HORIZONS:
        if end + h > stream["last_trade_idx"]:
            out["horizons"][str(h)] = {"censored": True}
            continue
        p = price_at(stream, end + h)
        vals = [price_at(stream, i) for i in range(end, end + h + 1)]
        vals = [x for x in vals if x is not None]
        if p is None or not vals:
            out["horizons"][str(h)] = {"censored": False, "class": None}
            continue
        signed = pol * (p - p0) / TICK
        oriented = [pol * (x - p0) / TICK for x in vals]
        cls = "continuation" if signed >= MATERIAL_TICKS else ("reversal" if signed <= -MATERIAL_TICKS else "chop")
        out["horizons"][str(h)] = {
            "censored": False,
            "signed_displacement_ticks": signed,
            "class": cls,
            "mfe_ticks": max(oriented),
            "mae_ticks": min(oriented),
        }
    return out


def event_rows_for_week(stream, pre_classifier, a_classifier):
    picked, candidates = detect_week_events(stream)
    flow = stream["roll20"]
    rows = []
    for t0, mag, prom, source_day in picked:
        raw0 = flow[t0]
        if not finite(raw0) or abs(raw0) < 1e-12:
            continue
        pol = 1 if raw0 > 0 else -1
        arc = [pol * flow[t0 + dt] if finite(flow[t0 + dt]) else float("nan") for dt in range(-PRE, POST + 1)]
        filled = fill_curve(arc)
        if filled is None:
            continue
        pre = filled[:PRE + 1]
        post = filled[PRE:]
        peak = pre[-1]
        if peak <= 0:
            continue
        fam = pre_classifier.classify(pre)
        family = fam.family
        a_state = None
        if family == "A":
            a_state = a_classifier.classify_full_minus60_to_plus60(filled).post_state
        zero_s = first_zero(post)
        t50 = first_persist_below(post, peak, .50)
        t25 = first_persist_below(post, peak, .25)
        t10 = first_persist_below(post, peak, .10)
        late_pressure = side_pressure(stream["buy"], stream["sell"], t0 + 41, t0 + 61, pol)
        late_book = [stream["book"][i] for i in range(t0 + 41, t0 + 61) if finite(stream["book"][i])]
        t0_book = [stream["book"][i] for i in range(t0 - 19, t0 + 1) if finite(stream["book"][i])]
        book_late_aligned = None if not late_book else pol * sum(late_book) / len(late_book)
        book_change_aligned = None
        if late_book and t0_book:
            book_change_aligned = pol * ((sum(late_book) / len(late_book)) - (sum(t0_book) / len(t0_book)))
        onset, confirm = endpoint(stream, t0, pol)
        now = dt_from_idx(stream["first_date"], t0)
        local = now.astimezone(ET)
        reopen_dt = dt_from_idx(stream["first_date"], stream["first_trade_idx"])
        since = t0 - stream["first_trade_idx"]
        event_id = f"{ymds(stream['week_sunday'])}-{int(t0):06d}-{pol:+d}"
        row = {
            "event_id": event_id,
            "week_sunday": ymds(stream["week_sunday"]),
            "t0_idx": t0,
            "source_utc_day": source_day,
            "t0_second_utc_day": int((now - datetime.combine(now.date(), time.min, tzinfo=timezone.utc)).total_seconds()),
            "polarity": pol,
            "family": family,
            "pre_family_distances": list(fam.distances),
            "a_frozen_post_state": a_state,
            "seed_state": seed_state(zero_s, late_pressure),
            "feature": {
                "peak_abs": abs(float(raw0)),
                "pre_prominence": prom,
                "exh_t50_s": t50,
                "exh_t25_s": t25,
                "exh_t10_s": t10,
                "exh_zero_onset_within60_s": zero_s,
                "roll20_at60": float(filled[-1]),
                "late_flow_pressure_41_60": late_pressure,
                "book_aligned_late_mean": book_late_aligned,
                "book_aligned_change_from_t0_window": book_change_aligned,
            },
            "dynamic_endpoint": {
                "structural_onset_idx": onset,
                "causal_confirmation_idx": confirm,
                "structural_onset_offset_s": None if onset is None else onset - t0,
                "causal_confirmation_offset_s": None if confirm is None else confirm - t0,
                "censored": confirm is None,
            },
            "time_context": {
                "utc": now.isoformat(),
                "america_new_york": local.isoformat(),
                "local_weekday": local.strftime("%A"),
                "local_clock": local.strftime("%H:%M:%S"),
                "local_hour": local.hour,
                "local_hour_ending": 24 if local.hour == 23 else local.hour + 1,
                "reopen_utc": reopen_dt.isoformat(),
                "seconds_since_reopen_trade": since,
                "hours_since_reopen_trade": since / 3600.0,
                "week_position_fraction": (t0 - stream["first_trade_idx"]) / max(1, stream["last_trade_idx"] - stream["first_trade_idx"]),
            },
            "outcome": {
                "post_endpoint_price": price_aftermath(stream, confirm, pol),
            },
        }
        rows.append(row)
    return rows, {"picked": len(picked), "candidate_count": len(candidates)}


def attach_links(rows):
    rows.sort(key=lambda r: r["t0_idx"])
    for i, r in enumerate(rows):
        r["sequence_index"] = i
        r["link"] = {
            "previous_event_id": None if i == 0 else rows[i - 1]["event_id"],
            "next_event_id": None if i + 1 == len(rows) else rows[i + 1]["event_id"],
        }
        if i + 1 == len(rows):
            r["link"].update({
                "next_dt_s": None,
                "next_polarity": None,
                "next_same_polarity": None,
                "next_seed_state": None,
                "next_family": None,
                "next_starts_before_endpoint_confirmation": None,
                "plus60_state_known_before_next": None,
                "endpoint_known_before_next": None,
            })
            continue
        n = rows[i + 1]
        confirm = r["dynamic_endpoint"]["causal_confirmation_idx"]
        r["link"].update({
            "next_dt_s": n["t0_idx"] - r["t0_idx"],
            "next_polarity": n["polarity"],
            "next_same_polarity": int(n["polarity"] == r["polarity"]),
            "next_seed_state": n["seed_state"],
            "next_family": n["family"],
            "next_starts_before_endpoint_confirmation": None if confirm is None else bool(n["t0_idx"] <= confirm),
            "plus60_state_known_before_next": bool(n["t0_idx"] > r["t0_idx"] + 60),
            "endpoint_known_before_next": None if confirm is None else bool(n["t0_idx"] > confirm),
        })


def load_frozen_roster(reveal_path, holdout_path):
    reveal = json.load(open(reveal_path))
    holdout = json.load(open(holdout_path))
    if len(reveal) != 1718 or len(holdout) != 1711:
        raise SystemExit("frozen roster population drift")
    out = {}
    blind_a = {}
    for split, arr in (("reveal", reveal), ("holdout", holdout)):
        for r in arr:
            key = (str(r["day"]), int(r["t0_second_utc"]), int(r["dipole_polarity"]))
            out[key] = {"split": split, "family": str(r["family"])}
            if split == "holdout" and r["family"] == "A":
                blind_a[key] = r.get("frozen_post_state_assignment", {}).get("label")
    return out, blind_a


def compare_target_roster(all_rows, frozen, blind_a):
    detected = {}
    for r in all_rows:
        key = (r["source_utc_day"], r["t0_second_utc_day"], r["polarity"])
        if key in frozen:
            detected[key] = r
    missing = sorted(set(frozen) - set(detected))
    family_mismatch = []
    a_state_mismatch = []
    for key, r in detected.items():
        if r["family"] != frozen[key]["family"]:
            family_mismatch.append({"key": key, "expected": frozen[key]["family"], "got": r["family"]})
        if key in blind_a and blind_a[key] is not None and r["a_frozen_post_state"] != blind_a[key]:
            a_state_mismatch.append({"key": key, "expected": blind_a[key], "got": r["a_frozen_post_state"]})
    if missing or family_mismatch or a_state_mismatch:
        raise SystemExit(
            f"target equivalence failure missing={len(missing)} family={len(family_mismatch)} a_state={len(a_state_mismatch)}"
        )
    target_days = set(k[0] for k in frozen)
    extra_target = [r for r in all_rows if r["source_utc_day"] in target_days and (r["source_utc_day"], r["t0_second_utc_day"], r["polarity"]) not in frozen]
    return {
        "frozen_events_expected": len(frozen),
        "frozen_events_recovered": len(detected),
        "missing": 0,
        "family_mismatches": 0,
        "blind_a_post_state_mismatches": 0,
        "continuous_week_extra_events_on_target_days": len(extra_target),
        "extra_target_examples": [x["event_id"] for x in extra_target[:20]],
    }


def deterministic_gzip_jsonl(path, rows):
    raw_path = Path(str(path) + ".tmp")
    h = hashlib.sha256()
    with raw_path.open("wb") as f:
        for r in rows:
            line = (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
            f.write(line)
            h.update(line)
    with raw_path.open("rb") as src, Path(path).open("wb") as dst:
        with gzip.GzipFile(filename="", mode="wb", fileobj=dst, mtime=0) as gz:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                gz.write(chunk)
    raw_path.unlink()
    return h.hexdigest(), hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reveal-records", required=True)
    ap.add_argument("--holdout-records", required=True)
    ap.add_argument("--pre-family-classifier", default="research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json")
    ap.add_argument("--a-classifier", default="research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json")
    ap.add_argument("--out-prefix", default="NG_EXHAUSTION_CHAIN_CANONICAL_20260817")
    ap.add_argument("raw_days", nargs="+")
    a = ap.parse_args()

    frozen, blind_a = load_frozen_roster(a.reveal_records, a.holdout_records)
    pre_classifier = FrozenPreFamilyClassifier.load(a.pre_family_classifier)
    a_classifier = FrozenAClassifier.load(a.a_classifier)
    streams = load_week_stream(a.raw_days)

    all_rows = []
    week_summary = {}
    for ws, stream in sorted(streams.items()):
        rows, det = event_rows_for_week(stream, pre_classifier, a_classifier)
        attach_links(rows)
        all_rows.extend(rows)
        first_dt = dt_from_idx(stream["first_date"], stream["first_trade_idx"])
        last_dt = dt_from_idx(stream["first_date"], stream["last_trade_idx"])
        cross_midnight = []
        for x, y in zip(rows, rows[1:]):
            if x["source_utc_day"] != y["source_utc_day"]:
                cross_midnight.append(y["t0_idx"] - x["t0_idx"])
        week_summary[ws] = {
            "event_n": len(rows),
            "candidate_n": det["candidate_count"],
            "first_actual_trade_utc": first_dt.isoformat(),
            "last_actual_trade_utc": last_dt.isoformat(),
            "raw_rows": stream["rows"],
            "trades": stream["trades"],
            "classified_aggressor_trades": stream["classified"],
            "events_by_day": dict(Counter(r["source_utc_day"] for r in rows)),
            "events_by_family": dict(Counter(r["family"] for r in rows)),
            "events_by_seed_state": dict(Counter(r["seed_state"] for r in rows)),
            "cross_utc_date_links": len(cross_midnight),
            "cross_utc_date_link_gap_s_min": None if not cross_midnight else min(cross_midnight),
            "cross_utc_date_link_gap_s_median": None if not cross_midnight else median(cross_midnight),
        }

    equivalence = compare_target_roster(all_rows, frozen, blind_a)
    all_rows.sort(key=lambda r: (r["week_sunday"], r["t0_idx"]))
    table_path = Path(a.out_prefix + "_EVENT_TABLE.jsonl.gz")
    raw_sha, gz_sha = deterministic_gzip_jsonl(table_path, all_rows)

    summary = {
        "status": "CHAIN_CANONICAL_EVENT_TABLE_FROZEN",
        "contract": "research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json",
        "source_seed": "research/NG_EXHAUSTION_AFTERMATH_POSTV2_CHAIN_SEED_FREEZE_20260817.json",
        "event_count": len(all_rows),
        "week_count": len(streams),
        "weeks": week_summary,
        "target_equivalence": equivalence,
        "table": {
            "path": str(table_path),
            "uncompressed_jsonl_sha256": raw_sha,
            "gzip_sha256": gz_sha,
        },
        "feature_outcome_separation": True,
        "event_detection_price_used": False,
        "calendar_day_chain_reset": False,
        "time_of_day_is_gate": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out_prefix + "_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
