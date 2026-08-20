#!/usr/bin/env python3
"""Fence and consolidate Databento NG.v.0 MBO batch jobs for the approved 5Y archive.

Purpose
-------
Early workflow revisions used two S3 receipt key schemes (YYYY-MM and exact
YYYYMMDD_YYYYMMDD), which allowed a few identical intervals to be submitted under
distinct Databento job IDs. This one-shot coordinator prevents that from cascading:

1. Enumerate every month-bounded interval in the approved 2021-08-20..2026-08-20 range.
2. Reconcile any existing legacy/exact receipts.
3. For an interval with no job yet, write a temporary reservation to BOTH key schemes
   before any Databento submit. Old runners therefore fail closed on the reservation
   instead of submitting a duplicate.
4. Submit exactly one canonical batch job for each reserved interval, then replace both
   receipts with the same job ID.

This coordinator submits jobs only; it does not download or transform data. Existing
workers can reuse the canonical jobs and download the native DBN files for free within
the Databento batch retention window.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from typing import Any

import boto3
import databento as db

DATASET="GLBX.MDP3"
SYMBOL="NG.v.0"
STYPE="continuous"
SCHEMA="mbo"
START=dt.date(2021,8,20)
END=dt.date(2026,8,20)
TOTAL_COST_CEILING_USD=145.80
RESERVATION_OWNER="NG_MBO_5Y_JOB_CONSOLIDATOR_V1"


def required(name:str)->str:
    value=os.environ.get(name)
    if not value: raise SystemExit(f"required environment variable unavailable: {name}")
    return value


def segments(a:dt.date,b:dt.date):
    cur=a
    while cur<b:
        nxt=dt.date(cur.year+1,1,1) if cur.month==12 else dt.date(cur.year,cur.month+1,1)
        stop=min(nxt,b)
        yield cur,stop
        cur=stop


def main()->None:
    key=required("DATABENTO_API_KEY")
    bucket=required("BUCKET")
    prefix=required("PREFIX").strip("/")
    s3=boto3.client("s3",region_name=os.environ.get("AWS_DEFAULT_REGION"))
    client=db.Historical(key)

    whole_quote=float(client.metadata.get_cost(dataset=DATASET,symbols=[SYMBOL],stype_in=STYPE,
                                                schema=SCHEMA,start=START.isoformat(),end=END.isoformat()))
    if whole_quote>TOTAL_COST_CEILING_USD:
        raise SystemExit(f"5Y quote ${whole_quote:.6f} exceeds approved ceiling ${TOTAL_COST_CEILING_USD:.2f}")

    def exists(k:str)->bool:
        try: s3.head_object(Bucket=bucket,Key=k); return True
        except Exception as exc:
            r=getattr(exc,"response",{}); code=r.get("Error",{}).get("Code"); status=r.get("ResponseMetadata",{}).get("HTTPStatusCode")
            if str(code) in {"404","NoSuchKey","NotFound"} or status==404: return False
            raise
    def getj(k:str)->dict[str,Any]: return json.loads(s3.get_object(Bucket=bucket,Key=k)["Body"].read())
    def putj(k:str,obj:Any)->None:
        s3.put_object(Bucket=bucket,Key=k,Body=(json.dumps(obj,indent=2,sort_keys=True)+"\n").encode(),ContentType="application/json")
    def del_if_ours(k:str)->None:
        if exists(k):
            try: d=getj(k)
            except Exception: return
            if d.get("reservation_owner")==RESERVATION_OWNER and not d.get("job_id"):
                s3.delete_object(Bucket=bucket,Key=k)

    audit={
        "schema":"NG_MBO_5Y_JOB_CONSOLIDATION_V1",
        "approved_5y_quote_usd":whole_quote,
        "approved_ceiling_usd":TOTAL_COST_CEILING_USD,
        "existing_reused":[],"existing_collisions":[],"reservations":[],"submitted":[],"errors":[],
    }
    reserved=[]

    # PASS 1: fence every interval that has no existing job, before submitting any new job.
    for a,b in segments(START,END):
        exact=f"{a:%Y%m%d}_{b:%Y%m%d}"; legacy=f"{a:%Y-%m}"
        exact_key=f"{prefix}/_jobs/{exact}.json"; legacy_key=f"{prefix}/_jobs/{legacy}.json"
        rows=[]
        for scheme,k in (("exact",exact_key),("legacy",legacy_key)):
            if exists(k): rows.append((scheme,k,getj(k)))
        valid=[x for x in rows if x[2].get("job_id") and x[2].get("start")==a.isoformat() and x[2].get("end")==b.isoformat()]
        distinct={x[2].get("job_id") for x in valid}
        if valid:
            # Choose exact if present, else first valid; alias a missing scheme to the SAME job.
            chosen=next((x for x in valid if x[0]=="exact"),valid[0])
            record=dict(chosen[2]); record["canonicalized_by"]=RESERVATION_OWNER
            if not exists(exact_key): putj(exact_key,{**record,"legacy_alias_from":chosen[1]})
            if not exists(legacy_key): putj(legacy_key,{**record,"exact_alias_from":chosen[1]})
            audit["existing_reused"].append({"segment":exact,"job_id":record.get("job_id"),"schemes":[x[0] for x in valid]})
            if len(distinct)>1:
                audit["existing_collisions"].append({"segment":exact,"job_ids":sorted(str(x) for x in distinct)})
            continue
        # Any non-job reservation from another coordinator is a hard stop rather than a submit race.
        foreign=[x for x in rows if x[2].get("reservation_owner") not in {None,RESERVATION_OWNER}]
        if foreign:
            raise RuntimeError(f"foreign reservation for {exact}: {[x[1] for x in foreign]}")
        reservation={
            "reservation_owner":RESERVATION_OWNER,"segment":exact,"start":a.isoformat(),"end":b.isoformat(),
            "dataset":DATASET,"symbol":SYMBOL,"stype_in":STYPE,"schema":SCHEMA,
            "reserved_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        putj(exact_key,reservation); putj(legacy_key,reservation)
        reserved.append((a,b,exact,exact_key,legacy_key))
        audit["reservations"].append(exact)

    putj(f"{prefix}/_consolidation/fenced.json",audit)
    print(f"[fence] reserved {len(reserved)} missing intervals; existing={len(audit['existing_reused'])}",flush=True)

    # PASS 2: submit exactly one job per fenced interval and atomically replace both receipt aliases.
    for a,b,segment,exact_key,legacy_key in reserved:
        try:
            quote=float(client.metadata.get_cost(dataset=DATASET,symbols=[SYMBOL],stype_in=STYPE,schema=SCHEMA,
                                                  start=a.isoformat(),end=b.isoformat()))
            job=client.batch.submit_job(dataset=DATASET,symbols=[SYMBOL],stype_in=STYPE,schema=SCHEMA,
                                        start=a.isoformat(),end=b.isoformat(),encoding="dbn",compression="zstd",
                                        split_duration="day")
            jid=job.get("id")
            if not jid: raise RuntimeError(f"no job id for {segment}: {job}")
            record={
                "job_id":jid,"segment":segment,"start":a.isoformat(),"end":b.isoformat(),"quote_usd":quote,
                "submitted_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"dataset":DATASET,
                "symbol":SYMBOL,"stype_in":STYPE,"schema":SCHEMA,"canonicalized_by":RESERVATION_OWNER,
            }
            putj(exact_key,record); putj(legacy_key,{**record,"alias_of":exact_key})
            audit["submitted"].append({"segment":segment,"job_id":jid,"quote_usd":quote})
            putj(f"{prefix}/_consolidation/progress.json",audit)
            print(f"[submit] {segment} job={jid} quote=${quote:.6f}",flush=True)
            # Databento batch submit rate limit is 20/min; stay comfortably below it.
            time.sleep(4.0)
        except Exception as exc:
            audit["errors"].append({"segment":segment,"type":type(exc).__name__,"message":str(exc)})
            del_if_ours(exact_key); del_if_ours(legacy_key)
            putj(f"{prefix}/_consolidation/FAILED.json",audit)
            raise

    audit["completed_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    audit["new_submission_quote_total_usd"]=sum(float(x["quote_usd"]) for x in audit["submitted"])
    putj(f"{prefix}/_consolidation/COMPLETE.json",audit)
    print(json.dumps(audit,indent=2,sort_keys=True))


if __name__=="__main__": main()
