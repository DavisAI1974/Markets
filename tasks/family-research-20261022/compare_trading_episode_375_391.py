"""Targeted offline episode comparison; original quotes/forecasts remain frozen.

Run from the relocated Markets worktree. No fits, networking or raw input restore.
Clock identities stay integer; relative seconds are plotting/display values only.
"""
import csv
import gzip
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trading-episode-375-391'
OUT.mkdir(exist_ok=True)
REVIEW = BASE / 'instance-market-review-20261023'
CLOCKS = ['source_ordinal', 'input_cursor', 'event_ns', 'receive_ns', 'known_by_ns']
CASES = {375: (1697634552081390598, 303655),
         391: (1697634840878613141, 319232)}


def save(frame, name):
    kw = {'compression': {'method': 'gzip', 'mtime': 0}} if name.endswith('.gz') else {}
    frame.to_csv(OUT / name, index=False, **kw)


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


class Parts(io.RawIOBase):
    def __init__(self, paths):
        self.paths = iter(paths)
        self.current = None

    def readable(self):
        return True

    def readinto(self, b):
        while True:
            if self.current is None:
                try:
                    self.current = next(self.paths).open('rb')
                except StopIteration:
                    return 0
            n = self.current.readinto(b)
            if n:
                return n
            self.current.close()
            self.current = None

    def close(self):
        if self.current is not None:
            self.current.close()
        super().close()


q = pd.read_csv(BASE / 'timestamped-mbo-window-v1/consecutive_quote_books.csv.gz',
                dtype={k: 'int64' for k in CLOCKS})
assert len(q) == 22194 and q.known_by_ns.is_monotonic_increasing
assert (q.known_by_ns == q.receive_ns).all()
assert not q.duplicated(['known_by_ns', 'input_cursor', 'source_ordinal']).any()
byord = q.set_index('source_ordinal')
checkpoints, nearords, movement = [], set(), []
times = [-120, -60, -20, -5, -1, -.8, -.2, -.1, -.061, -.02, -.005,
         .001, .01, .02, .05, .1, .2, .3, .5, 1, 2, 5, 20, 60, 120, 300]
fixed = {375: {'B': [3155000000,3154000000,3153000000,3152000000,3151000000,3150000000,3147000000],
               'A': [3156000000,3155000000,3154000000,3153000000,3152000000,3148000000]},
         391: {'B': [3141000000,3140000000,3139000000,3138000000,3137000000,3136000000,3135000000],
               'A': [3143000000,3142000000,3141000000,3140000000,3139000000,3138000000,3137000000,3136000000]}}
case_near = {}
for case, (t, cap) in CASES.items():
    w = q[(q.known_by_ns >= t - 5_000_000_000) & (q.known_by_ns <= t + 5_000_000_000)].copy()
    case_near[case] = set(w.source_ordinal)
    nearords.update(w.source_ordinal)
    w['relative_known_by_ns'] = w.known_by_ns - t
    w['case_reference'] = case
    # Detect changes against the actual predecessor, including first selected row.
    changes = q.mid.diff().abs() > 1e-12
    movement.append(w.loc[q.loc[w.index].index[changes.loc[w.index]]])
    targets = [(str(s) + 's', t + round(s * 1e9), None) for s in times]
    targets += [('strict_pre', t - 1, cap), ('family_group', t, cap + 1)]
    for label, cutoff, cursorcap in targets:
        eligible = q[q.known_by_ns <= cutoff]
        if cursorcap is not None:
            eligible = eligible[eligible.input_cursor <= cursorcap]
        row = {'case_reference': case, 'checkpoint': label, 'cutoff_ns': cutoff,
               'cursor_cap': cursorcap if cursorcap is not None else '',
               'disposition': 'no_saved_predecessor' if eligible.empty else 'observed_asof'}
        if not eligible.empty:
            last = eligible.iloc[-1]
            # Fetch each integer from the typed column, never a mixed numeric row.
            ix = eligible.index[-1]
            row.update({k: int(q.at[ix, k]) for k in CLOCKS})
            row.update({k: float(last[k]) for k in ['best_bid','best_ask','mid','spread','bid_depth_n','ask_depth_n','bid_depth_full','ask_depth_full']})
            row.update(age_ns=cutoff - row['known_by_ns'], relative_known_by_ns=row['known_by_ns'] - t)
        checkpoints.append(row)
