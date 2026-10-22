"""Render the completed descriptive results; no inference or invented error bars."""
import csv,gzip,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/'enriched-v2'
def rows(name):
    f=P/(name+'.csv')
    return list(csv.DictReader(f.open() if f.exists() else gzip.open(str(f)+'.gz','rt')))
q=rows('quote_trade_summary');d=rows('direction_freshness_sensitivity')
over=rows('overlap_summary');stable=rows('association_stability')
fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
colors={'up':'#a34032','down':'#206d9a'}
for direction in ['up','down']:
    r=sorted([r for r in q if r['phase']=='onset' and r['chronological_quarter']=='0' and r['max_endpoint_age_s']=='5.0' and r['pre_direction']==direction],key=lambda r:int(r['horizon_s']))
    x=[int(r['horizon_s']) for r in r]
    for field,style,label in [('mean_mid_change','-','midquote'),('mean_trade_change','--','trade')]:
        axes[0,0].plot(x,[float(a[field]) for a in r],style,color=colors[direction],label=f'Prior {direction}: {label}')
axes[0,0].set_xscale('log');axes[0,0].axhline(0,color='#888',linewidth=.7)
axes[0,0].set(title='Matched fresh quote/trade price changes',xlabel='Seconds after first-observed family start',ylabel='Mean change in source price units')
axes[0,0].legend(fontsize=8);axes[0,0].grid(alpha=.2)
selected=[next(r for r in d if r['phase']=='onset' and r['horizon_s']=='120' and r['pre_direction']==direction and r['sensitivity']=='pre_and_future_endpoints_fresh') for direction in ['up','down']]
bottom=[0,0]
for key,label,color in [('up_n','Later rise','#3e8e60'),('down_n','Later decline','#b76154'),('flat_n','Flat','#999')]:
    values=[int(r[key]) for r in selected]
    axes[0,1].bar(['Prior upward move','Prior downward move'],values,bottom=bottom,label=label,color=color)
    bottom=[a+b for a,b in zip(bottom,values)]
axes[0,1].set(title='Two-minute example: available pairs only',ylabel='Family starts; all four trade endpoint ages ≤5s')
axes[0,1].legend(fontsize=8)
x=[int(r['horizon_s'])/60 for r in over]
axes[1,0].bar([str(int(v)) for v in x],[int(r['starts_with_overlap']) for r in over],color='#6c669c')
axes[1,0].axhline(749,color='#555',linestyle='--',linewidth=1)
axes[1,0].set(title='Overlapping first-observed family starts',xlabel='Minutes on either side of a start',ylabel='Starts with at least one other start',ylim=(0,800))
pre=[r for r in stable if r['phase']=='before_start' and int(r['overall_pair_n'])>=100 and r['overall_correlation']]
enough=sum(r['all_quarters_at_least_30_pairs']=='true' for r in pre)
same=sum(r['all_quarters_at_least_30_pairs']=='true' and r['same_sign_all_quarters']=='true' for r in pre)
axes[1,1].barh(['≥100 pairs overall','≥30 in each quarter','Also same sign in all quarters'],[len(pre),enough,same],color=['#aaa','#6b93ad','#386989'])
axes[1,1].set(title='Pre-start marginal comparison stability',xlabel='Exploratory feature/horizon comparisons; dependent, uncorrected')
fig.suptitle('One retained market day · descriptive findings, not a validated trading edge',fontsize=14)
fig.supxlabel('Fresh quote/trade panel requires both future-price endpoints ≤5s; prior-direction ages may vary. Sample counts change by horizon. No causal or significance claim.',fontsize=8)
for ext in ['png','svg']:fig.savefig(P/('descriptive-findings.'+ext),dpi=170)
svg=P/'descriptive-findings.svg'
svg.write_text('\n'.join(l.rstrip() for l in svg.read_text().splitlines())+'\n')
plt.close(fig)
print('Saved descriptive-findings.png and .svg')
