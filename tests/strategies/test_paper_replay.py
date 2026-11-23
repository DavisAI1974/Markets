"""Part A checks on the REAL 7e recording only. A missing recording is a skip, never invented data."""
import json
from pathlib import Path

import numpy as np
import pytest

from crypto_ng import tick
from strategies.paper import feed_tasty
from strategies.paper.events import PRINT, QUOTE
from strategies.paper.lines import EMPTY, MISSING
from strategies.paper.replay import Engine, run
from strategies.paper.rule_base import Rule

RECORDING = Path('/home/user/markets-data/tasks/family-research-20261022/research-union-current/'
                 'paper-trading-20261123/7e/sandbox-stream-20261123T231452738619403Z.jsonl')


@pytest.fixture(scope='module')
def recording():
    if not RECORDING.exists():
        pytest.skip(f'the real recording is not here: {RECORDING}')
    return RECORDING


def _msg_nos(path):
    out = []
    for line in open(path, encoding='utf-8'):
        o = json.loads(line)
        if o.get('kind') == 'received':
            out.append(int(o['msg_no']))
    return out


def _dump(events):
    return json.dumps(events, sort_keys=True, default=str)


def test_cut_equals_whole(recording):
    msgs = _msg_nos(recording)
    whole = run(recording)
    assert whole.ledger.events, 'the whole recording made no ledger event: the check would prove nothing'
    ks = sorted({int(k) for k in np.linspace(10, len(msgs), 16)})
    assert len(ks) >= 12
    for k in ks:
        last = msgs[k - 1]
        cut = run(recording, cut=k)
        expected = [e for e in whole.ledger.events if e['at']['place'][0] <= last]
        assert _dump(cut.ledger.events) == _dump(expected), f'cut at {k} differs from the whole up to {k}'
        assert cut.counts()['prints'] == sum(1 for e in feed_tasty.events_from_recording(recording, k)
                                             if isinstance(e, PRINT))


def test_live_lines_equal_one_pass(recording):
    eng = run(recording)
    prints = [e for e in feed_tasty.events_from_recording(recording) if isinstance(e, PRINT)]
    sided = [p for p in prints if p.side is not None]
    assert len(eng.lines.log) == len(sided) > 0
    t = np.array([p.time_ns for p in sided], np.int64)
    buy = np.array([p.side == 'B' for p in sided])
    size = np.array([int(p.size) for p in sided], np.int64)
    until = int(t[-1]) + 1
    first = prints[0].time_ns
    for span, col in ((tick.LINE_NS, 1), (tick.LEAN_NS, 2)):
        r = tick.reads(t, buy, size, span, until)
        flow, quiet = tick.line(r['bought'], r['sold'])
        at = {int(tr): k for k, tr in enumerate(r['trade']) if tr != tick.NONE}
        assert len(at) == len(sided)
        for row in eng.lines.log:
            k = at[row[0]]
            if int(r['moment'][k]) - first < span:
                want = MISSING
            else:
                want = EMPTY if quiet[k] else float(flow[k])
            assert row[col] == want, f'sided print {row[0]}, span {span}: live {row[col]} one pass {want}'


class _Spy(Rule):
    code = 'SPY'

    def __init__(self):
        super().__init__()
        self.places = set()

    def decide(self, snap):
        self.places |= {f['place'] for f in snap.run_facts}
        return []


def test_quote_read_by_rules_never_from_a_quote_event(recording):
    events = list(feed_tasty.events_from_recording(recording))
    print_places = {e.place for e in events if isinstance(e, PRINT)}
    quote_places = {e.place for e in events if isinstance(e, QUOTE)}
    assert quote_places and not (quote_places & print_places)
    spy = _Spy()
    eng = Engine(rules=[spy])
    for e in events:
        eng.on_event(e)
    assert spy.places and spy.places <= print_places
    # the answer of every rule is the same with every QUOTE event taken away
    with_quotes = run(recording)
    eng2 = Engine()
    for e in events:
        if not isinstance(e, QUOTE):
            eng2.on_event(e)
    assert _dump(with_quotes.ledger.events) == _dump(eng2.ledger.events)
    assert eng.quotes.n_quote_messages == len(quote_places)