cp = pd.DataFrame(checkpoints)
# Missing boundaries remain blank strings; never let nullable clocks use float.
for k in CLOCKS + ['age_ns', 'relative_known_by_ns']:
    cp[k] = [str(r.get(k, '')) for r in checkpoints]
save(cp, 'checkpoints.csv')
save(pd.concat(movement), 'price-step-timeline.csv')
fullords = {int(s) for s in cp.source_ordinal if s != ''}
wanted = fullords | nearords
parts = sorted((BASE / 'timestamped-mbo-window-v1').glob('consecutive_bid_ask_levels.csv.gz.part*'))
assert len(parts) == 4
selected, count = [], 0
with io.BufferedReader(Parts(parts)) as stream, gzip.GzipFile(fileobj=stream) as gz:
    for c in pd.read_csv(gz, chunksize=200000, dtype={k: 'int64' for k in CLOCKS}):
        count += len(c)
        c = c[c.source_ordinal.isin(wanted)]
        keep = c.source_ordinal.isin(fullords) | (c['rank'] <= 15)
        for case in CASES:
            for side, prices in fixed[case].items():
                keep |= c.source_ordinal.isin(case_near[case]) & c.side.eq(side) & c.price_raw.isin(prices)
        selected.append(c.loc[keep].copy())
assert count == 10267320
levels = pd.concat(selected, ignore_index=True)
assert not levels.duplicated(['source_ordinal', 'side', 'price_raw']).any()
full = levels[levels.source_ordinal.isin(fullords)]
for ordinal, g in full.groupby('source_ordinal'):
    quote = byord.loc[ordinal]
    for side, prefix in [('B', 'bid'), ('A', 'ask')]:
        s = g[g.side == side]
        assert s['size'].sum() == quote[prefix + '_depth_full']
        assert s[s['rank'] <= 10]['size'].sum() == quote[prefix + '_depth_n']
        assert s[s['rank'] == 1].price.iloc[0] == quote['best_' + prefix]
save(full, 'checkpoint-full-ladders.csv.gz')
save(levels[levels.source_ordinal.isin(nearords)], 'nearby-queues-and-fixed-prices.csv.gz')
print('Selected levels and full checkpoint conservation verified', len(levels), flush=True)

touch = levels[levels['rank'] == 1].set_index(['source_ordinal', 'side'])
queue_summary = []
for row in checkpoints:
    if 'source_ordinal' not in row:
        continue
    r = dict(row)
    for side, prefix in [('B', 'bid'), ('A', 'ask')]:
        s = touch.loc[(r['source_ordinal'], side)]
        for col in ['size','order_count','front_order_size','front_order_age_s','queue_age_median_s','queue_age_p90_s','largest_order_share']:
            r[prefix + '_' + col] = float(s[col])
    queue_summary.append(r)
qs = pd.DataFrame(queue_summary)
save(qs, 'touch-queue-checkpoints.csv')
fixedrows = []
for case, (t, cap) in CASES.items():
    sub = levels[levels.source_ordinal.isin(case_near[case])].set_index(['source_ordinal','side','price_raw'])
    for ordinal in sorted(case_near[case]):
        for side, prices in fixed[case].items():
            for price in prices:
                idx = (ordinal, side, price)
                row = {'case_reference':case, 'source_ordinal':int(ordinal), 'side':side,'price_raw':price,
                       **{k:int(byord.at[ordinal,k]) for k in CLOCKS if k != 'source_ordinal'},
                       'relative_known_by_ns':int(byord.at[ordinal,'known_by_ns'])-t,
                       'present':idx in sub.index}
                if row['present']:
                    s = sub.loc[idx]
                    row.update({k:float(s[k]) for k in ['rank','size','order_count','front_order_size','front_order_age_s','queue_age_median_s','queue_age_p90_s','largest_order_share']})
                # Absent level is not zero executed volume; it means absent from full source ladder.
                fixedrows.append(row)
save(pd.DataFrame(fixedrows), 'fixed-price-queue-timeline.csv.gz')

