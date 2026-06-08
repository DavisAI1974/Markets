"""S26 (A): run the VALIDATED 128-dim per-pair dipole across the LARGER available set
in E:\refrag\discoveries\operator_discoveries, every tier, per pair, KEEP PAIRS SEPARATE.
Verbatim nearest-centroid construction from od_honest_val.py (the verified S25 harness),
plus:
  - permutation null z (real vs label-shuffle)            -> is separation real?
  - deterministic GROUPED split (sorted-filename halves)  -> honest floor (no time key exists)
  - algebraic dipole c_quad / R2_quad                     -> the surface
Tiers: '' (default/post-hoc, larger N, look-ahead), 'preentry' (20/20 honest),
       'preentry_cs100' (100/100 honest = the S25 validated set).
Writes JSON per tier + a combined summary. NO pooling, NO standardizing.
"""
import json, time
from pathlib import Path
import numpy as np

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
PAIRS = [
    "markets_btc_bybit_buy","markets_btc_bybit_sell","markets_btc_coinbase_buy","markets_btc_coinbase_sell",
    "markets_btc_kraken_buy","markets_btc_kraken_sell","markets_eth_bybit_buy","markets_eth_bybit_sell",
    "markets_eth_coinbase_buy","markets_eth_coinbase_sell","markets_eth_kraken_buy","markets_eth_kraken_sell",
]
K = 5
SEED = 1974
OUT = Path(r"C:\Users\A\AppData\Local\Temp\od_larger_set_results.json")
TIERS = ["", "preentry", "preentry_cs100"]

def load_coefs(domain):
    d = DISC / domain
    if not d.is_dir(): return []
    out = []
    for p in sorted(d.glob("*.json")):
        try: obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        c = obj.get("result", {}).get("operator_coefficients")
        if isinstance(c, list) and c: out.append([float(x) for x in c])
    return out

def strat_folds(y, k, rng):
    pos = np.where(y==1)[0].copy(); neg = np.where(y==0)[0].copy()
    rng.shuffle(pos); rng.shuffle(neg)
    return [np.sort(np.concatenate([pos[i::k], neg[i::k]])) for i in range(k)]

def _auc(sp, sn):
    if not len(sp) or not len(sn): return 0.5
    a = np.concatenate([sp, sn]); order = a.argsort(); a2 = a[order]
    r = np.empty(len(a2)); i = 0
    while i < len(a2):
        j = i
        while j < len(a2) and a2[j]==a2[i]: j += 1
        r[i:j] = (i+j+1)/2.0; i = j
    rk = np.empty(len(a)); rk[order] = r
    rpos = rk[np.concatenate([np.ones(len(sp),bool), np.zeros(len(sn),bool)])]
    U = rpos.sum() - len(sp)*(len(sp)+1)/2.0
    return U/(len(sp)*len(sn))

def kfold_acc_auc(X, y, rng):
    folds = strat_folds(y, K, rng)
    accs=[]; sp=[]; sn=[]
    for fi in range(K):
        te = folds[fi]; tr = np.concatenate([folds[j] for j in range(K) if j!=fi])
        Xw = X[tr][y[tr]==1]; Xl = X[tr][y[tr]==0]
        if len(Xw)==0 or len(Xl)==0: continue
        cw = Xw.mean(0); cl = Xl.mean(0)
        nw = np.linalg.norm(cw) or 1.0; nl = np.linalg.norm(cl) or 1.0
        d = cw/nw - cl/nl
        s = X[te] @ d
        accs.append(((s>0).astype(int)==y[te]).mean())
        sp.append(s[y[te]==1]); sn.append(s[y[te]==0])
    sp = np.concatenate(sp) if sp else np.array([]); sn = np.concatenate(sn) if sn else np.array([])
    auc = _auc(sp, sn)
    pooled = np.sqrt((sp.var()+sn.var())/2.0) if len(sp)>1 and len(sn)>1 else 0.0
    dcoh = (sp.mean()-sn.mean())/pooled if pooled>0 else 0.0
    return (np.mean(accs) if accs else 0.0), auc, dcoh

