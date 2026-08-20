#!/usr/bin/env python3
"""Read-only expected-vs-actual audit for the approved five-year NG.v.0 MBO archive.

No Databento API is called. This inspects S3 job/manifests/native DBN receipts only and
computes whether the archive is complete enough to safely cancel the historical source.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from collections import defaultdict
from pathlib import Path

import boto3

START=dt.date(2021,8,20)
END=dt.date(2026,8,20)


def segments(a:dt.date,b:dt.date):
    cur=a
    while cur<b:
        nxt=dt.date(cur.year+1,1,1) if cur.month==12 else dt.date(cur.year,cur.month+1,1)
        stop=min(nxt,b)
        yield cur,stop
        cur=stop


def main():
    bucket=os.environ['BUCKET']; prefix=os.environ['PREFIX'].strip('/')+'/'
    s3=boto3.client('s3',region_name=os.environ.get('AWS_DEFAULT_REGION'))
    objects=[]; token=None
    while True:
        kw={'Bucket':bucket,'Prefix':prefix,'MaxKeys':1000}
        if token: kw['ContinuationToken']=token
        page=s3.list_objects_v2(**kw); objects.extend(page.get('Contents',[]))
        if not page.get('IsTruncated'): break
        token=page['NextContinuationToken']
    keys=[o['Key'] for o in objects]
    def getj(k): return json.loads(s3.get_object(Bucket=bucket,Key=k)['Body'].read())

    expected=[(a.isoformat(),b.isoformat()) for a,b in segments(START,END)]
    expected_set=set(expected)
    jobs_by_interval=defaultdict(list)
    reservations=[]
    for k in sorted(x for x in keys if '/_jobs/' in x and x.endswith('.json')):
        try: d=getj(k)
        except Exception as exc:
            continue
        pair=(d.get('start'),d.get('end'))
        if all(pair):
            jobs_by_interval[pair].append({
                'key':k,'job_id':d.get('job_id'),'quote_usd':d.get('quote_usd'),
                'reservation_owner':d.get('reservation_owner'),
            })
        if d.get('reservation_owner') and not d.get('job_id'):
            reservations.append({'key':k,'start':d.get('start'),'end':d.get('end'),'owner':d.get('reservation_owner')})

    manifest_intervals=set(); manifest_errors=[]
    for k in sorted(x for x in keys if '/manifests/' in x and x.endswith('.json')):
        try: d=getj(k)
        except Exception as exc:
            manifest_errors.append({'key':k,'error':type(exc).__name__}); continue
        if d.get('start') and d.get('end'):
            manifest_intervals.add((d['start'],d['end']))

    expected_with_job=[]; expected_reserved=[]; expected_missing=[]; duplicates=[]
    duplicate_overhead=0.0
    for pair in expected:
        rows=jobs_by_interval.get(pair,[])
        ids=[]
        by_id={}
        for r in rows:
            jid=r.get('job_id')
            if jid and jid not in by_id:
                by_id[jid]=r; ids.append(jid)
        if ids:
            expected_with_job.append(pair)
            if len(ids)>1:
                quotes=[]
                for jid in ids:
                    q=by_id[jid].get('quote_usd')
                    if isinstance(q,(int,float)): quotes.append(float(q))
                if len(quotes)==len(ids): duplicate_overhead += sum(sorted(quotes)[:-1])
                duplicates.append({'start':pair[0],'end':pair[1],'job_ids':sorted(ids)})
        elif any(r.get('reservation_owner') for r in rows):
            expected_reserved.append(pair)
        else:
            expected_missing.append(pair)

    unexpected=[]
    for pair,rows in sorted(jobs_by_interval.items()):
        if pair not in expected_set:
            unexpected.append({
                'start':pair[0],'end':pair[1],
                'job_ids':sorted({str(r.get('job_id')) for r in rows if r.get('job_id')}),
                'reservation_keys':sorted(r['key'] for r in rows if r.get('reservation_owner') and not r.get('job_id')),
            })

    native=[o for o in objects if '/native/' in o['Key'] and o['Key'].endswith('.dbn.zst')]
    consolidation_state='NONE'; consolidation_key=None
    for state,name in [('FAILED','FAILED.json'),('COMPLETE','COMPLETE.json'),('PROGRESS','progress.json'),('FENCED','fenced.json')]:
        matches=[k for k in keys if k.endswith('/_consolidation/'+name)]
        if matches:
            consolidation_state=state; consolidation_key=matches[0]; break

    completed_expected=sorted(pair for pair in expected if pair in manifest_intervals)
    output={
        'schema':'NG_MBO_5Y_COMPACT_AUDIT_V1',
        'range':{'start':START.isoformat(),'end':END.isoformat()},
        'expected_interval_count':len(expected),
        'expected_intervals_with_job_count':len(expected_with_job),
        'expected_intervals_reserved_no_job_count':len(expected_reserved),
        'expected_intervals_missing_count':len(expected_missing),
        'expected_intervals_manifest_complete_count':len(completed_expected),
        'duplicate_expected_interval_count':len(duplicates),
        'duplicate_expected_intervals':duplicates,
        'estimated_duplicate_quote_overhead_usd':round(duplicate_overhead,12),
        'unexpected_interval_count':len(unexpected),
        'unexpected_intervals':unexpected,
        'unresolved_reservation_object_count':len(reservations),
        'consolidation_state':consolidation_state,
        'consolidation_key':consolidation_key,
        'native_dbn_object_count':len(native),
        'native_dbn_bytes':sum(int(o.get('Size',0)) for o in native),
        'manifest_parse_error_count':len(manifest_errors),
        'safe_to_cancel_databento':(
            len(expected_with_job)==len(expected)
            and not expected_reserved
            and not expected_missing
            and len(completed_expected)==len(expected)
            and not manifest_errors
            and len(native)>0
        ),
        'policy':'Do not cancel Databento until safe_to_cancel_databento is true and native hashes/manifests are independently verified.',
    }
    Path('research/kalshi/NG_MBO_5Y_COMPACT_AUDIT_20260820.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print(json.dumps(output,indent=2,sort_keys=True))

if __name__=='__main__': main()
