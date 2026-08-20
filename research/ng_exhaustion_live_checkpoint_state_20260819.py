#!/usr/bin/env python3
from __future__ import annotations

import gzip, json, math, re
from datetime import datetime
from pathlib import Path
import numpy as np

TICK = 0.001
PRICE_LAGS = (1,2,3,5,10,20,30,60,120)
RANGE_WINDOWS = (5,20,60)
FLOW_WINDOWS = (1,3,5,10,20,30,60)
BOOK_LAGS = (0,1,2,3,5,10,20,30,60)
POLICY = "USE_OBSERVED_PRICE_DIRECTION_FLOW_DIPOLE_BOOK_AND_CLOCK_STATE_THROUGH_EACH_CHECKPOINT_WITHOUT_REQUIRING_TARGET_POLARITY_OR_TARGET_CONFIRMATION"


def _day(p: Path):
    m=re.search(r"(20\d{6})",p.name)
    if not m: raise RuntimeError(f"cannot parse raw day {p}")
    return m.group(1)


def _arr(t,*vs):
    if not t:
        return (np.empty(0,float),)+tuple(np.empty(0,float) for _ in vs)
    tt=np.asarray(t,float); o=np.argsort(tt,kind="stable")
    return (tt[o],)+tuple(np.asarray(v,float)[o] for v in vs)


def load_week(raw_dir: str, week: str):
    sun=datetime.strptime(week,"%Y%m%d")
    pt,pv,ft,fs,fa,bt,bv=[],[],[],[],[],[],[]
    for p in sorted(Path(raw_dir).glob("NG_*.jsonl.gz")):
        di=(datetime.strptime(_day(p),"%Y%m%d")-sun).days
        if di<0 or di>5: continue
        with gzip.open(p,"rt") as f:
            for line in f:
                r=json.loads(line)
                try: ts=float(r.get("ts_event",r.get("ts")))
                except Exception: continue
                t=di*86400.0+(ts%86400.0)
                bid=sum(float(r.get(f"bid_sz_{j:02d}",0.0) or 0.0) for j in range(10))
                ask=sum(float(r.get(f"ask_sz_{j:02d}",0.0) or 0.0) for j in range(10))
                if bid+ask>0:
                    bt.append(t); bv.append((bid-ask)/(bid+ask))
                if r.get("action")!="T": continue
                try: px=float(r.get("price",0.0) or 0.0)
                except Exception: px=0.0
                if px>0: pt.append(t); pv.append(px)
                try:
                    sz=float(r.get("size",r.get("qty",0.0)) or 0.0)
                    b0=float(r.get("bid_px_00",0.0) or 0.0)
                    a0=float(r.get("ask_px_00",0.0) or 0.0)
                except Exception: continue
                if not(px>0 and sz>0 and b0>0 and a0>0 and a0>=b0): continue
                mid=.5*(b0+a0)
                if px>mid: ft.append(t); fs.append(sz); fa.append(sz)
                elif px<mid: ft.append(t); fs.append(-sz); fa.append(sz)
    pt,pv=_arr(pt,pv); ft,fs,fa=_arr(ft,fs,fa); bt,bv=_arr(bt,bv)
    if len(pt)==0: raise RuntimeError(f"no authoritative NG trades week={week}")
    return {"times":pt,"prices":pv,"flow_times":ft,"flow_signed":fs,"flow_abs":fa,
            "book_times":bt,"book_imb":bv,"first_trade":float(pt[0]),"last_trade":float(pt[-1])}


def load_cache(cases, raw_dir: str):
    keys=("times","prices","flow_times","flow_signed","flow_abs","book_times","book_imb","first_trade","last_trade")
    c={k:{} for k in keys}
    for w in sorted({x["week"] for x in cases}):
        q=load_week(raw_dir,w)
        for k in keys: c[k][w]=q[k]
    return c


def last_at(t,v,x):
    j=int(np.searchsorted(t,float(x),side="right"))-1
    return None if j<0 else float(v[j])


def flow_ratio(cache,w,lo,hi):
    t=cache["flow_times"][w]; s=cache["flow_signed"][w]; a=cache["flow_abs"][w]
    i=int(np.searchsorted(t,float(lo),side="left")); j=int(np.searchsorted(t,float(hi),side="right"))
    if j<=i: return 0.0,0.0,0.0,0.0
    signed=float(np.sum(s[i:j])); total=float(np.sum(a[i:j])); ratio=signed/total if total>0 else 0.0
    return 1.0,signed,total,ratio


def parts(cache,w: str,cutoff: int):
    t=cache["times"][w]; p=cache["prices"][w]
    now=last_at(t,p,cutoff)
    if now is None: raise RuntimeError(f"no causal price week={w} cutoff={cutoff}")
    price=[1.0,math.log(max(now,1e-12))]
    for lag in PRICE_LAGS:
        q=last_at(t,p,cutoff-lag)
        price += [0.0,0.0] if q is None else [1.0,math.asinh((now-q)/TICK)]
    for win in RANGE_WINDOWS:
        q=last_at(t,p,cutoff-win)
        i=int(np.searchsorted(t,float(cutoff-win),side="left")); j=int(np.searchsorted(t,float(cutoff),side="right"))
        if q is None:
            price += [0.0]*5; continue
        seg=np.concatenate((np.asarray([q]),p[i:j])) if j>i else np.asarray([q])
        hi=float(np.max(seg)); lo=float(np.min(seg))
        price += [1.0,math.asinh((now-q)/TICK),math.asinh((hi-q)/TICK),math.asinh((lo-q)/TICK),math.asinh((hi-lo)/TICK)]
    micro=[]
    for win in FLOW_WINDOWS:
        known,signed,total,ratio=flow_ratio(cache,w,cutoff-win,cutoff)
        micro += [known,math.asinh(signed),math.asinh(total),ratio]
    _,_,_,cur20=flow_ratio(cache,w,cutoff-20,cutoff)
    _,_,_,prev20=flow_ratio(cache,w,cutoff-40,cutoff-20)
    micro += [cur20,prev20,cur20-prev20,abs(cur20)]
    bt=cache["book_times"][w]; bv=cache["book_imb"][w]
    hist={}
    for lag in BOOK_LAGS:
        q=last_at(bt,bv,cutoff-lag); hist[lag]=q
        micro += [0.0,0.0] if q is None else [1.0,q]
    bnow=hist[0]
    for lag in (5,20,60):
        q=hist[lag]
        micro += [0.0,0.0] if bnow is None or q is None else [1.0,bnow-q]
    hour=(float(cutoff)%86400.0)/3600.0; th=2*math.pi*hour/24.0
    first=float(cache["first_trade"][w])
    micro += [math.sin(th),math.cos(th),math.asinh(max(0.0,float(cutoff)-first)/3600.0),max(0.0,min(1.0,float(cutoff)/(6*86400.0)))]
    return price,micro
