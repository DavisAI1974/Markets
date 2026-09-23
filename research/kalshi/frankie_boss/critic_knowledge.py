"""Causally eligible prior interpretations, separate from native market evidence."""
import hashlib
import json
from .c15_journal import evidence_hash

SCHEMA = 'FRANKIE_CRITIC_KNOWLEDGE_V1'
RECORD_FIELDS = {'request_id', 'available_ns', 'feedback_hash', 'principal_receipt_hash',
    'training_checkpoint_hash', 'lessons', 'frozen_memory_sha256'}
HASH_FIELDS = RECORD_FIELDS - {'request_id', 'available_ns', 'lessons'}

def _json(value):
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError('knowledge must contain canonical JSON values') from exc

def _id(value):
    if type(value) is not str or not value.strip():
        raise ValueError('explicit knowledge request identity required')

def _ns(value):
    if type(value) is not int or value < 0:
        raise ValueError('nonnegative integer knowledge availability required')

def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('knowledge provenance SHA256 required')

def _record(record):
    if type(record) is not dict or not RECORD_FIELDS <= set(record) or set(record)-RECORD_FIELDS-{'critic_exchange'}:
        raise ValueError('invalid knowledge record fields')
    _id(record['request_id']); _ns(record['available_ns'])
    for key in HASH_FIELDS: _hash(record[key])
    if type(record['lessons']) is not list:
        raise ValueError('explicit complete lesson list required')
    if 'critic_exchange' in record:
        value=record['critic_exchange']
        fields={'schema','status','verdict','request_hash','snapshot_hash','response_text','response_hash','available_ns'}
        if type(value) is not dict or set(value)!=fields or value['schema']!='FRANKIE_CRITIC_EXCHANGE_V1':
            raise ValueError('invalid retained critic exchange')
        _ns(value['available_ns'])
        if value['available_ns']!=record['available_ns']:
            raise ValueError('critic exchange differs from verified feedback availability')
        for key in ('request_hash','snapshot_hash'): _hash(value[key])
        if value['status'] not in ('accepted','rejected','timeout','transport_error','malformed_response','binding_mismatch'):
            raise ValueError('invalid retained critic status')
        text=value['response_text']
        if text is None:
            if value['response_hash'] is not None: raise ValueError('missing critic response has hash')
        elif type(text) is not str or hashlib.sha256(text.encode()).hexdigest()!=value['response_hash']:
            raise ValueError('retained critic response changed')

def build_knowledge(records, *, cutoff_ns, request_id):
    _ns(cutoff_ns); _id(request_id)
    if type(records) not in (list, tuple): raise ValueError('explicit knowledge record list required')
    owned=_json(records); seen=set(); entries=[]
    for record in owned:
        _record(record)
        key=record['request_id']
        if key==request_id or key in seen:
            raise ValueError('duplicate or current request in prior knowledge')
        seen.add(key)
        if record['available_ns']<=cutoff_ns:
            entries.append(dict(lesson_hash=evidence_hash(record),record=record))
    entries.sort(key=lambda entry:(entry['record']['available_ns'],entry['record']['request_id']))
    return _json(dict(schema=SCHEMA,request_id=request_id,cutoff_ns=cutoff_ns,entries=entries))

