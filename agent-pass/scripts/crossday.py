"""Side-by-side replication, with counts for every rendered series."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8})
DAYS=['20231002','20231003','20231017','20231018']
def run():
    R=[];summary=[]
    for ori in ['SAME','FLIP','NO_PREDECESSOR']:
        fig,axes=plt.subplots(3,4,figsize=(18,11),sharey='row')
        for col,day in enumerate(DAYS):
            M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv');L=pd.read_csv(ROOT/f'tables/{day}-life-measurements.csv');B=pd.read_csv(ROOT/f'tables/{day}-lag-measurements.csv')
            for row,(table,field) in enumerate([(M,'mid_change_ticks'),(L,'life_seconds'),(B,'recognition_lag_s')]):
                ax=axes[row,col];q=table[table.orientation==ori].copy()
                if 'kind' not in q:q['kind']='candidate'
                for kind,color in [('candidate','#285f9c'),('control1','#ca6c2e'),('control2','#477b48')]:
                    part=q[q.kind==kind];valid=part[field].notna()
                    if field=='life_seconds':valid&=part.disposition!='undefined_anchor_direction'
                    v=np.sort(part.loc[valid,field]);ax.scatter(np.arange(len(v)),v,s=4,label=f'{kind}: {len(part)}/{len(v)}/{len(part)-len(v)}',color=color)
                    R.append(dict(figure=f'crossday-{ori}.png',panel=day+' '+field+' '+kind,rows_in=len(part),points_plotted=len(v),rows_excluded=len(part)-len(v),reason='undefined direction or finalization-only live clock'))
                ax.set_title(day+' '+('partial' if day in ['20231002','20231017'] else 'all 863: includes 11 seam supplements' if day=='20231018' else 'full archived'));ax.set_ylabel('SPECULATIVE lifetime: third opposite\nsecond or tape-end censoring (s)' if field=='life_seconds' else field);ax.legend(title='in / plotted / unavailable',fontsize=6,title_fontsize=6)
        fig.suptitle(ori+': archived live populations side by side; Oct 18 includes 11 beyond the 852 primary subset');fig.tight_layout(rect=(0,0,1,.96));fig.savefig(ROOT/'figures'/f'crossday-{ori}.png',dpi=140);plt.close(fig)
    for day in DAYS:
        C=pd.read_csv(ROOT/f'tables/{day}-candidate-operands.csv');M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv');r=json.loads((ROOT/f'{day}-part1a-receipt.json').read_text());s=pd.read_csv(ROOT/f'tables/{day}-detector-summary.csv')
        summary.append(dict(day=day,scope='partial_archived' if day in ['20231002','20231017'] else 'full_archived',candidates=len(C),live=int(C.recognition_ns.notna().sum()),finalization_only=int(C.recognition_ns.isna().sum()),path_rows=r['path_rows'],controls=r['matched_controls'],groups=r['groups'],native_matches=int(s[s.variant=='native_action'].matched.iloc[0]),completed_group_missed=int(s[s.variant=='completed_group'].missed.iloc[0]),completed_group_added=int(s[s.variant=='completed_group'].added.iloc[0])))
    save(pd.DataFrame(summary),'crossday-summary.csv');save(pd.DataFrame(R),'crossday-figure-reconciliation.csv')
    print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':run()
