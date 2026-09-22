"""Publish a separately receipted recovery; never manufacture an original ingest receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

from .block_source_scope import block_source_scope
from .c15_journal import canonical_bytes, pack
from .sealed_compact_recovery import reconstruct, ORIGINAL_CODE_BLOBS

MANIFEST_HASH = 'a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355'
PARENT = '/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite'
PARENT_SHA = '947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888'
PARENT_HEAD = '534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c'

def write_once(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return dict(file=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def put(url, raw):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=raw, method='PUT'), timeout=120) as response:
            if response.status != 200:
                raise RuntimeError('unexpected artifact upload status')
    except Exception:
        raise RuntimeError('artifact upload failed; retained local evidence requires publication retry') from None

def validate_boundary(boundary,manifest):
    if (boundary.get('schema')!='FRANKIE_MONDAY_SOURCE_BOUNDARY_V1' or
            boundary.get('manifest_hash')!=MANIFEST_HASH or boundary.get('verified') is not True):
        raise ValueError('fresh independently verified source boundary required')
    last=boundary['last_included']
    first=boundary['first_excluded']
    if (boundary['take']!=1975176 or boundary['partition_mbo_records']!=1994358 or
            boundary['source_sha256']!=manifest['sources'][1]['sha256'] or
            last['session_id']!='20211004' or first['session_id']<='20211004' or
            last['is_last'] is not True):
        raise ValueError('boundary witness disagrees with declared Monday source')


def validate_retained(result,boundary):
    last=boundary['last_included']
    retained=result['member_boundaries'][1]
    if (retained['wire_sha256']!=last['wire_sha256'] or retained['ts_recv_ns']!=last['ts_recv_ns'] or
            retained['session_id']!=last['session_id'] or retained['is_last']!=last['is_last'] or
            retained['cursor']!=2032202):
        raise ValueError('source cutoff witness differs from the retained journal boundary')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--boundary', required=True)
    parser.add_argument('--code-commit', required=True)
    parser.add_argument('--upload-map', required=True)
    args=parser.parse_args()
    output=Path(args.output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('recovery output path must not contain symlinks')
    if output.parent != Path('/opt/frankie-box/work') or not output.name.startswith('sealed-recovery-'):
        raise ValueError('recovery requires a fresh isolated work directory')
    output.mkdir(exist_ok=False)
    uploads=json.loads(Path(args.upload_map).read_bytes())
    required={'source-boundary.json','builder-checkpoint.c15.json','completion.json','recovery-receipt.json'}
    if not required.issubset(uploads) or any(not isinstance(uploads[name],str) or not uploads[name].startswith('https://') for name in required):
        raise ValueError('complete HTTPS publication destinations required before recovery')
    root=Path(__file__).resolve().parents[3]
    manifest_raw=(root/'research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json').read_bytes()
    manifest=json.loads(manifest_raw)
    scope=block_source_scope(manifest, expected_manifest_hash=MANIFEST_HASH)
    boundary_raw=Path(args.boundary).read_bytes()
    boundary=json.loads(boundary_raw)
    validate_boundary(boundary,manifest)
    write_once(output/'source-boundary.json',boundary_raw)
    started=time.time()
    def emit(value):
        line=json.dumps(dict(value,unix=time.time()),sort_keys=True)+'\n'
        print(line,end='',flush=True)
        with (output/'progress.jsonl').open('a') as stream:
            stream.write(line)
            stream.flush()
        if 'progress.jsonl' in uploads:
            try:
                put(uploads['progress.jsonl'],(output/'progress.jsonl').read_bytes())
            except RuntimeError:
                print('Progress upload unavailable; local append-only progress retained',flush=True)
    emit(dict(phase='physical_identity_verification',bytes=23687368704))
    result=reconstruct(scope,PARENT,expected_sha256=PARENT_SHA,expected_bytes=23687368704,
        expected_count=4064406,expected_head_hash=PARENT_HEAD,code_blobs=ORIGINAL_CODE_BLOBS,
        workers=31,expected_session='20211004',emit=emit)
    validate_retained(result,boundary)
    emit(dict(phase='conformance_complete',records=result['completion']['record_count']))
    publish(output,uploads,result,boundary_raw,scope,args.code_commit,started)


def publish(output,uploads,result,boundary_raw,scope,code_commit,started):
    artifacts={}
    raw_checkpoint=canonical_bytes(pack(result['state']))
    artifacts['checkpoint']=write_once(output/'builder-checkpoint.c15.json',raw_checkpoint)
    raw_completion=(json.dumps(result['completion'],sort_keys=True,indent=2)+'\n').encode()
    artifacts['completion']=write_once(output/'completion.json',raw_completion)
    receipt=dict(schema='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1',status='complete',
        recovery_started_unix=started,recovered_unix=time.time(),code_commit=code_commit,
        original_ingest_status='Cancelled',original_run_id=35694087514,
        original_ssm_command_id='eea87d2f-a1d7-428e-ab57-3fdab2980eb6',
        manifest_hash=MANIFEST_HASH,scope_hash=scope.genesis_hash(),trading_day='20211004',
        session_policy='cme_trading_day',halt_utc_hour=21,source_object_naming='member_key',
        record_count=result['completion']['record_count'],journal_count=result['completion']['journal_count'],
        journal_hash=result['completion']['journal_hash'],group_count=result['completion']['group_count'],
        source_prefix_hash=result['completion']['source_prefix_hash'],completion_digest=result['completion_digest'],
        checkpoint_state_hash=result['state']['state_hash'],original_implementation=result['state']['implementation'],
        container=result['container'],source_boundary_sha256=hashlib.sha256(boundary_raw).hexdigest(),
        sessions=result['sessions'],member_boundaries=result['member_boundaries'],artifacts=artifacts,
        resources=result['resources'],source_replays=0,adapter_apply_calls=0,parent_writes=0,
        model_calls=0,training_updates=0)
    raw_receipt=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
    write_once(output/'recovery-receipt.json',raw_receipt)
    # Commit marker uploaded last, after both independently hashed artifacts.
    for name in ('source-boundary.json','builder-checkpoint.c15.json','completion.json'):
        put(uploads[name],(output/name).read_bytes())
    put(uploads['recovery-receipt.json'],raw_receipt)
    print('RECOVERY_RECEIPT '+raw_receipt.decode().replace('\n',''),flush=True)

if __name__=='__main__':
    main()
