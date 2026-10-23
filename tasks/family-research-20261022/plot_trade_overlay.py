"""Plot individual observed records for the saved combined trade example."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as dates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1'
case = json.loads((OUT / 'trade-dipole-overlay-example.json').read_text())
external = json.loads((OUT / 'trade-dipole-external-overlay.json').read_text())
trades = case['original_trades']
stages = case['original_supporting_path']['original_record']['dipole']['stages']


def utc(values):
    return pd.to_datetime(values, unit='ns', utc=True)


fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True, constrained_layout=True)
axes[0].scatter(utc([int(t['receive_ns']) for t in trades]),
                [int(t['price_raw']) / 1e9 for t in trades], s=28, color='#246584')
for trade in trades:
    if int(trade['source_ordinal']) in [122, 143, 144, 146, 147]:
        axes[0].annotate(trade['source_ordinal'], (utc(int(trade['receive_ns'])), int(trade['price_raw']) / 1e9),
                         xytext=(3, 7), textcoords='offset points', fontsize=8)
axes[0].set_ylabel('Actual trade price')
axes[0].set_title('Trades 118–149 with supporting dipole and external readings')
x = utc([s['recv_ns'] for s in stages])
axes[1].scatter(x[1:], [s['signed_flow'] for s in stages[1:]], s=10, color='#7f4a85')
axes[1].scatter(x[:1], [stages[0]['signed_flow']], s=35, facecolors='none', edgecolors='#7f4a85')
axes[1].annotate('Stage 0 timing open', (x[0], stages[0]['signed_flow']),
                 xytext=(-105, 17), textcoords='offset points', fontsize=8)
axes[1].scatter(x[-3:], [s['signed_flow'] for s in stages[-3:]], s=40, color='#bd4b3c', zorder=3)
axes[1].set_ylabel('Signed lots\nrolling 20 seconds')
axes[1].text(.01, .94, 'Three negative terminal readings; no fresh trade in those three seconds',
             transform=axes[1].transAxes, va='top', fontsize=9)
axes[2].scatter(x[1:], [s['bid_depth'] for s in stages[1:]], s=8, color='#227b6b', label='Stored full bid depth')
axes[2].scatter(x[1:], [s['ask_depth'] for s in stages[1:]], s=8, color='#a56a2a', label='Stored full ask depth')
axes[2].scatter(x[:1], [stages[0]['bid_depth']], s=35, facecolors='none', edgecolors='#227b6b')
axes[2].scatter(x[:1], [stages[0]['ask_depth']], s=35, facecolors='none', edgecolors='#a56a2a')
axes[2].set_ylabel('Stored stage depth')
axes[2].legend(loc='upper left', fontsize=8)
for name, color, label in [('mos.GFS.gw_hdd_D', '#3f6399', 'October 18 HDD'),
                            ('mos.GFS.gw_hdd_D1', '#c17b29', 'October 19 HDD')]:
    source = next(s for s in external['original_series'] if s['name'] == name)
    readings = [source['original_last_published_row_at_first_selected_trade'],
                source['original_last_published_row_at_trade143']]
    # Anchor the already-published background value to the first shown trade,
    # explicitly labelling its earlier publication rather than backfilling a new observation.
    axes[3].scatter(utc([int(trades[0]['receive_ns']), readings[1]['published_ns']]),
                    [r['value'] for r in readings], s=40, color=color, label=label)
    for i, reading in enumerate(readings):
        when = int(trades[0]['receive_ns']) if i == 0 else reading['published_ns']
        axes[3].annotate(str(reading['value']) + (' (earlier release)' if i == 0 else ' (new release)'),
                         (utc(when), reading['value']), xytext=(5, 6), textcoords='offset points', fontsize=8)
axes[3].set_ylabel('GFS forecast HDD')
axes[3].margins(y=.2)
axes[3].legend(loc='lower right', fontsize=8)
for ax in axes:
    ax.axvline(utc(1697582166000000000), color='#bd4b3c', alpha=.55, linewidth=1)
    ax.axvline(utc(1697581800000000000), color='#667b89', alpha=.5, linewidth=1, linestyle=':')
    ax.grid(alpha=.18)
axes[3].xaxis.set_major_formatter(dates.DateFormatter('%H:%M', tz='UTC'))
axes[3].set_xlabel('UTC, October 17, 2023. Source clocks and all raw records remain in the companion JSON.')
fig.savefig(OUT / 'trade-dipole-overlay.png', dpi=140)
plt.close(fig)
print('Saved individual-observation trade overlay', flush=True)
