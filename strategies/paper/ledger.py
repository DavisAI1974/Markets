"""One record per paper trade (Part A). No result figure, no mid price, no cost.

Both the events (an open and a close, each written when it happens) and the per-trade records are kept. Bid and
offer at each end stay each on its own.
"""
from __future__ import annotations

from strategies.paper.events import PRINT

NOT_SCORED = 'not scored: tastytrade sandbox feed'
STAND_INS = {
    'S1': 'the clock: the lines are made on the feed trade time in ms (as ns) and sequence',
    'S2': 'the event mark: a rule decides at the feed message (print) that shows its trigger; "a later exchange '
          'event" is read as "a later feed trade time"',
    'S3': 'the quotes: the print\'s own bid and offer only (G1); quote messages are recorded, never read by a rule',
    'S4': 'the trades: the lines and the rules use prints that carry a side; prints with no side are counted',
    'S5': 'a moment at which trades only leave a span is known at the next print; a close that depends on it is '
          'made then and marked known late',
    'S6': 'the end-of-trade-day close cannot be sent; the flatten at the stop takes its place (not in Part A)',
    'CL13': 'prints of one side sharing one feed time at more than one price',
}


def _end(p: PRINT) -> dict:
    return dict(place=list(p.place), feed_time_ns=p.time_ns, sequence=p.sequence, receive_t_ns=p.t_ns,
                bid=p.bid, offer=p.offer)


class Ledger:
    def __init__(self):
        self.events = []        # an open or a close, in the order made
        self.trades = {}        # trade id -> record

    def open(self, sig, p: PRINT):
        stands = ['S1', 'S2', 'S3', 'S4'] + (['CL13'] if sig.rule == 'CL13' else [])
        rec = dict(strategy=sig.rule, trade_id=sig.trade_id, side=sig.side, opened=_end(p),
                   trigger=sig.trigger, closed=None, stand_ins=stands, note=NOT_SCORED)
        self.trades[sig.trade_id] = rec
        self.events.append(dict(event='open', strategy=sig.rule, trade_id=sig.trade_id, side=sig.side,
                                at=_end(p), trigger=sig.trigger))

    def close(self, sig, p: PRINT):
        rec = self.trades[sig.trade_id]
        rec['closed'] = dict(_end(p), reason=sig.reason, verdict=sig.verdict, known_late=sig.known_late,
                             detail=sig.detail)
        if sig.known_late and 'S5' not in rec['stand_ins']:
            rec['stand_ins'].append('S5')
        self.events.append(dict(event='close', strategy=sig.rule, trade_id=sig.trade_id, at=_end(p),
                                reason=sig.reason, verdict=sig.verdict, known_late=sig.known_late, detail=sig.detail))

    def records(self) -> list:
        return list(self.trades.values())
