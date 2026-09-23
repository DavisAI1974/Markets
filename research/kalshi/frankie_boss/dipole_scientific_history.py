"""Lossless history view of scientific delivery, with repeated source bytes referenced.

All model responses, assessments, disagreements and scientific turns stay verbatim.
Only source bodies inside delivery prompts become exact reconstruction recipes.
Original attested response artifacts remain immutable and independently auditable.
"""
import copy
from . import dipole_scientific_review as S
from . import dipole_teacher_discussion as D
from .c15_journal import evidence_hash
from deploy.aws.box.frankie_box_staged_reading import validate_receipt, witness

SCHEMA='DIPOLE_SCIENTIFIC_LEARNING_VIEW_V1'


def _prior_history(history):
    if type(history) is not dict or history.get('schema')!='FRANKIE_CLASSROOM_LEARNING_HISTORY_V1':
        return dict(kind='INLINE',value=history)
    exchanges=history.get('exchanges')
    if type(exchanges) is not list:
        raise ValueError('complete prior exchange list required')
    for entry in exchanges:
        if type(entry) is not dict or entry.get('exchange_hash')!=evidence_hash(
                {k:v for k,v in entry.items() if k!='exchange_hash'}):
            raise ValueError('prior exchange witness changed')
    if history.get('history_hash')!=evidence_hash({k:v for k,v in history.items() if k!='history_hash'}):
        raise ValueError('prior history witness changed')
    return dict(kind='EXCHANGE_REFERENCES',key_order=list(history),header={k:v for k,v in history.items() if k!='exchanges'},
        exchange_hashes=[x['exchange_hash'] for x in exchanges])


def _restore_prior(description,prior_exchanges):
    if description.get('kind')=='INLINE':
        if set(description)!={'kind','value'}:raise ValueError('inline prior history fields differ')
        return description['value']
    if description.get('kind')!='EXCHANGE_REFERENCES' or set(description)!={'kind','key_order','header','exchange_hashes'}:
        raise ValueError('prior history reconstruction descriptor required')
    indexed={}
    for entry in prior_exchanges:
        key=entry.get('exchange_hash')
        if key!=evidence_hash({k:v for k,v in entry.items() if k!='exchange_hash'}) or key in indexed:
            raise ValueError('previous exchange changed or duplicated')
        indexed[key]=entry
    wanted=description['exchange_hashes']
    if type(wanted) is not list or len(set(wanted))!=len(wanted) or any(key not in indexed for key in wanted):
        raise ValueError('every referenced prior exchange is required')
    fields=dict(description['header'],exchanges=[indexed[key] for key in wanted])
    order=description['key_order']
    if type(order) is not list or len(order)!=len(fields) or set(order)!=set(fields):
        raise ValueError('original prior history field order required')
    value={key:fields[key] for key in order}
    if value.get('history_hash')!=evidence_hash({k:v for k,v in value.items() if k!='history_hash'}):
        raise ValueError('reconstructed prior history differs')
    return value


def _reading_view(receipt):
    validate_receipt(receipt)
    body=copy.deepcopy(receipt)
    for part in body['parts']:
        original=part['prompt'].pop('content').encode('utf-8')
        offset=part['source_offset']
        size=part['end']-part['start']
        # UTF-8 boundaries and exact range hashes were verified by validate_receipt.
        part['prompt']['source_fragment']=dict(
            source_id=part['source_id'],start=part['start'],end=part['end'],
            source_sha256=part['source_sha256'],chunk_sha256=part['chunk_sha256'],
            prefix=original[:offset].decode('utf-8'),suffix=original[offset+size:].decode('utf-8'))
    return body


