"""Finish all additions from the indexed extraction cache; gate one final Julia batch."""
import bisect
import collections
import csv
import gzip
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import statistics
from enrichment_rules import flatten

BASE = pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR', '/opt/frankie-box/work/family-research-20261022'))
OLD, OUT = BASE/'descriptive-v1', BASE/'enriched-v2'
db = sqlite3.connect(f'file:{BASE / "alignment.sqlite"}?mode=ro', uri=True)
db.row_factory = sqlite3.Row
contexts = list(csv.DictReader((OLD/'group_context_receipts.csv').open()))
samples = {r['sample_id']:r for r in csv.DictReader((OLD/'samples.csv').open())}
life = {}
with gzip.open(OUT/'lifecycle_original_rows.jsonl.gz','rt') as f:
    for line in f:
        r=json.loads(line);life[r['source_ordinal']]=r['row']
links=collections.defaultdict(list)
for r in csv.DictReader((OUT/'lifecycle_context_links.csv').open()):
    links[(r['sample_id'],int(r['lag_s']))].append(r)
safe_sections={'queue','replenishment','absorption','ladder','flow_substrate','recurrence','mirror'}
counter_checks=counter_mismatches=derived_zero_n=0
fieldnames=['sample_id','lag_s','feature','value','age_s','source_ordinal','reason','observed_n']
numeric_n=0
features=set()
with (OUT/'enriched_context_measurements.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader()
    def emit(c,feature,value,age=None,ordinal=None,reason='observed_source_measurement',n=1):
        global numeric_n
        writer.writerow(dict(sample_id=c['sample_id'],lag_s=c['lag_s'],feature=feature,
                             value=value,age_s=c['age_s'] if age is None else age,
                             source_ordinal=c['source_ordinal'] if ordinal is None else ordinal,
                             reason=reason,observed_n=n))
        features.add(feature);numeric_n+=1
    quality={}
    with gzip.open(OUT/'native_quality_contexts.jsonl.gz','rt') as qf:
        for line in qf:
            r=json.loads(line);quality[r['source_ordinal']]=r['quality']
    alphabets={k:set() for k in ['action','side']}
    for q in quality.values():
        for k in alphabets:alphabets[k].update(q['structure'][k+'_string'])
    for c in contexts:
        values=collections.defaultdict(list);counts=collections.Counter()
        for link in links[(c['sample_id'],int(c['lag_s']))]:
            if link['eligible']!='1':continue
            r=life[int(link['lifecycle_ordinal'])];sec=r['emitting_section']
            if sec not in safe_sections:continue
            counts[sec]+=1
            for name,value in flatten(r):
                # Same-side and other-side quantities remain separate; do not select a side from flow.
                values[f'lifecycle.{sec}.{r.get("side","UNSPECIFIED")}.{name}.mean'].append(value)
        for feature,v in values.items():emit(c,feature,statistics.mean(v),n=len(v))
        for sec in sorted(safe_sections):emit(c,f'lifecycle.{sec}.emission_count',counts[sec],reason='explicit_selected_group_receipt_count')
        # Direct counts of the complete recorded strings. This is a separately named
        # measurement, not a guess about source-null or rolling-window dictionaries.
        st=quality[int(c['source_ordinal'])]['structure']
        for k,alphabet in alphabets.items():
            observed=collections.Counter(st[k+'_string']);declared=st[k+'_counts']
            good=dict(observed)==declared and sum(observed.values())==st['component_count']
            counter_checks+=1;counter_mismatches+=int(not good)
            for action in sorted(alphabet):
                v=observed[action] if good else None
                derived_zero_n+=int(good and v==0)
                emit(c,f'native_observed.structure.{k}_count.{action}',v,
                     reason='count_complete_recorded_string_verified_against_source_counts' if good else 'source_counter_contradiction')

    # Every documented external field at all 2/5/10-minute context cutoffs,
    # preserving model, horizon, station, target day and immediate prior vintage.
    fields={'cot.023651':['managed_money_net_pctile_1y','managed_money_net_chg_wow','managed_money_net_pctile_3y'],
            'cot.023391':['managed_money_net_pctile_1y'], 'mos.gw_by_cycle':['gw_hdd','gw_cdd','coverage'],
            'eia930.us48':['wind_mwh','est_gas_burn_bcfd_rate'],
            'calendar.sessions_since_prompt_expiry':['sessions_since_prompt_expiry'],
            'mos.disagreement_by_cycle':['max_abs_spread_gw_hdd'], 'weather.gw_daily':['gw_hdd','gw_cdd','coverage'],
            'weather.obs_hourly':['tmpf','dwpf','sknt'], 'storage.weekly':['level_bcf','weekly_chg_bcf','vs_5yr_bcf'],
            'storage.estimate':['estimate_bcf','actual_bcf','surprise_bcf'],
            'curve.settled_shape':['slope_1','slope_back','curvature','front_next_spread'],
            'curve.traded_shape':['slope_1','slope_back','curvature','front_next_spread']}
    contextmap={(c['sample_id'],int(c['lag_s'])):c for c in contexts}
    external_feature_rows=0
    with gzip.open(OUT/'external_extended_asof.jsonl.gz','rt') as ef:
        for line in ef:
            x=json.loads(line);r=x['source'];point=x['series'].split('|')[0]
            if point not in fields:continue
            c=contextmap[(x['sample_id'],x['lag_s'])]
            j={} if r is None else json.loads(r['row_json'])
            age=None if r is None else (x['cutoff_ns']-r['published_ns'])/1e9
            for key in fields[point]:
                v=j.get(key)
                try:v=float(v) if v is not None and not isinstance(v,bool) else None
                except (ValueError,TypeError):v=None
                if v is not None and not math.isfinite(v):v=None
                emit(c,f'external_extended.vintage{x["vintage_offset"]}.{x["series"]}.{key}',v,
                     age='' if age is None else age,ordinal='' if r is None else r['source_ordinal'],
                     reason='no_prior_publication' if r is None else 'source_missing' if v is None else 'published_source_row')
                external_feature_rows+=1
    # Same-field published numeric weather history at every extended cutoff.
    weather_fields='alti drct dwpf feel gust ice_accretion_1hr ice_accretion_3hr ice_accretion_6hr mslp p01i peak_wind_drct peak_wind_gust relh sknt skyl1 skyl2 skyl3 skyl4 snowdepth tmpf vsby'.split()
    history=collections.defaultdict(list);stations=set()
    for r in db.execute("SELECT * FROM external_row WHERE point_name='weather.obs_hourly' ORDER BY published_ns,source_ordinal"):
        j=json.loads(r['row_json']);station=j['station'];stations.add(station)
        for key in weather_fields:
            try:v=float(j[key])
            except (KeyError,ValueError,TypeError):continue
            if math.isfinite(v):history[(station,key)].append((r['published_ns'],r['source_ordinal'],v))
    weather_n=0
    for station in sorted(stations):
        for key in weather_fields:
            h=history[(station,key)];times=[r[0] for r in h]
            for c in contexts:
                # Existing lag-zero weather values are already in the shared baseline.
                if int(c['lag_s'])==0:continue
                i=bisect.bisect_left(times,int(c['cutoff_ns']))-1
                r=h[i] if i>=0 else None
                emit(c,f'external_last_observed.weather.obs_hourly|station={station}.{key}',None if r is None else r[2],
                     age='' if r is None else (int(c['cutoff_ns'])-r[0])/1e9,
                     ordinal='' if r is None else r[1],reason='no_prior_numerical_observation' if r is None else 'actual_published_measurement_history')
                weather_n+=1

# Flatten quote outcomes for Julia; all clocks and source rows remain in the JSON receipts.
with (OUT/'quote_windows.csv').open('w',newline='') as f:
    names=['sample_id','family_id','phase','horizon_s','instrument_id','chronological_quarter',
           'from_age_s','to_age_s','from_ordinal','to_ordinal','bid_change','ask_change','mid_change',
           'from_spread','to_spread','edge_censored','disposition']
    w=csv.DictWriter(f,fieldnames=names);w.writeheader()
    with gzip.open(OUT/'quote_endpoint_receipts.jsonl.gz','rt') as qf:
        for line in qf:
            r=json.loads(line);a,b=r.pop('from_quote'),r.pop('to_quote')
            ok=a['disposition']==b['disposition']=='observed_quote'
            row={k:r[k] for k in names if k in r}
            row.update(from_age_s=a.get('age_s'),to_age_s=b.get('age_s'),from_ordinal=a.get('source_ordinal'),
                       to_ordinal=b.get('source_ordinal'),from_spread=a.get('spread'),to_spread=b.get('spread'),
                       edge_censored=not ok,disposition='observed_quotes' if ok else a['disposition']+'|'+b['disposition'])
            for prefix,key in [('bid','best_bid'),('ask','best_ask'),('mid','mid')]:
                row[prefix+'_change']=b[key]-a[key] if ok and a.get(key) is not None and b.get(key) is not None else None
            w.writerow(row)

assert counter_mismatches==0, 'Do not promote source counter contradictions into zero measurements'
assert len(samples)==3745 and len({s['family_id'] for s in samples.values()})==749
assert db.execute('SELECT count(*) FROM plane_registry').fetchone()[0]==99
# Reuse frozen baseline inputs through explicit symlinks; results have their own files.
inputs=['samples','features','elapsed_windows','group_measurements','external_last_observed_measurements',
        'pullback_measurements','complete_context_measurements','nearby_price_pairs','family_master',
        'plane_registry','external_point_provenance','source_registry','retained_group_sequence','view_definitions']
for name in inputs:
    target=OUT/(name+'.csv')
    if not target.exists():target.symlink_to(OLD/(name+'.csv'))
for name in ['Project.toml','Manifest.toml']:
    (OUT/name).write_bytes((OLD/name).read_bytes())
gaps=[
    ('queue_far_side','276054 of 771787 original rows undefined/not-last; retain NOT_F_LAST/NO_FLOW/SIDE_UNDEFINED; both-side observed ages already available'),
    ('pullback_completed_steps','No completed last step at 701/749 prestarts, no previous step at 743/749; ongoing step remains separate, no future completion backfill'),
    ('calendar_prior_publication','Saved calendar source not published at 659/749 starts; no independently demonstrated historical calendar count is available in the retained inputs'),
    ('forecast_vintage_edges','Specific model/horizon/target-day series have no earlier publication at early starts; latest and immediate prior vintages remain separately missing'),
    ('weather_missing_fields','Only genuinely earlier same-station numeric measurements used; fields with no prior measurement remain missing'),
    ('pre_session_trades','No earlier trades in retained price source for 26 T-120, 8 before-start and 7 onset contexts; opening-book evidence does not manufacture a prior trade'),
    ('post_session_endpoints','Actual group/price bounds enforced independently; no invented flat prices after the retained session'),
    ('rolling_dictionary_omissions','Complete structural action/side strings now counted directly and reconciled; unknown rolling-window dictionary keys remain absent, source-null stays null'),
    ('terminal_candidate_response_knowledge','Full original records retained with known-by clocks as later/provenance evidence; candidate, recognition, response and outcome labels are excluded from numerical input features'),
    ('ladder_price_units','Original ladder price/gap fields retained; unverified ladder scales are not promoted to price features; validated native bid/ask/mid supplied separately'),
    ('additional_days','One retained trading day; earlier SQLite catalog runs do not add independent days or observations')]
with (OUT/'remaining_gaps.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['area','disposition']);w.writerows(gaps)
receipt=dict(schema='FAMILY_ALL_ADDITIONS_READY_V2',all_agreed_areas_accounted_for=True,
             families=749,contexts=len(contexts),numeric_rows=numeric_n,features=len(features),
             structural_counter_checks=counter_checks,structural_counter_mismatches=counter_mismatches,
             directly_observed_zero_counts=derived_zero_n,external_feature_rows=external_feature_rows,
             extended_weather_rows=weather_n,excluded_input_sections=['candidate','episode','response'],
             missing_policy='No family or retained source row excluded; see remaining_gaps.csv; missing is never filled from future knowledge.',
             original_counts='771787 second-set rows, 583688 groups, 749 families, 329658 external rows, 13 conceptual points, 99 registry identities/dispositions, 30739 trades remain pinned',
             source_database_mode='read only',final_analysis_started=False)
(OUT/'all_additions_ready.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
