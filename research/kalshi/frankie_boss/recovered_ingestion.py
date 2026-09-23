"""Explicit admission of an independently verified sealed ingestion recovery.

This reads the original container in place. It does not replay source records,
restore an adapter, forge a normal-ingestion receipt, or rewrite producer evidence.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from . import c15_journal
from .block_source_scope import block_source_scope
from .causal_prefix_records import RecordPrefixChain
from .sealed_compact_recovery import ORIGINAL_CODE_BLOBS, original_identity
from .source_conformance import SourceCompletion

SCHEMA='FRANKIE_VERIFIED_RECOVERED_INGESTION_V1'

def _witness(path):
    path=Path(path)
    sha=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(8*1024*1024),b''): sha.update(block)
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha.hexdigest())

def _pinned(pin):
    if (type(pin) is not dict or not {'path','sha256','bytes'} <= set(pin)
            or type(pin['bytes']) is not int or pin['bytes']<0):
        raise ValueError('explicit file witness required')
    path=Path(pin['path'])
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError('pinned recovery artifact must be an absolute regular file')
    actual=_witness(path)
    if any(actual[k]!=pin[k] for k in ('sha256','bytes')):
        raise ValueError('pinned recovery artifact bytes differ')
    return path

def _json(pin):
    return json.loads(_pinned(pin).read_bytes())

def load_recovered_ingestion(pin):
    descriptor=_json(pin)
    if type(descriptor) is not dict or set(descriptor)!={'schema','source_manifest','recovery_receipt','verification','checkpoint','completion'} or descriptor['schema']!=SCHEMA:
        raise ValueError('explicit verified recovered ingestion descriptor required')
    receipt=_json(descriptor['recovery_receipt'])
    verification=_json(descriptor['verification'])
    checkpoint_path=_pinned(descriptor['checkpoint'])
    completion_path=_pinned(descriptor['completion'])
    manifest=_json(descriptor['source_manifest'])
    state=c15_journal.unpack(json.loads(checkpoint_path.read_bytes()))
    completion=json.loads(completion_path.read_bytes())
    if (receipt.get('schema')!='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1'
            or receipt.get('status')!='complete' or receipt.get('original_ingest_status')!='Cancelled'
            or receipt.get('session_policy')!='cme_trading_day' or receipt.get('trading_day')!='20211004'
            or receipt.get('source_object_naming')!='member_key'):
        raise ValueError('sealed recovery receipt provenance differs')
    if (verification.get('schema')!='FRANKIE_MONDAY_INGESTION_RECOVERY_VERIFIED_V1'
            or verification.get('status')!='complete'
            or verification.get('original_ingest_status')!='Cancelled'
            or verification.get('completion_method')!='sealed_journal_conformance_recovery'
            or verification.get('original_implementation_roundtrip') is not True):
        raise ValueError('independent recovery verification differs')
    if verification.get('recovery_receipt_sha256')!=descriptor['recovery_receipt']['sha256']:
        raise ValueError('independent raw recovery receipt hash differs')
    for body in (receipt,verification):
        if any(type(body.get(k)) is not int or body[k]!=0 for k in
                ('source_replays','adapter_apply_calls','parent_writes','model_calls')):
            raise ValueError('recovery must not replay, write the parent, or call a model')
    if receipt.get('training_updates')!=0:
        raise ValueError('recovery training updates differ')
    scope=block_source_scope(manifest,expected_manifest_hash=receipt['manifest_hash'])
    if (manifest.get('trading_day')!='20211004'
            or verification.get('source_manifest_hash')!=manifest['manifest_hash']
            or [x.get('session_id') for x in receipt.get('sessions',[])]!=['20211004']):
        raise ValueError('recovered source manifest or session differs')
    original=original_identity(ORIGINAL_CODE_BLOBS, require_adapter_semantics=False)
    state_hash=c15_journal.evidence_hash({k:v for k,v in state.items() if k!='state_hash'})
    if (state.get('implementation')!=original or receipt.get('original_implementation')!=original
            or state.get('state_hash')!=state_hash or receipt.get('checkpoint_state_hash')!=state_hash
            or verification.get('checkpoint_state_hash')!=state_hash
            or state.get('scope_genesis_hash')!=scope.genesis_hash()):
        raise ValueError('original recovery implementation or checkpoint state differs')
    for key,artifact in (('checkpoint',checkpoint_path),('completion',completion_path)):
        expected=receipt['artifacts'][key]
        actual=descriptor[key]
        if any(expected[k]!=actual[k] for k in ('sha256','bytes')) or expected.get('file')!=artifact.name:
            raise ValueError('recovered artifact differs from original receipt')
    if verification.get('checkpoint_sha256')!=descriptor['checkpoint']['sha256']:
        raise ValueError('independent checkpoint bytes differ')
    completed=SourceCompletion(**dict(completion,member_counts=tuple(completion['member_counts'])))
    chain=RecordPrefixChain.restore(scope,state['prefix'])
    expected=dict(schema='BOSS_SOURCE_CONFORMANCE_V1',builder_state_hash=state_hash,
        scope_kind=scope.kind.value,scope_hash=scope.genesis_hash(),record_count=chain.next_cursor,
        member_counts=tuple(m.mbo_records for m in scope.members),
        group_count=chain.next_global_group_ordinal,source_prefix_hash=chain.prefix_hash,
        journal_count=state['journal_count'],journal_hash=state['journal_hash'])
    normalized=dict(completion,member_counts=tuple(completion['member_counts']))
    if normalized!=expected or completed.digest!=receipt.get('completion_digest') or completed.digest!=verification.get('completion_digest'):
        raise ValueError('independent completion and restored prefix differ')
    for key in ('scope_hash','record_count','journal_count','journal_hash','group_count','source_prefix_hash'):
        if receipt.get(key)!=completion[key] or verification.get(key)!=completion[key]:
            raise ValueError('recovery count or prefix differs: '+key)
    if (chain.next_cursor!=sum(m.mbo_records for m in scope.members)
            or state['journal_count']!=2*chain.next_cursor
            or state['adapter']['record_count']!=chain.next_cursor
            or state['adapter']['completed_event_group_count']!=chain.next_global_group_ordinal):
        raise ValueError('recovered source is incomplete')
    window=verification.get('requested_window')
    if window!=dict(clock='ts_recv_ns',start_inclusive_ns=1633298400000000000,end_exclusive_ns=1633381200000000000):
        raise ValueError('independent Monday window differs')
    pre=verification.get('retained_preopen_context_records')
    count=verification.get('requested_window_records')
    if (type(pre) is not int or type(count) is not int or pre<0 or count<1
            or pre+count!=chain.next_cursor or verification.get('first_window_source_cursor')!=pre
            or verification.get('last_window_source_cursor')!=chain.next_cursor-1):
        raise ValueError('independent window coverage differs')
    container=receipt.get('container')
    if container!=verification.get('container'):
        raise ValueError('independent original container differs')
    path=Path(container['path'])
    if any(Path(str(path)+suffix).exists() for suffix in ('-wal','-shm','-journal')):
        raise ValueError('sealed original container has a live sidecar')
    _pinned(container)
    provenance=dict(descriptor=pin,recovery_receipt=descriptor['recovery_receipt'],
        verification=descriptor['verification'],checkpoint=descriptor['checkpoint'],
        completion=descriptor['completion'],original_implementation=original,
        original_ingest_status=receipt['original_ingest_status'])
    return SimpleNamespace(receipt=receipt,verification=verification,manifest=manifest,state=state,
        completion=completion,container=container,checkpoint_path=checkpoint_path,completion_path=completion_path,
        provenance=provenance,descriptor=descriptor,scope=scope)