def validate_knowledge(value, *, cutoff_ns=None, request_id=None):
    if type(value) is not dict or not {'schema','request_id','cutoff_ns','entries'} <= set(value) or set(value)-{'schema','request_id','cutoff_ns','entries','origins','priming'} or value['schema']!=SCHEMA:
        raise ValueError('invalid critic knowledge envelope')
    if type(value['entries']) is not list: raise ValueError('knowledge entries must be ordered list')
    if cutoff_ns is not None and value['cutoff_ns']!=cutoff_ns: raise ValueError('knowledge cutoff differs')
    if request_id is not None and value['request_id']!=request_id: raise ValueError('knowledge request differs')
    records=[]
    for entry in value['entries']:
        if type(entry) is not dict or set(entry)!={'lesson_hash','record'}:
            raise ValueError('invalid knowledge entry')
        _hash(entry['lesson_hash'])
        if entry['lesson_hash']!=evidence_hash(entry['record']): raise ValueError('knowledge record hash changed')
        records.append(entry['record'])
    expected=build_knowledge(records,cutoff_ns=value['cutoff_ns'],request_id=value['request_id'])
    if 'origins' in value:
        origins=value['origins']
        if type(origins) is not list or len(origins)!=len(expected['entries']):
            raise ValueError('complete knowledge origin roster required')
        for origin, entry in zip(origins, expected['entries']):
            fields={'request_id','binding_hash','feedback_stage_hash','training_hash','completion_hash',
                'source_hash','input_hash','through_cursor','as_of'}
            if type(origin) is not dict or set(origin)!=fields or origin['request_id']!=entry['record']['request_id']:
                raise ValueError('knowledge origin identity differs')
            for name in fields-{'request_id','through_cursor','as_of'}: _hash(origin[name])
            _ns(origin['as_of']); _ns(origin['through_cursor'])
            if origin['as_of']>entry['record']['available_ns']: raise ValueError('origin chronology differs')
        expected['origins']=_json(origins)
    if 'priming' in value:
        from .granite_positive_priming import validate_priming
        expected['priming']=validate_priming(value['priming'])
    if value!=expected: raise ValueError('knowledge order, availability or canonical content differs')
    return _json(expected)

def acknowledged(value, knowledge):
    """Receipt acknowledgment is observable output, not a claim about cognition."""
    if value.get('knowledge_hash')!=evidence_hash(knowledge): return False
    from .granite_positive_priming import public_knowledge
    visible=public_knowledge(knowledge)
    review=value.get('knowledge_review')
    if type(review) is not list or len(review)!=len(visible['entries']): return False
    expected=[entry['lesson_hash'] for entry in visible['entries']]
    actual=[]
    for item in review:
        if (type(item) is not dict or set(item)!={'lesson_hash','assessment'}
                or type(item['assessment']) is not str or not item['assessment'].strip()): return False
        try: _hash(item['lesson_hash'])
        except ValueError: return False
        actual.append(item['lesson_hash'])
    return len(set(actual))==len(actual) and set(actual)==set(expected)

def critic_exchange(result, *, available_ns):
    """Controller result was independently checked before principal feedback exists."""
    from .granite_shadow import GraniteIdentity, ShadowRequest
    _ns(available_ns)
    shadow=result['critic']['receipt']['shadow']
    raw=shadow['request']
    request=ShadowRequest(**{**raw,'identity':GraniteIdentity(**raw['identity'])})
    response=shadow['response']
    if shadow['status']=='binding_mismatch':
        response=None  # Foreign bytes remain in the original receipt, never in reusable knowledge.
    if response is not None and (response['request_hash']!=request.request_hash
            or response['identity_hash']!=request.identity.identity_hash):
        raise ValueError('critic exchange response binding differs')
    text=None if response is None else response['text']
    return dict(schema='FRANKIE_CRITIC_EXCHANGE_V1',status=shadow['status'],verdict=shadow['verdict'],
        request_hash=request.request_hash,snapshot_hash=request.snapshot_hash,
        response_text=text,response_hash=None if text is None else hashlib.sha256(text.encode()).hexdigest(),
        available_ns=available_ns)


def verify_prepared_knowledge(body, expected):
    """Read the actual admitted body, not an uncorroborated sidecar claim."""
    from .granite_context_route import context_route
    try:
        payload=json.loads(body)
        messages=payload['messages']
        if len(messages)!=1 or messages[0]['role']!='user':
            raise ValueError('one exact critic prompt required')
        prompt=messages[0]['content']
        _, separator, text=prompt.partition('\nstacked_native_context:\n')
        if not separator: raise ValueError('stacked critic body required')
        route=context_route('stacked_v1')
        from .granite_context import _text
        from .granite_positive_priming import public_knowledge
        visible=json.loads(text)
        if visible.pop('knowledge_view',None)!=public_knowledge(expected):
            raise ValueError('prepared body differs from helpful knowledge projection')
        visible['knowledge']=expected
        audit_text=_text(visible)
        snapshot=route.parse(audit_text,expected_hash=hashlib.sha256(audit_text.encode()).hexdigest())
        if route.build_prompt(snapshot).text!=prompt:
            raise ValueError('prepared body differs from frozen critic knowledge')
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid prepared critic knowledge body') from exc
