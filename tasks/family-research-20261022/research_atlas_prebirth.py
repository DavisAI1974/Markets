"""Strict-prebirth case/control discovery from retained completed groups.

Retrospective case selection is not a prospective detector or a trading rule.
"""
import numpy as np
import pandas as pd

from flow_book_discovery import HERE, GROUPS, NS, REV, rows
from research_atlas import OUT, OPEN, CLOSE, group_matrix, save, dump


def strict_before(times, cutoff):
    return int(np.searchsorted(times, cutoff, side='left')) - 1


def features_at(a, cumulative, cutoff):
    j = strict_before(a[:, 0], cutoff)
    if j < 0 or not a[j, 7]:
        return None
    g = a[j]
    r = dict(decision_ns=int(cutoff), source_group=j, source_cursor=int(g[1]),
             source_known_by_ns=int(g[0]), quote_age_ns=int(cutoff-g[0]),
             spread_raw=int(g[4]-g[3]), touch_imbalance=(g[5]-g[6])/(g[5]+g[6]),
             displayed_lots=int(g[5]+g[6]))
    for seconds in (1, 5, 20):
        k = strict_before(a[:, 0], cutoff-seconds*NS)
        if k < 0 or not a[k, 7] or a[k, 8] != g[8]:
            return None
        buy, sell, unknown = cumulative[j+1]-cumulative[k+1]
        total = buy+sell
        r.update({f'buy{seconds}':int(buy), f'sell{seconds}':int(sell),
                  f'unknown{seconds}':int(unknown), f'total{seconds}':int(total),
                  f'flow{seconds}':(buy-sell)/total if total else np.nan,
                  f'mid_change{seconds}':(int(g[2])-int(a[k,2]))/(2*NS)})
        if seconds == 5:
            r['touch_change5'] = r['touch_imbalance']-(a[k,5]-a[k,6])/(a[k,5]+a[k,6])
    r['activity_bucket'] = int(np.floor(np.log2(1+r['total20'])))
    return r


