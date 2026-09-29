# Frankie's data wish list (2026-09-29)

Greg asked: of the data points Frankie will have wired in when live, which 10 would he like historical data for
on the next Tue/Wed runs. Frankie has no model seat, so his brain answers: what his 90 plays depend on, counted (`operations/frankie_data_wishlist.py`, brain sha256 bf473faef4d5, live list 1717 served points).

Order: families: plays naming the family or any of its points; points: parsed conditions, all plays, declines. Counts, never a score (D37).

## His top 10 sources (not carried on the experiment days; history is needed)

| # | source family | source | cadence | plays naming it | of them by parsed condition | data points | the points his plays name |
|---|---|---|---|---|---|---|---|
| 1 | weather | NWS/IEM ASOS observations | daily, T+1 | 36 | 5 | 6 | weather (20), weather.gw_hdd (1) |
| 2 | storage | EIA weekly working gas in storage | weekly Thu 10:30 ET | 33 | 0 | 6 | storage (17), storage.weekly_chg (1), storage.vs_5yr (1) |
| 3 | cot | CFTC Commitments of Traders, futures and ICE HH | weekly Fri, suspended in shutdowns | 16 | 8 | 79 | cot.managed_money_net_pctile_1y (4), cot.managed_money_net_chg_wow (3), cot.managed_money_net_pctile_3y (2), cot.managed_money_net (1), cot.ice.pen.managed_money_net_pctile_3y (1), cot.ice.ld1.managed_money_net_pctile_3y (1) |
| 4 | weather_forecast | NWS MOS (GFS/NAM/MEX) via the IEM archive | per model cycle | 13 | 4 | 68 | weather_forecast.run_delta[].d_gw_cdd (5), weather_forecast.forecast_gw_hdd (4), weather_forecast.forecast_run_delta_cdd (3), weather_forecast.run_delta[].d_gw_hdd (1), weather_forecast.horizons[].forecast_gw_hdd (1), weather_forecast.horizons[].forecast_gw_cdd (1) |
| 5 | curve_regime | backwardation/contango label off the forward curve | daily | 9 | 0 | 1 | curve_regime (1) |
| 6 | grid_stack | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | daily, wall = period+2 | 8 | 4 | 88 | grid_stack.bas.US48.wind_mwh (2), grid_stack.bas.US48.est_gas_burn_bcfd (2), grid_stack.bas.US48.solar_mwh (1), grid_stack.bas.US48.gas_share (1), grid_stack.bas.SWPP.wind_mwh (1), grid_stack.bas.SWPP.solar_mwh (1) |
| 7 | squeeze_watch | expiry/OI/positioning conjunction detector | daily | 6 | 1 | 22 | squeeze_watch.sessions_since_prompt_expiry (2), squeeze_watch.calendar_dte_limb_satisfied_live (2), squeeze_watch.unwind_watch (1), squeeze_watch.calendar_front_next_spread (1), squeeze_watch.active (1) |
| 8 | solar | solar geometry + EIA-930 solar generation | daily | 4 | 0 | 86 | - |
| 9 | model_disagreement | cross-model spread between MOS families | per cycle | 2 | 1 | 431 | model_disagreement.stability.NAM[].d_gw_cdd (5), model_disagreement.stability.MEX[].d_gw_cdd (5), model_disagreement.stability.GFS[].d_gw_cdd (5), model_disagreement.summary.max_abs_spread_gw_hdd (1), model_disagreement.stability.NAM[].d_gw_hdd (1), model_disagreement.stability.MEX[].d_gw_hdd (1) |
| 10 | freeze_risk | station-level freeze-off proxy off the same ASOS obs | daily | 2 | 0 | 157 | - |

## The other source families he names

| family | source | plays | data points |
|---|---|---|---|
| stor_surprise | actual minus consensus | 2 | 1 |
| storage_consensus | street consensus for the storage print | 2 | 102 |
| weather_forecast_cycle | MOS cycle timing - which run was available at decision time | 2 | 35 |
| frozen_structure_stale | staleness flag on the one-shot mask | 1 | 4 |
| ngwu_balance | EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending 2026-01-21 | 1 | 83 |
| options_surface | NG options settle IV surface, ON/LNE roots | 1 | 67 |
| steo_vintage | EIA STEO monthly archived workbooks - the complete balance as-of release | 1 | 95 |
| storage_regional | EIA regional + salt/non-salt storage | 1 | 56 |

