"""Use retained NG quote and flow tables to investigate the primer's open questions."""

import argparse
from collections import Counter
import gzip
import io
import json
from math import sqrt
from pathlib import Path
import sqlite3

from audit_october18_touch_mechanisms import capture_groups, git_blob
from reconstruct_october18_candidate_inputs import rows
from research_october18_trade_prebirth import NS, TOUCH, adjacent, usable

TICK = 1_000_000
FLOW_REVISION = "f0bd88e1728668ae3fc9bdd5f62921f9d89fcd13"
BASE = "tasks/family-research-20261022"


def load_groups(db):
    db.executescript("""
        CREATE TABLE book(
            g INTEGER PRIMARY KEY, ns INTEGER, segment INTEGER, mid INTEGER, spread INTEGER,
            bid INTEGER, ask INTEGER, bid_size INTEGER, ask_size INTEGER,
            prior_mid INTEGER, prior_spread INTEGER, prior_bid INTEGER, prior_ask INTEGER,
            prior_bid_size INTEGER, prior_ask_size INTEGER,
            prints INTEGER, buy INTEGER, sell INTEGER, unknown INTEGER, one_at_prior_touch INTEGER
        );
    """)

    def records():
        previous, segment = None, 0
        for row in rows(TOUCH):
            if not usable(row):
                previous = None
                continue
            if not previous or not adjacent(previous, row):
                segment += 1
                previous = None
            bid, bid_size, _ = row["bid"]
            ask, ask_size, _ = row["ask"]
            prior_bid, prior_ask = (previous["bid"], previous["ask"]) if previous else ([None, None], [None, None])
            prior_mid = prior_bid[0] + prior_ask[0] if previous else None
            prior_spread = prior_ask[0] - prior_bid[0] if previous else None
            volume = Counter()
            for trade in row["prints"]:
                volume[trade["aggressor_side"]] += trade["size"]
            one_at_prior_touch = 0
            if len(row["prints"]) == 1:
                trade = row["prints"][0]
                price = {"B": prior_ask[0], "A": prior_bid[0]}.get(trade["aggressor_side"])
                one_at_prior_touch = int(trade["size"] == 1 and trade["price_raw"] == price)
            yield (
                row["group_ordinal"], row["receive_ns"], segment, bid + ask, ask - bid,
                bid, ask, bid_size, ask_size, prior_mid, prior_spread,
                prior_bid[0], prior_ask[0], prior_bid[1], prior_ask[1], len(row["prints"]),
                volume["B"], volume["A"], volume.total() - volume["B"] - volume["A"], one_at_prior_touch,
            )
            previous = row

    db.executemany("INSERT INTO book VALUES (" + ",".join("?" * 20) + ")", records())
    db.executescript("""
        CREATE INDEX book_clock ON book(ns, g);
        CREATE TABLE trade_groups AS
        WITH signed AS (
            SELECT *, CASE WHEN unknown > 0 OR (buy > 0 AND sell > 0) THEN 0
                       WHEN buy > 0 THEN 1 WHEN sell > 0 THEN -1 ELSE 0 END AS side
            FROM book WHERE prints > 0
        ), boundaries AS (
            SELECT *, COALESCE(side != LAG(side) OVER w OR segment != LAG(segment) OVER w, 1) AS starts
            FROM signed WINDOW w AS (ORDER BY g)
        ), runs AS (
            SELECT *, SUM(starts) OVER (ORDER BY g) AS run_id FROM boundaries
        )
        SELECT *, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY g) AS run_position,
               ROW_NUMBER() OVER (ORDER BY g) AS trade_number
        FROM runs ORDER BY g;
        CREATE UNIQUE INDEX trade_number ON trade_groups(trade_number);
    """)


def stats(db, select, source, where):
    values = db.execute(
        f"SELECT COUNT(*), AVG(x), AVG(y), AVG(x*y), AVG(x*x), AVG(y*y) "
        f"FROM (SELECT {select} FROM {source} WHERE {where})"
    ).fetchone()
    n, x, y, xy, xx, yy = values
    variance = (xx - x*x) * (yy - y*y) if n else 0
    return dict(n=n, pearson=(xy - x*y) / sqrt(variance) if variance > 0 else None)


def trade_memory(db):
    result = {}
    for lag in (1, 2, 5, 10, 20, 50, 100):
        base = f"trade_groups a JOIN trade_groups b ON b.trade_number=a.trade_number+{lag}"
        matched = "a.segment=b.segment AND a.side!=0 AND b.side!=0"
        result[str(lag)] = {
            "sign": stats(db, "a.side AS x,b.side AS y", base, matched),
            "immediate_midpoint": stats(
                db, "a.mid-a.prior_mid AS x,b.mid-b.prior_mid AS y", base,
                matched + " AND a.prior_mid IS NOT NULL AND b.prior_mid IS NOT NULL",
            ),
        }
    return result


