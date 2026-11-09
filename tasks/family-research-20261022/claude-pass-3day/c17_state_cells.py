"""One-second state cells: [last-second midpoint move] x [touch size imbalance at the end of the second] x [last-second net aggressor flow] -> what the midpoint does next.
Terciles of touch imbalance are taken INSIDE activity quintiles (trailing-60 s trade lots), so the cut is a market condition.  Flat = exactly zero change.
Outcomes: next second (t+1) and next five seconds (mid(t+5) - mid(t)).  net = (up - down) / (up + down + flat).  Stability = sign of net in 24 contiguous chronological chunks.
Null = outcome vector cyclically shifted >= 600 s, 300 shifts; cell z from that null.  ts/cursor coordinates are carried for exemplars only."""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
DATE = date_arg(); LEGACY = len(sys.argv) > 2 and sys.argv[2] == 'legacy'; SUF = '_legacy' if LEGACY else ''
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
d = pd.read_parquet(big(DATE, 'seconds' + SUF)); T = len(d)
d['act_q'] = pd.qcut(d.live60.rank(method='first'), 5, labels=False)
d['timb_t'] = np.nan
for k in range(5):
    m = (d.act_q == k) & d.valid; d.loc[m, 'timb_t'] = pd.qcut(d.loc[m, 'timb'].rank(method='first'), 3, labels=False)
d['timb_c'] = d.timb_t.map({0: 'ask-heavy', 1: 'mid', 2: 'bid-heavy'})
d['move_c'] = np.where(d.dmid > 0, 'up', np.where(d.dmid < 0, 'down', 'flat'))
d['flow_c'] = np.where(d.flow > 0, 'buy', np.where(d.flow < 0, 'sell', 'none'))
mid = d.mid.to_numpy(); d['y1'] = (np.roll(mid, -1) - mid) / 0.001; d['y5'] = (np.roll(mid, -5) - mid) / 0.001
ok = d.valid & d.timb_t.notna() & (np.arange(T) < T - 6) & (d.live60 > 0)       # need some trading in the trailing 60 s for the activity stratum
D = d[ok].copy(); n = len(D); print('usable seconds', n, 'of', T)
chunk = np.minimum((np.arange(n) * 24) // n, 23)
def cell_stats(y, mask):
    v = y[mask]; up = (v > 0).sum(); dn = (v < 0).sum(); fl = (v == 0).sum(); tot = len(v)
    return up, dn, fl, tot, (up - dn) / tot if tot else np.nan
y1 = D.y1.to_numpy(); y5 = D.y5.to_numpy()
keys = D.move_c + '|' + D.timb_c + '|' + D.flow_c
rng = np.random.default_rng(2); shifts = [int(rng.integers(600, n - 600)) for _ in range(300)]
rows = []
for key in sorted(keys.unique()):
    m = (keys == key).to_numpy()
    if m.sum() < 150: continue
    for h, y in (('next1s', y1), ('next5s', y5)):
        up, dn, fl, tot, net = cell_stats(y, m)
        nulls = np.array([cell_stats(np.roll(y, s), m)[4] for s in shifts]); z = (net - nulls.mean()) / (nulls.std() + 1e-9)
        sg = []; 
        for k in range(24):
            mk = m & (chunk == k)
            if mk.sum() >= 15: u, dd, f, t, nt = cell_stats(y, mk); sg.append(np.sign(u - dd))
        same = int((np.array(sg) == np.sign(up - dn)).sum()) if sg else 0
        rows.append(dict(cell=key, horizon=h, support=int(m.sum()), up=int(up), flat=int(fl), down=int(dn), net_share=net, null_mean=nulls.mean(), z=z, chunks=len(sg), same_sign_chunks=same, median_ticks=float(np.median(y[m]))))
C = pd.DataFrame(rows); C.to_csv(tab(DATE + SUF, 't2_state_cells.csv'), index=False)
pd.set_option('display.width', 200)
for h in ('next1s', 'next5s'):
    s = C[C.horizon == h].reindex(C[C.horizon == h].z.abs().sort_values(ascending=False).index)
    print('\n==', h, 'cells with support >=150:', len(s)); print(s.head(14)[['cell', 'support', 'up', 'flat', 'down', 'net_share', 'z', 'chunks', 'same_sign_chunks', 'median_ticks']].round(3).to_string(index=False))
# marginal vs stacked: net share of the next-5s move for each single factor level, then for pairs
print('\nMARGINALS (next5s)')
for col in ('move_c', 'timb_c', 'flow_c'):
    for lv, m in D.groupby(col).groups.items():
        mm = D.index.isin(m); up, dn, fl, tot, net = cell_stats(y5, mm); print(f'{col}={lv:9s} support {tot:6d} up {up:5d} flat {fl:5d} down {dn:5d} net {net:+.3f}')
D.to_parquet(big(DATE, 'seconds_states' + SUF))
