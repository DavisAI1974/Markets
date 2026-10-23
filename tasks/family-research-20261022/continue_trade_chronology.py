"""Trade-first navigation of saved originals; no source retrieval, fits or averaging."""
import csv
import collections
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1'
OUT = PARENT / 'chronological-lifecycle-v1'


def price_stretches(prices):
    """Maximal equal-price stretches, retaining every individual trade ordinal."""
    stretches, membership = [], []
    for ordinal, price in enumerate(prices):
        if not stretches or stretches[-1]['price_raw'] != price:
            stretches.append(dict(stretch_ordinal=len(stretches), price_raw=price,
                                  first_trade_ordinal=ordinal, last_trade_ordinal=ordinal))
        stretches[-1]['last_trade_ordinal'] = ordinal
        membership.append(len(stretches) - 1)
    for i, stretch in enumerate(stretches):
        incoming = None if i == 0 else stretch['price_raw'] - stretches[i - 1]['price_raw']
        outgoing = None if i + 1 == len(stretches) else stretches[i + 1]['price_raw'] - stretch['price_raw']
        stretch.update(incoming_step_raw=incoming, outgoing_step_raw=outgoing,
                       print_direction_turn=None if incoming is None or outgoing is None
                       else incoming * outgoing < 0)
    return stretches, membership


