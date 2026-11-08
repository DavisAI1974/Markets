"""Figures from saved dipole application tables."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from research_atlas import OUT


def main():
    f=pd.read_csv(OUT/'dipole-operator-observations.csv.gz')
    p=pd.read_csv(OUT/'dipole-weakening-path.csv.gz').drop_duplicates(['second','transition'])
    fig,ax=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    stages=['prebirth_60s','prebirth_20s','prebirth_5s','prebirth_1s','recognition']
    categories=['both_active','early_empty','late_empty','both_empty']
    colors=['#267d8d','#70a9a1','#e3ae54','#b7bdc4']
    counts=pd.crosstab(f.stage,f.half_activity).reindex(index=stages,columns=categories)
    bottom=[0]*5
    for category,color in zip(categories,colors):
        ax[0].bar(range(5),counts[category],bottom=bottom,color=color,label=category.replace('_',' '))
        bottom=counts[category]+bottom
    ax[0].set_xticks(range(5),['−60 s','−20 s','−5 s','−1 s','Recognition'])
    ax[0].set_ylabel('Candidates (all 863 retained)')
    ax[0].set_title('Is flow present in both halves of the 20-second window?')
    ax[0].legend(loc='upper left',fontsize=8)
    weak=p[p.transition.eq('weakening')].reason.value_counts()
    labels=['fresh_only','expiry_only','fresh_and_expiry']
    ax[1].barh(range(3),[weak.get(k,0) for k in labels],color=['#267d8d','#e3ae54','#70a9a1'])
    ax[1].set_yticks(range(3),['Fresh lots only','Expired lots only','Fresh and expired lots'])
    for i,k in enumerate(labels):ax[1].text(weak.get(k,0)+15,i,str(weak.get(k,0)),va='center')
    ax[1].set_xlim(0,max(weak)*1.15)
    ax[1].set_xlabel('Unique seconds within selected birth-to-recognition paths')
    ax[1].set_title('Defined imbalance moved toward balance')
    fig.suptitle('October 18 dipole dive: weakening has different mechanisms',fontsize=15)
    fig.supxlabel('Completed-group quote classification. Empty flow is undefined, not balance. Selected overlapping paths; no independence claim.',fontsize=9)
    for ext in ('png','svg'):fig.savefig(OUT/f'figures/dipole-weakening-mechanisms.{ext}',dpi=160)
    svg=OUT/'figures/dipole-weakening-mechanisms.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':main()
