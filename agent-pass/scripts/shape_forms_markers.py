"""Retain every original point and describe exact sign boundaries/local gap extrema."""
from shape_forms import *
P=pd.read_csv(ROOT/'tables/shape_forms-observations.csv',float_precision='round_trip')
parts=[]
for _,q in P.groupby(['day','definition'],sort=False):
    q=q.copy();g=q.adjacent_gap_s;left=g.shift(1);right=g.shift(-1);valid=g.notna()&left.notna()&right.notna()
    q['local_gap_maximum']=valid&(g>=left)&(g>=right)&((g>left)|(g>right))
    q['local_gap_minimum']=valid&(g<=left)&(g<=right)&((g<left)|(g<right))
    q['gap_neighbors_defined']=valid
    q['sign_section_boundary']=q.section!=q.section.shift(1)
    q['boundary_label']=np.where(q.sign_section_boundary,q.section.shift(1).fillna('curve_start')+' -> '+q.section,'')
    parts.append(q)
P=pd.concat(parts,ignore_index=True);save(P,'shape_forms-markers.csv')
for definition in DEFS:
    fig,axes=plt.subplots(4,1,figsize=(13,14),sharex=True,sharey=True);name=f'shape_forms-markers-{definition}.png'
    for ax,day,color in zip(axes,DAYS,COLORS):
        q=P[(P.day==day)&(P.definition==definition)];ok=q.recognition_minus_event_s.notna();ax.plot(q.loc[ok,'rank'],q.loc[ok,'recognition_minus_event_s'],'.-',ms=2,lw=.7,color=color,label=f'all {len(q)}/{ok.sum()}/{(~ok).sum()}');count(name,str(day)+' all',len(q),int(ok.sum()))
        for field,marker,offset in [('local_gap_maximum','^',0),('local_gap_minimum','v',0),('sign_section_boundary','s',0)]:
            mask=q[field]&ok;ax.scatter(q.loc[mask,'rank'],q.loc[mask,'recognition_minus_event_s'],marker=marker,s=24,facecolors='none',edgecolors='black',label=f'{field}: {len(q)}/{mask.sum()}/{(~mask).sum()}');count(name,str(day)+' '+field,len(q),int(mask.sum()),'not this marker or clock unavailable; original point remains in all series')
        ax.axhline(0,lw=.5,color='gray');ax.set_title(str(day));ax.set_xlabel('Original sorted rank');ax.set_ylabel('Recognition minus event (s)');ax.legend(fontsize=6,title='in / marked / not marked')
    fig.suptitle(definition+': every local gap extremum and exact signed-section boundary');finish(fig,name)
save(pd.DataFrame(RECON),'shape_forms-markers-figure-reconciliation.csv')
print('marker observations',len(P),'maxima',P.local_gap_maximum.sum(),'minima',P.local_gap_minimum.sum(),'boundary rows',P.sign_section_boundary.sum())