## Families already carried on the experiment days

| family | source | plays | data points |
|---|---|---|---|
| dow | day of week | 82 | 1 |
| note | free-text annotation, not a quantity | 82 | 1 |
| tape_conditions | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 42 | 92 |
| holiday | CME holiday table - HARDCODED, ends 2027-02-15 (A-14) | 24 | 3 |
| flow_calendar | exchange + index calendar: roll, BCOM, expiry, holidays | 19 | 34 |
| vol_regime | realized vol regime derived from the tape | 12 | 42 |
| firehose_present | whether the MBO firehose reached this day | 10 | 2 |
| contract_structure | CME definitions + forward curve, calendar-front pair | 3 | 52 |

## His top 10 single data points (parsed conditions first)

| data point | source | plays (condition) | plays (all) | declines | play status |
|---|---|---|---|---|---|
| cot.managed_money_net_pctile_1y | CFTC Commitments of Traders, futures and ICE HH | 4 | 4 | 3 | PROPOSED 1, PROVISIONAL 3 |
| weather_forecast.forecast_gw_hdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 4 | 4 | 0 | DEGENERATE 2, PROVISIONAL 2 |
| cot.managed_money_net_chg_wow | CFTC Commitments of Traders, futures and ICE HH | 3 | 3 | 1 | PROVISIONAL 3 |
| cot.managed_money_net_pctile_3y | CFTC Commitments of Traders, futures and ICE HH | 2 | 2 | 0 | PROPOSED 2 |
| grid_stack.bas.US48.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 2 | 2 | 0 | PROVISIONAL 2 |
| squeeze_watch.sessions_since_prompt_expiry | expiry/OI/positioning conjunction detector | 1 | 2 | 4 | DESCRIPTOR 1, PROVISIONAL 1 |
| grid_stack.bas.US48.est_gas_burn_bcfd | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 1 | 2 | 0 | PROPOSED 1, REFUTED 1 |
| cot.ice.ld1.managed_money_net_pctile_1y | CFTC Commitments of Traders, futures and ICE HH | 1 | 1 | 3 | PROVISIONAL 1 |
| model_disagreement.summary.max_abs_spread_gw_hdd | cross-model spread between MOS families | 1 | 1 | 0 | PROVISIONAL 1 |
| weather.gw_hdd | NWS/IEM ASOS observations | 1 | 1 | 0 | PROVISIONAL 1 |

## The rest he names (same order, nothing dropped)