# Only two instances' recorded context projections; no continuous trade tape is invented.
context, receipts = [], []
with gzip.open(BASE / 'descriptive-v1/complete_context_measurements.csv.gz', 'rt', newline='') as f:
    for r in csv.DictReader(f):
        if r['sample_id'].split(':')[0] in ['375','391']:
            context.append(r)
with gzip.open(BASE / 'descriptive-v1/group_context_receipts.csv.gz', 'rt', newline='') as f:
    for r in csv.DictReader(f):
        if r['sample_id'].split(':')[0] in ['375','391']:
            receipts.append(r)
save(pd.DataFrame(context), 'saved-context-measurements.csv.gz')
save(pd.DataFrame(receipts), 'saved-context-clock-receipts.csv')
forecast = pd.concat([pd.read_csv(REVIEW / f'instance-{i}-all-model-forecasts.csv', dtype=str, keep_default_na=False) for i in CASES])
save(forecast, 'original-all-model-forecasts.csv.gz')

fig, axes = plt.subplots(4,2,figsize=(15,13), constrained_layout=True)
for col,(case,(t,cap)) in enumerate(CASES.items()):
    for row,(lo,hi) in enumerate([(-120,300),(-1,2)]):
        s=q[(q.known_by_ns>=t+round(lo*1e9))&(q.known_by_ns<=t+round(hi*1e9))]
        x=(s.known_by_ns-t)/1e9
        axes[row,col].step(x,s.best_bid,where='post',label='Bid',lw=.9)
        axes[row,col].step(x,s.best_ask,where='post',label='Ask',lw=.9)
        axes[row,col].axvline(0,color='black',ls=':',label='Family reference' if row==0 else None)
        axes[row,col].set_ylabel('Observed quote price')
        axes[row,col].set_title(f'Episode portion near {case}: {lo} to +{hi} seconds')
    s=q[(q.known_by_ns>=t-5_000_000_000)&(q.known_by_ns<=t+5_000_000_000)]
    x=(s.known_by_ns-t)/1e9
    axes[2,col].step(x,s.bid_depth_n,where='post',label='Bid top 10')
    axes[2,col].step(x,s.ask_depth_n,where='post',label='Ask top 10')
    axes[2,col].set_ylabel('Displayed size')
    f=pd.DataFrame(fixedrows)
    price=3155000000 if case==375 else 3139000000
    f=f[f.case_reference.eq(case)&f.side.eq('B')&f.price_raw.eq(price)]
    axes[3,col].step(f.relative_known_by_ns/1e9, f['size'].fillna(0),where='post',label=f'Bid at {price/1e9:.3f}')
    axes[3,col].set_ylabel('Displayed size; absent level = 0')
    for row in [2,3]: axes[row,col].axvline(0,color='black',ls=':')
    for ax in axes[:,col]:
        ax.grid(alpha=.2);ax.legend(loc='best',fontsize=8);ax.set_xlabel('Seconds from family reference (not a trade entry)')
fig.suptitle('One connected trading episode: decline/continuation near 375 and drop/recovery near 391\nObserved completed-group states only; queue size changes do not identify executions or cancellations')
fig.savefig(OUT/'episode-comparison.png',dpi=160)
plt.close(fig)
dump('verification-receipt.json',{
    'quote_rows':len(q),'source_level_rows_streamed_once':count,'selected_level_rows':len(levels),
    'full_ladders_checked':len(fullords),'fixed_price_timeline_rows':len(fixedrows),
    'exact_clock_columns':CLOCKS,'strict_pre_caps':{str(i):{'cutoff_ns':t-1,'cursor_cap':c} for i,(t,c) in CASES.items()},
    'ladder_checks':'touch, full-size conservation, top10 conservation, unique side/absolute price',
    'missing_375_minus120_predecessor':'explicitly blank; not interpolated',
    'coverage_391_600s':False,'one_related_episode_not_independent_confirmations':True,
    'execution_tape_and_order_identity_reconstruction':False,
    'continuous_aggressor_first_detection_time':'not available in quote/level exports; only saved context samples',
    'semantic_coverage':'NOT_PASSED',
    'mlp_reproducibility':'unresolved occurrence 120s fold4 max prediction difference 0.4313412606716156; original attempt canonical',
    'no_new_fit_aws_call_or_live_execution':True})
print('Episode projections saved', OUT, flush=True)