def quote_panel(db):
    db.executescript(f"""
        CREATE TABLE regular AS
        WITH RECURSIVE ends(t, finish) AS (
            SELECT MIN(ns)/{NS}+1, MAX(ns)/{NS} FROM book
            UNION ALL SELECT t+1, finish FROM ends WHERE t<finish
        )
        SELECT ends.t, b.segment, b.mid, b.spread, ends.t*{NS}-b.ns AS age
        FROM ends JOIN book b ON b.g=(
            SELECT g FROM book WHERE ns<ends.t*{NS} ORDER BY ns DESC,g DESC LIMIT 1
        );
        CREATE UNIQUE INDEX regular_time ON regular(t);
        CREATE TABLE regular_changes AS
        SELECT b.t, b.segment, a.age AS first_age, b.age AS last_age,
               ABS(b.mid-a.mid) AS magnitude, a.spread AS prior_spread
        FROM regular a JOIN regular b ON b.t=a.t+1 AND b.segment=a.segment;
        CREATE UNIQUE INDEX regular_changes_time ON regular_changes(t);
    """)
    results = {}
    for age in (1, 10):
        for lag in (1, 5, 20, 60):
            results[f"max_age_{age}s/lag_{lag}s"] = stats(
                db, "a.magnitude AS x,b.magnitude AS y",
                f"regular_changes a JOIN regular_changes b ON b.t=a.t+{lag}",
                f"a.segment=b.segment AND max(a.first_age,a.last_age,b.first_age,b.last_age)<={age*NS}",
            )
    tail = db.execute(f"""
        SELECT prior_spread/{TICK} AS spread_ticks, COUNT(*),
               SUM(magnitude=0), SUM(magnitude>={4*TICK}), SUM(magnitude>={8*TICK}),
               MAX(magnitude)/{TICK} FROM regular_changes
        WHERE MAX(first_age,last_age)<={NS} GROUP BY 1 ORDER BY 1
    """)
    columns = ("prior_spread_ticks", "n", "flat", "at_least_two_ticks", "at_least_four_ticks", "max_half_ticks")
    return results, [dict(zip(columns, row)) for row in tail]


def response_cells(db):
    # Both move and flow refer to the just-completed group. Future outcomes start at its close.
    db.executescript(f"""
        CREATE TABLE segment_end AS SELECT segment,MAX(ns) AS last_ns FROM book GROUP BY segment;
        CREATE UNIQUE INDEX segment_end_number ON segment_end(segment);
        CREATE TABLE response AS
        SELECT a.*, (a.mid-a.prior_mid)*a.side/{TICK} AS impact_half_ticks,
               CASE WHEN a.side=1 THEN a.prior_ask_size ELSE a.prior_bid_size END AS contra_size,
               CASE WHEN a.run_position=1 THEN '1' WHEN a.run_position<=3 THEN '2-3'
                    WHEN a.run_position<=7 THEN '4-7' ELSE '8+' END AS run_band,
               CASE WHEN a.buy+a.sell=1 THEN '1' WHEN a.buy+a.sell<5 THEN '2-4'
                    WHEN a.buy+a.sell<20 THEN '5-19' ELSE '20+' END AS volume_band,
               CASE WHEN (a.side=1 AND a.ask!=a.prior_ask) OR
                         (a.side=-1 AND a.bid!=a.prior_bid) THEN 'opposite_touch_moved'
                    WHEN (a.side=1 AND a.ask_size>a.prior_ask_size) OR
                         (a.side=-1 AND a.bid_size>a.prior_bid_size) THEN 'opposite_touch_gained_size'
                    WHEN (a.side=1 AND a.ask_size<a.prior_ask_size) OR
                         (a.side=-1 AND a.bid_size<a.prior_bid_size) THEN 'opposite_touch_lost_size'
                    ELSE 'opposite_touch_same_size' END AS touch_state,
               CASE WHEN b.segment=a.segment AND a.ns+5*{NS}-b.ns<={NS} AND b.g>=a.g AND a.ns+5*{NS}<=ends.last_ns
                    THEN (b.mid-a.mid)*a.side/{TICK} END AS after_5s_half_ticks
        FROM trade_groups a JOIN segment_end ends ON a.segment=ends.segment
        LEFT JOIN book b ON b.g=(
            SELECT g FROM book WHERE ns<=a.ns+5*{NS} ORDER BY ns DESC,g DESC LIMIT 1
        )
        WHERE a.side!=0 AND a.prior_mid IS NOT NULL;
    """)
    metrics = """COUNT(*) AS n, AVG(impact_half_ticks) AS mean_impact_half_ticks,
        SUM(impact_half_ticks>0) AS aligned_immediate, SUM(impact_half_ticks=0) AS flat_immediate,
        SUM(impact_half_ticks<0) AS opposed_immediate,
        AVG(contra_size) AS mean_prior_opposite_size,
        SUM(touch_state='opposite_touch_moved') AS opposite_touch_moved,
        COUNT(after_5s_half_ticks) AS n_after_5s, SUM(after_5s_half_ticks>0) AS further_after_5s,
        SUM(after_5s_half_ticks=0) AS flat_after_5s, SUM(after_5s_half_ticks<0) AS reversed_after_5s"""
    populations = {
        "run": ("run_band", ""),
        "run_one_tick_spread": ("run_band", f"WHERE prior_spread={TICK}"),
        "run_one_tick_spread_by_volume": ("run_band,volume_band", f"WHERE prior_spread={TICK}"),
        "volume_by_spread": (f"volume_band,prior_spread/{TICK} AS spread_ticks", ""),
        "touch_by_run": ("run_band,touch_state", ""),
        "one_lot_printed_at_prior_touch_by_exact_depth": (
            "run_band,contra_size", f"WHERE prior_spread={TICK} AND one_at_prior_touch=1 AND contra_size<=10"
        ),
        "one_lot_by_exact_contra_depth": (
            "run_band,contra_size", f"WHERE prior_spread={TICK} AND volume_band='1' AND contra_size<=10"
        ),
    }
    result = {}
    for name, (keys, where) in populations.items():
        columns = keys.count(",") + 1
        group_by = ",".join(str(i + 1) for i in range(columns))
        query = db.execute(f"SELECT {keys},{metrics} FROM response {where} GROUP BY {group_by} ORDER BY {group_by}")
        result[name] = [dict(zip((item[0] for item in query.description), row)) for row in query]
    return result


