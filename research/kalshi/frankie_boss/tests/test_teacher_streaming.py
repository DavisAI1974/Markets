"""New bounded R3 seams against a saved pre-change varied numerical reference."""
import json
from pathlib import Path
import sys

import pytest

from research.kalshi.frankie_boss.c15_builder import C15Builder
from research.kalshi.frankie_boss.causal_prefix import SourceScope, SourceMember, ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import SUPPORTED_ADAPTER_REVISION
from research.kalshi.frankie_boss.c15_teacher_r3 import JournalTeacherR3
from research.kalshi.frankie_boss.c15_normalizer_r3 import NormalizerR3
from research.kalshi.frankie_boss.c15_normalizer import NormalizerConfig


def varied_case(tmp_path):
    scope=SourceScope(ScopeKind.RESULT_BEARING,'a'*64,(SourceMember(0,'synthetic','b'*64,100,80),),SUPPORTED_ADAPTER_REVISION)
    builder=C15Builder(scope,tmp_path/'evidence.sqlite')
    records=[dict(action='A',side='A',order_id=1,price=101,size=10),
             dict(action='A',side='B',order_id=2,price=99,size=20)]
    records += [dict(action='T',side='B',order_id=0,price=101,size=1) for _ in range(62)]
    records += [dict(action='F',side='A',order_id=1,price=101,size=2,flags=0),
                dict(action='M',side='A',order_id=1,price=101,size=8),
                dict(action='M',side='A',order_id=1,price=102,size=9),
                dict(action='C',side='A',order_id=1,price=102,size=3),
                dict(action='A',side='A',order_id=3,price=103,size=7),
                dict(action='T',side='N',order_id=0,price=103,size=1),
                dict(action='N',side='N',order_id=0,price=0,size=0)]
    for i,record in enumerate(records):
        raw=dict(instrument_id=1,publisher_id=1,channel_id=1,sequence=i,ts_event=i*100+1,
            ts_recv=i*100+2,ts_in_delta=1,flags=128,**{k:v for k,v in record.items() if k!='flags'})
        raw['flags']=record.get('flags',128)
        builder.apply(raw,source_member_index=0,session_id='s')
    evidence=list(builder.evidence_stream());builder.journal.close()
    selected=(0,62,63,64,65,66,67,68,69,70)
    context=[{k:evidence[i][k] for k in ('cursor','raw_record','normalized','source_member_index',
        'session_id','integrity','terminal_prefix_hash')} for i in selected]
    teacher=JournalTeacherR3({1:1},normalizer=NormalizerR3(NormalizerConfig((1,),n_warm=2,n_norm=8)))
    kwargs=dict(as_of=evidence[-1]['normalized']['ts_recv_ns'],source_manifest_hash=scope.genesis_hash())
    return teacher,evidence,context,kwargs


def numerical(result):
    return dict(raw=result['raw'],values=[target.values.tolist() for target in result['targets']],
        states=[target.states.tolist() for target in result['targets']],
        timestamps=[target.as_of_ts_recv_ns for target in result['targets']],
        normalizer_states=[r['normalizer']['state_hash'] for r in result['step_receipts']],
        processed_records=result['processed_records'],context_cursors=list(result['context_cursors']))


def test_streaming_matches_prechange_values_masks_and_normalizer_chronology(tmp_path):
    teacher,evidence,context,kwargs=varied_case(tmp_path)
    result=teacher.attach(iter(evidence),context,**kwargs)
    expected=json.loads(Path(__file__).with_name('teacher_streaming_reference.json').read_text())
    assert numerical(result)==expected['numerical']


def test_unused_full_row_payload_is_not_accumulated_and_control_targets_not_built(tmp_path,monkeypatch):
    teacher,evidence,context,kwargs=varied_case(tmp_path)
    sentinels=[str(i)+'x'*(256*1024) for i in range(len(evidence))]
    def stream():
        for i,row in enumerate(evidence):
            observation=(dict(row['observation'],unused_depth_payload=sentinels[i])
                if row['observation'] is not None else None)
            yield dict(row,unused_full_row_payload=sentinels[i],observation=observation)
            if i>=6:
                retained=sum(sys.getrefcount(marker)>3 for marker in sentinels)
                assert retained<=4, 'full prefix evidence accumulated instead of streamed'
    monkeypatch.setattr(teacher.control,'_target',lambda *a,**k:pytest.fail('unused full-prefix control target built'))
    result=teacher.attach(stream(),context,**kwargs)
    assert result['processed_records']==len(evidence)
    assert len(result['targets'])==len(context)


def test_unselected_future_suffix_is_still_consumed_and_rejected(tmp_path):
    teacher,evidence,context,kwargs=varied_case(tmp_path)
    context=context[:1]
    kwargs['as_of']=evidence[-2]['normalized']['ts_recv_ns']
    with pytest.raises(ValueError,match='future'):
        teacher.attach(iter(evidence),context,**kwargs)


def test_history_view_keeps_every_fifo_member_in_both_three_level_cohorts(tmp_path):
    from research.kalshi.frankie_boss.c15_teacher_r3 import _history_row,_cohort
    teacher,evidence,context,kwargs=varied_case(tmp_path)
    start=dict(evidence[63])
    observation=dict(start['observation'])
    orders=list(observation['orders'])
    levels={side:list(observation['levels'][side]) for side in ('A','B')}
    for side in ('A','B'):
        for rank in range(1,4):
            ids=[]
            for offset in range(7):
                oid=100+(100 if side=='B' else 0)+rank*10+offset
                order=dict(orders[0],order_id=oid,side=side,size=rank+offset+1)
                orders.append(order);ids.append(oid)
            levels[side].append(dict(levels[side][0],order_ids=ids,price_raw=200+rank))
    start['observation']=dict(observation,orders=orders,levels=levels)
    view=_history_row(start)
    for side in ('A','B'):
        expected={oid for level in levels[side][:3] for oid in level['order_ids']}
        assert expected.issubset({o['order_id'] for o in view['observation']['orders']})
        groups=[[evidence[65]],[evidence[66]]]
        assert _cohort(start,groups,side)==_cohort(view,[[_history_row(e)] for g in groups for e in g],side)


def test_missing_rank_remains_explicit_invalid_under_history_view(tmp_path):
    from research.kalshi.frankie_boss.c15_teacher_r3 import RawJournalTeacherR3
    teacher,evidence,context,kwargs=varied_case(tmp_path)
    evidence=evidence[:68]
    evidence[65]=dict(evidence[65])
    del evidence[65]['rank_before']
    result=RawJournalTeacherR3().attach(iter(evidence),context_cursors=(67,),
        expected_prefix_hash=evidence[-1]['terminal_prefix_hash'],**kwargs)
    assert result['rows'][0]['columns'][0]['reason']=='RANK_UNAVAILABLE'
    assert result['rows'][0]['columns'][0]['mask']==0
