"""Rebuild and run the full-depth, order-linked fill-to-displayed-reduction ratio."""

import argparse
from collections import Counter, deque
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import time

from .verify_ng_book_replay import SESSION_PIN, TAPE_PIN, expect, git_blob, read_member, tape_blob
from .verify_retained_root_inputs import ROOT_PIN, RestingBook
from .verify_second_set_encoding import RECEIPT, verified_matrix


DAYS = ("20231002", "20231003", "20231017", "20231018")
NEXT = {"20231002": "20231003", "20231017": "20231018"}
HALT = 21 * 3600 * 10**9
OPEN = 22 * 3600 * 10**9
DAY_NS = 24 * 3600 * 10**9
WORST_CURSOR = 185120


def manifest(day):
    return json.loads(git_blob(SESSION_PIN, f"research/kalshi/frankie_boss/blocks/BLOCK_{day}_SOURCE_MANIFEST.json"))


def records(day):
    files = {r["file"].split("_")[-1][:8]: r for r in json.loads(tape_blob("MANIFEST.json"))["files"]}
    current = read_member(files[day])
    if day in NEXT:
        limit = manifest(NEXT[day])["tail_members"][0]["skip"]
        return enumerate(itertools.islice(current, limit))
    scope = manifest(day)
    tail, head = scope["tail_members"][0], scope["partial_members"][0]
    previous = read_member(files[tail["member_key"][10:18]])
    return enumerate(itertools.chain(
        itertools.islice(previous, tail["skip"] + tail["take"]),
        itertools.islice(current, head["take"]),
    ), start=-tail["skip"])


class Window:
    def __init__(self, length):
        self.length = length
        self.groups = deque()
        self.totals = Counter()

    def add(self, counts):
        if self.length is not None:
            if len(self.groups) == self.length:
                self.totals.subtract(self.groups.popleft())
            self.groups.append(counts)
        self.totals.update(counts)


def ratio(fills, removed):
    """Return a quantity ratio. Zero observed reduction has its own state."""
    return fills / removed if removed else None


def saved_short_ratios():
    pin = json.loads(git_blob(ROOT_PIN, RECEIPT))
    by_name = {Path(member["original_member"]).name: member for member in pin["source_members"]}
    raw = verified_matrix(by_name["raw-components-f64.bin"], pin["source_rows"])
    states = verified_matrix(by_name["states-u8.bin"], pin["source_rows"])
    clocks = verified_matrix(by_name["clocks-i64.bin"], pin["source_rows"])
    col = pin["original_number_names"].index("far_absorption_share_64")
    return {
        int(cursor): float(value) for cursor, value, state in zip(clocks[:, 0], raw[:, col], states[:, col], strict=True)
        if state == 0 and value > 1
    }


def apply_record(book, record, pending, counts):
    """Apply documented DBN transitions and retain each observed quantity separately."""
    action, side, oid = record.action.value, record.side.value, record.order_id
    before = book.orders.get(oid)
    book.apply(record)
    after = book.orders.get(oid)
    if action == "T":
        counts["trade", side] += record.size
    if action == "F":
        pending[oid] += record.size
        counts["wire_fill", side] += record.size
        if before is not None and before.price == record.price and side in {before.side, "N"}:
            pending[oid, before.side, before.price] += record.size
            counts["sided_fill", before.side] += record.size
            if side == "N":
                counts["fill_side_from_book", before.side] += record.size
        else:
            counts["unresolved_fill", side] += record.size
    if action in {"A", "C", "M"}:
        filled = pending.pop(oid, 0)
        if before is not None:
            remaining = after.size if after is not None and after.side == before.side else 0
            counts["reduction", before.side] += max(0, before.size - remaining)
            counts["legacy_linked_fill", before.side] += filled
            linked = pending.pop((oid, before.side, before.price), 0)
            counts["linked_fill", before.side] += linked
            if linked and after is not None and after.price == before.price and remaining == before.size:
                counts["linked_fill_unchanged_display", before.side] += linked
    return before, after


