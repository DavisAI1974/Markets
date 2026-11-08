# ROOT ledger headings

These are all 324 scalar field paths and 23 top-level headings found in the 1,667 retained October 18 ROOT frames. Array positions are written as `[]`. The fitted extraction has a separate [full column registry](../../../../../artifacts/sqlite-triage/20261022/families/joint-inputs-v4/root_full_feature_registry.csv).

Top-level headings in source order

`ts_recv_ns`, `ts_event_ns`, `best_bid`, `best_ask`, `mid`, `depth_imbalance_n`, `spread`, `depth_imbalance_full`, `bid_depth_full`, `ask_depth_full`, `bid_order_count_full`, `ask_order_count_full`, `bid_price_level_count_full`, `ask_price_level_count_full`, `transition`, `book`, `activity`, `integrity`, `native_frame`, `observation`, `input_records`, `input_record_indices`, `input_cursor`

The review role below identifies how to read the field. Derived and unknown fields still need a calculation and availability check. `No exclusion` means the old search filter returned no reason to block the field. It is not evidence the field was calculated or is eligible.

| Field path | Stored type | Review role | Old search filter |
| --- | --- | --- | --- |
| `activity.1.action_count.A` | int | Review definition and units | No exclusion |
| `activity.1.action_count.C` | int | Review definition and units | No exclusion |
| `activity.1.action_count.F` | int | Review definition and units | No exclusion |
| `activity.1.action_count.M` | int | Review definition and units | No exclusion |
| `activity.1.action_count.N` | int | Review definition and units | No exclusion |
| `activity.1.action_count.T` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.A` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.C` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.F` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.M` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.N` | int | Review definition and units | No exclusion |
| `activity.1.action_qty.T` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.A_A` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.A_B` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.C_A` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.C_B` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.F_A` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.F_B` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.F_N` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.M_A` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.M_B` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.N_N` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.T_A` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.T_B` | int | Review definition and units | No exclusion |
| `activity.1.action_side_qty.T_N` | int | Review definition and units | No exclusion |
| `activity.1.add_cancel_churn` | float64, null | Review definition and units | No exclusion |
| `activity.1.event_count` | int | Review definition and units | No exclusion |
| `activity.1.missing_reference_count` | int | Source quality | No exclusion |
| `activity.1.priority_lost_modify_count` | int | Review definition and units | No exclusion |
| `activity.1.top_level_add_qty_derived` | int | Review definition and units | No exclusion |
| `activity.1.top_level_cancel_qty_derived` | int | Review definition and units | No exclusion |
| `activity.1.trade_aggressor_imbalance` | float64, null | Review definition and units | No exclusion |
| `activity.1.trade_buy_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.1.trade_sell_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.20.action_count.A` | int | Review definition and units | No exclusion |
| `activity.20.action_count.C` | int | Review definition and units | No exclusion |
| `activity.20.action_count.F` | int | Review definition and units | No exclusion |
| `activity.20.action_count.M` | int | Review definition and units | No exclusion |
| `activity.20.action_count.N` | int | Review definition and units | No exclusion |
| `activity.20.action_count.T` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.A` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.C` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.F` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.M` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.N` | int | Review definition and units | No exclusion |
| `activity.20.action_qty.T` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.A_A` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.A_B` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.C_A` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.C_B` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.F_A` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.F_B` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.F_N` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.M_A` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.M_B` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.N_N` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.T_A` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.T_B` | int | Review definition and units | No exclusion |
| `activity.20.action_side_qty.T_N` | int | Review definition and units | No exclusion |
| `activity.20.add_cancel_churn` | float64 | Review definition and units | No exclusion |
| `activity.20.event_count` | int | Review definition and units | No exclusion |
| `activity.20.missing_reference_count` | int | Source quality | No exclusion |
| `activity.20.priority_lost_modify_count` | int | Review definition and units | No exclusion |
| `activity.20.top_level_add_qty_derived` | int | Review definition and units | No exclusion |
| `activity.20.top_level_cancel_qty_derived` | int | Review definition and units | No exclusion |
| `activity.20.trade_aggressor_imbalance` | float64, null | Review definition and units | No exclusion |
| `activity.20.trade_buy_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.20.trade_sell_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.300.action_count.A` | int | Review definition and units | No exclusion |
| `activity.300.action_count.C` | int | Review definition and units | No exclusion |
| `activity.300.action_count.F` | int | Review definition and units | No exclusion |
| `activity.300.action_count.M` | int | Review definition and units | No exclusion |
| `activity.300.action_count.N` | int | Review definition and units | No exclusion |
| `activity.300.action_count.T` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.A` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.C` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.F` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.M` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.N` | int | Review definition and units | No exclusion |
| `activity.300.action_qty.T` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.A_A` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.A_B` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.C_A` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.C_B` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.F_A` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.F_B` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.F_N` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.M_A` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.M_B` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.N_N` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.T_A` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.T_B` | int | Review definition and units | No exclusion |
| `activity.300.action_side_qty.T_N` | int | Review definition and units | No exclusion |
| `activity.300.add_cancel_churn` | float64 | Review definition and units | No exclusion |
| `activity.300.event_count` | int | Review definition and units | No exclusion |
| `activity.300.missing_reference_count` | int | Source quality | No exclusion |
| `activity.300.priority_lost_modify_count` | int | Review definition and units | No exclusion |
| `activity.300.top_level_add_qty_derived` | int | Review definition and units | No exclusion |
| `activity.300.top_level_cancel_qty_derived` | int | Review definition and units | No exclusion |
| `activity.300.trade_aggressor_imbalance` | float64 | Review definition and units | No exclusion |
| `activity.300.trade_buy_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.300.trade_sell_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.5.action_count.A` | int | Review definition and units | No exclusion |
| `activity.5.action_count.C` | int | Review definition and units | No exclusion |
| `activity.5.action_count.F` | int | Review definition and units | No exclusion |
| `activity.5.action_count.M` | int | Review definition and units | No exclusion |
| `activity.5.action_count.N` | int | Review definition and units | No exclusion |
| `activity.5.action_count.T` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.A` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.C` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.F` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.M` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.N` | int | Review definition and units | No exclusion |
| `activity.5.action_qty.T` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.A_A` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.A_B` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.C_A` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.C_B` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.F_A` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.F_B` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.F_N` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.M_A` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.M_B` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.N_N` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.T_A` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.T_B` | int | Review definition and units | No exclusion |
| `activity.5.action_side_qty.T_N` | int | Review definition and units | No exclusion |
| `activity.5.add_cancel_churn` | float64 | Review definition and units | No exclusion |
| `activity.5.event_count` | int | Review definition and units | No exclusion |
| `activity.5.missing_reference_count` | int | Source quality | No exclusion |
| `activity.5.priority_lost_modify_count` | int | Review definition and units | No exclusion |
| `activity.5.top_level_add_qty_derived` | int | Review definition and units | No exclusion |
| `activity.5.top_level_cancel_qty_derived` | int | Review definition and units | No exclusion |
| `activity.5.trade_aggressor_imbalance` | float64, null | Review definition and units | No exclusion |
| `activity.5.trade_buy_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.5.trade_sell_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.60.action_count.A` | int | Review definition and units | No exclusion |
| `activity.60.action_count.C` | int | Review definition and units | No exclusion |
| `activity.60.action_count.F` | int | Review definition and units | No exclusion |
| `activity.60.action_count.M` | int | Review definition and units | No exclusion |
| `activity.60.action_count.N` | int | Review definition and units | No exclusion |
| `activity.60.action_count.T` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.A` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.C` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.F` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.M` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.N` | int | Review definition and units | No exclusion |
| `activity.60.action_qty.T` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.A_A` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.A_B` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.C_A` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.C_B` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.F_A` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.F_B` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.F_N` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.M_A` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.M_B` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.N_N` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.T_A` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.T_B` | int | Review definition and units | No exclusion |
| `activity.60.action_side_qty.T_N` | int | Review definition and units | No exclusion |
| `activity.60.add_cancel_churn` | float64 | Review definition and units | No exclusion |
| `activity.60.event_count` | int | Review definition and units | No exclusion |
| `activity.60.missing_reference_count` | int | Source quality | No exclusion |
| `activity.60.priority_lost_modify_count` | int | Review definition and units | No exclusion |
| `activity.60.top_level_add_qty_derived` | int | Review definition and units | No exclusion |
| `activity.60.top_level_cancel_qty_derived` | int | Review definition and units | No exclusion |
| `activity.60.trade_aggressor_imbalance` | float64, null | Review definition and units | No exclusion |
| `activity.60.trade_buy_aggressor_qty` | int | Review definition and units | No exclusion |
| `activity.60.trade_sell_aggressor_qty` | int | Review definition and units | No exclusion |
| `ask_depth_full` | int | Market measurement or derived book statistic | No exclusion |
| `ask_order_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `ask_price_level_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `best_ask` | float64 | Market measurement or derived book statistic | No exclusion |
| `best_bid` | float64 | Market measurement or derived book statistic | No exclusion |
| `bid_depth_full` | int | Market measurement or derived book statistic | No exclusion |
| `bid_order_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `bid_price_level_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_depth_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_depth_n` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].front_order_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].front_order_size` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].largest_order_share` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].order_count` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].price` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].queue_age_median_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].queue_age_p90_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels[].side` | str | Action, side, or book definition | No exclusion |
| `book.ask_levels[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].fifo_queue[].order_id` | int | Identity or ordering | context_only |
| `book.ask_levels_full[].fifo_queue[].priority_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].fifo_queue[].priority_recv_ns` | int | Clock or delivery timing | No exclusion |
| `book.ask_levels_full[].fifo_queue[].priority_sequence` | int | Identity or ordering | No exclusion |
| `book.ask_levels_full[].fifo_queue[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].fifo_queue[].volume_ahead` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].front_order_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].front_order_size` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].largest_order_share` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].order_count` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].price` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].queue_age_median_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].queue_age_p90_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.ask_levels_full[].side` | str | Action, side, or book definition | No exclusion |
| `book.ask_levels_full[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_order_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.ask_price_level_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.best_ask` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.best_bid` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_depth_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_depth_n` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].front_order_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].front_order_size` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].largest_order_share` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].order_count` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].price` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].queue_age_median_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].queue_age_p90_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels[].side` | str | Action, side, or book definition | No exclusion |
| `book.bid_levels[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].fifo_queue[].order_id` | int | Identity or ordering | context_only |
| `book.bid_levels_full[].fifo_queue[].priority_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].fifo_queue[].priority_recv_ns` | int | Clock or delivery timing | No exclusion |
| `book.bid_levels_full[].fifo_queue[].priority_sequence` | int | Identity or ordering | No exclusion |
| `book.bid_levels_full[].fifo_queue[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].fifo_queue[].volume_ahead` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].front_order_age_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].front_order_size` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].largest_order_share` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].order_count` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].price` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].queue_age_median_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].queue_age_p90_s` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.bid_levels_full[].side` | str | Action, side, or book definition | No exclusion |
| `book.bid_levels_full[].size` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_order_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.bid_price_level_count_full` | int | Market measurement or derived book statistic | No exclusion |
| `book.depth_imbalance_full` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.depth_imbalance_n` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.mid` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.spread` | float64 | Market measurement or derived book statistic | No exclusion |
| `book.top_n` | int | Encoding, provenance, or control | No exclusion |
| `depth_imbalance_full` | float64 | Market measurement or derived book statistic | No exclusion |
| `depth_imbalance_n` | float64 | Market measurement or derived book statistic | No exclusion |
| `input_cursor` | int | Identity or ordering | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_record_indices[]` | int | Identity or ordering | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].action` | str | Action, side, or book definition | No exclusion |
| `input_records[].channel_id` | int | Identity or ordering | context_only |
| `input_records[].dbn_extraction_hash` | str | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].dbn_length` | int | Encoding, provenance, or control | No exclusion |
| `input_records[].dbn_wire_bytes` | bytes | Encoding, provenance, or control | No exclusion |
| `input_records[].flags` | int | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].instrument_id` | int | Identity or ordering | context_only |
| `input_records[].order_id` | int | Identity or ordering | context_only |
| `input_records[].price` | int | Market measurement or derived book statistic | No exclusion |
| `input_records[].publisher_id` | int | Identity or ordering | context_only |
| `input_records[].rtype` | int | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].sequence` | int | Identity or ordering | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].side` | str | Action, side, or book definition | No exclusion |
| `input_records[].size` | int | Market measurement or derived book statistic | No exclusion |
| `input_records[].ts_event` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].ts_in_delta` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `input_records[].ts_out` | null | Encoding, provenance, or control | No exclusion |
| `input_records[].ts_recv` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `mid` | float64 | Market measurement or derived book statistic | No exclusion |
| `native_frame.adapter_revision` | str | Encoding, provenance, or control | No exclusion |
| `native_frame.causal_availability_clock` | str | Encoding, provenance, or control | No exclusion |
| `native_frame.census_view` | str | Encoding, provenance, or control | No exclusion |
| `native_frame.channel_id` | int | Identity or ordering | context_only |
| `native_frame.event_group_complete_f_last` | bool | Encoding, provenance, or control | No exclusion |
| `native_frame.fifo_priority_reconstructed` | bool | Encoding, provenance, or control | No exclusion |
| `native_frame.instrument_id` | int | Identity or ordering | context_only |
| `native_frame.native_priority_id_exposed` | bool | Encoding, provenance, or control | No exclusion |
| `native_frame.publisher_id` | int | Identity or ordering | context_only |
| `native_frame.raw_actions[].action` | str | Action, side, or book definition | No exclusion |
| `native_frame.raw_actions[].channel_id` | int | Identity or ordering | context_only |
| `native_frame.raw_actions[].flags` | int | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].instrument_id` | int | Identity or ordering | context_only |
| `native_frame.raw_actions[].is_last` | bool | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].is_snapshot` | bool | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].order_id` | int | Identity or ordering | context_only |
| `native_frame.raw_actions[].price` | float64, null | Market measurement or derived book statistic | No exclusion |
| `native_frame.raw_actions[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `native_frame.raw_actions[].publisher_id` | int | Identity or ordering | context_only |
| `native_frame.raw_actions[].raw_symbol` | null | Encoding, provenance, or control | context_only |
| `native_frame.raw_actions[].sequence` | int | Identity or ordering | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].side` | str | Action, side, or book definition | No exclusion |
| `native_frame.raw_actions[].size` | int | Market measurement or derived book statistic | No exclusion |
| `native_frame.raw_actions[].source_dbn_object` | null | Encoding, provenance, or control | No exclusion |
| `native_frame.raw_actions[].source_dbn_sha256` | null | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].ts_event_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].ts_in_delta_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_actions[].ts_recv_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.raw_symbol` | null | Encoding, provenance, or control | context_only |
| `native_frame.schema` | str | Encoding, provenance, or control | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.sequence` | int | Identity or ordering | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.snapshot_bootstrap_only` | bool | Encoding, provenance, or control | No exclusion |
| `native_frame.ts_event_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.ts_in_delta_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `native_frame.ts_recv_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `observation.instrument_id` | int | Identity or ordering | context_only |
| `observation.last_event_ns` | int | Clock or delivery timing | No exclusion |
| `observation.last_recv_ns` | int | Clock or delivery timing | No exclusion |
| `observation.last_sequence` | int | Identity or ordering | No exclusion |
| `observation.levels.A[].order_ids[]` | int | Identity or ordering | context_only |
| `observation.levels.A[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `observation.levels.B[].order_ids[]` | int | Identity or ordering | context_only |
| `observation.levels.B[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `observation.orders[].instrument_id` | int | Identity or ordering | context_only |
| `observation.orders[].last_update_recv_ns` | int | Clock or delivery timing | No exclusion |
| `observation.orders[].order_id` | int | Identity or ordering | context_only |
| `observation.orders[].price_raw` | int | Market measurement or derived book statistic | No exclusion |
| `observation.orders[].priority_recv_ns` | int | Clock or delivery timing | No exclusion |
| `observation.orders[].priority_sequence` | int | Identity or ordering | No exclusion |
| `observation.orders[].side` | str | Action, side, or book definition | No exclusion |
| `observation.orders[].size` | int | Market measurement or derived book statistic | No exclusion |
| `observation.priority_time_semantics` | str | Encoding, provenance, or control | No exclusion |
| `spread` | float64 | Market measurement or derived book statistic | No exclusion |
| `transition` | str | Action, side, or book definition | No exclusion |
| `ts_event_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
| `ts_recv_ns` | int | Clock or delivery timing | record identity, source bookkeeping or encoded bytes are not market quantities |
