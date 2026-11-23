"""Quote-only paper decisions. Every management action names its originating entry."""
from .claude_rules import ClaudeRules
from .inputs import StrategyInputs
from .rulebook import catalogue, confirmation, management, manager_action


def quote(t):
    return {k:t[k] for k in ('position', 'received', 'exchange', 'reference', 'bid', 'ask')}


class Engine:
    def __init__(self, trade_day, run_id):
        self.run_id = run_id
        self.inputs = StrategyInputs(trade_day)
        self.cl = ClaudeRules()
        self.rules = catalogue()
        self.cx = [r for r in self.rules.values() if r['family'] == 'CX']
        self.open = {}
        self.managers = {}
        self.p = None
        self.last = None
        self.ended = False

    def event(self, rule, action, why, tick, key, **details):
        return dict(rule=rule, action=action, reason=why, trade_id=key, **quote(tick), **details)

    def open_trade(self, signal, t, p=None):
        rule = signal['rule']
        key = f"{self.run_id}/{rule}/{t['position']}/{signal['identity']}"
        self.open[key] = dict(**signal, opened_at=t['position'], closed=False, p=p, q=t)
        return self.event(rule, 'open', signal['reason'], t, key, side=signal['side'])

    def close_trade(self, key, reason, t, administrative=False):
        idea = self.open.pop(key)
        self.managers.pop(key, None)
        return self.event(idea['rule'], 'close', reason, t, key, side=idea['side'],
                          entry=quote(idea['q']), trade_data=not administrative)

    def manage(self, key, idea, t):
        # Independent assessments refer to one parent's trade. They never create a second entry.
        active = self.managers.setdefault(key, {})
        events = []
        for rule in self.cx:
            if rule['role'] != 'manager' or rule['direction'] != idea['side']:
                continue
            name = rule['id']
            state = active.get(name)
            if state is not None:
                if state['finished']:
                    continue
                action, missing = management(rule, idea['side'], state['p'], state['q'], t)
                if action == 'exit' or missing:
                    state['finished'] = True
                elif action == 'release warning':
                    del active[name]
            elif self.p and t['trade']:
                action, missing = manager_action(rule, idea, self.p, t)
                if action:
                    active[name] = dict(p=self.p, q=t, finished=action == 'exit')
            else:
                continue
            if missing:
                action = 'not scored'
                reason = 'not scored: the feed lacks ' + ', '.join(sorted(set(missing)))
            else:
                reason = rule['specification'].splitlines()[0][3:]
            if action:
                events.append(self.event(name, action, reason, t, key, entry_rule=idea['rule'],
                                         entry=quote(idea['q']), side=idea['side']))
        return events

    def tick(self, message):
        if self.ended:
            return []
        if not message['in_session']:
            # Trade-day closure is knowable only when the clock leaves the trade day.
            # Later-file vendor snapshots are bookkeeping, including while a position is open.
            if self.last and message['period'] != 'vendor snapshot' and message['raw']['ts_event'] >= self.inputs.end_of_day:
                self.ended = True
                closed = self.stop('trade day ended', administrative=False)
                for event in closed:
                    event['known_at'] = [message['source_sha256'], message['record_index']]
                    event['known_received_ns'] = message['raw']['ts_recv']
                return closed
            return []
        t = self.inputs.at(message)
        self.last = t
        signals = self.cl.at(message, t)
        events = []
        for key, idea in list(self.open.items()):
            if not t['settlement']:
                events.extend(self.manage(key, idea, t))
            rule = self.rules[idea['rule']]
            if rule['family'] == 'CL':
                close = self.cl.close(idea, message, t)
                if t['settlement'] and not idea.get('settlement_seen'):
                    idea['settlement_seen'] = True
                    events.append(self.event(rule['id'], 'held into settlement', 'settlement window began', t, key))
            elif t['settlement']:
                close = 'observation interrupted at settlement'
            else:
                close, missing = management(rule, idea['side'], idea['p'], idea['q'], t)
                if missing:
                    close = 'not scored: the feed lacks ' + ', '.join(sorted(set(missing)))
            if close:
                events.append(self.close_trade(key, close, t))
        for signal in signals:
            events.append(self.open_trade(signal, t))
        if t['settlement']:
            self.p = None
        elif t['trade']:
            if self.p:
                active_names = {idea['rule'] for idea in self.open.values()}
                for rule in self.cx:
                    if rule['role'] == 'manager' or rule['id'] in active_names:
                        continue
                    side, missing = confirmation(rule, self.p, t)
                    if side:
                        signal = dict(rule=rule['id'], side=side, identity=self.p['position'],
                                      reason=rule['specification'].splitlines()[0][3:])
                        events.append(self.open_trade(signal, t, self.p))
                    elif missing:
                        events.append(self.event(rule['id'], 'not scored', 'not scored: the feed lacks ' +
                                                 ', '.join(sorted(set(missing))), t, None))
            self.p = t
        return events

    def stop(self, why, administrative=True):
        if self.last is None:
            return []
        return [self.close_trade(key, why, self.last, administrative) for key in list(self.open)]

