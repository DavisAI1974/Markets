"""Exact-clock shared readers; each study retains its own event population."""
import collections,gzip,io,json,os,pathlib
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from finish_family_replication import get,jsonwrite,seal,READS,BASE,MREV,DREV,NREV,SNAP
NS=10**9
TICK=10**6
FREV="54e1b1be98ae6defff25ccfe7e1c3498e8f569f9"
FROOT=BASE+"/family-replication/run-42564821790-1/family-preflight"
COLUMNS=["group_ordinal","first_cursor","close_cursor","event_ns","receive_ns","known_by_ns",
"snapshot_member","reset_member","bad_receive_clock_member","print_count",
"bid_price_raw","bid_size","bid_orders","ask_price_raw","ask_size","ask_orders",
"bid_full_size","ask_full_size","bid_full_orders","ask_full_orders"]

def records(path,rows):
    # Arrow infers int64+null directly from Python ints; no float clock conversion.
    pq.write_table(pa.Table.from_pylist(rows),path,compression="zstd")

def source_file(ctx,name):
    p=ctx.source/name
    if not p.exists():
        e=next(e for e in ctx.manifest["files"] if e["path"]==name)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(get("markets-data",ctx.source_rev,ctx.source_path+"/"+name,e["sha256"]))
    return p

def native_table(day,suffix):
    manifest=json.loads(get("markets-data",NREV,SNAP+"/MANIFEST.json"))
    path=f"agent-pass/tables/{day}-{suffix}"
    e=next(e for e in manifest["entries"] if e["source"]==path)
    return pd.read_csv(io.BytesIO(get("markets-data",NREV,e["path"],e["sha256"])),dtype=str,keep_default_na=False)

class Context:
    def __init__(self,day,out,source):
        self.day=day;self.out=out;out.mkdir(parents=True,exist_ok=True)
        self.source=source;source.mkdir(parents=True,exist_ok=True)
        self.source_rev=os.environ["SOURCE_REV"]
        self.source_path=BASE+f"/combined-events/run-{os.environ['SOURCE_RUN']}-1/events-{day}"
        self.manifest=json.loads(get("markets-data",self.source_rev,self.source_path+"/MANIFEST.json"))
        names=[e["path"] for e in self.manifest["files"] if e["path"].startswith("groups-")]
        self.group_files=[source_file(self,n) for n in sorted(names)]
        self.g=pd.concat([pd.read_parquet(p,columns=COLUMNS) for p in self.group_files],ignore_index=True)
        self.tr=pd.read_parquet(source_file(self,"trades.parquet"))
        receipt=json.loads(source_file(self,"source-receipt.json").read_text())
        assert len(self.g)==receipt["groups"] and len(self.tr)==receipt["trades"]
        g=self.g;self.t=g.receive_ns.to_numpy(np.int64);self.c=g.close_cursor.to_numpy(np.int64)
        assert g.group_ordinal.tolist()==list(range(len(g))) and np.all(np.diff(self.t)>=0)
        midnight=int(datetime.strptime(day,"%Y%m%d").replace(tzinfo=timezone.utc).timestamp())
        self.open=(midnight if day in ("20231002","20231017") else midnight-7200)*NS
        self.close=(midnight+21*3600)*NS
        self.valid=((self.t>=self.open)&(self.t<self.close)&
            ~g[["snapshot_member","reset_member","bad_receive_clock_member"]].any(axis=1).to_numpy()&
            (g.bid_price_raw.to_numpy()>0)&(g.ask_price_raw.to_numpy()>g.bid_price_raw.to_numpy()))
        connected=np.r_[False,(g.first_cursor.to_numpy()[1:]==self.c[:-1]+1)&(self.t[1:]>=self.t[:-1])]
        self.seg=np.full(len(g),-1,np.int64);sid=-1
        for j in range(len(g)):
            if self.valid[j]:
                if j==0 or not self.valid[j-1] or not connected[j]:sid+=1
                self.seg[j]=sid
        self.end=np.full(len(g),-1,np.int64)
        for j in range(len(g)-1,-1,-1):
            if self.valid[j]:self.end[j]=self.end[j+1] if j+1<len(g) and self.seg[j+1]==self.seg[j] else j
        self.mid=g.bid_price_raw.to_numpy(np.int64)+g.ask_price_raw.to_numpy(np.int64)
        self.trades=self.tr.to_dict("records")
        self.tt=self.tr.receive_ns.to_numpy(np.int64);self.tc=self.tr.trade_input_cursor.to_numpy(np.int64)
        self.tp=self.tr.price_raw.to_numpy(np.int64)
        self.summary={}
    def point(self,j):
        if j<0 or j>=len(self.g):return None
        r=self.g.iloc[j]
        return dict(group=j,event_ns=int(r.event_ns),receive_ns=int(r.receive_ns),
            known_by_ns=int(r.known_by_ns),first_cursor=int(r.first_cursor),close_cursor=int(r.close_cursor),
            bid_raw=int(r.bid_price_raw),ask_raw=int(r.ask_price_raw),segment=int(self.seg[j]))
    def prior(self,t,cap):
        return min(int(np.searchsorted(self.t,t,side="left"))-1,int(np.searchsorted(self.c,cap,side="right"))-1)
    def endpoint(self,j,target):
        k=int(np.searchsorted(self.t,target,side="right"))-1
        valid=0<=j<len(self.g) and self.valid[j] and k>=j and k<=self.end[j] and target<=self.t[self.end[j]]
        return k,valid
    def eligible_later(self,j,target):
        k=max(j+1,int(np.searchsorted(self.t,target,side="left")))
        return k if self.valid[j] and k<=self.end[j] else None
    def save(self,name,rows):records(self.out/(name+".parquet"),rows)
    def finish(self):
        jsonwrite(self.out/"analysis-summary.json",self.summary)
        jsonwrite(self.out/"input-manifest.json",READS);seal(self.out)
