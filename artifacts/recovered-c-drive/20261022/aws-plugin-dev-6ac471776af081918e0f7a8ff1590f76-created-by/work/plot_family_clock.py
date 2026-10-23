import csv
import datetime as dt
import pathlib
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

output = pathlib.Path(__file__).resolve().parents[1] / 'outputs'
with (output / 'price-curve-timestamps.csv').open() as handle:
    trades = list(csv.DictReader(handle))
with (output / 'family-start-timestamps.csv').open() as handle:
    families = list(csv.DictReader(handle))
zone = ZoneInfo('America/New_York')
def display_time(ns):
    # Float conversion is only for the rendered axis. Source nanoseconds stay
    # unchanged as integers in the exported data.
    return dt.datetime.fromtimestamp(int(ns) / 1e9, tz=zone)
times = [display_time(row['receive_ns']) for row in trades]
prices = [float(row['price']) for row in trades]
stamp = 'first_observed_recv_ns'
if stamp not in families[0]:
    raise ValueError('Inspect family timestamp columns before rendering')
starts = [display_time(row[stamp]) for row in families]
fig, (top, rug) = plt.subplots(2,1,figsize=(13,5.5),sharex=True,gridspec_kw={'height_ratios':[4,0.8]},layout='constrained')
top.plot(times,prices,color='#2563a6',linewidth=0.7)
top.set_title('Family anchors and timestamped trade prices',loc='left',fontsize=16,pad=14)
top.set_ylabel('Traded price (source units)')
top.grid(axis='y',alpha=0.2)
top.text(0.01,0.02,'30,739 original trade prints; no smoothing or price backfill',transform=top.transAxes,fontsize=9,color='#425466')
rug.eventplot(starts,colors='#c55b29',linewidths=0.65,linelengths=0.7)
rug.set_yticks([])
rug.set_ylabel('749 family\nfirst sightings',fontsize=9,rotation=0,labelpad=58,va='center')
rug.set_ylim(0.5,1.5)
rug.xaxis.set_major_locator(mdates.HourLocator(interval=3,tz=zone))
rug.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M',tz=zone))
rug.set_xlabel('Original receive clock · America/New_York · October 17–18, 2023')
left=min(min(starts)-dt.timedelta(minutes=2),min(times))
right=max(max(starts),max(times))
rug.set_xlim(left,right)
if min(starts)<min(times):
    top.axvspan(left,min(times),color='#dce3eb',alpha=0.55,zorder=-1)
    top.text(left+(min(times)-left)/2,top.get_ylim()[0]+0.55*(top.get_ylim()[1]-top.get_ylim()[0]),'No trade prints\nin this export',ha='center',fontsize=8,color='#566475',rotation=90)
for axis in [top,rug]:
    axis.spines[['top','right']].set_visible(False)
fig.savefig(output/'family-price-timeline.png',dpi=180)
fig.savefig(output/'family-price-timeline.svg')
print(output/'family-price-timeline.png')
