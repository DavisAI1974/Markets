"""Reconcile saved T/F roles with exact resting IDs, without changing originals."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from continue_trade_chronology import PARENT, ROOT, sequence_diagnostics

GAP = PARENT / 'quote-order-gapfill-v1'
OUT = GAP / 'role-reconciliation-v1'
REFERENCE = '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    # Exact Git objects already present locally; no fetch, checkout or runtime change.
    references = []
    for path in ['research/ng_exhaustion_mbo_v4_state_adapter_20260820.py',
                 'research/kalshi/frankie_raw_mbo_benchmark/native_clocks.py']:
        spec = REFERENCE + ':' + path
        data = subprocess.check_output(['git', 'show', spec], cwd=ROOT)
        destination = OUT / Path(path).name
        destination.write_bytes(data)
        references.append(dict(reference_commit=REFERENCE, original_path=path,
                               local_file=destination.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                               git_blob_sha=subprocess.check_output(['git', 'rev-parse', spec], cwd=ROOT, text=True).strip(),
                               status='CANONICAL_REFERENCE; exact runtime db96f24f identity remains unproved'))
    save('producer-reference-provenance.json', references)
    analyses = json.loads((GAP / 'each-trade-exact-quote-order-analysis.json').read_text())
    wanted = {(r[k]['chunk'], r[k]['chunk_line_number']) for r in analyses
              for k in ['exact_before_group_ref', 'exact_after_group_ref']}
    states = {}
    for chunk in sorted({x[0] for x in wanted}):
        with gzip.open(GAP / chunk, 'rt', encoding='utf-8') as handle:
            for n, line in enumerate(handle, 1):
                if (chunk, n) in wanted:
                    states[(chunk, n)] = json.loads(line)
    results = []
    for r in analyses:
        before_ref, after_ref = r['exact_before_group_ref'], r['exact_after_group_ref']
        before = states[(before_ref['chunk'], before_ref['chunk_line_number'])]
        after = states[(after_ref['chunk'], after_ref['chunk_line_number'])]
        t = r['original_matched_trade_actions'][0]
        resting = {q['order_id']: dict(resting_side=side, resting_price_raw=level['price_raw'],
                                      original_queue_entry=q, original_before_group_ref=before_ref)
                   for side, key in [('B', 'bid_levels_full'), ('A', 'ask_levels_full')]
                   for level in before['book_full'][key] for q in level['fifo_queue']}
        fills = []
        for fill in r['original_same_price_fill_actions']:
            state = resting.get(fill['order_id'])
            updates = [a for a in after['raw_actions'] if a['action'] in ['C', 'M']
                       and a['order_id'] == fill['order_id']]
            fills.append(dict(original_fill_action=fill, pre_group_resting_order=state,
                              original_same_id_book_updates=updates,
                              same_id_as_T=fill['order_id'] == t['order_id'],
                              resting_price_matches_execution_price=None if state is None
                              else state['resting_price_raw'] == fill['price_raw']))
        seq = sequence_diagnostics([a['sequence'] for a in after['raw_actions']])
        assert seq['literal_one_sequence_per_action'] == after['sequence_contiguous']
        results.append(dict(trade_ordinal=r['trade_ordinal'], original_trade=r['original_trade'],
                            original_before_group_ref=before_ref, original_after_group_ref=after_ref,
                            original_root_before_ref=r['exact_root_before_ref'], original_root_after_ref=r['exact_root_after_ref'],
                            original_rich_second_set_ref=r['rich_second_set_ref'],
                            original_complete_group_actions=after['raw_actions'], original_T=t,
                            source_reported_aggressor_side=t['side'],
                            aggressor_side_status='SOURCE_UNSPECIFIED' if t['side'] == 'N' else 'SOURCE_REPORTED; do not replace from price movement',
                            original_T_id_pre_group_resting_state=resting.get(t['order_id']),
                            fill_order_reconciliation=fills,
                            original_quantity_reconciliation=r['quantity_and_side_reconciliation'],
                            literal_sequence_diagnostics=seq, original_integrity=after['integrity'],
                            original_integrity_delta=after['integrity_delta'],
                            original_capture_observations=after.get('capture_observations'),
                            exact_known_by_ns=after_ref['known_by_ns'], exact_cursor=after_ref['input_cursor']))
    save('all-32-trade-role-reconciliation.json', results)
    diagnostics = []
    with gzip.open(GAP / 'all-original-actions-in-episode.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            sequences = [a['sequence'] for a in row['original_raw_actions']]
            diagnostics.append(dict(original_source_ref=row['source_ref'], original_action_sequences=sequences,
                                    diagnostics=sequence_diagnostics(sequences)))
    save('all-1667-group-sequence-diagnostics.json', diagnostics)
    counts = collections.Counter()
    for row in diagnostics:
        d = row['diagnostics']
        counts['groups'] += 1
        for name, value in [('literal_false', not d['literal_one_sequence_per_action']),
                            ('duplicate_sequence_groups', bool(d['duplicate_adjacent_pairs'])),
                            ('forward_jump_groups', bool(d['forward_jump_pairs'])),
                            ('regression_groups', bool(d['regression_pairs']))]:
            counts[name] += value
    save('verification.json', dict(status='PASSED_SAVED_ROLE_AND_LITERAL_SEQUENCE_CHECKS',
                                  exact_trade_contexts=len(results), sequence_group_counts=dict(counts),
                                  original_sources_overwritten=False, network_source_reads=0, aws_operations=0,
                                  semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED',
                                  remaining_quantity_trade_ordinals=[119, 134],
                                  source_unspecified_aggressor_trade_ordinals=[126, 133],
                                  same_side_fill_role_trade_ordinals=[123, 128],
                                  channel_continuity='UNRESOLVED; instrument-scoped jumps are not a channel packet-loss audit'))
    print(json.dumps(dict(exact_trade_contexts=len(results), sequence_group_counts=dict(counts))))


if __name__ == '__main__':
    main()
