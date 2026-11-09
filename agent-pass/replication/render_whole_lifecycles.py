"""Printable whole lifecycle books and original render catalogue; audited inputs only."""
import argparse,collections,html,io,json,math,os,pathlib,tempfile
from datetime import datetime,timezone
import numpy as np
import pyarrow.parquet as pq
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import fitz
from finish_family_replication import get,jsonwrite,seal,READS,NREV,SNAP,BASE
from event_common import Context,NS
from audit_whole_lifecycles import Inputs
W,H=842,595
COLORS=["#1261a0","#d75c23","#25854b","#8e44ad"]
def stamp(ns):
    if ns is None:return "unavailable"
    return datetime.fromtimestamp(ns//NS,timezone.utc).strftime("%Y-%m-%d %H:%M:%S")+"."+f"{ns%NS:09d}"+" UTC"
def label(c,x,y,text,size=8,color="#243549"):
    c.setFillColor(color);c.setFont("Helvetica",size);c.drawString(x,y,str(text))
def chart(c,rect,title,series,xrange,marks=()):
    x,y,w,h=rect;plot=(x+47,y+19,w-55,h-40);px,py,pw,ph=plot
    label(c,x,y+h-12,title,9)
    vals=[float(v) for _,ys,_,_ in series for v in ys if v is not None and np.isfinite(v)]
    low,high=(min(vals),max(vals)) if vals else (0.,1.)
    pad=(high-low)*.08 if high!=low else max(abs(high)*.01,.1);low-=pad;high+=pad
    a,b=xrange;b=max(a+1e-9,b)
    def xy(t,v):return px+(t-a)/(b-a)*pw,py+(v-low)/(high-low)*ph
    c.setStrokeColor("#c9d1d9");c.setLineWidth(.5);c.rect(px,py,pw,ph)
    for q in (0,.5,1):
        v=low+q*(high-low);label(c,x,py+q*ph-2,f"{v:.5g}",6.5)
        label(c,px+q*pw-8,y+5,f"{a+q*(b-a):.4g}",6.5)
    for t,name,color in marks:
        if a<=t<=b:
            xx,_=xy(t,low);c.setStrokeColor(color);c.setDash(2,2);c.line(xx,py,xx,py+ph);c.setDash()
    c.saveState();clip=c.beginPath();clip.rect(px,py,pw,ph);c.clipPath(clip,stroke=0,fill=0)
    for xs,ys,color,step in series:
        c.setStrokeColor(color);c.setLineWidth(.7);p=c.beginPath();last=None;last_finite=None;count=0
        for t,v in zip(xs,ys):
            if v is None or not np.isfinite(v) or not np.isfinite(t):
                last=None;continue
            xx,yy=xy(float(t),float(v))
            if last is None:p.moveTo(xx,yy)
            else:
                if step:p.lineTo(xx,last[1])
                p.lineTo(xx,yy)
            last=(xx,yy);last_finite=last;count+=1
        c.drawPath(p)
        if count==1:
            c.setFillColor(color);c.circle(last_finite[0],last_finite[1],1.8,fill=1,stroke=0)
    c.restoreState()
    if not vals:label(c,px+10,py+ph/2,"No observed values",9)
def chart_tests():
    target=io.BytesIO();c=canvas.Canvas(target,pagesize=(W,H))
    for values in ([None,1.,None],[1.,None,None],[None,None,None]):
        chart(c,(30,30,350,200),"Gap regression",[(range(3),values,COLORS[0],False)],(0,2))
        c.showPage()
    c.save();d=fitz.open(stream=target.getvalue(),filetype="pdf");assert len(d)==3;d.close()
    print("PASS: isolated valid point followed by gaps and entirely missing series",flush=True)
def preview(pdf,out,name,page=0):
    d=fitz.open(pdf);p=d[page];p.get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(out/name)
    assert p.get_text().strip();d.close()
def load_audit(day,out):
    root=BASE+f"/whole-lifecycles/run-{os.environ['AUDIT_RUN']}-1/audit-{day}"
    rev=os.environ["AUDIT_REV"];m=json.loads(get("markets-data",rev,root+"/MANIFEST.json"))
    content={}
    for e in m["files"]:
        if e["path"] in ("audit.json","whole-lifecycles.parquet","whole-lifecycle-points.parquet","component-windows.parquet","native-flow-source-clocks.parquet"):
            raw=get("markets-data",rev,root+"/"+e["path"],e["sha256"]);content[e["path"]]=raw
    audit=json.loads(content["audit.json"]);assert audit["status"]=="passed"
    parents=pq.read_table(io.BytesIO(content["whole-lifecycles.parquet"])).to_pylist()
    points=pq.read_table(io.BytesIO(content["whole-lifecycle-points.parquet"])).to_pylist()
    flow=pq.read_table(io.BytesIO(content["native-flow-source-clocks.parquet"])).to_pylist()
    return parents,points,flow,audit,root
def daybook(day,out):
    parents,points,flow,audit,aroot=load_audit(day,out)
    byparent=collections.defaultdict(list)
    for p in points:byparent[p["parent_id"]].append(p)
    I=Inputs(day);index=[];counts=collections.Counter();books=[]
    with tempfile.TemporaryDirectory() as tmp:
        ctx=Context(day,out,pathlib.Path(tmp))
        ft=np.array([r["label_ns"] for r in flow],np.int64)
        for kind in ("candidate","control1","control2"):
            items=sorted((p for p in parents if p["kind"]==kind),key=lambda p:(p["anchor_label_ns"],p["candidate_id"]))
            for chunk in range(0,len(items),100):
                name=f"{day}-{kind}-whole-lifecycles-{chunk//100+1:02d}.pdf"
                pdf=out/name;c=canvas.Canvas(str(pdf),pagesize=(W,H),pageCompression=1)
                c.setTitle(f"{day} {kind} whole lifecycles {chunk+1}-{min(chunk+100,len(items))}")
                for page,p in enumerate(items[chunk:chunk+100],1):
                    anchor=p["anchor_label_ns"];end=p["lifecycle_end_label_ns"];rec=p["recognition_ns"]
                    left=anchor-60*NS;right=max(anchor+NS,end or anchor,rec or anchor)+20*NS
                    xlim=((left-anchor)/NS,(right-anchor)/NS)
                    a=int(np.searchsorted(ft,left));b=int(np.searchsorted(ft,right,side="right"));f=flow[a:b]
                    times=[(r["label_ns"]-anchor)/NS for r in f]
                    ga=max(0,int(np.searchsorted(ctx.t,left,side="right"))-1);gb=int(np.searchsorted(ctx.t,right,side="right"))
                    gt=(ctx.t[ga:gb]-anchor)/NS
                    good=ctx.valid[ga:gb];bid=np.where(good,ctx.g.bid_price_raw.to_numpy()[ga:gb]/NS,np.nan)
                    ask=np.where(good,ctx.g.ask_price_raw.to_numpy()[ga:gb]/NS,np.nan)
                    bs=np.where(good,ctx.g.bid_size.to_numpy()[ga:gb],np.nan);asz=np.where(good,ctx.g.ask_size.to_numpy()[ga:gb],np.nan)
                    marks=[(0,"anchor","#25854b")]
                    if end is not None:marks.append(((end-anchor)/NS,"defined end","#b83b3b"))
                    if rec is not None:marks.append(((rec-anchor)/NS,"recognition","#8e44ad"))
                    label(c,30,566,f"{day}  {kind}  |  {p['candidate_id']}  |  {p['orientation']}",15)
                    label(c,30,549,f"One whole lifecycle: {p['endpoint_definition']} | {p['point_count']} original seconds including anchor",9)
                    label(c,30,535,"Green: anchor   Red: operational endpoint   Purple: actual recognition   Context extends outside the whole.",8)
                    chart(c,(30,329,385,194),"Native action-midpoint classified 20s lean",
                        [(times,[r["native_ratio"] for r in f],COLORS[0],False)],xlim,marks)
                    chart(c,(427,329,385,194),"Original bid (blue) and ask (orange), price units",
                        [(gt,bid,COLORS[0],True),(gt,ask,COLORS[1],True)],xlim,marks)
                    chart(c,(30,132,385,194),"Fresh native classified buy (blue) / sell (orange) lots",
                        [(times,[r["native_buy"] for r in f],COLORS[0],False),(times,[r["native_sell"] for r in f],COLORS[1],False)],xlim,marks)
                    chart(c,(427,132,385,194),"Displayed best bid (blue) / ask (orange) lots",
                        [(gt,bs,COLORS[0],True),(gt,asz,COLORS[1],True)],xlim,marks)
                    label(c,30,119,"All panels: elapsed seconds from this instance's anchor. Original values; no smoothing, scaling or averaging.",8)
                    label(c,30,103,"Anchor label: "+stamp(anchor),8)
                    label(c,30,90,"Actual recognition: "+stamp(rec)+(" (controls have no detector recognition)" if kind!="candidate" else ""),8)
                    label(c,30,77,"Endpoint label: "+stamp(end),8)
                    label(c,30,64,"Endpoint known-by: "+stamp(p["lifecycle_end_known_by_ns"]),8)
                    label(c,30,49,"Parent: "+p["parent_id"],7)
                    label(c,30,37,"Exact event/receive/known-by/source cursors remain in audited tables. Undefined values are gaps inside the same parent.",7)
                    label(c,30,25,"Endpoint = third opposite second (or censoring), not proven natural event death. Control anchors are independent instances.",7)
                    label(c,750,25,f"Page {page}",7)
                    c.showPage()
                    index.append(dict(parent_id=p["parent_id"],candidate_id=p["candidate_id"],kind=kind,day=day,
                        pdf=name,page=page,anchor_label_ns=anchor,recognition_ns=rec,lifecycle_end_label_ns=end,
                        audit_revision=os.environ["AUDIT_REV"],audit_path=aroot,
                        plotted_context_first_ns=left,plotted_context_last_ns=right,
                        whole_path_points=p["point_count"],original_quote_groups=gb-ga))
                    counts[kind]+=1
                c.save();books.append(name)
                doc=fitz.open(pdf);assert len(doc)==min(100,len(items)-chunk)
                assert all(p.get_text().strip() for p in doc);doc.close()
                assert pdf.stat().st_size<95_000_000
                if chunk==0:preview(pdf,out,f"{day}-{kind}-preview.png")
                print("RENDERED",name,flush=True)
        # New analyses: show every individual observation with table/row IDs in the companion index.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        legs=I.combined("a-print-legs");episodes=I.combined("b-quote-episodes");moves=I.combined("c-large-quote-events")
        fig,axes=plt.subplots(2,2,figsize=(15,10))
        candidate=[p for p in parents if p["kind"]=="candidate"]
        panels=[
          ("Whole candidate duration (defined endpoint; seconds)",candidate,lambda r:None if r["lifecycle_end_label_ns"] is None else (r["lifecycle_end_label_ns"]-r["anchor_label_ns"])/NS,"parent_id"),
          ("Whole directional print-leg duration (receive seconds)",legs,lambda r:r["duration_receive_ns"]/NS,"first_trade"),
          ("Size-one quote episode duration (known-by seconds)",episodes,lambda r:None if r["duration_known_by_ns"] is None else r["duration_known_by_ns"]/NS,"event_id"),
          ("Large move to first full return (known-by seconds)",moves,lambda r:None if r["full_recovery_elapsed_ns"] is None else r["full_recovery_elapsed_ns"]/NS,"event_id")]
        renderpoints=[]
        for ax,(title,rows,value,key) in zip(axes.flat,panels):
            vals=[value(r) for r in rows];ok=[j for j,v in enumerate(vals) if v is not None]
            ax.scatter(ok,[vals[j] for j in ok],s=4,color=COLORS[0]);ax.set_title(f"{title}\n{len(rows)} individual records; {len(rows)-len(ok)} unavailable/censored")
            ax.set_xlabel("Original record order (not elapsed time)");ax.set_ylabel("Seconds");ax.grid(alpha=.18)
            renderpoints.extend(dict(panel=title,record_ordinal=j,record_id=str(r[key]),value_seconds=vals[j]) for j,r in enumerate(rows))
        fig.suptitle(day+" | Individual duration observations - each whole and each component remains identifiable",fontsize=15)
        fig.tight_layout(rect=(0,0,.99,.95));fig.savefig(out/f"{day}-individual-durations.png",dpi=150);fig.savefig(out/f"{day}-individual-durations.pdf");plt.close(fig)
        jsonwrite(out/"duration-render-points.json",renderpoints)
    # Compact coordination packet: first chronological candidate per orientation plus its original control1.
    # Selection is by source order, never by a favorable outcome.
    chosen=[]
    for ori in ("NO_PREDECESSOR","SAME","FLIP"):
        pool=sorted((p for p in parents if p["kind"]=="candidate" and p["orientation"]==ori),key=lambda p:p["anchor_label_ns"])
        if pool:
            for k in ("candidate","control1"):
                chosen.extend(r for r in index if r["candidate_id"]==pool[0]["candidate_id"] and r["kind"]==k)
    packet=fitz.open()
    for r in chosen:
        source=fitz.open(out/r["pdf"]);packet.insert_pdf(source,from_page=r["page"]-1,to_page=r["page"]-1);source.close()
    packet.save(out/f"{day}-pinning-starter.pdf");packet.close()
    jsonwrite(out/"pinning-starter-index.json",dict(selection="First chronological candidate per orientation, plus its original control1; no outcome selection",pages=chosen))
    jsonwrite(out/"lifecycle-render-index.json",index)
    jsonwrite(out/"render-receipt.json",dict(status="passed",day=day,parents=len(parents),counts=dict(counts),pdf_books=books,
        pages=len(index),audit=audit,whole_paths_retained=True,whole_path_points=len(points),
        note="Every parent has one complete page. PDF file volumes are packaging only; no lifecycle crosses pages."))
    links=["# "+day+" complete lifecycle renders","",
        "All candidate and control instances have one full page. Exact IDs/clocks are in lifecycle-render-index.json and the audit tables.",
        "","| Book | Pages |","|---|---:|"]
    links += [f"| [{n}]({n}) | {sum(r['pdf']==n for r in index)} |" for n in books]
    (out/"README.md").write_text("\n".join(links)+"\n")
    jsonwrite(out/"input-manifest.json",READS);seal(out)

def archive(out):
    I=Inputs("20231018");entries=[e for e in I.man["entries"] if e["source"].startswith("agent-pass/figures/") and e["source"].endswith(".png")]
    assert len(entries)==337
    groups=collections.defaultdict(list)
    for e in entries:
        name=pathlib.PurePosixPath(e["source"]).name
        group=name[:8] if name[:8] in ("20231002","20231003","20231017","20231018") else "cross-date"
        groups[group].append(e)
    index=[];books=[]
    for group,items in sorted(groups.items()):
        name=f"original-dipole-renders-{group}.pdf";pdf=out/name
        c=canvas.Canvas(str(pdf),pagesize=(W,H),pageCompression=1)
        for page,e in enumerate(sorted(items,key=lambda e:e["source"]),1):
            raw=I.raw(e["source"]);img=ImageReader(io.BytesIO(raw));iw,ih=img.getSize()
            scale=min((W-40)/iw,(H-84)/ih);dw,dh=iw*scale,ih*scale
            title=pathlib.PurePosixPath(e["source"]).name
            label(c,20,H-22,title,10)
            label(c,20,H-36,"Original published render, unchanged. Individual source tables and figure reconciliation remain linked.",8)
            c.drawImage(img,(W-dw)/2,42+(H-84-dh)/2,width=dw,height=dh)
            source=f"https://github.com/DavisAI1974/markets-data/blob/{NREV}/{e['path']}"
            c.linkURL(source,(20,14,W-20,35),relative=0);label(c,20,23,"Open full-resolution source image | Snapshot "+NREV[:12]+" | Page "+str(page),8)
            c.showPage()
            index.append(dict(source=e["source"],source_revision=NREV,source_path=e["path"],source_sha256=e["sha256"],pdf=name,page=page,full_resolution=source))
        c.save();books.append(name);assert pdf.stat().st_size<95_000_000
        d=fitz.open(pdf);assert len(d)==len(items);d.close()
        preview(pdf,out,"original-"+group+"-preview.png")
    # Add the completed continuous precursor render without changing its observations.
    extrev="71240aa56a8b27f7d7f68acd154784579094e5c1"
    extpath=BASE+"/four-day-extensions/run-42563528655-1/continuous-onsets-four-days.png"
    raw=get("markets-data",extrev,extpath);(out/"continuous-onsets-four-days.png").write_bytes(raw)
    jsonwrite(out/"original-render-index.json",index)
    (out/"README.md").write_text("# All 337 original dipole renders\n\n"+"\n".join(f"- [{n}]({n})" for n in books)+
        "\n\nEach original figure remains unchanged and links to its full-resolution source. Heat strips, sorted distributions, controls, structural groupings and fitted descriptions retain their original scopes. They are not whole lifecycle plots; use the new whole-lifecycle books for those.\n\n[Continuous precursor scan](continuous-onsets-four-days.png)\n")
    jsonwrite(out/"render-receipt.json",dict(status="passed",original_figures=len(index),pdf_books=books,source_revision=NREV))
    jsonwrite(out/"input-manifest.json",READS);seal(out)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",required=True,type=pathlib.Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);chart_tests()
    archive(a.output) if a.day=="archive" else daybook(a.day,a.output)
