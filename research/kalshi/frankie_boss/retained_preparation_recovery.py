"""Recover a retained first-prefix preparation, calculating only its missing teacher.

No adapter replay, native forward, or full-source read. Returned tuples must still
be installed through the host's independently bound cache/checkpoint lifecycle.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from . import granite_context_compact as compact
from .c15_journal import unpack,pack,evidence_hash
from .causal_prefix_records import RecordPrefixChain,RecordInput
from .context_session import journal_prefix,tensor_identity,PACKET_SCHEMA
from .verified_journal_reader import VerifiedJournalReader
from .granite_context import PACKET_FIELDS


def _bytes(pin):
    raw=Path(pin['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('retained artifact byte pin differs')
    return raw


def recover_retained_preparation(context,witness,*,as_of,through_cursor,progress=None):
    """Return exact (tokens,info,input_hash,teacher,rows) from explicit file pins.

    witness schema RETAINED_FIRST_PREPARATION_RECOVERY_V1 carries request,
    prepared, initialization {path,sha256}, and prefix {path,sha256,count,head_hash}.
    Only contiguous complete first-prefix context is supported. No cached tuple
    is accepted merely because its digest looks correct.
    """
    if (set(witness)!={'schema','request','prepared','initialization','prefix'} or
            witness.get('schema')!='RETAINED_FIRST_PREPARATION_RECOVERY_V1'):raise ValueError('retained recovery schema differs')
    if context.builder._failed or context.builder.chain.next_cursor!=through_cursor+1:
        raise ValueError('healthy exact retained prefix view required')
    request_raw=_bytes(witness['request']);prepared=json.loads(_bytes(witness['prepared']))
    initial=unpack(json.loads(_bytes(witness['initialization'])))
    if (prepared['schema']!='BOSS_ACTUAL_CRITIC_INPUT_V1' or
            prepared['request_sha256']!=hashlib.sha256(request_raw).hexdigest() or
            prepared['request_bytes']!=len(request_raw) or prepared['model_forward_performed'] is not False or
            prepared['inference_performed'] is not False):raise ValueError('retained preparation receipt differs')
    if (context._model_hash()!=initial['native_hash'] or context.teacher is None or
            context.teacher.binding!=initial['teacher_binding'] or
            pack(context.teacher.normalizer.export())!=pack(initial['teacher_normalizer'])):
        raise ValueError('retained native or initial teacher identity differs')
    request=json.loads(request_raw);messages=request['messages']
    if len(messages)!=1 or messages[0]['role']!='user':raise ValueError('retained exact user request required')
    prompt=messages[0]['content']
    if hashlib.sha256(prompt.encode()).hexdigest()!=prepared['prompt_sha256']:raise ValueError('retained prompt differs')
    marker='\ncompact_native_context:\n'
    text=prompt.split(marker,1)[1]
    snapshot=compact.parse_compact_context(text,expected_hash=prepared['compact_snapshot_hash'])
    if compact.build_compact_prompt(snapshot).text!=prompt:raise ValueError('retained prompt canonical form differs')
    native=snapshot.native()
    if native.hash!=prepared['native_snapshot_hash']:raise ValueError('retained native snapshot differs')
    body=json.loads(native.text);receipt=unpack(body['receipt'])
    if json.loads(json.dumps(receipt))!=prepared['context']:raise ValueError('retained context receipt differs')
    if (receipt['model_hash']!=initial['native_hash'] or receipt['teacher_binding']!=initial['teacher_binding'] or
            prepared['teacher_binding']!=initial['teacher_binding'] or receipt['as_of']!=as_of or
            receipt['t_ctx']!=context.t_ctx or tuple(body['entity'])!=context.entity or
            receipt['registry_hash']!=context.model.trunk.registry.digest or
            receipt['scope_hash']!=context.builder.scope.genesis_hash() or context.qsv is not None or
            receipt['context_cursors']!=tuple(range(through_cursor+1)) or receipt['prefix_rows']!=through_cursor+1 or
            receipt['consumed_rows']!=through_cursor+1):raise ValueError('exact complete first-prefix context required')
    tokens=native.reconstruct()
    device=context.model.trunk.encoder.numeric.weight.device
    tokens={key:value.to(device=device) for key,value in tokens.items()}
    payloads=native.payloads();chain=RecordPrefixChain(context.builder.scope);by_cursor={}
    for payload in payloads:
        meta=payload['metadata'];source=meta['source_context']
        normalized={k:v for k,v in meta['adapter'].items() if k!='independent_clocks'}
        chain.advance(RecordInput(source['cursor'],source['source_member_index'],normalized,context.builder.scope.adapter_revision))
        row=dict(cursor=source['cursor'],raw_record=payload['record'],normalized=normalized,
            source_member_index=source['source_member_index'],session_id=source['session_id'],
            integrity=meta['defects'],terminal_prefix_hash=chain.prefix_hash)
        packet=evidence_hash(dict(schema=PACKET_SCHEMA,source_prefix=chain.prefix_hash,record=payload['record'],metadata=meta,as_of=as_of))
        if packet!=receipt['packet_hashes'][source['cursor']]:raise ValueError('retained per-row packet differs')
        by_cursor[source['cursor']]=row
    rows=[by_cursor[cursor] for cursor in receipt['context_cursors']]
    if chain.prefix_hash!=receipt['source_prefix_hash']:raise ValueError('retained terminal prefix differs')
    info={name:receipt[name] for name in PACKET_FIELDS}
    input_hash=evidence_hash(dict(info=info,entity=context.entity,tensors=tensor_identity(tokens)))
    if input_hash!=receipt['input_hash']:raise ValueError('retained native tensor input identity differs')
    pin=witness['prefix'];path=Path(pin['path'])
    wal=Path(str(path)+'-wal')
    if path.is_symlink() or (wal.exists() and wal.stat().st_size):raise ValueError('retained prefix must be closed')
    if (context.builder.journal.count,context.builder.journal.head_hash)!=(pin['count'],pin['head_hash']):
        raise ValueError('context journal handle differs from retained checkpoint')
    with path.open('rb') as stream:physical=hashlib.file_digest(stream,'sha256').hexdigest()
    if physical!=pin['sha256'] or pin['count']!=2*(through_cursor+1) or pin['head_hash']!=receipt['journal_prefix_hash']:
        raise ValueError('retained closed prefix witness differs')
    if path.resolve()!=Path(context.builder.journal.path).resolve():raise ValueError('context uses a different retained prefix')
    reader=VerifiedJournalReader(path,expected_count=pin['count'],expected_head_hash=pin['head_hash'])
    view=SimpleNamespace(_failed=False,scope=context.builder.scope,chain=SimpleNamespace(next_cursor=through_cursor+1),journal=reader)
    summary={}
    def evidence():
        for index,row in enumerate(journal_prefix(view,through_cursor,summary),1):
            if progress is not None and (index%100==0 or index==through_cursor+1):progress(index,through_cursor+1)
            yield row
    try:teacher=context.teacher.attach(evidence(),rows,as_of=as_of,source_manifest_hash=context.builder.scope.scope_id)
    finally:reader.close()
    if (teacher['attachment_hash']!=receipt['teacher_hash'] or teacher['processed_records']!=through_cursor+1 or
            teacher['context_cursors']!=receipt['context_cursors'] or len(teacher['targets'])!=len(rows) or
            summary['journal_entries']!=receipt['journal_entries'] or summary['journal_prefix_hash']!=receipt['journal_prefix_hash']):
        raise ValueError('recovered teacher or journal attachment differs from retained receipt')
    if context._model_hash()!=initial['native_hash'] or context.teacher.binding!=initial['teacher_binding']:
        raise ValueError('recovery identities changed during calculation')
    return tokens,info,input_hash,teacher,rows
