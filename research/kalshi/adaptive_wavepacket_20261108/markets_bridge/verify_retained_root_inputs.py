"""Check retained ROOT values and independently rebuild resting orders from pinned DBN."""

from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import gzip
import json
from pathlib import Path
import struct
import subprocess
import time

from databento_dbn import UNDEF_PRICE, UNDEF_TIMESTAMP

from .verify_ng_book_replay import SESSION_PIN, TAPE_PIN, expect, git_blob, read_member, tape_blob


ROOT_PIN = "2de247bbf02c3918e537c32d32c3267a54d563df"
ROOT_PATH = Path("artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1")
DAY = "20231018"
INSTRUMENT = 150611
WINDOWS = (1, 5, 20, 60, 300)
NS_PER_SECOND = 1_000_000_000
COMMON = ("instrument_id", "publisher_id", "channel_id", "order_id", "size", "flags", "sequence", "action", "side")
RENAMED = {"ts_event": "ts_event_ns", "ts_recv": "ts_recv_ns", "ts_in_delta": "ts_in_delta_ns", "price": "price_raw"}


@dataclass(frozen=True, slots=True)
class Order:
    side: str
    price: int
    size: int
    priority_recv: int
    priority_sequence: int
    last_update: int
    priority_from_snapshot: bool
    update_from_snapshot: bool


class RestingBook:
    """Independent order map in priority-insertion order for Databento MBO."""

    def __init__(self):
        self.orders = {}

    def apply(self, record):
        action = record.action.value
        if action in {"T", "F", "N"}:
            return
        if action == "R":
            self.orders.clear()
            return

        oid, side, price, size = record.order_id, record.side.value, record.price, record.size
        if side not in {"A", "B"} or price == UNDEF_PRICE or size < 0 or record.flags & (16 | 64):
            raise ValueError(f"Unsupported book-mutating message for order {oid}")
        old = self.orders.get(oid)
        if action == "C":
            if old is None or (side, price) != (old.side, old.price) or size > old.size:
                raise ValueError(f"Unreconciled cancel for order {oid}")
            if size == old.size:
                del self.orders[oid]
            else:
                self.orders[oid] = replace(old, size=old.size - size, last_update=record.ts_recv,
                                           update_from_snapshot=False)
            return

        if action == "A" and old is not None:
            raise ValueError(f"Duplicate active order {oid}")
        if action not in {"A", "M"}:
            raise ValueError(f"Unsupported book action {action!r}")
        if old is not None and side != old.side:
            raise ValueError(f"Unsupported side change for order {oid}")
        if old is not None and price == old.price and 0 < size <= old.size:
            self.orders[oid] = replace(old, size=size, last_update=record.ts_recv, update_from_snapshot=False)
            return
        if old is not None:
            del self.orders[oid]
        if size:
            snapshot = bool(record.flags & 32)
            self.orders[oid] = Order(side, price, size, record.ts_recv, record.sequence, record.ts_recv,
                                     snapshot, snapshot)


def check_book(frame, book, checked):
    observation = frame["observation"]
    rows = {row["order_id"]: row for row in observation["orders"]}
    expect(len(rows), len(observation["orders"]), "unique observed orders")
    expect(rows.keys(), book.orders.keys(), "resting identities")
    cutoff = frame["ts_recv_ns"]
    levels = defaultdict(list)
    for oid, order in book.orders.items():
        observed = rows[oid]
        expected = (order.side, order.price, order.size, order.priority_recv, order.priority_sequence,
                    order.last_update)
        actual = tuple(observed[key] for key in (
            "side", "price_raw", "size", "priority_recv_ns", "priority_sequence", "last_update_recv_ns"
        ))
        expect(actual, expected, f"resting order {oid} state and source clocks")
        if not order.priority_recv <= order.last_update <= cutoff:
            raise ValueError(f"Out-of-order clocks for resting order {oid}")
        levels[order.side, order.price].append((oid, order.size))
        checked["resting_orders"] += 1
        checked["snapshot_priority_observations"] += order.priority_from_snapshot
        checked["snapshot_last_update_observations"] += order.update_from_snapshot

    for side, name in (("B", "bid"), ("A", "ask")):
        prices = sorted((price for label, price in levels if label == side), reverse=side == "B")
        full = frame["book"][f"{name}_levels_full"]
        expect([level["price_raw"] for level in full], prices, f"{name} full depth prices")
        for level, price in zip(full, prices, strict=True):
            queue = levels[side, price]
            expect(level["size"], sum(size for _, size in queue), f"{name} level size")
            expect(level["order_count"], len(queue), f"{name} order count")
            volume_ahead = 0
            for row, (oid, size) in zip(level["fifo_queue"], queue, strict=True):
                expect((row["order_id"], row["size"], row["volume_ahead"]), (oid, size, volume_ahead),
                       f"{name} FIFO state at {price}")
                volume_ahead += size
            checked["full_depth_levels"] += 1


