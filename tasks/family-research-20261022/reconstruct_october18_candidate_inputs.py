"""Reconstruct October 18 dipole input states and exact recognition availability."""

import argparse
from bisect import insort
from collections import Counter, defaultdict
import csv
import gzip
import io
import json
from math import ceil, floor
from pathlib import Path
from statistics import median

from audit_october18_touch_mechanisms import (
    Book, F_LAST, INSTRUMENT, OCTOBER18_UTC_OFFSET, TAPE, TAPE_FILE, db, git_blob,
)
from research_october18_trade_prebirth import CLOSE, LIFECYCLE, NS, OPEN, TOUCH, adjacent, sign, usable

REVISION = "d25fc3f7e59c2a1cb51ec943cd91ff34e176a72a"
PRODUCER = "2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134"
OCTOBER17_CURSOR_OFFSET = 841601


def rows(path, *, table=False):
    with gzip.open(io.BytesIO(git_blob(REVISION, path)), "rt", encoding="utf-8") as stream:
        yield from csv.DictReader(stream) if table else map(json.loads, stream)


def historical_records():
    return {
        name: [row["original_record"] for row in rows(f"{LIFECYCLE}/source-{name}.jsonl.gz")]
        for name in ("episode", "candidate", "flow_substrate")
    }


def raw_records():
    for path, offset in (
        (TAPE_FILE.replace("20231018", "20231017"), -OCTOBER17_CURSOR_OFFSET),
        (TAPE_FILE, OCTOBER18_UTC_OFFSET),
    ):
        for index, record in enumerate(db.DBNStore.from_bytes(git_blob(TAPE, path))):
            yield index + offset, record


def action_quote(book):
    bid, ask = 0, None
    for (side, price), orders in book.levels.items():
        if not orders:
            continue
        if side == "B":
            bid = max(bid, price)
        elif side == "A":
            ask = price if ask is None else min(ask, price)
    return bid, ask


def midpoint_side(price, size, bid, ask):
    if price <= 0 or size <= 0 or not bid or ask is None or ask < bid:
        return "no_quote_or_unusable"
    price, bid, ask = price / NS, bid / NS, ask / NS
    mid = 0.5 * (bid + ask)
    return "buy" if price > mid else "sell" if price < mid else "at_mid"