| data point | source | plays (condition) | plays (all) | declines | play status |
|---|---|---|---|---|---|
| model_disagreement.stability.GFS[].d_gw_cdd | cross-model spread between MOS families | 0 | 5 | 0 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 1, REFUTED 1 |
| model_disagreement.stability.MEX[].d_gw_cdd | cross-model spread between MOS families | 0 | 5 | 0 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 1, REFUTED 1 |
| model_disagreement.stability.NAM[].d_gw_cdd | cross-model spread between MOS families | 0 | 5 | 0 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 1, REFUTED 1 |
| weather_forecast.run_delta[].d_gw_cdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 5 | 0 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 1, REFUTED 1 |
| weather_forecast.forecast_run_delta_cdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 3 | 0 | DEGENERATE 1, HYPOTHESIS 1, PROVISIONAL 1 |
| squeeze_watch.calendar_dte_limb_satisfied_live | expiry/OI/positioning conjunction detector | 0 | 2 | 3 | DESCRIPTOR 1, PROVISIONAL 1 |
| cash_basis.age_days | Henry Hub cash vs front-futures settle | 0 | 1 | 21 | PROPOSED 1 |
| cot.age_days | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 21 | PROPOSED 1 |
| grid_stack.age_days | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 21 | PROPOSED 1 |
| ngwu_balance.age_days | EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending 2026-01-21 | 0 | 1 | 21 | PROPOSED 1 |
| ngwu_balance.latest_sd_levels.age_days | EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending 2026-01-21 | 0 | 1 | 21 | PROPOSED 1 |
| nuclear_outages.age_days | NRC daily reactor status | 0 | 1 | 21 | PROPOSED 1 |
| steo_vintage.age_days | EIA STEO monthly archived workbooks - the complete balance as-of release | 0 | 1 | 21 | PROPOSED 1 |
| storage_vintage.age_days | EIA storage as-of each vintage - the revision process | 0 | 1 | 21 | PROPOSED 1 |
| squeeze_watch.active | expiry/OI/positioning conjunction detector | 0 | 1 | 5 | DEGENERATE 1 |
| squeeze_watch.unwind_watch | expiry/OI/positioning conjunction detector | 0 | 1 | 5 | DESCRIPTOR 1 |
| storage_consensus.next_print | street consensus for the storage print | 0 | 1 | 1 | PROVISIONAL 1 |
| cot.ice.hh_basis.managed_money_net_pctile_3y | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 0 | PROPOSED 1 |
| cot.ice.hh_index.managed_money_net_pctile_3y | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 0 | PROPOSED 1 |
| cot.ice.ld1.managed_money_net_pctile_3y | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 0 | PROPOSED 1 |
| cot.ice.pen.managed_money_net_pctile_3y | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 0 | PROPOSED 1 |
| cot.managed_money_net | CFTC Commitments of Traders, futures and ICE HH | 0 | 1 | 0 | PROPOSED 1 |
| grid_stack.bas.CISO.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.CISO.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.CISO.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.ERCO.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.ERCO.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.ERCO.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.MISO.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.MISO.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.MISO.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.PJM.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.PJM.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.PJM.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SOCO.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SOCO.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SOCO.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SWPP.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SWPP.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.SWPP.wind_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.US48.gas_share | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| grid_stack.bas.US48.solar_mwh | EIA-930 hourly/daily BA operations: demand, day-ahead forecast, gen by fuel | 0 | 1 | 0 | PROVISIONAL 1 |
| model_disagreement.stability.GFS[].d_gw_hdd | cross-model spread between MOS families | 0 | 1 | 0 | PROVISIONAL 1 |
| model_disagreement.stability.MEX[].d_gw_hdd | cross-model spread between MOS families | 0 | 1 | 0 | PROVISIONAL 1 |
| model_disagreement.stability.NAM[].d_gw_hdd | cross-model spread between MOS families | 0 | 1 | 0 | PROVISIONAL 1 |
| ngwu_balance.lng_vessel_capacity_bcf | EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending 2026-01-21 | 0 | 1 | 0 | WIRED_UNPROVEN 1 |
| ngwu_balance.lng_vessels_departed | EIA Natural Gas Weekly Update. LIVE RISK: final edition was the week ending 2026-01-21 | 0 | 1 | 0 | WIRED_UNPROVEN 1 |
| squeeze_watch.calendar_front_next_spread | expiry/OI/positioning conjunction detector | 0 | 1 | 0 | DESCRIPTOR 1 |
| storage.vs_5yr | EIA weekly working gas in storage | 0 | 1 | 0 | PROPOSED 1 |
| storage.weekly_chg | EIA weekly working gas in storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_consensus.last_print.consensus_chg_bcf | street consensus for the storage print | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_consensus.next_print.consensus_chg_bcf | street consensus for the storage print | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.east.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.l48.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.midwest.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.mountain.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.pacific.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.south_central.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.south_central_nonsalt.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| storage_regional.regions.south_central_salt.weekly_chg | EIA regional + salt/non-salt storage | 0 | 1 | 0 | PROVISIONAL 1 |
| weather_forecast.forecast_gw_cdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 1 | 0 | DEGENERATE 1 |
| weather_forecast.forecast_run_delta | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 1 | 0 | PROVISIONAL 1 |
| weather_forecast.horizons[].forecast_gw_cdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 1 | 0 | DEGENERATE 1 |
| weather_forecast.horizons[].forecast_gw_hdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 1 | 0 | PROVISIONAL 1 |
| weather_forecast.run_delta[].d_gw_hdd | NWS MOS (GFS/NAM/MEX) via the IEM archive | 0 | 1 | 0 | PROVISIONAL 1 |
| weather_forecast_cycle.sunday_reopen.delta_vs_prior_by_horizon[].d_gw_hdd | MOS cycle timing - which run was available at decision time | 0 | 1 | 0 | PROVISIONAL 1 |
| weather_forecast_cycle.weekday_open.delta_vs_prior_by_horizon[].d_gw_hdd | MOS cycle timing - which run was available at decision time | 0 | 1 | 0 | PROVISIONAL 1 |
| squeeze_watch.calendar_limb_satisfied_live | expiry/OI/positioning conjunction detector | 0 | 0 | 9 |  |
| squeeze_watch.days_to_calendar_front_expiry_live | expiry/OI/positioning conjunction detector | 0 | 0 | 7 |  |
| cot.ice.hh_basis.managed_money_net_pctile_1y | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 3 |  |
| cot.ice.hh_index.managed_money_net_pctile_1y | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 3 |  |
| cot.ice.pen.managed_money_net_pctile_1y | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 3 |  |
| cash_basis.vintage_asof | Henry Hub cash vs front-futures settle | 0 | 0 | 1 |  |
| cot.ice.hh_basis.managed_money_net_chg_wow | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.hh_basis.report_date | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.hh_index.managed_money_net_chg_wow | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.hh_index.report_date | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.ld1.managed_money_net_chg_wow | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.ld1.report_date | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.pen.managed_money_net_chg_wow | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.ice.pen.report_date | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| cot.report_date | CFTC Commitments of Traders, futures and ICE HH | 0 | 0 | 1 |  |
| options_surface.vintage_asof | NG options settle IV surface, ON/LNE roots | 0 | 0 | 1 |  |
| squeeze_watch.vintage_asof | expiry/OI/positioning conjunction detector | 0 | 0 | 1 |  |

