"""S72 eyeball: 10 random winners + 10 random losers per cell — flow/exhaustion + price movement + exit
markers, on real individual trades (live run_kraken_cell legs, book-only, per-trade, no averaging)."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,"/home/user/Markets"); sys.path.insert(0,"/home/user/Markets/research/shape_s71")
sys.path.insert(0,"/home/user/Markets/scripts")
import arc_gate as AG
from arc_gate import load_raw, build_channels, median_spread_bps, run_kraken_cell, KRAKEN
CPS=10; SMOOTH=20; THETA=20.0   # price-turn = first retrace >=20bps from running favorable extreme
PRE=30*CPS; HZ=300*CPS          # show -30s .. +300s
def analyze(coin):
    path=f"/tmp/kbook/{coin}_book.jsonl"; cfg=[c for c in KRAKEN if c.coin==coin][0]
    raw=load_raw(path); ch,g=build_channels(path,cfg.K,20,raw=raw)
    mid=np.asarray(g["mid"],float); bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    hs=median_spread_bps(path,raw=raw)/2.0; N=len(mid)
    res,_=run_kraken_cell(cfg,mid,buy,sell,bb,ba,hs); flow=AG.rolling_imb(buy,sell,SMOOTH)
    W,L=[],[]
    for l in res.legs:
        o=int(l.open_idx); c=int(l.close_idx); s=int(l.side)
        if o-PRE<0 or o+HZ>=N or c<=o: continue
        (W if float(l.net_bps)>0 else L).append((o,c,s,float(l.net_bps)))
    return dict(mid=mid,flow=flow,W=W,L=L,coin=coin)

def price_turn(pf):  # first retrace >=THETA from running favorable max (t>0)
    rm=-1e9
    for i in range(len(pf)):
        rm=max(rm,pf[i])
        if pf[i]<rm-THETA: return i, rm
    return None, rm
def flow_zero(fl):   # after post-entry flow peak, first return to <=0
    pk=int(np.argmax(fl[:HZ+PRE])) if len(fl) else 0
    for i in range(max(pk,PRE),len(fl)):
        if fl[i]<=0: return i
    return None

def plot_coin(D, seed=0):
    coin=D["coin"]; mid=D["mid"]; flow=D["flow"]
    rng=np.random.default_rng(seed)
    def pick(pool):
        idx=rng.choice(len(pool),min(10,len(pool)),replace=False); return [pool[i] for i in idx]
    ws=pick(D["W"]); ls=pick(D["L"])
    fig,axs=plt.subplots(4,5,figsize=(22,13)); axs=axs.ravel()
    tsec=(np.arange(PRE+HZ+1)-PRE)*0.1
    for k,(grp,lab) in enumerate([(ws,"WIN"),(ls,"LOSE")]):
        for j,(o,c,s,net) in enumerate(grp):
            ax=axs[k*10+j]; lo=o-PRE; hi=o+HZ
            fl=flow[lo:hi+1]*s
            pf=s*(mid[lo:hi+1]-mid[o])/mid[o]*1e4
            ax.plot(tsec,fl,color="C0",lw=1.1); ax.axhline(0,color="0.6",lw=0.5)
            ax.axvline(0,color="k",ls="--",lw=0.8,alpha=0.6)
            ax2=ax.twinx(); ax2.plot(tsec,pf,color="C3",lw=1.1)
            csec=(c-o)*0.1
            if csec<=300: ax.axvline(csec,color="green",ls=":",lw=1.2)          # close/exit
            ti,_=price_turn(pf[PRE:]);                                          # price turn (post entry)
            if ti is not None: ax2.axvline(ti*0.1,color="red",lw=1.0,alpha=0.7)
            zi=flow_zero(fl)
            if zi is not None and zi<=PRE+HZ: ax.plot((zi-PRE)*0.1,0,"o",color="purple",ms=5)
            ax.set_title(f"{lab} net{net:+.0f}bp dur{csec:.0f}s",fontsize=8)
            ax.tick_params(labelsize=6); ax2.tick_params(labelsize=6)
    fig.suptitle(f"{coin}_kraken — 10 random WINNERS (top 2 rows) + 10 random LOSERS (bottom 2 rows)\n"
                 f"blue=flow/exhaustion (L axis)  red=price move bps (R axis)  black--=entry  "
                 f"green:=close  red|=price turn(>={THETA:.0f}bp retrace)  purple o=flow returns to 0",fontsize=11)
    fig.tight_layout(rect=[0,0,1,0.96])
    p=f"/tmp/kbook/{coin}_eyeball20.png"; fig.savefig(p,dpi=95); plt.close(); return p

if __name__=="__main__":
    for coin in ["btc","eth","sol","xrp","doge"]:
        D=analyze(coin); p=plot_coin(D)
        print(f"{coin}: W={len(D['W'])} L={len(D['L'])}  ->  {p}",flush=True)
