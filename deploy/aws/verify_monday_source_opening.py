"""Classify the exact Sunday18ET to Monday17ET window without state replay."""
from collections import Counter
from contextlib import ExitStack
import hashlib,io,json,os
from pathlib import Path
from types import SimpleNamespace
from verify_monday_source_boundary import ROOT,MANIFEST,functions,require
import datetime as dt

def main():
    require(not any(os.environ.get(k) for k in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN')),'credential-free decoder required')
    import databento_dbn as dbn
    import zstandard as zstd
    from importlib.metadata import version
    require(version('databento-dbn')=='0.62.0' and version('zstandard')=='0.25.0','pinned decoder required')
    name='glbx-mdp3-20211003.mbo.dbn.zst'
    sha='4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88'
    raw=Path(name).read_bytes()
    require(len(raw)==973355 and hashlib.sha256(raw).hexdigest()==sha,'Sunday source identity differs')
    boundary_raw=(ROOT/'research/kalshi/frankie_boss/blocks/MONDAY_SOURCE_BOUNDARY_VERIFIED_20260922.json').read_bytes()
    boundary=json.loads(boundary_raw)
    require(boundary['verified'] is True and boundary['manifest_hash']==MANIFEST and boundary['take']==1975176,'verified ending boundary required')
    namespace=dict(tempfile=SimpleNamespace(TemporaryFile=io.BytesIO),_extract=lambda record,pin,module:record)
    decoder=functions(ROOT/'research/kalshi/frankie_boss/mbo_source.py',{'_decompressed','_read_exact','_metadata','_records'},namespace)
    count=in_window=after=0
    pre=[]
    first=last=None
    late=False
    def row(r,n):
        wire=bytes(r)
        return dict(member_record_number=n,source_cursor=n-1,ts_recv_ns=int(r.ts_recv),ts_event_ns=int(r.ts_event),
            action=str(r.action),flags=int(r.flags),is_snapshot=bool(int(r.flags)&32),is_last=bool(int(r.flags)&128),
            instrument_id=int(r.instrument_id),sequence=int(r.sequence),wire_sha256=hashlib.sha256(wire).hexdigest(),wire_hex=wire.hex())
    with ExitStack() as stack:
        stream=namespace['_decompressed'](io.BytesIO(raw),zstd,stack)
        pin=SimpleNamespace(dbn_version=3)
        metadata,ts_out=namespace['_metadata'](stream,pin,dbn)
        for r in namespace['_records'](stream,pin,ts_out,dbn):
            count+=1
            stamp=int(r.ts_recv)
            if stamp<1633298400000000000:
                pre.append(row(r,count))
                late|=first is not None
            elif stamp<1633381200000000000:
                in_window+=1
                current=row(r,count)
                if first is None:first=current
                last=current
            else:after+=1
            require(count<=57027,'source count exceeds declaration')
    require(count==57027 and first and after==0 and count==len(pre)+in_window,'source classification incomplete')
    receipt=dict(schema='FRANKIE_MONDAY_SOURCE_OPENING_V1',verified=True,code_commit=os.environ['GITHUB_SHA'],
        github_run_id=os.environ['GITHUB_RUN_ID'],verified_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_sha256=sha,source_bytes=len(raw),manifest_hash=MANIFEST,decoder_code=decoder,
        monday_end_boundary_sha256=hashlib.sha256(boundary_raw).hexdigest(),
        window=dict(clock='ts_recv_ns',start_inclusive_ns=1633298400000000000,end_exclusive_ns=1633381200000000000),
        sunday_physical_records=count,before_open_records=len(pre),sunday_in_window_records=in_window,
        monday_member_in_window_records=boundary['take'],actual_window_source_records=in_window+boundary['take'],
        sealed_physical_source_records=2032203,after_window_records=after,
        before_open_forms_initial_prefix=not late,before_open_all_snapshot=bool(pre) and all(x['is_snapshot'] for x in pre),
        before_open_non_snapshot_records=sum(not x['is_snapshot'] for x in pre),
        before_open_actions=dict(Counter(x['action'] for x in pre)),before_open_flags=dict(Counter(str(x['flags']) for x in pre)),
        first_window_record=first,last_sunday_window_record=last,last_preopen_record=pre[-1] if pre else None,
        before_open_records_full=pre,source_replays=0,adapter_apply_calls=0,journal_reads=0,journal_writes=0)
    raw_receipt=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
    with Path('source-opening.json').open('xb') as stream:stream.write(raw_receipt)
    summary={k:v for k,v in receipt.items() if k!='before_open_records_full'}
    summary['full_receipt_sha256']=hashlib.sha256(raw_receipt).hexdigest()
    print('SOURCE_OPENING '+json.dumps(summary,sort_keys=True),flush=True)
if __name__=='__main__':main()
