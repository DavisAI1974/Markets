"""Plot saved quote transitions and individual prints; no source re-read or averaging."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as dates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1'
trades = json.loads((OUT / 'each-trade-exact-quote-order-analysis.json').read_text())
changes = json.loads((OUT / 'every-observed-quote-transition.json').read_text())
points = {}
for row in changes:
    for side in ['before', 'after']:
        ref = row[side + '_ref']
        points[ref['source_ordinal']] = (ref['known_by_ns'], row['observed_' + side])
quotes = [points[key] for key in sorted(points)]


def utc(values):
    return pd.to_datetime(values, unit='ns', utc=True)


fig, axes = plt.subplots(2, 1, figsize=(14, 8), constrained_layout=True)
for ax in axes:
    ax.scatter(utc([row[0] for row in quotes]), [row[1]['bid_raw'] / 1e9 for row in quotes],
               s=13, marker='s', color='#207b65', label='Recorded bid transition states')
    ax.scatter(utc([row[0] for row in quotes]), [row[1]['ask_raw'] / 1e9 for row in quotes],
               s=15, marker='^', color='#b47b2e', label='Recorded ask transition states')
    ax.scatter(utc([int(row['original_trade']['receive_ns']) for row in trades]),
               [int(row['original_trade']['price_raw']) / 1e9 for row in trades],
               s=28, color='#253b68', label='Individual trade print', zorder=4)
    ax.axvline(utc(1697582166000000000), color='#c45143', linestyle=':', label='Terminal dipole stage')
    ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M:%S', tz='UTC'))
    ax.grid(alpha=.18)
    ax.set_ylabel('Recorded price')
axes[0].set_title('Exact quote transitions and individual trades 118–149')
axes[0].legend(loc='upper left', fontsize=8)
axes[1].set_xlim(utc(1697582090000000000), utc(1697582340000000000))
axes[1].set_ylim(3.0635, 3.069)
axes[1].set_title('Tail: bid retreat, unchanged offer, further bid depletion and subsequent buys')
for row in trades:
    if row['trade_ordinal'] in [139, 142, 143, 144, 145, 146, 147, 148, 149]:
        axes[1].annotate(str(row['trade_ordinal']),
                         (utc(int(row['original_trade']['receive_ns'])), int(row['original_trade']['price_raw']) / 1e9),
                         xytext=(4, 7 if row['trade_ordinal'] != 148 else -12),
                         textcoords='offset points', fontsize=8)
axes[1].set_xlabel('UTC, October 17, 2023. All original records and integer clocks remain in the saved source chunks.')
fig.savefig(OUT / 'exact-quote-trade-path.png', dpi=140)
plt.close(fig)
print('Saved exact quote/trade path', flush=True)
