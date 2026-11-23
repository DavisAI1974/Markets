"""Contract checks against Greg's purchased NG tape only. No broker, saved session or fixtures."""
import json
import os
from datetime import date
from itertools import islice
from pathlib import Path

import numpy as np
import pytest
from crypto_ng.tick import LEAN_NS, LINE_NS, line, reads
from root import tape
from root.book import Book, compare_with_restatement, BID, ASK

from .engine import Engine
from .feed import HistoricalFeed
from .inputs import StrategyInputs
from .rulebook import catalogue


@pytest.fixture(scope='module')
def feed():
    folder = Path(os.environ['MARKETS_DATA']) / 'data/nymex_mbo/ng_v0_oct2023'
    return HistoricalFeed(folder, date(2023, 10, 2))


def test_every_field_order_and_midnight_restatement(feed):
    first, second = feed.week
    boundary = len(first.records)
    it = feed.messages()
    for i, event in enumerate(islice(it, boundary)):
        assert event['cursor'] == i
        assert event['record_index'] == i
        assert event['source_sha256'] == first.sha256
        assert event['received_by_replay_ns'] > event['raw']['ts_recv']
        expected = first.records[i]
        assert event['raw'] == {k:expected[k].decode() if expected.dtype[k].kind == 'S'
                                else int(expected[k]) for k in expected.dtype.names}
    end_quotes = (event['best_bid'], event['best_ask'])
    for i in range(second.vendor_snapshot):
        restated = next(it)
        assert restated['period'] == tape.VENDOR_SNAPSHOT
        assert restated['position_on_tape'] is None
        assert restated['record_index'] == i
        assert (restated['best_bid'], restated['best_ask']) == end_quotes
    resumed = next(it)
    assert resumed['position_on_tape'] == boundary
    assert resumed['source_sha256'] == second.sha256


def test_lines_equal_root_at_each_sided_print(feed):
    inputs = StrategyInputs(feed.trade_day)
    times, buy, sizes, observations = [], [], [], []
    for message in islice(feed.messages(), len(feed.week[0].records)):
        t = inputs.at(message)
        if t and t['trade'] and t['aggressor']:
            times.append(t['received'])
            buy.append(t['aggressor'] == 'B')
            sizes.append(message['raw']['size'])
            observations.append((t['exhaustion'], t['dipole']))
    assert times
    for column, width in enumerate((LINE_NS, LEAN_NS)):
        reference = reads(np.array(times), np.array(buy), np.array(sizes), width, times[-1]+1)
        values, _ = line(reference['bought'], reference['sold'])
        assert np.array_equal(values[reference['trade'] >= 0], [o[column] for o in observations])


def test_trade_prefix_including_equal_nanoseconds(feed):
    full = Engine(feed.trade_day, 'contract-check')
    prefix = Engine(feed.trade_day, 'contract-check')
    # The cut is a real source record inside a group of equal receive timestamps.
    raw = feed.week[0].records
    cutoff = next(i for i in range(len(raw)//2, len(raw)-1)
                  if raw[i]['ts_recv'] == raw[i+1]['ts_recv'])
    left, right, later = [], [], False
    for m in islice(feed.messages(), len(raw)):
        events = full.tick(m)
        if m['cursor'] <= cutoff:
            left.extend(events)
            right.extend(prefix.tick(m))
        else:
            later = True
    assert later and left and left == right
    assert all(e['bid'] is None or isinstance(e['bid'], int) for e in left)
    assert all('fill_price' not in e and 'pnl' not in e for e in left)


def test_thirty_pinned_rule_definitions():
    rules = catalogue()
    assert set(rules) == {f'{family}{i:02}' for family in ('CL','CX') for i in range(1,16)}
    assert sum(r['role']=='manager' for r in rules.values()) == 6
    for name, r in rules.items():
        assert r['specification'].startswith('## '+name) and '/blob/' in r['evidence']

