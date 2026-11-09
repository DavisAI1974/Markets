"""Verify and compare the four retained date applications without fitting again."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

from research_atlas_stack import ARMS

HERE=Path(__file__).resolve().parent
BASE=HERE/'replay-comparison'
DAYS=['20231002','20231003','20231017','20231018']


def main():
    metrics,conditions,populations,mechanisms,prebirth=[],[],[],[],[]
    checks={}
    for day in DAYS:
        root=BASE/day;out=root/'research-atlas-v2'
        summary=json.loads((root/'summary.json').read_text())
        f=pd.read_csv(out/'stack-features.csv.gz',dtype={'decision_ns':str,'quote_known_by_ns':str,'flow_closed_by_ns':str})
        summary['live_recognitions']=len(f)
        summary['unavailable_finalize_only']=summary['candidates']-len(f)
        assert f.candidate_id.is_unique
        for r in f[f.input_disposition=='available'].itertuples():
            assert int(r.quote_known_by_ns)<=int(r.decision_ns)
            assert int(r.flow_closed_by_ns)<=int(r.decision_ns)
        assert not any(c.startswith('future') for c in f.columns)
        predictions=pd.read_csv(out/'stack-predictions.csv.gz')
        for _,g in predictions.groupby(['target','horizon_s','fold']):
            sets={arm:set(v.candidate_id) for arm,v in g.groupby('arm')}
            assert set(sets)==set(ARMS)
            assert all(v==sets['baseline'] for v in sets.values())
        splits=pd.read_csv(out/'stack-splits.csv',dtype=str)
        for r in splits.itertuples():
            assert int(r.last_train_target_ns)+int(r.embargo_s)*10**9<int(r.test_start_ns)
        m=pd.read_csv(out/'stack-metrics.csv');m.insert(0,'day',day);metrics.append(m)
        s=pd.read_csv(out/'stack-conditional-states.csv')
        assert s.groupby('horizon_s').n.sum().to_dict()=={5:len(f),20:len(f),60:len(f)}
        assert (s.up+s.down+s.flat==s.available).all()
        s.insert(0,'day',day);conditions.append(s)
        cases=pd.read_csv(out/'prebirth-cases.csv.gz')
        assert len(cases)==summary['candidates']*4
        assert (cases.groupby('lead_s').size()==summary['candidates']).all()
        for lead,g in cases.groupby('lead_s'):
            prebirth.append(dict(day=day,lead_s=lead,n=len(g),available=int(g.input_disposition.eq('available').sum()),matched=int(g.matched.sum())))
        for state,count in summary['recognition_states'].items():
            populations.append(dict(day=day,scope=summary['scope'],state=state,n=count,total=summary['candidates']))
        for ending,count in summary['resting_endings'].items():
            mechanisms.append(dict(day=day,ending=ending,n=count,total=summary['resting_events']))
        checks[day]=dict(candidates=summary['candidates'],live_recognitions=len(f),
                         finalize_only_retained=summary['unavailable_finalize_only'],
                         identical_arms=True,causal_feature_clocks=True,purge_and_embargo=True,
                         conditional_denominators=True,all_prebirths_retained=True)
        (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')

    # Oct 18 is a regression oracle for the reused historical calculations.
    parity=[]
    for name in ['stack-features.csv.gz','stack-metrics.csv','stack-conditional-states.csv',
                 'dipole-operator-observations.csv.gz','aggression-to-rest-events.csv',
                 'resting-observation-summary.csv']:
        pd.testing.assert_frame_equal(pd.read_csv(HERE/'research-atlas-v2'/name),
                                     pd.read_csv(BASE/'20231018/research-atlas-v2'/name))
        parity.append(name)
    old=pd.read_csv(HERE/'research-atlas-v2/prebirth-cases.csv.gz')
    new=pd.read_csv(BASE/'20231018/research-atlas-v2/prebirth-cases.csv.gz')
    pd.testing.assert_frame_equal(old[old.population=='dipole_birth'].reset_index(drop=True),new[old.columns],check_dtype=False)
    parity.append('prebirth-cases.csv.gz (dipole population)')
    all_metrics=pd.concat(metrics,ignore_index=True)
    for name,data in [('metrics',all_metrics),('conditions',pd.concat(conditions,ignore_index=True)),
                      ('recognition-states',pd.DataFrame(populations)),('resting-mechanisms',pd.DataFrame(mechanisms)),
                      ('prebirth-coverage',pd.DataFrame(prebirth))]:
        data.to_csv(BASE/f'four-date-{name}.csv',index=False)
    (BASE/'verification.json').write_text(json.dumps(dict(date_checks=checks,october18_exact_reproduction=parity),indent=2)+'\n')
    pooled=all_metrics[all_metrics.fold==-1]
    rows=[]
    for day in DAYS:
        for arm in ['plus_book','full']:
            rows.append(pooled[(pooled.day==day)&(pooled.arm==arm)].set_index(['target','horizon_s']).mse_ratio_to_baseline)
    pairs=[('midpoint_ticks',h) for h in (5,20,60)]+[('absolute_ticks',h) for h in (5,20,60)]+[('flow_strength_change',20)]
    values=np.array([[100*(r.loc[p]-1) for p in pairs] for r in rows])
    fig,ax=plt.subplots(figsize=(12,6),layout='constrained')
    ax.imshow(values,cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-3,vcenter=0,vmax=115),aspect='auto')
    ax.set_xticks(range(7),['Price 5s','Price 20s','Price 60s','Magnitude 5s','Magnitude 20s','Magnitude 60s','Flow strength 20s'])
    ax.set_yticks(range(8),[f'Oct {int(d[-2:])}{" (partial)" if d in (DAYS[0],DAYS[2]) else ""} | {a}' for d in DAYS for a in ['+ book','full stack']])
    for i in range(8):
        for j in range(7):ax.text(j,i,f'{values[i,j]:+.1f}%',ha='center',va='center',color='white' if values[i,j]>65 or values[i,j]<-1.5 else '#172536')
    for i in (1.5,3.5,5.5):ax.axhline(i,color='white',linewidth=2)
    ax.set_title('The small five-second book improvement repeats; the full stack adds error',pad=16)
    fig.supxlabel('Change in mean squared error versus price-context baseline. Negative = lower error. Same fixed model, fitted separately within each discovery date.',fontsize=9)
    for ext in ('png','svg'):fig.savefig(BASE/f'four-date-stack-comparison.{ext}',dpi=160)
    svg=BASE/'four-date-stack-comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    print('Verified all four dates; exact October 18 reproduction:',len(parity),'tables')
    print(pooled[pooled.arm=='full'][['day','target','horizon_s','n','mse_ratio_to_baseline']].to_string(index=False))


if __name__=='__main__':main()
