import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
d = pd.read_csv('tables/t1_family_master_flags.csv'); d = d.copy()
x = d['root.depth_imbalance_full']; print('full-depth imbalance across 749: min %.4f q25 %.4f med %.4f q75 %.4f max %.4f' % (x.min(), x.quantile(.25), x.median(), x.quantile(.75), x.max()))
print('bid_depth_full/ask_depth_full ratio: min %.2f med %.2f max %.2f' % ((d['root.bid_depth_full']/d['root.ask_depth_full']).min(), (d['root.bid_depth_full']/d['root.ask_depth_full']).median(), (d['root.bid_depth_full']/d['root.ask_depth_full']).max()))
y = d['root.depth_imbalance_n']; print('first-ten imbalance: min %.3f med %.3f max %.3f; neg %d pos %d zero %d' % (y.min(), y.median(), y.max(), (y<0).sum(), (y>0).sum(), (y==0).sum()))
print('correlation full vs near imbalance: %.3f' % np.corrcoef(x, y)[0,1])
# near-depth corners
H=[1,5,20,60,300]
def dist(sub,h):
    v=sub[f'tk_{h}s'].dropna(); return dict(n=len(v),down=int((v<0).sum()),flat=int((v==0).sum()),up=int((v>0).sum()),med=v.median() if len(v) else np.nan)
d['flowpat'] = np.where((d.f60=='+')&(d.f5=='-')&(d.f1=='-'),'orig(60+/5-/1-)',np.where((d.f60=='-')&(d.f5=='+')&(d.f1=='+'),'flipped(60-/5+/1+)','other'))
d['near'] = np.where(d.dsg_n=='+','near bid-heavy',np.where(d.dsg_n=='-','near ask-heavy','near zero'))
rows=[]
for (fp,nr),sub in d.groupby(['flowpat','near']):
    for h in H:
        r=dist(sub,h); r.update(flow=fp,near_depth=nr,support=len(sub),horizon_s=h); rows.append(r)
T=pd.DataFrame(rows)[['flow','near_depth','support','horizon_s','n','down','flat','up','med']]
T.to_csv('tables/t1_corners_flow_x_neardepth.csv',index=False)
print(T[T.horizon_s.isin([1,5,60,300])].round(2).to_string(index=False))
# orientation: outcome in the direction of the 5 s flow (sell-heavy 5 s -> down). aligned/flat/opposed.
d['dir5']=np.where(d.f5=='+',1,np.where(d.f5=='-',-1,0))
rows=[]
for fp in ['orig(60+/5-/1-)','flipped(60-/5+/1+)']:
    sub=d[d.flowpat==fp]
    for h in H:
        v=(sub[f'tk_{h}s']*sub.dir5).dropna(); rows.append(dict(flow=fp,horizon_s=h,n=len(v),with_5s_flow=int((v>0).sum()),flat=int((v==0).sum()),against_5s_flow=int((v<0).sum()),med_ticks_in_flow_dir=v.median()))
O=pd.DataFrame(rows); O.to_csv('tables/t1_oriented_to_5s_flow.csv',index=False); print(O.round(2).to_string(index=False))
# baseline for all families with defined 5 s flow
sub=d[d.dir5!=0]
for h in H:
    v=(sub[f'tk_{h}s']*sub.dir5).dropna(); print('all families with signed 5s flow h=%d: n=%d with=%d flat=%d against=%d'%(h,len(v),(v>0).sum(),(v==0).sum(),(v<0).sum()))
