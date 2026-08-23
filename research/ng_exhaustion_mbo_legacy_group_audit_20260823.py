#!/usr/bin/env python3
"""Read-only exact-day audit of MBO event groups against authoritative MBP-10 rows."""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import databento as db

from ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _price(value: Any) -> float | None:
    number = _number(value)
    return None if number is None or abs(number) >= 9e9 else number


def mbp_book_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    signature: list[Any] = []
    for i in range(10):
        signature.extend((
            _price(row.get(f"bid_px_{i:02d}")),
            int(row.get(f"bid_sz_{i:02d}", 0) or 0),
            int(row.get(f"bid_ct_{i:02d}", 0) or 0),
            _price(row.get(f"ask_px_{i:02d}")),
            int(row.get(f"ask_sz_{i:02d}", 0) or 0),
            int(row.get(f"ask_ct_{i:02d}", 0) or 0),
        ))
    return tuple(signature)


def frame_book_signature(frame: dict[str, Any]) -> tuple[Any, ...]:
    book = frame["book"]
    bids = book["bid_levels"]
    asks = book["ask_levels"]
    signature: list[Any] = []
    for i in range(10):
        bid = bids[i] if i < len(bids) else None
        ask = asks[i] if i < len(asks) else None
        signature.extend((
            None if bid is None else _price(bid.get("price")),
            0 if bid is None else int(bid.get("size", 0)),
            0 if bid is None else int(bid.get("order_count", 0)),
            None if ask is None else _price(ask.get("price")),
            0 if ask is None else int(ask.get("size", 0)),
            0 if ask is None else int(ask.get("order_count", 0)),
        ))
    return tuple(signature)


def signatures_equal(left: tuple[Any, ...], right: tuple[Any, ...]) -> bool:
    if len(left) != len(right):
        return False
    for lv, rv in zip(left, right):
        if lv is None or rv is None:
            if lv is not None or rv is not None:
                return False
        elif isinstance(lv, float) or isinstance(rv, float):
            if not math.isclose(float(lv), float(rv), rel_tol=0.0, abs_tol=1e-12):
                return False
        elif lv != rv:
            return False
    return True


def _timestamp_us(value: Any) -> int:
    number = float(value)
    return int(round(number / 1_000.0)) if abs(number) > 1e14 else int(round(number * 1e6))


def row_key(row: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(row.get("instrument_id", 0)),
        int(row.get("sequence", 0)),
        _timestamp_us(row.get("ts_event", row.get("ts", 0.0))),
    )


def load_mbp(path: Path) -> tuple[dict[tuple[int, int, int], list[dict[str, Any]]], int]:
    grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = collections.defaultdict(list)
    count = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            grouped[row_key(row)].append(row)
            count += 1
    return dict(grouped), count


def audit(mbp_path: Path, mbo_path: Path) -> dict[str, Any]:
    mbp_by_key, mbp_count = load_mbp(mbp_path)
    remaining = dict(mbp_by_key)
    adapter = V4MboAdapter()
    previous_book: dict[int, tuple[Any, ...]] = {}
    pattern_counts: collections.Counter[str] = collections.Counter()
    group_counts: collections.Counter[str] = collections.Counter()
    raw_row_book_matches = 0
    raw_row_book_mismatches = 0
    matched_mbp_rows = 0
    examples: list[dict[str, Any]] = []
    mbo_records = 0

    store = db.DBNStore.from_file(str(mbo_path))
    for record in store:
        if type(record).__name__ not in {"MboMsg", "MBOMsg"}:
            continue
        frame, _legacy = adapter.apply(record)
        mbo_records += 1
        if frame is None:
            continue
        iid = int(frame["instrument_id"])
        actions = frame["raw_actions"]
        sequence = int(frame["sequence"])
        action_keys = []
        for action in actions:
            key = (
                iid,
                int(action["sequence"]),
                _timestamp_us(action["ts_event_ns"]),
            )
            if key not in action_keys:
                action_keys.append(key)
        mbp_rows = []
        for key in action_keys:
            mbp_rows.extend(remaining.pop(key, []))
        post = frame_book_signature(frame)
        before = previous_book.get(iid)
        changed = before is None or not signatures_equal(before, post)
        previous_book[iid] = post
        snapshot = bool(actions) and all(bool(row.get("is_snapshot")) for row in actions)
        mbo_pattern = "".join(str(row.get("action")) for row in actions)
        mbp_pattern = "".join(str(row.get("action")) for row in mbp_rows)
        has_trade = any(row.get("action") == "T" for row in actions)
        category = (
            f"snapshot={int(snapshot)}|trade={int(has_trade)}|top10_changed={int(changed)}|"
            f"mbp_rows={len(mbp_rows)}"
        )
        group_counts[category] += 1
        pattern_counts[f"mbo={mbo_pattern}|mbp={mbp_pattern or '-'}"] += 1
        matched_mbp_rows += len(mbp_rows)
        mismatched_books = 0
        for row in mbp_rows:
            if signatures_equal(post, mbp_book_signature(row)):
                raw_row_book_matches += 1
            else:
                raw_row_book_mismatches += 1
                mismatched_books += 1
        unexpected = (
            (snapshot and mbp_rows)
            or (not snapshot and has_trade and not mbp_rows)
            or (not snapshot and changed and not mbp_rows)
            or mismatched_books
        )
        if unexpected and len(examples) < 100:
            examples.append({
                "instrument_id": iid,
                "sequence": sequence,
                "ts_event_ns": int(frame["ts_event_ns"]),
                "snapshot": snapshot,
                "top10_changed": changed,
                "mbo_actions": mbo_pattern,
                "mbp_actions": mbp_pattern,
                "mbp_row_count": len(mbp_rows),
                "mbp_book_mismatch_count": mismatched_books,
            })

    adapter.assert_groups_closed()
    unmatched_rows = [row for rows in remaining.values() for row in rows]
    return {
        "schema": "NG_EXHAUSTION_MBO_LEGACY_GROUP_AUDIT_V1_20260823",
        "mbp10_gzip_sha256": sha256_file(mbp_path),
        "mbo_dbn_sha256": sha256_file(mbo_path),
        "mbo_record_count": mbo_records,
        "mbo_completed_group_count": adapter.completed_event_group_count,
        "mbp10_row_count": mbp_count,
        "matched_mbp10_row_count": matched_mbp_rows,
        "unmatched_mbp10_row_count": len(unmatched_rows),
        "unmatched_mbp10_action_counts": dict(sorted(collections.Counter(
            str(row.get("action")) for row in unmatched_rows
        ).items())),
        "post_group_book_match_count": raw_row_book_matches,
        "post_group_book_mismatch_count": raw_row_book_mismatches,
        "group_category_counts": dict(sorted(group_counts.items())),
        "top_group_action_patterns": [
            {"pattern": pattern, "count": count}
            for pattern, count in pattern_counts.most_common(100)
        ],
        "first_unexpected_examples": examples,
        "source_prefix_wide_enumeration_used": False,
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mbp10", type=Path, required=True)
    parser.add_argument("--mbo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.mbp10, args.mbo)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