def trace_examples(db):
    examples = {}
    for case, condition in (
        ("gained_size_then_against", "touch_state='opposite_touch_gained_size' AND after_5s_half_ticks<0"),
        ("touch_moved_then_with", "touch_state='opposite_touch_moved' AND impact_half_ticks>0 AND after_5s_half_ticks>0"),
    ):
        query = db.execute(f"""
            SELECT g,ns,run_position,bid,ask,bid_size,ask_size,prior_bid,prior_ask,
                   prior_bid_size,prior_ask_size,impact_half_ticks,after_5s_half_ticks
            FROM response
            WHERE ns>=1697587200000000000 AND side=1 AND run_position>=8
            AND prior_spread={TICK} AND volume_band='1' AND {condition}
            ORDER BY g LIMIT 1
        """)
        examples[case] = dict(zip((item[0] for item in query.description), query.fetchone()))
    by_group = {row["g"]: row for row in examples.values()}
    snapshots = {}
    previous = None
    for row in rows(TOUCH):
        if row["group_ordinal"] in by_group:
            example = by_group[row["group_ordinal"]]
            example["close_cursor"] = row["close_cursor"]
            snapshots[row["close_cursor"]] = previous, row
        if len(snapshots) == len(examples):
            break
        previous = row
    traces = capture_groups(snapshots)
    for example in examples.values():
        example["order_trace"] = traces[example["close_cursor"]]
    return examples


def per_second_flow():
    result = {}
    for day in ("20231002", "20231017"):
        path = f"{BASE}/flow-book-discovery-v1/date-tables/{day}/legacy_native_signed_flow.json.gz"
        raw = json.loads(gzip.decompress(git_blob(FLOW_REVISION, path)))
        seconds = {r["second"]: (r["buy"] > r["sell"]) - (r["buy"] < r["sell"]) for r in raw["per_second"]}
        result[day] = {
            str(lag): dict(Counter(
                "same" if direction == seconds[sec+lag] else "opposite"
                for sec, direction in seconds.items() if direction and seconds.get(sec+lag)
            )) for lag in (1, 5, 20, 60)
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    with sqlite3.connect(":memory:") as db:
        load_groups(db)
        book_groups, print_groups, pure_groups = db.execute("""
            SELECT (SELECT COUNT(*) FROM book), COUNT(*), SUM(side!=0) FROM trade_groups
        """).fetchone()
        memory = trade_memory(db)
        clustering, tail = quote_panel(db)
        response = response_cells(db)
        examples = trace_examples(db)
    result = dict(
        book_groups=book_groups, print_groups=print_groups, pure_signed_print_groups=pure_groups,
        trade_memory=memory, quote_volatility_clustering=clustering, spread_conditioned_tails=tail,
        signed_group_response=response, contrasting_order_traces=examples,
        partial_day_classified_flow=per_second_flow(),
        notes=["Group midpoint changes are in half ticks.",
               "The partial dates use midpoint-classified flow and measure second lags. The October 18 group study uses wire side and measures group lags.",
               "Fixed-time outcomes require a quote from the same segment with no more than one second of staleness.",
               "Positive, flat, negative and unavailable outcomes stay separate."],
    )
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
