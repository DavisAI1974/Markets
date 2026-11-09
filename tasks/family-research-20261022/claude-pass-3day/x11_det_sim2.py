import sys; sys.path.insert(0,'.')
from x11_det_tape_flow import *
import bisect
def prep2(d, r):
    n=len(r); a=np.abs(r); fin=np.isfinite(a)
    base=np.zeros(n)
    for i in range(n):
        lo=max(0,i-30); hi=i-9
        w=a[lo:hi] if hi>lo else np.array([]); w=w[np.isfinite(w)]; base[i]=np.median(w) if len(w) else 0.0
    prom=np.where(fin,a-base,-np.inf)
    return a,fin,base,prom
def thr_series(a,fin,quant=0.85,minobs=600):
    L=[]; t=np.full(len(a),np.nan)
    for i in range(len(a)):
        if fin[i]: bisect.insort(L,a[i])
        if len(L)>=minobs: t[i]=L[min(int(np.ceil(quant*len(L)))-1,len(L)-1)]
    return t
def sim(a,fin,prom,thr_at,Rd=5,Rp=5,REF=45,tie='all',warm=900,fwd=None):
    n=len(a); ev=[]; last=-10**9; c=dict(warm=0,nonfin=0,zero=0,below=0,supp=0,refr=0)
    for i in range(n-Rd):
        s=i+Rd
        if i<warm or not np.isfinite(thr_at[s]): c['warm']+=1; continue
        if not fin[i]: c['nonfin']+=1; continue
        if a[i]<1e-12: c['zero']+=1; continue
        if a[i]<thr_at[s]: c['below']+=1; continue
        lo=max(0,i-Rp); hi=min(n,i+Rp+1)
        if fwd is not None: lo=max(0,i-Rp); hi=min(n,i+fwd+1)
        w=prom[lo:hi]; q=a[lo:hi]>=thr_at[s]; pm=np.where(q,w,-np.inf).max()
        if prom[i]<pm: c['supp']+=1; continue
        if tie=='first' and np.any((w[:i-lo]==pm)&q[:i-lo]): c['supp']+=1; continue
        if i-last<REF: c['refr']+=1; continue
        ev.append(i); last=i
    return np.array(ev),c
if __name__=='__main__':
    d=sys.argv[1]; S,top,ops=load(d); sec=S.second.to_numpy(); recset=set(int(x) for x in top.birth_second)
    r=series(d,'HYB',S); a,fin,base,prom=prep2(d,r); thr=thr_series(a,fin)
    for Rp in (3,5,10,20,30,45,50):
        for tie in ('all','first'):
            ev,c=sim(a,fin,prom,thr,Rp=Rp,tie=tie); es=set(int(sec[i]) for i in ev)
            print('Rp',Rp,tie,'emit',len(ev),'overlap',len(es&recset),c)
