"""Clarify fill-side roles while retaining every original F/C and quantity discrepancy."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1'
path = OUT / 'each-trade-exact-quote-order-analysis.json'
trades = json.loads(path.read_text())
assert len(trades) == 32
edge_cases = []
side_cases = []
for row in trades:
    if 'original_maker_fill_actions' in row:
        row['original_same_price_fill_actions'] = row.pop('original_maker_fill_actions')
        row['original_fill_order_price_levels_before_trade'] = row.pop('original_maker_price_levels_before_trade')
        row['original_fill_linked_removal_actions'] = row.pop('original_same_id_removal_actions')
    action = row['original_matched_trade_actions'][0]
    opposite = [fill for fill in row['original_same_price_fill_actions']
                if fill['side'] in ['A', 'B'] and fill['side'] != action['side']]
    same = [fill for fill in row['original_same_price_fill_actions'] if fill['side'] == action['side']]
    row['original_opposite_side_fill_actions'] = opposite
    row['original_same_side_fill_actions'] = same
    # These sums reconcile reported source units only; all individual records stay.
    quantity = sum(fill['size'] for fill in opposite)
    reported = int(row['original_trade']['size'])
    all_quantity = sum(fill['size'] for fill in row['original_same_price_fill_actions'])
    if quantity == reported:
        disposition = 'OPPOSITE_SIDE_F_QUANTITY_MATCH_OTHER_RECORDS_RETAINED'
    elif all_quantity == reported and action['side'] == 'N':
        disposition = 'QUANTITY_MATCH_DIRECTION_UNRESOLVED'
    elif all_quantity == reported:
        disposition = 'QUANTITY_MATCH_FILL_ROLE_UNRESOLVED'
    else:
        disposition = 'UNRESOLVED_SOURCE_QUANTITY_DIFFERENCE_RETAINED'
    row['quantity_and_side_reconciliation'] = dict(
        original_T_reported_size=reported,
        original_all_same_price_F_quantity=all_quantity,
        original_opposite_side_F_quantity=quantity,
        original_same_side_F_quantity=sum(fill['size'] for fill in same),
        disposition=disposition,
        limit='T and F are different source actions. Same-side and opposite-side fills are retained separately; do not sum both sides as unique traded volume or infer hidden liquidity.')
    if disposition == 'UNRESOLVED_SOURCE_QUANTITY_DIFFERENCE_RETAINED':
        edge_cases.append(row)
    elif disposition in ['QUANTITY_MATCH_DIRECTION_UNRESOLVED', 'QUANTITY_MATCH_FILL_ROLE_UNRESOLVED']:
        side_cases.append(row)
path.write_text(json.dumps(trades, indent=2) + '\n')
assert [r['trade_ordinal'] for r in edge_cases] == [119, 134]
lookup = {r['trade_ordinal']: r for r in trades}
assert lookup[123]['quantity_and_side_reconciliation']['original_all_same_price_F_quantity'] == 2
assert lookup[123]['quantity_and_side_reconciliation']['original_opposite_side_F_quantity'] == 1
arrivals = []
with gzip.open(OUT / 'all-original-actions-in-episode.jsonl.gz', 'rt') as handle:
    for line in handle:
        row = json.loads(line)
        for action in row['original_raw_actions']:
            if (action['action'] == 'A' and action['side'] == 'A' and action['price_raw'] == 3068000000
                    and 1697582090000000000 <= action['ts_recv_ns'] <= 1697582227000000000):
                arrivals.append(dict(source_ref=row['source_ref'], original_action=action))
assert [r['original_action']['order_id'] for r in arrivals] == [788699917763, 788699917827, 788699917842, 788699917850]
report = dict(
    status='EXACT_QUOTES_AND_ORDER_ACTIONS_CLOSE_ORIGINAL_TAIL_GAPS',
    original_trade_ordinals=[118, 149], exact_trade_contexts=32, all_day_trades_retained=30739,
    full_nested_source_rows_retained=17663, continuous_group_records=1667,
    explicit_new_ask_orders_at_3068_in_tail=arrivals,
    original_quantity_edge_cases=edge_cases,
    original_side_role_edge_cases=side_cases,
    same_side_fill_example=lookup[123],
    interpretation=[
        'Trade127 consumes the one displayed unit at ask3.064; the recorded ask becomes3.066. This supports quote progress from local displayed level depletion for that event, not a rule inferred from full-book imbalance.',
        'Trades139,140,141 consume the same ask order788699906633 across three individual one-unit fills. Trades142 and144 consume order788699906668. Quote ask3.068 persists because other recorded orders remain at that price; four explicit A additions are separately retained. No iceberg inference.',
        'Trade143 has a one-unit bid queue at3.067, explicit opposite-side F on order788699917734 and same-id C cleanup. Its bid retreats3.067 to3.066 and midpoint3.0675 to3.067. The flow reversal is later confirmation of opposition after a quote retreat.',
        'Trade144 fills the front ask order at3.068 without moving either3.066 bid or3.068 ask. The higher print is a buy at an unchanged offer, not evidence of a bullish quote reversal.',
        'Trade146 fills all three displayed one-unit orders at bid3.066; the bid retreats to3.065. Trade147 fills the one-unit bid3.065; the bid retreats to3.064. These are execution-supported quote declines, not just tape alternation or cancellation inferred from snapshots.',
        'Trades148 and149 are subsequent buys. Trade148 removes the one-unit ask3.065 and lifts the ask to3.066; trade149 buys3.067 without a quote change. Preserve this recovery alongside the pullback.',
        'Trade123 carries both same-side and opposite-side F records for one T. The opposite-side F quantity reconciles to its one-unit print; summing both F sides would double-count unique volume.',
        'Trades126 and133 have N-side T/F records; trade128 has same-side T/F records without an opposite-side F in the group. Their reported F quantities match T, but direction/fill roles remain unresolved. Do not force a side from subsequent price movement.',
        'Trade119 has T size1 and no same-price F in the completed group; trade134 has T size12 and opposite-side F quantity2. Their full original records remain. Source meaning/coverage must be resolved before asserting complete displayed execution or hidden replenishment.',
        'Empty integrity_delta and sequence_contiguous=False both occur in these records. Preserve both; neither silently certifies complete feed continuity nor establishes a feed loss by itself.',
    ],
    exhaustion='Observed lack of further offer progress and subsequent bid depletion are descriptive evidence for weakening upward momentum. A validated exhaustion call and the broader cause remain open; append existing exhaustion workflow later.',
    clocks=dict(first_opposed_stage_ns=1697582164000000000, terminal_stage_ns=1697582166000000000,
                full_path_known_by_ns=1697582167857645502,
                bid_retreat_group_known_by_ns=int(lookup[143]['original_trade']['available_ns']),
                first_opposed_stage_after_bid_retreat_ns=1697582164000000000-int(lookup[143]['original_trade']['available_ns']),
                terminal_stage_after_bid_retreat_ns=1697582166000000000-int(lookup[143]['original_trade']['available_ns'])),
    semantic_coverage='NOT_PASSED', mlp_reproducibility='Original unresolved evidence unchanged',
    source_data_policy='Every original field, order, trade, invalid/contrary state and later tail remains retained; no averages, flattened replacement sources or model votes.')
(OUT / 'checked-lifecycle-findings.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status=report['status'], quantity_edge_trade_ordinals=[r['trade_ordinal'] for r in edge_cases],
                      side_role_edge_trade_ordinals=[r['trade_ordinal'] for r in side_cases],
                      same_side_fill_reconciled_trade=123, exact_quote_order_contexts=32,
                      all_day_trades_retained=30739)), flush=True)
