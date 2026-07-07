"""Regroup {duration x outcome} mean arcs BY TYPE across coins: 4 graphs, one type each, all 5 coins.
Saves lifted arcs to quad_means.npz for instant future regroups."""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
SP="/tmp/claude-0/-home-user-Markets/9c530e49-5a24-51c2-b8c4-60c751ae23a0/scratchpad"
sys.path.insert(0, SP)
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps, run_kraken_cell, KRAKEN)
CPS=10; PRE_SEC, POST_SEC, SMOOTH_SEC = 45, 60, 20
PRE, POST = PRE_SEC*CPS, POST_SEC*CPS
COINS=["btc","eth","sol","xrp","doge"]; TYPES=["short-loser","long-winner","short-winner","long-loser"]

def quad_means(coin):
    path=f"/tmp/kbook/{coin}_book.jsonl"; cfg=[c for c in KRAKEN if c.coin==coin][0]
    raw=load_raw(path); ch,g=build_channels(path,cfg.K,20,raw=raw)
    mid=np.asarray(g["mid"],float); bb=np.asarray(g["bidK"][1],float); ba=np.asarray(g["askK"][1],float)
    buy=np.asarray(g["buy"],float); sell=np.asarray(g["sell"],float)
    hs=median_spread_bps(path,raw=raw)/2.0; N=len(mid)
    res,_=run_kraken_cell(cfg,mid,buy,sell,bb,ba,hs); imb=rolling_imb(buy,sell,SMOOTH_SEC)
    arcs,dur,net=[],[],[]
    for l in res.legs:
        o=int(l.open_idx); c=int(l.close_idx)
        if o-PRE<0 or o+POST>=N or c<=o: continue
        arcs.append(imb[o-PRE:o+POST+1]*int(l.side)); dur.append((c-o)*0.1); net.append(float(l.net_bps))
    arcs=np.array(arcs); dur=np.array(dur); net=np.array(net)
    dmed=np.median(dur); short=dur<=dmed; longL=dur>dmed; win=net>0; lose=net<=0
    masks={"short-loser":short&lose,"long-winner":longL&win,"short-winner":short&win,"long-loser":longL&lose}
    return {k:(arcs[m].mean(0) if m.sum()>=8 else None) for k,m in masks.items()}

data={}
for c in COINS:
    print("computing",c,flush=True); data[c]=quad_means(c)
tsec=(np.arange(PRE+POST+1)-PRE)*0.1
np.savez(os.path.join(SP,"quad_means.npz"), tsec=tsec,
         **{f"{c}__{t}": (data[c][t] if data[c].get(t) is not None else np.array([])) for c in COINS for t in TYPES})
print("saved quad_means.npz",flush=True)
ccol=dict(zip(COINS, plt.cm.tab10(np.linspace(0,1,10))[:5]))
tcol={"short-loser":"(was RED)","long-winner":"(was GREEN)","short-winner":"(was ORANGE)","long-loser":"(was PURPLE)"}
fig,axs=plt.subplots(2,2,figsize=(15,9))
for ax,t in zip(axs.ravel(),TYPES):
    for c in COINS:
        m=data[c].get(t)
        if m is not None: ax.plot(tsec,m,color=ccol[c],lw=1.8,label=c)
    ax.axvline(0,color="k",ls="--",lw=1,alpha=0.6); ax.axhline(0,color="gray",lw=0.6)
    ax.set_title(f"{t.upper()} {tcol[t]} — all 5 coins overlaid",fontsize=12,fontweight="bold")
    ax.set_xlabel("seconds relative to onset (t=0)"); ax.set_ylabel("mean flow")
    ax.legend(fontsize=9,ncol=5,loc="lower left"); ax.grid(alpha=0.25)
fig.suptitle("Kraken onset->exhaustion arcs REGROUPED BY TYPE (each graph = one type, all coins)",fontsize=13)
plt.tight_layout(rect=[0,0,1,0.98]); pp=os.path.join(SP,"kraken_types_regrouped.png")
plt.savefig(pp,dpi=115); plt.close(); print("saved",pp,flush=True)
