"""Trace large one-group NG midpoint moves to orders and measure their aftermath."""

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
import gzip
import json
from pathlib import Path

from audit_october18_touch_mechanisms import Book, F_LAST, PUBLICATIONS
from reconstruct_october18_candidate_inputs import rows, raw_records
from research_october18_trade_prebirth import NS, TOUCH, adjacent, sign, usable

TICK_RAW = 1_000_000
HORIZONS = (1, 5, 20)
MAX_ENDPOINT_AGE_NS = NS


def mid2(row):
    return row["bid"][0] + row["ask"][0]


def close_segment(clocks, mids, events):
    for row in events:
        current = row["group"]
        for seconds in HORIZONS:
            target = current["receive_ns"] + seconds * NS
            index = bisect_right(clocks, target) - 1
            age = target - clocks[index]
            valid = target <= clocks[-1] and age <= MAX_ENDPOINT_AGE_NS
            displacement = (mids[index] - mid2(current)) * row["direction"]
            row["after"][str(seconds)] = dict(
                state={-1: "against", 0: "flat", 1: "with"}[sign(displacement)] if valid else "unavailable",
                signed_half_ticks=displacement // TICK_RAW if valid else None,
                full_retrace=displacement <= -abs(row["move_half_ticks"]) * TICK_RAW if valid else None,
                endpoint_receive_ns=clocks[index] if valid else None,
                endpoint_age_ns=age if valid else None,
            )


def find_moves():
    previous = None
    clocks, mids, segment_events = [], [], []
    recent_print_groups = deque()
    events = []
    comparable = Counter()
    move_sizes = defaultdict(Counter)
    last_disjoint = -20 * NS
    for row in rows(TOUCH):
        lawful = usable(row)
        continuous = lawful and previous is not None and adjacent(previous, row)
        if not continuous:
            close_segment(clocks, mids, segment_events)
            clocks, mids, segment_events = [], [], []
            recent_print_groups.clear()
        if not lawful:
            previous = None
            continue
        now = row["receive_ns"]
        clocks.append(now)
        mids.append(mid2(row))
        while recent_print_groups and recent_print_groups[0][0] < now - 20 * NS:
            recent_print_groups.popleft()
        if continuous:
            move = mid2(row) - mid2(previous)
            if move % TICK_RAW:
                raise ValueError(f"non-tick quote at group {row['group_ordinal']}")
            size = abs(move) // TICK_RAW
            comparable["all"] += 1
            comparable["nonzero"] += size > 0
            if size:
                key = "4_or_more" if size >= 4 else str(size)
                move_sizes[key]["with_print" if row["prints"] else "without_print"] += 1
            comparable["two_ticks_or_more"] += size >= 4
            comparable["three_ticks_or_more"] += size >= 6
            if size >= 4:
                disjoint = now >= last_disjoint + 20 * NS
                if disjoint:
                    last_disjoint = now
                event = dict(
                    group=row, prior=previous, move_half_ticks=move // TICK_RAW, direction=sign(move),
                    prior_spread_ticks=(previous["ask"][0] - previous["bid"][0]) // TICK_RAW,
                    prior_20s_print_count=sum(n for _, n in recent_print_groups),
                    first_of_disjoint_20s=disjoint, after={},
                )
                events.append(event)
                segment_events.append(event)
        if row["prints"]:
            recent_print_groups.append((now, len(row["prints"])))
        previous = row
    close_segment(clocks, mids, segment_events)
    return events, comparable, move_sizes


def classify(side, prior, final, mutations):
    old_price, new_price = prior[0], final[0]
    if old_price == new_price:
        return {}, set()
    counts = Counter()
    entrants = set()
    toward = new_price > old_price if side == "B" else new_price < old_price
    for change in mutations:
        before, after = change["before"], change["after"]
        action = change["action"]
        if toward and after and after[:2] == (side, new_price) and (not before or before[:2] != after[:2]):
            counts["entered_at_new_best_by_" + action] += after[2]
            entrants.add(change["order_id"])
        elif not toward and before and before[:2] == (side, old_price):
            retained = after[2] if after and before[:2] == after[:2] else 0
            reduced = max(0, before[2] - retained)
            linked = change["linked_display_reduction"]
            if linked:
                counts["fill_linked_lots_at_old_best"] += linked
            if reduced > linked:
                counts["other_reduction_at_old_best_by_" + action] += reduced - linked
    return dict(counts), entrants


