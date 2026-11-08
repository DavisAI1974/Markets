"""Pre-event refill behaviour at the side being hit, with raw operands.
For families whose last 1 s had sell-aggressor lots (hits on the bid): bid_adds = add_touch_b + add_near_b (lots added at or within 4 ticks of the bid touch),
bid_fills = fill_b (lots of resting bids executed), ratio = bid_adds / bid_fills (undefined when fills = 0).
Mirror for buy aggression on the ask.  All as of the strict cutoff.  Outcomes: midpoint change in ticks."""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
d = pd.read_csv('tables/t1_family_master_flags.csv'); d = d[d.in_member].copy()
d['bid_adds_1s'] = d.ob_add_touch_b_1s + d.ob_add_near_b_1s; d['ask_adds_1s'] = d.ob_add_touch_a_1s + d.ob_add_near_a_1s
d['bid_ratio_1s'] = np.where(d.ob_fill_b_1s > 0, d.bid_adds_1s / d.ob_fill_b_1s, np.nan)
d['ask_ratio_1s'] = np.where(d.ob_fill_a_1s > 0, d.ask_adds_1s / d.ob_fill_a_1s, np.nan)
sell = d[(d.ob_trade_sellagg_1s > 0) & (d.ob_fill_b_1s > 0)].copy()
buy = d[(d.ob_trade_buyagg_1s > 0) & (d.ob_fill_a_1s > 0)].copy()
print('in-member families', len(d), '| last-1s sell-hit with bid fills:', len(sell), '| last-1s buy-lift with ask fills:', len(buy))
H = [1, 5, 20, 60, 300]
def tert(sub, ratio, label, hit_dir):
    sub = sub.copy(); sub['grp'] = pd.qcut(sub[ratio].rank(method='first'), 3, labels=['low', 'mid', 'high'])
    rows = []
    for g, s in sub.groupby('grp'):
        for h in H:
            v = s[f'tk_{h}s'].dropna()
            rows.append(dict(set=label, tercile=g, ratio_lo=s[ratio].min(), ratio_hi=s[ratio].max(), horizon_s=h, n=len(v), down=int((v<0).sum()), flat=int((v==0).sum()), up=int((v>0).sum()), med_ticks=v.median(),
                             med_fill_lots=s['ob_fill_b_1s' if hit_dir=='bid' else 'ob_fill_a_1s'].median()))
    return pd.DataFrame(rows)
T = pd.concat([tert(sell, 'bid_ratio_1s', 'sell-hit last 1s: bid adds / bid fills', 'bid'), tert(buy, 'ask_ratio_1s', 'buy-lift last 1s: ask adds / ask fills', 'ask')])
T.to_csv('tables/t1_refill_terciles.csv', index=False); pd.set_option('display.width', 200)
print(T[T.horizon_s.isin([1, 5, 60, 300])].round(2).to_string(index=False))
for lab, sub, r, sgn in (('sell-hit', sell, 'bid_ratio_1s', 1), ('buy-lift', buy, 'ask_ratio_1s', 1)):
    for h in H:
        x = sub[[r, f'tk_{h}s']].dropna(); rho, p = spearmanr(x[r], x[f'tk_{h}s']); print(f'{lab} spearman(ratio, tk_{h}s) = {rho:+.3f} n={len(x)} p~{p:.3f}')
# within strata of fill size (activity control): ratio terciles inside fill-size halves
sell['fillbin'] = pd.qcut(sell.ob_fill_b_1s.rank(method='first'), 2, labels=['small fills', 'large fills'])
rows = []
for fb, s in sell.groupby('fillbin'):
    hi = s.bid_ratio_1s >= s.bid_ratio_1s.median()
    for h in (1, 5, 300):
        for lab, ss in (('ratio>=median', s[hi]), ('ratio<median', s[~hi])):
            v = ss[f'tk_{h}s'].dropna(); rows.append(dict(fill_stratum=fb, group=lab, horizon_s=h, n=len(v), down=int((v<0).sum()), flat=int((v==0).sum()), up=int((v>0).sum()), med=v.median()))
S = pd.DataFrame(rows); S.to_csv('tables/t1_refill_by_fill_stratum.csv', index=False); print(S.to_string(index=False))
# the two named cases
for k in (375, 391):
    r = d[d.instance == k].iloc[0]; print(k, 'bid adds touch/near', r.ob_add_touch_b_1s, r.ob_add_near_b_1s, 'bid fills', r.ob_fill_b_1s, 'sell agg lots', r.ob_trade_sellagg_1s, 'ratio', round(r.bid_ratio_1s, 3))
