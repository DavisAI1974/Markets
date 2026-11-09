"""Recover exact action clocks and reconcile saved books from immutable tapes."""
import argparse,collections,gzip,io,json,pathlib,tempfile,types
import numpy as np
import pandas as pd
from sortedcontainers import SortedDict
import databento as db
from finish_family_replication import inputs,get,jsonwrite,seal,READS,DREV,MREV,BASE,selected_source

class Book:
    def __init__(self):
        self.orders={};self.levels={"B":SortedDict(),"A":SortedDict()}
        self.depth=collections.Counter();self.count=collections.Counter()
    def change(self,oid,before,after):
        for v,sign in ((before,-1),(after,1)):
            if v:
                side,price,size=v
                if side not in self.levels:raise ValueError(("invalid resting side",v))
                lev=self.levels[side];q,n=lev.get(price,(0,0))
                q+=sign*size;n+=sign
                if n:lev[price]=(q,n)
                else:
                    assert q==0
                    lev.pop(price,None)
                self.depth[side]+=sign*size;self.count[side]+=sign
        if after:self.orders[oid]=after
        else:self.orders.pop(oid,None)
    def apply(self,r,pending):
        action,side,price,size,oid=str(r.action),str(r.side),int(r.price),int(r.size),int(r.order_id)
        before=self.orders.get(oid);after=before;linked=refresh=0
        if action=="R":
            self.__init__();pending.clear()
        elif action=="F":
            if before and before[1]==price:pending[(oid,*before[:2])]+=size
        elif action in ("A","M","C"):
            if action=="C":
                if before is None:raise ValueError(("unobserved cancel",oid))
                after=(*before[:2],before[2]-size) if before[2]>size else None
            else:after=(side,price,size) if size else None
            if before:
                key=(oid,*before[:2]);old_remaining=after[2] if after and after[:2]==before[:2] else 0
                reduction=max(0,before[2]-old_remaining)
                if action in ("C","M") and (not after or after[:2]==before[:2]):
                    linked=min(reduction,pending[key]);pending[key]-=linked
                if action=="M" and after==before and pending[key]:refresh=pending.pop(key)
            self.change(oid,before,after)
        return before,after,linked,refresh
    def top(self,side,n=10):
        levels=self.levels[side]
        keys=list(reversed(levels.keys()))[:n] if side=="B" else list(levels.keys())[:n]
        return [[p,*levels[p]] for p in keys]

def effect(mutations,side,price):
    add=remove=linked=refresh=0
    for a in mutations:
        old=a["before_size"] if a["before_side"]==side and a["before_price"]==price else 0
        new=a["after_size"] if a["after_side"]==side and a["after_price"]==price else 0
        add+=max(0,new-old);remove+=max(0,old-new)
        if old:linked+=min(max(0,old-new),a["fill_linked_reduction"]);refresh+=a["fill_unchanged_display"]
    return dict(added=add,removed=remove,fill_linked=linked,unlinked=remove-linked,unchanged_display_fill=refresh)

def rank_change(before,after):
    x={p:q for p,q,n in before};y={p:q for p,q,n in after}
    shared=sum(y[p]-x[p] for p in x.keys()&y.keys())
    entering=sum(y[p] for p in y.keys()-x.keys());leaving=sum(x[p] for p in x.keys()-y.keys())
    delta=sum(y.values())-sum(x.values())
    assert delta==shared+entering-leaving
    return dict(delta=delta,shared_price_delta=shared,entering_size=entering,leaving_size=leaving)

def tests():
    b=Book();pending=collections.Counter()
    def r(action,side="B",price=100,size=2,oid=1):
        return types.SimpleNamespace(action=action,side=side,price=price,size=size,order_id=oid)
    b.apply(r("A"),pending);b.apply(r("F",size=1),pending)
    _,_,linked,_=b.apply(r("C",size=1),pending)
    assert linked==1 and b.top("B")==[[100,1,1]]
    b.apply(r("A",price=99,size=4,oid=2),pending)
    assert b.depth["B"]==5 and b.count["B"]==2
    assert rank_change([[100,1,1],[99,4,1]],[[99,4,1],[98,8,1]])==dict(delta=7,shared_price_delta=0,entering_size=8,leaving_size=1)
    b.apply(r("R"),pending);assert not b.orders and not b.top("B")
    print("PASS: order mutation, fill linkage, rank-vs-fixed-price decomposition and reset",flush=True)

def savepart(folder,stem,part,rows):
    if rows:
        # Nested payloads are JSON strings; all scalar source clocks stay int64.
        pd.DataFrame(rows).to_parquet(folder/f"{stem}-{part:03d}.parquet",index=False)

