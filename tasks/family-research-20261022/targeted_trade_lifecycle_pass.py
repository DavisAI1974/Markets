"""Bounded local trade-first postprocessing of frozen run artifacts; no fits/network.

Raw lifecycle evidence is read from one exact member of the existing local archive
into an in-memory, read-only SQLite connection. No database copy is saved on C:.
Every trade is retained. Stored/reconstructed dipole paths remain supporting data.
"""
import collections
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tarfile
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

START = time.monotonic()
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'artifacts/sqlite-triage/20261022/families'
OUT = BASE/'trade-lifecycle-targeted-v1'
OUT.mkdir(exist_ok=True)
ARCHIVE = ROOT/'artifacts/recovered-c-drive/20261022/family-continuation-archives/full-context-continuation-v1.tar.gz'
MEMBER = 'episode-path-audit-v1/lifecycle_asof.sqlite'


def check_time():
    if time.monotonic()-START > 1800:
        raise RuntimeError('30-minute local pass limit reached; saved checkpoints retained')


def dump(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def save_rows(name, rows):
    # DictWriter preserves nullable clocks as integer-or-blank, never float.
    keys = list(dict.fromkeys(k for r in rows for k in r))
    opener = gzip.open if name.endswith('.gz') else open
    with opener(OUT/name, 'wt', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def source_rows(path):
    opener = gzip.open if path.suffix=='.gz' else open
    with opener(path, 'rt', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


scope=json.loads((BASE/'completed-run-source-list.json').read_text())
trades=source_rows(BASE/'price-curve-timestamps.csv')
assert len(trades)==30739
clock_fields=['source_ordinal','trade_input_cursor','trade_journal_ordinal','group_close_input_cursor',
              'instrument_id','event_ns','receive_ns','available_ns','price_raw','size']
for r in trades:
    for k in clock_fields: r[k]=int(r[k])
    assert r['issues_json']=='[]'
    assert r['receive_ns']<=r['available_ns']
assert [r['source_ordinal'] for r in trades]==list(range(30739))
assert len({r['trade_input_cursor'] for r in trades})==len(trades)
assert {r['instrument_id'] for r in trades}=={150611}
available=np.array([r['available_ns'] for r in trades],dtype=np.int64)
receive=np.array([r['receive_ns'] for r in trades],dtype=np.int64)
prices=np.array([r['price_raw'] for r in trades],dtype=np.int64)
sizes=np.array([r['size'] for r in trades],dtype=np.int64)
assert np.all(np.diff(available)>=0) and np.all(np.diff(receive)>=0)
n=len(trades)
volume=np.r_[np.int64(0),np.cumsum(sizes)]
path_length=np.r_[np.int64(0),np.cumsum(np.abs(np.diff(prices)))]

# Sparse-table range queries: all trades x all horizons, with no trade filtering.
mins=[prices]; maxs=[prices]
for k in range(1,n.bit_length()):
    half=1<<(k-1);width=1<<k
    if width>n: break
    mins.append(np.minimum(mins[-1][:-half],mins[-1][half:]))
    maxs.append(np.maximum(maxs[-1][:-half],maxs[-1][half:]))


def ranges(left,right):
    lengths=right-left+1
    ks=np.floor(np.log2(lengths)).astype(int)
    low=np.empty(len(left),dtype=np.int64);high=low.copy()
    for k in np.unique(ks):
        take=ks==k;start=left[take];end=right[take]-(1<<int(k))+1
        low[take]=np.minimum(mins[k][start],mins[k][end])
        high[take]=np.maximum(maxs[k][start],maxs[k][end])
    return low,high


burst_map=collections.defaultdict(list)
for i,r in enumerate(trades): burst_map[r['group_close_input_cursor']].append(i)
bursts=[]
for cursor,inds in burst_map.items():
    lo,hi=inds[0],inds[-1]
    assert inds==list(range(lo,hi+1))
    bursts.append(dict(group_close_input_cursor=cursor,first_trade_ordinal=lo,last_trade_ordinal=hi,
        available_ns=int(available[hi]),first_event_ns=trades[lo]['event_ns'],last_event_ns=trades[hi]['event_ns'],
        first_receive_ns=int(receive[lo]),last_receive_ns=int(receive[hi]),trade_count=len(inds),
        size=int(volume[hi+1]-volume[lo]),first_price_raw=int(prices[lo]),last_price_raw=int(prices[hi]),
        min_price_raw=int(prices[lo:hi+1].min()),max_price_raw=int(prices[lo:hi+1].max()),
        within_group_price_change_raw=int(prices[hi]-prices[lo]),
        interpretation='recorded trade prints grouped by original emission cursor; not an inferred strategy position'))
save_rows('all-native-trade-bursts.csv.gz',bursts)

for i,r in enumerate(trades):
    r.update(previous_trade_price_change_raw='' if i==0 else int(prices[i]-prices[i-1]),
        previous_trade_gap_receive_ns='' if i==0 else int(receive[i]-receive[i-1]),
        receive_to_group_availability_ns=int(available[i]-receive[i]),
        strict_pre_receive_cutoff_ns=int(receive[i])-1,strict_pre_input_cursor_cap=r['trade_input_cursor']-1,
        burst_print_count=len(burst_map[r['group_close_input_cursor']]),
        price_step_is_aggressor_direction=False)
    for seconds in [1,5,20,60,120]:
        lo=int(np.searchsorted(available,receive[i]-seconds*1_000_000_000,side='left'))
        hi=int(np.searchsorted(available,receive[i],side='left'))
        hi=min(hi,i);lo=min(lo,hi)
        r[f'prior{seconds}s_observable_prints']=hi-lo
        r[f'prior{seconds}s_observable_size']=int(volume[hi]-volume[lo])
        if hi>lo:
            r[f'prior{seconds}s_trade_change_raw']=int(prices[hi-1]-prices[lo])
            r[f'prior{seconds}s_last_trade_age_ns']=int(receive[i]-available[hi-1])
        else:
            r[f'prior{seconds}s_trade_change_raw']='';r[f'prior{seconds}s_last_trade_age_ns']=''

horizon_rows=[]
for seconds in [1,5,20,60,120,300,600]:
    check_time()
    ends=available+seconds*1_000_000_000
    right=np.searchsorted(available,ends,side='right')-1
    left=np.arange(n)
    low,high=ranges(left,right)
    for i in range(n):
        j=int(right[i]);censored=bool(ends[i]>available[-1]);span=int(path_length[j]-path_length[i])
        horizon_rows.append(dict(trade_ordinal=i,horizon_s=seconds,
            baseline_available_ns=int(available[i]),baseline_trade_input_cursor=trades[i]['trade_input_cursor'],
            horizon_cutoff_ns=int(ends[i]),endpoint_trade_ordinal=j,endpoint_available_ns=int(available[j]),
            endpoint_group_close_input_cursor=trades[j]['group_close_input_cursor'],
            endpoint_age_ns=int(ends[i]-available[j]),retained_session_edge_censored=censored,
            observed_later_prints=j-i,observed_size=int(volume[j+1]-volume[i+1]),
            endpoint_change_raw='' if censored else int(prices[j]-prices[i]),
            up_excursion_raw='' if censored else int(high[i]-prices[i]),
            down_excursion_raw='' if censored else int(prices[i]-low[i]),
            absolute_path_raw='' if censored else span,
            path_efficiency='' if censored or span==0 else abs(int(prices[j]-prices[i]))/span,
            disposition='edge_censored' if censored else 'no_later_print_not_a_flat_market_claim' if j==i else 'observed_transaction_path_not_a_strategy_return'))
save_rows('every-trade-observed-lifecycle-windows.csv.gz',horizon_rows)
print('All 30739 trade prints and 215173 horizon records retained',flush=True)

# Exact source group references for each trade's current emission and last pre-trade group.
groups=pd.read_csv(BASE/'descriptive-v1/retained_group_sequence.csv.gz',
    dtype={k:'int64' for k in ['source_ordinal','input_cursor','event_ns','recv_ns','known_by_ns','source_offset','instrument_id']})
assert groups.known_by_ns.is_monotonic_increasing and groups.input_cursor.is_monotonic_increasing
gtime=groups.known_by_ns.to_numpy();gcursor=groups.input_cursor.to_numpy()
grows=groups.to_dict('records');gmap={r['input_cursor']:r for r in grows}
for r in trades:
    g=gmap[r['group_close_input_cursor']]
    assert g['known_by_ns']==r['available_ns']
    r['emission_group_source_ordinal']=g['source_ordinal'];r['emission_group_structural_family_annotation']=g['family_id']
    a=int(np.searchsorted(gtime,r['receive_ns'],side='left'))-1
    b=int(np.searchsorted(gcursor,r['trade_input_cursor'],side='left'))-1
    ix=min(a,b)
    if ix>=0:
        p=grows[ix];assert p['known_by_ns']<r['receive_ns'] and p['input_cursor']<r['trade_input_cursor']
        r.update(pre_group_source_ordinal=p['source_ordinal'],pre_group_input_cursor=p['input_cursor'],
            pre_group_event_ns=p['event_ns'],pre_group_known_by_ns=p['known_by_ns'],
            pre_group_source_offset=p['source_offset'],pre_group_age_ns=r['receive_ns']-p['known_by_ns'])
    else:
        for k in ['pre_group_source_ordinal','pre_group_input_cursor','pre_group_event_ns','pre_group_known_by_ns','pre_group_source_offset','pre_group_age_ns']:r[k]=''

# The existing archive is already pinned/verified; no frozen input/database rehash.
with tarfile.open(ARCHIVE,'r|gz') as archive:
    for member in archive:
        if member.name.lstrip('./')==MEMBER:
            assert member.size==464343040
            db=sqlite3.connect(':memory:');db.deserialize(archive.extractfile(member).read());break
    else: raise RuntimeError('Exact saved lifecycle member not found')
db.execute('PRAGMA query_only=ON')
counts=dict(db.execute('SELECT section,count(*) FROM record GROUP BY section'))
spec=importlib.util.spec_from_file_location('frozen_phase_rule',BASE/'scripts/reconstruct_dipole_event_phases.py')
phase_rule=importlib.util.module_from_spec(spec);spec.loader.exec_module(phase_rule)
scalar=collections.defaultdict(list);paths=[];stages=[];queues=[];phase_counts=collections.Counter()
for section,total in counts.items():
    check_time()
    with gzip.open(OUT/f'source-{section}.jsonl.gz','wt',encoding='utf-8',compresslevel=3) as f:
        for sha,known,cursor,instrument,filename,line,text in db.execute(
                'SELECT record_sha256,known_by_ns,input_cursor,instrument_id,source_file,source_line,row_json FROM record WHERE section=? ORDER BY known_by_ns,input_cursor,record_sha256',(section,)):
            j=json.loads(text)
            ref=dict(record_sha256=sha,known_by_ns=known,input_cursor=cursor,instrument_id=instrument,source_file=filename,source_line=line)
            f.write(json.dumps(dict(ref,original_record=j),separators=(',',':'))+'\n')
            # Index references only; the full nested original record above is the evidence.
            scalar[section].append(ref)
            if section=='queue':
                for number,e in enumerate(j.get('episodes',[])):
                    queues.append(dict(ref,order_id=j.get('order_id'),order_episode_index=number,
                        own_fill_count=j.get('own_fill_count'),own_fill_size=j.get('own_fill_size'),
                        terminal_status=j.get('terminal_status'),priority_loss_count=j.get('priority_loss_count'),**e))
            if section=='episode' and isinstance(j.get('dipole'),dict):
                c=j['candidate'];p=j['dipole'];recognition=j['recognition'];s=p['stages']
                labels=phase_rule.phases(s,c['polarity'])
                assert len(s)==p['stage_count'] and known>=s[-1]['recv_ns']
                birth=int(c['event_second'])*1_000_000_000;end=int(s[-1]['recv_ns'])
                idx=np.flatnonzero((receive>=birth)&(receive<=end))
                paths.append(dict(ref,candidate_id=j['candidate_id'],birth_recv_ns=birth,
                    candidate_available_ns=int(c['available_second'])*1_000_000_000,
                    last_stage_recv_ns=end,duration_ns=end-birth,orientation=j['orientation'],
                    polarity=c['polarity'],stage_count=len(s),terminal_phase=j['terminal_phase'],
                    supporting_family_id=recognition.get('family_id'),
                    overlapping_trade_prints=len(idx),overlapping_trade_size=int(sizes[idx].sum()),
                    stage_zero_source_instant='OPEN_SOURCE_AUDIT_FLAG',
                    zero_flow_stages=sum(x['signed_flow']==0 for x in s),
                    path_price_coupling_raw=p.get('price_coupling_raw'),
                    sign_reversal_count=p.get('sign_reversal_count')))
                for st,label in zip(s,labels):
                    phase_counts[label]+=1
                    stages.append(dict(st,candidate_id=j['candidate_id'],candidate_polarity=c['polarity'],
                        reconstructed_event_phase=label,full_row_known_by_ns=known,
                        full_row_input_cursor=cursor,full_row_sha256=sha,
                        phase_basis='EXISTING_CANONICAL_CALLER_RULE_NOT_A_NEW_TRADE_LABEL'))
    print('Read archived lifecycle section',section,total,flush=True)
db.close()
assert len(paths)==862 and len(stages)==54042
assert dict(phase_counts)=={'BIRTH':1319,'PERSISTENCE':51861,'REVERSAL':862}
save_rows('supporting-dipole-paths.csv.gz',paths)
phase_annotations=[]
for path in paths:
    annotations=[{'stage_index':s['stage_index'],'source_stage_recv_ns':s['recv_ns'],
                  'reconstructed_phase':s['reconstructed_event_phase']}
                 for s in stages if s['candidate_id']==path['candidate_id']]
    phase_annotations.append({'candidate_id':path['candidate_id'],'original_full_record_sha256':path['record_sha256'],
                              'original_nested_source':'source-episode.jsonl.gz','stage_annotations':annotations})
with gzip.open(OUT/'supporting-path-phase-annotations.jsonl.gz','wt',encoding='utf-8') as f:
    for row in phase_annotations:f.write(json.dumps(row,separators=(',',':'))+'\n')

# Record all temporal path memberships; overlap is supporting context, not causality.
memberships=[];membership_counts=np.zeros(n,dtype=int)
for path in paths:
    lo=int(np.searchsorted(receive,path['birth_recv_ns'],side='left'))
    hi=int(np.searchsorted(receive,path['last_stage_recv_ns'],side='right'))
    membership_counts[lo:hi]+=1
    for i in range(lo,hi):
        memberships.append(dict(trade_ordinal=i,candidate_id=path['candidate_id'],
            trade_receive_ns=int(receive[i]),path_birth_recv_ns=path['birth_recv_ns'],
            path_last_stage_recv_ns=path['last_stage_recv_ns'],path_complete_known_by_ns=path['known_by_ns'],
            relation='TEMPORAL_OVERLAP_ONLY; path selection does not define trade inventory'))
save_rows('trade-to-supporting-path-links.csv.gz',memberships)
section_cursor={section:set(r['input_cursor'] for r in rows) for section,rows in scalar.items()}
for i,r in enumerate(trades):
    r['overlapping_saved_dipole_paths']=int(membership_counts[i])
    for section in counts:
        r[f'exact_emission_{section}_evidence']=r['group_close_input_cursor'] in section_cursor[section]
save_rows('all-30739-trades.csv.gz',trades)

# Keep the exact run inventory, including roles not represented numerically.
canonical={e['layer_id']:e for g in scope['canonical_99_registry']['groups'] for e in g['entries']}
coverage=[]
for p in scope['original_99_plane_records']:
    entry=p['entry_id'];original=p['original_run_record'];definition=canonical.get(entry,{})
    source_paths=definition.get('source_paths',[])
    coverage.append(dict(ordinal=p['ordinal'],entry_id=entry,role=original.get('role'),
        original_piece_disposition=original.get('disposition'),original_reason=original.get('reason'),
        source_paths_json=json.dumps(source_paths),
        local_canonical_payloads=sum((BASE/'full-context-audit/canonical-sources'/s).is_file() for s in source_paths),
        source_path_count=len(source_paths),
        current_status='IN_SCOPE; full semantic consumer mapping remains NOT_PASSED',
        not_a_claim='original teacher-piece disposition is not a current research exclusion'))
assert len(coverage)==99
save_rows('all-99-source-role-coverage.csv',coverage)
dump('all-13-input-bindings.json',scope['original_13_point_binding'])
knowledge=[]
for filename in ['native_classroom_claims.json','external_classroom_claims.json']:
    original=json.loads((BASE/'full-context-audit/runtime-knowledge'/filename).read_text())
    for row in original:
        knowledge.append(dict(source=filename,original_finding=row,interpretation='hypothesis retained; not a proven trade-lifecycle mechanism'))
dump('all-510-frankie-knowledge-claims.json',knowledge)
assert len(knowledge)==510

# Audit reproducible source rule against transaction outcomes; do not equate flow flips with price flips.
checks=[]
for p in paths:
    idx=np.flatnonzero((receive>=p['birth_recv_ns'])&(receive<=p['last_stage_recv_ns']))
    if len(idx)==0:
        checks.append(dict(candidate_id=p['candidate_id'],prints=0,disposition='no_trade_print_in_path'));continue
    first,last=int(idx[0]),int(idx[-1]);sign=p['polarity']
    actual=int(prices[last]-prices[first]);extreme=(prices[idx].max() if sign>0 else prices[idx].min())
    excursion=int(sign*(extreme-prices[first]));giveback=int(sign*(extreme-prices[last]))
    endlo=int(np.searchsorted(available,p['last_stage_recv_ns'],side='right'))-1
    tailend=int(np.searchsorted(available,p['last_stage_recv_ns']+60_000_000_000,side='right'))-1
    checks.append(dict(candidate_id=p['candidate_id'],prints=len(idx),first_trade_ordinal=first,last_trade_ordinal=last,
        first_trade_receive_ns=int(receive[first]),last_trade_receive_ns=int(receive[last]),
        candidate_polarity=sign,actual_trade_change_raw=actual,flow_aligned_trade_change_raw=sign*actual,
        aligned_maximum_excursion_raw=excursion,giveback_from_aligned_extreme_raw=giveback,
        terminal_flow_phase=p['terminal_phase'],
        after_terminal60s_endpoint_change_raw='' if endlo<0 or tailend<0 or p['last_stage_recv_ns']+60_000_000_000>available[-1] else int(prices[tailend]-prices[endlo]),
        terminal60s_endpoint_age_ns='' if tailend<0 else int(p['last_stage_recv_ns']+60_000_000_000-available[tailend]),
        disposition='transaction-path diagnostic; terminal flow reversal does not establish a price reversal'))
save_rows('flow-lifecycle-vs-actual-trades.csv',checks)

summary=dict(status='COMPLETED_LOCAL_TARGETED_POSTPROCESSING_NOT_A_NEW_MODEL_FIT',
    elapsed_seconds=round(time.monotonic()-START,3),trade_prints=n,native_trade_bursts=len(bursts),
    trade_window_records=len(horizon_rows),session_first_available_ns=int(available[0]),session_last_available_ns=int(available[-1]),
    total_print_size=int(sizes.sum()),trade_price_low_raw=int(prices.min()),trade_price_high_raw=int(prices.max()),
    archived_lifecycle_section_counts=counts,complete_dipole_paths=len(paths),stage_records=len(stages),phase_counts=dict(phase_counts),
    fifo_order_episode_rows=len(queues),trades_with_temporal_path_overlap=int((membership_counts>0).sum()),
    trades_without_temporal_path_overlap=int((membership_counts==0).sum()),trade_path_memberships=len(memberships),
    exact_emission_evidence_counts={section:sum(r[f'exact_emission_{section}_evidence'] for r in trades) for section in counts},
    all_99_roles_retained=True,all_13_bindings_retained=True,all_510_saved_knowledge_claims_retained=True,
    still_open=['Complete 99-plane/knowledge consumer and unit certification NOT_PASSED',
        'Stage-zero source instant for 862 completed paths remains flagged; source-rule phase is not a true trade birth',
        'Full depth/FIFO/lifecycle records are not a continuous full-book/order replay at every trade in these saved projections',
        'Existing exhaustion workflow is retained; append later results by exact trade/cursor/path identity. No trained exhaustion target or duplicate workflow is asserted here',
        'Original MLP repeatability, negative magnitude outputs, poor tail calibration and one-day validation limits unchanged'],
    exact_member_read=dict(archive=str(ARCHIVE.relative_to(ROOT)),member=MEMBER,bytes=464343040,method='SQLite in-memory deserialize; no database saved on C; frozen inputs not rehashed'),
    aws_calls=0,new_fits=0,new_orders=0,old_case_work=False)
dump('targeted-pass-receipt.json',summary)

# Useful whole-day view: actual prints and volumes; no synthetic continuous price.
fig,axs=plt.subplots(2,1,figsize=(15,8),constrained_layout=True,sharex=True)
x=pd.to_datetime(available,unit='ns',utc=True)
axs[0].scatter(x,prices/1e9,s=2,alpha=.45,c='#245878')
axs[0].set_ylabel('Recorded traded price')
axs[0].set_title('All 30,739 recorded trades — retained 2023-10-18 market session (UTC)')
axs[1].scatter(x,sizes,s=3,alpha=.35,c='#a76528')
axs[1].set_ylabel('Trade print size');axs[1].set_xlabel('Actual group-close availability time, UTC')
for ax in axs: ax.grid(alpha=.2)
fig.savefig(OUT/'whole-day-trade-record.png',dpi=140);plt.close(fig)
print(json.dumps(summary,indent=2),flush=True)
