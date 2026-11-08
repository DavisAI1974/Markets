"""Run two standalone signals without requiring the falling-touch condition."""
from bisect import bisect_left
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

from adaptive_locality.information import derive_information
from .ng_runner import frozen_bins_from_history
from .october18_book_entropy_pilot import BOOKS, BLOCK, HORIZONS, REPLAY, build_blocks, rows

TRADES = REPLAY / "local-liquidity-v1/every-trade-local-liquidity-links.jsonl.gz"
NANOSECOND = 1_000_000_000
ENTRY_DELAY = 1_000_000


def point(book, line):
    original = book["original_quote_book"]
    return {
        "book_line": line, "group": book["source_ordinal"], "cursor": int(original["input_cursor"]),
        "known_by_ns": int(original["known_by_ns"]),
        "bid_raw": int(book["sides"]["B"]["original_touch_level"]["price_raw"]),
        "ask_raw": int(book["sides"]["A"]["original_touch_level"]["price_raw"]),
    }


def score(points, clocks, index, side):
    start = bisect_left(clocks, clocks[index] + ENTRY_DELAY, lo=index + 1)
    entry = points[start] if start < len(points) else None
    outcomes = {}
    for horizon in HORIZONS:
        if entry is None:
            outcomes[horizon] = {"status": "ENTRY_CENSORED"}
            continue
        end = bisect_left(clocks, clocks[start] + int(horizon) * NANOSECOND, lo=start + 1)
        if end == len(points):
            outcomes[horizon] = {"status": "EXIT_CENSORED"}
            continue
        exit_quote = points[end]
        delta = (exit_quote["bid_raw"] + exit_quote["ask_raw"]
                 - entry["bid_raw"] - entry["ask_raw"])
        signed = delta if side == "A" else -delta
        outcomes[horizon] = {
            "status": "AGREES" if signed > 0 else "OPPOSES" if signed < 0 else "FLAT",
            "signed_twice_midpoint_change_raw": signed, "exit": exit_quote,
        }
    return entry, outcomes


def main(path):
    books = rows(BOOKS)
    points = [point(book, line) for line, book in enumerate(books, 1)]
    clocks = [row["known_by_ns"] for row in points]
    keys, blocks, trailing = build_blocks(books)
    n_cal = len(blocks) // 4
    bins = frozen_bins_from_history(blocks[:n_cal], calibration_fraction=1,
                                    version="oct18-touch-entropy-pilot")
    info = [None] * n_cal + [derive_information(block, bins) for block in blocks[n_cal:]]
    records, dispositions, scores = [], Counter(), defaultdict(Counter)

    def add(rule, status, index, side=None, **evidence):
        dispositions[rule, side or "UNASSIGNED", status] += 1
        entry, outcomes = score(points, clocks, index, side) if status == "TAKE" else (None, {})
        for horizon, outcome in outcomes.items():
            scores[rule, side, horizon][outcome["status"]] += 1
        records.append({"rule": rule, "disposition": status, "side": side, "signal": points[index],
                        "entry": entry, "outcomes": outcomes, **evidence})

    for i, current in enumerate(info):
        for side in ("A", "B"):
            index = (i + 1) * BLOCK - 1
            prior = info[i-1] if i else None
            if current is None:
                add("ENTROPY_ONLY", "CALIBRATION_PERIOD", index, side)
            elif prior is None:
                add("ENTROPY_ONLY", "NEEDS_TWO_POST_CALIBRATION_BLOCKS", index, side)
            elif current.status != "READY" or prior.status != "READY":
                add("ENTROPY_ONLY", "REVIEW_REQUIRED", index, side,
                    reasons=prior.review_reasons + current.review_reasons)
            else:
                before, after = dict(prior.entropy)[side], dict(current.entropy)[side]
                add("ENTROPY_ONLY", "TAKE" if after < before else "NO_ENTROPY_DECLINE", index, side,
                    entropy_nats=[before, after], prior_block_end=keys[i-1])

    links = defaultdict(list)
    for trade in rows(TRADES):
        if trade["window_book_line"] is not None:
            links[trade["window_book_line"]].append(trade)
    for index, book in enumerate(books):
        group_trades = links.get(index + 1, ())
        ordinals = sorted(trade["trade_ordinal"] for trade in group_trades)
        if ordinals != sorted(book["original_trade_ordinals"]):
            raise ValueError(f"Unreconciled print group {index + 1}")
        if not ordinals:
            continue
        signal = points[index]
        for trade in group_trades:
            source = trade["original_trade"]
            clock = trade["exact_clocks"]
            if (source["instrument_id"] != "150611"
                    or clock["group_close_input_cursor"] != signal["cursor"]
                    or clock["trade_input_cursor"] > signal["cursor"]
                    or clock["available_ns"] > signal["known_by_ns"]):
                raise ValueError(f"Print unavailable at group {signal['group']}")
        prints = [int(trade["original_trade"]["price_raw"]) for trade in group_trades]
        evidence = {"print_ordinals": ordinals, "print_prices_raw": prints}
        if not index:
            add("PRINT_ONLY", "NO_PRIOR_BOOK", index, **evidence)
            continue
        prior = points[index-1]
        evidence["prior_book"] = prior
        if all(price == prior["ask_raw"] for price in prints):
            add("PRINT_ONLY", "TAKE", index, "A", **evidence)
        elif all(price == prior["bid_raw"] for price in prints):
            add("PRINT_ONLY", "TAKE", index, "B", **evidence)
        else:
            add("PRINT_ONLY", "AMBIGUOUS_VS_PRIOR_TOUCH", index, **evidence)

    records.sort(key=lambda row: (row["signal"]["book_line"], row["rule"], row["side"] or ""))
    with path.open("xb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
        for record in records:
            stream.write((json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode())
    print(json.dumps({
        "books": len(books), "trailing_groups": trailing, "calibration_blocks": n_cal,
        "records": len(records), "dispositions": [[*key, v] for key, v in sorted(dispositions.items())],
        "outcomes": [[*key, dict(v)] for key, v in sorted(scores.items())],
        "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (BOOKS, TRADES)},
    }, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