def trace(events):
    starts = {event["group"]["first_cursor"]: event for event in events}
    book, pending = Book(), Counter()
    current = None
    changes, messages = [], []
    for cursor, record in raw_records():
        if cursor in starts:
            current = starts[cursor]
            changes, messages = [], []
            current["prior_next_levels"] = book.check_touch(current["prior"])
        if current is not None:
            messages.append([cursor, str(record.action), str(record.side), record.price, record.size, record.order_id])
        book.apply(record, cursor, pending, changes if current is not None else None)
        if not record.flags & F_LAST:
            continue
        pending.clear()
        if current is None:
            continue
        row = current["group"]
        if cursor != row["close_cursor"] or record.ts_recv != row["receive_ns"]:
            raise ValueError(f"source coordinate differs at {cursor}")
        book.check_touch(row)
        current["actions"] = messages
        mechanisms, linked_entrants = {}, {}
        print_ids = {order_id for _, action, _, _, _, order_id in messages if action == "T" and order_id}
        for side, field in (("B", "bid"), ("A", "ask")):
            evidence, entrants = classify(side, current["prior"][field], row[field], changes)
            mechanisms[field] = evidence
            linked_entrants[field] = sorted(entrants & print_ids)
            if row[field][0] != current["prior"][field][0] and not evidence:
                raise ValueError(f"unexplained {field} price change at {cursor}")
        current["quote_mechanisms"] = mechanisms
        current["new_best_order_ids_shared_with_print"] = linked_entrants
        current["print_lots"] = sum(size for _, action, _, _, size, _ in messages if action == "T")
        if current is events[-1]:
            return
        current = None
    raise ValueError("raw tape ended before the final large move")


def publication_context(events):
    clocks = defaultdict(list)
    for row in rows(PUBLICATIONS):
        clock = row["original_declared_publication_ns"]
        tables = {item["original_table"] for item in row["all_original_observation_refs"]}
        for table in tables:
            clocks[table].append(clock)
    for values in clocks.values():
        values.sort()
    for row in events:
        now = row["group"]["receive_ns"]
        row["retained_publications_in_prior_second"] = {
            table: bisect_right(values, now) - bisect_left(values, now - NS)
            for table, values in clocks.items()
        }
    return {table: len(values) for table, values in sorted(clocks.items())}


def summarize(events, comparable, move_sizes, publications):
    states = defaultdict(Counter)
    for row in events:
        size = abs(row["move_half_ticks"])
        clock = row["retained_publications_in_prior_second"]
        changed = [name for data in row["quote_mechanisms"].values() for name in data]
        mechanisms = []
        if any(name.startswith("entered_") for name in changed):
            mechanisms.append("new_best")
        if any(name.startswith("other_reduction") for name in changed):
            mechanisms.append("other_old_best_reduction")
        if "fill_linked_lots_at_old_best" in changed:
            mechanisms.append("fill_linked")
        row["mechanisms"] = mechanisms
        print_state = "print" if row["print_lots"] else "no_print"
        totals = states["cohort"]
        totals[f"size_half_ticks/{size}"] += 1
        totals[f"direction/{row['direction']}"] += 1
        mechanism = "+".join(mechanisms)
        totals[f"mechanism/{mechanism}"] += 1
        totals[f"print/{print_state}"] += 1
        totals["new_best_shares_print_order_id"] += any(row["new_best_order_ids_shared_with_print"].values())
        totals[f"prior_spread_ticks/{row['prior_spread_ticks']}"] += 1
        totals["near_retained_traded_curve"] += bool(clock.get("curve.traded_shape"))
        totals["near_retained_other_publication"] += any(value for key, value in clock.items()
                                                       if key != "curve.traded_shape")
        for population in ("all_moves", f"size_{size}_half_ticks", mechanism):
            for horizon, outcome in row["after"].items():
                key = f"{population}/{print_state}/{horizon}s"
                states[key][outcome["state"]] += 1
                if outcome["full_retrace"]:
                    states[key]["full_retrace"] += 1
                if row["first_of_disjoint_20s"]:
                    states[f"disjoint/{key}"][outcome["state"]] += 1
    return dict(comparable_group_pairs=comparable, nonzero_midpoint_moves_by_absolute_half_ticks=move_sizes,
                retained_publications_by_table=publications,
                counts={name: dict(counts) for name, counts in states.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    directory = parser.parse_args().output_directory
    events, comparable, move_sizes = find_moves()
    trace(events)
    summary = summarize(events, comparable, move_sizes, publication_context(events))
    data = "".join(json.dumps(row, sort_keys=True) + "\n" for row in events)
    (directory / "october18-large-quote-moves.jsonl.gz").write_bytes(gzip.compress(data.encode(), mtime=0))
    (directory / "october18-large-quote-moves-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary["comparable_group_pairs"], indent=2))
    print(json.dumps(summary["counts"]["cohort"], indent=2))


if __name__ == "__main__":
    main()
