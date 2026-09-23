"""Positive model-visible priming with independently retained, truthful provenance."""
import hashlib
import json
from pathlib import Path
from .c15_journal import evidence_hash

MODE='knowledge_primed_learning_replay'
SCHEMA='FRANKIE_HISTORICAL_PRIMING_V2'
HELPFUL='FRANKIE_HELPFUL_KNOWLEDGE_V1'
RETAINED='research/kalshi/frankie_boss/records/chat6_scratchpad_20260921'
PINS={
    'response-00.json':'b65123b3113846bdba9c232da0542c471b61893061728bbceb0fc604993f0e21',
    'host-session-record.json':'e170e3635bf7ac43d87be857ab4f466610fa01339dbc5490cc5b1d317441146a',
    'cycle-00-docs/brain/cycle-00/derive.md':'864ba0b039d57294f0531db25133fa584cb1093d3fe523bb8029b85eb9e059b3'}
METHODS={
    'legacy_price':('research/ng_exhaustion_mbo_v4_state_adapter_20260820.py (legacy control row projection)',
        'Reconstruct price observations through the native legacy control row projection.'),
    'legacy_native_signed_flow':('research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py SecondBinner (clock ts_recv)',
        'Aggregate native signed flow on the receive-time clock.'),
    'legacy_per_second_roll20':('research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py roll20 (window 20, clock ts_recv)',
        'Calculate rolling signed flow over 20-second receive-time windows.'),
    'legacy_book_imbalance':('V4MboAdapter F_LAST book snapshot + a_memory_member_first_recalculation_20260828.book_values/book_transition',
        'Use completed F_LAST book snapshots to derive book imbalance and book transitions.'),
    'legacy_structure_observables':('a_memory_member_first_recalculation_20260828.describe_structure per F_LAST group (action string, side string, mirror, fill disposition, family candidate)',
        'Build structure observables from completed event groups while preserving action, side, mirror and fill disposition.')}

def canonical(value):
    return json.loads(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))