## Single data points already carried on the experiment days (tape, calendar), not wished for

| data point | source | plays (condition) | plays (all) | declines | play status |
|---|---|---|---|---|---|
| tape_conditions.session_b_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 5 | 6 | 24 | DEGENERATE 3, PROVISIONAL 3 |
| tape_conditions.big_print_b_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 5 | 5 | 8 | PROPOSED 2, PROVISIONAL 3 |
| flow_calendar.bidweek_delivery_month | exchange + index calendar: roll, BCOM, expiry, holidays | 4 | 4 | 0 | PROVISIONAL 4 |
| flow_calendar.days_to_next_eia_release | exchange + index calendar: roll, BCOM, expiry, holidays | 3 | 3 | 0 | DEGENERATE 1, HYPOTHESIS 1, PROVISIONAL 1 |
| tape_conditions.session_signed_flow | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 2 | 4 | 27 | PROPOSED 3, PROVISIONAL 1 |
| tape_conditions.big_prints_n | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 2 | 2 | 3 | PROPOSED 2 |
| flow_calendar.days_to_futures_expiry | exchange + index calendar: roll, BCOM, expiry, holidays | 2 | 2 | 0 | PROPOSED 1, PROVISIONAL 1 |
| tape_conditions.phase_signed_flow[] | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 1 | 3 | 2 | HYPOTHESIS 1, PROPOSED 2 |
| flow_calendar.bcom_roll_day_n | exchange + index calendar: roll, BCOM, expiry, holidays | 1 | 1 | 1 | PROPOSED 1 |
| flow_calendar.gsci_roll_day_n | exchange + index calendar: roll, BCOM, expiry, holidays | 1 | 1 | 1 | PROPOSED 1 |
| dow | day of week | 0 | 53 | 62 | DEGENERATE 8, HYPOTHESIS 9, PROPOSED 6, PROVISIONAL 28, REFUTED 1, STABLE 1 |
| note | free-text annotation, not a quantity | 0 | 11 | 9 | DEGENERATE 3, HYPOTHESIS 2, PROVISIONAL 6 |
| holiday | CME holiday table - HARDCODED, ends 2027-02-15 (A-14) | 0 | 9 | 3 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 6 |
| tape_conditions.prior_full_session.session_b_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 6 | 24 | DEGENERATE 3, PROVISIONAL 3 |
| tape_conditions.prior_full_session.big_print_b_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 4 | 8 | PROPOSED 2, PROVISIONAL 2 |
| tape_conditions.prior_full_session.session_signed_flow | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 3 | 27 | PROPOSED 2, PROVISIONAL 1 |
| flow_calendar.in_bcom_roll | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 3 | 5 | PROPOSED 3 |
| flow_calendar.in_gsci_roll | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 3 | 5 | PROPOSED 3 |
| tape_conditions.prior_full_session.session_b_share_two_sided | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 3 | 2 | DEGENERATE 2, PROVISIONAL 1 |
| tape_conditions.session_b_share_two_sided | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 3 | 2 | DEGENERATE 2, PROVISIONAL 1 |
| tape_conditions.prior_full_session.phase_signed_flow[] | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 2 | 2 | HYPOTHESIS 1, PROPOSED 1 |
| flow_calendar.is_expiry_day | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 2 | 1 | PROPOSED 2 |
| flow_calendar.is_opex_day | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 2 | 0 | PROPOSED 2 |
| tape_conditions.session | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 2 | 0 | DEGENERATE 1, PROPOSED 1 |
| contract_structure.curve_regime | CME definitions + forward curve, calendar-front pair | 0 | 1 | 21 | PROVISIONAL 1 |
| tape_conditions.prior_full_session.big_prints_n | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 1 | 3 | PROPOSED 1 |
| firehose_present.l1_book | whether the MBO firehose reached this day | 0 | 1 | 2 | HYPOTHESIS 1 |
| tape_conditions.l1_book.quote_bid_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 1 | 2 | PROVISIONAL 1 |
| tape_conditions.prior_full_session.l1_book.quote_bid_share | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 1 | 2 | PROVISIONAL 1 |
| contract_structure.calendar_front_next_spread | CME definitions + forward curve, calendar-front pair | 0 | 1 | 0 | DESCRIPTOR 1 |
| flow_calendar.in_bidweek | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 1 | 0 | PROPOSED 1 |
| vol_regime.n0_net_sigma_10 | realized vol regime derived from the tape | 0 | 1 | 0 | PROVISIONAL 1 |
| vol_regime.n0_prev_trades | realized vol regime derived from the tape | 0 | 1 | 0 | PROPOSED 1 |
| vol_regime.n0_range_pctile | realized vol regime derived from the tape | 0 | 1 | 0 | PROVISIONAL 1 |
| tape_conditions.never_masked | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 23 |  |
| tape_conditions.prior_full_session.never_masked | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 23 |  |
| tape_conditions.n_trades | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 21 |  |
| tape_conditions.prior_full_session.n_trades | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 21 |  |
| flow_calendar.gsci_ng_roll_this_month | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 0 | 3 |  |
| flow_calendar.bcom_ng_roll_this_month | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 0 | 2 |  |
| flow_calendar.business_day_of_month | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 0 | 2 |  |
| contract_structure.vintage_asof | CME definitions + forward curve, calendar-front pair | 0 | 0 | 1 |  |
| flow_calendar.in_bcom_hedge_roll | exchange + index calendar: roll, BCOM, expiry, holidays | 0 | 0 | 1 |  |
| tape_conditions.big_print_b_share_two_sided | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 1 |  |
| tape_conditions.phase_volume_lots[] | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 1 |  |
| tape_conditions.prior_full_session.big_print_b_share_two_sided | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 1 |  |
| tape_conditions.prior_full_session.phase_volume_lots[] | Databento MBO/MBP-10 NYMEX tape - prior-session activity. NEVER MASKED | 0 | 0 | 1 |  |
| vol_regime.vintage_asof | realized vol regime derived from the tape | 0 | 0 | 1 |  |

