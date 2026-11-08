"""Observation-clock study of surviving aggression-to-rest events, not execution."""
import numpy as np
import pandas as pd

from flow_book_discovery import GROUPS, NS, rows
from research_atlas import OUT, group_matrix, save, dump


def main():
    groups = group_matrix(rows(GROUPS))
    events = pd.read_csv(OUT/'aggression-to-rest-events.csv')
    actions = pd.read_csv(OUT/'aggression-to-rest-actions.csv.gz')
    by_event = {key: g.sort_values('cursor') for key, g in actions.groupby('event_id')}
    decisions, results = [], []
    for e in events.itertuples():
        action = by_event.get(e.event_id, pd.DataFrame())
        for delay_ms in (0, 5, 25, 100):
            decision = int(e.start_known_by_ns) + delay_ms * 1_000_000
            gi = int(np.searchsorted(groups[:, 0], decision, side='right')) - 1
            alive = e.end_known_by_ns > decision
            row = dict(event_id=e.event_id, order_id=e.order_id, side=e.side, direction=e.direction,
                       delay_ms=delay_ms, decision_cutoff_ns=decision, quote_group=gi,
                       quote_cursor=int(groups[gi, 1]), quote_receive_ns=int(groups[gi, 0]),
                       quote_age_ns=decision-int(groups[gi, 0]), eligible=bool(alive),
                       initial_display=e.initial_display, initial_trade_lots=e.initial_trade_lots,
                       initial_trade_price_count=e.initial_trade_price_count,
                       fills_known=0, display_known=e.size_at_start_close,
                       last_action_cursor=e.add_cursor, last_action_known_by_ns=e.start_known_by_ns)
            if len(action):
                known = action[action.group_known_by_ns <= decision]
                if len(known):
                    last = known.iloc[-1]
                    row.update(fills_known=int(last.cumulative_passive_fills), display_known=int(last.displayed_after),
                               last_action_cursor=int(last.cursor), last_action_known_by_ns=int(last.group_known_by_ns))
            quote_price = groups[gi, 3] if e.side == 'B' else groups[gi, 4]
            row['at_touch'] = bool(e.resting_price_raw == quote_price)
            row['fill_fraction_known'] = row['fills_known']/e.initial_display
            row['fill_state'] = 'some_passive_fills' if row['fills_known'] else 'no_passive_fills_yet'
            decisions.append(row)
            if not alive:
                continue
            for h in (.1, 1, 5, 20):
                target = decision + round(h * NS)
                end = int(np.searchsorted(groups[:, 0], target, side='right')) - 1
                valid = target <= groups[-1, 0] and groups[gi, 7] and groups[end, 7] and groups[gi, 8] == groups[end, 8]
                change = (int(groups[end, 2])-int(groups[gi, 2]))/(2*NS)*e.direction
                results.append(dict(**row, horizon_s=h, endpoint_group=end, endpoint_cursor=int(groups[end, 1]),
                                    endpoint_receive_ns=int(groups[end, 0]), target_ns=target,
                                    disposition='available' if valid else 'censored_or_boundary',
                                    direction_oriented_change=change if valid else None))
    save('resting-observation-decisions.csv.gz', decisions)
    save('resting-observation-outcomes.csv.gz', results)
    summaries = []
    result = pd.DataFrame(results)
    for (delay, h, side, state, touch), g in result.groupby(['delay_ms','horizon_s','side','fill_state','at_touch']):
        v = g[g.disposition.eq('available')].direction_oriented_change
        summaries.append(dict(delay_ms=delay, horizon_s=h, side=side, fill_state=state, at_touch=touch,
                              n=len(g), available=len(v), continuation=int((v>0).sum()), reversal=int((v<0).sum()),
                              flat=int((v==0).sum()), mean=v.mean(), median=v.median()))
    save('resting-observation-summary.csv', summaries)
    dump('observation-method.json', dict(version='NG-RESTING-OBSERVATION-v1',
                                         delays_ms=[0,5,25,100], horizons_s=[.1,1,5,20],
                                         decision='Timer after initial completed-group recognition; state and quote use only completed groups at or before that timer.',
                                         eligibility='Original order still present at the decision; identity may have moved away from the touch. Endpoint availability separately recorded.',
                                         prohibited_inference='This is an observation schedule, not order placement, processing latency or fill simulation.',
                                         limitations=['Survival cohorts change with delay; denominator selection is explicit.',
                                                      'Some fills and final disposition observed later cannot be used at an earlier decision.',
                                                      'Same-day overlapping events and repeated observations are dependent.',
                                                      'No cost-adjusted return or scoring admission.']))
    print(pd.DataFrame(decisions).groupby('delay_ms').eligible.agg(['count','sum']).to_string())


if __name__ == '__main__':
    main()
