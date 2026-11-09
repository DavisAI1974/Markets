"""Three phone-readable raw negative-section overlays; no fitted/warped observations."""
from shape_forms import *
P=pd.read_csv(ROOT/'tables/shape_forms-observations.csv',float_precision='round_trip')
for definition in DEFS:
    fig,ax=plt.subplots(figsize=(9,6.6));name=f'shape_forms-negative-focus-{definition}.png'
    for day,color in zip(DAYS,COLORS):
        allq=P[(P.day==day)&(P.definition==definition)];q=allq[allq.section=='negative']
        ax.plot(q['rank'],q.recognition_minus_event_s,'.-',lw=1.3,ms=4,color=color,label=f'Oct {str(day)[-2:]}: {len(allq)} / {len(q)} / {len(allq)-len(q)}')
        count(name,str(day),len(allq),len(q),'zero/positive sections or unavailable clock; full curve retained separately')
    ax.axhline(0,color='gray',lw=.6);ax.set_title(definition.replace('_',' ').capitalize()+'\nNegative section: four original day curves',loc='left',pad=12)
    ax.set_xlabel('Original sorted observation rank');ax.set_ylabel('Recognition minus first event (seconds)');ax.grid(axis='y',color='#dddddd',lw=.5);ax.legend(title='All rows / negative points / other or unavailable',loc='lower right',fontsize=9,title_fontsize=9)
    fig.text(.12,.02,'Negative means event AFTER recognition. Rank is not chronological time.\nFull curves and every other section remain retained. Oct 2/17 partial; Oct 18 included.',fontsize=8)
    fig.tight_layout(rect=(0,.075,1,1));fig.savefig(ROOT/'figures'/name,dpi=160);plt.close(fig)
save(pd.DataFrame(RECON),'shape_forms-focus-figure-reconciliation.csv')
