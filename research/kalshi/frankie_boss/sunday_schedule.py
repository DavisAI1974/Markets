"""Map the retained nineteen principal cutoffs to exact closed C15 prefixes."""
import hashlib
import json
from pathlib import Path

from .c15_journal import evidence_hash, canonical_bytes, pack
from .context_session import journal_prefix


def build_schedule(builder, mapping_index, *, expected_index_sha256,
                   cutoffs_path, expected_cutoffs_sha256, model_context_rows):
    """Read every source entry once; no forecasts or market labels are computed.

    Retained group_index is zero-based (the verified first member is group zero).
    Source clocks are prefix maxima, never guessed from the last event alone.
    """
    if type(model_context_rows) is not int or model_context_rows < 1:
        raise ValueError('the schedule declares a positive model_context_rows; it is never a code default')
    raw = Path(cutoffs_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_cutoffs_sha256:
        raise ValueError('retained principal cutoff bytes changed')
    cutoffs = json.loads(raw)['invocation_cutoffs']
    indices = [row['group_index'] for row in cutoffs]
    if len(indices) != 19 or indices != sorted(set(indices)):
        raise ValueError('complete retained nineteen-cutoff roster required')
    mapped, index_hash, group_count, final_cursor = {}, hashlib.sha256(), 0, -1
    with Path(mapping_index).open('rb') as stream:
        for group_index, line in enumerate(stream):
            index_hash.update(line)
            row = json.loads(line)
            if row['cursor_start'] != final_cursor+1:
                raise ValueError('mapping cursor gap')
            final_cursor = row['cursor_end']
            group_count += 1
            if group_index in indices:
                mapped[group_index] = row
    if index_hash.hexdigest() != expected_index_sha256 or set(mapped) != set(indices):
        raise ValueError('full mapping identity or retained cutoff coverage differs')
    if final_cursor != builder.chain.next_cursor-1:
        raise ValueError('full journal and full mapping record counts differ')
    selected = {mapped[i]['cursor_end']: (i, cutoff) for i, cutoff in zip(indices, cutoffs)}
    source_as_of = as_of = 0
    steps, first_trade = [], None
    for row in journal_prefix(builder, final_cursor):
        normal = row['normalized']
        source_as_of = max(source_as_of, normal['ts_event_ns'])
        as_of = max(as_of, normal['ts_recv_ns'])
        record = row['raw_record']
        if (first_trade is None and record.get('action') == 'T'
                and type(record.get('price')) is int and 0 < record['price'] < 2**63-1):
            first_trade = dict(cursor=row['cursor'], ts_event_ns=normal['ts_event_ns'],
                ts_recv_ns=normal['ts_recv_ns'], price_raw=record['price'],
                evidence_hash=evidence_hash(row), source_prefix_hash=row['terminal_prefix_hash'])
        if row['cursor'] in selected:
            group_index, original = selected[row['cursor']]
            if (not record['flags'] & 128 or original['recv_ns'] != normal['ts_recv_ns']
                    or original['first_lawful_availability_ns'] != as_of):
                raise ValueError('retained cutoff differs from actual closed causal prefix')
            steps.append(dict(group_index=group_index, groups_delivered=group_index+1,
                through_cursor=row['cursor'], records_delivered=row['cursor']+1,
                as_of=as_of, source_as_of=source_as_of,
                source_hash=row['terminal_prefix_hash']))
    terminal = dict(groups_delivered=group_count, records_delivered=final_cursor+1,
        through_cursor=final_cursor, as_of=as_of, source_as_of=source_as_of,
        source_hash=builder.chain.prefix_hash)
    for index, step in enumerate(steps):
        later = steps[index+1] if index+1 < len(steps) else terminal
        if later['as_of'] <= step['as_of']:
            raise ValueError('strictly later feedback availability required')
        step['feedback_available_through'] = dict(later)
    result = dict(schema='BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1',
        cutoff_file_sha256=expected_cutoffs_sha256, mapping_index_sha256=expected_index_sha256,
        steps=steps, terminal_delivery=terminal, first_observed_trade_candidate=first_trade,
        anchor_authorship='candidate evidence only; principal must certify interval convention',
        model_context_rows=model_context_rows, source_dates_required=1, feedback_lag='next retained cutoff')
    return dict(result, schedule_sha256=hashlib.sha256(canonical_bytes(pack(result))).hexdigest())
