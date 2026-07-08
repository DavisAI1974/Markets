"""S74 ARCHETYPE ASCENT-EQUATION FIT — characterize the 4 per-cell mean arcs (the archetype PICTURES from
quad_means.npz) with a UNIQUE ascent equation each. Averaging is allowed HERE only to describe the archetype
shape (a picture of the archetype); the gate decision stays per-trade (that runs live elsewhere).

Pre-onset ignition limb = t in [-45,0]s (indices 0..450). We fit competing functional forms to the RISE
and report which wins + coefficients, per coin x cell. Scale-free measures only (the arc is already the
normalized imbalance ratio in [-1,1]).
"""
import numpy as np
np.set_printoptions(suppress=True)
d = np.load("quad_means.npz")
tsec = d["tsec"]; ON = int(np.argmin(np.abs(tsec)))     # onset index (t=0)
COINS = ["btc", "eth", "sol", "xrp"]                     # doge excluded
CELLS = ["short-loser", "short-winner", "long-winner", "long-loser"]

def r2(y, yhat):
    ss = ((y - y.mean())**2).sum()
    return 1.0 - ((y - yhat)**2).sum()/(ss + 1e-12)

def fit_forms(t, y):
    """Fit competing ascent forms on the pre-onset limb. t in seconds (-45..0), y = mean arc."""
    out = {}
    # 1) LINEAR  y = a + b t
    b, a = np.polyfit(t, y, 1)
    out["linear"] = dict(r2=r2(y, a + b*t), a=a, b=b)
    # 2) QUADRATIC y = a + b t + c t^2  (c>0 = convex/accelerating-in = hockey)
    c, b2, a2 = np.polyfit(t, y, 2)
    out["quad"] = dict(r2=r2(y, a2 + b2*t + c*t*t), a=a2, b=b2, c=c)
    # convexity vs chord: how far the MIDPOINT bows off the start->peak straight line
    chord = y[0] + (y[-1]-y[0]) * (t - t[0])/(t[-1]-t[0] + 1e-12)
    bow = y - chord                       # >0 above chord (concave/early), <0 below (convex/hockey)
    out["chord"] = dict(bow_mean=float(bow.mean()), bow_min=float(bow.min()), bow_max=float(bow.max()),
                        convexity=float(-bow.mean()))   # + => below chord => hockey-stick
    # 3) HOCKEY-STICK piecewise: flat handle then steep blade, breakpoint scan
    best = None
    for k in range(8, len(t)-8):
        tb = t[k]
        # handle slope (before break), blade slope (after)
        bh = np.polyfit(t[:k+1], y[:k+1], 1)[0]
        bl = np.polyfit(t[k:], y[k:], 1)[0]
        # two-segment continuous fit r2
        yh = np.piecewise(t, [t <= tb, t > tb],
                          [lambda tt: y[:k+1].mean() + bh*(tt - t[:k+1].mean()),
                           lambda tt: y[k:].mean() + bl*(tt - t[k:].mean())])
        rr = r2(y, yh)
        if best is None or rr > best["r2"]:
            best = dict(r2=rr, t_break=float(tb), b_handle=float(bh), b_blade=float(bl),
                        ratio=float(bl/(abs(bh)+1e-6)))
    out["hockey"] = best
    # 4) EXPONENTIAL toward peak: y = P - A exp(k t), k>0 accelerating up into t=0
    #    fit on shifted positive: solve via log on (P - y). P = peak + small margin
    P = y.max() + 0.02*(abs(y.max())+1e-3)
    z = P - y
    z = np.clip(z, 1e-6, None)
    kk, lnA = np.polyfit(t, np.log(z), 1)   # ln z = lnA + (-k) t  -> here slope = -k? z=A exp(-k t)... careful
    yhat = P - np.exp(lnA + kk*t)
    out["exp"] = dict(r2=r2(y, yhat), P=float(P), A=float(np.exp(lnA)), k=float(kk))
    return out

def summarize():
    for coin in COINS:
        print(f"\n########## {coin.upper()} ##########")
        for cell in CELLS:
            a = d[f"{coin}__{cell}"]
            if a.size == 0:
                print(f"  {cell:14} (no data)"); continue
            pre = a[:ON+1]; t = tsec[:ON+1]
            F = fit_forms(t, pre)
            peak = pre[-1]; start = pre[0]; mn = pre.min()
            # active-climb rate = dip->peak per second
            imin = int(np.argmin(pre)); ipk = int(np.argmax(pre))
            climb = (pre[ipk]-pre[imin])/((ipk-imin)*0.1) if ipk > imin else 0.0
            below = float((pre < 0).mean())
            print(f"  {cell:14} start={start:+.3f} peak={peak:+.3f} min={mn:+.3f} below0={below*100:4.0f}%"
                  f"  climb={climb:+.4f}/s")
            print(f"       LINEAR   r2={F['linear']['r2']:.3f}  b={F['linear']['b']:+.4f}")
            print(f"       QUAD     r2={F['quad']['r2']:.3f}  b={F['quad']['b']:+.4f} c={F['quad']['c']:+.5f}"
                  f"  (c>0=convex/hockey)")
            print(f"       convexity(below-chord)={F['chord']['convexity']:+.4f}  bow_min={F['chord']['bow_min']:+.3f} bow_max={F['chord']['bow_max']:+.3f}")
            print(f"       HOCKEY   r2={F['hockey']['r2']:.3f}  t_break={F['hockey']['t_break']:+.1f}s"
                  f"  b_handle={F['hockey']['b_handle']:+.4f} b_blade={F['hockey']['b_blade']:+.4f}"
                  f"  blade/handle={F['hockey']['ratio']:+.1f}")
            print(f"       EXP      r2={F['exp']['r2']:.3f}  k={F['exp']['k']:+.4f}")

if __name__ == "__main__":
    summarize()
