"""Tier 1 cell tables: flow pattern x depth sign over all 749 families, matched-50 detail, activity-matched controls.
Sign convention: outcome = midpoint change in ticks (0.001); negative = lower.  Flat = exactly 0.  Missing stays missing."""
import numpy as np, pandas as pd, json
d = pd.read_csv('tables/t1_family_master.csv')
H = [1, 5, 20, 60, 120, 300, 600]
sg = lambda x: np.where(pd.isna(x), 'NA', np.where(x > 0, '+', np.where(x < 0, '-', '0')))
d['f60'] = sg(d['root.activity.60.trade_aggressor_imbalance']); d['f5'] = sg(d['root.activity.5.trade_aggressor_imbalance'])
d['f1'] = sg(d['root.activity.1.trade_aggressor_imbalance']); d['dsg'] = sg(d['root.depth_imbalance_full'])
d['dsg_n'] = sg(d['root.depth_imbalance_n'])
d['pattern'] = d.f60 + '/' + d.f5 + '/' + d.f1
def dist(sub, h):
    x = sub[f'tk_{h}s'].dropna()
    return dict(n=len(x), down=int((x < 0).sum()), flat=int((x == 0).sum()), up=int((x > 0).sum()),
                q25=x.quantile(.25) if len(x) else np.nan, med=x.median() if len(x) else np.nan, q75=x.quantile(.75) if len(x) else np.nan)
# 1. cells: flow pattern x full-depth sign
rows = []
for (pat, ds), sub in d.groupby(['pattern', 'dsg']):
    for h in (1, 5, 60, 300):
        r = dist(sub, h); r.update(pattern_60_5_1=pat, full_depth_sign=ds, horizon_s=h, cell_n=len(sub)); rows.append(r)
cells = pd.DataFrame(rows)[['pattern_60_5_1','full_depth_sign','cell_n','horizon_s','n','down','flat','up','q25','med','q75']]
cells.to_csv('tables/t1_cells_flow_pattern_x_depth.csv', index=False)
print('patterns x depth, cell sizes (all 749):', d.groupby(['pattern','dsg']).size().shape[0], 'cells; sum', int(d.groupby(['pattern','dsg']).size().sum()))
print(d.dsg.value_counts().to_dict(), 'depth_n', d.dsg_n.value_counts().to_dict())
tab = d.groupby(['pattern','dsg']).size().unstack(fill_value=0); tab['all'] = tab.sum(axis=1); print(tab.sort_values('all', ascending=False).head(14).to_string())
# 2. stack variants (support + outcome at 1,5,60,300)
var = {
 'original: 60+/5-/1- , bid-heavy full depth': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='+'),
 'inverse (all four flipped): 60-/5+/1+ , ask-heavy': (d.f60=='-')&(d.f5=='+')&(d.f1=='+')&(d.dsg=='-'),
 'flow same, depth flipped: 60+/5-/1- , ask-heavy': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='-'),
 'flow flipped, depth same: 60-/5+/1+ , bid-heavy': (d.f60=='-')&(d.f5=='+')&(d.f1=='+')&(d.dsg=='+'),
 'flow same, depth missing/zero': (d.f60=='+')&(d.f5=='-')&(d.f1=='-')&(d.dsg=='0'),
 'flow of original with any depth sign': (d.f60=='+')&(d.f5=='-')&(d.f1=='-'),
 'flow flipped with any depth sign': (d.f60=='-')&(d.f5=='+')&(d.f1=='+'),
 'bid-heavy full depth, any flow': (d.dsg=='+'),
 'ask-heavy full depth, any flow': (d.dsg=='-'),
 'all 749': d.instance>0,
}
rows = []
for name, m in var.items():
    for h in H:
        r = dist(d[m], h); r.update(variant=name, support=int(m.sum()), horizon_s=h); rows.append(r)
V = pd.DataFrame(rows)[['variant','support','horizon_s','n','down','flat','up','q25','med','q75']]
V.to_csv('tables/t1_stack_variants.csv', index=False)
pd.set_option('display.width', 220)
print(V[V.horizon_s.isin([1,5,60,300])].round(2).to_string(index=False))
d.to_csv('tables/t1_family_master_flags.csv', index=False)