def _restore_reading(view,sources):
    body=copy.deepcopy(view)
    for part in body['parts']:
        prompt=part['prompt']
        fragment=prompt.pop('source_fragment',None)
        fields={'source_id','start','end','source_sha256','chunk_sha256','prefix','suffix'}
        if type(fragment) is not dict or set(fragment)!=fields:
            raise ValueError('exact delivery source fragment required')
        for key in ('source_id','start','end','source_sha256','chunk_sha256'):
            if fragment[key]!=part[key]:raise ValueError('delivery source fragment differs from its receipt')
        source=sources(fragment['source_id'])
        if type(source) is not bytes or witness(source)['sha256']!=fragment['source_sha256']:
            raise ValueError('full delivery source differs')
        chunk=source[fragment['start']:fragment['end']]
        if witness(chunk)['sha256']!=fragment['chunk_sha256']:
            raise ValueError('reconstructed delivery chunk differs')
        raw=fragment['prefix'].encode('utf-8')+chunk+fragment['suffix'].encode('utf-8')
        if witness(raw)!={k:prompt[k] for k in ('sha256','bytes')}:
            raise ValueError('reconstructed delivery prompt differs')
        prompt['content']=raw.decode('utf-8')
    return validate_receipt(body)


def project(request,value):
    """Produce a plaintext learning view, not a substitute attestation artifact."""
    D.validate(request,value)
    body=copy.deepcopy(value)
    body['reading']=_reading_view(value['reading'])
    body['teacher_discussion']['reading']=_reading_view(value['teacher_discussion']['reading'])
    view=dict(schema=SCHEMA,scientific_request_hash=request['scientific_request_hash'],
        original_exchange_hash=value['exchange_hash'],prior_history=_prior_history(request['learning_history']),
        exchange_without_repeated_sources=body,
        meaning=('All model responses, assessments and scientific discussions are verbatim. Repeated delivery '
            'source bodies use source_fragment references to the full shared catalog, this cycle original response '
            'and fact review, earlier exchanges, or this cycle classroom exchange. Prefix, suffix, exact ranges '
            'and all original hashes reconstruct the complete delivery. This learning view is not a raw attestation.'))
    view['projection_hash']=S.digest(view)
    return view


def restore(view,*,request_fields,initial_response,prior_exchanges,resolve_source):
    """Reconstruct and validate the original attested scientific exchange exactly.

    request_fields is the retained scientific request without repeated initial
    response/history. prior_exchanges supplies earlier learning entries once in
    their ordinary complete learning-view form; it does not recursively expand
    their own raw delivery receipts. resolve_source returns pinned research bytes.
    """
    if (type(view) is not dict or view.get('schema')!=SCHEMA
            or view.get('projection_hash')!=S.digest({k:v for k,v in view.items() if k!='projection_hash'})):
        raise ValueError('scientific learning view binding differs')
    history=_restore_prior(view['prior_history'],prior_exchanges)
    fields=dict(request_fields)
    initial_hash=fields.pop('initial_response_hash',None)
    previous_hash=fields.pop('earlier_learning_history_hash',None)
    if initial_hash is not None and initial_hash!=evidence_hash(initial_response):
        raise ValueError('original scientific response differs')
    if previous_hash is not None and (history is None or history.get('history_hash')!=previous_hash):
        raise ValueError('original scientific prior history differs')
    request=dict(fields,initial_response=initial_response,learning_history=history)
    S.validate_request(request)
    if request['scientific_request_hash']!=view['scientific_request_hash']:
        raise ValueError('scientific learning view belongs to another request')
    sources={'initial-response':S.canonical(initial_response),'fact-review':S.canonical(request['fact_review']),
        'learning-history':S.canonical(history)}
    allowed={x['source_id'] for x in request['shared_knowledge']['sources']}
    def source(name):
        if name in sources:return sources[name]
        if name not in allowed:raise ValueError('unknown scientific learning source')
        raw=resolve_source(name)
        if type(raw) is not bytes:raise ValueError('exact research bytes required')
        sources[name]=raw
        return raw
    body=copy.deepcopy(view['exchange_without_repeated_sources'])
    body['reading']=_restore_reading(body['reading'],source)
    sources['classroom-exchange']=S.canonical(D.base_exchange(body))
    body['teacher_discussion']['reading']=_restore_reading(body['teacher_discussion']['reading'],source)
    if body['exchange_hash']!=view['original_exchange_hash']:
        raise ValueError('original scientific exchange identity differs')
    return D.validate(request,body)