def unpack(value):
    tag, *payload = value
    if tag == "null":
        return None
    item, = payload
    if tag == "dict":
        return {key: unpack(nested) for key, nested in item}
    if tag == "list":
        return [unpack(nested) for nested in item]
    if tag == "bytes":
        return bytes.fromhex(item)
    if tag == "float64":
        return struct.unpack(">d", bytes.fromhex(item))[0]
    if tag in {"str", "int", "bool"}:
        return item
    raise ValueError(f"Unreviewed packed ROOT encoding {tag!r}")


def archived_frames():
    listing = subprocess.check_output(["git", "ls-tree", ROOT_PIN, "--", str(ROOT_PATH.as_posix())], text=True)
    if not listing:
        raise ValueError("Missing pinned ROOT archive tree")
    directory_oid = listing.split()[2]
    listing = subprocess.check_output(["git", "ls-tree", directory_oid], text=True)
    chunk_pins = {
        name: meta.split()[2] for meta, name in (line.split("\t") for line in listing.splitlines())
        if name.startswith("root.frames.chunk") and name.endswith(".jsonl.gz")
    }
    expect(len(chunk_pins), 16, "pinned ROOT chunks")
    for name, oid in sorted(chunk_pins.items()):
        path = ROOT_PATH / name
        actual_oid = subprocess.check_output(["git", "hash-object", "--no-filters", str(path)], text=True).strip()
        expect(actual_oid, oid, name)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                tag, pairs = json.loads(line)
                expect(tag, "dict", "packed ROOT row")
                row = dict(pairs)
                frame = {key: unpack(row[key]) for key in (
                    "input_cursor", "input_records", "input_record_indices", "ts_recv_ns", "ts_event_ns", "activity",
                    "book", "observation"
                )}
                frame["raw_actions"] = unpack(dict(row["native_frame"][1])["raw_actions"])
                yield frame


def tape_groups(book):
    scope = json.loads(git_blob(SESSION_PIN, f"research/kalshi/frankie_boss/blocks/BLOCK_{DAY}_SOURCE_MANIFEST.json"))
    tail = scope["tail_members"][0]
    member_name = f"NG_v0_mbo_{tail['member_key'][10:18]}.dbn.zst"
    spec = next(item for item in json.loads(tape_blob("MANIFEST.json"))["files"] if item["file"] == member_name)
    clocks, activity, pending = [], [], []
    group = 0
    for index, record in enumerate(read_member(spec)):
        cursor = index - tail["skip"]
        expect(record.instrument_id, INSTRUMENT, "tape instrument")
        book.apply(record)
        if not record.flags & 32:
            if clocks and record.ts_recv < clocks[-1]:
                raise ValueError("Nonmonotonic receive times in activity history")
            clocks.append(record.ts_recv)
            activity.append((record.action.value, record.side.value, int(record.size)))
        if cursor < 0:
            continue
        if cursor >= tail["take"]:
            break
        pending.append((cursor, record))
        if record.flags & 128:
            yield group, pending, clocks, activity
            group += 1
            pending = []


