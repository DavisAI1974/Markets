"""Paired real-data NG book entropy pilot. See the October 18 pilot receipt."""
from bisect import bisect_right
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

from adaptive_locality.information import RawFrame, RawMember, derive_information
from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner import frozen_bins_from_history

DAY = "20231018"
INSTRUMENT = 150611
BLOCK = 60
SOURCE = f"NG:{DAY}:{INSTRUMENT}:native_group_close"
HORIZONS = ("1", "5", "30")
REPLAY = Path("artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1")
BOOKS = REPLAY / "local-liquidity-v1/all-22194-window-local-liquidity-books.jsonl.gz"
SIGNALS = REPLAY / "historical-paper-replay-v1/every-early-falling-touch-signal.jsonl.gz"


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def coordinate(quote):
    return int(quote["known_by_ns"]), int(quote["cursor"])


def asof_index(coordinates, signal):
    return bisect_right(coordinates, signal) - 1


def build_blocks(books):
    coordinates, frames, members = [], [], []
    last_group, last_key = None, None
    for line, book in enumerate(books, 1):
        quote = book["original_quote_book"]
        group = int(book["source_ordinal"])
        clock = int(quote["known_by_ns"])
        cursor = int(quote["input_cursor"])
        key = clock, cursor
        if int(quote["instrument_id"]) != INSTRUMENT or int(quote["source_ordinal"]) != group:
            raise ValueError(f"Book identity mismatch at line {line}")
        if last_group is not None and (group != last_group + 1 or key <= last_key or cursor <= last_key[1]):
            raise ValueError(f"Book gap or nonmonotonic clock/cursor at line {line}")
        last_group, last_key = group, key
        for side in ("B", "A"):
            touch = book["sides"][side]["original_touch_level"]
            if (int(touch["input_cursor"]), int(touch["known_by_ns"])) != (cursor, clock):
                raise ValueError(f"Touch source mismatch at line {line}")
            size = int(touch["size"])
            members.append(RawMember(f"{SOURCE}:{group}:{side}", str(group), side, size,
                                     f"{BOOKS}:{line}:sha256={quote['source_row_sha256']}"))
        if line % BLOCK == 0:
            coordinates.append(key)
            frames.append(RawFrame(clock, SOURCE, tuple(members)))
            members.clear()
    return coordinates, frames, len(members) // 2


def baseline_result(row, horizon):
    outcome = row["outcomes"][horizon]
    if outcome["status"] != "OBSERVED":
        return outcome["status"]
    movement = outcome["signed_twice_midpoint_change_raw"]
    return "AGREES" if movement > 0 else "OPPOSES" if movement < 0 else "FLAT"


def main(output):
    books, signals = rows(BOOKS), rows(SIGNALS)
    keys, blocks, trailing_groups = build_blocks(books)
    n_cal = len(blocks) // 4
    if not n_cal or len(blocks) < n_cal + 2:
        raise ValueError("Insufficient blocks for calibration and testing")
    bins = frozen_bins_from_history(blocks[:n_cal], calibration_fraction=1,
                                    version="oct18-touch-entropy-pilot")
    info = [None] * n_cal + [derive_information(frame, bins) for frame in blocks[n_cal:]]
    all_counts = Counter()
    scored_counts = Counter()
    per_signal = []
    for line, row in enumerate(signals, 1):
        key = coordinate(row["signal"])
        book_line = row["signal"]["book_line"]
        book = books[book_line - 1]
        quote = book["original_quote_book"]
        if (int(quote["known_by_ns"]), int(quote["input_cursor"])) != key or book["source_ordinal"] != row["signal"]["group"]:
            raise ValueError(f"Signal source mismatch at line {line}")
        side = row["side"]
        i = asof_index(keys, key)
        before = after = None
        reason_ids = ()
        if i < n_cal:
            decision = "CALIBRATION_PERIOD"
        elif i == n_cal:
            decision = "NEEDS_TWO_POST_CALIBRATION_BLOCKS"
        elif any(frame.status != "READY" for frame in info[i-1:i+1]):
            decision = "REVIEW_REQUIRED"
            reason_ids = tuple(reason for frame in info[i-1:i+1] for reason in frame.review_reasons)
        else:
            before, after = (dict(frame.entropy)[side] for frame in info[i-1:i+1])
            decision = "TAKE" if after < before else "SKIP_NO_COMPRESSION"
        all_counts[side, decision] += 1
        outcomes = {}
        for horizon in HORIZONS:
            result = baseline_result(row, horizon)
            scored_counts[side, horizon, decision, result] += 1
            outcomes[horizon] = {
                "midpoint_result": result,
                "status": row["outcomes"][horizon]["status"],
                "signed_twice_midpoint_change_raw": row["outcomes"][horizon].get("signed_twice_midpoint_change_raw"),
                "exit": row["outcomes"][horizon].get("exit"),
            }
        per_signal.append({
            "signal_line": line, "side": side, "signal": row["signal"], "entry": row["entry"],
            "overlay": decision, "prior_entropy_nats": before, "latest_entropy_nats": after,
            "latest_block_end": keys[i] if i >= 0 else None,
            "prior_block_end": keys[i-1] if i >= 1 else None,
            "latest_block_age_ns": key[0] - keys[i][0] if i >= 0 else None,
            "review_reasons": reason_ids, "baseline_outcomes": outcomes,
        })
    if len(per_signal) != len(signals) or sum(all_counts.values()) != len(signals):
        raise ValueError("Signal reconciliation failed")
    report = {
        "source_identity": SOURCE, "block_size_completed_groups": BLOCK, "books": len(books),
        "input_sha256": {str(path): hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
                         for path in (BOOKS, SIGNALS)},
        "calibration_blocks": n_cal, "calibration_end": keys[n_cal-1], "bins": dict(bins.edges),
        "total_complete_blocks": len(blocks), "trailing_groups_preserved_in_source": trailing_groups,
        "post_calibration_block_status": dict(Counter(frame.status for frame in info[n_cal:])),
        "signals": len(signals), "rule": "Take existing signal only if same-side entropy declines",
        "outcome": "original signed midpoint change, at 1/5/30 seconds after replay entry",
        "decisions": [[side, decision, count] for (side, decision), count in sorted(all_counts.items())],
        "results": [[side, horizon, decision, result, count]
                    for (side, horizon, decision, result), count in sorted(scored_counts.items())],
    }
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            for row in per_signal:
                stream.write((json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n").encode())
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