def grouped_split_acc(nw, nl):
    """Deterministic non-random split (NO time key exists): train on the first half of each
    class by sorted-filename order, test on the second half, and vice-versa; average.
    This removes the random-fold optimism (trades from the same sorted block are kept together)."""
    def one(Xw, Xl):
        hw=len(Xw)//2; hl=len(Xl)//2
        if hw<1 or hl<1 or len(Xw)-hw<1 or len(Xl)-hl<1: return None
        cw=Xw[:hw].mean(0); cl=Xl[:hl].mean(0)
        a=np.linalg.norm(cw) or 1.0; b=np.linalg.norm(cl) or 1.0
        d=cw/a-cl/b
        Xte=np.vstack([Xw[hw:],Xl[hl:]]); yte=np.array([1]*(len(Xw)-hw)+[0]*(len(Xl)-hl))
        return ((Xte@d>0).astype(int)==yte).mean()
    Xw=np.array(nw,float); Xl=np.array(nl,float)
    a=one(Xw,Xl); b=one(Xw[::-1],Xl[::-1])
    vals=[v for v in (a,b) if v is not None]
    return float(np.mean(vals)) if vals else None

def algebraic_r2(X, y):
    cw = X[y==1].mean(0); cl = X[y==0].mean(0)
    nw = np.linalg.norm(cw) or 1.0; nl = np.linalg.norm(cl) or 1.0
    Ha = X @ cw / nw; Hb = X @ cl / nl
    x = Ha*Hb; yy = Ha*Ha
    A = np.vstack([np.ones_like(x), x, x*x]).T
    coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
    pred = A @ coef; ss_res=((yy-pred)**2).sum(); ss_tot=((yy-yy.mean())**2).sum()
    r2 = 1 - ss_res/ss_tot if ss_tot>0 else 0.0
    return float(coef[2]), float(r2)

def run_tier(suffix, nperm=200):
    suf = f"_{suffix}" if suffix else ""
    rows=[]
    for pair in PAIRS:
        cw = load_coefs(f"{pair}_win{suf}"); cl = load_coefs(f"{pair}_lose{suf}")
        if not cw or not cl:
            rows.append({"pair":pair,"nw":len(cw),"nl":len(cl),"incomplete":True}); continue
        X = np.array(cw+cl,float); y=np.array([1]*len(cw)+[0]*len(cl))
        acc,auc,d = kfold_acc_auc(X,y,np.random.default_rng(SEED))
        null=[]
        for pi in range(nperm):
            yp=y.copy(); np.random.default_rng(SEED+1+pi).shuffle(yp)
            na,_,_=kfold_acc_auc(X,yp,np.random.default_rng(SEED+pi)); null.append(na)
        null=np.array(null); nm=float(null.mean()); nsd=float(null.std() or 1e-9)
        z=float((acc-nm)/nsd); p=float((null>=acc).mean())
        gs=grouped_split_acc(cw,cl)
        cq,r2=algebraic_r2(X,y)
        rows.append({"pair":pair,"nw":len(cw),"nl":len(cl),
                     "acc":round(float(acc),3),"auc":round(float(auc),3),"d_oof":round(float(d),2),
                     "null_acc":round(nm,3),"null_sd":round(nsd,3),"z":round(z,1),"p":round(p,3),
                     "grouped_acc":(round(gs,3) if gs is not None else None),
                     "c_quad":round(cq,2),"r2_quad":round(r2,3)})
    return rows

def main():
    t0=time.time()
    allres={}
    for tier in TIERS:
        print(f"\n#### TIER {tier or 'default(post-hoc)'} ####  ({time.time()-t0:.0f}s)")
        rows=run_tier(tier)
        allres[tier or "default"]=rows
        hdr=f"{'pair':28s}{'nw':>4s}{'nl':>4s}{'acc':>6s}{'auc':>6s}{'z':>7s}{'grp':>6s}{'c_q':>6s}{'R2q':>6s}"
        print(hdr); print("-"*len(hdr))
        zs=[]; accs=[]
        for r in rows:
            if r.get("incomplete"):
                print(f"{r['pair']:28s}{r['nw']:>4d}{r['nl']:>4d}  (incomplete)"); continue
            g = r['grouped_acc'] if r['grouped_acc'] is not None else float('nan')
            print(f"{r['pair']:28s}{r['nw']:>4d}{r['nl']:>4d}{r['acc']:>6.3f}{r['auc']:>6.3f}{r['z']:>+7.1f}{g:>6.3f}{r['c_quad']:>+6.1f}{r['r2_quad']:>6.3f}")
            zs.append(r['z']); accs.append(r['acc'])
        if zs:
            print(f"  -> mean acc {np.mean(accs):.3f}  mean z {np.mean(zs):+.1f}  pairs z>3: {sum(1 for z in zs if z>3)}/{len(zs)}")
        OUT.write_text(json.dumps(allres,indent=2),encoding="utf-8")
    print(f"\nDONE in {time.time()-t0:.0f}s -> {OUT}")

if __name__=="__main__":
    main()
