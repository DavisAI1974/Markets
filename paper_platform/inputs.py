"""Strategy inputs for one ordered MBO stream, using ROOT's recorded-clock conventions."""
from collections import deque
import numpy as np

from crypto_ng.tick import LEAN_NS, LINE_NS, line
from root.calendar import SETTLE_FROM_EASTERN, SETTLE_TO_EASTERN, eastern, to_ns, trade_day_bounds
from root.calcs.quote_runs import FACT_NAMES, QuoteRuns
from root.calcs.leg_peaks import Legs


class Flow:
    def __init__(self, width):
        self.width = width
        self.trades = deque()
        self.size = [0, 0]
        self.value = None

    def change(self):
        values, empty = line(np.array(self.size[:1]), np.array(self.size[1:]))
        self.value = None if empty[0] else float(values[0])

    def expire(self, received):
        changed = False
        while self.trades and self.trades[0][0] + self.width <= received:
            _, side, qty = self.trades.popleft()
            self.size[side] -= qty
            changed = True
        if changed:
            self.change()

    def add(self, received, side, size):
        key = 0 if side == 'B' else 1
        self.trades.append((received, key, size))
        self.size[key] += size
        self.change()


class StrategyInputs:
    def __init__(self, trade_day):
        self.dipole = Flow(LEAN_NS)
        self.exhaustion = Flow(LINE_NS)
        self.quotes = QuoteRuns()
        self.legs = Legs()
        self.start = to_ns(eastern(trade_day, SETTLE_FROM_EASTERN))
        self.end = to_ns(eastern(trade_day, SETTLE_TO_EASTERN))
        self.end_of_day = trade_day_bounds(trade_day)[1]
        self.last_received = None

    def at(self, message):
        if not message['in_session']:
            return None
        raw = message['raw']
        received = raw['ts_recv']
        if self.last_received is not None and received < self.last_received:
            raise ValueError('received clock went backwards within the selected trade day')
        self.last_received = received
        for flow in (self.dipole, self.exhaustion):
            flow.expire(received)
        before = self.dipole.value, self.exhaustion.value
        trade = raw['action'] == 'T'
        if trade and raw['side'] in ('B', 'A'):
            for flow in (self.dipole, self.exhaustion):
                flow.add(received, raw['side'], raw['size'])
        bid, ask = message['best_bid'], message['best_ask']
        pos = message['position_on_tape']
        facts = []
        if bid is not None and ask is not None:
            _, facts = self.quotes.tick(pos, received, bid, ask)
        else:
            self.quotes = QuoteRuns()
        if trade:
            self.legs.trade(pos, received, raw['price'])
        return dict(position=pos, received=received, exchange=raw['ts_event'],
                    reference=(message['source_sha256'], message['record_index']),
                    event=message['event_start_position'], bid=bid, ask=ask,
                    trade=trade, price=raw['price'] if trade else None,
                    aggressor=raw['side'] if trade and raw['side'] in ('B', 'A') else None,
                    dipole=self.dipole.value, exhaustion=self.exhaustion.value,
                    dipole_before=before[0], exhaustion_before=before[1],
                    settlement=self.start <= raw['ts_event'] < self.end,
                    quote_facts=[dict(zip(FACT_NAMES, fact)) for fact in facts],
                    leg=self.legs.now())

