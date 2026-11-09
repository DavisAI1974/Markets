"""Independent recovered detector, with all inputs and counterexamples retained."""
from common import *
from bisect import insort
import heapq, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':8})

def native_flow(day):
    f=ROOT/'cache'/f'native-flow-{day}.csv.gz'
    if f.exists(): return pd.read_csv(f)
    import databento as db
    G=groups(day); F=flow(day); seconds=F.second.to_numpy(); buy=np.zeros(len(F));sell=buy.copy();unknown=buy.copy()
    sources=[(day,0)] if day in ('20231002','20231017') else [(str(int(day)-1),-808453 if day=='20231003' else -841601),(day,4889 if day=='20231003' else 17375)]
    gi=0;pending=[];checks=0;orders={};levels={'B':{},'A':{}};heaps={'B':[],'A':[]}
    def remove(o):
        side,p,size=o;levels[side][p]-=size
    def top(side):
        h=heaps[side];sgn=-1 if side=='B' else 1
        while h and levels[side].get(sgn*h[0],0)<=0: heapq.heappop(h)
        return sgn*h[0] if h else None
    for d,offset in sources:
      b=blob(f'data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{d}.dbn.zst',TAPE)
      for ix,r in enumerate(db.DBNStore.from_bytes(b)):
        cursor=ix+offset
        if cursor>G.cursor.iloc[-1]:break
        act,side=str(r.action),str(r.side);p,size,oid=int(r.price),int(r.size),int(r.order_id)
        if act=='T' and cursor>=0:
            bb,aa=top('B'),top('A')
            # Preserve native floating midpoint comparison, including exact-mid cases.
            mid=.5*(bb/S+aa/S) if bb is not None and aa is not None and aa>=bb else None
            cls='buy' if mid is not None and p/S>mid else 'sell' if mid is not None and p/S<mid else 'unknown'
            pending.append((cls,size))
        if act=='R':orders={};levels={'B':{},'A':{}};heaps={'B':[],'A':[]}
        elif act in ('A','C','M'):
            before=orders.pop(oid,None)
            if before:remove(before)
            after=(before[0],before[1],max(0,before[2]-size)) if act=='C' and before else (side,p,size) if act in ('A','M') else None
            if after and after[2]>0 and after[0] in levels:
                s,px,q=after;orders[oid]=after;levels[s][px]=levels[s].get(px,0)+q;heapq.heappush(heaps[s],-px if s=='B' else px)
        if cursor>=0 and gi<len(G) and cursor==G.cursor.iloc[gi]:
            g=G.iloc[gi];bb,aa=top('B'),top('A')
            if g.good and pd.notna(g.bid_raw) and pd.notna(g.ask_raw):
                assert (bb,aa)==(g.bid_raw,g.ask_raw),(day,cursor,bb,aa,g.bid_raw,g.ask_raw)
                assert (levels['B'][bb],levels['A'][aa])==(g.bid_size,g.ask_size)
                checks+=1
            k=int(g.receive_ns//S-seconds[0])
            if 0<=k<len(F):
                for cls,q in pending:{'buy':buy,'sell':sell,'unknown':unknown}[cls][k]+=q
            pending=[];gi+=1
    assert gi==len(G)
    out=pd.DataFrame(dict(second=seconds,buy=buy,sell=sell,unknown=unknown))
    out['roll_buy']=out.buy.rolling(20,min_periods=1).sum();out['roll_sell']=out.sell.rolling(20,min_periods=1).sum();out['total']=out.roll_buy+out.roll_sell;out['ratio']=(out.roll_buy-out.roll_sell)/out.total.replace(0,np.nan)
    out.to_csv(f,index=False,compression='gzip');print(day,'action-book quote checks',checks,flush=True);return out

def detect(F):
    """Source-equivalent rule; incremental quantile avoids repeatedly sorting history."""
    vals=F.ratio.to_numpy();sec=F.second.to_numpy();ordered=[];first=None;pending=[];found=[];last=None;audits=[]
    def release(now,truncate=False):
        nonlocal pending,last
        while pending:
            op=pending[0]['birth_second'];close=op+50
            if not truncate and now<close:break
            group=[c for c in pending if c['birth_second']<op+45]
            win=max(group,key=lambda c:(c['prominence'],c['magnitude']))
            pending=[c for c in pending if c['birth_second']>=win['birth_second']+45]
            last=win['birth_second'];found.append(dict(win,available_second=close,window_open=op,window_truncated=truncate,competing_peaks=len(group)))
    for i,v in enumerate(vals):
        if np.isfinite(v):
            insort(ordered,abs(v))
            if first is None:first=int(sec[i])
        j=i-5
        if j<5:continue
        t=int(sec[j]);x=vals[j];reason='qualifying'
        if i+1<=900 or len(ordered)<600:reason='warmup'
        elif not np.isfinite(x):reason='undefined'
        elif abs(x)<1e-12:reason='zero'
        else:
            pos=.85*(len(ordered)-1);lo=math.floor(pos);hi=math.ceil(pos)
            threshold=ordered[lo] if lo==hi else ordered[lo]*(hi-pos)+ordered[hi]*(pos-lo)
            if abs(x)<threshold:reason='below_recorded_rule_quantile'
            elif abs(x)<np.nanmax(np.abs(vals[j-5:j+6]))-1e-12:reason='not_local_maximum'
            else:
                h=np.abs(vals[max(0,j-30):j-9]);h=h[np.isfinite(h)];baseline=float(np.median(h)) if len(h) else 0.
                c=dict(birth_second=t,polarity=1 if x>0 else -1,magnitude=abs(x),baseline=baseline,prominence=abs(x)-baseline,threshold=threshold,observations_behind_threshold=len(ordered),searched_span_seconds=t-first+1)
                if last is not None and t-last<45:reason='within_winner_refractory'
                else:pending.append(c)
        audits.append((t,reason));release(int(sec[i]))
    release(int(sec[-1]));release(int(sec[-1]),True)
    return pd.DataFrame(found),pd.DataFrame(audits,columns=['second','disposition'])

def run(day):
    C,rs=candidates(day);F=flow(day);N=native_flow(day);G=groups(day);summ=[];joins=[]
    for name,f in [('completed_group',F),('native_action',N)]:
        D,A=detect(f);D['variant']=name;save(D,f'{day}-detected-{name}.csv');save(A,f'{day}-seconds-disposition-{name}.csv.gz')
        J=C.merge(D,on='birth_second',how='outer',suffixes=('_recorded','_recovered'),indicator=True);J['variant']=name
        J['birth_disposition']=J['_merge'].astype(str).map({'both':'matched','left_only':'missed','right_only':'added'});J=J.drop(columns='_merge')
        # Clock comparison retains finalization-only candidates without a live recognition.
        J['nominal_timing_difference_s']=J.available_second_recovered-J.available_second_recorded
        valid=J.available_second_recovered.notna() & ~J.window_truncated_recovered.fillna(True).astype(bool)
        # Native closes second s on first group with integer second > s.
        J['recovered_recognition_ns']=pd.Series([str(int(G.receive_ns.iloc[np.searchsorted(G.receive_ns.to_numpy(),(int(v)+1)*S,side='left')])) if ok and np.searchsorted(G.receive_ns.to_numpy(),(int(v)+1)*S,side='left')<len(G) else None for v,ok in zip(J.available_second_recovered,valid)],index=J.index)
        save(J[J.birth_disposition!='matched'],f'{day}-birth-differences-{name}.csv');joins.append(J)
        summ.append(dict(day=day,variant=name,recorded=len(C),recovered=len(D),matched=int((J.birth_disposition=='matched').sum()),missed=int((J.birth_disposition=='missed').sum()),added=int((J.birth_disposition=='added').sum()),nominal_exact=int(((J.birth_disposition=='matched')&(J.nominal_timing_difference_s==0)).sum())))
    save(pd.concat(joins,ignore_index=True),f'{day}-detector-all-comparisons.csv');save(pd.DataFrame(summ),f'{day}-detector-summary.csv')
    L=C.copy();L['nominal_lag_s']=L.available_second-L.birth_second;L['recognition_lag_s']=(L.recognition_ns-L.birth_second*S)/S;L['dispatch_lag_s']=(L.recognition_ns-L.available_second*S)/S
    L=L.merge(detect(N)[0][['birth_second','window_open','competing_peaks']],on='birth_second',how='left');L['winning_offset_s']=L.birth_second-L.window_open
    save(L,f'{day}-lag-measurements.csv')
    recon=[];fig,axes=plt.subplots(2,3,figsize=(13,8))
    for ax,col in zip(axes.flat,['nominal_lag_s','dispatch_lag_s','recognition_lag_s','winning_offset_s','observations_behind_threshold','searched_span_seconds']):
        valid=L[col].notna();v=np.sort(L.loc[valid,col].to_numpy());ax.scatter(np.arange(len(v)),v,s=5);ax.set_title(f'{col}\nin {len(L)}; points {len(v)}; unavailable {len(L)-len(v)}');ax.set_xlabel('ordered observation');recon.append(dict(figure=f'{day}-lag-distributions.png',panel=col,rows_in=len(L),points_plotted=len(v),rows_excluded=len(L)-len(v),reason='finalization-only or no recovered matching birth'))
    fig.tight_layout();fig.savefig(ROOT/'figures'/f'{day}-lag-distributions.png',dpi=140);plt.close(fig);save(pd.DataFrame(recon),f'{day}-detector-figure-reconciliation.csv')
    # All unequal operand rows retained, not only aggregate match rates.
    print(pd.DataFrame(summ).to_string(index=False),flush=True)
if __name__=='__main__':
    import sys;run(sys.argv[1])
