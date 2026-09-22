"""Independently verify published recovery artifacts with the original implementation."""
import hashlib,json,os,sys,time
from pathlib import Path
import boto3

BUCKET='frankie-granite42-568968024170-us-east-1'
PREFIX='readiness/20260922/sealed-recovery/35797500956/'
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    s3=boto3.client('s3',region_name='us-east-1')
    started=time.time()
    while True:
        try:raw_receipt=s3.get_object(Bucket=BUCKET,Key=PREFIX+'recovery-receipt.json')['Body'].read();break
        except s3.exceptions.NoSuchKey:
            if time.time()-started>20000:raise RuntimeError('published recovery is not complete')
            time.sleep(30)
    receipt=json.loads(raw_receipt)
    require(receipt['schema']=='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1' and receipt['status']=='complete',
        'explicit recovery completion required')
    require(receipt['code_commit']=='01945e24da7ac3e628b897a5d45fda2cde9b1536'
        and receipt['original_ingest_status']=='Cancelled' and receipt['record_count']==2032203
        and receipt['journal_count']==4064406 and receipt['source_replays']==receipt['adapter_apply_calls']==receipt['parent_writes']==0,
        'recovery identity/count/preservation differs')
    require(receipt['container']==dict(path='/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite',
        bytes=23687368704,sha256='947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888'),'container witness differs')
    bodies={}
    for name in ('builder-checkpoint.c15.json','completion.json','source-boundary.json','publication-receipt.json'):
        bodies[name]=s3.get_object(Bucket=BUCKET,Key=PREFIX+name)['Body'].read()
    for field,name in (('checkpoint','builder-checkpoint.c15.json'),('completion','completion.json')):
        pin=receipt['artifacts'][field]
        require(pin['file']==name and pin['bytes']==len(bodies[name]) and pin['sha256']==sha(bodies[name]),'artifact hash/size differs')
    require(sha(bodies['source-boundary.json'])==receipt['source_boundary_sha256'],'ending witness differs')
    publication=json.loads(bodies['publication-receipt.json'])
    require(publication['recovery_receipt_sha256']==sha(raw_receipt) and publication['status']=='complete'
        and publication['computation_run_id']==35796793428,'publication witness differs')
    # Load only the original pinned implementation for the independent checkpoint roundtrip.
    sys.path.insert(0,str(Path('.original').resolve()))
    from types import SimpleNamespace
    from research.kalshi.frankie_boss.c15_journal import canonical_bytes,pack,unpack,evidence_hash
    from research.kalshi.frankie_boss.c15_builder import C15Builder
    from research.kalshi.frankie_boss.c15_registry import implementation_identity
    from research.kalshi.frankie_boss.mbo_resume_state import restore_adapter_state
    from research.kalshi.frankie_boss.causal_prefix_records import RecordPrefixChain
    from research.kalshi.frankie_boss.block_source_scope import block_source_scope
    from research.kalshi.frankie_boss.source_conformance import SourceCompletion
    manifest=json.loads(Path('research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json').read_bytes())
    scope=block_source_scope(manifest,expected_manifest_hash='a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355')
    state=unpack(json.loads(bodies['builder-checkpoint.c15.json']))
    require(state['implementation']==implementation_identity()==receipt['original_implementation'],'original scientific implementation differs')
    require(state['state_hash']==receipt['checkpoint_state_hash']
        and state['state_hash']==evidence_hash({k:v for k,v in state.items() if k!='state_hash'}),'checkpoint hash differs')
    builder=C15Builder.__new__(C15Builder)
    builder.scope,builder.identity=scope,implementation_identity()
    builder.adapter=restore_adapter_state(state['adapter'])
    builder.chain=RecordPrefixChain.restore(scope,state['prefix'])
    builder._sessions=dict(state['sessions'])
    builder._failed=False
    builder.journal=SimpleNamespace(count=state['journal_count'],head_hash=state['journal_hash'])
    require(canonical_bytes(pack(builder.export_state()))==bodies['builder-checkpoint.c15.json'],'original implementation roundtrip differs')
    completion=json.loads(bodies['completion.json'])
    completion['member_counts']=tuple(completion['member_counts'])
    record=SourceCompletion(**completion)
    require(record.digest==receipt['completion_digest'] and record.builder_state_hash==state['state_hash']
        and record.scope_hash==scope.genesis_hash() and record.record_count==2032203
        and record.member_counts==(57027,1975176) and record.journal_count==4064406
        and record.journal_hash=='534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c',
        'full conformance completion differs')
    opening_raw=s3.get_object(Bucket=BUCKET,Key='readiness/20260922/sealed-recovery/35796992952/source-opening.json')['Body'].read()
    require(sha(opening_raw)=='e1c61be7678132712ca6de82606621cc51e10e08d4da82f11afc34b398a718af','opening witness differs')
    opening=json.loads(opening_raw)
    require(opening['verified'] and opening['before_open_forms_initial_prefix']
        and opening['before_open_records']==447 and opening['actual_window_source_records']==2031756
        and opening['first_window_record']['source_cursor']==447 and opening['last_preopen_record']['is_last']
        and opening['monday_end_boundary_sha256']==receipt['source_boundary_sha256'],
        'requested window coverage differs')
    verified=dict(schema='FRANKIE_MONDAY_INGESTION_RECOVERY_VERIFIED_V1',status='complete',
        verified_unix=time.time(),verification_run_id=os.environ['GITHUB_RUN_ID'],verification_commit=os.environ['GITHUB_SHA'],
        source_recovery_run_id=35796793428,publication_run_id=35797500956,
        recovery_receipt_sha256=sha(raw_receipt),recovery_receipt_s3=dict(bucket=BUCKET,key=PREFIX+'recovery-receipt.json'),
        original_ingest_status='Cancelled',completion_method='sealed_journal_conformance_recovery',
        original_implementation_roundtrip=True,source_manifest_hash=manifest['manifest_hash'],scope_hash=scope.genesis_hash(),
        record_count=2032203,journal_count=4064406,group_count=record.group_count,
        source_prefix_hash=record.source_prefix_hash,journal_hash=record.journal_hash,container=receipt['container'],
        checkpoint_sha256=sha(bodies['builder-checkpoint.c15.json']),checkpoint_state_hash=state['state_hash'],
        completion_digest=record.digest,requested_window=opening['window'],
        requested_window_records=2031756,first_window_source_cursor=447,last_window_source_cursor=2032202,
        retained_preopen_context_records=447,opening_receipt_sha256=sha(opening_raw),
        source_replays=0,adapter_apply_calls=0,parent_writes=0,model_calls=0)
    raw=(json.dumps(verified,sort_keys=True,indent=2)+'\n').encode()
    Path('verified-ingestion-recovery.json').write_bytes(raw)
    s3.put_object(Bucket=BUCKET,Key='readiness/20260922/sealed-recovery/'+os.environ['GITHUB_RUN_ID']+'/verified-ingestion-recovery.json',
        Body=raw,IfNoneMatch='*',ServerSideEncryption='AES256')
    print('VERIFIED_INGESTION_RECOVERY '+json.dumps(verified,sort_keys=True),flush=True)
if __name__=='__main__':main()
