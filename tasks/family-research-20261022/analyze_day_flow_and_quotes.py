"""Whole-day navigation of saved flow and quote evidence; no imputation or fitting."""
import bisect
import collections
import csv
import gzip
import json

from analyze_saved_trade_quotes import exact_projected_quote, quote_position
from query_saved_run_connections import BASE, TRADE, rows

OUT = TRADE / 'day-wide-mechanisms-v1'
NS = 1000000000


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(name, records):
    with (OUT / name).open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
            for record in records:
                handle.write((json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n').encode())


def csv_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', newline='') as handle:
        yield from csv.DictReader(handle)


def second_bounds(second, window):
    return (second - window + 1) * NS, (second + 1) * NS


def publication_range(stamps, previous_ns, current_ns):
    if previous_ns is None:
        return None
    lower = bisect.bisect_right(stamps, previous_ns)
    upper = bisect.bisect_right(stamps, current_ns)
    return None if lower == upper else [lower + 1, upper]


def flow_flags(record, tape_count):
    flags = []
    if record['trades'] != tape_count:
        flags.append('SOURCE_FRESH_COUNT_MISMATCH')
    if not tape_count and record['window_signed_flow'] != 0:
        flags.append('NONZERO_ROLL_WITHOUT_NEW_TAPE')
    if tape_count and record['window_signed_flow'] == 0:
        flags.append('FRESH_TAPE_WITH_ZERO_ROLL')
    if record['net_volume'] * record['window_signed_flow'] < 0:
        flags.append('FRESH_NET_OPPOSES_ROLL')
    return flags


def quote_consensus(views):
    if not views:
        status = 'NOT_MATERIALIZED'
    elif any(not v['clock_match'] or v['bid_raw'] is None or v['ask_raw'] is None for v in views):
        status = 'UNRESOLVED_SAVED_VIEW_RETAINED'
    elif len({(v['bid_raw'], v['ask_raw']) for v in views}) != 1:
        status = 'CONFLICTING_SAVED_QUOTES'
    elif views[0]['bid_raw'] <= 0 or views[0]['bid_raw'] >= views[0]['ask_raw']:
        status = 'LOCKED_CROSSED_OR_INVALID_SAVED_QUOTE'
    else:
        return dict(status='CONSISTENT_EXACT_SAVED_QUOTES', bid_raw=views[0]['bid_raw'], ask_raw=views[0]['ask_raw'])
    return dict(status=status, bid_raw=None, ask_raw=None)


def collect_quotes():
    views, unplaced = collections.defaultdict(list), []

    def add(ordinal, bid, ask, payload, ref, known=None, cursor=None, raw_prices=False):
        item = dict(original_ref=ref, original_quote_payload=payload,
                    reported_known_by_ns=known, reported_input_cursor=cursor,
                    bid_raw=bid if raw_prices else exact_projected_quote([str(bid)])['raw_integer'],
                    ask_raw=ask if raw_prices else exact_projected_quote([str(ask)])['raw_integer'])
        if ordinal is None:
            unplaced.append(item)
        else:
            views[int(ordinal)].append(item)

    for line, parent in enumerate(rows(BASE / 'enriched-v2/quote_endpoint_receipts.jsonl.gz'), 1):
        for field in ('from_quote', 'to_quote'):
            quote = parent.get(field)
            q = quote or {}
            add(q.get('source_ordinal'), q.get('best_bid'), q.get('best_ask'), quote,
                dict(file='../../enriched-v2/quote_endpoint_receipts.jsonl.gz', line_number=line, field=field),
                q.get('known_by_ns'), q.get('input_cursor'))
    for line, q in enumerate(csv_rows(BASE / 'timestamped-mbo-window-v1/consecutive_quote_books.csv.gz'), 1):
        add(int(q['source_ordinal']), q['best_bid'], q['best_ask'], q,
            dict(file='../../timestamped-mbo-window-v1/consecutive_quote_books.csv.gz', csv_data_row=line),
            int(q['known_by_ns']), int(q['input_cursor']))
    for line, q in enumerate(rows(TRADE / 'chronological-lifecycle-v1/all-saved-selected-quote-views.jsonl.gz'), 1):
        add(q['source_ordinal'], q['bid']['raw_integer'], q['ask']['raw_integer'], q,
            dict(file='../chronological-lifecycle-v1/all-saved-selected-quote-views.jsonl.gz', line_number=line), raw_prices=True)
    path = TRADE / 'quote-order-gapfill-v1/each-trade-exact-quote-order-analysis.json'
    for index, q in enumerate(json.loads(path.read_text())):
        for side in ('before', 'after'):
            original = q[f'exact_{side}_group_ref']
            book = q[f'{side}_book']
            add(original['source_ordinal'], book['best_bid'], book['best_ask'], book,
                dict(file='../quote-order-gapfill-v1/each-trade-exact-quote-order-analysis.json', array_ordinal=index, field=f'{side}_book'),
                original['known_by_ns'], original['input_cursor'])
    return views, unplaced


def main():
    OUT.mkdir(exist_ok=True)
    master = json.loads((BASE / 'completed-run-source-list.json').read_text())
    assert len(master['original_99_plane_records']) == 99
    trades = list(csv_rows(BASE / 'price-curve-timestamps.csv'))
    nav_trades = list(csv_rows(TRADE / 'all-30739-trades.csv.gz'))
    assert len(trades) == len(nav_trades) == 30739
    assert len({t['instrument_id'] for t in trades}) == 1
    instrument = int(trades[0]['instrument_id'])
    receive = [int(t['receive_ns']) for t in trades]
    assert receive == sorted(receive)
    bins = collections.defaultdict(list)
    for i, t in enumerate(trades):
        bins[int(t['receive_ns']) // NS].append(i)

    flow_rows, flow_by_second = [], collections.defaultdict(list)
    flow_counts = collections.Counter()
    flag_examples = collections.defaultdict(list)
    for line, wrapper in enumerate(rows(TRADE / 'source-flow_substrate.jsonl.gz'), 1):
        source = wrapper['original_record']
        assert wrapper['instrument_id'] == instrument
        second = source['second']
        lo, hi = second_bounds(second, source['window_seconds'])
        lower, upper = bisect.bisect_left(receive, lo), bisect.bisect_left(receive, hi)
        fresh = bins.get(second, [])
        flags = flow_flags(source, len(fresh))
        if source['binning_clock'] != 'ts_recv':
            flags.append('UNRESOLVED_BINNING_CLOCK')
        if wrapper['known_by_ns'] < hi:
            flags.append('SOURCE_EMISSION_BEFORE_SECOND_END')
        if lower == upper and source['window_signed_flow'] != 0:
            flags.append('NONZERO_ROLL_WITHOUT_ANY_WINDOW_TAPE')
        for flag in flags:
            flow_counts[flag] += 1
            flag_examples[flag].append(line)
        flow_counts['records'] += 1
        row = dict(original_flow_record=wrapper, original_ref=dict(file='../source-flow_substrate.jsonl.gz', line_number=line),
                   fresh_second_bounds_ns=[second * NS, (second + 1) * NS],
                   all_original_fresh_tape_ordinals=fresh,
                   original_fresh_tape_size=sum(int(trades[i]['size']) for i in fresh),
                   rolling_window_bounds_ns=[lo, hi],
                   all_original_window_tape_ordinal_range=None if lower == upper else [lower, upper - 1],
                   second_end_to_emission_ns=wrapper['known_by_ns'] - hi, interpretation_flags=flags,
                   interpretation='Fresh per-second midpoint-classified source flow, rolling signed lots and normalized roll20 are distinct. Tape side is not reconstructed here; no fresh flow is inferred from repeated rolling readings.')
        flow_rows.append(row)
        flow_by_second[second].append(line)
    assert len(flow_rows) == 8088
    write_rows('all-8088-original-flow-seconds-with-tape.jsonl.gz', flow_rows)
    print('Flow checked against all original tape; building saved-quote union.', flush=True)

    views, unplaced = collect_quotes()
    wanted = set(views)
    wanted.update(int(t[k]) for t in nav_trades for k in ('pre_group_source_ordinal', 'emission_group_source_ordinal') if t[k])
    groups = {}
    for group in csv_rows(BASE / 'descriptive-v1/retained_group_sequence.csv.gz'):
        ordinal = int(group['source_ordinal'])
        if ordinal in wanted:
            groups[ordinal] = group
    quote_rows, quote_lookup = [], {}
    quote_counts = collections.Counter()
    for ordinal, original_views in sorted(views.items()):
        group = groups.get(ordinal)
        for v in original_views:
            v['clock_match'] = bool(group) and all(v[field] is None or v[field] == int(group[column]) for field, column in (
                ('reported_known_by_ns', 'known_by_ns'), ('reported_input_cursor', 'input_cursor')))
        result = quote_consensus(original_views)
        row = dict(source_ordinal=ordinal, original_group=group, all_original_views=original_views,
                   consensus=result, interpretation='All saved source views retained separately. Consensus requires exact integral scalar conversion, matching supplied clocks and no conflicting or unresolved view; no source is selected by outcome.')
        quote_rows.append(row)
        quote_lookup[ordinal] = (len(quote_rows), row)
        quote_counts[result['status']] += 1
    write_rows('all-saved-quote-source-views.jsonl.gz', quote_rows)
    write_rows('all-unplaced-quote-endpoints.jsonl.gz', unplaced)

    history = json.loads((BASE / 'external-classroom-audit-v1/original_series_known_values.json').read_text())
    assert len(history['series']) == 48
    publications = collections.defaultdict(list)
    history_rows = 0
    for series_index, series in enumerate(history['series']):
        history_rows += len(series['known'])
        for known_index, value in enumerate(series['known']):
            published = value['published_ns']
            assert type(published) is int
            if receive[0] <= published <= receive[-1]:
                publications[published].append(dict(
                    source_series_index=series_index, original_known_index=known_index,
                    series_name=series['name'], original_table=series['table'],
                    original_source_ordinal=value.get('source_ordinal'),
                    original_state=value.get('state'), original_reason=value.get('reason'),
                    original_value=value.get('value')))
    assert history_rows == 211055
    publication_rows = []
    for line, (stamp, observations) in enumerate(sorted(publications.items()), 1):
        shared = collections.defaultdict(list)
        for i, obs in enumerate(observations):
            shared[(obs['original_table'], obs['original_source_ordinal'])].append(i)
        publication_rows.append(dict(
            publication_line=line, original_declared_publication_ns=stamp,
            all_original_observation_refs=observations,
            original_full_nested_history='../../external-classroom-audit-v1/original_series_known_values.json',
            same_table_and_source_ordinal_groups=[dict(table=k[0], source_ordinal=k[1], observation_array_ordinals=members)
                                                 for k, members in shared.items()],
            contains_non_curve_traded_table=any(o['original_table'] != 'curve.traded_shape' for o in observations),
            interpretation='Declared publication clocks and shared source coordinates only, not verified live arrivals, independent signals or a causal release. Different target days/models, source states and values remain separate.'))
    write_rows('all-declared-external-publications-during-tape.jsonl.gz', publication_rows)
    publication_stamps = sorted(publications)

    def lookup(ordinal):
        if ordinal == '' or ordinal is None:
            return None, dict(status='NOT_MATERIALIZED', bid_raw=None, ask_raw=None)
        found = quote_lookup.get(int(ordinal))
        if not found:
            return None, dict(status='NOT_MATERIALIZED', bid_raw=None, ask_raw=None)
        return dict(file='all-saved-quote-source-views.jsonl.gz', line_number=found[0]), found[1]['consensus']

    counts = collections.Counter()
    examples = collections.defaultdict(list)
    comparison_rows = []
    for i, (trade, nav) in enumerate(zip(trades, nav_trades)):
        assert trade == {k: nav[k] for k in trade}
        prior_ref, before = lookup(nav['pre_group_source_ordinal'])
        close_ref, after = lookup(nav['emission_group_source_ordinal'])
        bid, ask, cbid, cask = before['bid_raw'], before['ask_raw'], after['bid_raw'], after['ask_raw']
        paired = None not in (bid, ask, cbid, cask)
        print_step = None if i == 0 else int(trade['price_raw']) - int(trades[i - 1]['price_raw'])
        delta2 = cbid + cask - bid - ask if paired else None
        flags = []
        if paired:
            counts['paired_exact_uncrossed_quotes'] += 1
            if (bid, ask) == (cbid, cask) and print_step not in (None, 0):
                flags.append('PRINT_CHANGE_WITH_UNCHANGED_GROUP_QUOTES')
            if print_step is not None and print_step * delta2 < 0:
                flags.append('PRINT_STEP_OPPOSES_GROUP_MIDPOINT_CHANGE')
        same_second = flow_by_second.get(int(trade['receive_ns']) // NS, [])
        counts['trades_with_saved_own_second_flow'] += bool(same_second)
        publication_lines = publication_range(publication_stamps, receive[i - 1] if i else None, receive[i])
        counts['trades_with_declared_publication_since_previous_trade'] += publication_lines is not None
        counts['trades_with_declared_non_curve_traded_publication_since_previous_trade'] += bool(publication_lines and any(
            publication_rows[line - 1]['contains_non_curve_traded_table'] for line in range(publication_lines[0], publication_lines[1] + 1)))
        for flag in flags:
            counts[flag] += 1
            examples[flag].append(i)
        comparison_rows.append(dict(
            trade_ordinal=i, original_trade=trade,
            exact_clocks={k: int(trade[k]) for k in ('event_ns', 'receive_ns', 'available_ns', 'trade_input_cursor', 'group_close_input_cursor', 'trade_journal_ordinal')},
            strict_prior_group_ordinal=None if not nav['pre_group_source_ordinal'] else int(nav['pre_group_source_ordinal']),
            emission_group_ordinal=int(nav['emission_group_source_ordinal']), original_prior_quote_ref=prior_ref,
            original_emission_quote_ref=close_ref, prior_quote_status=before['status'], emission_quote_status=after['status'],
            prior_bid_raw=bid, prior_ask_raw=ask, emission_bid_raw=cbid, emission_ask_raw=cask,
            prior_quote_position=quote_position(int(trade['price_raw']), bid, ask), previous_print_step_raw=print_step,
            group_twice_midpoint_change_raw=delta2, interpretation_flags=flags,
            original_own_second_flow_refs=[dict(file='all-8088-original-flow-seconds-with-tape.jsonl.gz', line_number=line,
                known_by_ns=flow_rows[line - 1]['original_flow_record']['known_by_ns'],
                input_cursor=flow_rows[line - 1]['original_flow_record']['input_cursor']) for line in same_second],
            original_declared_publication_lines_since_previous_trade=publication_lines,
            publication_index='all-declared-external-publications-during-tape.jsonl.gz',
            original_all_48_series_and_entire_history_ref=dict(file='../every-trade-original-external-links.jsonl.gz', line_number=i + 1),
            publication_rule='Left-open/right-closed interval between neighboring receive clocks; no prior boundary for trade zero. All earlier/later history retained via original full-history links; no old-valid substitution or causal assignment.',
            other_original_context='Link by this trade ordinal to ../completed-run-connections-v1/every-trade-completed-run-and-lineage-links.jsonl.gz and the original external/second-set evidence. Later evidence remains eligible.',
            limits='Last completed group versus emission group; intragroup quotes and action causes may differ. Same-second flow usually emits later. No invented aggressor, independent-event claim or exhaustion classification.',
            semantic_coverage='NOT_PASSED'))
    write_rows('every-trade-flow-and-expanded-quote-comparison.jsonl.gz', comparison_rows)

    # Runs break at every unobserved/invalid group, even if sparse endpoints agree.
    runs = []
    for row in quote_rows:
        c = row['consensus']
        if c['status'] != 'CONSISTENT_EXACT_SAVED_QUOTES':
            continue
        ordinal = row['source_ordinal']
        pair = [c['bid_raw'], c['ask_raw']]
        if runs and ordinal == runs[-1]['last_group_ordinal'] + 1 and pair == runs[-1]['bid_ask_raw']:
            runs[-1]['last_group_ordinal'] = ordinal
        else:
            runs.append(dict(run_ordinal=len(runs), first_group_ordinal=ordinal, last_group_ordinal=ordinal, bid_ask_raw=pair))
    trade_by_group = collections.defaultdict(list)
    for r in comparison_rows:
        trade_by_group[r['emission_group_ordinal']].append(r['trade_ordinal'])
    run_counts = collections.Counter()
    for run in runs:
        members = [i for ordinal in range(run['first_group_ordinal'], run['last_group_ordinal'] + 1) for i in trade_by_group.get(ordinal, [])]
        internal_steps = [int(trades[b]['price_raw']) - int(trades[a]['price_raw']) for a, b in zip(members, members[1:])]
        run.update(all_original_trade_ordinals=members, complete_group_count=run['last_group_ordinal'] - run['first_group_ordinal'] + 1,
                   first_known_by_ns=int(groups[run['first_group_ordinal']]['known_by_ns']),
                   last_known_by_ns=int(groups[run['last_group_ordinal']]['known_by_ns']),
                   contains_both_rising_and_falling_prints=any(s > 0 for s in internal_steps) and any(s < 0 for s in internal_steps),
                   scope='Unchanged consecutive completed-group quotes only; no statement of unchanged intragroup quotes or a surviving order. All individual prints retained.')
        run_counts['runs'] += 1
        run_counts['runs_with_trades'] += bool(members)
        run_counts['runs_with_both_rising_and_falling_prints'] += run['contains_both_rising_and_falling_prints']
    write_rows('all-consecutive-unchanged-group-quote-runs.jsonl.gz', runs)
    save('analysis-receipt.json', dict(
        source_master='../../completed-run-source-list.json', original_master_unchanged=True, source_roles=99,
        trades=30739, dropped_trades=0, flow_counts=dict(flow_counts), unique_saved_flow_seconds=len(flow_by_second),
        flow_flag_original_line_numbers=dict(flag_examples), quote_counts=dict(quote_counts),
        total_quote_source_views=sum(len(v) for v in views.values()), unplaced_quote_endpoints=len(unplaced),
        external_series=48, original_full_external_history_rows=history_rows,
        distinct_declared_publication_clocks_during_tape=len(publication_rows),
        original_external_known_records_during_tape=sum(len(r['all_original_observation_refs']) for r in publication_rows),
        original_external_tables_during_tape=sorted({o['original_table'] for r in publication_rows for o in r['all_original_observation_refs']}),
        quote_source_ordinals=len(quote_rows), trade_comparison_counts=dict(counts),
        all_flagged_trade_ordinals=dict(examples), unchanged_quote_run_counts=dict(run_counts),
        paired_group_counts={flag: len({comparison_rows[i]['original_trade']['group_close_input_cursor'] for i in members}) for flag, members in examples.items()},
        evidence_policy='Original nested sources retained unchanged; separate views and counterexamples retained; counts describe coverage, not averaged signals.',
        completed_run_findings_used=['distinguish transaction paths from quote endpoints', 'history and conditional book use do not establish universal direction', 'preserve output failures and model disagreements'],
        reference_definitions=['../../full-context-audit/scripts/source_reference/native_roll20.py', '../../full-context-audit/scripts/source_reference/native_replay_driver.py'],
        source_definition_limit='Recovered reference source is not certified byte-identical to runtime db96f24f; native source-side and midpoint-inferred flow remain separate.',
        raw_market_journal_reads=0, aws_operations=0, refits=0, averaging=False,
        semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED'))
    print(json.dumps(dict(flow=dict(flow_counts), quotes=dict(quote_counts), trades=dict(counts), runs=dict(run_counts))), flush=True)


if __name__ == '__main__':
    main()
