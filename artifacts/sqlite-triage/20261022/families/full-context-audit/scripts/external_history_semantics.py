"""Explicit field roles and source-defined clocks for recovered external history.

Raw variants are never rewritten. Derived clocks implement EVENT_TIME_RULES in
the saved reader, with original publication stamps and stamp shapes retained.
"""
import calendar
import datetime as dt
import functools
import math
import re
from zoneinfo import ZoneInfo

ET=ZoneInfo('America/New_York')
SESSION_DAY=dt.date(2023,10,18)
COMMON={'published_ns','event_time_ns'}
COT_NUM={'managed_money_long','managed_money_net','managed_money_net_chg_wow','managed_money_net_pctile_1y',
         'managed_money_net_pctile_3y','managed_money_short','open_interest','other_reportable_net',
         'pctile_1y_n_obs','pctile_3y_n_obs','producer_merchant_net','swap_dealer_net'}
WEATHER_NUM={'alti','drct','dwpf','feel','gust','ice_accretion_1hr','ice_accretion_3hr','ice_accretion_6hr',
             'mslp','p01i','peak_wind_drct','peak_wind_gust','relh','sknt','skyl1','skyl2','skyl3','skyl4','snowdepth','tmpf','vsby'}
# scope, observation coordinate(s), numeric fields, categories, provenance, structured fields
SPECS={
 'calendar.sessions_since_prompt_expiry':((),(),{'sessions_since_prompt_expiry'},{'last_prompt_symbol'},{'last_prompt_expiry'},set()),
 'curve.definitions':(('instrument_id','raw_symbol'),(),set(),{'instrument_class'},{'expiration_ns'},set()),
 'curve.statistics':(('instrument_id','raw_symbol','stat_type'),('ts_event','ts_ref'),{'price','quantity'},
                     {'update_action','stat_flags'},set(),set()),
 'curve.trades':(('instrument_id','raw_symbol'),('ts_event',),{'price','size'},{'side'},set(),set()),
 'curve.settled_shape':(('front_symbol','next_symbol'),(),{'front','c1','back_rank','back','slope_1','slope_back','curvature','front_next_spread','n_ranks'},{'regime'},set(),set()),
 'curve.traded_shape':(('front_symbol','next_symbol'),(),{'front','c1','back_rank','back','slope_1','slope_back','curvature','front_next_spread','n_ranks'},{'regime'},set(),set()),
 'eia930.hourly':(('respondent','route','fueltype_or_type','units'),('period_utc',),{'value'},set(),set(),set()),
 'eia930.us48':((),('period_utc',),{'wind_mwh','gas_mwh','est_gas_burn_bcfd_rate'},set(),set(),set()),
 'mos.gw_by_cycle':(('model','target_day'),('runtime_utc',),{'gw_hdd','gw_cdd','n_metros','coverage'},set(),{'horizon_days'},{'metros_missing'}),
 'mos.raw':(('station','model','valid_utc'),('runtime_utc',),{'tmp_f'},set(),set(),set()),
 'mos.disagreement_by_cycle':((),('runtime_utc',),{'max_abs_spread_gw_hdd'},set(),{'at_horizon_days'},{'spreads_by_horizon'}),
 'storage.weekly':((),('week_ending',),{'level_bcf','weekly_chg_bcf','vs_5yr_bcf','five_yr_avg_bcf','year_ago_bcf'},set(),{'source'},{'same_week_prior_5y_levels'}),
 'storage.estimate':((),('print_ns','print_date','week_ending'),{'estimate_bcf','actual_bcf','surprise_bcf'},{'missing_reason'},{'source'},set()),
 'storage.estimate_captures':(('house',),('print',),set(),set(),{'capture_key','sha256'},set()),
 'weather.gw_daily':((),('gas_day',),{'gw_hdd','gw_cdd','gw_precip','n_stations','coverage'},{'regime'},set(),set()),
 'weather.obs_hourly':(('station',),('valid_utc',),WEATHER_NUM,{'skyc1','skyc2','skyc3','skyc4'},{'peak_wind_time'},set()),
}
COT_SPEC=(('contract_code',),('report_date',),COT_NUM,
          {'market_name','publication_confidence','publication_delayed','store_publication_confidence','store_publication_delayed'},
          {'publication_ts','store_published_ns'},set())


@functools.lru_cache(maxsize=200000)
def ns_utc(text):
    value=dt.datetime.fromisoformat(text.replace('Z','+00:00'))
    if value.tzinfo is None:value=value.replace(tzinfo=dt.timezone.utc)
    return calendar.timegm(value.utctimetuple())*10**9+value.microsecond*1000


@functools.lru_cache(maxsize=5000)
def ns_et(day,hour):
    value=dt.datetime.combine(dt.date.fromisoformat(day),dt.time(hour),tzinfo=ET)
    return calendar.timegm(value.utctimetuple())*10**9


def normalize_aliases(point,row):
    out={}
    for key,value in row.items():
        match=re.fullmatch(r'(publication_confidence|publication_delayed|published_ns)__source_column_\d+',key)
        name='store_'+match[1] if point.startswith('cot.') and match else key
        if name in out:assert out[name]==value,(point,name,out[name],value)
        out[name]=value
    return out


def derived_event(point,row):
    if point.startswith('cot.'):return ns_et(row['report_date'],17) if row.get('report_date') else None
    if point=='storage.weekly':return ns_et(row['week_ending'],17)
    if point=='storage.estimate':return row['print_ns']
    if point=='weather.obs_hourly':return ns_utc(row['valid_utc'])
    if point=='weather.gw_daily':return row['published_ns']-600*10**9
    if point.startswith('mos.'):return ns_utc(row['runtime_utc'])
    if point.startswith('eia930.'):return ns_utc(row['period_utc'])
    if point in ['curve.statistics','curve.trades']:return row['ts_event']
    if point.startswith('curve.'):return row['published_ns']
    return None


