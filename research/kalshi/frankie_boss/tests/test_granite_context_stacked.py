import copy
import struct

import pytest

from research.kalshi.frankie_boss import granite_context_stacked as codec
from research.kalshi.frankie_boss.c15_journal import canonical_bytes, pack, evidence_hash
from research.kalshi.frankie_boss.causal_prefix import SourceScope, SourceMember, ScopeKind
from research.kalshi.frankie_boss.causal_prefix_records import RecordPrefixChain, RecordInput


def exact(value):
    return canonical_bytes(pack(value))


def native_fixture(count=3):
    scope=SourceScope(ScopeKind.PROBE_ONLY,'b'*64,
        (SourceMember(0,'synthetic.dbn','a'*64,56*count,count),),
        'NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823')
    chain=RecordPrefixChain(scope); rows=[]; packets=[]; prefixes=[]
    for cursor in range(count):
        record=dict(publisher_id=1,instrument_id=111313,ts_event=100+cursor,
            order_id=cursor+1,price=1_000_000_000+cursor,size=2,action='A',side='B',
            ts_recv=200+cursor,flags=128,channel_id=1,ts_in_delta=0,sequence=cursor,
            ts_out=None,dbn_length=14,rtype=160,dbn_extraction_hash='c'*64)
        record['dbn_wire_bytes']=codec._wire(record)
        adapter=codec._adapter(record)
        adapter.update(raw_symbol=None,source_dbn_object='synthetic.dbn',source_dbn_sha256='a'*64)
        chain.advance(RecordInput(cursor,0,adapter,scope.adapter_revision))
        prefixes.append(chain.prefix_hash)
        metadata=dict(adapter=dict(adapter,independent_clocks=True),
            source_context=dict(cursor=cursor,source_member_index=0,session_id='synthetic'),defects={})
        rows.append(dict(record=record,metadata=metadata))
        packets.append(evidence_hash(dict(schema='BOSS_NATIVE_CONTEXT_RECORD_PACKET_V1',
            source_prefix=chain.prefix_hash,record=record,metadata=metadata,as_of=500)))
    value=dict(evidence=rows,receipt=dict(scope_hash=scope.genesis_hash(),prefix_rows=count,
        source_prefix_hash=chain.prefix_hash,context_cursors=tuple(range(count)),
        packet_hashes=tuple(packets),as_of=500),other={'unchanged':(True,b'',None)})
    return value,scope,prefixes


def transformed(encoded):
    return codec._decode(encoded['data'],codec._Budget(codec.DEFAULT_LIMITS))


def test_stacked_exact_types_float_bits_order_and_shared_shapes():
    nan=struct.unpack('>d',bytes.fromhex('fff8000000000042'))[0]
    value={'ordered_second':[(2**65,-0.0,nan,b'\x00\xff','a'*64)]*3,
           'ordered_first':{'one':True,'two':1},'integer_delta':[10,11,12,13],
           'byte_columns':[b'\x00\x01',b'\x00\x02'], 'table':[{'a':2,'b':'x'},{'a':3,'b':'x'}]}
    encoded=codec.encode(value)
    assert exact(codec.decode(encoded))==exact(value)
    assert encoded==codec.encode(value)


def test_stacked_full_genesis_and_explicit_later_seed_reproduce_all_hashes():
    value,scope,prefixes=native_fixture()
    first=codec.encode(value,scope_public=scope.public_dict())
    assert transformed(first)['packet_recipe'] is not None
    assert exact(codec.decode(first))==exact(value)
    later=copy.deepcopy(value)
    later['evidence']=later['evidence'][1:]
    later['receipt']['context_cursors']=(1,2)
    later['receipt']['packet_hashes']=later['receipt']['packet_hashes'][1:]
    seed=dict(next_cursor=1,previous_prefix_hash=prefixes[0],scope_genesis_hash=scope.genesis_hash())
    encoded=codec.encode(later,scope_public=scope.public_dict(),prefix_seed=seed)
    assert transformed(encoded)['packet_recipe']['prefix_seed']==seed
    assert exact(codec.decode(encoded))==exact(later)


def test_stacked_missing_seed_gap_or_wrong_commitment_keeps_literal_hashes():
    value,scope,prefixes=native_fixture()
    cases=[]
    later=copy.deepcopy(value)
    later['evidence']=later['evidence'][1:]
    later['receipt']['context_cursors']=(1,2)
    later['receipt']['packet_hashes']=later['receipt']['packet_hashes'][1:]
    cases.append(later)
    gap=copy.deepcopy(value)
    gap['evidence']=[gap['evidence'][0],gap['evidence'][2]]
    gap['receipt']['context_cursors']=(0,2)
    gap['receipt']['packet_hashes']=(gap['receipt']['packet_hashes'][0],gap['receipt']['packet_hashes'][2])
    cases.append(gap)
    wrong=copy.deepcopy(value)
    wrong['receipt']['packet_hashes']=('d'*64,)*3
    cases.append(wrong)
    for candidate in cases:
        encoded=codec.encode(candidate,scope_public=scope.public_dict())
        assert transformed(encoded)['packet_recipe'] is None
        assert exact(codec.decode(encoded))==exact(candidate)


def test_stacked_wire_and_adapter_exceptions_remain_literal_and_exact():
    value,scope,_=native_fixture(1)
    value['evidence'][0]['record']['dbn_wire_bytes']=b'literal noncanonical wire'
    value['evidence'][0]['metadata']['adapter']['price']=-0.0
    encoded=codec.encode(value)
    recipe=transformed(encoded)['record_recipe']
    assert recipe['wire_fallbacks']=={'0':b'literal noncanonical wire'}
    assert exact(recipe['adapter_exceptions']['0']['price'])==exact(-0.0)
    assert exact(codec.decode(encoded))==exact(value)


def test_stacked_decoder_refuses_expansion_bomb_and_duplicate_map_keys():
    base=dict(schema=codec.SCHEMA,prompt_version=codec.PROMPT_VERSION,grammar_sha256=codec.grammar_hash())
    with pytest.raises(ValueError,match='expansion'):
        codec.decode(dict(base,data=['S','L',10**12,['V',0]]))
    with pytest.raises(ValueError,match='unique'):
        codec.decode(dict(base,data=['M',['x','x'],[['V',1],['V',2]]]))


def test_stacked_preserves_escaped_lone_surrogates_in_strings_and_map_keys():
    value={'\ud800key':'value\udfff', 'nested':[{'\udfff':'\ud800'}, '\ud800\udfff']}
    encoded=codec.encode(value)
    assert exact(codec.decode(encoded))==exact(value)
