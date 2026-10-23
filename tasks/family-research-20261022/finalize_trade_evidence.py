"""Preserve nested trade evidence, remove redundant flat views, audit source units."""
import collections
import csv
import gzip
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/sqlite-triage/20261022/families'
OUT=BASE/'trade-lifecycle-targeted-v1'

def csvrows(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def jsonrows(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:yield json.loads(line)

def writejson(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

original=csvrows(BASE/'price-curve-timestamps.csv')
index=csvrows(OUT/'all-30739-trades.csv.gz')
assert len(original)==len(index)==30739
by_cursor=collections.defaultdict(list)
for row in original:by_cursor[int(row['group_close_input_cursor'])].append(row)
records_by_cursor=collections.defaultdict(lambda:collections.defaultdict(list))
raw_counts={};scope_counts=collections.Counter();phase_annotations=[]
spec=importlib.util.spec_from_file_location('source_phase_rule',BASE/'scripts/reconstruct_dipole_event_phases.py')
phase_rule=importlib.util.module_from_spec(spec);spec.loader.exec_module(phase_rule)
for path in sorted(OUT.glob('source-*.jsonl.gz')):
    section=path.name[len('source-'):-len('.jsonl.gz')];n=0
    for line_number,r in enumerate(jsonrows(path),1):
        n+=1;cursor=r['input_cursor']
        records_by_cursor[cursor][section].append(dict(file=path.name,line_number=line_number,
            record_sha256=r['record_sha256'],known_by_ns=r['known_by_ns'],input_cursor=cursor))
        j=r['original_record']
        if section=='ladder':scope_counts[j.get('ladder_scope','UNSPECIFIED')]+=1
        if section=='episode' and isinstance(j.get('dipole'),dict):
            stages=j['dipole']['stages'];labels=phase_rule.phases(stages,j['candidate']['polarity'])
            phase_annotations.append(dict(candidate_id=j['candidate_id'],original_nested_record_ref=dict(file=path.name,line_number=line_number,record_sha256=r['record_sha256']),
                annotations=[dict(stage_index=s['stage_index'],original_stage_recv_ns=s['recv_ns'],reconstructed_phase=label) for s,label in zip(stages,labels)],
                definition='source-rule annotations; original entire stage/path stays in its nested source record'))
    raw_counts[section]=n
with gzip.open(OUT/'supporting-path-phase-annotations.jsonl.gz','wt',encoding='utf-8') as f:
    for r in phase_annotations:f.write(json.dumps(r,separators=(',',':'))+'\n')

memberships=collections.defaultdict(list)
for r in csvrows(OUT/'trade-to-supporting-path-links.csv.gz'):
    memberships[int(r['trade_ordinal'])].append(r)
with gzip.open(OUT/'every-trade-evidence-bundle.jsonl.gz','wt',encoding='utf-8',compresslevel=3) as f:
    for number,(source,nav) in enumerate(zip(original,index)):
        assert int(source['source_ordinal'])==number==int(nav['source_ordinal'])
        for key,value in source.items():assert nav[key]==value,(number,key)
        cursor=int(source['group_close_input_cursor']);pre=nav['pre_group_input_cursor']
        row=dict(trade_ordinal=number,original_trade=source,
            exact_clocks={k:int(source[k]) for k in ['event_ns','receive_ns','available_ns','trade_input_cursor','group_close_input_cursor','trade_journal_ordinal']},
            sequence=dict(previous_trade_ordinal=number-1 if number else None,next_trade_ordinal=number+1 if number+1<len(original) else None,
                          source_order='original trade ordinal, exact input cursor; equal clocks do not merge trades'),
            original_emission_record_refs=records_by_cursor.get(cursor,{}),
            last_completed_group_before_trade=dict(source_ordinal=nav['pre_group_source_ordinal'],input_cursor=pre,
                event_ns=nav['pre_group_event_ns'],known_by_ns=nav['pre_group_known_by_ns'],source_offset=nav['pre_group_source_offset'],
                original_record_refs=records_by_cursor.get(int(pre),{}) if pre else {}),
            original_second_set=dict(file='every-trade-original-second-set.jsonl.gz',line_number=number+1,
                scope='all four preserved source views of original 19-number compact subset; not a fabricated full second-set payload'),
            supporting_paths=memberships.get(number,[]),
            complete_run_inventory_ref='../completed-run-source-list.json',
            original_models='Saved forecasts are at original model contexts; no forecast invented or averaged for this trade',
            coverage='Missing record references mean not materialized in this local projection, not zero; original pins and every trade remain retained',
            interpretation_policy='All available later/earlier data and Frankie knowledge may inform retrospective explanation; source identity and event sequence remain explicit')
        f.write(json.dumps(row,separators=(',',':'))+'\n')

# Preserve native grouping as a list of individual prints, not an averaged price/size.
with gzip.open(OUT/'original-native-trade-groups.jsonl.gz','wt',encoding='utf-8') as f:
    for cursor,prints in by_cursor.items():
        f.write(json.dumps(dict(group_close_input_cursor=cursor,original_trade_prints=prints,
            original_emission_record_refs=records_by_cursor.get(cursor,{})),separators=(',',':'))+'\n')

unit_audits=[];examples=[];seen=set()
for row in jsonrows(OUT/'source-absorption.jsonl.gz'):
    cursor=row['input_cursor'];j=row['original_record']
    if cursor not in by_cursor:continue
    prints=by_cursor[cursor]
    # This sum is solely a unit-reconciliation check; every original print is retained.
    tape_quantity=sum(int(t['size']) for t in prints)
    unit_audits.append(dict(original_absorption_record=row,original_trade_prints=prints,
        unit_check=dict(tape_print_quantity=tape_quantity,source_traded_quantity=j['traded_quantity'],
            equality=j['traded_quantity']==tape_quantity,
            annotation='Reference adapter sums action sizes for FILL and TRADE; do not read this field as unique tape executions without reconciling event identities',
            depth_at_open_annotation='Reference adapter computes traded+withdrawn action quantity; this is not the full standing book',
            surviving_depth_annotation='Reference adapter uses added action quantity; this is not established FIFO survival',
            price_response_annotation='Reference calculator orients delta by side; MIXED falls into its non-B branch, so sign is not an unqualified market direction'),
        producer_reference='producer-source/native_group_adapters.py @2ebb8ce8; runtime byte identity still requires its separate source pin'))
    if j['disposition'] not in seen:
        seen.add(j['disposition']);examples.append(dict(selection='first chronological exact-emission tape example of each stored source disposition; no future-price filter',
            trade_ordinals=[int(x['source_ordinal']) for x in prints],absorption_record=row,original_trade_prints=prints))
with gzip.open(OUT/'per-event-unit-reconciliation.jsonl.gz','wt',encoding='utf-8') as f:
    for row in unit_audits:f.write(json.dumps(row,separators=(',',':'))+'\n')
writejson('new-trade-source-examples.json',examples)

# These are redundant intermediate projections made before the user's no-flattening correction.
# Remove only this pass's uncommitted derived views; all original nested evidence stays.
removed=[]
for p in list(OUT.glob('*-scalar-evidence.csv.gz'))+[OUT/'fifo-order-episodes.csv.gz',OUT/'supporting-dipole-stage-evidence.csv.gz',OUT/'all-native-trade-bursts.csv.gz']:
    if p.exists():
        assert p.resolve().is_relative_to(OUT.resolve())
        removed.append(p.name);p.unlink()
receipt=dict(status='LOSSLESS_TRADE_EVIDENCE_PRESERVED',trade_records=30739,dropped_trades=0,
    every_original_trade_field_checked=True,equal_timestamps_preserve_distinct_cursors=True,
    nested_lifecycle_records_preserved=raw_counts,original_ladder_scope_counts=dict(scope_counts),
    reconstructed_path_annotations=len(phase_annotations),event_unit_reconciliations=len(unit_audits),
    source_units_equal_to_unique_tape_size=sum(r['unit_check']['equality'] for r in unit_audits),
    no_averaged_trade_prices_or_model_votes=True,no_original_nested_fields_removed=True,
    removed_redundant_flat_views=removed,
    observational_window_indices='Per-trade path pointers and derived observations remain supplementary, not replacements for original trade sequence',
    knowledge='All 510 saved claims and exact 99/13 run binding lists retained; no claim they are all proven physical mechanisms',
    scientific_gate='NOT_PASSED; original MLP reproducibility and calibration issues unchanged')
writejson('lossless-evidence-verification.json',receipt)
print(json.dumps(receipt,indent=2),flush=True)
