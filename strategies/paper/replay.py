"""Replay a recording through lines, quotes, legs and the CL rules (Part A). Sends nothing anywhere.

    python3 -m strategies.paper.replay --recording FILE --out DIR [--cut K]

DIR must not be inside the Markets checkout. Writes ledger.jsonl (one line per paper trade) and receipt.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from types import MappingProxyType

from strategies.paper import feed_tasty
from strategies.paper.events import DAYVOLUME, PRINT, QUOTE
from strategies.paper.ledger import NOT_SCORED, STAND_INS, Ledger
from strategies.paper.lines import LiveLines
from strategies.paper.quotes_live import LiveLegs, LiveQuotes
from strategies.paper.rule_base import CLOSE, OPEN, Snapshot
from strategies.paper.rules_cl import all_rules

MARKETS = Path(__file__).resolve().parents[2]


class Engine:
    def __init__(self, rules=None):
        self.lines, self.quotes, self.legs, self.ledger = LiveLines(), LiveQuotes(), LiveLegs(), Ledger()
        self.rules = all_rules() if rules is None else rules
        self.n_prints = self.n_unsided = self.n_quote_messages = 0
        self.pending_runs, self.pending_legs = [], []
        self.printed_size = 0.0
        self.dv0 = None                 # (day volume, printed size) at the first Trade message with a day volume
        self.unexplained_last, self.gaps, self.day_volume_messages = 0.0, 0, 0
        self.last_unexplained = 0.0
        self.snapshots_seen = 0

    def on_event(self, ev):
        if isinstance(ev, PRINT):
            self._print(ev)
        elif isinstance(ev, QUOTE):
            self.n_quote_messages += 1
            self.quotes.on_quote(ev)
        elif isinstance(ev, DAYVOLUME):
            self._day_volume(ev)

    def _day_volume(self, ev):
        self.day_volume_messages += 1
        if ev.day_volume is None:
            return
        if self.dv0 is None:
            self.dv0 = (ev.day_volume, self.printed_size)
        un = (ev.day_volume - self.dv0[0]) - (self.printed_size - self.dv0[1])
        if un > self.unexplained_last and un > 0:
            self.gaps += 1
        self.unexplained_last = un

    def _print(self, p: PRINT):
        idx = self.n_prints
        self.n_prints += 1
        if p.size is not None:
            self.printed_size += p.size
        run_facts, quote_missing = self.quotes.on_print(p, idx)
        leg_facts = self.legs.on_print(p, idx)
        for f in run_facts + leg_facts:
            f['here'] = True
        state = self.lines.on_print(p, idx)
        self.pending_runs += run_facts
        self.pending_legs += leg_facts
        if state is None:                               # no side: neither opens nor closes anything (rule 5)
            self.n_unsided += 1
            for f in self.pending_runs + self.pending_legs:
                f['here'] = False
            return
        snap = Snapshot(p, idx, state, tuple(self.pending_runs), tuple(self.pending_legs), quote_missing,
                        lambda i: self.quotes.at_print[i])
        self.pending_runs, self.pending_legs = [], []
        for rule in self.rules:
            own = dataclasses.replace(snap, own_open=MappingProxyType({k: dict(v) for k, v in rule.trades.items()}))
            for sig in rule.step(own):
                if isinstance(sig, OPEN):
                    self.ledger.open(sig, p)
                elif isinstance(sig, CLOSE):
                    self.ledger.close(sig, p)
        # facts left over as "here" belong to this print only
        self.snapshots_seen += 1

    def counts(self) -> dict:
        return dict(prints=self.n_prints, prints_with_no_side=self.n_unsided, quote_messages=self.n_quote_messages,
                    day_volume_messages=self.day_volume_messages, gaps=self.gaps,
                    unexplained_day_volume_at_end=self.unexplained_last, print_size_seen=self.printed_size,
                    prints_missing_bid_or_offer=self.quotes.n_print_missing,
                    quote_messages_missing_bid_or_offer=self.quotes.n_quote_missing,
                    prints_with_no_size=self.lines.n_no_size, prints_with_no_price=self.legs.n_price_missing,
                    rules={r.code: dict(r.counts, missing=dict(r.missing_counts), title=r.title) for r in self.rules})


def run(path, cut=None) -> Engine:
    eng = Engine()
    for ev in feed_tasty.events_from_recording(path, cut):
        eng.on_event(ev)
    return eng


def _sha(path) -> tuple:
    b = Path(path).read_bytes()
    return len(b), hashlib.sha256(b).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recording', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cut', type=int, default=None)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if out == MARKETS or MARKETS in out.parents:
        print(f'refused: --out {out} is inside {MARKETS}; outputs go to a markets-data checkout', file=sys.stderr)
        return 2
    eng = run(a.recording, a.cut)
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / 'ledger.jsonl'
    ledger_path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in eng.ledger.records()))
    size, sha = _sha(ledger_path)
    rec_size, rec_sha = _sha(a.recording)
    receipt = dict(
        what='replay of a 7e recording through the paper runner, Part A: sends nothing', note=NOT_SCORED,
        recording=dict(path=str(a.recording), bytes=rec_size, sha256=rec_sha, cut_first_k_messages=a.cut),
        counts=eng.counts(), trades_in_ledger=len(eng.ledger.records()), stand_ins=STAND_INS,
        leakage_gate='the cut-equals-whole check stands in for odcore/leakage.py on a replay; nothing here is a '
                     'backtest result',
        not_testable_on_real_data='the 4:44 pm stop, the halt hour and the settlement window (the recordings cover '
                                  'about 6:00 to 6:26 pm on the feed)',
        manifest_entries=[dict(path='ledger.jsonl', bytes=size, sha256=sha, source=str(a.recording))])
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + '\n')
    c = eng.counts()
    print(f"prints {c['prints']}  prints with no side {c['prints_with_no_side']}  quote messages "
          f"{c['quote_messages']}  gaps {c['gaps']}  (unexplained day volume {c['unexplained_day_volume_at_end']}, "
          f"print sizes seen {c['print_size_seen']})")
    for code, r in c['rules'].items():
        print(f"{code}  armed {r['armed']}  opened {r['opened']}  closed {r['closed']}  missing {r['missing']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