def evaluate(day, reference=None):
    started = time.perf_counter()
    book = RestingBook()
    windows = {label: Window(length) for label, length in (("64", 64), ("1024", 1024), ("span_to_date", None))}
    historical = Window(64)
    history_detail = deque(maxlen=64)
    checks = Counter()
    stats = {label: {side: Counter() for side in ("A", "B")} for label in windows}
    digests = {label: hashlib.sha256() for label in windows}
    pending, counts, detail = Counter(), Counter(), []
    group_snapshot = False
    traced = {}
    discrepancies = []
    revised_links = []
    unusual = []
    seam_before = None
    seam_cursor = None
    seam = None
    for cursor, record in records(day):
        if cursor < 0:
            book.apply(record)
            continue
        expect(record.instrument_id, 150611, "NGX3 instrument")
        if record.flags & 32 and day not in NEXT and seam_before is None and seam is None:
            seam_before = {oid: (order.side, order.price, order.size) for oid, order in book.orders.items()}
            seam_cursor = cursor
        before, after = apply_record(book, record, pending, counts)
        checks["source_records"] += 1
        group_snapshot |= bool(record.flags & 32)
        if reference is not None and WORST_CURSOR - 300 <= cursor <= WORST_CURSOR:
            detail.append({
                "cursor": cursor, "receive_ns": record.ts_recv, "event_ns": record.ts_event,
                "action": record.action.value, "side": record.side.value, "size": record.size,
                "price_raw": record.price, "order_id": record.order_id,
                "before_size": None if before is None else before.size,
                "after_size": None if after is None else after.size,
            })
        if not record.flags & 128:
            continue
        checks["completed_groups"] += 1
        if group_snapshot and seam_before is not None:
            seam_after = {oid: (order.side, order.price, order.size) for oid, order in book.orders.items()}
            expect(seam_after == seam_before, True, "midnight snapshot displayed-state continuity")
            seam = {"first_cursor": seam_cursor, "last_cursor": cursor, "identical_orders": len(seam_after)}
            seam_before = None
        if reference is not None:
            historical.add(counts)
            if WORST_CURSOR - 300 <= cursor <= WORST_CURSOR:
                history_detail.append((cursor, detail))
            if cursor in reference:
                buy, sell = historical.totals["trade", "B"], historical.totals["trade", "A"]
                far = "A" if buy > sell else "B"
                fills, removed = historical.totals["legacy_linked_fill", far], historical.totals["reduction", far]
                value = ratio(fills, removed) if abs(buy - sell) * 20 > buy + sell else None
                checks["flagged_archive_windows_compared"] += 1
                verified_fills = historical.totals["linked_fill", far]
                checks["flagged_windows_with_independently_verified_numerator"] += verified_fills == fills
                if value != reference[cursor]:
                    discrepancies.append(dict(cursor=cursor, archived=reference[cursor], calculated=value))
                if verified_fills != fills:
                    revised_links.append(dict(
                        cursor=cursor, receive_ns=record.ts_recv, side=far,
                        original_linked_fill_qty=fills, verified_linked_fill_qty=verified_fills,
                        displayed_reduction_qty=removed, original_ratio=value,
                        verified_ratio=ratio(verified_fills, removed),
                    ))
                if cursor == WORST_CURSOR:
                    traced = dict(cursor=cursor, side=far, fills=fills, reductions=removed,
                                  ratio=value, known_buy=buy, known_sell=sell,
                                  independently_linked_fill=verified_fills,
                                  same_price_unchanged_display_fill=historical.totals["linked_fill_unchanged_display", far],
                                  groups=list(history_detail))
        for side in ("A", "B", "N"):
            checks[f"wire_fill_qty_{side}"] += counts["wire_fill", side]
            checks[f"fill_qty_sided_by_resting_book_{side}"] += counts["fill_side_from_book", side]
            checks[f"unresolved_fill_qty_{side}"] += counts["unresolved_fill", side]
        phase = record.ts_recv % DAY_NS
        if not group_snapshot and (phase < HALT or phase >= OPEN):
            checks["active_groups"] += 1
            for label, window in windows.items():
                window.add(counts)
                if window.length is not None and len(window.groups) < window.length:
                    continue
                identity = [cursor, record.ts_recv]
                for side in ("A", "B"):
                    fills = window.totals["linked_fill", side]
                    removed = window.totals["reduction", side]
                    sided_fills = window.totals["sided_fill", side]
                    explicit_wire_fills = window.totals["wire_fill", side]
                    unchanged = window.totals["linked_fill_unchanged_display", side]
                    value = ratio(fills, removed)
                    summary = stats[label][side]
                    summary["windows"] += 1
                    summary["ratio_defined"] += value is not None
                    summary["above_one"] += removed > 0 and fills > removed
                    summary["fills_with_zero_reduction"] += removed == 0 and fills > 0
                    expect(fills <= sided_fills, True, "linked fills are a subset of independently sided fill quantity")
                    identity.extend((fills, removed, sided_fills, explicit_wire_fills, unchanged))
                    if fills > removed:
                        unusual.append({
                            "cursor": cursor, "receive_ns": record.ts_recv, "side": side, "horizon": label,
                            "linked_fill_qty": fills, "displayed_reduction_qty": removed,
                            "independently_sided_fill_qty": sided_fills, "explicit_wire_side_fill_qty": explicit_wire_fills,
                            "unchanged_display_fill_qty": unchanged,
                            "ratio": value,
                        })
                digests[label].update((json.dumps(identity, separators=(",", ":")) + "\n").encode())
        elif group_snapshot:
            checks["snapshot_groups"] += 1
        else:
            checks["halt_groups"] += 1
        pending, counts, detail = Counter(), Counter(), []
        group_snapshot = False
    if reference is not None:
        expect(checks["flagged_archive_windows_compared"], len(reference), "flagged archive windows")
    return {
        "trade_date": day,
        "midnight_snapshot": seam,
        "scope": "available partial trade date" if day in NEXT else "full trade date",
        "checks": dict(checks), "window_counts_by_side": stats,
        "window_row_sha256": {label: digest.hexdigest() for label, digest in digests.items()},
        "archive_discrepancies": discrepancies,
        **({"archive_windows_with_revised_fill_links": revised_links} if reference is not None else {}),
        "largest_archived_ratio_tape_trace": traced,
        "wall_seconds": round(time.perf_counter() - started, 2),
    }, unusual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", choices=DAYS)
    parser.add_argument("--unusual-out", type=Path, help="Write every ratio above 1 and every positive fill with zero reduction")
    args = parser.parse_args()
    reference = saved_short_ratios() if args.day == "20231018" else None
    result, unusual = evaluate(args.day, reference)
    result["unusual_window_count"] = len(unusual)
    if args.unusual_out is not None:
        with args.unusual_out.open("xb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as stream:
            for row in unusual:
                stream.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
        with args.unusual_out.open("rb") as stream:
            result["unusual_window_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    result["tape_git_commit"] = TAPE_PIN
    result["boundary_manifest_git_commit"] = SESSION_PIN
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
