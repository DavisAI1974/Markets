"""Part 2 C/D/E. All distances and residuals precede interpretation; no fitted forecast."""
from common import *
from part1b import native_flow
from scipy.cluster.hierarchy import linkage, fcluster, leaves_list
from scipy.spatial.distance import pdist
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8})


def run(day):
    X=pd.read_csv(ROOT/f'tables/{day}-paths.csv.gz',dtype={'original_coverage':str},low_memory=False)
    M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv',dtype={'recognition_ns':'Int64','anchor_ns':'int64','original_coverage':str})
    C=pd.read_csv(ROOT/f'tables/{day}-candidate-operands.csv',dtype={'recognition_ns':'Int64','original_coverage':str})
    reconc=[];hier=[];members=[];counts=[]
    # Fixed common interval exists before minimum observed recognition lag. Every time coordinate retained.
    q=X[(X.kind=='candidate')&(X.relative_s>=-60)&(X.relative_s<=5)&(X.relative_s%1==0)]
    if day=='20231018':q=q[q.original_coverage!='none']
    # Different physical units remain separate; no amplitude normalization or imputation.
    blocks={'signed_ratio':['ratio'],'touch_lots':['bid_size','ask_size'],'quote_levels':['bid','ask'],'wire_trade_lots':['trade_B','trade_A']}
    for block,fields in blocks.items():
        mats=[q.pivot(index='candidate_id',columns='relative_s',values=f) for f in fields]
        arr=np.concatenate([m.to_numpy() for m in mats],axis=1);ids=mats[0].index.to_numpy();complete=np.isfinite(arr).all(axis=1)
        valid=arr[complete];vi=ids[complete]
        labels=np.zeros(len(ids),dtype=int);label_note='no positive merge gap'
        if len(valid)>=2:
            distances=pdist(valid,metric='cityblock');Z=linkage(distances,method='single');heights=Z[:,2]
            left,right=np.triu_indices(len(valid),1)
            save(pd.DataFrame({'left_candidate':vi[left],'right_candidate':vi[right],'distance':distances}),f'{day}-pair-distances-{block}.csv.gz')
            gaps=np.diff(np.r_[0,heights]);order=np.argsort(gaps)[::-1];gap_idx=int(order[0])
            # Display the data's largest separation in merge heights, and every alternative gap.
            low=heights[gap_idx-1] if gap_idx else 0.;high=heights[gap_idx];cut=(low+high)/2
            lab=fcluster(Z,cut,criterion='distance');labels[complete]=lab
            label_note='largest observed merge-height gap; descriptive cut, not a unique natural count'
            for i,z in enumerate(Z):hier.append(dict(day=day,representation=block,merge=i,left=int(z[0]),right=int(z[1]),distance=z[2],members=int(z[3]),gap=gaps[i],groups_before=len(valid)-i,largest_gap=i==gap_idx))
            fig,ax=plt.subplots(1,3,figsize=(14,max(4,(len(valid)+180)/140)))
            dv=np.sort(distances);ax[0].scatter(np.arange(len(dv)),dv,s=1);ax[0].set_title(f'Pair distances: in {len(dv)}, points {len(dv)}, excluded 0');ax[0].set_ylabel('raw cityblock distance')
            ax[1].scatter(np.arange(len(heights)),heights,s=5);ax[1].set_title(f'Merges: in {len(heights)}, points {len(heights)}, excluded 0');ax[1].set_ylabel('raw merge distance')
            rows=leaves_list(Z);im=ax[2].imshow(valid[rows],aspect='auto',interpolation='nearest');fig.colorbar(im,ax=ax[2]);ax[2].set_title(f'Path coordinates: in {arr.size}, cells {valid.size}\nundefined rows {int((~complete).sum())}');ax[2].set_xlabel('all time coordinates, consecutive field blocks')
            for panel,n in [('pair_distances',len(dv)),('merge_heights',len(heights))]:reconc.append(dict(figure=f'{day}-structure-{block}.png',panel=panel,rows_in=n,points_plotted=n,rows_excluded=0,reason='none'))
            reconc.append(dict(figure=f'{day}-structure-{block}.png',panel='coordinates',rows_in=arr.size,points_plotted=valid.size,rows_excluded=arr.size-valid.size,reason='entire rows with undefined ratio retained in disposition table; not imputed'))
            fig.suptitle(f'{day} {block}; no preset cluster count; no normalization');fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-structure-{block}.png',dpi=140);plt.close(fig)
        for ident,lab,ok,vec in zip(ids,labels,complete,arr):
            c=C[C.candidate_id==ident].iloc[0]
            members.append(dict(day=day,candidate_id=ident,representation=block,group=int(lab) if ok else None,orientation=c.orientation,disposition='complete' if ok else 'undefined_coordinates',undefined_coordinates=int((~np.isfinite(vec)).sum()),missing_pattern=''.join('1' if np.isfinite(x) else '0' for x in vec)))
        counts.append(dict(day=day,representation=block,candidates=len(ids),complete=int(complete.sum()),undefined_rows=int((~complete).sum()),groups_at_largest_gap=int(len(set(labels[complete]))),note=label_note))
    H=pd.DataFrame(hier);U=pd.DataFrame(members)
    save(H,f'{day}-all-hierarchy-merges.csv');save(U,f'{day}-grouping-members.csv');save(pd.DataFrame(counts),f'{day}-grouping-counts.csv');save(U.groupby(['representation','group','orientation'],dropna=False).size().reset_index(name='candidates'),f'{day}-grouping-orientation.csv')
    # Falsification ledger: every matched candidate/control, operational life to opposite-sign hold of 3 seconds.
    F=native_flow(day); sec=F.second.to_numpy();ratio=F.ratio.to_numpy();net=(F.roll_buy-F.roll_sell).to_numpy();total=F.total.to_numpy();buy=F.buy.to_numpy();sell=F.sell.to_numpy()
    residuals=[];life=[];life_paths=[]
    path_groups={key:g.sort_values('relative_s') for key,g in X.groupby(['candidate_id','kind'],sort=False)}
    for m in M.itertuples():
        sub=path_groups[(m.candidate_id,m.kind)];pre=sub[sub.relative_s==0].iloc[0]
        i=int(m.anchor_ns//S-sec[0]);last=min(len(F)-1,int((m.anchor_ns+round(m.lag_s*S))//S-sec[0])-1)
        base=dict(day=day,candidate_id=m.candidate_id,kind=m.kind,orientation=m.orientation)
        observed=np.sign(m.mid_change_ticks) if abs(m.mid_change_ticks)>1e-8 else 0
        for name,pred in [('flow_sign_determines_quote',np.sign(ratio[i]) if np.isfinite(ratio[i]) else np.nan),('depth_sign_determines_quote',np.sign(pre.bid_size-pre.ask_size)),('fixed_50s_nominal_lag',50)]:
            actual=observed if name!='fixed_50s_nominal_lag' else (m.available_second-m.birth_second if m.kind=='candidate' else np.nan)
            residuals.append(dict(**base,form=name,predicted=pred,observed=actual,residual=actual-pred,disposition='defined' if np.isfinite(pred) and pd.notna(actual) else 'undefined'))
        # Life definition, not a target imposed on the detector: first third consecutive second opposite to anchor sign.
        p=np.sign(ratio[i]) if np.isfinite(ratio[i]) else 0
        opposite=(np.sign(ratio[i+1:])==-p)&np.isfinite(ratio[i+1:]) if p else np.zeros(len(ratio)-i-1,bool)
        hits=np.flatnonzero(opposite[:-2]&opposite[1:-1]&opposite[2:]) if len(opposite)>=3 else np.array([],int)
        stop=i if not p else i+int(hits[0])+3 if len(hits) else len(F)-1
        finite=np.isfinite(ratio[i:stop+1]);vals=ratio[i:stop+1];dv=np.diff(np.abs(vals));finite_pairs=np.isfinite(dv)
        undefined=np.flatnonzero(~finite);changes=np.diff(net[i:stop+1]);maxn=float(np.max(np.abs(changes))) if len(changes) else np.nan
        life.append(dict(**base,anchor_ratio=ratio[i],life_seconds=(stop-i if p else np.nan),life_end_second=int(sec[stop]),disposition='opposite_hold3' if len(hits) else 'right_censored' if p else 'undefined_anchor_direction',first_undefined_after_anchor_s=int(undefined[0]) if len(undefined) else None,finite_adjacent_pairs=int(finite_pairs.sum()),magnitude_increases=int((dv[finite_pairs]>1e-12).sum()),magnitude_decreases=int((dv[finite_pairs]<-1e-12).sum()),magnitude_unchanged=int((abs(dv[finite_pairs])<=1e-12).sum()),max_net_change=maxn))
        for k in range(i+1,stop+1):
            fresh=buy[k]-sell[k];expiry=buy[k-20]-sell[k-20] if k>=20 else 0.
            predicted_net=net[k-1]+fresh-expiry;res=net[k]-predicted_net
            life_paths.append(dict(**base,relative_s=k-i,second=int(sec[k]),ratio=ratio[k],net=net[k],total=total[k],fresh_buy=buy[k],fresh_sell=sell[k],expired_buy=buy[k-20] if k>=20 else 0.,expired_sell=sell[k-20] if k>=20 else 0.,net_recurrence_residual=res,magnitude_delta=abs(ratio[k])-abs(ratio[k-1]) if np.isfinite(ratio[k]) and np.isfinite(ratio[k-1]) else np.nan))
        residuals.append(dict(**base,form='monotone_magnitude_decay',predicted=0,observed=int((dv[finite_pairs]>1e-12).sum()),residual=int((dv[finite_pairs]>1e-12).sum()),disposition='defined' if finite_pairs.any() else 'undefined'))
        residuals.append(dict(**base,form='constant_signed_numerator',predicted=0,observed=maxn,residual=maxn,disposition='defined' if np.isfinite(maxn) else 'undefined'))
    V=pd.DataFrame(residuals);LP=pd.DataFrame(life_paths);L=pd.DataFrame(life)
    save(V,f'{day}-operator-residuals.csv');save(L,f'{day}-life-measurements.csv');save(LP,f'{day}-life-paths.csv.gz')
    summary=[]
    for (form,kind,ori),q in V.groupby(['form','kind','orientation']):
        ok=q.disposition=='defined';r=q.loc[ok,'residual'].to_numpy();zero=np.isclose(r,0,atol=1e-12,rtol=0)
        summary.append(dict(day=day,form=form,kind=kind,orientation=ori,rows_in=len(q),defined=len(r),undefined=int((~ok).sum()),zero_residual=int(zero.sum()),counterexamples=int((~zero).sum())))
    for (kind,ori),q in LP.groupby(['kind','orientation']):
        r=q.net_recurrence_residual.to_numpy();summary.append(dict(day=day,form='signed_net_rolling_recurrence',kind=kind,orientation=ori,rows_in=len(q),defined=len(q),undefined=0,zero_residual=int((abs(r)<=1e-12).sum()),counterexamples=int((abs(r)>1e-12).sum())))
    save(pd.DataFrame(summary),f'{day}-operator-summary.csv')
    # Full residual and life-duration distributions, split SAME/FLIP and controls with counts.
    for ori in C.orientation.unique():
        fig,axes=plt.subplots(2,3,figsize=(14,8))
        for ax,form in zip(axes.flat, list(V.form.unique())+['life_seconds']):
            for kind,col in [('candidate','#285f9c'),('control1','#ca6c2e'),('control2','#477b48')]:
                q=(L if form=='life_seconds' else V[V.form==form]);q=q[(q.orientation==ori)&(q.kind==kind)];v=q['life_seconds' if form=='life_seconds' else 'residual'];valid=v.notna();arr=np.sort(v[valid].to_numpy());ax.scatter(np.arange(len(arr)),arr,s=4,label=f'{kind}: {len(q)}/{len(arr)}/{len(q)-len(arr)}',color=col,alpha=.7)
                reconc.append(dict(figure=f'{day}-operators-{ori}.png',panel=form+' '+kind,rows_in=len(q),points_plotted=len(arr),rows_excluded=len(q)-len(arr),reason='undefined operands or noncandidate nominal clock'))
            ax.set_title(form);ax.legend(fontsize=6,title='in / plotted / undefined',title_fontsize=6);ax.set_xlabel('ordered observation')
        fig.suptitle(f'{day} {ori}: all residuals; no model selection');fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-operators-{ori}.png',dpi=140);plt.close(fig)
    save(pd.DataFrame(reconc),f'{day}-part2-figure-reconciliation.csv')
    print(day,'structure',pd.DataFrame(counts)[['representation','complete','groups_at_largest_gap']].to_dict('records'),'life rows',len(LP),flush=True)
if __name__=='__main__':
 import sys;run(sys.argv[1])
