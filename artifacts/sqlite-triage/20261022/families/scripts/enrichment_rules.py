"""Explicit source-measurement rules. IDs, clocks and outcomes stay provenance."""
import math

COUNTS = set('''gap_count run_count counterparts_considered nearest_candidate_distance
depth_concentration_after depth_migration level_birth_count level_death_count
occupied_levels_after occupied_levels_before total_depth_after total_depth_before
depth_at_open displayed_depletion member_count opposite_side_retreat_quantity
order_id_turnover order_ids_at_close order_ids_at_open order_ids_persisting
same_side_replacement_quantity surviving_depth traded_quantity withdrawn_quantity
depth_after depth_before neighbourhood_ticks order_count_delta quantity episode_count
modify_count own_fill_count own_fill_size priority_loss_count ahead_increase_violations
cancels_ahead fills_ahead final_orders_ahead final_volume_ahead identity_violations
initial_orders_ahead initial_volume_ahead queue_movement residual_negative_violations
length refill_quantity removal_quantity refill_count removal_count trade_count
initial_size final_size remaining_size size_at_open size_at_close size volume
replacement_quantity depletion_quantity replenished_quantity cancelled_quantity
at_mid_trades buy_trades buy_volume net_volume no_quote_trades roll20_value rows
sell_trades sell_volume trades unusable_trades window_seconds window_signed_flow
neighborhood_arrival_quantity neighborhood_arrival_ratio neighboring_price_refill_quantity
new_id_add_count new_id_add_quantity overshoot_quantity peak_restored_quantity
refill_attributions removed_order_count removed_quantity same_id_modify_count
same_id_modify_quantity same_price_refill_quantity shared_with_episode_count'''.split())
DURATIONS = {'gap_ns', 'duration_ns', 'elapsed_ns', 'lifetime_ns', 'time_to_refill_ns',
             'time_to_restoration_ns', 'touch_restoration_ns', 'horizon_ns'}
RAW_PRICES = {'price_raw', 'price_at_close_raw', 'price_at_open_raw',
              'price_response_raw', 'touch_price_after', 'touch_price_before', 'touch_price_at_open', 'tick_raw'}


def eligible(known, cursor, instrument, cutoff, cap, target_instrument):
    return known <= cutoff and cursor <= cap and instrument == target_instrument


def measurement(key, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if key in COUNTS:
        return key, float(value)
    if key in DURATIONS:
        return key[:-3] + '_s', value / 1e9
    if key in RAW_PRICES:
        return key.removesuffix('_raw'), value / 1e9
    return None


def flatten(obj, prefix=''):
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f'{prefix}.{key}' if prefix else key
            if isinstance(value, (dict, list)):
                if key != 'frankie_emission':
                    yield from flatten(value, name)
            else:
                m = measurement(key, value)
                if m:
                    yield (f'{prefix}.{m[0]}' if prefix else m[0]), m[1]
    elif isinstance(obj, list):
        for value in obj:
            yield from flatten(value, prefix + '[]')
