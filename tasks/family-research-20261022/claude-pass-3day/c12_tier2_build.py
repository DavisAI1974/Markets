"""Tier 2: dense decision grid over the Oct 18 UTC member (2023-10-18 00:10 to 23:49 UTC), one decision every STEP seconds.
Every feature is as of the decision cutoff c (records in groups closed by c).  Outcomes use only records/groups after c.
Series: flow (known wire side lots), book behaviour by side (adds at touch / near / far, fill-linked removals, unlinked cancels, fills, touch modifies),
touch state, near depth, prior displacement, quote changes.  No cost assumption.  Output: tables/t2_grid.parquet"""
import sys; sys.path.insert(0, '.')   # cwd is this code directory, not a data directory
from odcfg import *
DATE = date_arg(); LEGACY = len(sys.argv) > 2 and sys.argv[2] == 'legacy'; SUF = '_legacy' if LEGACY else ''
import os, numpy as np, pandas as pd
from c04_order_features import enrich, Windows
STEP = 3; S = 10**9
R0 = pd.read_parquet(recon(DATE)); R, C = enrich(R0); W = Windows(R, C)
G = np.load(f'{WORK}/groups_retained_20231018.npz' if LEGACY else groups(DATE)); recv = G['recv_ns']; mid = (G['bid_px'] + G['ask_px']) / 2e9
bidp = G['bid_px'] / 1e9; askp = G['ask_px'] / 1e9
t0 = int(R.ts.iloc[0]) + 600 * S; t1 = int(R.ts.iloc[-1]) - 660 * S
cut = np.arange(t0, t1, STEP * S, dtype=np.int64)
CUTS = os.environ.get('OD_CUTS')                       # optional: a .npy of explicit as-of cutoffs (ns); same feature code, different decision times
if CUTS: cut = np.load(CUTS).astype(np.int64)
n = len(cut); print('decisions', n)
e = np.searchsorted(W.last_ts, cut, side='right') - 1; E = W.last_idx[e]            # last record index of a group closed by cut
cols = W.cols; cum = W.cum; ci = {c: i for i, c in enumerate(cols)}
def win(w):                                                                      # (cut-w, cut] sums for every cut, vectorised
    s = np.searchsorted(W.ts, cut - w * S, side='right'); s = np.minimum(s, E + 1)
    return {c: cum[ci[c], E + 1] - cum[ci[c], s] for c in cols}
D = {'cut_ns': cut, 'rec_idx': E}
for w in (1, 2, 5, 10, 20, 60):
    s = win(w)
    D[f'buy_{w}'] = s['trade_buyagg']; D[f'sell_{w}'] = s['trade_sellagg']; D[f'ntr_{w}'] = s['n_trade']
    D[f'net_{w}'] = s['trade_buyagg'] - s['trade_sellagg']; tot = s['trade_buyagg'] + s['trade_sellagg']
    D[f'imb_{w}'] = np.where(tot > 0, D[f'net_{w}'] / np.maximum(tot, 1), np.nan)
    if w in (1, 5, 20, 60):
        for sd in ('b', 'a'):
            D[f'addT_{sd}_{w}'] = s[f'add_touch_{sd}']; D[f'addN_{sd}_{w}'] = s[f'add_near_{sd}']; D[f'addF_{sd}_{w}'] = s[f'add_far_{sd}']
            D[f'fill_{sd}_{w}'] = s[f'fill_{sd}']; D[f'rmF_{sd}_{w}'] = s[f'rm_fill_{sd}']
            D[f'cxT_{sd}_{w}'] = s[f'rm_cx_touch_{sd}']; D[f'cxN_{sd}_{w}'] = s[f'rm_cx_near_{sd}']; D[f'cxF_{sd}_{w}'] = s[f'rm_cx_far_{sd}']
            D[f'modT_{sd}_{w}'] = s[f'mod_touch_{sd}']
        for sd in ('b', 'a'):   # net displayed support near the touch = adds - removals (fill-linked + unlinked)
            D[f'sup_{sd}_{w}'] = D[f'addT_{sd}_{w}'] + D[f'addN_{sd}_{w}'] - D[f'rmF_{sd}_{w}'] - D[f'cxT_{sd}_{w}'] - D[f'cxN_{sd}_{w}']
            D[f'refill_{sd}_{w}'] = np.where(D[f'fill_{sd}_{w}'] > 0, (D[f'addT_{sd}_{w}'] + D[f'addN_{sd}_{w}']) / np.maximum(D[f'fill_{sd}_{w}'], 1), np.nan)
            D[f'cxshare_{sd}_{w}'] = np.where((D[f'rmF_{sd}_{w}'] + D[f'cxT_{sd}_{w}'] + D[f'cxN_{sd}_{w}']) > 0, (D[f'cxT_{sd}_{w}'] + D[f'cxN_{sd}_{w}']) / np.maximum(D[f'rmF_{sd}_{w}'] + D[f'cxT_{sd}_{w}'] + D[f'cxN_{sd}_{w}'], 1), np.nan)
        D[f'supdiff_{w}'] = D[f'sup_b_{w}'] - D[f'sup_a_{w}']