def run(day,out):
    tests();out.mkdir(parents=True,exist_ok=True)
    groups,raw=inputs(day,True);raw=raw.sort_values("cursor")
    manifest=json.loads(get("markets-data",DREV,"MANIFEST.json"))
    offsets={}
    for d,f in raw.groupby("tape_day",sort=True):
        ds=(f.cursor-f.record_index).unique();assert len(ds)==1;offsets[str(d)]=int(ds[0])
    expected=iter(raw.itertuples(index=False));next_raw=next(expected,None)
    byclose={g["close_cursor"]:i for i,g in enumerate(groups)}
    b=Book();pending=collections.Counter();mutations=[];actionrows=[];grouprows=[];trades=[]
    actionpart=grouppart=0;groupchecks=actionchecks=0
    previous={"B":[],"A":[]}
    for tapedate,offset in sorted(offsets.items()):
        e=next(e for e in manifest["entries"] if e["path"].endswith(f"NG_v0_mbo_{tapedate}.dbn.zst"))
        blob=get("markets-data",DREV,e["markets_data_path"],e["sha256"])
        for idx,r in enumerate(db.DBNStore.from_bytes(blob)):
            cursor=idx+offset
            if cursor>int(raw.cursor.iloc[-1]):break
            before,after,linked,refresh=b.apply(r,pending)
            active=next_raw is not None and cursor==int(next_raw.cursor) and tapedate==str(next_raw.tape_day)
            if active:
                assert (int(r.ts_recv),str(r.action),str(r.side),int(r.price),int(r.size),int(r.order_id),int(r.flags))==(
                    int(next_raw.receive_ns),next_raw.action,next_raw.side,int(next_raw.price),int(next_raw.size),int(next_raw.order_id),int(next_raw.flags))
                actionchecks+=1
                a=dict(day=day,source_tape_day=tapedate,source_record_index=idx,cursor=cursor,
                       event_ns=int(r.ts_event),receive_ns=int(r.ts_recv),action=str(r.action),side=str(r.side),
                       price_raw=int(r.price),size=int(r.size),order_id=int(r.order_id),flags=int(r.flags),
                       before_side=before[0] if before else "",before_price=before[1] if before else 0,before_size=before[2] if before else 0,
                       after_side=after[0] if after else "",after_price=after[1] if after else 0,after_size=after[2] if after else 0,
                       fill_linked_reduction=linked,fill_unchanged_display=refresh)
                mutations.append(a)
                next_raw=next(expected,None)
            if int(r.flags)&128:
                pending.clear()
                if cursor in byclose and active:
                    j=byclose[cursor];g=groups[j]
                    assert int(r.ts_recv)==g["receive_ns"] and len(mutations)==g["close_cursor"]-g["first_cursor"]+1
                    assert mutations[0]["cursor"]==g["first_cursor"]
                    tops={side:b.top(side) for side in ("B","A")}
                    for side,field in (("B","bid"),("A","ask")):
                        actual=tops[side][0] if tops[side] else None
                        assert actual==g[field],(day,j,side,actual,g[field])
                    for a in mutations:
                        a.update(group_ordinal=j,known_by_ns=g["receive_ns"],group_close_cursor=cursor)
                    bycursor={a["cursor"]:a for a in mutations}
                    for t in g["prints"]:
                        a=bycursor[t["trade_input_cursor"]]
                        assert a["action"]=="T" and (a["event_ns"],a["receive_ns"],a["price_raw"],a["size"])==(t["event_ns"],t["receive_ns"],t["price_raw"],t["size"])
                        trades.append(dict(t,day=day,source_tape_day=a["source_tape_day"],source_record_index=a["source_record_index"]))
                    row={k:v for k,v in g.items() if k not in ("prints","bid","ask")}
                    row.update(day=day,known_by_ns=g["receive_ns"])
                    for side,label in (("B","bid"),("A","ask")):
                        top=tops[side];old=previous[side]
                        for k,col in enumerate(("price_raw","size","orders")):row[f"{label}_{col}"]=top[0][k] if top else 0
                        row[f"{label}_full_size"]=b.depth[side];row[f"{label}_full_orders"]=b.count[side]
                        row[f"{label}_top10_json"]=json.dumps(top,separators=(",",":"))
                        row[f"{label}_rank_change_json"]=json.dumps(rank_change(old,top),separators=(",",":"))
                        for role,price in (("old",old[0][0] if old else 0),("new",top[0][0] if top else 0)):
                            row[f"{label}_{role}_touch_effect_json"]=json.dumps(effect(mutations,side,price),separators=(",",":"))
                    actionrows.extend(mutations);mutations=[];grouprows.append(row);previous=tops;groupchecks+=1
                    if len(actionrows)>=100000:savepart(out,"actions",actionpart,actionrows);actionpart+=1;actionrows=[]
                    if len(grouprows)>=100000:savepart(out,"groups",grouppart,grouprows);grouppart+=1;grouprows=[];print(f"{day}: reconciled {groupchecks} groups",flush=True)
    assert next_raw is None and actionchecks==len(raw) and groupchecks==len(groups)
    assert len(trades)==sum(len(g["prints"]) for g in groups)
    savepart(out,"actions",actionpart,actionrows);savepart(out,"groups",grouppart,grouprows)
    pd.DataFrame(trades).to_parquet(out/"trades.parquet",index=False)
    jsonwrite(out/"source-receipt.json",dict(day=day,groups=groupchecks,actions=actionchecks,trades=len(trades),
        action_and_group_checks="passed",all_group_quotes_sizes_order_counts="passed",
        clocks="integer event_ns, receive_ns, known_by_ns, cursor; group event clock is not individual action event clock",
        book_initialization="Original UTC tape from first available member snapshot, including source prehistory before retained cursor zero",
        scope="Original retained date span; October2/17 remain partial; no external layer inputs",
        source_modules_revision=MREV))
    jsonwrite(out/"input-manifest.json",READS);seal(out)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",required=True,type=pathlib.Path);a=p.parse_args();run(a.day,a.output)
