"""_s52_winner_persistence.py — S52 JOB 1b, step 1: is there LEG-OUTCOME PERSISTENCE per cell?

Entry-conviction sizing barely picks winners (Job 1a: corr(size,net)~+0.03 — it loads |move|, not wins).
Greg's ask is broader: size up on WINNERS beyond entry. The cleanest leakage-clean mechanism is SEQUENCE
sizing (anti-martingale): press size on leg i when the RECENT PRIOR legs (fully realized before i opens)
have been winning — i.e. the cell is in a working swing regime. This is causal by construction (only prior
realized legs), honestly exitable (a per-leg size multiplier on the same one-shot executor, no new inventory).

It only earns if leg outcomes PERSIST: win_i correlated with the recent prior win rate. This measures that on
the FORWARD LEDGER (25,845 trades, multi-window OOS), per cell:
  - lag-1 autocorrelation of net_bps and of the win indicator
  - does mean(net over prior k legs) predict sign / magnitude of next-leg net? (k = 3,5,10,20)
  - a shuffle control (destroy the ordering) — persistence must vanish under shuffle or it is a base-rate artifact
No trading yet; this decides whether a winner-side SIZE overlay can exist at all.
"""
import json, os
import numpy as np

LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper_ledger.jsonl")
rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
coins = ["sol", "doge", "xrp", "eth", "btc"]
KS = [3, 5, 10, 20]


def ac1(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def prior_mean_pred(net, k):
    """corr( mean(net over prior k legs) , this-leg net ). Causal: prior window strictly before i."""
    net = np.asarray(net, float)
    n = len(net)
    if n <= k + 2:
        return float("nan"), float("nan")
    pm, tgt = [], []
    for i in range(k, n):
        pm.append(net[i - k:i].mean()); tgt.append(net[i])
    pm, tgt = np.asarray(pm), np.asarray(tgt)
    c = float(np.corrcoef(pm, tgt)[0, 1]) if pm.std() > 1e-12 else float("nan")
    # conditional next-leg net when prior window is winning (>0) vs losing (<0)
    up = tgt[pm > 0].mean() if (pm > 0).any() else float("nan")
    dn = tgt[pm < 0].mean() if (pm < 0).any() else float("nan")
    return c, up - dn


print(f"=== S52 JOB 1b/step1 — leg-outcome PERSISTENCE per cell (forward ledger, {len(rows)} trades) ===\n")
out = {}
for c in coins:
    rs = [r for r in rows if r["coin"] == c]
    rs.sort(key=lambda r: r["ts"])
    net = [r["net_bps"] for r in rs]
    win = [1.0 if r["net_bps"] > 0 else 0.0 for r in rs]
    ac_net, ac_win = ac1(net), ac1(win)
    # shuffle control on lag-1 net autocorr
    rng = np.random.default_rng(0)
    shuf = [ac1(rng.permutation(net)) for _ in range(200)]
    z = (ac_net - np.mean(shuf)) / (np.std(shuf) + 1e-12)
    print(f"[{c.upper()}]  n={len(rs)}  mean_net={np.mean(net):+.2f}  win={100*np.mean(win):.0f}%")
    print(f"    lag-1 autocorr:  net {ac_net:+.3f}  win {ac_win:+.3f}   (shuffle z on net-AC = {z:+.1f})")
    preds = {}
    for k in KS:
        cc, spread = prior_mean_pred(net, k)
        preds[k] = dict(corr=cc, updn=spread)
        print(f"    prior-{k:>2} mean → next net:  corr {cc:+.3f}   E[next|prior>0]−E[next|prior<0] = {spread:+.2f} bps")
    out[c] = dict(n=len(rs), ac_net=ac_net, ac_win=ac_win, shuffle_z=float(z),
                  mean_net=float(np.mean(net)), win=float(np.mean(win)), preds=preds)
    print()

print("READING: if lag-1 net-AC is >0 with shuffle z>>2 AND prior-k mean predicts next-net (corr>0, up−dn>0),")
print("a causal anti-martingale SIZE overlay can add winner-side credit the entry-conviction sizing misses.")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s52_winner_persistence_results.json"), "w") as f:
    json.dump(out, f, indent=2)
