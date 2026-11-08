"""Build the exact trade-clock input for the date-scoped SQLite replay."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from .verify_absorption_ratio import DAY_NS, DAYS, HALT, NEXT, OPEN, records
from .verify_ng_book_replay import SESSION_PIN, TAPE_PIN, expect


FAMILIES = Path("artifacts/sqlite-triage/20261022/families")
ARCHIVE = FAMILIES / "price-curve-timestamps.csv"
FIELDS = (
    "source_ordinal", "trade_input_cursor", "group_close_input_cursor", "group_ordinal",
    "instrument_id", "event_ns", "receive_ns", "available_ns", "price_raw", "size", "aggressor_side",
)
ARCHIVED_COMPARABLE = (
    "source_ordinal", "trade_input_cursor", "group_close_input_cursor", "instrument_id",
    "event_ns", "receive_ns", "available_ns", "price_raw", "size",
)
TAPE_COUNTS = {
    "20231002": (808453, 600291, 37670),
    "20231003": (879830, 653912, 41410),
    "20231017": (841601, 635170, 33451),
    "20231018": (771787, 583688, 30739),
}


def build(day):
    trades, pending = [], []
    total = group = 0
    last_clock = None
    for cursor, record in records(day):
        if cursor < 0:
            continue
        expect(cursor, total, "contiguous source cursor")
        expect(record.instrument_id, 150611, "NGX3 instrument")
        if last_clock is not None and record.ts_recv < last_clock:
            raise ValueError(f"Receive clock regressed at cursor {cursor}")
        last_clock = record.ts_recv
        total += 1
        if record.action.value == "T":
            phase = record.ts_recv % DAY_NS
            if record.flags & 32 or HALT <= phase < OPEN:
                raise ValueError(f"Trade encountered in snapshot/halt at cursor {cursor}")
            pending.append((cursor, record))
        if record.flags & 128:
            for trade_cursor, trade in pending:
                trades.append(dict(
                    source_ordinal=len(trades), trade_input_cursor=trade_cursor,
                    group_close_input_cursor=cursor, group_ordinal=group,
                    instrument_id=trade.instrument_id, event_ns=trade.ts_event,
                    receive_ns=trade.ts_recv, available_ns=record.ts_recv,
                    price_raw=trade.price, size=trade.size, aggressor_side=trade.side.value,
                ))
            pending.clear()
            group += 1
    if pending:
        raise ValueError("Unclosed trades at the date boundary")
    expect((total, group, len(trades)), TAPE_COUNTS[day], f"{day} exact source population")
    return trades


def check_archived(trades):
    with ARCHIVE.open(encoding="utf-8", newline="") as stream:
        for recorded, decoded in zip(csv.DictReader(stream), trades, strict=True):
            expected = tuple(int(recorded[key]) for key in ARCHIVED_COMPARABLE)
            actual = tuple(decoded[key] for key in ARCHIVED_COMPARABLE)
            expect(actual, expected, f"archived trade {decoded['source_ordinal']}")
    return len(trades)


def write_csv(path, trades):
    with path.open("xb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as binary:
        with io.TextIOWrapper(binary, encoding="utf-8", newline="") as text:
            writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(trades)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        for stored, decoded in zip(csv.DictReader(stream), trades, strict=True):
            expect(stored, {k: str(v) for k, v in decoded.items()}, "trade CSV read-back")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", choices=DAYS)
    parser.add_argument("--output", type=Path, help="Write verified trade-clock rows to a new gzip CSV")
    args = parser.parse_args()
    trades = build(args.day)
    compared = check_archived(trades) if args.day == "20231018" else 0
    receipt = dict(
        trade_date=args.day, scope="available partial trade date" if args.day in NEXT else "full trade date",
        tape_git_commit=TAPE_PIN, boundary_manifest_git_commit=SESSION_PIN,
        source_records=TAPE_COUNTS[args.day][0], completed_groups=TAPE_COUNTS[args.day][1],
        trades=len(trades), archived_trades_compared=compared,
        clock_basis="Integer event/receive nanoseconds and receive clock of the source F_LAST record",
        ordinal_basis="Zero-based tape trade, session input and F_LAST group coordinates",
    )
    if args.output is not None:
        receipt["output"] = args.output.name
        receipt["sha256"] = write_csv(args.output, trades)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
