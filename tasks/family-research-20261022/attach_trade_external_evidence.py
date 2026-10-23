"""Attach every original external series to every trade without replacing raw history.

No new external source, fit, resampling, interpolation or averaged value. The
complete original nested history stays in its existing Git file; pointers retain
all earlier/later rows. Time selects descriptive views, never evidence eligibility.
"""
import bisect
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trade-lifecycle-targeted-v1'
SOURCE = BASE / 'external-classroom-audit-v1/original_series_known_values.json'
source = json.loads(SOURCE.read_text(encoding='utf-8'))
series = source['series']
assert len(series) == 48
binding = json.loads((OUT / 'all-13-input-bindings.json').read_text())
bound_names = {row['series'] for point in binding['points'] for row in point.get('series', [])}
assert bound_names <= {item['name'] for item in series}
with (BASE / 'price-curve-timestamps.csv').open(newline='', encoding='utf-8') as handle:
    trades = list(csv.DictReader(handle))
assert len(trades) == 30739

prepared = []
for source_series_index, item in enumerate(series):
    indexed = sorted(enumerate(item['known']), key=lambda pair: (pair[1]['published_ns'], pair[0]))
    times = [record['published_ns'] for _, record in indexed]
    assert all(type(value) is int for value in times)
    prepared.append((source_series_index, item, indexed, times))


def position(indexed, times, when):
    at = bisect.bisect_right(times, when) - 1
    return dict(last_published_original_known_index=indexed[at][0] if at >= 0 else None,
                first_later_original_known_index=indexed[at + 1][0] if at + 1 < len(indexed) else None)


source_ref = SOURCE.relative_to(OUT.parent).as_posix()
examples = {}
with gzip.open(OUT / 'every-trade-original-external-links.jsonl.gz', 'wt', encoding='utf-8') as output:
    for number, trade in enumerate(trades):
        assert number == int(trade['source_ordinal'])
        receive = int(trade['receive_ns'])
        available = int(trade['available_ns'])
        observations = []
        for index, item, indexed, times in prepared:
            observations.append(dict(source_series_index=index, series_name=item['name'],
                                     at_trade_receive=position(indexed, times, receive),
                                     at_group_known_by=position(indexed, times, available)))
        record = dict(trade_ordinal=number, event_ns=int(trade['event_ns']), receive_ns=receive,
                      known_by_ns=available, trade_input_cursor=int(trade['trade_input_cursor']),
                      group_close_input_cursor=int(trade['group_close_input_cursor']),
                      original_nested_source='../' + source_ref,
                      original_series=observations,
                      full_history='Every original known[] row remains accessible, including all later rows; these views do not restrict retrospective evidence',
                      pointer_rule='source.series[source_series_index].known[original_known_index]; equal publication clocks use the last original row; no interpolation or fallback to an older PRESENT state')
        output.write(json.dumps(record, separators=(',', ':')) + '\n')
        if number in [118, 122, 123, 143, 144, 149]:
            examples[str(number)] = record

start = int(trades[118]['receive_ns'])
end = int(trades[149]['available_ns'])
terminal_start = 1697582164000000000
terminal_end = 1697582167000000000
case = []
for index, item, indexed, times in prepared:
    at = position(indexed, times, int(trades[143]['receive_ns']))
    pre_case = position(indexed, times, start)['last_published_original_known_index']
    before_index = at['last_published_original_known_index']
    next_index = at['first_later_original_known_index']
    case.append(dict(source_series_index=index, name=item['name'], table=item['table'], column=item['column'],
                     original_where=item.get('where'),
                     original_last_published_row_at_first_selected_trade=item['known'][pre_case] if pre_case is not None else None,
                     original_last_published_row_at_trade143=item['known'][before_index] if before_index is not None else None,
                     original_first_later_row=item['known'][next_index] if next_index is not None else None,
                     original_rows_published_during_selected_trade_sequence=[r for r in item['known'] if start <= r['published_ns'] <= end],
                     original_rows_published_during_three_terminal_seconds=[r for r in item['known'] if terminal_start <= r['published_ns'] < terminal_end]))
claims = json.loads((OUT / 'all-510-frankie-knowledge-claims.json').read_text())
report = dict(case='Original trades 118–149 around the supporting dipole transition; all day trades retained',
              original_series=case, selected_trade_links=examples,
              interpretation=[
                  'GFS published_ns 1697581800000000000 falls inside this sequence: October 18 HDD changes 5.126 to 4.941 while October 19 changes 3.756 to 4.087. Preserve opposite horizon changes; no combined weather vote or causal claim.',
                  'No original external series declares a new publication within the three terminal dipole seconds. This limits a fresh-release explanation there; existing and later context remain available.',
                  'The curve fields at trade143 share source_ordinal 16023 and its receive clock. Multiple fields of one row are not independent confirmations.',
                  'Invalid temperature records, including literal M at ATL, are retained as INVALID rather than zero, a valid temperature or an imputed older reading.'
              ],
              knowledge='All 510 original Frankie claims remain available in all-510-frankie-knowledge-claims.json; an external reading or claim does not establish a trade mechanism',
              evidence_clock_limit='Original published_ns are source declarations, not proof of actual live capture; later knowledge is permitted in this analysis',
              no_source_averaging_or_state_imputation=True)
(OUT / 'trade-dipole-external-overlay.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
receipt = dict(status='ALL_TRADES_LINKED_TO_ALL_48_ORIGINAL_EXTERNAL_SERIES', trades=len(trades), dropped_trades=0,
               original_series=len(series), original_known_rows=sum(len(item['known']) for item in series),
               original_binding_points=len(binding['points']), all_bound_series_accounted_for=True,
               original_source='../' + source_ref, original_13_binding='all-13-input-bindings.json',
               original_nested_rows_untouched=True, all_later_rows_retained=True,
               selected_sequence_series_with_declared_updates=sum(bool(row['original_rows_published_during_selected_trade_sequence']) for row in case),
               terminal_three_second_series_with_declared_updates=sum(bool(row['original_rows_published_during_three_terminal_seconds']) for row in case),
               frankie_claims_retained=len(claims), aws_calls=0, fits=0, source_rehash=False,
               semantic_coverage='NOT_PASSED; linking original evidence does not certify consumers or a trade signal')
(OUT / 'external-overlay-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt, indent=2), flush=True)