def main(populations=None):
    groups = rows(GROUPS)
    a = group_matrix(groups)
    quantities = np.zeros((len(groups),3), dtype=np.int64)
    for i,g in enumerate(groups):
        for t in g['prints']:
            # Classification uses the immediately preceding completed quote;
            # availability is the containing completed group's close.
            if i == 0 or not a[i-1,7] or a[i-1,8] != a[i,8]:
                quantities[i,2] += t['size']; continue
            delta = 2*t['price_raw']-a[i-1,2]
            quantities[i,0 if delta>0 else 1 if delta<0 else 2] += t['size']
    cumulative = np.vstack([np.zeros(3,dtype=np.int64),np.cumsum(quantities,axis=0)])
    if populations is None:
        family = pd.read_csv(HERE/'flow-book-discovery-v1/opportunities.csv.gz',dtype={'anchor_ns':str})
        candidates = rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz')
        populations = {
            'family_start':[(str(r.instance),int(r.anchor_ns)) for r in family.itertuples()],
            'dipole_birth':[(r['candidate_id'],int(r['birth_second'])*NS) for r in candidates],
        }
    grid = []
    for t in range(OPEN+120*NS,CLOSE-60*NS,5*NS):
        f = features_at(a,cumulative,t)
        if f is not None: grid.append(f)
    grid = pd.DataFrame(grid)
    cases, pairs, summaries = [],[],[]
    measurements = ['touch_imbalance','displayed_lots','flow1','flow5','flow20',
                    'total1','total20','mid_change1','mid_change5','mid_change20','touch_change5']
    for population, births in populations.items():
        birth_times = np.sort([t for _,t in births])
        points = grid.decision_ns.to_numpy()
        # Control exclusion is retrospective outcome labeling, not a feature.
        lo = np.searchsorted(birth_times,points-60*NS,side='left')
        hi = np.searchsorted(birth_times,points+60*NS,side='right')
        controls = grid[lo==hi]
        for ident,birth in births:
            for lead in (1,5,20,60):
                f = features_at(a,cumulative,birth-lead*NS)
                if f is None:
                    cases.append(dict(population=population,case_id=ident,birth_ns=birth,lead_s=lead,
                                      decision_ns=birth-lead*NS,input_disposition='boundary_or_invalid',matched=False))
                    continue
                case = dict(population=population,case_id=ident,birth_ns=birth,lead_s=lead,
                            input_disposition='available',**f)
                case['matched'] = False
                possible = controls[(controls.decision_ns < f['decision_ns']) &
                                    (controls.decision_ns >= f['decision_ns']-1800*NS) &
                                    controls.spread_raw.eq(f['spread_raw']) &
                                    controls.activity_bucket.eq(f['activity_bucket'])]
                if len(possible):
                    c = possible.iloc[-1]
                    case['matched'] = True
                    for name in measurements:
                        pairs.append(dict(population=population,case_id=ident,lead_s=lead,
                                          quarter=int((birth-OPEN)*4//(CLOSE-OPEN))+1,
                                          case_decision_ns=f['decision_ns'],
                                          control_decision_ns=int(c.decision_ns),
                                          feature=name,case_value=f[name],control_value=c[name],
                                          difference=f[name]-c[name]))
                cases.append(case)
        save(f'prebirth-{population}-control-grid.csv.gz',controls)
    paired = pd.DataFrame(pairs)
    for keys,g in paired.groupby(['population','lead_s','quarter','feature']):
        v = g.dropna(subset=['difference'])
        summaries.append(dict(zip(['population','lead_s','quarter','feature'],keys),
                              matched_pairs=len(g),defined_pairs=len(v),
                              unique_controls=g.control_decision_ns.nunique(),
                              case_mean=v.case_value.mean(),control_mean=v.control_value.mean(),
                              mean_difference=v.difference.mean(),median_difference=v.difference.median(),
                              greater=int((v.difference>0).sum()),equal=int((v.difference==0).sum()),
                              less=int((v.difference<0).sum())))
    case_frame = pd.DataFrame(cases)
    for column in case_frame:
        if column.endswith(('_ns','_cursor','_group')):
            case_frame[column] = [str(r[column]) if column in r else '' for r in cases]
    save('prebirth-cases.csv.gz',case_frame)
    save('prebirth-matched-pairs.csv.gz',paired)
    save('prebirth-summary.csv',summaries)
    dump('prebirth-method.json',dict(source_revision=REV,source_groups=GROUPS,
         source_family='f0bd88e1728668ae3fc9bdd5f62921f9d89fcd13:flow-book-discovery-v1/opportunities.csv.gz',
         birth_definitions={'family_start':'Recorded family start receive clock; not an executed trade.',
                            'dipole_birth':'Recorded birth second start; retrospective signal location, not actual recognition.'},
         leads_s=[1,5,20,60],lookbacks_s=[1,5,20],
         availability='Strictly earlier completed groups than the decision cutoff, itself earlier than birth. No birth polarity, later threshold, final disposition or future movement in features.',
         control='Latest earlier five-second grid point within 30 minutes with same exact spread and floor(log2(1+classified lots20)); no recorded birth of this population within plus/minus 60 seconds.',
         limitations=['Controls may be reused; report unique controls. Pairs and leads overlap.',
                      'Control exclusion uses future labels retrospectively. It is not an online eligibility rule.',
                      'Matching may fail; retain unmatched case rows. No learned thresholds or test-set claims.',
                      'One discovery date; selected births do not exhaust market opportunities.',
                      'Only touch depth is in this input; deeper depth, order-ID turnover and external precursors remain pending.',
                      'This compares upcoming setup births, not future profitable trades or execution.']))
    print(pd.DataFrame(cases).groupby(['population','lead_s']).matched.agg(['size','sum']).to_string())


if __name__ == '__main__':
    main()