def numeric_state(value):
    if value is None:return None,'SOURCE_NULL'
    if value=='M':return None,'SOURCE_MISSING_MARKER_M'
    if isinstance(value,bool):raise ValueError('Boolean was not declared a numerical measurement')
    try:result=float(value)
    except (ValueError,TypeError):return None,'SOURCE_NON_NUMERIC'
    return (result,'PRESENT') if math.isfinite(result) else (None,'SOURCE_NON_FINITE')


def normalize(point,raw,source_day):
    row=normalize_aliases(point,raw)
    scope_fields,obs_fields,numeric_fields,category_fields,provenance_fields,structured_fields=COT_SPEC if point.startswith('cot.') else SPECS[point]
    allowed=COMMON|set(scope_fields)|set(obs_fields)|numeric_fields|category_fields|provenance_fields|structured_fields
    unknown=set(row)-allowed
    if unknown:raise ValueError((point,'unreviewed_fields',sorted(unknown)))
    publication=row['published_ns'];assert type(publication) is int
    declared='event_time_ns' in row
    event=row.get('event_time_ns') if declared else derived_event(point,row)
    if event==2**64-1:event=None
    day=dt.datetime.strptime(source_day,'%Y%m%d').date()
    available=publication if declared else max(publication,event if event is not None else ns_et(day.isoformat(),14))
    assert event is None or (type(event) is int and event<=available),(point,event,available)
    numbers={};states={};categories={k:row[k] for k in sorted(category_fields) if k in row}
    provenance={k:row[k] for k in sorted(provenance_fields) if k in row}
    for key in sorted(numeric_fields):
        if key not in row:continue
        numbers[key],states[key]=numeric_state(row[key])
    scope={k:row[k] for k in scope_fields}
    observation={k:row[k] for k in obs_fields}
    # A calendar row is a daily count; a prior day's count remains a prior-day observation.
    if point.startswith('calendar.'):observation['source_trading_day']=day.isoformat()
    if point in ['curve.statistics','curve.trades','curve.definitions','curve.settled_shape','curve.traded_shape']:
        observation['source_published_ns']=publication
    if point=='curve.statistics':
        if row.get('quantity')==2**63-1:
            numbers['quantity']=None;states['quantity']='UNDEFINED_STAT_QUANTITY'
        ref=row.get('ts_ref');provenance['reference_ns']=None if ref==2**64-1 else ref
        if row.get('update_action')==2:
            for field in ['price','quantity']:
                if field in numbers:numbers[field]=None;states[field]='DELETED_STATISTIC'
    if point=='curve.definitions':
        expiry=row.get('expiration_ns');provenance['expiration_ns']=None if expiry==2**64-1 else expiry
    if point=='mos.gw_by_cycle':
        provenance['source_horizon_days']=provenance.pop('horizon_days')
        target=dt.date.fromisoformat(row['target_day'])
        numbers['target_offset_from_aligned_session_days']=(target-SESSION_DAY).days
        states['target_offset_from_aligned_session_days']='PRESENT'
        categories['metros_missing']=row.get('metros_missing')
        numbers['metros_missing_count']=len(row['metros_missing']) if row.get('metros_missing') is not None else None
        states['metros_missing_count']='PRESENT' if row.get('metros_missing') is not None else 'SOURCE_NULL'
    if point=='mos.raw':provenance['forecast_valid_ns']=ns_utc(row['valid_utc'])
    if point=='mos.disagreement_by_cycle':
        scope['source_target_session']=day.isoformat()
        provenance['source_at_horizon_days']=provenance.pop('at_horizon_days',None)
        for horizon,spread,metros in row.get('spreads_by_horizon') or []:
            target=day+dt.timedelta(days=horizon);offset=(target-SESSION_DAY).days
            for field,value in [('spread_gw_hdd',spread),('common_metros',metros)]:
                key='target_session_offset_days_'+str(offset)+'.'+field
                numbers[key],states[key]=numeric_state(value)
        if row.get('at_horizon_days') is not None:
            numbers['max_spread_target_offset_from_aligned_session_days']=(day-SESSION_DAY).days+row['at_horizon_days']
            states['max_spread_target_offset_from_aligned_session_days']='PRESENT'
    if point=='storage.weekly':
        for year,value in row.get('same_week_prior_5y_levels') or []:
            back=dt.date.fromisoformat(row['week_ending']).year-int(year)
            assert 1<=back<=5
            key='same_week_prior_'+str(back)+'y_level_bcf'
            numbers[key],states[key]=numeric_state(value)
        numbers['same_week_prior_5y_levels_count']=len(row.get('same_week_prior_5y_levels') or [])
        states['same_week_prior_5y_levels_count']='PRESENT'
    roles={k:('clock_provenance' if k in COMMON else 'scope_coordinate' if k in scope_fields else
              'observation_vintage_coordinate' if k in obs_fields else 'numeric_measurement_with_state' if k in numeric_fields else
              'observed_category' if k in category_fields else 'structured_values_explicitly_unpacked' if k in structured_fields else
              'source_provenance_and_clock_derivation') for k in row}
    return dict(point=point,scope=scope,observation=observation,numeric=numbers,states=states,categories=categories,
                provenance=provenance,event_ns=event,available_ns=available,source_published_ns=publication,
                clock_rule='SOURCE_READER_STAMP' if declared else 'SOURCE_PUBLICATION_PLUS_EXPLICIT_READER_EVENT_PLACEMENT',
                field_roles=roles)
