#!/usr/bin/env python3
"""Compatibility guard for the 5Y NG MBO acquisition.

A first workflow revision keyed partial boundary spans by YYYY-MM; the corrected
revision keys by exact YYYYMMDD_YYYYMMDD. This guard aliases any legacy job or
completed manifest whose recorded [start,end) exactly matches the new segment,
so reruns never submit the same Databento span again.
"""
from __future__ import annotations
import datetime as dt
import json,os
import boto3


def _required(name:str)->str:
    v=os.environ.get(name)
    if not v: raise SystemExit(f"required environment variable unavailable: {name}")
    return v


def _segments(a:dt.date,b:dt.date):
    cur=a
    while cur<b:
        nxt=dt.date(cur.year+1,1,1) if cur.month==12 else dt.date(cur.year,cur.month+1,1)
        stop=min(nxt,b); yield cur,stop; cur=stop


def migrate_legacy_receipts()->dict:
    bucket=_required('BUCKET'); prefix=_required('PREFIX').strip('/')
    start=dt.date.fromisoformat(_required('START')); end=dt.date.fromisoformat(_required('END'))
    s3=boto3.client('s3',region_name=os.environ.get('AWS_DEFAULT_REGION'))
    def exists(k):
        try: s3.head_object(Bucket=bucket,Key=k); return True
        except Exception as exc:
            r=getattr(exc,'response',{}); code=r.get('Error',{}).get('Code'); status=r.get('ResponseMetadata',{}).get('HTTPStatusCode')
            if str(code) in {'404','NoSuchKey','NotFound'} or status==404: return False
            raise
    def getj(k): return json.loads(s3.get_object(Bucket=bucket,Key=k)['Body'].read())
    def putj(k,v): s3.put_object(Bucket=bucket,Key=k,Body=(json.dumps(v,indent=2,sort_keys=True)+'\n').encode(),ContentType='application/json')
    result={'aliased_jobs':[],'aliased_completed':[],'collisions':[]}
    for a,b in _segments(start,end):
        exact=f'{a:%Y%m%d}_{b:%Y%m%d}'; legacy=f'{a:%Y-%m}'
        ej=f'{prefix}/_jobs/{exact}.json'; lj=f'{prefix}/_jobs/{legacy}.json'
        ed=f'{prefix}/_done/{exact}.done'; ld=f'{prefix}/_done/{legacy}.done'
        em=f'{prefix}/manifests/{exact}.json'; lm=f'{prefix}/manifests/{legacy}.json'
        legacy_job=getj(lj) if exists(lj) else None
        matches=lambda x: bool(x) and x.get('start')==a.isoformat() and x.get('end')==b.isoformat()
        if not exists(ej) and matches(legacy_job):
            putj(ej,{**legacy_job,'segment':exact,'legacy_alias_from':lj})
            result['aliased_jobs'].append(exact)
        elif exists(ej) and matches(legacy_job):
            exact_job=getj(ej)
            if exact_job.get('job_id')!=legacy_job.get('job_id'):
                result['collisions'].append({'segment':exact,'legacy_job_id':legacy_job.get('job_id'),'exact_job_id':exact_job.get('job_id')})
        if not (exists(ed) and exists(em)) and exists(ld) and exists(lm):
            legacy_manifest=getj(lm)
            if matches(legacy_manifest):
                exact_manifest={**legacy_manifest,'segment':exact,'legacy_alias_from':lm}
                putj(em,exact_manifest)
                s3.put_object(Bucket=bucket,Key=ed,Body=(json.dumps({'segment':exact,'job_id':legacy_manifest.get('job_id'),'manifest':em,'legacy_alias_from':ld})+'\n').encode())
                result['aliased_completed'].append(exact)
    audit=f'{prefix}/_compat/{_required("LABEL")}.json'
    putj(audit,result)
    print(json.dumps(result,indent=2,sort_keys=True))
    return result

if __name__=='__main__':
    migrate_legacy_receipts()
    # This file is executed directly from research/kalshi, so import the sibling
    # module directly instead of assuming the repository root is on sys.path.
    from ng_mbo_5y_native_to_s3 import main
    main()
