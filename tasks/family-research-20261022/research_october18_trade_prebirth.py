"""Descriptive next-group and retained dipole timing checks on October 18."""

import argparse
from collections import Counter, defaultdict, deque
import csv
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import subprocess

REVISION = "c7740c6e9ce35bb4a3abeb30c7cdee2470fbd1af"
BASE = "tasks/family-research-20261022"
TOUCH = ("research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/"
         "root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz")
LIFECYCLE = "artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1"
NS = 1_000_000_000
OPEN = int(datetime(2023, 10, 17, 22, tzinfo=timezone.utc).timestamp()) * NS
CLOSE = int(datetime(2023, 10, 18, 21, tzinfo=timezone.utc).timestamp()) * NS
FLAGS = ("snapshot_member", "reset_member", "bad_receive_clock_member")


def git_rows(path, *, table=False):
    payload = subprocess.check_output(["git", "show", f"{REVISION}:{path}"])
    with gzip.open(io.BytesIO(payload), "rt", encoding="utf-8") as source:
        yield from csv.DictReader(source) if table else map(json.loads, source)


def sign(value):
    return (value > 0) - (value < 0)


def usable(row):
    return (OPEN <= row["receive_ns"] < CLOSE and not any(row[key] for key in FLAGS)
            and row["bid"] and row["ask"] and row["bid"][0] < row["ask"][0])


def adjacent(previous, row):
    return (row["group_ordinal"] == previous["group_ordinal"] + 1
            and row["first_cursor"] == previous["close_cursor"] + 1
            and row["receive_ns"] >= previous["receive_ns"])


