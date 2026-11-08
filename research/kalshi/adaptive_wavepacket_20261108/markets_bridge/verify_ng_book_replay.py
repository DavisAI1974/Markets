"""Replay the two pinned NG sessions using the original native book adapter.

Run as a module from the repository root with a discovery trade date.
Emits a coverage receipt for the available span without scoring.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType
from urllib.request import urlopen

import databento as db


TAPE_PIN = "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202"
ADAPTER_PIN = "af36937d1e478831d4c7bc612c98d969e9a0848b"
SESSION_PIN = "93895487c199b1e486d5407f9e103a0964903d2d"
JOURNAL_PIN = "c28a4de13263b6354662cd376fecc7733b47a991"
ADAPTER_PATH = "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py"
DATA_PATH = "data/nymex_mbo/ng_v0_oct2023"
ARCHIVE = Path(
    "artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/"
    "local-liquidity-v1/all-22194-window-local-liquidity-books.jsonl.gz"
)


def git_blob(pin, path):
    bundled = os.getenv("NG_REPLAY_PINNED_SOURCES")
    if bundled:
        return (Path(bundled) / pin / path).read_bytes()
    return subprocess.check_output(["git", "show", f"{pin}:{path}"])


def tape_blob(name):
    staged = os.getenv("NG_REPLAY_TAPE_DIR")
    if staged:
        return (Path(staged) / name).read_bytes()
    # Read only the named files at the verified Git revision.
    url = f"https://raw.githubusercontent.com/DavisAI1974/Markets/{TAPE_PIN}/{DATA_PATH}/{name}"
    with urlopen(url, timeout=60) as stream:
        return stream.read()


def load_adapter():
    # Execute the original standalone adapter without copying it into the active tree.
    source = git_blob(ADAPTER_PIN, ADAPTER_PATH)
    name = "_pinned_ng_book_adapter"
    module = ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, f"{ADAPTER_PIN}:{ADAPTER_PATH}", "exec"), module.__dict__)
    return module.V4MboAdapter()


def read_member(spec):
    payload = tape_blob(spec["file"])
    if len(payload) != spec["bytes"] or hashlib.sha256(payload).hexdigest() != spec["sha256"]:
        raise ValueError(f"Git tape bytes do not match manifest for {spec['file']}")
    # https://databento.com/docs/api-historical/helpers/dbnstore
    return db.DBNStore.from_bytes(payload)


def expect(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: observed {actual!r}, expected {expected!r}")


def archived_books(day):
    if day != "20231018":
        return {}
    with ARCHIVE.open("rb") as compressed:
        digest = hashlib.file_digest(compressed, "sha256").hexdigest()
    expect(digest, "e31c3fce963eff341396504ab3505ed9b971bcc2f64eabc0f811f148b97349a4",
           "archived October 18 books SHA-256")
    rows = {}
    with gzip.open(ARCHIVE, "rt", encoding="utf-8") as stream:
        for row in map(json.loads, stream):
            group = int(row["source_ordinal"])
            if group in rows:
                raise ValueError(f"duplicate archived book group {group}")
            rows[group] = row
    expect(len(rows), 22_194, "archived October 18 books")
    return rows


def check_book(cursor, group, frame, row):
    source = row["original_quote_book"]
    expect(cursor, int(source["input_cursor"]), f"group {group} cursor")
    expect(frame["ts_recv_ns"], int(source["receive_ns"]), f"group {group} receive clock")
    expect(frame["ts_event_ns"], int(source["event_ns"]), f"group {group} event clock")
    book = frame["book"]
    for side, name in (("B", "bid"), ("A", "ask")):
        touch = row["sides"][side]["original_touch_level"]
        observed = book[f"{name}_levels"][0]
        for key in ("price_raw", "size", "order_count"):
            expect(observed[key], int(touch[key]), f"group {group} {name} touch {key}")
        for key in ("depth_n", "depth_full"):
            field = f"{name}_{key}"
            expect(book[field], int(source[field]), f"group {group} {field}")
        expect(book[f"{name}_price_level_count_full"], int(source[f"{name}_level_n"]),
               f"group {group} {name} price levels")


def run(day, *, observe_group=None):
    began = time.perf_counter()
    scope = json.loads(git_blob(
        SESSION_PIN, f"research/kalshi/frankie_boss/blocks/BLOCK_{day}_SOURCE_MANIFEST.json"
    ))
    prior_receipt = json.loads(git_blob(
        JOURNAL_PIN, f"ingest_pointers/{day}-gh-36571235912-1.json"
    ))["receipt"]
    spec_by_file = {x["file"]: x for x in json.loads(tape_blob("MANIFEST.json"))["files"]}
    members = [spec_by_file[f"NG_v0_mbo_{member['member_key'][10:18]}.dbn.zst"]
               for member in scope["sources"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        prior, current = pool.map(read_member, members)

    adapter = load_adapter()
    opening = prior_receipt["opening_book"]
    tail, head = scope["tail_members"][0], scope["partial_members"][0]
    skip = tail["skip"]
    archive = archived_books(day)
    checks = 0
    cursor = 0
    opening_snapshots = 0

    print(f"{day} replaying {skip:,} opening records", file=sys.stderr, flush=True)
    for i, record in enumerate(prior):
        if i >= skip + tail["take"]:
            raise ValueError("first UTC file exceeds pinned partition length")
        frame, _ = adapter.apply(record, "NGX3")
        if i < skip:
            opening_snapshots += bool(int(record.flags) & 32)
            if i + 1 == skip:
                adapter.assert_groups_closed()
                expect(opening_snapshots, opening["snapshot_records"], f"{day} opening snapshots")
                expect(sum(len(book.orders) for book in adapter.books.values()),
                       opening["resting_orders"], f"{day} opening resting orders")
                adapter.record_count = adapter.completed_event_group_count = 0
                print(f"{day} opening book count matched", file=sys.stderr, flush=True)
            continue
        if frame is not None and observe_group is not None:
            observe_group(cursor, adapter.completed_event_group_count - 1, frame)
        cursor += 1

    expect(cursor, tail["take"], f"{day} prior UTC tail count")
    adapter.assert_groups_closed()
    for record in current:
        if cursor == tail["take"] + head["take"]:
            break
        frame, _ = adapter.apply(record, "NGX3")
        if frame is not None:
            group = adapter.completed_event_group_count - 1
            if group in archive:
                check_book(cursor, group, frame, archive[group])
                checks += 1
            if observe_group is not None:
                observe_group(cursor, group, frame)
        cursor += 1
        if cursor % 200_000 == 0:
            print(f"{day} replayed {cursor:,} session records", file=sys.stderr, flush=True)

    adapter.assert_groups_closed()
    expect(adapter.record_count, prior_receipt["record_count"], f"{day} native records")
    expect(adapter.completed_event_group_count, prior_receipt["group_count"], f"{day} groups")
    expect(checks, len(archive), f"{day} archived book comparisons")
    return {
        "session": day,
        "tape_git_commit": TAPE_PIN,
        "adapter_git_commit": ADAPTER_PIN,
        "session_manifest_commit": SESSION_PIN,
        "sealed_receipt_commit": JOURNAL_PIN,
        "databento_version": db.__version__,
        "opening_warmup_records": skip,
        "opening_snapshot_records": opening_snapshots,
        "opening_resting_orders": opening["resting_orders"],
        "records": adapter.record_count,
        "completed_groups": adapter.completed_event_group_count,
        "archived_books_compared": checks,
        "integrity": {str(key): dict(book.integrity) for key, book in adapter.books.items()},
        "wall_seconds": round(time.perf_counter() - began, 2),
    }


def run_partial(day, *, observe_group=None):
    """Replay the available midnight-to-halt portion of an earlier trade date."""
    following_day, groups, trades = {
        "20231002": ("20231003", 600291, 37670),
        "20231017": ("20231018", 635170, 33451),
    }[day]
    began = time.perf_counter()
    scope = json.loads(git_blob(
        SESSION_PIN, f"research/kalshi/frankie_boss/blocks/BLOCK_{following_day}_SOURCE_MANIFEST.json"
    ))
    next_opening = json.loads(git_blob(
        JOURNAL_PIN, f"ingest_pointers/{following_day}-gh-36571235912-1.json"
    ))["receipt"]["opening_book"]
    file_name = f"NG_v0_mbo_{day}.dbn.zst"
    spec = next(item for item in json.loads(tape_blob("MANIFEST.json"))["files"] if item["file"] == file_name)
    limit = scope["tail_members"][0]["skip"]
    adapter = load_adapter()
    first = last = None
    snapshots = trade_count = 0
    for index, record in enumerate(read_member(spec)):
        if index == limit:
            expect(record.ts_recv // 3_600_000_000_000 % 24, 21, "first halt record UTC hour")
            break
        if index == 0:
            first = record.ts_recv
            expect(first % 86_400_000_000_000, 0, "UTC midnight snapshot clock")
            expect(bool(record.flags & 32), True, "opening UTC snapshot flag")
        expect(record.instrument_id, 150611, "tape instrument")
        if last is not None and record.ts_recv < last:
            raise ValueError("Nonmonotonic receive clock")
        last = record.ts_recv
        snapshots += bool(record.flags & 32)
        trade_count += record.action.value == "T"
        frame, _ = adapter.apply(record, "NGX3")
        if frame is not None and observe_group is not None:
            observe_group(index, adapter.completed_event_group_count - 1, frame)
        if (index + 1) % 200_000 == 0:
            print(f"{day} replayed {index + 1:,} available records", file=sys.stderr, flush=True)
    else:
        raise ValueError("Missing pinned halt boundary record")
    adapter.assert_groups_closed()
    expect(adapter.record_count, limit, "available trade-date records")
    expect(adapter.completed_event_group_count, groups, "available trade-date group count")
    expect(snapshots, next_opening["snapshot_records"], "available snapshot records")
    expect(trade_count, trades, "available trades")
    orders = sum(len(book.orders) for book in adapter.books.values())
    expect(orders, next_opening["resting_orders"], "resting orders at halt")
    return {
        "session": day,
        "scope": "PARTIAL_TRADE_DATE",
        "tape_git_commit": TAPE_PIN,
        "adapter_git_commit": ADAPTER_PIN,
        "boundary_manifest_commit": SESSION_PIN,
        "databento_version": db.__version__,
        "first_ts_recv_ns": first,
        "last_ts_recv_ns": last,
        "records": limit,
        "completed_groups": groups,
        "trades": trades,
        "opening_snapshot_records": snapshots,
        "resting_orders_at_halt": orders,
        "archived_books_compared": 0,
        "integrity": {str(key): dict(book.integrity) for key, book in adapter.books.items()},
        "wall_seconds": round(time.perf_counter() - began, 2),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", choices=("20231002", "20231003", "20231017", "20231018"))
    day = parser.parse_args().day
    replay = run_partial if day in {"20231002", "20231017"} else run
    print(json.dumps(replay(day), indent=2), flush=True)
