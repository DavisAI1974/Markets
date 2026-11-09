"""Render every archived candidate using immutable saved Claude arrays; no tape reconstruction."""
import argparse,csv,gzip,hashlib,io,json,os,pathlib,time,urllib.request,zipfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from render_core import relative_seconds,lifecycle_markers,candidate_labels,prebirth_cutoff
REV="beb2104c079045c24832f2279eac5e8e69bc576e"
ROOT="tasks/family-research-20261022"
CLAUDE=ROOT+"/claude-pass-3day"
COLORS={"add_touch":"#1f77b4","add_near":"#6baed6","add_far":"#b0cbe1","fill":"#d62728",
        "rm_fill":"#ff9896","rm_cx_touch":"#8c564b","rm_cx_near":"#c49c94","rm_cx_far":"#ddc8bc"}
SOURCES=[]
def fetch(path):
    url=f"https://raw.githubusercontent.com/DavisAI1974/Markets/{REV}/{path}"
    for attempt in range(5):
        try:
            b=urllib.request.urlopen(url,timeout=90).read();break
        except Exception:
            if attempt==4:raise
            time.sleep(attempt+1)
    SOURCES.append(dict(repository="DavisAI1974/Markets",revision=REV,path=path,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
    return b
def csvrows(b,compressed=False):
    if compressed:b=gzip.decompress(b)
    return list(csv.DictReader(io.StringIO(b.decode())))
def number(x):
    return None if x in (None,"","nan","NaN") else int(x)
def utc(ns):
    import datetime
    if ns is None:return "unavailable"
    s,n=divmod(int(ns),10**9)
    return datetime.datetime.fromtimestamp(s,datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")+f".{n:09d}Z"
def bars(ax,x,y,bottom=None,color="black",label=None):
    # A collection draws the same individual rectangles without thousands of Artists.
    y=np.asarray(y,float);bottom=np.zeros(len(y)) if bottom is None else np.asarray(bottom,float)
    ok=np.isfinite(y)&np.isfinite(bottom)
    x=np.asarray(x)[ok];v=y[ok];b=bottom[ok]
    polys=np.stack([np.column_stack([x-.5,b]),np.column_stack([x+.5,b]),
                    np.column_stack([x+.5,b+v]),np.column_stack([x-.5,b+v])],axis=1)
    if len(polys):
        ax.add_collection(PolyCollection(polys,facecolors=color,edgecolors="none",label=label))
        ax.autoscale_view()
    else: ax.plot([],[],color=color,label=label)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def render(day,shard,out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    source=out/"sources";source.mkdir(exist_ok=True)
    base=ROOT if day=="20231018" else ROOT+"/replay-comparison/"+day
    cp=ROOT+"/october18-candidate-inputs.jsonl.gz" if day=="20231018" else base+"/candidate-inputs.jsonl.gz"
    def saved(path,name):
        b=fetch(path)
        if shard==0:(source/name).write_bytes(b)
        return b
    rows=[json.loads(x) for x in gzip.decompress(saved(cp,"candidate-inputs.jsonl.gz")).splitlines()]
    z=np.load(io.BytesIO(saved(CLAUDE+f"/tables/dipole/{day}/instances/x13_life_paths.npz","x13_life_paths.npz")),allow_pickle=False)
    cov={int(r["row"]):r for r in csvrows(saved(CLAUDE+f"/tables/dipole/{day}/t6_cohort_coverage.csv","coverage.csv"))}
    flow=csvrows(saved(base+"/research-atlas-v2/dipole-completed-group-flow.csv.gz","flow.csv.gz"),True)
    weak=csvrows(saved(base+"/research-atlas-v2/dipole-weakening-path.csv.gz","weakening.csv.gz"),True)
    ledger=csvrows(saved(CLAUDE+f"/crossday/detector/ledger_saturated_seconds_{day}.csv","detector-ledger.csv"))
    disposition={int(r["second"]):r["disposition"] for r in ledger}
    sec=np.array([int(r["second"]) for r in flow],dtype=np.int64)
    ratio=np.array([float(r["ratio"]) if r["ratio"] else np.nan for r in flow])
    assert len(set(sec.tolist()))==len(sec) and np.all(np.diff(sec)>0)
    array_rows=[int(x) for x in z["row"]]
    assert len(set(array_rows))==len(array_rows)
    assert all(0<=x<len(rows) for x in array_rows)
    zi={row:n for n,row in enumerate(array_rows)}
    ks=z["ks"];assert np.array_equal(ks,np.arange(-60,1261))
    # Existing numbered array rows retain their order; omitted source rows follow.
    order=array_rows+[i for i in range(len(rows)) if i not in zi]
    assert len(order)==len(rows)==len(set(order))
    weakby={}
    for w in weak:weakby.setdefault(w["candidate_id"],[]).append(w)
    oldrecords={};oldcounts={};oldclocks={}
    if (out/f"index-{shard}.json").exists():
        oldrecords={r["input_row"]:r for r in json.loads((out/f"index-{shard}.json").read_text())}
        for c in json.loads((out/f"reconciliation-{shard}.json").read_text()):oldcounts.setdefault(c["input_row"],[]).append(c)
        oldclocks={r["candidate_id"]:r for r in json.loads((out/f"clocks-{shard}.json").read_text())}
    recovered_births=[candidate_labels(r)["birth_second"] for r in rows if r.get("birth_second") is None]
    records=[];counts=[];clocks=[];allbirths=[(candidate_labels(r)["birth_second"],int(r.get("recorded_operands",{}).get("polarity",0))) for r in rows]
    for ordinal,rowidx in sorted(enumerate(order),key=lambda pair: pair[1] in zi):
        if ordinal%4!=shard:continue
        r=rows[rowidx];cid=r["candidate_id"];labels=candidate_labels(r);bs=labels["birth_second"];pol=int(r.get("recorded_operands",{}).get("polarity",0))
        assert pol in (-1,1)
        n=zi.get(rowidx);c=cov.get(rowidx,{})
        saved_pre=number(c.get("pre_ns"));pre=prebirth_cutoff(saved_pre,bs)
        assert pre==bs*10**9-1,(day,rowidx,pre,bs)
        rec=number(c.get("rec_ns")) if n is not None else None
        if not labels["live_recognition_allowed"] or (rec is not None and rec<=0):rec=None
        available=labels["available_second"]
        m=lifecycle_markers(sec,ratio,bs,pol);hi=m["window_end_s"];L=int((ks<=hi).sum())
        old=oldrecords.get(rowidx)
        if old is not None and not any(b!=bs and -60<=b-bs<=hi for b in recovered_births):
            assert sha(out/old["file"])==old["sha256"]
            old["reused_image"]=True;old.setdefault("render_code_revision","141d876541aae7e04e5de242d0af0a9e047228b9")
            records.append(old);counts.extend(oldcounts[rowidx]);clocks.append(oldclocks[cid])
            continue
        kvals=ks[:L];xb=kvals[:-1]+.5
        fig,ax=plt.subplots(6,1,figsize=(14,15),sharex=True,gridspec_kw={"height_ratios":[1.3,1,1,1.2,1.2,1.1]})
        missing=[];candidate_counts=[]
        def arr(v):
            length=L if z[v].shape[1]==len(ks) else L-1
            a=np.full(length,np.nan) if n is None else z[v][n,:length]
            valid=np.isfinite(a)
            candidate_counts.append(dict(candidate_id=cid,input_row=rowidx,array_row=n,variable=v,
                source_cells=length,finite_cells=int(valid.sum()),missing_cells=int((~valid).sum()),
                rendered_cells=int(valid.sum()),first_k=-60,last_k=int(kvals[length-1])))
            if not valid.all():missing.append(v)
            return a
        ax[0].step(kvals,arr("mid_o"),where="post",color="#222",lw=1,label="oriented midpoint")
        ax[0].step(kvals,arr("spr"),where="post",color="#999",lw=.8,label="spread")
        ax[1].step(kvals,arr("tgt_sz"),where="post",color="#d62728",label="target-side touch")
        ax[1].step(kvals,arr("own_sz"),where="post",color="#1f77b4",label="own-side touch")
        bars(ax[2],xb,arr("with_lots"),color="#2ca02c",label="aggressor lots with")
        bars(ax[2],xb,-arr("against_lots"),color="#e377c2",label="aggressor lots against")
        for a,side in [(ax[3],"tgt"),(ax[4],"own")]:
            up=np.zeros(len(xb));down=np.zeros(len(xb))
            for cl,color in COLORS.items():
                v=arr(side+"_"+cl)
                if cl.startswith("add"):
                    bars(a,xb,v,up,color,cl);up=up+v
                else:
                    bars(a,xb,-v,down,color,cl);down=down-v
            a.set_ylabel(side+" book lots")
        ax[3].legend(fontsize=6,ncol=4,loc="upper left")
        sl=(sec>=bs-60)&(sec<=bs+hi);xs=sec[sl]-bs;ys=ratio[sl]*pol
        ax[5].step(xs,ys,where="post",color="#333",lw=1)
        ax[5].set_ylim(-1.16,1.16);ax[5].axhline(0,color="#bbb",lw=.5)
        candidate_counts.append(dict(candidate_id=cid,input_row=rowidx,array_row=n,variable="companion_ratio",
            source_cells=len(ys),finite_cells=int(np.isfinite(ys).sum()),missing_cells=int((~np.isfinite(ys)).sum()),
            rendered_cells=int(np.isfinite(ys).sum()),first_k=int(xs[0]) if len(xs) else None,last_k=int(xs[-1]) if len(xs) else None))
        baseline=r.get("recorded_operands",{}).get("baseline")
        if baseline is not None:ax[5].axhline(float(baseline),color="#ff7f0e",ls="--",lw=.8)
        for w in weakby.get(cid,[]):
            rel=int(w["second"])-bs
            if -60<=rel<=hi:ax[5].plot(rel,-1.03,"v",color="#9467bd",ms=4)
        for b,p in allbirths:
            if b!=bs and -60<=b-bs<=hi:ax[5].plot([b-bs]*2,[1.03,1.12] if p>0 else [-1.12,-1.03],color="black",lw=.6)
        markers=[(relative_seconds(rec,pre),"#d62728",":","recognition"),
            (m["run_onset_s"],"#2ca02c","-","run onset"),(m["run_end_s"],"#2ca02c","--","loss of one-sidedness"),
            (m["first_flip_s"],"#9467bd","--","first flip"),(m["first_empty_s"],"#777","--","first empty")]
        for a in ax:
            a.axvspan(0,1,color="#ffd54f",alpha=.3,lw=0)
            for when,color,style,label in markers:
                if when is not None and -60<=when<=hi:a.axvline(when,color=color,ls=style,lw=.8)
            a.set_xlim(-60,hi);a.grid(alpha=.16);a.tick_params(labelsize=8)
        for a in ax[:3]:a.legend(loc="upper left",fontsize=7,ncol=2)
        ax[0].set_ylabel("ticks");ax[1].set_ylabel("lots");ax[2].set_ylabel("lots / interval")
        ax[5].set_ylabel("20 s ratio x polarity")
        if n is None:
            for a in ax[:5]:a.text(.5,.5,"No saved lifecycle-array row for this candidate",ha="center",transform=a.transAxes,color="#8b3e23")
        elif missing:
            for j,vars_ in enumerate([["mid_o","spr"],["tgt_sz","own_sz"],["with_lots","against_lots"],
                ["tgt_"+x for x in COLORS],["own_"+x for x in COLORS]]):
                miss=np.zeros(len(kvals) if j<2 else len(xb),bool)
                for v in vars_:miss|=~np.isfinite(z[v][n,:len(miss)])
                xx=kvals if j<2 else xb
                if miss.any():ax[j].scatter(xx[miss],np.full(int(miss.sum()),.02),s=3,marker="|",color="#ae5c26",transform=ax[j].get_xaxis_transform())
        def fmt(v):return "not observed" if v is None else f"{v:+g}s"
        note="saved array absent" if n is None else "saved array present"
        tail="tail unresolved within companion coverage" if m["tail_unresolved"] else "flip and empty observed"
        partial="; partial archived coverage" if day in ("20231002","20231017") else ""
        title=f"{day} | {ordinal+1}/{len(order)} | {cid} | {'BUY' if pol>0 else 'SELL'}{partial}"
        title+=f"\nBirth {utc(bs*10**9)} | available-second label {available if available is not None else 'unavailable'} | recognition {utc(rec)}"
        title+=f"\nRun onset {fmt(m['run_onset_s'])}; loss of one-sidedness {fmt(m['run_end_s'])}; flip {fmt(m['first_flip_s'])}; empty {fmt(m['first_empty_s'])}"
        title+=f"\n{note}; {tail}; displayed through +{hi}s"+("; later marker outside saved array" if m["window_capped"] else "")
        fig.suptitle(title,fontsize=9,y=.995)
        ax[5].set_xlabel("Seconds from prebirth cutoff (birth boundary minus 1 ns); ratio/marker second labels use birth boundary.\n"
            "Yellow: birth second | red dotted: recognition | green solid/dashed: onset/loss | purple: flip | grey: empty\n"
            "Triangles: saved weakening; black ticks: neighbouring births; orange baseline: saved operand. Brown bottom ticks: unavailable array cells.",
            fontsize=8)
        fig.tight_layout(rect=(0,.01,1,.925))
        filename=f"{day}_{ordinal+1:04d}_{cid}.png"
        fig.savefig(out/filename,dpi=100);plt.close(fig)
        record=dict(day=day,ordinal=ordinal+1,candidate_id=cid,input_row=rowidx,array_row=n,file=filename,
            birth_ns=bs*10**9,pre_cutoff_ns=pre,pre_cutoff_origin="saved" if saved_pre is not None and saved_pre>=0 else "axis convention derived from explicit birth clock; no observed array",recognition_ns=rec,available_second=available,
            markers=m,detector_disposition=disposition.get(bs,"not present in saturated-second ledger"),
            missing_array=n is None,sha256=sha(out/filename),weakening_rows=weakby.get(cid,[]),
            source_revision=REV,render_code_revision=os.environ.get("CODE_REV"),reused_image=False,birth_clock_source=labels["birth_clock_source"],input_disposition=r.get("input_disposition"))
        records.append(record);counts.extend(candidate_counts)
        clocks.append(dict(candidate_id=cid,birth_ns=bs*10**9,pre_cutoff_ns=pre,recognition_ns=rec,
            recognition_after_cutoff_s=relative_seconds(rec,pre),available_second=available,
            bin_convention="(pre_cutoff_ns+k*1e9, pre_cutoff_ns+(k+1)*1e9]",
            ratio_convention="saved companion epoch-second labels; no availability inferred"))
        if len(records)%25==0:print(day,shard,len(records),"rendered",flush=True)
    for name,value in [("index",records),("reconciliation",counts),("clocks",clocks),("sources",SOURCES)]:
        (out/f"{name}-{shard}.json").write_text(json.dumps(value,indent=1))
    (out/f"receipt-{shard}.json").write_text(json.dumps(dict(day=day,shard=shard,candidates=len(rows),saved_array_rows=len(zi),rendered=len(records),omitted_source_rows=[i for i in range(len(rows)) if i not in zi]),indent=2))
    print(day,shard,"complete",len(records),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--shard",type=int,required=True);p.add_argument("--output",required=True);a=p.parse_args()
    render(a.day,a.shard,a.output)