def measure_close_pairs():
    falling = defaultdict(set)
    for row in git_rows(f"{BASE}/october18-touch-print-decisions.jsonl.gz"):
        if row["rule"] == "falling-touch.v1" and row["disposition"] == "CANDIDATE":
            falling[(row["group"], row["cursor"], row["known_by_ns"])].add(row["side"])

    prints = {}
    opportunities = defaultdict(Counter)
    midpoint = defaultdict(Counter)
    skips = Counter()
    lead_ns = []
    previous = None
    for row in git_rows(TOUCH):
        prior = previous if previous and usable(previous) and usable(row) and adjacent(previous, row) else None
        for trade in row["prints"]:
            ordinal = trade["source_ordinal"]
            if ordinal in prints:
                raise ValueError(f"duplicate print {ordinal}")
            prints[ordinal] = dict(
                receive=trade["receive_ns"], cursor=trade["trade_input_cursor"],
                prior_receive=prior["receive_ns"] if prior else None,
                prior_cursor=prior["close_cursor"] if prior else None,
            )
        if prior is not None:
            coordinate = (prior["group_ordinal"], prior["close_cursor"], prior["receive_ns"])
            sides = falling.get(coordinate, set())
            candidate = bool(sides)
            hour = prior["receive_ns"] // (3600 * NS)
            previous_print = bool(prior["prints"])
            spread = prior["ask"][0] - prior["bid"][0]
            has_print = bool(row["prints"])
            counts = opportunities[hour, previous_print, spread, candidate]
            counts["opportunities"] += 1
            counts["next_print_group"] += has_print
            if has_print:
                lead_ns.append(row["prints"][0]["receive_ns"] - prior["receive_ns"])

            change = sign(sum(row[side][0] - prior[side][0] for side in ("ask", "bid")))
            queue = sign(prior["bid"][1] - prior["ask"][1])
            falling_call = (1 if "ask" in sides else -1) if len(sides) == 1 else 0
            for rule, direction in (("falling_touch", falling_call), ("queue_imbalance_sign", queue)):
                if direction:
                    midpoint[rule]["agree" if change == direction else "flat" if not change else "oppose"] += 1
                else:
                    midpoint[rule]["no_unique_call"] += 1
        elif previous is not None:
            skips["pair_outside_scope_or_boundary"] += 1
        previous = row

    totals = defaultdict(Counter)
    for (_, previous_print, _, candidate), counts in opportunities.items():
        totals[previous_print, candidate].update(counts)
    matched = Counter()
    weighted_reference = 0.0
    for (hour, previous_print, spread, candidate), counts in opportunities.items():
        if not candidate:
            continue
        control = opportunities.get((hour, previous_print, spread, False))
        if control:
            n = counts["opportunities"]
            matched.update(counts)
            weighted_reference += n * control["next_print_group"] / control["opportunities"]
    lead_ns.sort()
    result = dict(
        unconditional=[dict(current_group_has_print=previous_print, falling_touch=candidate, **counts)
                       for (previous_print, candidate), counts in sorted(totals.items())],
        matching=dict(candidate_opportunities=matched["opportunities"],
                      candidate_next_print_group=matched["next_print_group"],
                      expected_using_matched_reference=weighted_reference,
                      strata=["UTC hour", "current group has a print", "quoted spread raw"]),
        midpoint=dict(midpoint),
        next_print_lead_ns=dict(minimum=lead_ns[0], median=lead_ns[len(lead_ns)//2],
                                zero_lead=lead_ns.count(0), target_groups=len(lead_ns)),
        skips=dict(skips),
    )
    return result, prints


def gap_state(times, decision_ns):
    if len(times) < 3:
        return "insufficient_history", "insufficient_history"
    first, middle, last = times
    earlier_gap = middle - first
    last_gap = last - middle
    trend = "widening" if last_gap > earlier_gap else "narrowing" if last_gap < earlier_gap else "equal"
    age = "beyond_last_gap" if decision_ns - last > last_gap else "within_last_gap"
    return trend, age


def measure_exhaustion():
    episodes = {row["onset_group"]: row
                for row in git_rows(f"{BASE}/october18-size-one-mechanisms.jsonl.gz")}
    all_tape = deque(maxlen=3)
    directed = defaultdict(lambda: deque(maxlen=3))
    counts = defaultdict(Counter)
    previous = None
    seen = set()
    for row in git_rows(TOUCH):
        if not usable(row) or (previous and not adjacent(previous, row)):
            all_tape.clear()
            directed.clear()
        previous = row
        if not usable(row):
            continue
        group = row["group_ordinal"]
        clock = row["receive_ns"]
        if group in episodes:
            case = episodes[group]
            if (case["onset_cursor"], case["onset_ns"]) != (row["close_cursor"], clock):
                raise ValueError(f"exhaustion onset differs at group {group}")
            seen.add(group)
            attacking_side = "A" if case["side"] == "B" else "B"
            key = attacking_side, case["original_price_raw"]
            prior_tape = (("all_print_groups", all_tape),
                          ("known_attacking_side_at_touch_price", directed.get(key, ())))
            for source, times in prior_tape:
                trend, age = gap_state(times, clock)
                counts[source, case["side"], trend, age][case["outcome"]] += 1
        if row["prints"]:
            all_tape.append(clock)
            for key in {(trade["aggressor_side"], trade["price_raw"]) for trade in row["prints"]
                        if trade["aggressor_side"] in ("A", "B")}:
                directed[key].append(clock)
        if len(seen) == len(episodes):
            break
    if set(episodes) != seen:
        raise ValueError("exhaustion onset scope is incomplete")
    return [dict(source=source, side=side, gap_trend=trend, age=age, outcomes=dict(outcomes))
            for (source, side, trend, age), outcomes in sorted(counts.items())]


def measure_dipole_timing(prints):
    paths = {row["candidate_id"]: row
             for row in git_rows(f"{LIFECYCLE}/supporting-dipole-paths.csv.gz", table=True)}
    linked_prints = set()
    candidates_before = set()
    full_before = set()
    counts = Counter()
    for link in git_rows(f"{LIFECYCLE}/trade-to-supporting-path-links.csv.gz", table=True):
        ordinal = int(link["trade_ordinal"])
        trade = prints[ordinal]
        path = paths[link["candidate_id"]]
        receive = trade["receive"]
        known_by = int(path["known_by_ns"])
        if receive != int(link["trade_receive_ns"]) or known_by != int(link["path_complete_known_by_ns"]):
            raise ValueError(f"source coordinate mismatch for {ordinal}")
        linked_prints.add(ordinal)
        counts["links"] += 1
        counts["birth_label_before_print"] += int(path["birth_recv_ns"]) < receive
        if int(path["candidate_available_ns"]) < receive:
            counts["candidate_clock_before_print"] += 1
            candidates_before.add(ordinal)
        if known_by < receive:
            counts["completed_path_clock_before_print"] += 1
            if int(path["input_cursor"]) < trade["cursor"]:
                counts["completed_path_clock_and_cursor_before_print"] += 1
                full_before.add(ordinal)
        if (trade["prior_receive"] is not None and known_by <= trade["prior_receive"]
                and int(path["input_cursor"]) <= trade["prior_cursor"]):
            counts["completed_path_available_by_prior_eligible_close"] += 1
    keys = ("links", "birth_label_before_print", "candidate_clock_before_print",
            "completed_path_clock_before_print", "completed_path_clock_and_cursor_before_print",
            "completed_path_available_by_prior_eligible_close")
    return dict(paths=len(paths), all_prints=len(prints), linked_prints=len(linked_prints),
                prints_with_candidate_clock_before=len(candidates_before), prints_with_full_path_before=len(full_before),
                **{key: counts[key] for key in keys})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    close_pairs, prints = measure_close_pairs()
    if len(prints) != 30739:
        raise ValueError("October 18 input print inventory differs")
    result = dict(trade_date="20231018", instrument_id=150611, pinned_inputs=REVISION,
                  scope="October 18 discovery diagnostics with completed touch and print inputs",
                  close_pairs=close_pairs, retained_dipole_overlap=measure_dipole_timing(prints),
                  exhaustion_at_strict_prior_close=measure_exhaustion())
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