def check_raw(frame, pending):
    expect(frame["input_record_indices"], [cursor for cursor, _ in pending], "native group record indices")
    cursor, closing = pending[-1]
    for field, value in (("input_cursor", cursor), ("ts_recv_ns", closing.ts_recv), ("ts_event_ns", closing.ts_event)):
        expect(frame[field], value, f"group close {field}")
    for original, normalized, (_, record) in zip(frame["input_records"], frame["raw_actions"], pending, strict=True):
        wire = bytes(record)
        values = {field: int(getattr(record, field)) for field in (*COMMON[:-2], *RENAMED, "rtype")}
        values.update(action=record.action.value, side=record.side.value)
        for field, value in values.items():
            expect(original[field], value, f"native {field}")
        expect(original["dbn_wire_bytes"], wire, "native DBN wire bytes")
        expect(original["dbn_length"], wire[0], "native DBN length encoding")
        expect(original["ts_out"], None if record.ts_out == UNDEF_TIMESTAMP else record.ts_out, "native outbound timestamp")
        for field in COMMON:
            expect(normalized[field], values[field], f"ROOT normalized {field}")
        for source, target in RENAMED.items():
            expect(normalized[target], values[source], f"ROOT normalized {target}")
        price = values["price"]
        expect(normalized["price"], None if price == UNDEF_PRICE else price / NS_PER_SECOND,
               "decimal price in USD per MMBtu")
        expect(normalized["is_last"], bool(record.flags & 128), "group close flag")
        expect(normalized["is_snapshot"], bool(record.flags & 32), "snapshot flag")


def activity_values(rows):
    counts, qty, side_qty = Counter(), Counter(), Counter()
    for action, side, size in rows:
        counts[action] += 1
        qty[action] += size
        side_qty[f"{action}_{side}"] += size
    buy, sell = side_qty["T_B"], side_qty["T_A"]
    adds, cancels = qty["A"], qty["C"]
    return dict(
        event_count=len(rows), action_count=dict(counts), action_qty=dict(qty),
        action_side_qty=dict(side_qty), trade_buy_aggressor_qty=buy,
        trade_sell_aggressor_qty=sell,
        trade_aggressor_imbalance=(buy - sell) / (buy + sell) if buy + sell else None,
        add_cancel_churn=cancels / (adds + cancels) if adds + cancels else None,
    )


def run():
    started = time.perf_counter()
    receipt = json.loads(git_blob(ROOT_PIN, (ROOT_PATH / "source-read-receipt.json").as_posix()))
    book = RestingBook()
    groups = tape_groups(book)
    checked = Counter()
    differences = Counter()
    first_difference = {}
    for ordinal, frame in enumerate(archived_frames(), receipt["first_group"]):
        group, pending, clocks, activity = next(groups)
        while group < ordinal:
            group, pending, clocks, activity = next(groups)
        expect(group, ordinal, "ROOT native group ordinal")
        check_raw(frame, pending)
        check_book(frame, book, checked)
        checked["groups"] += 1
        checked["messages"] += len(pending)
        for seconds in WINDOWS:
            cutoff = frame["ts_recv_ns"] - seconds * NS_PER_SECOND
            first = bisect_left(clocks, cutoff)
            values = activity_values(activity[first:])
            if values["action_side_qty"].get("T_N", 0):
                checked["windows_with_unspecified_trade_side"] += 1
            for key, calculated in values.items():
                observed = frame["activity"][str(seconds)][key]
                checked["activity_cells"] += 1
                if calculated != observed:
                    field = f"activity.{seconds}.{key}"
                    differences[field] += 1
                    first_difference.setdefault(field, dict(group=group, observed=observed, calculated=calculated))
    expect(checked["groups"], receipt["group_records"], "checked retained ROOT groups")
    return dict(
        session=DAY, tape_git_commit=TAPE_PIN, archive_git_commit=ROOT_PIN,
        group_first=receipt["first_group"], group_last=receipt["last_group"],
        checks=dict(checked), raw_message_mismatches=0, resting_state_mismatches=0, activity_mismatches=dict(differences),
        first_activity_difference=first_difference,
        activity_definition="Non-snapshot DBN messages in the inclusive receive window through this F_LAST cursor",
        exclusions=["Book-state-dependent activity", "Original extraction hash formula", "Full-session verification"],
        wall_seconds=round(time.perf_counter() - started, 2),
    )


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
