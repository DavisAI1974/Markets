"""Check exact signal-close coverage of saved flow and fully emitted dipole paths."""
from collections import Counter, defaultdict
import json
import math

from analyze_day_flow_and_quotes import NS, OUT as FLOW_DIR, TRADE, csv_rows
from replay_early_falling_touch import LEDGER
from replay_local_liquidity import DEST, rows, save_rows, sign

FLOW = 'all-8088-original-flow-seconds-with-tape.jsonl.gz'
DIPOLES = 'supporting-dipole-paths.csv.gz'
RESULT = 'every-early-signal-flow-and-dipole-availability.jsonl.gz'
RECEIPT = 'early-signal-flow-and-dipole-availability-receipt.json'
INSTRUMENT = 150611


def same_close(flow, known_by, cursor):
    record = flow['original_record']
    emission = record['frankie_emission']
    return ((flow['known_by_ns'], flow['input_cursor']) == (known_by, cursor)
            and (emission['ts_recv_ns'], emission['input_cursor'], emission['instrument_id'], emission['phase'])
            == (known_by, cursor, INSTRUMENT, 'GROUP_CLOSE'))


def flow_context(flow):
    source = flow['original_flow_record']['original_record']
    fresh, rolling = source['net_volume'], source['window_signed_flow']
    if (source['status'] != 'RESOLVED' or not math.isfinite(fresh) or not math.isfinite(rolling)
            or source['trades'] != len(flow['all_original_fresh_tape_ordinals'])
            or source['no_quote_trades'] or source['unusable_trades']):
        return None
    return dict(fresh_sign=sign(fresh), rolling_sign=sign(rolling), fresh_net=fresh,
                rolling_signed_lots=rolling, fresh_trade_count=source['trades'],
                original_fresh_tape_ordinals=flow['all_original_fresh_tape_ordinals'],
                rolling_defined=source['roll20_defined'], original_flags=flow['interpretation_flags'])


def main():
    flow_by_second = defaultdict(list)
    for line, row in enumerate(rows(FLOW_DIR / FLOW), 1):
        original = row['original_flow_record']
        if original['instrument_id'] == INSTRUMENT and original['original_record']['source_day'] == '20231018':
            second = original['original_record']['second']
            assert row['fresh_second_bounds_ns'] == [second * NS, (second + 1) * NS]
            flow_by_second[second].append((line, row))

    dipoles_by_close = defaultdict(list)
    for line, row in enumerate(csv_rows(TRADE / DIPOLES), 1):
        if int(row['instrument_id']) == INSTRUMENT:
            key = int(row['known_by_ns']), int(row['input_cursor'])
            dipoles_by_close[key].append(dict(data_line=line, candidate_id=row['candidate_id'],
                                              known_by_ns=key[0], input_cursor=key[1],
                                              record_sha256=row['record_sha256']))

    by_side = defaultdict(Counter)
    outcomes = defaultdict(Counter)
    evidence = []
    for line, paper in enumerate(rows(DEST / LEDGER), 1):
        side = paper['side']
        close = paper['signal']
        stamp, cursor = close['known_by_ns'], close['cursor']
        target_second = stamp // NS - 1
        candidates = flow_by_second[target_second]
        exact = [(i, row) for i, row in candidates if same_close(row['original_flow_record'], stamp, cursor)]
        context = flow_context(exact[0][1]) if len(exact) == 1 else None
        if context is not None:
            status = 'EXACT_USABLE'
        elif len(exact) == 1:
            status = 'EXACT_SOURCE_UNRESOLVED'
        elif len(exact) > 1:
            status = 'MULTIPLE_EXACT_ROWS_RETAINED'
        else:
            status = 'SAVED_BUT_NO_EXACT_CLOSE' if candidates else 'NO_SAVED_PRIOR_SECOND'
        dipoles = dipoles_by_close.get((stamp, cursor), [])
        one_second = paper['outcomes']['1']
        by_side[side][status] += 1
        by_side[side]['WITH_EXACT_CLOSE_DIPOLE' if dipoles else 'WITHOUT_EXACT_CLOSE_DIPOLE'] += 1
        if context is not None:
            counts = outcomes[side, context['fresh_sign'], context['rolling_sign'], bool(context['fresh_trade_count'])]
            counts[one_second['status']] += 1
            if one_second['status'] == 'OBSERVED':
                counts[f"quote_pnl_sign_{sign(one_second['cross_spread_pnl_raw'])}"] += 1
                counts[f"midpoint_sign_{sign(one_second['signed_twice_midpoint_change_raw'])}"] += 1
        evidence.append(dict(paper_signal_line=line, side=side, signal=close, target_receive_second=target_second,
                             flow_availability=status, saved_flow_lines=[i for i, _ in candidates],
                             exact_flow_lines=[i for i, _ in exact], matched_flow=context,
                             exact_close_full_dipole_refs=dipoles, original_paper_one_second=one_second))
    original = json.loads((DEST / 'early-falling-touch-replay-receipt.json').read_text(encoding='utf-8'))
    assert len(evidence) == sum(s['signals'] for s in original['results_by_side'].values())
    assert sum(sum(counts[k] for k in ('OBSERVED', 'ENTRY_CENSORED', 'EXIT_CENSORED'))
               for counts in outcomes.values()) == sum(counts['EXACT_USABLE'] for counts in by_side.values())
    save_rows(DEST / RESULT, evidence)
    receipt = dict(session='20231018', total_signals=len(evidence), instrument_id=INSTRUMENT,
                   availability_by_side=by_side, flow_source_file=FLOW, dipole_source_file=DIPOLES,
                   one_second_matched_cells=[dict(side=side, fresh_sign=fresh, rolling_sign=rolling,
                                                  had_fresh_prints=prints, counts=counts)
                                             for (side, fresh, rolling, prints), counts in sorted(outcomes.items())],
                   research_status='NOT_ENOUGH_INFO', semantic_coverage='NOT_PASSED', mlp_reproducibility='UNRESOLVED')
    (DEST / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