def sequence_diagnostics(sequences):
    """Diagnose the literal producer test without calling repeats packet loss."""
    return dict(
        literal_one_sequence_per_action=sequences == list(range(sequences[0], sequences[0] + len(sequences))),
        duplicate_adjacent_pairs=[[i, i + 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if a == b],
        forward_jump_pairs=[[i, i + 1, b - a - 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if b > a + 1],
        regression_pairs=[[i, i + 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if b < a])


def print_legs(stretches):
    """Maximal same-sign distinct-print steps; turning stretches belong to both."""
    legs = []
    membership = [[] for _ in stretches]
    for end in range(1, len(stretches)):
        sign = 1 if stretches[end]['incoming_step_raw'] > 0 else -1
        if not legs or legs[-1]['step_sign'] != sign:
            legs.append(dict(leg_ordinal=len(legs), first_stretch_ordinal=end - 1,
                             last_stretch_ordinal=end, step_sign=sign))
        else:
            legs[-1]['last_stretch_ordinal'] = end
    for leg in legs:
        for stretch in range(leg['first_stretch_ordinal'], leg['last_stretch_ordinal'] + 1):
            membership[stretch].append(leg['leg_ordinal'])
    return legs, membership


def jsonrows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            yield json.loads(line)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(name, rows):
    with (OUT / name).open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
            for row in rows:
                handle.write((json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n').encode())


def main():
    OUT.mkdir(exist_ok=True)
    with (PARENT.parent / 'price-curve-timestamps.csv').open(newline='') as handle:
        trades = list(csv.DictReader(handle))
    assert len(trades) == 30739
    assert [int(t['source_ordinal']) for t in trades] == list(range(len(trades)))
    stretches, membership = price_stretches([int(t['price_raw']) for t in trades])
    legs, leg_membership = print_legs(stretches)
    for stretch in stretches:
        lo, hi = stretch['first_trade_ordinal'], stretch['last_trade_ordinal']
        stretch.update(first_exact_clocks=clocks(trades[lo]), last_exact_clocks=clocks(trades[hi]),
                       observed_first_to_last_receive_ns=int(trades[hi]['receive_ns']) - int(trades[lo]['receive_ns']),
                       previous_different_price_trade_ordinal=None if lo == 0 else lo - 1,
                       next_different_price_trade_ordinal=None if hi + 1 == len(trades) else hi + 1,
                       original_trade_file='../every-trade-evidence-bundle.jsonl.gz',
                       original_trade_line_numbers_1based=[lo + 1, hi + 1],
                       scope='OBSERVED_PRINT_SEQUENCE; equal prices are navigation, not merged trades or inferred orders')
    for leg in legs:
        lo = stretches[leg['first_stretch_ordinal']]['first_trade_ordinal']
        hi = stretches[leg['last_stretch_ordinal']]['last_trade_ordinal']
        leg.update(first_trade_ordinal=lo, last_trade_ordinal=hi, first_exact_clocks=clocks(trades[lo]),
                   last_exact_clocks=clocks(trades[hi]),
                   observed_first_to_last_receive_ns=int(trades[hi]['receive_ns']) - int(trades[lo]['receive_ns']),
                   print_price_change_raw=int(trades[hi]['price_raw']) - int(trades[lo]['price_raw']),
                   left_observation_boundary=lo == 0, right_observation_boundary=hi == len(trades) - 1,
                   original_trade_file='../every-trade-evidence-bundle.jsonl.gz',
                   scope='SAME_SIGN_PRINT_STEPS; overlaps at turns are retained; not aggressor flow or quote momentum')
    write_rows('all-price-stretches.jsonl.gz', stretches)
    write_rows('all-overlapping-print-legs.jsonl.gz', legs)

    removals = collections.defaultdict(list)
    for line_n, row in enumerate(jsonrows(PARENT / 'each-removal-with-original-order-evidence.jsonl.gz'), 1):
        original = row['original_removal_record']
        removals[original['input_cursor']].append(dict(
            original_source_file='../each-removal-with-original-order-evidence.jsonl.gz', line_number=line_n,
            order_id=original['original_record']['order_id'], known_by_ns=original['known_by_ns'],
            source_bound_interpretation=row['source_bound_interpretation'],
            terminal_states=[x['original_record'].get('terminal_status') for x in row['original_terminal_order_records']]))
    exact = {r['trade_ordinal']: i + 1 for i, r in enumerate(json.loads(
        (PARENT / 'quote-order-gapfill-v1/role-reconciliation-v1/all-32-trade-role-reconciliation.json').read_text()))}
    counts = collections.Counter()

    def annotated():
        for i, bundle in enumerate(jsonrows(PARENT / 'every-trade-evidence-bundle.jsonl.gz')):
            assert bundle['trade_ordinal'] == i and bundle['original_trade'] == trades[i]
            t = trades[i]
            assert bundle['exact_clocks'] == clocks(t)
            stretch_id = membership[i]
            stretch = stretches[stretch_id]
            counts['trades'] += 1
            counts['with_same_emission_removal_links'] += bool(removals[int(t['group_close_input_cursor'])])
            counts['without_supporting_dipole_overlap'] += not bundle['supporting_paths']
            counts['with_exact_quote_order_role_context'] += i in exact
            yield dict(
                trade_ordinal=i, original_trade=t, exact_clocks=clocks(t),
                original_evidence_bundle=dict(file='../every-trade-evidence-bundle.jsonl.gz', line_number=i + 1),
                earlier_observed_trade_ordinals=None if i == 0 else [0, i - 1],
                later_observed_trade_ordinals=None if i + 1 == len(trades) else [i + 1, len(trades) - 1],
                all_later_evidence_eligible=True,
                equal_price_stretch_ref=dict(file='all-price-stretches.jsonl.gz', line_number=stretch_id + 1),
                overlapping_print_leg_refs=[dict(file='all-overlapping-print-legs.jsonl.gz', line_number=n + 1)
                                           for n in leg_membership[stretch_id]],
                previous_different_price_trade_ordinal=stretch['previous_different_price_trade_ordinal'],
                next_different_price_trade_ordinal=stretch['next_different_price_trade_ordinal'],
                incoming_print_step_raw=stretch['incoming_step_raw'], outgoing_print_step_raw=stretch['outgoing_step_raw'],
                observed_print_direction_turn=stretch['print_direction_turn'],
                original_strict_prior_group=bundle['last_completed_group_before_trade'],
                original_emission_record_refs=bundle['original_emission_record_refs'],
                same_emission_recorded_removal_refs=removals[int(t['group_close_input_cursor'])],
                supporting_paths=bundle['supporting_paths'],
                original_second_set_ref=dict(file='../every-trade-original-second-set.jsonl.gz', line_number=i + 1),
                original_root_measurement_links_ref=dict(file='../every-trade-root-record-links.jsonl.gz', line_number=i + 1),
                original_external_links_ref=dict(file='../every-trade-original-external-links.jsonl.gz', line_number=i + 1),
                continuous_native_links_ref=dict(file='../quote-order-gapfill-v1/every-trade-new-source-links.jsonl.gz', line_number=i + 1),
                checked_quote_order_role_context=None if i not in exact else dict(
                    file='../quote-order-gapfill-v1/role-reconciliation-v1/all-32-trade-role-reconciliation.json',
                    array_ordinal=exact[i] - 1),
                knowledge_and_full_run_policy_ref='scope-and-interpretation-policy.json',
                lifecycle_status=dict(print_path='OBSERVED_CHRONOLOGY_ANNOTATED',
                                      order_quote_mechanism='BOUNDED_CHECKED_CONTEXT_WITH_RETAINED_LIMITS' if i in exact
                                      else 'UNFINISHED; follow original source links',
                                      causal_precursor='NOT_VALIDATED', exhaustion='UNASSESSED; attach existing work later',
                                      terminal_status='OBSERVATION_BOUNDARY' if i + 1 == len(trades) else 'LATER_PRINTS_RETAINED',
                                      semantic_coverage='NOT_PASSED'))
        assert counts['trades'] == len(trades)
    write_rows('every-trade-chronological-lifecycle.jsonl.gz', annotated())
    scope = json.loads((PARENT.parent / 'completed-run-source-list.json').read_text())
    knowledge = json.loads((PARENT / 'all-510-frankie-knowledge-claims.json').read_text())
    assert len(scope['original_99_plane_records']) == 99 and len(knowledge) == 510
    save('scope-and-interpretation-policy.json', dict(
        exact_original_full_run_scope='../../completed-run-source-list.json', source_roles=99,
        all_original_knowledge_claims='../all-510-frankie-knowledge-claims.json', knowledge_claims=510,
        original_bindings='../all-13-input-bindings.json', original_external_history='../../external-classroom-audit-v1/original_series_known_values.json',
        all_original_forecasts='../../final-model-analysis-20261023/source/',
        frankie_method_reference='../../full-context-audit/canonical-sources/research/kalshi/agents/frankie_native_raw_mbo_knowledge/A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md',
        method_clauses_applied=['separate exact event/receive/group-availability clocks',
                                'families do not define eligibility', 'do not replace first available evidence with later favorable evidence',
                                'retain negative, unresolved, unmatched and censored evidence'],
        retrospective_later_evidence='All complete external histories, later original source rows and later knowledge remain eligible. No time cutoff limits retrospective evidence.',
        historical_forecast_rule='Original forecasts retain their actual contexts; no per-trade forecast invented or future information assigned to a historical forecast.',
        coverage_limit='References preserve the entire exact source scope. They do not certify semantic consumption of every role or knowledge claim.',
        print_path_limit='Print steps can reflect bid/ask alternation. They are not inferred aggressor flow, quote reversals, causal precursors, strategy inventory or exhaustion signals.',
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED; original evidence unchanged'))
    save('chronology-receipt.json', dict(
        status='ALL_TRADES_ANNOTATED_WITH_EXACT_OBSERVED_CHRONOLOGY', counts=dict(counts),
        equal_price_stretches=len(stretches), overlapping_same_sign_print_legs=len(legs),
        print_direction_turn_stretches=sum(s['print_direction_turn'] is True for s in stretches),
        source_trades=30739, dropped_trades=0, original_trade_fields_unchanged=True,
        exact_integer_clocks=True, averaging=False, raw_source_scan=False, source_retrieval=False,
        fits=0, aws_operations=0, new_resources=0,
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print(json.dumps(dict(counts=counts, stretches=len(stretches), print_legs=len(legs))))


def clocks(trade):
    return {k: int(trade[k]) for k in ['event_ns', 'receive_ns', 'available_ns',
                                      'trade_input_cursor', 'group_close_input_cursor', 'trade_journal_ordinal']}


if __name__ == '__main__':
    main()
