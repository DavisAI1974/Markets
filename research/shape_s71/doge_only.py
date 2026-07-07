import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = np.load("research/shape_s71/quad_means.npz")
t = d["tsec"]
types = [
    ("doge__long-winner",  "long-winner",  "#2ca02c"),
    ("doge__long-loser",   "long-loser",   "#9467bd"),
    ("doge__short-winner", "short-winner", "#ff7f0e"),
    ("doge__short-loser",  "short-loser",  "#d62728"),
]

fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)

# LEFT: all 4 doge types overlaid, doge's own scale
for k, lab, c in types:
    ax0.plot(t, d[k], color=c, lw=1.4, label=lab)
ax0.axvline(0, ls="--", color="0.4", lw=1)
ax0.axhline(0, color="0.75", lw=0.8)
ax0.axvspan(t.min(), 0, color="0.90", alpha=0.5, zorder=0)   # pre-fire region
ax0.set_title("DOGE only — 4 type-arcs overlaid (doge's own scale)")
ax0.set_xlabel("seconds relative to onset (t=0)")
ax0.set_ylabel("mean flow")
ax0.legend(loc="lower right", fontsize=9)
ax0.text(-42, ax0.get_ylim()[1]*0.92, "PRE-FIRE", fontsize=9, color="0.4", weight="bold")

# RIGHT: zoom the pre-onset limb only (the tradeable window)
m = (t >= -45) & (t <= 2)
for k, lab, c in types:
    ax1.plot(t[m], d[k][m], color=c, lw=1.6, label=lab)
ax1.axvline(0, ls="--", color="0.4", lw=1)
ax1.axhline(0, color="0.75", lw=0.8)
ax1.set_title("DOGE pre-fire limb only (t<0) — the ascension we gate on")
ax1.set_xlabel("seconds relative to onset (t=0)")
ax1.legend(loc="upper left", fontsize=9)

fig.suptitle("DOGE graphed separately — same 2x2 distinctions at doge's own numbers", fontsize=13, weight="bold")
fig.tight_layout(rect=[0,0,1,0.96])
fig.savefig("research/shape_s71/doge_only.png", dpi=130)
print("saved research/shape_s71/doge_only.png")

# quick numeric read of the pre-fire tells per type (native units)
print("\nPRE-FIRE tells (native flow units):")
print(f"{'type':14s} {'start@-45':>9s} {'peak@t=0area':>12s} {'slope[-20..0]':>13s}")
i0 = np.argmin(np.abs(t-0))
for k, lab, c in types:
    a = d[k]
    start = np.nanmean(a[(t>=-45)&(t<=-40)])
    peak  = np.nanmax(a[(t>=-5)&(t<=1)])
    seg   = (t>=-20)&(t<=0)
    slope = np.polyfit(t[seg], a[seg], 1)[0]
    print(f"{lab:14s} {start:9.3f} {peak:12.3f} {slope:13.4f}")
