"""Trace the observed onset and first end of each archived size-one episode."""

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import gzip
import io
import json
from pathlib import Path
import subprocess

import databento as db

DISCOVERY = "b81b15b972ec39df69333bb6999d01d2495629cd"
TAPE = "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202"
TAPE_FILE = "data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_20231018.dbn.zst"
EPISODES = ("artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/"
            "historical-paper-replay-v1/every-size-one-onset-comparison.jsonl.gz")
TOUCH = ("research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/"
         "root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz")
PUBLICATIONS = ("artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/"
                "day-wide-mechanisms-v1/all-declared-external-publications-during-tape.jsonl.gz")
OCTOBER18_UTC_OFFSET = 17375
F_LAST = 128
INSTRUMENT = 150611


def git_blob(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"])


def git_rows(path):
    with gzip.open(io.BytesIO(git_blob(DISCOVERY, path)), "rt", encoding="utf-8") as stream:
        yield from map(json.loads, stream)


def book_evidence(episodes):
    wanted = {quote["cursor"] for episode in episodes
              for quote in (episode["signal"], episode["first_paper_entry"], episode["first_end"]["quote"])
              if quote is not None}
    spans = sorted((episode["signal"]["cursor"], episode["first_end"]["quote"]["cursor"])
                   for episode in episodes)
    stop = max(wanted)
    snapshots = {}
    previous = None
    span_index = 0
    covered_to = -1
    for row in git_rows(TOUCH):
        cursor = row["close_cursor"]
        while span_index < len(spans) and spans[span_index][0] <= cursor:
            covered_to = max(covered_to, spans[span_index][1])
            span_index += 1
        if cursor <= covered_to or cursor in wanted:
            snapshots[cursor] = (previous, row)
        if cursor >= stop:
            break
        previous = row
    if not wanted.issubset(snapshots):
        raise ValueError("one or more target closes are absent")
    return snapshots


class Book:
    def __init__(self):
        self.orders = {}
        self.levels = defaultdict(dict)
        self.refreshes = {}

    def set_order(self, order_id, before, after):
        if before:
            del self.levels[before[:2]][order_id]
        if after:
            self.orders[order_id] = after
            self.levels[after[:2]][order_id] = after[2]
        else:
            self.orders.pop(order_id, None)
        if not before or not after or before[:2] != after[:2]:
            self.refreshes.pop(order_id, None)

    def apply(self, record, cursor, pending, capture):
        action, order_id = str(record.action), record.order_id
        price, size, side = record.price, record.size, str(record.side)
        before = self.orders.get(order_id)
        if action == "R":
            self.orders.clear()
            self.levels.clear()
            self.refreshes.clear()
            return
        if action == "F":
            if before and before[1] == price:
                pending[order_id, *before[:2]] += size
            return
        if action not in ("A", "C", "M"):
            return
        if action == "C":
            if before is None:
                raise ValueError(f"cancel without an observed order at {cursor}")
            after = (*before[:2], before[2] - size) if before[2] > size else None
        else:
            after = (side, price, size) if size else None
        matched = unchanged = 0
        if before:
            key = (order_id, *before[:2])
            old_price_size = after[2] if after and after[:2] == before[:2] else 0
            reduction = max(0, before[2] - old_price_size)
            if action in ("C", "M") and (not after or after[:2] == before[:2]):
                matched = min(reduction, pending[key])
                pending[key] -= matched
            if action == "M" and after == before and pending[key]:
                unchanged = pending.pop(key)
                self.refreshes[order_id] = (cursor, record.ts_recv)
        self.set_order(order_id, before, after)
        if capture is not None:
            capture.append(dict(cursor=cursor, action=action, order_id=order_id, before=before,
                                after=after, linked_display_reduction=matched,
                                linked_fill_unchanged_display=unchanged))

    def level(self, side, price):
        return self.levels.get((side, price), {})

    def check_touch(self, snapshot):
        next_levels = {}
        for side, field in (("B", "bid"), ("A", "ask")):
            quote = snapshot[field]
            prices = sorted((price for (book_side, price), orders in self.levels.items()
                             if book_side == side and orders), reverse=side == "B")
            best = prices[0] if prices else None
            level = self.level(side, best)
            actual = [best, sum(level.values()), len(level)] if best is not None else None
            if actual != quote:
                raise ValueError(f"touch quantity or order count differs at {snapshot['close_cursor']}")
            if len(prices) > 1:
                next_price = prices[1]
                next_levels[side] = [next_price, sum(self.level(side, next_price).values())]
        return next_levels


def level_effect(mutations, side, price):
    additions = Counter()
    reductions = Counter()
    support = []
    for change in mutations:
        before, after = change["before"], change["after"]
        old = before[2] if before and before[:2] == (side, price) else 0
        new = after[2] if after and after[:2] == (side, price) else 0
        if old or new:
            support.append(change)
        if new > old:
            label = "ADD" if change["action"] == "A" else "REPRICE_IN" if not old and before else "MODIFY"
            additions[label] += new - old
        elif old > new:
            linked = min(old - new, change["linked_display_reduction"])
            if linked:
                reductions["FILL_LINKED"] += linked
            if old - new > linked:
                label = "REPRICE_OUT" if after and after[:2] != before[:2] else f"UNLINKED_{change['action']}"
                reductions[label] += old - new - linked
    return dict(additions=dict(additions), reductions=dict(reductions), mutations=support)


def capture_groups(snapshots):
    starts = {after["first_cursor"]: before for before, after in snapshots.values()}
    stop = max(snapshots)
    book = Book()
    pending = Counter()
    targets = {}
    capture = None
    for index, record in enumerate(db.DBNStore.from_bytes(git_blob(TAPE, TAPE_FILE))):
        cursor = index + OCTOBER18_UTC_OFFSET
        if record.instrument_id != INSTRUMENT:
            raise ValueError(f"unexpected instrument at {cursor}")
        if cursor in starts:
            before_next_levels = book.check_touch(starts[cursor])
            capture = []
            messages = []
        if capture is not None:
            messages.append([cursor, str(record.action), str(record.side), record.price, record.size, record.order_id])
        book.apply(record, cursor, pending, capture)
        if int(record.flags) & F_LAST:
            pending.clear()
            if capture is not None:
                _, after = snapshots[cursor]
                next_levels = book.check_touch(after)
                survivors = {}
                for side, field in (("B", "bid"), ("A", "ask")):
                    if after[field]:
                        price = after[field][0]
                        orders = book.level(side, price)
                        survivors[side] = [
                            dict(order_id=order_id, displayed=size,
                                 last_unchanged_display_fill=book.refreshes.get(order_id))
                            for order_id, size in sorted(orders.items())
                        ]
                targets[cursor] = dict(mutations=capture, messages=messages, survivors=survivors,
                                       before_next_levels=before_next_levels, next_levels=next_levels)
                capture = None
        if cursor == stop:
            break
    if set(targets) != set(snapshots):
        raise ValueError("not all target closes were reconstructed")
    return targets


def explain_episode(episode, snapshots, groups, ordered_cursors):
    signal = episode["signal"]
    ending = episode["first_end"]
    onset_cursor = signal["cursor"]
    end_cursor = ending["quote"]["cursor"]
    side = episode["side"]
    field = "bid" if side == "B" else "ask"
    old_price = signal[f"{field}_raw"]
    new_price = ending["quote"][f"{field}_raw"]
    onset_group = groups[onset_cursor]
    end_group = groups[end_cursor]
    entry = episode["first_paper_entry"]
    between = []
    for cursor in ordered_cursors[bisect_right(ordered_cursors, onset_cursor):
                                  bisect_left(ordered_cursors, end_cursor)]:
        group = groups[cursor]
        effect = level_effect(group["mutations"], side, old_price)
        prints = [message for message in group["messages"]
                  if message[1] == "T" and message[3] == old_price]
        if effect["mutations"] or prints:
            between.append(dict(close_cursor=cursor, touch=effect, prints=prints))
    return dict(
        side=side, onset=episode["onset"], recorded_t=episode["recorded_t"],
        onset_group=signal["group"], onset_cursor=onset_cursor,
        onset_ns=signal["known_by_ns"], end_group=ending["quote"]["group"],
        end_cursor=end_cursor, end_ns=ending["quote"]["known_by_ns"],
        entry_cursor=entry["cursor"] if entry else None,
        end_vs_entry=episode["end_vs_entry"], outcome=ending["status"],
        original_price_raw=old_price, ending_price_raw=new_price,
        onset_touch=level_effect(onset_group["mutations"], side, old_price),
        onset_orders=onset_group["survivors"][side],
        onset_messages=onset_group["messages"],
        onset_next_level=onset_group["next_levels"].get(side),
        between_at_original_price=between,
        before_end_next_level=end_group["before_next_levels"].get(side),
        end_original_touch=level_effect(end_group["mutations"], side, old_price),
        end_new_touch=(level_effect(end_group["mutations"], side, new_price)
                       if new_price != old_price else None),
        end_messages=end_group["messages"],
        prior_touch=snapshots[onset_cursor][0][field],
        before_end_touch=snapshots[end_cursor][0][field],
        ending_touch=snapshots[end_cursor][1][field],
    )


def export(output):
    episodes = list(git_rows(EPISODES))
    snapshots = book_evidence(episodes)
    groups = capture_groups(snapshots)
    ordered_cursors = sorted(groups)
    publications = sorted(git_rows(PUBLICATIONS), key=lambda row: row["original_declared_publication_ns"])
    clocks = [row["original_declared_publication_ns"] for row in publications]
    with (output.open("xb") as raw,
          gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out):
        for episode in episodes:
            evidence = explain_episode(episode, snapshots, groups, ordered_cursors)
            first = bisect_right(clocks, evidence["onset_ns"])
            last = bisect_right(clocks, evidence["end_ns"])
            evidence["declared_publications_after_onset"] = [
                dict(source_line=row["publication_line"], declared_ns=row["original_declared_publication_ns"],
                     tables=sorted({entry["original_table"] for entry in row["all_original_observation_refs"]}))
                for row in publications[first:last]
            ]
            out.write((json.dumps(evidence, separators=(",", ":")) + "\n").encode())
    print(f"Traced {len(episodes)} episodes and checked {len(groups)} distinct targeted group closes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output)
