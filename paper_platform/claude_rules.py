"""CL rule signals. An event may arm a rule inside the event; only its end can confirm entry."""
from collections import deque

from databento_dbn import F_LAST
from root.calcs.quote_runs import FURTHER, STARTED, STEP_BACK


def sign(value):
    return 0 if value is None else (value > 0) - (value < 0)


class ClaudeRules:
    def __init__(self):
        self.pending = []
        self.runs = {}
        self.ended = {'bid': deque(maxlen=2), 'ask': deque(maxlen=2)}
        self.levels = {}
        self.hump = None
        self.together = {}
        self.pair_start = None
        self.leg = None
        self.stretch = None
        self.reload_seen = set()
        self.gone = set()
        self.emitted = set()
        self.trades = set()
        self.fill_prices = set()
        self.previous_quotes = {}
        self.last_print = None

    def arm(self, rule, direction, identity, reason, **conditions):
        self.pending.append(dict(rule=rule, side='buy' if direction > 0 else 'sell',
                                 identity=identity, reason=reason, conditions=conditions))

    def active(self, c, tick):
        name = c.get('quote')
        run = self.runs.get(name)
        if 'run' in c and (not run or run['start'] != c['run'] or run['moves'] > c.get('max_steps', float('inf'))):
            return False
        if 'leg' in c and c['leg'] != self.leg:
            return False
        if 'hump' in c and (self.hump is None or self.hump['start'] != c['hump']):
            return False
        if 'level' in c and (name not in self.levels or self.levels[name]['start'] != c['level']
                             or self.levels[name]['disturbed']):
            return False
        if 'order' in c and c['order'] in self.gone:
            return False
        if 'pair' in c and c['pair'] != self.pair_start:
            return False
        return True

    def at(self, m, t):
        raw = m['raw']
        action, pos, event = raw['action'], t['position'], t['event']
        if t['trade']:
            self.trades.add(t['aggressor'])
        if action == 'F':
            self.fill_prices.add(raw['price'])
        # An exchange fill names a resting order. Its subsequent update or removal moves the book.
        old, new, filled = (m['order_change'][k] for k in ('old', 'new', 'filled_in_event'))
        oid = raw['order_id']
        self.gone = {key for key in self.gone if any(p['conditions'].get('order') == key for p in self.pending)}
        if old and new is None:
            self.gone.add((oid, old[3]))
        previous_cohorts = {}
        for name, tag, direction in [('bid', 'B', -1), ('ask', 'A', 1)]:
            previous = self.previous_quotes.get(name)
            level = self.levels.get(name)
            if level and old and old[2] == tag and old[0] == previous:
                if action == 'F':
                    level['hit'] = True
                if action in ('M', 'C'):
                    if new is None or new[0] != old[0]:
                        if oid in level['cohort']:
                            level['cohort'].remove(oid)
                            level['departures'].add('fill' if filled and new is None else 'pull')
                    if new and (new[0] != old[0] or new[1] > old[1]) or not filled and (not new or new[1] != old[1]):
                        level['disturbed'] = True
                    if filled and new and new[0] == old[0] and new[1] >= old[1]:
                        key = (oid, old[3])
                        if key not in self.reload_seen:
                            self.reload_seen.add(key)
                            self.arm('CL12', -direction, (pos, oid), 'first same-size or larger reload',
                                     order=key, quote=name, price=old[0])
            if level and action in ('A','M') and new and new[2] == tag and new[0] == previous and (not old or old[0] != new[0]):
                level['disturbed'] = True
            if level and level['hit'] and not level['disturbed'] and t[name] == previous:
                key = (name, level['start'])
                if not level['armed']:
                    self.arm('CL04', direction, key, 'only fills at the standing best', quote=name, level=level['start'])
                    level['armed'] = True
            if t[name] != previous:
                previous_cohorts[name] = level
                visible = m['entered_levels'].get(tag)
                self.levels[name] = dict(start=pos, cohort=set(visible or ()), known=bool(visible),
                                         hit=False, disturbed=False, armed=False, departures=set())

        before = sign(t['exhaustion_before'])
        after = sign(t['exhaustion'])
        if self.hump and before != self.hump['direction']:
            self.hump = None
        if not self.hump or self.hump['direction'] != after:
            self.hump = None
            if after and before != after and t['trade'] and t['aggressor']:
                self.hump = dict(start=pos, direction=after, event=event,
                                 opposite=sign(t['dipole_before']) == -after)
                if sign(t['dipole_before']) == after:
                    self.arm('CL07', after, pos, 'trade began a hump on the prior dipole side', hump=pos)
        if t['trade']:
            price = t['price']
            leg = t['leg'][0]
            if leg != self.leg and leg is not None and self.stretch:
                direction = 1 if t['leg'][1] == 'up' else -1
                if after == direction and self.stretch != (t['bid'], t['ask']):
                    self.arm('CL05', direction, leg, 'first print step with a quote change and same-side exhaustion', leg=leg)
            self.leg = leg
            if price != self.last_print:
                self.stretch = (t['bid'], t['ask'])
                self.last_print = price

        for fact in t['quote_facts']:
            name = fact['quote'].split()[-1]
            direction = 1 if fact['direction'] == 'up' else -1
            moves, start = fact['moves'], fact['run_start_position']
            if fact['fact'] == STEP_BACK:
                self.ended[name].append((direction, moves))
                continue
            self.runs[name] = dict(start=start, moves=moves, direction=direction, last=pos, tested=False)
            identity = (name, start)
            common = dict(quote=name, run=start)
            outward = (name == 'ask') == (direction > 0)
            if moves == 1 and outward and old and old[0] == fact['price_before_tick'] and new is None:
                if filled:
                    self.arm('CL03', direction, identity, 'first step on removal by fill', require_side=direction, **common)
                elif action == 'C':
                    self.arm('CL09', -direction, identity, 'first step on cancellation without a trade', no_trade=True,
                             max_steps=1, **common)
            if moves == 2:
                cohort = previous_cohorts.get(name)
                if outward and cohort and cohort['known'] and not cohort['cohort']:
                    if cohort['departures'] == {'fill'}:
                        self.arm('CL01', direction, identity, 'every initial order at the first level left by fill', **common)
                    if cohort['departures'] == {'pull'}:
                        self.arm('CL02', -direction, identity, 'every initial order at the first level was pulled',
                                 max_steps=2, **common)
                if sign(t['dipole']) == -direction:
                    self.arm('CL10', direction, identity, 'second quote step against dipole', **common)
                    self.arm('CL11', -direction, identity, 'fade second quote step against dipole', max_steps=2, **common)
            if moves == 1 and list(self.ended[name]) and len(self.ended[name]) == 2:
                first, back = self.ended[name]
                if first[0] == direction and first[1] >= 2 and back == (-direction, 1):
                    self.arm('CL15', direction, identity, 'return after one step back', **common)
            if self.hump and self.hump['opposite'] and outward and self.hump['direction'] == direction and event != self.hump['event']:
                self.arm('CL08', direction, self.hump['start'], 'later quote step confirms a trade-born opposing hump',
                         hump=self.hump['start'], **common)
            if any(v != direction for v in self.together.values()):
                self.together.clear()
                self.pair_start = None
            self.together[name] = direction
            if len(self.together) == 2 and self.pair_start is None and t['ask'] > t['bid']:
                self.pair_start = pos
                self.arm('CL06', direction, pos, 'both quotes stepped in the same direction', pair=pos)

        if t['trade']:
            for name, side, direction in [('bid','A',1),('ask','B',-1)]:
                run = self.runs.get(name)
                if run and run['direction'] == direction and not run['tested'] and t['aggressor'] == side:
                    run['tested'] = True
                    if t['price'] == t[name]:
                        self.arm('CL14', -direction, (name, run['last']), 'first opposing print at latest step',
                                 quote=name, run=run['start'], max_steps=run['moves'])
        self.previous_quotes = {'bid':t['bid'], 'ask':t['ask']}
        if not raw['flags'] & F_LAST:
            return []
        if len(self.fill_prices) > 1 and self.trades in ({'B'}, {'A'}):
            direction = 1 if self.trades == {'B'} else -1
            self.arm('CL13', direction, event, 'one aggressor side filled multiple levels in the exchange event',
                     quote='ask' if direction > 0 else 'bid')
        confirmed = []
        for item in self.pending:
            c = item['conditions']
            key = (item['rule'], item['identity'])
            if key in self.emitted or not self.active(c, t) or t['settlement']:
                continue
            if c.get('no_trade') and self.trades:
                continue
            if 'require_side' in c and ('B' if c['require_side'] == 1 else 'A') not in self.trades:
                continue
            self.emitted.add(key)
            confirmed.append(item)
        self.pending.clear()
        self.trades.clear()
        self.fill_prices.clear()
        return confirmed

    def close(self, idea, m, t):
        c = idea['conditions']
        name = c.get('quote')
        rule = idea['rule']
        if rule == 'CL04':
            if 'run' in c:
                return None if self.active({'quote':name, 'run':c['run']}, t) else 'first step back after level gave'
            level = self.levels.get(name)
            if level and level['start'] == c['level']:
                return 'standing level disturbed' if level['disturbed'] else None
            run = self.runs.get(name)
            if run and run['direction'] == (1 if name == 'ask' else -1):
                c['run'] = run['start']
                return None
            return 'better quote stepped in front'
        if rule == 'CL12':
            change = m['order_change']
            old = change['old']
            if old and (m['raw']['order_id'],old[3]) == c['order'] and not change['new']:
                return 'reloaded order left by fill' if change['filled_in_event'] else 'reloaded order cancelled'
            for fact in t['quote_facts']:
                if fact['fact'] != STEP_BACK and fact['direction'] == ('down' if name == 'ask' else 'up'):
                    return 'quote stepped away from reload'
            if t[name] is not None and (t[name] - c['price']) * (1 if name == 'ask' else -1) > 0:
                return 'quote stepped through reloaded level'
            return None
        if rule == 'CL13':
            for f in t['quote_facts']:
                if f['quote'] == 'best ' + name and f['fact'] != STEP_BACK and f['direction'] == ('down' if name=='ask' else 'up'):
                    return 'swept quote stepped back'
            return None
        return None if self.active(c, t) else 'written close condition reached: ' + rule