## Whole blocks named in prose (not one data point)

| data point | source | plays (condition) | plays (all) | declines | play status |
|---|---|---|---|---|---|
| dow | day of week | 0 | 53 | 62 | DEGENERATE 8, HYPOTHESIS 9, PROPOSED 6, PROVISIONAL 28, REFUTED 1, STABLE 1 |
| weather | NWS/IEM ASOS observations | 0 | 20 | 4 | DEGENERATE 2, DESCRIPTOR 1, HYPOTHESIS 1, PROPOSED 3, PROVISIONAL 12, REFUTED 1 |
| storage | EIA weekly working gas in storage | 0 | 17 | 43 | DEGENERATE 3, HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 11 |
| note | free-text annotation, not a quantity | 0 | 11 | 9 | DEGENERATE 3, HYPOTHESIS 2, PROVISIONAL 6 |
| holiday | CME holiday table - HARDCODED, ends 2027-02-15 (A-14) | 0 | 9 | 3 | HYPOTHESIS 1, PROPOSED 2, PROVISIONAL 6 |
| curve_regime | backwardation/contango label off the forward curve | 0 | 1 | 21 | PROVISIONAL 1 |
| stor_surprise | actual minus consensus | 0 | 1 | 1 | PROVISIONAL 1 |

## Named by a play but not in the live list

| data point | source | plays (condition) | plays (all) | declines | play status |
|---|---|---|---|---|---|
| grid_stack.bas.US48.gas_share_chg_7d | - | 1 | 1 | 0 | PROVISIONAL 1 |
| self.guess_day_move_usd | - | 1 | 1 | 0 | PROVISIONAL 1 |
