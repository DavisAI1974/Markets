"""Attach original selected ROOT/native rows and distinguish fill cleanup from cancels.

No averaging, replacement of original fields, model changes or trade filtering.
"""
import collections
import csv
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/sqlite-triage/20261022/families'
OUT=BASE/'trade-lifecycle-targeted-v1'

def csvrows(path):
    with gzip.open(path,'rt',newline='') as f:return list(csv.DictReader(f))

def jsonrows(path):
    with gzip.open(path,'rt') as f:
        for line in f:yield json.loads(line)

trades=csvrows(OUT/'all-30739-trades.csv.gz')
wanted={r[k] for r in trades for k in ['pre_group_source_ordinal','emission_group_source_ordinal'] if r[k]!=''}
root_refs=collections.defaultdict(list);example_quotes=collections.defaultdict(lambda:collections.defaultdict(list))
examples={217,588,286458,286459}
source=BASE/'descriptive-v1/complete_context_measurements.csv.gz'
count=0
with gzip.open(source,'rt',newline='') as f,gzip.open(OUT/'original-root-native-measurement-rows.jsonl.gz','wt') as out:
    for source_row,r in enumerate(csv.DictReader(f),1):
        if int(r['source_ordinal']) in examples and r['feature'] in ['root.best_bid','root.best_ask','root.mid','root.bid_depth_full','root.ask_depth_full']:
            example_quotes[int(r['source_ordinal'])][r['feature']].append(r)
        if r['source_ordinal'] not in wanted:continue
        count+=1
        out.write(json.dumps(dict(original_source='descriptive-v1/complete_context_measurements.csv.gz',original_csv_row=source_row,
                                  original_measurement_row=r),separators=(',',':'))+'\n')
        root_refs[r['source_ordinal']].append(count)
with gzip.open(OUT/'every-trade-root-record-links.jsonl.gz','wt') as out:
    for r in trades:
        out.write(json.dumps(dict(trade_ordinal=int(r['source_ordinal']),
            original_source_record_file='original-root-native-measurement-rows.jsonl.gz',
            last_completed_group_original_record_lines=root_refs.get(r['pre_group_source_ordinal'],[]),
            emission_group_original_record_lines=root_refs.get(r['emission_group_source_ordinal'],[]),
            interpretation='Exact original selected-context measurements; repeated source occurrences retained. Missing links do not delete the trade or assert a zero.'),separators=(',',':'))+'\n')

queues=collections.defaultdict(list);tape=collections.defaultdict(list)
for t in trades:tape[int(t['group_close_input_cursor'])].append(t)
for r in jsonrows(OUT/'source-queue.jsonl.gz'):
    j=r['original_record'];queues[(r['input_cursor'],j['order_id'])].append(r)
links=collections.Counter();selected=[];records=0
with gzip.open(OUT/'each-removal-with-original-order-evidence.jsonl.gz','wt') as out:
    for r in jsonrows(OUT/'source-replenishment.jsonl.gz'):
        j=r['original_record']
        if j.get('action')!='C':continue
        records+=1;matches=queues.get((r['input_cursor'],j.get('order_id')),[])
        statuses={m['original_record'].get('terminal_status') for m in matches}
        if len(statuses)>1:classification='CONTRADICTORY_TERMINAL_ORDER_STATES_RETAINED'
        elif statuses=={'FILLED'}:classification='SOURCE_LINKED_FILLED_ORDER_REMOVAL; DO_NOT_COUNT_AS_NEW_MAKER_CANCELLATION'
        elif statuses=={'CANCELLED'}:classification='SOURCE_LINKED_CANCELLED_ORDER'
        else:classification='UNRESOLVED_WITHOUT_SAME_EMISSION_TERMINAL_ORDER_RECORD'
        links[classification]+=1
        row=dict(original_removal_record=r,original_terminal_order_records=matches,
                 original_tape_prints_at_same_emission=tape.get(r['input_cursor'],[]),
                 source_bound_interpretation=classification,
                 boundary='Exact emission cursor plus order identity, not net snapshot differencing. Full producer/runtime provenance remains separately auditable.')
        out.write(json.dumps(row,separators=(',',':'))+'\n')
        if r['input_cursor'] in [1141,374919]:selected.append(row)
(OUT/'new-trade-order-evidence.json').write_text(json.dumps(selected,indent=2)+'\n')
(OUT/'new-trade-exact-root-evidence.json').write_text(json.dumps(dict(example_quotes),indent=2)+'\n')
receipt=dict(status='ORIGINAL_MEASUREMENT_AND_ORDER_IDENTITIES_ATTACHED',trade_records=len(trades),dropped_trades=0,
    original_root_native_measurement_rows=count,source_ordinals_with_saved_measurements=len(root_refs),
    exact_emission_measurement_coverage=sum(bool(root_refs.get(r['emission_group_source_ordinal'])) for r in trades),
    exact_pre_group_measurement_coverage=sum(bool(root_refs.get(r['pre_group_source_ordinal'])) for r in trades),
    removal_records_preserved=records,removal_evidence_states=dict(links),
    no_source_values_overwritten=True,no_average_or_model_vote=True,
    scope='Original selected-context ROOT/native measurement export plus archived MBO lifecycle records; not a new continuous full-payload export for every trade prefix')
(OUT/'root-and-order-evidence-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
