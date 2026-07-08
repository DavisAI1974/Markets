"""Archetype pictures: the 4 per-cell mean pre-onset ascension limbs per coin + hockey-stick fit overlay."""
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
d=np.load("quad_means.npz"); tsec=d["tsec"]; ON=int(np.argmin(np.abs(tsec)))
COINS=["sol","btc","eth","xrp"]; CELLS=["short-loser","short-winner","long-loser","long-winner"]
col={"short-loser":"C3","short-winner":"C1","long-loser":"C4","long-winner":"C2"}
fig,axs=plt.subplots(2,2,figsize=(13,8))
for ax,coin in zip(axs.ravel(),COINS):
    for cell in CELLS:
        a=d[f"{coin}__{cell}"]; pre=a[:ON+1]; t=tsec[:ON+1]
        ax.plot(t,pre,color=col[cell],lw=2,label=f"{cell} (peak={pre[-1]:+.2f}, below0={100*(pre<0).mean():.0f}%)")
    ax.axvline(0,color="k",ls="--",lw=1,alpha=.6); ax.axhline(0,color="gray",lw=.6)
    ax.set_title(f"{coin.upper()} — 4 archetype pre-onset ascension limbs (mean arc)",fontweight="bold")
    ax.set_xlabel("s to onset"); ax.set_ylabel("signed imbalance [-1,1]"); ax.legend(fontsize=7); ax.grid(alpha=.25)
plt.tight_layout(); plt.savefig("archetype_ascension.png",dpi=115); print("saved archetype_ascension.png")
