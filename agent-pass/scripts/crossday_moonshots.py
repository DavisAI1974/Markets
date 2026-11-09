"""Same M1/M2 distributions on four days, with common raw-unit scales per row."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8})
DAYS=['20231002','20231003','20231017','20231018']
recon=[]
near={d:pd.read_csv(ROOT/f'tables/{d}-detector-free-nearest.csv') for d in DAYS}
foot={d:pd.read_csv(ROOT/f'tables/{d}-first-footprint-events.csv') for d in DAYS}
for ori in ['SAME','FLIP','NO_PREDECESSOR']:
    fig,axes=plt.subplots(3,4,figsize=(18,10),sharey='row')
    for row,definition in enumerate(['quote_relocation','touch_size_change','wire_aggressor_run_start']):
      for col,day in enumerate(DAYS):
        q=near[day];q=q[(q.orientation==ori)&(q.definition==definition)];ok=q.recognition_advantage_s.notna();v=np.sort(q.loc[ok,'recognition_advantage_s']);a=axes[row,col];a.scatter(np.arange(len(v)),v,s=4);a.axhline(0,color='gray',lw=.5)
        a.set_title(f'{day}: in {len(q)}, points {len(v)}, unavailable {len(q)-len(v)}');a.set_ylabel(definition+'\nrecognition minus event seconds')
        recon.append(dict(figure=f'crossday-M1-{ori}.png',panel=day+' '+definition,rows_in=len(q),points_plotted=len(v),rows_excluded=len(q)-len(v),reason='finalization-only or no later structural event'))
    fig.suptitle(f'SPECULATIVE M1 {ori}: definitions compared on common scales; Oct 2/17 partial, Oct 18 all 863');fig.tight_layout(rect=(0,0,1,.96));fig.savefig(ROOT/'figures'/f'crossday-M1-{ori}.png',dpi=140);plt.close(fig)
    event_names=foot[DAYS[0]].event.unique()
    for page in range(2):
      fig,axes=plt.subplots(7,4,figsize=(18,20),sharey='row')
      for row,event in enumerate(event_names[7*page:7*(page+1)]):
       for col,day in enumerate(DAYS):
        a=axes[row,col]
        for kind,color in [('candidate','#285f9c'),('control1','#ca6c2e'),('control2','#477b48')]:
            q=foot[day];q=q[(q.orientation==ori)&(q.event==event)&(q.kind==kind)];ok=q.first_s.notna();v=np.sort(q.loc[ok,'first_s']);a.scatter(np.arange(len(v)),v,s=4,color=color,label=f'{kind} {len(q)}/{len(v)}/{len(q)-len(v)}')
            recon.append(dict(figure=f'crossday-M2-{ori}-{page+1}.png',panel=day+' '+event+' '+kind,rows_in=len(q),points_plotted=len(v),rows_excluded=len(q)-len(v),reason='event absent within lag'))
        a.set_title(day+' '+event);a.set_ylabel('first event from birth (seconds)');a.legend(title='in / plotted / absent',fontsize=5,title_fontsize=5)
      fig.suptitle(f'SPECULATIVE M2 {ori}: strictly before recognition, all event types, page {page+1}/2; Oct 2/17 partial, Oct 18 all 863');fig.tight_layout(rect=(0,0,1,.975));fig.savefig(ROOT/'figures'/f'crossday-M2-{ori}-{page+1}.png',dpi=140);plt.close(fig)
Z=pd.DataFrame(recon);assert (Z.rows_in==Z.points_plotted+Z.rows_excluded).all();save(Z,'crossday-moonshot-figure-reconciliation.csv');print('cross-day moonshot panels',len(Z))
