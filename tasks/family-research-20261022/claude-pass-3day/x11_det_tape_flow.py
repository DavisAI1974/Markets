import sys; sys.path.insert(0,'.')
from x11_det_emu import *
W='/home/claude/work/derived'
def per_second(d, mode):
    R=pd.read_parquet(f'{W}/recon_{d}.parquet'); G=np.load(f'{W}/groups_{d}.npz')
    T=R[R.action=='T']
    ts=T.ts_recv.astype('int64').to_numpy()  # ns
    recv=G['recv_ns']; mid=(G['bid_px']+G['ask_px'])/2e9; px=T.px_idx.to_numpy()*0.001  # price index units
    gi=np.searchsorted(recv,ts,side='left')    # containing group close
    ok=gi<len(recv)
    gsec=(recv[np.minimum(gi,len(recv)-1)]//10**9)
    prevmid=mid[np.maximum(np.searchsorted(recv,ts,side='left')-1,0)]
    sz=T['size'].to_numpy(float)
    if mode=='H1':
        cls=np.where(px>prevmid+1e-9,1,np.where(px<prevmid-1e-9,-1,0))
    elif mode=='H2':
        cls=np.where(T.side.to_numpy()=='B',1,np.where(T.side.to_numpy()=='A',-1,0))
    df=pd.DataFrame(dict(sec=gsec[ok],cls=cls[ok],sz=sz[ok]))
    b=df[df.cls==1].groupby('sec').sz.sum(); s=df[df.cls==-1].groupby('sec').sz.sum(); u=df[df.cls==0].groupby('sec').sz.sum()
    return b,s,u,T
if __name__=='__main__':
    d=sys.argv[1]; S,top,ops=load(d); X=S.set_index('second')
    for mode in ('H1','H2'):
        b,s,u,T=per_second(d,mode)
        mb=b.reindex(X.index).fillna(0); ms=s.reindex(X.index).fillna(0); mu=u.reindex(X.index).fillna(0)
        print(mode,'trades',len(T),'sum buy mine',mb.sum(),'comp',X.buy.sum(),' sell',ms.sum(),X.sell.sum(),' unk',mu.sum(),X.unknown.sum())
        print('  seconds equal buy',(mb==X.buy).mean().round(4),'sell',(ms==X.sell).mean().round(4),'unk',(mu==X.unknown).mean().round(4))

def series(d, mode, S):
    """per-second buy/sell lots and 20 s rolling ratio over the companion's second grid for classification mode"""
    R=pd.read_parquet(f'{W}/recon_{d}.parquet'); G=np.load(f'{W}/groups_{d}.npz')
    T=R[R.action=='T']; ts=T.ts_recv.astype('int64').to_numpy(); recv=G['recv_ns']; mid=(G['bid_px']+G['ask_px'])/2e9
    px=T.px_idx.to_numpy()*0.001; gi=np.searchsorted(recv,ts,side='left'); ok=gi<len(recv)
    gsec=recv[np.minimum(gi,len(recv)-1)]//10**9; pm=mid[np.maximum(gi-1,0)]
    side=np.where(T.side.to_numpy()=='B',1,np.where(T.side.to_numpy()=='A',-1,0))
    h1=np.where(px>pm+1e-9,1,np.where(px<pm-1e-9,-1,0))
    cls={'H1':h1,'H2':side,'HYB':np.where(h1!=0,h1,side)}[mode]
    sz=T['size'].to_numpy(float)
    df=pd.DataFrame(dict(sec=gsec[ok],cls=cls[ok],sz=sz[ok]))
    idx=S.second.to_numpy()
    b=df[df.cls==1].groupby('sec').sz.sum().reindex(idx).fillna(0).to_numpy(); s=df[df.cls==-1].groupby('sec').sz.sum().reindex(idx).fillna(0).to_numpy()
    rb=pd.Series(b).rolling(20,min_periods=1).sum().to_numpy(); rs=pd.Series(s).rolling(20,min_periods=1).sum().to_numpy()
    tot=rb+rs; ratio=np.where(tot>0,(rb-rs)/np.where(tot>0,tot,1),np.nan)
    return ratio