def observe_tape(recognition, birth_seconds):
    source = iter(rows(TOUCH))
    group = next(source)
    previous = None
    book = Book()
    pending = Counter()
    pending_trades = []
    seconds = defaultdict(Counter)
    trades = {}
    closes = {}
    comparisons = Counter()
    births = {}
    pending_births = iter(sorted(birth_seconds))
    next_birth = next(pending_births, None)

    for cursor, record in raw_records():
        if record.instrument_id != INSTRUMENT:
            raise ValueError(f"unexpected instrument at {cursor}")
        if cursor >= 0 and group["first_cursor"] <= cursor <= group["close_cursor"]:
            if str(record.action) == "T":
                pending_trades.append((cursor, record, action_quote(book)))
        book.apply(record, cursor, pending, None)
        if not record.flags & F_LAST:
            continue
        pending.clear()
        if cursor < 0:
            continue
        if cursor != group["close_cursor"] or record.ts_recv != group["receive_ns"]:
            raise ValueError(f"group close does not align at {cursor}")
        while next_birth is not None and next_birth <= record.ts_recv // NS:
            births[next_birth] = previous
            next_birth = next(pending_births, None)
        if cursor in recognition:
            book.check_touch(group)
            closes[cursor] = group
        if len(pending_trades) != len(group["prints"]):
            raise ValueError(f"trade count does not align at {cursor}")
        prior = previous if previous and usable(previous) and usable(group) and adjacent(previous, group) else None
        for (raw_cursor, trade, quote), saved in zip(pending_trades, group["prints"], strict=True):
            if (raw_cursor, trade.ts_recv, trade.price) != (
                saved["trade_input_cursor"], saved["receive_ns"], saved["price_raw"],
            ):
                raise ValueError(f"trade does not align at {raw_cursor}")
            ordinal = saved["source_ordinal"]
            if ordinal in trades:
                raise ValueError(f"duplicate tape ordinal {ordinal}")
            trades[ordinal] = (trade.ts_recv, raw_cursor, cursor, prior)
            if not OPEN <= record.ts_recv < CLOSE:
                continue
            counts = seconds[record.ts_recv // NS]
            action_side = midpoint_side(trade.price, trade.size, *quote)
            wire_side = {"B": "buy", "A": "sell"}.get(str(trade.side), "unspecified")
            counts["prints"] += 1
            counts[action_side + "_prints"] += 1
            counts[action_side + "_lots"] += trade.size
            counts["wire_" + wire_side + "_lots"] += trade.size
            comparisons[f"action_{action_side}/wire_{wire_side}"] += 1
            if prior:
                prior_side = midpoint_side(trade.price, trade.size, prior["bid"][0], prior["ask"][0])
                comparisons[f"action_{action_side}/prior_{prior_side}"] += 1
        pending_trades.clear()
        previous = group
        group = next(source, None)
        if group is None:
            return seconds, trades, closes, births, comparisons
    raise ValueError("raw tape ended before the last saved group")


def window(seconds, second, width=20):
    counts = Counter()
    for slot in range(second - width + 1, second + 1):
        counts.update(seconds.get(slot, {}))
    buys, sells = counts["buy_lots"], counts["sell_lots"]
    counts["classified_lots"] = buys + sells
    return dict(counts, roll20=(buys - sells) / (buys + sells) if buys + sells else None)


def pct(values):
    return dict(minimum=min(values), median=median(values), maximum=max(values))


def overlap(episodes, trades):
    counts, prints = Counter(), defaultdict(set)
    by_candidate = defaultdict(Counter)
    for row in rows(f"{LIFECYCLE}/trade-to-supporting-path-links.csv.gz", table=True):
        candidate = row["candidate_id"]
        event = episodes[candidate]
        emission = event["frankie_emission"]
        ordinal = int(row["trade_ordinal"])
        ns, cursor, close_cursor, prior = trades[ordinal]
        if ns != int(row["trade_receive_ns"]):
            raise ValueError(f"overlap clock does not align for {ordinal}")
        flags = {
            "all": True,
            "nominal_bin_before_print": event["recognized_recv_ns"] < ns,
            "record_emission_before_print": emission["ts_recv_ns"] < ns and emission["input_cursor"] < cursor,
            "record_emission_by_prior_group": bool(prior and emission["ts_recv_ns"] <= prior["receive_ns"]
                                                  and emission["input_cursor"] <= prior["close_cursor"]),
            "record_emission_in_trade_group": emission["input_cursor"] == close_cursor,
        }
        for name, value in flags.items():
            if value:
                counts[name] += 1
                prints[name].add(ordinal)
                by_candidate[candidate][name] += 1
    return dict(links=dict(counts), distinct_prints={name: len(values) for name, values in prints.items()}), by_candidate


def substrate_comparison(retained, seconds, roll):
    counts = Counter()
    for row in retained:
        second = row["second"]
        if not OPEN // NS <= second < CLOSE // NS:
            continue
        counts["retained_active"] += 1
        fresh = seconds.get(second, Counter())
        counts["fresh_operands_match"] += (
            row["buy_volume"] == fresh["buy_lots"] and row["sell_volume"] == fresh["sell_lots"]
            and row["trades"] == fresh["prints"]
        )
        counts["roll20_match"] += row["roll20_value"] == roll[second]
    return counts


def thresholds(roll, births):
    """The archived detector judges t when it observes t+5, which enters its trailing bar."""
    ordered = []
    first = None
    result = {}
    for second, value in roll.items():
        if value is not None:
            insort(ordered, abs(value))
            if first is None:
                first = second
        birth = second - 5
        if birth in births:
            position = 0.85 * (len(ordered) - 1)
            low, high = floor(position), ceil(position)
            threshold = (ordered[low] if low == high
                         else ordered[low] * (high - position) + ordered[high] * (position - low))
            result[birth] = (threshold, len(ordered), birth - first + 1)
    return result


def quote_direction(previous, current, polarity):
    if not previous or not usable(previous) or not usable(current) or not polarity:
        return None
    move = current["bid"][0] + current["ask"][0] - previous["bid"][0] - previous["ask"][0]
    return sign(move) * polarity


def reconstruct():
    retained = historical_records()
    episodes = {row["candidate_id"]: row for row in retained["episode"] if "birth_recv_ns" in row}
    completion_inputs = {row["candidate"]["candidate_id"]: row["candidate"] for row in retained["episode"]
                         if "candidate" in row}
    direct_inputs = {row["candidate_id"]: row for row in retained["candidate"]}
    coordinates = {row["frankie_emission"]["input_cursor"] for row in episodes.values()}
    birth_seconds = {row["birth_recv_ns"] // NS for row in episodes.values()}
    seconds, trades, closes, births, comparisons = observe_tape(coordinates, birth_seconds)
    overlap_counts, by_candidate = overlap(episodes, trades)
    roll = {sec: window(seconds, sec)["roll20"] for sec in range(OPEN // NS, CLOSE // NS)}
    bars = thresholds(roll, birth_seconds)
    substrate = substrate_comparison(retained["flow_substrate"], seconds, roll)
    rows_out = []
    counts = Counter()
    lags = []
    cross_plane = defaultdict(Counter)
    prebirth_stack = defaultdict(Counter)
    for candidate, event in episodes.items():
        emission = event["frankie_emission"]
        close = closes[emission["input_cursor"]]
        if (emission["ts_recv_ns"], emission["group_index"]) != (close["receive_ns"], close["group_ordinal"]):
            raise ValueError(f"recognition coordinates disagree for {candidate}")
        birth = event["birth_recv_ns"] // NS
        latest = close["receive_ns"] // NS - 1
        available = event["recognized_recv_ns"] // NS
        lags.append(close["receive_ns"] - event["recognized_recv_ns"])
        earlier = [abs(roll[s]) for s in range(birth - 30, birth - 9) if roll.get(s) is not None]
        baseline = median(earlier) if earlier else 0.0
        birth_window = window(seconds, birth)
        latest_window = window(seconds, latest)
        prior_window = window(seconds, birth - 1)
        threshold, observations, span = bars[birth]
        birth_value, latest_value = birth_window["roll20"], latest_window["roll20"]
        observed = direct_inputs.get(candidate, completion_inputs.get(candidate))
        if observed:
            counts["retained_candidate_operands"] += 1
            counts["magnitude_and_polarity_match"] += (
                birth_value is not None and abs(birth_value) == observed["magnitude"]
                and sign(birth_value) == observed["polarity"]
            )
            counts["baseline_match"] += baseline == observed["baseline"]
            counts["threshold_and_history_match"] += (
                (threshold, observations, span) == (observed["threshold"],
                    observed["observations_behind_threshold"], observed["searched_span_seconds"])
            )
        if candidate in direct_inputs:
            counts["direct_candidate_row"] += 1
        if candidate in direct_inputs and candidate in completion_inputs:
            counts["direct_and_later_candidate_row"] += 1
            counts["direct_and_later_operands_match"] += all(
                direct_inputs[candidate][key] == completion_inputs[candidate][key]
                for key in ("baseline", "threshold", "magnitude", "polarity", "prominence", "available_second")
            )
        if latest_value is None:
            state = "undefined_at_emission"
        elif birth_value is None or not birth_value:
            state = "no_reconstructed_birth_direction"
        elif not latest_value:
            state = "balanced_at_emission"
        elif sign(birth_value) == sign(latest_value):
            state = "same_direction_at_emission"
        else:
            state = "opposite_direction_at_emission"
        counts[state] += 1
        quote_move = quote_direction(births[birth], close, sign(birth_value or 0))
        quote_state = {None: "unavailable", -1: "opposite", 0: "flat", 1: "same"}[quote_move]
        cross_plane[state][quote_state] += 1
        prior_quote = births[birth]
        if usable(prior_quote):
            displayed = sign(prior_quote["bid"][1] - prior_quote["ask"][1])
            aligned = displayed * sign(birth_value or 0)
            depth_state = {-1: "opposed", 0: "balanced", 1: "aligned"}[aligned]
        else:
            depth_state = "unavailable"
        lots_state = "one_lot" if birth_window["classified_lots"] == 1 else "multiple_lots"
        prebirth_stack[f"{lots_state}/{depth_state}"][quote_state] += 1
        counts["birth_no_fresh_print"] += not seconds.get(birth, {}).get("prints")
        counts["birth_single_classified_lot_in_window"] += birth_window["classified_lots"] == 1
        row = dict(
            candidate_id=candidate, birth_second=birth, available_second=available,
            recognition_group=close["group_ordinal"], recognition_cursor=close["close_cursor"],
            recognition_receive_ns=close["receive_ns"], recognition_orientation=event["orientation"],
            last_closed_second=latest, birth_window=birth_window, birth_fresh=dict(seconds.get(birth, {})),
            prebirth_window=prior_window, prebirth_quote=prior_quote,
            prebirth_displayed_depth_relative_to_birth_flow=depth_state,
            quote_move_relative_to_birth_polarity=quote_state,
            last_closed_window=latest_window, last_closed_fresh=dict(seconds.get(latest, {})),
            recognition_bid=close["bid"], recognition_ask=close["ask"],
            reconstructed_threshold=threshold, reconstructed_threshold_observations=observations,
            reconstructed_threshold_span_seconds=span, reconstructed_baseline=baseline, birth_to_emission_flow_state=state,
            overlaps=dict(by_candidate[candidate]),
        )
        if observed:
            row["recorded_operands"] = {key: observed[key] for key in (
                "baseline", "threshold", "magnitude", "polarity", "prominence",
                "observations_behind_threshold", "searched_span_seconds", "window_truncated",
            )}
            row["recorded_operands_source"] = "candidate_emission" if candidate in direct_inputs else "later_episode"
        rows_out.append(row)

    return dict(
        evidence_revision=REVISION, raw_tape_revision=TAPE, producer_reference_revision=PRODUCER,
        recognitions=len(episodes), later_episode_rows=len(completion_inputs), tape_prints=len(trades),
        flow_and_midpoint_direction={key: dict(value) for key, value in cross_plane.items()},
        birth_flow_and_prebirth_touch_size_vs_midpoint={key: dict(value) for key, value in prebirth_stack.items()},
        candidate_counts=dict(counts), recognition_delay_from_nominal_bin_ns=pct(lags),
        retained_flow_comparison=dict(substrate), print_classifier_comparison=dict(comparisons),
        overlap=overlap_counts,
    ), rows_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    summary, records = reconstruct()
    (args.output_directory / "october18-candidate-input-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    (args.output_directory / "october18-candidate-inputs.jsonl.gz").write_bytes(
        gzip.compress(payload.encode("utf-8"), mtime=0),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
