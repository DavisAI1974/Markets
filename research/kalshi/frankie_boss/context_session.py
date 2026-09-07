"""BOSS_CONTEXT_SESSION_V1: receipted native context over complete C15 evidence.

One context row is one market record, not one SQLite audit entry. Model context
is declared separately from evidence retention. Native mapping and journal
coverage are verified before any model forward; no result-bearing run is implied.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import heapq
import torch
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

try:
    from .native_mbo_encoder import NativeTrunk, T_CTX, encode, reconstruct_payloads
    from .b1_reasoner import B1Reasoner
    from .c15_journal import evidence_hash, pack, unpack
    from .trunk import TRUNK_SCHEMA
except ImportError:
    from native_mbo_encoder import NativeTrunk, T_CTX, encode, reconstruct_payloads
    from b1_reasoner import B1Reasoner
    from c15_journal import evidence_hash, pack, unpack
    from trunk import TRUNK_SCHEMA

SCHEMA = 'BOSS_CONTEXT_SESSION_V1'
PACKET_SCHEMA = 'BOSS_NATIVE_CONTEXT_RECORD_PACKET_V1'


def tensor_identity(tensors):
    return {k: dict(dtype=str(v.dtype), shape=tuple(v.shape),
                    bytes=v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
            for k,v in sorted(tensors.items())}


def journal_prefix(builder, through_cursor, summary=None):
    """Stream and verify every pair, yielding only the declared causal prefix.

    No full-day list is materialized. Iteration must finish to verify suffix/tail
    integrity. Future suffix counts never enter an earlier cutoff's receipt.
    """
    if builder._failed:
        raise ValueError('unprocessed evidence exists; builder is stopped')
    if type(through_cursor) is not int or not 0 <= through_cursor < builder.chain.next_cursor:
        raise ValueError('cutoff cursor outside applied journal')
    summary = {} if summary is None else summary
    applied=0; pending=None
    for entry in builder.journal.entries():
        payload=entry['payload']
        if entry['kind']=='INPUT':
            if pending is not None or payload['cursor'] != applied:
                raise ValueError('journal input cursor gap or unprocessed submission')
            pending=payload
        elif entry['kind']=='APPLIED':
            if (pending is None or payload['cursor'] != pending['cursor']
                    or pack(payload['raw_record']) != pack(pending['record'])
                    or any(payload[k] != pending[k] for k in ('source_member_index','session_id'))):
                raise ValueError('journal applied record differs from submitted evidence')
            applied+=1; pending=None
            if payload['cursor']<=through_cursor:
                summary.update(journal_prefix_hash=evidence_hash(entry),
                               journal_entries=entry['ordinal']+1)
                yield payload
        else:
            raise ValueError('failed or unknown journal entry cannot be mapped as complete')
    if pending is not None or applied!=builder.chain.next_cursor:
        raise ValueError('journal does not account for every source record')


def record_metadata(evidence):
    return dict(adapter={**evidence['normalized'],'independent_clocks':True}, source_context=dict(
        cursor=evidence['cursor'], source_member_index=evidence['source_member_index'],
        session_id=evidence['session_id']), defects=evidence['integrity'])


@dataclass(frozen=True)
class ContextReceipt:
    schema: str
    trunk_schema: str
    registry_hash: str
    scope_kind: str
    scope_hash: str
    teacher_hash: str | None
    teacher_binding: str | None
    input_hash: str
    model_hash: str
    journal_prefix_hash: str
    journal_entries: int
    source_prefix_hash: str
    prefix_rows: int
    entity_rows: int
    other_entity_rows: int
    context_start: int
    context_end: int
    outside_context_rows: int
    context_cursors: tuple[int,...]
    packet_hashes: tuple[str,...]
    consumed_rows: int
    as_of: int
    t_ctx: int


@dataclass(frozen=True)
class ContextOutput:
    heads: dict
    receipt: ContextReceipt
    recurrence_receipt: object | None
    teacher: object | None = None


class ContextSessionRunner:
    def __init__(self,model,builder,*,entity,t_ctx=T_CTX,teacher=None):
        if type(t_ctx) is not int or t_ctx<1:
            raise ValueError('positive declared context length required')
        if type(entity) is not tuple or len(entity)!=2 or any(type(x) is not int for x in entity):
            raise ValueError('entity must be exact (publisher_id,instrument_id)')
        self.model,self.builder,self.entity,self.t_ctx,self.teacher=model,builder,entity,t_ctx,teacher
        self._retry=None; self._last=None
        self._check_model()

    def _check_model(self):
        trunk=self.model.trunk if isinstance(self.model,B1Reasoner) else self.model
        if not isinstance(trunk,NativeTrunk):
            raise TypeError('native session requires NativeTrunk, optionally wrapped by B1')
        if any(m.training for m in self.model.modules()):
            raise ValueError('audited context inference requires eval mode')
        if trunk.encoder.numeric.weight.dtype!=torch.float64:
            raise ValueError('native model must use float64; implicit precision reduction forbidden')
        return trunk

    def _model_hash(self):
        trunk=self._check_model()
        names=('trunk.py','b1_reasoner.py','native_mbo_encoder.py','context_session.py',
               'c15_journal.py','causal_packet.py')
        code={n:Path(__file__).with_name(n).read_bytes() for n in names}
        return evidence_hash(dict(schema=SCHEMA,trunk_schema=TRUNK_SCHEMA,
            weights=tensor_identity(self.model.state_dict()),config=asdict(trunk.cfg),
            qsv_ablated=trunk.encoder._qsv_ablated,qsv_registry=QSV_FEATURE_REGISTRY,
            registry=trunk.registry.payload(),code=code,
            recurrence=asdict(self.model.config) if isinstance(self.model,B1Reasoner) else None))

    def append(self,record,**source):
        if self._retry is not None:
            raise ValueError('failed forward retained its input; retry run() before append')
        return self.builder.apply(record,**source)

    def _prepare(self,as_of,through_cursor):
        trunk=self._check_model()
        summary={}; prefix_rows=entity_rows=0; context_heap=[]; last=None
        for e in journal_prefix(self.builder,through_cursor,summary):
            last=e; prefix_rows+=1
            recv=e['normalized']['ts_recv_ns']
            if recv>as_of:
                raise ValueError('journal prefix contains future receive times; supply an earlier cursor')
            if (e['normalized']['publisher_id'],e['normalized']['instrument_id'])==self.entity:
                entity_rows+=1
                item=(recv,e['cursor'],{k:e[k] for k in ('cursor','raw_record','normalized','source_member_index','session_id','integrity','terminal_prefix_hash')})
                if len(context_heap)<self.t_ctx:
                    heapq.heappush(context_heap,item)
                else:
                    heapq.heappushpop(context_heap,item)
        context=[item[2] for item in sorted(context_heap)]
        start=max(0,entity_rows-self.t_ctx)
        rows=[e['raw_record'] for e in context]
        metadata=[record_metadata(e) for e in context]
        tokens=encode(rows,as_of=as_of,registry=trunk.registry,metadata=metadata)
        expected=[dict(record=r,metadata=m) for r,m in zip(rows,metadata)]
        if pack(reconstruct_payloads(tokens,trunk.registry))!=pack(expected):
            raise ValueError('native inverse reconstruction differs from journal evidence')
        device=trunk.encoder.numeric.weight.device
        tokens={k:v.to(device=device) for k,v in tokens.items()}
        packets=tuple(evidence_hash(dict(schema=PACKET_SCHEMA,source_prefix=e['terminal_prefix_hash'],
            record=e['raw_record'],metadata=m,as_of=as_of)) for e,m in zip(context,metadata))
        info=dict(schema=SCHEMA,trunk_schema=TRUNK_SCHEMA,registry_hash=trunk.registry.digest,
            **summary,source_prefix_hash=last['terminal_prefix_hash'],
            scope_kind=self.builder.scope.kind.value,scope_hash=self.builder.scope.genesis_hash(),
            teacher_hash=None,teacher_binding=None,
            prefix_rows=prefix_rows,entity_rows=entity_rows,other_entity_rows=prefix_rows-entity_rows,
            context_start=start,context_end=entity_rows,outside_context_rows=start,
            context_cursors=tuple(e['cursor'] for e in context),packet_hashes=packets,
            consumed_rows=len(context),as_of=as_of,t_ctx=self.t_ctx)
        teacher=None
        if self.teacher is not None:
            teacher=self.teacher.attach(journal_prefix(self.builder,through_cursor),context,as_of=as_of,
                source_manifest_hash=self.builder.scope.scope_id)
            info['teacher_hash']=teacher['attachment_hash']
            info['teacher_binding']=self.teacher.binding
        input_hash=evidence_hash(dict(info=info,entity=self.entity,tensors=tensor_identity(tokens)))
        return tokens,info,input_hash,teacher,context

    def run(self,*,as_of,through_cursor=None):
        cursor=self.builder.chain.next_cursor-1 if through_cursor is None else through_cursor
        identity=(as_of,cursor,self.builder.journal.count,self.builder.journal.head_hash)
        if self._retry is not None and self._retry[:4]!=identity:
            raise ValueError('retry the original failed cutoff with unchanged journal')
        tokens,info,input_hash,teacher,context=self._prepare(as_of,cursor)
        model_hash=self._model_hash()
        if self._retry is not None and self._retry[4:]!=(input_hash,model_hash):
            raise ValueError('retry input or model differs from failed forward')
        self._retry=identity+(input_hash,model_hash)
        kwargs=dict(tokens={k:v.detach().clone() for k,v in tokens.items()})
        kwargs['numeric']=kwargs['tokens']['numeric']
        # Native event-only candidate has no invented book/QSV projection. QSV
        # can be explicitly ablated; an enabled unablated branch requires a
        # separately governed mapping, and cannot be silently zero-filled.
        with torch.no_grad():
            if isinstance(self.model,B1Reasoner):
                heads=self.model.forward_decision(**kwargs,packet_hash=evidence_hash(info))
            else:
                heads=self.model(**kwargs)
        if heads['evidence_scores'].shape!=(1,len(context)) or any(not torch.isfinite(v).all() for v in heads.values()):
            raise ValueError('model did not produce finite evidence scores for every context row')
        if self._model_hash()!=model_hash:
            raise ValueError('model changed during forward; retry requires original model')
        receipt=ContextReceipt(**info,input_hash=input_hash,model_hash=model_hash)
        self._last=dict(tokens=tokens,receipt=receipt,through_cursor=cursor)
        self._retry=None
        return ContextOutput(dict(heads),receipt,getattr(heads,'receipt',None),teacher)

    def export(self):
        if self._retry is not None or self._last is None:
            raise ValueError('complete the pending cutoff before checkpoint export')
        last=self._last
        return dict(schema=SCHEMA,entity=self.entity,t_ctx=self.t_ctx,through_cursor=last['through_cursor'],
            receipt=asdict(last['receipt']),tokens={k:v.detach().clone() for k,v in last['tokens'].items()})

    @classmethod
    def restore(cls,model,builder,state,*,expected_input_hash,expected_model_hash,teacher=None):
        if set(state)!={'schema','entity','t_ctx','through_cursor','receipt','tokens'} or state['schema']!=SCHEMA:
            raise ValueError('invalid native session checkpoint')
        result=cls(model,builder,entity=tuple(state['entity']),t_ctx=state['t_ctx'],teacher=teacher)
        receipt=state['receipt']
        if result._model_hash()!=expected_model_hash or receipt['model_hash']!=expected_model_hash:
            raise ValueError('model differs from trusted checkpoint identity')
        tokens,info,input_hash,_,_=result._prepare(receipt['as_of'],state['through_cursor'])
        if (input_hash!=expected_input_hash or receipt['input_hash']!=expected_input_hash
                or evidence_hash(tensor_identity(tokens))!=evidence_hash(tensor_identity(state['tokens']))):
            raise ValueError('input differs from trusted checkpoint or journal mapping')
        expected=asdict(ContextReceipt(**info,input_hash=input_hash,model_hash=expected_model_hash))
        if pack(receipt)!=pack(expected):
            raise ValueError('input receipt coverage differs from journal')
        result._last=dict(tokens=tokens,receipt=ContextReceipt(**expected),through_cursor=state['through_cursor'])
        return result
