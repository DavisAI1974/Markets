"""Independent checks of the new pointers against existing nested source exports."""
import collections
import csv
import json
import re

from query_saved_run_connections import BASE, OUT, TRADE, ROOT, rows


def main():
    with (BASE / 'price-curve-timestamps.csv').open(newline='') as handle:
        originals = list(csv.DictReader(handle))
    cases = list(rows(BASE / 'instance-market-review-20261023/individual-instance-records.jsonl.gz'))
    assert [c['instance'] for c in cases] == list(range(1, 750))
    contexts = list(rows(OUT / 'all-749-original-model-context-links.jsonl.gz'))
    assert len(contexts) == len(cases) == 749
    for i, (context, case) in enumerate(zip(contexts, cases), 1):
        assert context['context_line'] == i
        for k in ('instance', 'family_id', 'sample_id', 'instrument_id', 'start_receive_ns', 'start_event_ns',
                  'decision_cutoff_ns', 'cursor_cap', 'pre_source_ordinal', 'pre_known_by_ns', 'pre_input_cursor',
                  'forecast_disposition'):
            assert context[k] == case[k]
        assert context['original_forecast_rows'] == len(case['forecasts'])
        assert context['original_nested_case']['line_number'] == i
        assert (OUT / context['original_nested_case']['file']).is_file()
        assert (OUT / context['readable_case']).is_file()
    assert sum(c['original_forecast_rows'] for c in contexts) == 109674

    orders = list(rows(OUT / 'all-observed-removal-and-bounded-T-order-lineage-links.jsonl.gz'))
    by_order = {(r['instrument_id'], r['order_id']): r for r in orders}
    assert len(by_order) == len(orders) == 7939
    expected = collections.defaultdict(list)
    for record in rows(TRADE / 'source-lineage.jsonl.gz'):
        raw = record['original_record']
        for field in ('node_id', 'parent_id'):
            identity = raw.get(field)
            if not identity or not identity.startswith('ord-'):
                continue
            key = record['instrument_id'], int(identity[4:])
            if key in by_order:
                expected[key].append((record, field))
    for line, order in enumerate(orders, 1):
        key = order['instrument_id'], order['order_id']
        assert order['order_link_line'] == line
        checks = {(r['record_sha256'], field): r for r, field in expected[key]}
        links = order['all_original_lineage_associations']
        assert len(links) == len(expected[key])
        for link in links:
            original = checks[(link['record_sha256'], link['matching_identity_field'])]
            assert (OUT / link['original_file']).is_file()
            for k in ('known_by_ns', 'input_cursor', 'instrument_id'):
                assert type(link[k]) is int and link[k] == original[k]
            raw = original['original_record']
            for k in ('node_id', 'parent_id', 'entered_recv_ns', 'exited_recv_ns'):
                assert link[k] == raw.get(k)
            for out, original_key in (('source_status', 'status'), ('source_side_orientation', 'side_orientation'),
                                      ('source_role', 'role'), ('source_transition_type', 'transition_type')):
                assert link[out] == raw.get(original_key)

    removals = list(rows(TRADE / 'each-removal-with-original-order-evidence.jsonl.gz'))
    roles = json.loads((TRADE / 'quote-order-gapfill-v1/role-reconciliation-v1/all-32-trade-role-reconciliation.json').read_text())
    assert [r['trade_ordinal'] for r in roles] == list(range(118, 150))
    bounded_ids = {r['trade_ordinal']: (int(r['original_trade']['instrument_id']), r['original_T']['order_id']) for r in roles}
    by_emission = collections.defaultdict(list)
    wanted = set(bounded_ids.values())
    for line, removal in enumerate(removals, 1):
        r = removal['original_removal_record']
        wanted.add((r['instrument_id'], r['original_record']['order_id']))
        by_emission[(r['instrument_id'], r['input_cursor'])].append((line, removal))
    assert set(by_order) == wanted
    case_cursors = collections.defaultdict(list)
    for c in contexts:
        case_cursors[(c['instrument_id'], c['pre_input_cursor'])].append(c['context_line'])
    timeline = list(rows(OUT / 'every-trade-completed-run-and-lineage-links.jsonl.gz'))
    assert len(timeline) == len(originals) == 30739
    counts = collections.Counter()
    for i, (new, old) in enumerate(zip(timeline, originals)):
        assert new['trade_ordinal'] == i and new['original_trade'] == old
        assert new['semantic_coverage'] == 'NOT_PASSED'
        for k, value in new['exact_clocks'].items():
            assert type(value) is int and value == int(old[k])
        instrument, cursor = int(old['instrument_id']), int(old['group_close_input_cursor'])
        prior = [c['context_line'] for c in contexts if c['instrument_id'] == instrument and c['start_receive_ns'] <= int(old['receive_ns'])]
        later = [c['context_line'] for c in contexts if c['instrument_id'] == instrument and c['start_receive_ns'] > int(old['receive_ns'])]
        actual = new['model_context_navigation']
        assert actual['nearest_prior_or_equal_start_line'] == (prior[-1] if prior else None)
        assert actual['nearest_later_start_line'] == (later[0] if later else None)
        assert actual['all_prior_or_equal_start_line_range'] == ([prior[0], prior[-1]] if prior else None)
        assert actual['all_later_start_line_range'] == ([later[0], later[-1]] if later else None)
        assert new['exact_shared_model_pre_group_lines'] == case_cursors.get((instrument, cursor), [])
        expected_removals = by_emission.get((instrument, cursor), [])
        assert [r['line_number'] for r in new['same_emission_removal_refs']] == [line for line, _ in expected_removals]
        expected_keys = {(instrument, r['original_removal_record']['original_record']['order_id']) for _, r in expected_removals}
        if i in bounded_ids:
            expected_keys.add(bounded_ids[i])
            assert new['bounded_original_T_identity']['order_id'] == bounded_ids[i][1]
            assert new['bounded_original_T_identity']['array_ordinal'] == i - 118
        else:
            assert new['bounded_original_T_identity'] is None
        assert {(instrument, r['order_id']) for r in new['order_lineage_refs']} == expected_keys
        for ref, (_, removal) in zip(new['same_emission_removal_refs'], expected_removals):
            assert ref['interpretation'] == removal['source_bound_interpretation']
            assert (OUT / ref['file']).is_file()
        for ref in new['order_lineage_refs']:
            record = orders[ref['line_number'] - 1]
            assert ref['order_id'] == record['order_id'] and record['instrument_id'] == instrument
            assert ref['associations_known_after_trade_group'] == sum(
                l['known_by_ns'] > int(old['available_ns']) for l in record['all_original_lineage_associations'])
            assert ref['associations_at_later_cursor'] == sum(l['input_cursor'] > cursor for l in record['all_original_lineage_associations'])
        counts['trades'] += 1
        counts['trades_with_same_emission_removals'] += bool(expected_removals)
        counts['trades_sharing_original_model_pre_group'] += bool(new['exact_shared_model_pre_group_lines'])
        counts['trades_with_order_lineage_associations'] += any(
            orders[ref['line_number'] - 1]['all_original_lineage_associations'] for ref in new['order_lineage_refs'])
        counts['trades_with_later_known_lineage_associations'] += any(
            ref['associations_known_after_trade_group'] for ref in new['order_lineage_refs'])
    for i in (119, 134):
        assert timeline[i]['quantity_gap_status'] == 'UNRESOLVED'
        identity = timeline[i]['bounded_original_T_identity']['order_id']
        assert not by_order[(150611, identity)]['all_original_lineage_associations']

    originals_by_sha = {r['record_sha256']: r for r in rows(TRADE / 'source-absorption.jsonl.gz')}
    tapes = collections.defaultdict(list)
    for i, trade in enumerate(originals):
        tapes[(int(trade['instrument_id']), int(trade['group_close_input_cursor']))].append(i)
    compared = list(rows(OUT / 'all-6265-absorption-to-original-tape-links.jsonl.gz'))
    assert len(compared) == len(originals_by_sha) == 6265
    seen = set()
    quantity = collections.Counter()
    for row in compared:
        ref = row['original_absorption_ref']
        sha = ref['record_sha256']
        assert sha not in seen
        seen.add(sha)
        original = originals_by_sha[sha]
        for k in ('known_by_ns', 'input_cursor', 'instrument_id'):
            assert ref[k] == original[k] and type(ref[k]) is int
        raw = original['original_record']
        for output, key in (('source_traded_quantity', 'traded_quantity'), ('source_displayed_depletion', 'displayed_depletion'),
                            ('source_withdrawn_quantity', 'withdrawn_quantity'), ('source_side', 'side'), ('source_disposition', 'disposition')):
            assert row[output] == raw[key]
        ordinals = tapes.get((ref['instrument_id'], ref['input_cursor']), [])
        assert row['original_trade_ordinals'] == ordinals
        total = sum(int(originals[i]['size']) for i in ordinals) if ordinals else None
        assert row['original_tape_quantity'] == total
        assert row['equality'] == (None if total is None else total == raw['traded_quantity'])
        quantity['absorption_records'] += 1
        quantity['with_original_tape_prints'] += bool(ordinals)
        quantity['source_traded_quantity_differs_from_unique_tape_sum'] += row['equality'] is False
    receipt = json.loads((OUT / 'sqlite-query-receipt.json').read_text())
    assert dict(counts) == receipt['counts']
    assert dict(quantity) == receipt['quantity_definition_checks']
    index = json.loads((OUT / 'run-evidence-index.json').read_text())
    paths = [index['controlling_master'], index['identified_run']['run_handoff'], index['identified_run']['completion_receipt']]
    paths += [p for item in index['evidence'] for p in item['paths']]
    for path in paths:
        assert (OUT / path).exists(), path
    docs = [OUT / 'README.md', TRADE / 'README.md', TRADE / 'trade-lifecycle-handoff-20261023.md']
    link_count = 0
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                resolved = (doc.parent / target.split('#')[0]).resolve()
                # This receipt is written only after every other check has passed.
                if resolved != (OUT / 'verification.json').resolve():
                    assert resolved.exists(), (doc, target)
                link_count += 1
    assert not list(OUT.glob('*.sqlite'))
    verification = dict(status='PASSED_SUPPLEMENTARY_POINTER_AND_PRESERVATION_CHECKS',
                        all_original_trades_and_exact_integer_clocks_verified=30739,
                        all_original_model_contexts_verified=749, nested_original_forecast_rows=109674,
                        all_original_absorption_refs_and_individual_tape_members_verified=6265,
                        all_queried_order_identities_retained=7939, matched_original_lineage_associations_verified=4,
                        all_temporal_context_ranges_verified=True, no_new_per_trade_predictions=True,
                        evidence_paths_verified=len(paths), local_document_links_verified=link_count,
                        quantity_gaps_119_134='UNRESOLVED', semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (OUT / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')
    assert (OUT / 'verification.json').is_file()
    print(json.dumps(verification), flush=True)


if __name__ == '__main__':
    main()
