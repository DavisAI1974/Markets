"""Export and reconcile standalone touch and print inputs for a discovery date."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile

from .export_trade_clocks import ARCHIVE, ARCHIVED_COMPARABLE, TAPE_COUNTS
from .verify_ng_book_replay import expect, run, run_partial


DAY = "20231018"
INSTRUMENT = 150611
ARCHIVED_PRINTS_SHA256 = "fe842ad1cb670973abc8311273363cedb8e447b56ae9b30c0479828057fff3d5"
TRADE_CLOCKS = Path(__file__).parent / "tasks" / "trade-clock-inputs"


def group_row(cursor, ordinal, frame):
    actions = frame["raw_actions"]
    expect(frame["instrument_id"], INSTRUMENT, f"group {ordinal} instrument")
    expect([bool(a["flags"] & 128) for a in actions], [False] * (len(actions) - 1) + [True],
           f"group {ordinal} F_LAST boundary")
    start = cursor - len(actions) + 1
    receive = frame["ts_recv_ns"]
    row = dict(group_ordinal=ordinal, first_cursor=start, close_cursor=cursor,
               event_ns=frame["ts_event_ns"], receive_ns=receive,
               snapshot_member=any(a["flags"] & 32 for a in actions),
               reset_member=any(a["action"] == "R" for a in actions),
               bad_receive_clock_member=any(a["flags"] & 8 for a in actions))
    for side in ("bid", "ask"):
        levels = frame["book"][f"{side}_levels"]
        row[side] = [levels[0][k] for k in ("price_raw", "size", "order_count")] if levels else None
    prints = [
        dict(trade_input_cursor=index, group_close_input_cursor=cursor, group_ordinal=ordinal,
             instrument_id=INSTRUMENT, event_ns=a["ts_event_ns"], receive_ns=a["ts_recv_ns"],
             available_ns=receive, price_raw=a["price_raw"], size=a["size"], aggressor_side=a["side"],
             order_id=a["order_id"], sequence=a["sequence"], flags=a["flags"])
        for index, a in enumerate(actions, start) if a["action"] == "T"
    ]
    row["print_count"] = len(prints)
    return row, prints


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export(output, *, day=DAY):
    if output.exists():
        raise FileExistsError(output)
    if day == DAY:
        archive_path, archive_sha, opener = ARCHIVE, ARCHIVED_PRINTS_SHA256, open
        compare = ARCHIVED_COMPARABLE
    else:
        saved = next(r for r in json.loads((TRADE_CLOCKS / "receipt.json").read_bytes()) if r["trade_date"] == day)
        archive_path, archive_sha, opener = TRADE_CLOCKS / saved["output"], saved["sha256"], gzip.open
        compare = (*ARCHIVED_COMPARABLE, "group_ordinal")
    expect(digest(archive_path), archive_sha, f"{day} print reference SHA-256")
    replay = run_partial if day in {"20231002", "20231017"} else run
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{day}-inputs-", dir=output.parent) as tmp:
        pending = Path(tmp)
        path = pending / "groups.jsonl.gz"
        counts = Counter()
        next_cursor = 0
        last_recv = None
        with (opener(archive_path, "rt", encoding="utf-8", newline="") as archive, path.open("xb") as raw,
              gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=3) as packed,
              io.TextIOWrapper(packed, encoding="utf-8", newline="\n") as groups):
            original = csv.DictReader(archive)

            def observe(cursor, ordinal, frame):
                nonlocal next_cursor, last_recv
                row, prints = group_row(cursor, ordinal, frame)
                expect(ordinal, counts["groups"], "contiguous group")
                expect(row["first_cursor"], next_cursor, f"group {ordinal} first cursor")
                for action in frame["raw_actions"]:
                    receive = action["ts_recv_ns"]
                    if last_recv is not None and receive < last_recv:
                        raise ValueError(f"Receive clock regressed in group {ordinal}")
                    last_recv = receive
                expect(row["receive_ns"], last_recv, f"group {ordinal} close receive time")
                next_cursor = cursor + 1
                for trade in prints:
                    trade["source_ordinal"] = counts["prints"]
                    saved = next(original, None)
                    if saved is None:
                        raise ValueError(f"No archived print for {trade['source_ordinal']}")
                    expect(tuple(trade[k] for k in compare),
                           tuple(int(saved[k]) for k in compare),
                           f"archived print {trade['source_ordinal']}")
                    if day != DAY:
                        expect(trade["aggressor_side"], saved["aggressor_side"], "tape print aggressor side")
                    counts["prints"] += 1
                counts["groups"] += 1
                counts["no_print_groups"] += not prints
                counts["without_two_sided_touch"] += row["bid"] is None or row["ask"] is None
                for name in ("snapshot_member", "reset_member", "bad_receive_clock_member"):
                    counts[name] += row[name]
                row["prints"] = prints
                groups.write(json.dumps(row, separators=(",", ":")) + "\n")

            receipt = replay(day, observe_group=observe)
            expect(next(original, None), None, "unmatched archived prints")
            expect((next_cursor, counts["groups"], counts["prints"]), TAPE_COUNTS[day],
                   "available session coverage")

        expect(digest(archive_path), archive_sha, "print reference unchanged during replay")
        receipt.update(
            coverage_scope="Pinned native group-close touch and trade print inputs",
            full_discovery_gate="NOT_PASSED",
            counts=dict(counts),
            archived_prints_sha256=archive_sha,
            groups_file=dict(path=path.name, bytes=path.stat().st_size, sha256=digest(path)),
            format=dict(instrument_id=INSTRUMENT, cursor_base=0, group_base=0,
                        touch_fields=["price_raw", "size", "order_count"],
                        known_by="group close receive_ns; ties ordered by close_cursor",
                        note="Boundary flags and empty sides are retained; no rule eligibility is inferred."),
        )
        (pending / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        pending.rename(output)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", choices=TAPE_COUNTS, default=DAY)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.output_dir, day=args.day), indent=2))


if __name__ == "__main__":
    main()
