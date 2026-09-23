"""Verify the existing V1 schedule after sorted-JSON transport.

C15 map packing preserves insertion order. The V1 producer hashes its schema
order before its file writer sorts JSON keys. Restore only the producer's known
field order, never values, before checking the already-published commitment.
"""
import hashlib
from .c15_journal import canonical_bytes, pack

TOP=('schema','cutoff_file_sha256','mapping_index_sha256','steps','terminal_delivery',
     'first_observed_trade_candidate','anchor_authorship','model_context_rows',
     'source_dates_required','feedback_lag')
STEP=('group_index','groups_delivered','through_cursor','records_delivered',
      'as_of','source_as_of','source_hash')
TERMINAL=('groups_delivered','records_delivered','through_cursor','as_of',
          'source_as_of','source_hash')
TRADE=('cursor','ts_event_ns','ts_recv_ns','price_raw','evidence_hash','source_prefix_hash')

def _ordered(value,keys):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValueError('schedule V1 fields differ')
    return {key:value[key] for key in keys}

def verified_schedule(value,*,expected_digest):
    from .trading_day_schedule import SCHEMA, WHOLE_DAY_SCHEMA, verify
    if isinstance(value, dict) and value.get('schema') in (SCHEMA, WHOLE_DAY_SCHEMA):
        return verify(value, expected_digest=expected_digest)
    result=_ordered(value,(*TOP,'schedule_sha256'))
    if result['schema']!='BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1':
        raise ValueError('unsupported schedule schema')
    steps=result['steps']
    if type(steps) is not list or len(steps)!=19:
        raise ValueError('nineteen original cutoffs required')
    rebuilt=[]
    for index,step in enumerate(steps):
        row=_ordered(step,(*STEP,'feedback_available_through'))
        row['feedback_available_through']=_ordered(row['feedback_available_through'],
            STEP if index<18 else TERMINAL)
        rebuilt.append(row)
    result['steps']=rebuilt
    result['terminal_delivery']=_ordered(result['terminal_delivery'],TERMINAL)
    if result['first_observed_trade_candidate'] is not None:
        result['first_observed_trade_candidate']=_ordered(result['first_observed_trade_candidate'],TRADE)
    body={key:result[key] for key in TOP}
    digest=hashlib.sha256(canonical_bytes(pack(body))).hexdigest()
    if digest!=result['schedule_sha256'] or digest!=expected_digest:
        raise ValueError('completed logical schedule identity differs')
    return result
