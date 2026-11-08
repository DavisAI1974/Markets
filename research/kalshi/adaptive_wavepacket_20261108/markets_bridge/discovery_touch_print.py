"""Log candidate touch and print decisions from standalone NGX3 inputs."""

import argparse
from collections import Counter, deque
from datetime import date, datetime, time, timedelta, timezone
import gzip
import json
from pathlib import Path


DAYS = ("20231002", "20231003", "20231017", "20231018")
PARTIAL_DAYS = {"20231002", "20231017"}
SIDES = ("ask", "bid")
BOUNDARY_FLAGS = ("snapshot_member", "reset_member", "bad_receive_clock_member")


def active_span(day):
    session = date.fromisoformat(day)
    if day in PARTIAL_DAYS:
        opened = datetime.combine(session, time(0), timezone.utc)
    else:
        opened = datetime.combine(session - timedelta(days=1), time(22), timezone.utc)
    closed = datetime.combine(session, time(21), timezone.utc)
    return tuple(int(value.timestamp()) * 1_000_000_000 for value in (opened, closed))


def decision(row, rule, side, disposition, **details):
    return dict(group=row["group_ordinal"], cursor=row["close_cursor"],
                known_by_ns=row["receive_ns"], event_ns=row["event_ns"],
                rule=rule, side=side, disposition=disposition, **details)


def adjacent(prior, row):
    return (row["group_ordinal"] == prior["group_ordinal"] + 1
            and row["first_cursor"] == prior["close_cursor"] + 1
            and row["receive_ns"] >= prior["receive_ns"])


def falling_path(history, side):
    if len(history) != 3 or any(group[side] is None for group in history):
        return False
    first, middle, last = (group[side] for group in history)
    return (first[0] == middle[0] == last[0]
            and first[1] >= middle[1] >= last[1] > 1 and first[1] > last[1])


def print_decision(row, prior):
    prints = [{key: trade[key] for key in ("source_ordinal", "trade_input_cursor", "price_raw")}
              for trade in row["prints"]]
    rule = "prior-touch-print.v1"
    if prior is None or any(prior[side] is None for side in SIDES):
        return decision(row, rule, None, "PRIOR_TOUCH_UNAVAILABLE", prints=prints)
    ask, bid = (prior[side][0] for side in SIDES)
    prices = {trade["price_raw"] for trade in prints}
    side = None
    if bid < ask and prices == {ask}:
        side = "ask"
    elif bid < ask and prices == {bid}:
        side = "bid"
    return decision(row, rule, side, "CANDIDATE" if side else "AMBIGUOUS_VS_PRIOR_TOUCH",
                    prior_group=prior["group_ordinal"], prior_cursor=prior["close_cursor"],
                    prior_touch_raw={"ask": ask, "bid": bid}, prints=prints)


def decisions(groups, start_ns, stop_ns, counts):
    history = deque(maxlen=3)
    latched = dict.fromkeys(SIDES, False)
    for row in groups:
        counts["source_groups"] += 1
        counts["source_prints"] += len(row["prints"])
        eligible = start_ns <= row["receive_ns"] < stop_ns
        boundary = any(row[key] for key in BOUNDARY_FLAGS)
        if not eligible or boundary or (history and not adjacent(history[-1], row)):
            history.clear()
            latched = dict.fromkeys(SIDES, False)
        if not eligible or boundary:
            disposition = "OUTSIDE_ACTIVE_SPAN" if not eligible else "BOUNDARY_GROUP"
            counts[disposition] += 1
            if row["prints"]:
                yield decision(row, "prior-touch-print.v1", None, disposition,
                               print_ordinals=[trade["source_ordinal"] for trade in row["prints"]])
            continue

        counts["eligible_groups"] += 1
        prior = history[-1] if history else None
        history.append(row)
        for side in SIDES:
            qualifies = falling_path(history, side)
            if qualifies and not latched[side]:
                path = [{"group": group["group_ordinal"], "cursor": group["close_cursor"],
                         "size": group[side][1]} for group in history]
                details = dict(price_raw=row[side][0], path=path)
                yield decision(row, "falling-touch.v1", side, "CANDIDATE", **details)
                if row["prints"]:
                    yield decision(row, "falling-touch+print.v1", side, "CANDIDATE", **details,
                                   print_ordinals=[trade["source_ordinal"] for trade in row["prints"]])
            latched[side] = qualifies
        if row["prints"]:
            yield print_decision(row, prior)


def export(source, target, day):
    counts = Counter()
    dispositions = Counter()
    start_ns, stop_ns = active_span(day)
    with (gzip.open(source, "rt", encoding="utf-8") as stream, target.open("xb") as raw,
          gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=3) as output):
        for row in decisions(map(json.loads, stream), start_ns, stop_ns, counts):
            dispositions[row["rule"], row["side"] or "unassigned", row["disposition"]] += 1
            row.update(trade_date=day, instrument_id=150611)
            output.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
    return dict(trade_date=day, scope="partial" if day in PARTIAL_DAYS else "full",
                counts=dict(counts), dispositions=[[*key, count] for key, count in sorted(dispositions.items())])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", required=True, choices=DAYS)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.input, args.output, args.day), indent=2))


if __name__ == "__main__":
    main()
