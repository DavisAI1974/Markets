"""Inspect one trade sequence with all locally saved evidence around a dipole turn.

The day-wide inventory remains unchanged. This is an exploratory case, not a
validated signal. Original nested records and all compact states stay intact.
"""
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trade-lifecycle-targeted-v1'
CASE = 'dip-19648-1697581775'


def rows(name):
    with gzip.open(OUT / name, 'rt', encoding='utf-8') as handle:
        for number, line in enumerate(handle, 1):
            yield number, json.loads(line)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


with (BASE / 'price-curve-timestamps.csv').open(newline='', encoding='utf-8') as handle:
    trades = list(csv.DictReader(handle))
assert len(trades) == 30739
selected = set(range(118, 150))
path = next((number, row) for number, row in rows('source-episode.jsonl.gz')
            if row['original_record'].get('candidate_id') == CASE
            and row['original_record'].get('dipole'))
number, original_path = path
stages = original_path['original_record']['dipole']['stages']
terminal_stages = stages[-3:]
assert [stage['signed_flow'] for stage in terminal_stages] == [-1, -1, -1]
assert [stage['price_raw'] for stage in terminal_stages] == [3067000000] * 3
start_ns = terminal_stages[0]['recv_ns']
end_ns = terminal_stages[-1]['recv_ns'] + 1_000_000_000
fresh = [trade for trade in trades if start_ns <= int(trade['receive_ns']) < end_ns]
assert not fresh
before = max((trade for trade in trades if int(trade['receive_ns']) < start_ns),
             key=lambda trade: int(trade['source_ordinal']))
after = next(trade for trade in trades if int(trade['receive_ns']) >= end_ns)
assert (before['source_ordinal'], after['source_ordinal']) == ('143', '144')

compact = [row for _, row in rows('every-trade-original-second-set.jsonl.gz')
           if row['trade_ordinal'] in selected]
bundles = [row for _, row in rows('every-trade-evidence-bundle.jsonl.gz')
           if row['trade_ordinal'] in selected]
root_links = [row for _, row in rows('every-trade-root-record-links.jsonl.gz')
              if row['trade_ordinal'] in selected]
nearby = {}
for section in ['flow_substrate', 'queue', 'replenishment', 'ladder', 'absorption', 'response']:
    nearby[section] = [dict(original_record_line=number, source_record=row)
                       for number, row in rows(f'source-{section}.jsonl.gz')
                       if start_ns - 10_000_000_000 <= row['known_by_ns'] <= end_ns + 10_000_000_000]

refill = next(row['source_record'] for row in nearby['replenishment']
              if row['source_record']['original_record'].get('order_id') == 788699917772)
assert refill['original_record']['action'] == 'A'
assert refill['original_record']['liquidity_kind'] == 'NEW_ID_ADD'
assert refill['original_record']['side'] == 'B'
assert refill['original_record']['price_raw'] == 3066000000
assert refill['original_record']['quantity'] == 1
assert refill['input_cursor'] == 5695

case = dict(
    selection='Exploratory trade sequence used in the conversation; no signal success claim or independent-confirmation claim',
    trade_inventory='All 30,739 trades retained in every-trade-evidence-bundle.jsonl.gz; this case does not filter that population',
    original_trades=trades[118:150],
    original_supporting_path_ref=dict(file='source-episode.jsonl.gz', line_number=number,
                                      record_sha256=original_path['record_sha256']),
    original_supporting_path=original_path,
    original_trade_bundles=bundles, original_compact_views=compact, original_root_links=root_links,
    original_local_records_around_terminal=nearby,
    observed=dict(terminal_stage_interval_start_ns=start_ns, terminal_stage_interval_end_exclusive_ns=end_ns,
                  fresh_trade_prints_in_terminal_interval=fresh,
                  last_actual_trade_before_terminal_readings=before,
                  next_actual_trade=after, direct_new_id_bid_add=refill),
    conclusions=[
        'Three opposed dipole readings are rolling 20-second window observations, not three fresh selling bursts: the complete recorded tape has no new trade in those seconds.',
        'The next actual print is 3.068 after the prior 3.067 print. This rejects an immediate price-reversal reading of the terminal label; it does not prove continued bullish momentum.',
        'A later explicit A event adds one unit with a new order ID at bid 3.066. This establishes a displayed addition at that source clock, not absorption, iceberg refresh or causation of the next higher trade.',
        'A RESTORED outcome credits every pending episode in the neighborhood. Its ratio 43 is arrival density relative to one removed unit, not a fraction of the original order restored; shared credits are not independent confirmations.',
        'Later trades 146 and 147 are 3.066 and 3.065. The higher first tail print therefore does not establish that the wider pullback failed; keep the entire tail.',
        'Second-set numbers are kept individually with states. Far-book identity survival does not prove that a particular touch order survived; source units and windows still require their definitions.',
    ],
    unresolved=[
        'Exact ROOT quote and terminal order identity at trades 143/144 are absent from this local selected-context export. Continuous source pins remain in the original run inventory.',
        'Stage-zero source instant remains open; its event-second label must not be treated as a certified contemporaneous book snapshot or a true trade birth.',
        'Candidate event_second is 1697581775; available_second is 1697581825. No claim of a prebirth forecast from this candidate.',
        'Exhaustion interpretation remains open. Attach existing exhaustion workflow results later by instrument, exact clocks, cursor, order/path identity; do not launch a duplicate workflow.',
        'Semantic coverage NOT_PASSED and original MLP repeatability/calibration issues remain explicit.',
    ],
    reference_definitions=dict(
        rolling_flow='../full-context-audit/scripts/source_reference/native_replay_driver.py:907',
        phase_rule='../scripts/reconstruct_dipole_event_phases.py:11',
        exhaustion='../full-context-audit/scripts/source_reference/native_exhaustion.py',
        identity_limit='Reference definitions do not certify byte identity with every runtime producer'))
save('trade-dipole-overlay-example.json', case)
save('trade-dipole-overlay-receipt.json', dict(
    status='LOCAL_SOURCE_OVERLAY_CHECKED', case=CASE, original_case_trades=len(selected),
    day_trades_retained=len(trades), dropped_day_trades=0,
    fresh_trades_in_three_opposed_stage_seconds=len(fresh),
    original_compact_trade_views=len(compact), original_evidence_bundles=len(bundles),
    original_root_link_records=len(root_links), nearby_source_record_counts={k:len(v) for k,v in nearby.items()},
    no_averaging=True, no_snapshot_execution_inference=True, exhaustion_result='OPEN_EXISTING_WORKFLOW_APPEND_LATER',
    semantic_coverage='NOT_PASSED'))
print('Checked trade/dipole overlay; all 30739 day trades retained; no fresh print in the three opposed stage seconds', flush=True)
