"""Scientific figures and reviewed interactive chart configurations."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from flow_book_discovery import HERE, GROUPS, rows, NS
from research_atlas import OUT, group_matrix, save, dump

V1 = HERE/'flow-book-discovery-v1'
FIG = OUT/'figures'
COLORS = {'with':'#0072B2', 'against':'#D55E00', 'flat':'#999999', 'censored':'#CC79A7'}


def finish(fig, name):
    fig.savefig(FIG/f'{name}.png', dpi=155, bbox_inches='tight')
    fig.savefig(FIG/f'{name}.svg', bbox_inches='tight')
    svg = FIG/f'{name}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)


def draw_overview():
    f = pd.read_csv(OUT/'rolling-flow-date-summary.csv')
    e = pd.read_csv(OUT/'aggression-to-rest-events.csv')
    d = pd.read_csv(OUT/'resting-observation-decisions.csv.gz')
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout='constrained')
    fig.suptitle('NG discovery: the signal changes, and the opportunity changes', fontsize=20, ha='left', x=.02)
    ax=axes[0,0]
    for i,r in enumerate(f.itertuples()):
        age=r.age_only_direction_flips/r.direction_flips
        ax.barh(i,age,color=COLORS['against'],label='No fresh classified lots' if i==0 else None)
        ax.barh(i,1-age,left=age,color=COLORS['with'],label='Fresh classified lots present' if i==0 else None)
        ax.text(age/2,i,f'{r.age_only_direction_flips:,}\n{age:.1%}',ha='center',va='center',color='white')
        ax.text(age+(1-age)/2,i,f'{r.direction_flips-r.age_only_direction_flips:,}',ha='center',va='center',color='white')
    ax.set_yticks(range(3),['Oct 2 · partial','Oct 17 · partial','Oct 18 · full'])
    ax.set_xlim(0,1);ax.set_xlabel('Share of rolling-flow direction flips')
    ax.set_title('Aging alone can reverse the rolling signal',loc='left')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=1,frameon=False,fontsize=10)
    ax=axes[0,1]
    counts=e.end_kind.value_counts().reindex(['fill_linked_clear','unmatched_clear','reprice','reset_censored','session_end_censored']).fillna(0)
    ax.barh(range(5),counts,color=[COLORS['with'],COLORS['against'],'#009E73',COLORS['censored'],COLORS['censored']])
    ax.set_yticks(range(5),['Fill-linked clear','Unmatched final clear','Reprice','Reset censored','Session-end censored'])
    for i,v in enumerate(counts):ax.text(v+7,i,str(int(v)),va='center')
    ax.set_xlim(0,700);ax.invert_yaxis();ax.set_xlabel('Events · 980 total')
    ax.set_title('Aggression becomes resting liquidity',loc='left')
    ax=axes[1,0]
    x=d.groupby('delay_ms').eligible.agg(['size','sum'])
    ax.plot(x.index,x['sum']/x['size'],marker='o',color=COLORS['with'])
    for delay,r in x.iterrows():ax.annotate(f"{int(r['sum'])}/980",(delay,r['sum']/r['size']),xytext=(8,8),textcoords='offset points')
    ax.set_ylim(0,1.15);ax.set_xlim(-5,120);ax.set_xlabel('Observation delay after recognition (ms)')
    ax.set_ylabel('Share still resting');ax.set_title('The eligible cohort shrinks quickly',loc='left')
    ax=axes[1,1]
    s=pd.read_csv(V1/'setup-crosstabs.csv')
    s=s[(s.setup=='original50')&(s.horizon_s==1)]
    for i,r in enumerate(s.itertuples()):
        left=0
        for key,color in [('with_recent_flow',COLORS['with']),('flat',COLORS['flat']),('against_recent_flow',COLORS['against'])]:
            value=getattr(r,key)
            ax.barh(i,value/r.n,left=left,color=color)
            if value:ax.text(left+value/r.n/2,i,str(value),ha='center',va='center',color='white')
            left+=value/r.n
    ax.set_yticks(range(3),['Touch aligned · n=21','Equal touch · n=5','Touch opposed · n=24'])
    ax.set_xlabel('1-second outcome: with selling / flat / against selling')
    ax.set_xlim(0,1);ax.set_title('Whole-book sign hides local differences',loc='left')
    for ax in axes.flat:
        ax.spines[['top','right']].set_visible(False)
    fig.supxlabel('Historical discovery only · rolling seconds and nearby events overlap · final removal is a later outcome',fontsize=11)
    finish(fig,'mechanism-overview')


def draw_case(groups):
    actions=pd.read_csv(OUT/'aggression-to-rest-actions.csv.gz')
    e=pd.read_csv(OUT/'aggression-to-rest-events.csv')
    event=e[e.order_id.eq(788701345922)].iloc[0]
    a=actions[actions.event_id.eq(event.event_id)].copy()
    a=a.drop_duplicates('group_known_by_ns',keep='last')
    t=int(event.start_known_by_ns)
    x=np.r_[0,(a.group_known_by_ns.to_numpy(dtype=np.int64)-t)/1e6]
    qty=np.r_[150,a.displayed_after.to_numpy()]
    fill=np.r_[0,a.cumulative_passive_fills.to_numpy()]
    g=groups[(groups[:,0]>=t-30_000_000)&(groups[:,0]<=t+350_000_000)]
    fig,axes=plt.subplots(3,1,figsize=(14,9),sharex=True,layout='constrained')
    fig.suptitle('Case 391: one order changes from aggressor to resting liquidity',fontsize=20,x=.02,ha='left')
    axes[0].step(x,qty,where='post',color=COLORS['against']);axes[0].set_ylabel('Displayed offer (lots)')
    axes[0].annotate('150-lot offer added after\n50 lots in trade summaries',(0,150),xytext=(35,135),arrowprops={'arrowstyle':'->','color':'#555555'})
    axes[1].step(x,fill,where='post',color=COLORS['with']);axes[1].set_ylabel('Cumulative passive fills (lots)')
    axes[1].annotate('150 passive lots filled;\nfinal removal is linked to a fill',(204.026301,150),xytext=(225,90),arrowprops={'arrowstyle':'->','color':'#555555'})
    gx=(g[:,0]-t)/1e6
    axes[2].step(gx,g[:,3]/NS,where='post',label='Bid',color=COLORS['with'])
    axes[2].step(gx,g[:,4]/NS,where='post',label='Ask',color=COLORS['against'])
    axes[2].set_ylabel('Quoted price');axes[2].set_xlabel('Milliseconds from family-group close / remainder recognition')
    axes[2].legend(frameon=False,loc='upper right')
    for ax in axes:
        ax.axvline(0,color='#777777',lw=1,ls=':');ax.axvline(204.026301,color='#777777',lw=1,ls=':')
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15)
    axes[-1].set_xlim(-30,350)
    fig.supxlabel('Order 788701345922 · initial group G244934 / cursor 319233 · final offer-clear group G245219 / cursor 319629\nThe 150-lot remainder is the largest of 980 detected events; this path is not representative of every case.',fontsize=11)
    finish(fig,'case-391-order-path')


def draw_landscape():
    e=pd.read_csv(OUT/'aggression-to-rest-events.csv')
    fig,axes=plt.subplots(1,2,figsize=(14,6),layout='constrained')
    fig.suptitle('Aggression-to-rest: many short events, several different endings',fontsize=19,x=.02,ha='left')
    mapping=[('fill_linked_clear','Fill-linked clear',COLORS['with']),('unmatched_clear','Unmatched clear',COLORS['against']),('reprice','Reprice','#009E73')]
    for kind,label,color in mapping:
        x=e[e.end_kind.eq(kind)]
        axes[0].scatter(x.initial_display,x.duration_from_start_close_ns/1e6,s=20,alpha=.45,label=f'{label} · n={len(x)}',color=color)
        values=np.sort(x.duration_from_start_close_ns/1e6)
        axes[1].step(values,np.arange(1,len(values)+1)/len(values),where='post',color=color,label=label)
    r=e[e.order_id.eq(788701345922)].iloc[0]
    axes[0].annotate('391: 150 lots, 204 ms',(r.initial_display,r.duration_from_start_close_ns/1e6),xytext=(12,1500),arrowprops={'arrowstyle':'->','color':'#555555'})
    axes[0].set(xscale='log',yscale='log',xlabel='Initial displayed lots (log scale)',ylabel='Lifetime from recognition (ms, log scale)')
    axes[1].set(xscale='log',xlabel='Lifetime from recognition (ms, log scale)',ylabel='Fraction of observed endings')
    axes[0].legend(frameon=False,fontsize=10,loc='lower right')
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
    fig.supxlabel('978 observed endings; 2 censored events excluded from lifetime curves · final end types are hindsight labels',fontsize=11)
    finish(fig,'resting-event-landscape')


def draw_ablation():
    m=pd.read_csv(V1/'arm-metrics.csv')
    pivot=m.pivot(index=['target','fold','horizon_s'],columns='arm',values='mae')
    figs,axes=plt.subplots(1,2,figsize=(14,7),layout='constrained')
    figs.suptitle('A useful layer must add information beyond the same baseline',fontsize=19,x=.02,ha='left')
    for ax,target,title in zip(axes,['signed','absolute'],['Signed midpoint change','Absolute midpoint change']):
        matrix=[];labels=[]
        for fold in (1,2,3):
            for arm in ('flow','book','both'):
                g=pivot.loc[(target,fold)]
                matrix.append((100*(g[arm]/g.baseline-1)).to_numpy());labels.append(f'{arm.capitalize()} · fold {fold}')
        matrix=np.array(matrix)
        im=ax.imshow(matrix,cmap='RdBu_r',vmin=-35,vmax=35,aspect='auto')
        for i,j in np.ndindex(matrix.shape):ax.text(j,i,f'{matrix[i,j]:+.1f}%',ha='center',va='center',fontsize=10,color='white' if abs(matrix[i,j])>21 else '#222222')
        ax.set_yticks(range(9),labels);ax.set_xticks(range(5),['1','5','20','60','300']);ax.set_xlabel('Outcome horizon (seconds)');ax.set_title(title,loc='left')
    figs.colorbar(im,ax=axes,label='MAE change vs baseline (%) · negative improves / positive worsens',shrink=.8)
    figs.supxlabel('Same opportunities and targets in four arms · training-only preprocessing · 600-second embargo · single-day discovery',fontsize=11)
    finish(figs,'four-arm-stability')


def draw_relationships():
    r=pd.read_csv(V1/'all-field-relationships.csv.gz')
    fields={'root.activity.1.trade_aggressor_imbalance':'1 s signed flow',
            'root.activity.60.trade_aggressor_imbalance':'60 s signed flow',
            'root.depth_imbalance_full':'Full-depth imbalance',
            'root.depth_imbalance_n':'Near-depth imbalance',
            'second_group.far_size_retention_64':'Far size retention',
            'second_group.far_identity_survival_64':'Far identity survival'}
    subs=['all','original50','quarter1','quarter2','quarter3','quarter4']
    fig,axes=plt.subplots(1,2,figsize=(15,6),layout='constrained')
    fig.suptitle('Relationships change with the question and the cohort',fontsize=19,x=.02,ha='left')
    for ax,target,title in zip(axes,['future_signed_1s','future_absolute_20s'],['Next 1-second signed move','Next 20-second absolute move']):
        g=r[r.target.eq(target)&r.feature.isin(fields)].set_index(['feature','subset'])
        data=np.array([[g.at[(f,s),'spearman'] for s in subs] for f in fields])
        im=ax.imshow(data,cmap='RdBu',vmin=-.5,vmax=.5,aspect='auto')
        for i,f in enumerate(fields):
            for j,s in enumerate(subs):
                ax.text(j,i,f'{data[i,j]:+.2f}\nn={int(g.at[(f,s),"n"])}',ha='center',va='center',fontsize=9,color='white' if abs(data[i,j])>.32 else '#222222')
        ax.set_yticks(range(len(fields)),list(fields.values()));ax.set_xticks(range(6),['All','Original 50','Q1','Q2','Q3','Q4'],rotation=30,ha='right');ax.set_title(title,loc='left')
    fig.colorbar(im,ax=axes,label='Descriptive Spearman correlation',shrink=.85)
    fig.supxlabel('Selected view of 14,784 retained comparisons · overlapping observations · no significance or independent validation claim',fontsize=11)
    finish(fig,'relationship-context-map')


def build_configs():
    candidate=rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz')
    metadata={r['candidate_id']:r for r in candidate}
    dipoles=pd.read_csv(V1/'dipole-after-recognition.csv.gz')
    events=pd.read_csv(OUT/'aggression-to-rest-events.csv')
    outcomes=pd.read_csv(OUT/'aggression-to-rest-outcomes.csv.gz')
    op=pd.read_csv(V1/'opportunities.csv.gz')
    family_out=pd.read_csv(V1/'outcomes.csv.gz')
    state_names={'same_direction_at_emission':'Flow persists','opposite_direction_at_emission':'Flow reverses',
                 'balanced_at_emission':'Flow balances','undefined_at_emission':'No classified volume'}
    configs={}
    for h in (1,5,20,60,300):
        paths=[]
        for r in dipoles[dipoles.horizon_s.eq(h)].itertuples():
            c=metadata[r.candidate_id]
            direction=r.change*r.birth_polarity
            later='Unavailable' if r.disposition!='available' else 'With birth direction' if direction>0 else 'Against birth direction' if direction<0 else 'Flat midpoint'
            paths.append(['Fresh print at birth' if c['birth_fresh'].get('prints',0) else 'No fresh print at birth',state_names[r.flow_state],later])
        count=pd.DataFrame(paths,columns=['Birth','Recognition','Later']).value_counts().reset_index(name='count')
        configs[f'dipole-{h}-all']=dict(id='ng-research-atlas',title=f'Dipole pathways · {h} seconds after actual recognition',
                                      description='863 selected recognitions. Birth prints → flow at recognition → later midpoint. Widths count cases; flat and unavailable outcomes remain visible.',
                                      height=440,spec=dict(type='sankey',stages=['Birth','Recognition','Later'],value='count'),
                                      rows=count.to_dict('records'))
        m=outcomes[(outcomes.anchor=='start_close')&outcomes.horizon_s.eq(h)].merge(events,on='event_id')
        m['Initial execution']=np.where(m.initial_trade_price_count>1,'Multiple trade prices','One trade price')
        m['Eventual resting fate']=m.end_kind.map({'fill_linked_clear':'Fill-linked clear','unmatched_clear':'Unmatched final clear','reprice':'Reprice','reset_censored':'Censored','session_end_censored':'Censored'})
        m['Later midpoint']=np.where(m.disposition!='available','Unavailable',np.where(m.direction_oriented_change>0,'With original aggression',np.where(m.direction_oriented_change<0,'Against original aggression','Flat midpoint')))
        cols=['Initial execution','Eventual resting fate','Later midpoint']
        c=m.groupby(cols).size().reset_index(name='count')
        configs[f'resting-{h}-all']=dict(id='ng-research-atlas',title=f'Aggression-to-rest pathways · {h}-second midpoint outcome',
                                       description='980 events. Eventual removal is hindsight, not a birth-time predictor. Outcomes begin at the initial completed group; widths count events.',
                                       height=440,spec=dict(type='sankey',stages=cols,value='count'),rows=c.to_dict('records'))
        m=op.merge(family_out[family_out.horizon_s.eq(h)],on='instance')
        for scope in ('all','original'):
            g=m[m.four_arm_eligible].copy()
            if scope=='original':g=g[g.cohort.eq('original')]
            g['Outcome']=np.where(g.outcome_disposition!='available','Unavailable',np.where(g.change>0,'Up',np.where(g.change<0,'Down','Flat')))
            points=[dict(flow=float(r.flow1),touch=float(r.touch_imbalance),Outcome=r.Outcome,
                         name=f'Case {r.instance} · {r.start_utc} · change {r.change:+.4f}' if r.outcome_disposition=='available' else f'Case {r.instance} · unavailable outcome') for r in g.itertuples()]
            configs[f'family-{h}-{scope}']=dict(id='ng-research-atlas',title=f'Flow and touch depth · {h}-second outcome',
                                              description=f'{len(g)} family-selected opportunities. Every full book was bid-heavy; local touch varies. Coincident points remain inspectable in the grouped tooltip.',
                                              height=440,spec=dict(type='scatter',x='flow',y='touch',series='Outcome',
                                                                   xLabel='Prior 1-second signed flow ratio',yLabel='Prior touch imbalance',xDomain=[-1,1],yDomain=[-1,1],
                                                                   colors={'Up':'var(--chart-1)','Down':'var(--chart-2)','Flat':'var(--secondary)','Unavailable':'var(--chart-4)'}),rows=points)
    dump('interactive-configs.json',configs)
    return configs


def main():
    FIG.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'svg.fonttype':'none'})
    draw_overview();draw_case(group_matrix(rows(GROUPS)));draw_landscape();draw_ablation();draw_relationships()
    c=build_configs()
    print('Saved 5 PNG/SVG figures and',len(c),'interactive states.')


if __name__=='__main__':
    main()
