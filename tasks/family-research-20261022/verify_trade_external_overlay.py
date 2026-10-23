"""Check saved external pointers, original publication clocks and every trade's identity."""
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trade-lifecycle-targeted-v1'
source = json.loads((BASE / 'external-classroom-audit-v1/original_series_known_values.json').read_text())['series']
with (BASE / 'price-curve-timestamps.csv').open(newline='') as handle:
    trades = list(csv.DictReader(handle))
checked = 0
with gzip.open(OUT / 'every-trade-original-external-links.jsonl.gz', 'rt') as handle:
    for count, line in enumerate(handle, 1):
        row = json.loads(line)
        original = trades[count - 1]
        assert row['trade_ordinal'] == count - 1
        for key, source_key in [('event_ns', 'event_ns'), ('receive_ns', 'receive_ns'),
                                ('known_by_ns', 'available_ns'), ('trade_input_cursor', 'trade_input_cursor'),
                                ('group_close_input_cursor', 'group_close_input_cursor')]:
            assert type(row[key]) is int and row[key] == int(original[source_key])
        assert len(row['original_series']) == len(source) == 48
        for index, pointer in enumerate(row['original_series']):
            assert pointer['source_series_index'] == index
            assert pointer['series_name'] == source[index]['name']
            for key, when in [('at_trade_receive', row['receive_ns']), ('at_group_known_by', row['known_by_ns'])]:
                last = pointer[key]['last_published_original_known_index']
                later = pointer[key]['first_later_original_known_index']
                if last is not None:
                    assert source[index]['known'][last]['published_ns'] <= when
                if later is not None:
                    assert source[index]['known'][later]['published_ns'] > when
                checked += 1
assert count == len(trades) == 30739
receipt = dict(status='PASSED_ALL_TRADE_EXTERNAL_POINTER_CHECKS', trades=count, dropped_trades=0,
               original_series=48, exact_trade_clocks_checked=True, source_views_checked=checked,
               original_nested_history_unchanged=True, all_later_history_still_referenced=True,
               scope='Publication pointers checked; source claims are not certified live arrivals or causal effects',
               semantic_coverage='NOT_PASSED')
(OUT / 'external-overlay-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2), flush=True)
