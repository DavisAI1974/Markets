"""Additional causal native/second-set measurements with explicit units.

Ordered queue/message positions are state coordinates, not order identities.
Original payloads remain necessary for identity-linked scientific checks.
"""
import json
import math
import re
from fractions import Fraction

IDS={'order_id','family_id','instrument_id','publisher_id','channel_id','group_index','input_cursor',
     'sequence','sequence_first','sequence_last','priority_sequence','continuity_segment','source_member_index',
     'candidate_family_id','carried_native_family','native_family_id'}
CLOCKS={'anchor_event_ns','anchor_recv_ns','priority_recv_ns','ts_event_ns','ts_recv_ns','birth_recv_ns',
        'start_recv_ns','end_recv_ns','available_second','event_second','from_ordinal','to_ordinal','ordinal'}


def number(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def norm(path):
    return path.replace('|','_')


class Measurements:
    def __init__(self):
        self.numeric={};self.categories={};self.units={};self.source_paths={}

    def add(self,name,value,unit,path):
        assert value is None or isinstance(value,bool) or number(value),(name,value)
        name=norm(name)
        if name in self.numeric:assert self.numeric[name]==value, name
        self.numeric[name]=float(value) if value is not None else None
        self.units[name]=unit;self.source_paths[name]=path

    def category(self,name,value,path):
        if value is None:value={'source_state':'NULL'}
        assert isinstance(value,(str,bool,int,dict,list)),(name,value)
        name=norm(name);self.categories[name]=json.dumps(value,sort_keys=True,separators=(',',':'))
        self.units[name]='categorical_observation';self.source_paths[name]=path

    def counts(self,obj,prefix,source_prefix=None):
        """Count/flag blocks only. This is not an unrestricted numeric flattener."""
        source_prefix=source_prefix or prefix
        for key,value in obj.items():
            name=prefix+'.'+key;path=source_prefix+'.'+key
            if key in IDS or key in CLOCKS or key.endswith(('_hash','_sha256','_id','_sequence','_cursor','_ordinal')):continue
            if key=='state' and 'value' in obj:
                self.category(name,value,path);continue
            if key=='value' and 'state' in obj:
                self.add(name,value if obj['state'] in [0,'PRESENT'] else None,'source_defined_measurement_with_state',path);continue
            if isinstance(value,dict):self.counts(value,name,path)
            elif isinstance(value,list):continue
            elif key.endswith('_ns'):
                if any(t in key for t in ['elapsed','latency','gap','duration','delay']):self.add(name,value,'nanoseconds_duration',path)
            elif isinstance(value,bool):self.add(name,value,'boolean',path)
            elif number(value) or value is None:self.add(name,value,'source_defined_count_or_quantity',path)
            elif isinstance(value,str):self.category(name,value,path)


def native_measurements(j):
    out=Measurements()
    for side in ['bid','ask']:
        levels=j['book_full'][side+'_levels_full']
        for rank,level in enumerate(levels,1):
            queue=level['fifo_queue'];assert len(queue)==level['order_count']
            ahead=0
            for position,order in enumerate(queue,1):
                assert order['volume_ahead']==ahead
                ahead+=order['size']
                for key,unit in [('size','contracts'),('volume_ahead','contracts'),('priority_age_s','seconds_age')]:
                    out.add(f'native.book.{side}_levels.rank{rank}.fifo_position{position}.{key}',order[key],unit,
                            f'book_full.{side}_levels_full[].fifo_queue[].{key}')
            assert ahead==level['size']
    for key in ['component_count','channel_count','sequence_span','event_group_complete_f_last','fifo_priority_reconstructed',
                'native_priority_id_exposed','sequence_contiguous','single_channel_group','snapshot_bootstrap_only',
                'formation_latency_ns','f_last_to_decision_delay_ns','max_within_group_receive_gap_ns']:
        out.add('native.'+key,j.get(key),'nanoseconds_duration' if key.endswith('_ns') else 'boolean_or_count',key)
    for key in ['session_phase','side_orientation','decision_basis','interpretation_domain','source_role']:
        out.category('native.quality.'+key,j.get(key),key)
    for key in ['capture_observations','activity_since']:
        if isinstance(j.get(key),dict):out.counts(j[key],'native.'+key,key)
    for key in ['integrity','integrity_delta']:
        value=j.get(key)
        if isinstance(value,dict):out.counts(value,'native.quality.'+key,key)
        else:out.category('native.quality.'+key,value,key)
    scalar_keys=['action','side','is_last','is_snapshot','flags','size','ts_in_delta_ns']
    effect_keys=['action','side','missing_reference','new_size','old_size','priority_lost','removed','reported_size',
                 'sequence_gap_messages','size_delta','touched_or_improved_top_before']
    known=j['frankie_emission']['ts_recv_ns']
    for slot,action in enumerate(j['raw_actions'],1):
        prefix=f'native.raw_actions.slot{slot}';assert action['ts_recv_ns']<=known
        for key in scalar_keys:
            value=action.get(key);path='raw_actions[].'+key
            if key in ['action','side','flags']:out.category(prefix+'.'+key,value,path)
            else:out.add(prefix+'.'+key,value,'nanoseconds_duration' if key.endswith('_ns') else 'contracts_or_boolean',path)
        raw=action.get('price_raw');price=action.get('price')
        if number(raw) and number(price):assert abs(raw/1e9-price)<1e-10
        out.add(prefix+'.price',price if number(price) else None,'price_units','raw_actions[].price')
        out.add(prefix+'.event_receive_latency_ns',action['ts_recv_ns']-action['ts_event_ns'],'nanoseconds_duration','raw_actions[].ts_{recv,event}_ns')
        out.add(prefix+'.group_availability_delay_ns',known-action['ts_recv_ns'],'nanoseconds_duration','raw_actions[].ts_recv_ns')
        effect=action.get('book_effect',{})
        for key in effect_keys:
            value=effect.get(key);path='raw_actions[].book_effect.'+key
            if key in ['action','side']:out.category(prefix+'.book_effect.'+key,value,path)
            else:out.add(prefix+'.book_effect.'+key,value,'contracts_count_or_boolean',path)
        for key in ['price_raw','top_before_price_raw']:
            value=effect.get(key)
            out.add(prefix+'.book_effect.'+key.removesuffix('_raw'),value/1e9 if number(value) else None,'price_units','raw_actions[].book_effect.'+key)
    return out


def state_field_eligible(name):
    """Identity/future-answer/narrative buckets remain scientific provenance."""
    if re.search(r'(^|[|.])(family_id|candidate_family_id|carried_native_family|candidate_id|order_id|input_cursor|sequence|.*_hash)([|.]|$)',name):return False
    field=name.split('|')[-1]
    if field in IDS or field in CLOCKS or field.endswith(('_id','_ns','_sequence','_cursor','_ordinal')):return False
    if name.startswith(('native.lifecycle:candidate|','native.lifecycle:episode|','native.lifecycle:response|')):return False
    if any(v in name for v in ['availability_note','discovery_status','matches_carried_native_family']):return False
    return name.startswith(('native.member|','native.lifecycle:flow_substrate|','native.lifecycle:mirror|',
                            'native.lifecycle:absorption|','native.lifecycle:replenishment|','native.lifecycle:queue|','native.lifecycle:ladder|','root.structures|'))


def second_measurements(j,native):
    out=Measurements()
    # Reconcile the complete independently read book representation before
    # treating these depth triples as aliases of the native level scalars.
    depth=j['book_columns']['group']['depth']
    for label,side in [('A','ask'),('B','bid')]:
        wanted=[[z['price_raw'],z['size'],z['order_count']] for z in native['book_full'][side+'_levels_full']]
        assert depth[label]==wanted,('book_depth_alias',side)
    for name,c in j['raw_components'].items():
        out.add('second_group.'+name,c['value'] if c['state']==0 else None,'source_component_unit','raw_components.'+name+'.value')
        out.category('second_quality.'+name+'.state',['PRESENT','MISSING','INVALID','ABLATED'][c['state']],'raw_components.'+name+'.state')
        out.category('second_quality.'+name+'.reason',c.get('reason'),'raw_components.'+name+'.reason')
        for key,value in c.items():
            if key in ['value','state','reason']:continue
            if isinstance(value,dict):out.counts(value,'second_quality.'+name+'.'+key,'raw_components.'+name+'.'+key)
            else:out.add('second_quality.'+name+'.'+key,value,'source_incomplete_count','raw_components.'+name+'.'+key)
    d=j['dstate'];s=d.get('state')
    if isinstance(s,dict):
        for key in ['anchor_dir','armed','broken','n_ext','age','duration_last']:
            out.add('second_geometry.state.'+key,s.get(key),'orientation_boolean_or_groups','dstate.state.'+key)
        for key in ['E','E_prev','pull_depth','m_last','m_prev','p_last','p_prev']:
            v=s.get(key)
            rational=Fraction(v['numerator'],v['denominator']) if isinstance(v,dict) else None
            out.add('second_geometry.state.'+key+'_ticks',float(rational) if rational is not None else None,'signed_ticks' if key in ['E','E_prev'] else 'ticks','dstate.state.'+key)
        for key in ['g_E','g_E_prev']:
            v=s.get(key);age=d['group_ordinal']-v if v is not None else None
            assert age is None or age>=0
            out.add('second_geometry.state.since_'+key+'_groups',age,'groups_elapsed','dstate.state.'+key)
    out.category('second_geometry.status',d.get('status'),'dstate.status')
    columns=j['book_columns']
    out.counts(columns['group']['sides'],'second_book.group.sides','book_columns.group.sides')
    for window,value in columns.get('windows',{}).items():
        out.counts(value,'second_book.windows.'+window,'book_columns.windows.'+window)
    for key,value in j['state_labels'].items():
        if not state_field_eligible(key):continue
        values=value if isinstance(value,list) else [value]
        for index,v in enumerate(values,1):
            out.category('second_quality.observed_state.'+key+f'.position{index}',v,'state_labels.'+key)
    for window,split in j.get('state_split',{}).items():
        out.counts({k:v for k,v in split.items() if k!='fields'},'second_book.state_split.'+window,'state_split.'+window)
        for name,field in split.get('fields',{}).items():
            if state_field_eligible(name):out.counts(field,'second_book.state_split.'+window+'.fields.'+name,'state_split.'+window+'.fields.'+name)
    return out