# touch state at the cutoff
b = R.bb_a.to_numpy()[E]; a = R.ba_a.to_numpy()[E]
D['spr'] = (a - b).astype(float); D['bsz'] = R.bsz_a.to_numpy()[E].astype(float); D['asz'] = R.asz_a.to_numpy()[E].astype(float)
D['bn'] = R.bn_a.to_numpy()[E].astype(float); D['an'] = R.an_a.to_numpy()[E].astype(float)
D['tch_imb'] = (D['bsz'] - D['asz']) / (D['bsz'] + D['asz']); D['tchn_imb'] = (D['bn'] - D['an']) / (D['bn'] + D['an'])
D['bsz_per_ord'] = D['bsz'] / np.maximum(D['bn'], 1); D['asz_per_ord'] = D['asz'] / np.maximum(D['an'], 1)
for k in (5, 10):
    nb = R[f'near_bid{k}'].to_numpy()[E].astype(float); na = R[f'near_ask{k}'].to_numpy()[E].astype(float)
    D[f'nb{k}'] = nb; D[f'na{k}'] = na; D[f'near{k}_imb'] = (nb - na) / (nb + na)
D['mid'] = (b + a) / 2.0
# prior displacement / quote changes from group arrays
qchg = np.concatenate([[0], ((np.diff(bidp) != 0) | (np.diff(askp) != 0)).astype(int)]); qcum = np.cumsum(qchg)
gi = np.searchsorted(recv, cut, side='right') - 1
for w in (1, 5, 20, 60, 300):
    j = np.maximum(np.searchsorted(recv, cut - w * S, side='right') - 1, 0)
    D[f'prior_{w}'] = (mid[gi] - mid[j]) / 0.001; D[f'qchg_{w}'] = (qcum[gi] - qcum[j]).astype(float)
# outcomes
def at(h): return np.minimum(np.searchsorted(recv, cut + h * S, side='right') - 1, len(recv) - 1)
for h in (1, 5, 20, 60):
    j = at(h); D[f'dm_{h}'] = (mid[j] - mid[gi]) / 0.001; D[f'am_{h}'] = np.abs(D[f'dm_{h}'])
    if h in (5, 20):
        D[f'dbid_{h}'] = (bidp[j] - bidp[gi]) / 0.001; D[f'dask_{h}'] = (askp[j] - askp[gi]) / 0.001; D[f'dspr_{h}'] = ((askp[j] - bidp[j]) - (askp[gi] - bidp[gi])) / 0.001
# forward book / flow responses over (c, c+h]
def fwd(h):
    s_i = E + 1; e_i = at_rec(h)
    return {c: cum[ci[c], e_i + 1] - cum[ci[c], s_i] for c in cols}
def at_rec(h):
    j = np.searchsorted(W.last_ts, cut + h * S, side='right') - 1; return W.last_idx[np.maximum(j, 0)]
for h in (5, 20):
    f = fwd(h)
    D[f'F_buy_{h}'] = f['trade_buyagg']; D[f'F_sell_{h}'] = f['trade_sellagg']; D[f'F_net_{h}'] = f['trade_buyagg'] - f['trade_sellagg']; D[f'F_ntr_{h}'] = f['n_trade']
    D[f'F_sup_b_{h}'] = f['add_touch_b'] + f['add_near_b'] - f['rm_fill_b'] - f['rm_cx_touch_b'] - f['rm_cx_near_b']
    D[f'F_sup_a_{h}'] = f['add_touch_a'] + f['add_near_a'] - f['rm_fill_a'] - f['rm_cx_touch_a'] - f['rm_cx_near_a']
    D[f'F_cx_b_{h}'] = f['rm_cx_touch_b'] + f['rm_cx_near_b']; D[f'F_cx_a_{h}'] = f['rm_cx_touch_a'] + f['rm_cx_near_a']
    D[f'F_add_b_{h}'] = f['add_touch_b'] + f['add_near_b']; D[f'F_add_a_{h}'] = f['add_touch_a'] + f['add_near_a']
D['age_s'] = (cut - recv[gi]) / S                                                   # seconds since the last completed group close (age of the book snapshot)
_ci = np.where(qchg > 0)[0]; _j = np.searchsorted(_ci, gi, side='right') - 1
D['qage_s'] = np.where(_j >= 0, (cut - recv[_ci[np.maximum(_j, 0)]]) / S, np.nan)    # seconds since the touch price last changed
D['closed'] = np.zeros(n, dtype=bool) if LEGACY else closed_mask(recv, cut, R.ts.to_numpy()[(R.action == 'T').to_numpy()])                  # closed-market stretch (data-defined gap) + 600 s re-open warm-up
df = pd.DataFrame(D)
df['utc_hour'] = pd.to_datetime(df.cut_ns, unit='ns', utc=True).dt.hour; df['block'] = df.utc_hour
df['settle_tag'] = (pd.to_datetime(df.cut_ns, unit='ns', utc=True).dt.hour * 60 + pd.to_datetime(df.cut_ns, unit='ns', utc=True).dt.minute).between(18 * 60 + 25, 18 * 60 + 35)
df.to_parquet(os.environ['OD_OUT'] if CUTS else big(DATE, 'grid' + SUF)); print(DATE, SUF, df.shape, 'closed rows', int(df.closed.sum()))
print(df[['dm_5', 'am_5', 'imb_5', 'spr', 'sup_b_5', 'F_net_5']].describe().round(2).T)