def _hash(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def _helpful(value):
    if (type(value) is not dict or set(value)!={'schema','statement','evidence_hashes'} or
            value['schema']!=HELPFUL or type(value['statement']) is not str or not value['statement'].strip() or
            type(value['evidence_hashes']) is not list or not value['evidence_hashes'] or
            any(not _hash(h) for h in value['evidence_hashes'])):
        raise ValueError('explicit supported helpful statement and evidence hashes required')
    return canonical(value)

def select_helpful(lessons):
    """Closed structured evidence; never infer positivity from a word in prose."""
    selected=[]
    for item in lessons:
        if type(item) is not dict: continue
        if item.get('schema')==HELPFUL:
            _helpful(item)  # Preserve validation; self-labeled prose is audit-only.
            continue
        elif item.get('ledger')=='calculation_accounting':
            harness=item.get('harness_derivation',{})
            layers=item.get('layers',[])
            if type(harness) is not dict or type(layers) is not list: continue
            accounted={v.get('layer'):v for v in layers if type(v) is dict}
            for name,(producer,statement) in METHODS.items():
                proof=harness.get(name);entry=accounted.get(name)
                if (type(proof) is dict and type(entry) is dict and
                        proof.get('status')=='derived' and entry.get('status')=='derived' and
                        proof.get('producer')==producer and _hash(proof.get('sha256')) and
                        type(entry.get('where')) is str and proof['sha256'][:16] in entry['where']):
                    selected.append(_helpful(dict(schema=HELPFUL,statement=statement,evidence_hashes=[proof['sha256']])))
    # Identical supported statements may be mentioned more than once in an audit.
    unique={}
    for item in selected: unique.setdefault(evidence_hash(item),item)
    return list(unique.values())

def validate_priming(value):
    fields={'schema','mode','source_available_ns','source_request_id','response_sha256',
        'response_canonical_sha256','derivation_sha256','host_record_sha256','lessons','market_context'}
    if type(value) is not dict or set(value)!=fields or value['schema']!=SCHEMA or value['mode']!=MODE:
        raise ValueError('explicit historical learning replay priming mode required')
    if type(value['source_available_ns']) is not int or value['source_available_ns']<0:
        raise ValueError('true source knowledge availability required')
    if type(value['source_request_id']) is not str or not value['source_request_id'].strip():
        raise ValueError('true source request required')
    for name in ('response_sha256','response_canonical_sha256','derivation_sha256','host_record_sha256'):
        if not _hash(value[name]): raise ValueError('priming source hash required')
    if type(value['lessons']) is not list or not value['lessons']: raise ValueError('supported priming lessons required')
    for item in value['lessons']:
        _helpful(item)
        if item['statement'] not in {v[1] for v in METHODS.values()}:
            raise ValueError('unapproved historical calculation statement')
    from .knowledge_calendar import market_calendar
    context=value['market_context']
    if type(context) is not dict or context!=market_calendar(context.get('observed_ns')):
        raise ValueError('historical source market calendar differs')
    if context['observed_ns']>value['source_available_ns']:
        raise ValueError('source observation after knowledge availability')
    return canonical(value)

def public_knowledge(audit):
    """Only this projection enters model-visible text; the source audit remains intact."""
    from .knowledge_calendar import market_calendar
    from .critic_knowledge import CUMULATIVE
    cumulative=audit.get('learning_policy')==CUMULATIVE
    entries=[]
    origins={row['request_id']:row for row in audit.get('origins',[])}
    for entry in audit['entries']:
        if cumulative:
            origin=origins.get(entry['record']['request_id'])
            context=(dict(status='unverified',reason='source_market_time_not_bound')
                if origin is None else market_calendar(origin['as_of']))
            entries.append(dict(lesson_hash=entry['lesson_hash'], learned_record=entry['record'], market_context=context))
            continue
        items=select_helpful(entry['record']['lessons'])
        if items:
            origin=origins.get(entry['record']['request_id'])
            context=(dict(status='unverified',reason='source_market_time_not_bound')
                if origin is None else market_calendar(origin['as_of']))
            entries.append(dict(lesson_hash=entry['lesson_hash'],helpful_lessons=items,market_context=context))
    capsule=audit.get('priming')
    if capsule is not None:
        capsule=validate_priming(capsule)
        entries.append(dict(lesson_hash=evidence_hash(capsule),helpful_lessons=capsule['lessons'],market_context=capsule['market_context']))
    if cumulative:
        return canonical(dict(schema='FRANKIE_CUMULATIVE_MODEL_VIEW_V1', knowledge_mode=MODE,
            learning_policy=audit['learning_policy'], entries=entries))
    return canonical(dict(schema='FRANKIE_HELPFUL_MODEL_VIEW_V1',entries=entries))

def load_retained_priming(repository, *, mode):
    """Read only pinned Git artifacts. This does not claim a completed training cycle."""
    if mode!=MODE: raise ValueError('historical priming needs explicit learning replay mode')
    root=Path(repository)/RETAINED
    bodies={}
    for name,digest in PINS.items():
        path=root/name
        if path.is_symlink() or not path.is_file(): raise ValueError('retained priming source must be regular file')
        body=path.read_bytes()
        if hashlib.sha256(body).hexdigest()!=digest: raise ValueError('retained priming source hash changed')
        bodies[name]=body
    response=json.loads(bodies['response-00.json'])
    record=json.loads(bodies['host-session-record.json'])
    canonical_response=json.dumps(response,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
    response_hash=hashlib.sha256(canonical_response).hexdigest()
    if (response_hash!=record['response_sha256'] or record['response']['sha256']!=PINS['response-00.json']
            or record['response']['bytes']!=len(bodies['response-00.json'])
            or record['request_sha256']!=response['request_sha256']
            or record['session_id']!=response['session_id'] or not record.get('host_authority')):
        raise ValueError('retained principal response attestation differs')
    raw=bodies['cycle-00-docs/brain/cycle-00/derive.md'].decode()
    derivation=json.loads(raw.split('```json\n',1)[1].split('\n```',1)[0])
    if derivation['schema']!='FRANKIE_BOX_DERIVATION_RECEIPT_V1' or derivation['failure_count']!=0:
        raise ValueError('verified successful derivation required')
    lessons=select_helpful(response['lessons'])
    for item in lessons:
        for sha in item['evidence_hashes']:
            if not any(v.get('status')=='derived' and v.get('sha256')==sha and
                    v.get('producer')==METHODS[name][0] for name,v in derivation['layers'].items() if name in METHODS):
                raise ValueError('positive lesson lacks matching successful derivation receipt')
    from .knowledge_calendar import market_calendar
    observed=[row['observed_through_ns'] for session in response['feedback']['sessions'] for row in session['timing']]
    if not observed or any(type(ns) is not int for ns in observed):
        raise ValueError('retained source market timestamps required')
    return validate_priming(dict(schema=SCHEMA,mode=mode,market_context=market_calendar(min(observed)),
        source_available_ns=response['feedback']['available_ns'],source_request_id=response['feedback']['request_id'],
        response_sha256=PINS['response-00.json'],response_canonical_sha256=response_hash,
        derivation_sha256=PINS['cycle-00-docs/brain/cycle-00/derive.md'],
        host_record_sha256=PINS['host-session-record.json'],lessons=lessons))
