"""Plot saved stack comparisons and conditional outcomes with their counts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from research_atlas import OUT


def export(fig,name):
    for ext in ('png','svg'):fig.savefig(OUT/f'figures/{name}.{ext}',dpi=160)
    p=OUT/f'figures/{name}.svg'
    p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
    plt.close(fig)


def main():
    m=pd.read_csv(OUT/'stack-metrics.csv');m=m[m.fold.eq(-1)]
    arms=['plus_dipole','plus_fresh','plus_book','plus_display','dipole_book','full',
          'without_dipole','without_fresh','without_book','without_display']
    pairs=[('midpoint_ticks',h) for h in (5,20,60)]+[('absolute_ticks',h) for h in (5,20,60)]+[('flow_strength_change',20)]
    table=m.pivot(index='arm',columns=['target','horizon_s'],values='mse_ratio_to_baseline').reindex(index=arms,columns=pairs)
    values=(table.to_numpy()-1)*100
    fig,ax=plt.subplots(figsize=(12,6),layout='constrained')
    ax.imshow(values,cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-5,vcenter=0,vmax=32),aspect='auto')
    ax.set_yticks(range(len(arms)),['+ Dipole','+ Fresh trades','+ Book','+ Display changes','+ Dipole and book','FULL STACK',
                                  'Full minus dipole','Full minus fresh trades','Full minus book','Full minus display changes'])
    ax.set_xticks(range(7),['Price\n5 s','Price\n20 s','Price\n60 s','Magnitude\n5 s','Magnitude\n20 s','Magnitude\n60 s','Flow strength\n20 s'])
    for i in range(len(arms)):
        for j in range(7):ax.text(j,i,f'{values[i,j]:+.1f}%',ha='center',va='center',color='white' if values[i,j]>22 else '#132537')
    ax.axhline(5.5,color='white',linewidth=3)
    ax.set_title('Adding indicators does not automatically improve the forecast',fontsize=16,pad=15)
    fig.supxlabel('Change in out-of-fold squared error versus price-context baseline. Negative = better. One discovery day; 11 fixed arms, no tuning.',fontsize=9)
    export(fig,'stack-incremental-information')
    s=pd.read_csv(OUT/'stack-conditional-states.csv');s=s[s.horizon_s.eq(20)]
    rows=[];labels=[]
    for state in ['weakening','strengthening','steady','one_half_empty']:
        for book in ['aligned','opposed']:
            row=s[s.dipole_state.eq(state)&s.book_vs_flow.eq(book)].iloc[0]
            rows.append(row);labels.append(f'{state.replace("_"," ")} / book {book}  (n={row.n})')
    fig,ax=plt.subplots(figsize=(12,6),layout='constrained');left=np.zeros(len(rows))
    for key,label,color in [('follows_current_flow','Move with current flow','#267d8d'),
                             ('opposes_current_flow','Move against current flow','#d98157'),
                             ('flat','No midpoint change','#b7bdc4'),('missing','Unavailable','#483e4e')]:
        counts=np.array([r.n-r.available if key=='missing' else r[key] for r in rows])
        shares=counts/np.array([r.n for r in rows])*100
        ax.barh(range(len(rows)),shares,left=left,label=label,color=color)
        for i,(n,w) in enumerate(zip(counts,shares)):
            if w>4:ax.text(left[i]+w/2,i,str(n),ha='center',va='center',color='white' if key!='flat' else '#17262b',fontsize=10)
        left+=shares
    ax.set_yticks(range(len(rows)),labels);ax.invert_yaxis();ax.set_xlim(0,100)
    ax.set_xlabel('Share of selected cases; labels are case counts')
    ax.set_title('The book changes the context of a dipole state',fontsize=16,pad=15)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2,fontsize=9)
    fig.supxlabel('20-second midpoint response after recognition. 442 cases shown; 345 empty-flow and 76 balanced-book/flow cases remain in the complete table.',fontsize=9)
    export(fig,'stack-conditional-story')


if __name__=='__main__':main()
