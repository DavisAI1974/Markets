"""Independent source-boundary verification. No adapter or journal operations."""
import ast
from contextlib import ExitStack
import datetime as dt
import hashlib
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
MEMBER='glbx-mdp3-20211004.mbo.dbn.zst'
SHA='8ed47cc0a68cf40cae9fde45e158142978076e60d3f9fc7cf940196babfddc0a'
MANIFEST='a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355'
def require(ok,message):
    if not ok:raise ValueError(message)
def functions(path,names,namespace):
    raw=path.read_bytes()
    nodes=[x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name in names]
    require(len(nodes)==len(names) and not any(x.decorator_list for x in nodes),'unexpected decoder functions')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),functions=sorted(names))
def main():
    require(not any(os.environ.get(k) for k in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN')),
        'decoder stage must not carry AWS credentials')
    import databento_dbn as dbn
    import zstandard as zstd
    versions={name:version(name) for name in ('databento-dbn','zstandard')}
    require(versions=={'databento-dbn':'0.62.0','zstandard':'0.25.0'},'decoder versions differ')
    raw=Path(MEMBER).read_bytes()
    require(len(raw)==34300424 and hashlib.sha256(raw).hexdigest()==SHA,'source physical identity differs')
    manifest_raw=(ROOT/'research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json').read_bytes()
    manifest=json.loads(manifest_raw)
    require(manifest['manifest_hash']==MANIFEST and manifest['sources'][1]['sha256']==SHA
        and manifest['partial_members']==[dict(member_key=MEMBER,partition_mbo_records=1994358,
        reason='records before the 21:00Z halt belong to this trading day; the rest are the next day',take=1975176)],
        'manifest differs from independently pinned declaration')
    namespace=dict(tempfile=SimpleNamespace(TemporaryFile=io.BytesIO),_extract=lambda record,pin,module:record,dt=dt)
    decoder=functions(ROOT/'research/kalshi/frankie_boss/mbo_source.py',
        {'_decompressed','_read_exact','_metadata','_records'},namespace)
    policy=functions(ROOT/'research/kalshi/frankie_boss/operations/ingest_block_sources.py',{'session_policy'},namespace)
    _,session=namespace['session_policy']('cme_trading_day',halt_utc_hour=21)
    class Frames:
        ZstdError=zstd.ZstdError
        def __init__(self):self.count=0
        def ZstdDecompressor(self):
            self.count+=1
            return zstd.ZstdDecompressor()
    frames=Frames()
    pin=SimpleNamespace(dbn_version=3)
    count=0
    sessions={}
    last=following=terminal=None
    def row(record,index,day):
        wire=bytes(record)
        return dict(member_record_number=index,session_id=day,ts_recv_ns=int(record.ts_recv),
            ts_event_ns=int(record.ts_event),flags=int(record.flags),is_last=bool(int(record.flags)&128),
            instrument_id=int(record.instrument_id),sequence=int(record.sequence),wire_sha256=hashlib.sha256(wire).hexdigest(),
            wire_hex=wire.hex())
    with ExitStack() as stack:
        stream=namespace['_decompressed'](io.BytesIO(raw),frames,stack)
        metadata,ts_out=namespace['_metadata'](stream,pin,dbn)
        for record in namespace['_records'](stream,pin,ts_out,dbn):
            count+=1
            stamp=int(record.ts_recv)
            day=session(None,{'ts_recv':stamp})
            sessions[day]=sessions.get(day,0)+1
            if count<=1975176:
                require(day=='20211004' and 1633298400000000000<=stamp<1633381200000000000,
                    'included record is outside Monday session')
                if count==1975176:last=row(record,count,day)
            else:
                require(day>'20211004' and stamp>=1633381200000000000,'excluded remainder re-enters Monday')
                if count==1975177:following=row(record,count,day)
            if count==1994358:terminal=row(record,count,day)
            require(count<=1994358,'partition exceeds declaration')
    require(count==1994358 and last and following and last['is_last'] and terminal['is_last'],
        'full count or closed boundary differs')
    receipt=dict(schema='FRANKIE_MONDAY_SOURCE_BOUNDARY_V1',verified=True,
        verification='new independent full source inspection; not the original ingest lookahead receipt',
        verified_at=dt.datetime.now(dt.timezone.utc).isoformat(),code_commit=os.environ['GITHUB_SHA'],
        github_run_id=os.environ['GITHUB_RUN_ID'],source_sha256=SHA,source_bytes=len(raw),
        source_bucket='bento-568968024170-us-east-2-an',source_key='frankie/block_20211004_20211006/sources/'+MEMBER,
        manifest_hash=MANIFEST,manifest_file_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        take=1975176,partition_mbo_records=count,sessions=sessions,last_included=last,first_excluded=following,
        last_record=terminal,decoder_code=decoder,session_policy_code=policy,versions=versions,
        metadata_sha256=hashlib.sha256(metadata).hexdigest(),zstd_frames=frames.count,
        adapter_apply_calls=0,journal_reads=0,journal_writes=0,source_replays=0)
    with Path('source-boundary.json').open('x') as out:json.dump(receipt,out,indent=2,sort_keys=True);out.write('\n')
    print('SOURCE_BOUNDARY '+json.dumps(receipt,sort_keys=True),flush=True)
if __name__=='__main__':main()
