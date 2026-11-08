"""Retained-field relationship screen and original-message extracts for discovery.

No significance selection, scoring admission, producer replay or external fetch.
"""
from collections import Counter
import json
import subprocess

import numpy as np
import pandas as pd

from flow_book_discovery import BASE, REVIEW, OUT, REV, NS, rows, save, dump


def field_screen(opportunities, outcomes):
    measurements = pd.DataFrame(rows(REVIEW + 'pre-event-measurements.csv.gz'))
    measurements['instance'] = measurements.sample_id.str.split(':').str[0]
    measurements['numeric'] = pd.to_numeric(measurements.value, errors='coerce')
    measurements['usable'] = measurements.state.isin(['', '0']) & np.isfinite(measurements.numeric)
    inventory = []
    for feature, g in measurements.groupby('feature'):
        inventory.append(dict(feature=feature, rows=len(g), usable=int(g.usable.sum()),
                              distinct_values=int(g.loc[g.usable, 'numeric'].nunique()),
                              states=json.dumps([dict(state=s, reason=r, count=n) for (s, r), n in Counter(zip(g.state, g.reason)).items()]),
                              source_files=';'.join(sorted(g.measurement_file.unique())),
                              interpretation='saved strict-pre projection; semantic admission remains separate'))
    save('measurement-coverage.csv', inventory)
    values = measurements[measurements.usable].pivot(index='instance', columns='feature', values='numeric')
    # The registry comprises market evidence, shared transforms, clocks, controls,
    # outcomes and runtime records. It is not 99 independent numerical signals.
    planes = rows(BASE + 'descriptive-v1/plane_registry.csv')
    coverage = []
    for p in planes:
        n, body = int(p['ordinal']), json.loads(p['body'])
        if n in (12, 78, 79, 85, 86):
            relation = 'outcome_or_selection_boundary'
        elif 71 <= n <= 77 or n in (28, 45, 52, 65, 98):
            relation = 'availability_or_provenance'
        elif 29 <= n <= 51 or n == 26:
            relation = 'market_mechanism_or_state'
        elif 53 <= n <= 70 or 13 <= n <= 21:
            relation = 'derived_transform_or_lifecycle_context'
        else:
            relation = 'control_runtime_or_unresolved_context'
        coverage.append(dict(ordinal=n, entry_id=p['entry_id'], original_role=body.get('role'),
                             relationship_class=relation, original_disposition=body.get('disposition'),
                             status='in_scope; mapping is not numerical or semantic admission'))
    save('all-99-relationship-roles.csv', coverage)

    ext = [r for r in rows(BASE + 'descriptive-v1/external_asof.csv.gz') if r['sample_id'].endswith(':before_start')]
    provenance = {r['name']: json.loads(r['body']) for r in rows(BASE + 'descriptive-v1/external_point_provenance.csv')}
    cutoff = opportunities.set_index('sample_id').cutoff_ns.map(int).to_dict()
    prequote = opportunities.set_index('sample_id').pre_receive_ns.map(int).to_dict()
    extracts, series_coverage = [], []
    chosen = {'cot.023651': ('managed_money_net_pctile_1y', 'managed_money_net_chg_wow', 'managed_money_net_pctile_3y'),
              'cot.023391': ('managed_money_net_pctile_1y',), 'mos.gw_by_cycle': ('gw_hdd',),
              'eia930.us48': ('wind_mwh', 'est_gas_burn_bcfd_rate'),
              'calendar.sessions_since_prompt_expiry': ('sessions_since_prompt_expiry',),
              'mos.disagreement_by_cycle': ('max_abs_spread_gw_hdd',), 'weather.gw_daily': ('gw_hdd',),
              'storage.weekly': ('level_bcf', 'weekly_chg_bcf', 'vs_5yr_bcf'), 'storage.estimate': ('surprise_bcf',),
              'curve.traded_shape': ('slope_1', 'slope_back', 'curvature'),
              'curve.settled_shape': ('slope_1', 'slope_back', 'curvature')}
    for r in ext:
        if not r['source_row_json']:
            continue
        if not r['published_ns'] or int(r['published_ns']) > cutoff[r['sample_id']]:
            raise ValueError('external record violates its declared availability')
        record = json.loads(r['source_row_json'])
        for field in chosen.get(r['point_name'], ()):
            value = record.get(field)
            if not isinstance(value, (int, float)):
                continue
            extracts.append(dict(instance=r['sample_id'].split(':')[0], feature=f'external:{r["series"]}:{field}',
                                 value=value, source_ordinal=r['source_ordinal'], published_ns=r['published_ns'],
                                 event_time_ns=r['event_time_ns'], source_series=r['series'],
                                 published_after_prequote=int(r['published_ns']) > prequote[r['sample_id']],
                                 source_table=r['point_name'], source_field=field,
                                 points=json.dumps(provenance.get(r['point_name'], {}).get('points', []))))
    save('external-operands.csv.gz', extracts)
    ex = pd.DataFrame(extracts)
    values = values.join(ex.pivot(index='instance', columns='feature', values='value'), how='outer')
    for series, g in pd.DataFrame(ext).groupby('series'):
        present = g[g.source_row_json.ne('')]
        metadata = provenance.get(g.point_name.iloc[0], {})
        series_coverage.append(dict(series=series, n=len(g), present=len(present),
                                    distinct_source_rows=present.source_ordinal.nunique(),
                                    points=json.dumps(metadata.get('points', [])),
                                    timing_basis=metadata.get('event_time_basis'),
                                    source=metadata.get('source'), vintage=metadata.get('vintage'),
                                    limitation='Declared publication availability only; vendor/revision vintage not independently strengthened here.'))
    save('external-series-coverage.csv', series_coverage)
    bindings = json.loads(subprocess.check_output(['git', 'show', f'{REV}:{BASE}trade-lifecycle-targeted-v1/all-13-input-bindings.json']))
    point_coverage = []
    for p in bindings['points']:
        tables = [t['table'] for t in p['tables']]
        relevant = [r for r in series_coverage if p['point_id'] in json.loads(r['points'])]
        point_coverage.append(dict(point_id=p['point_id'], name=p['name'], bound_tables=json.dumps(tables),
                                   asof_series=len(relevant), present_records=sum(r['present'] for r in relevant),
                                   variable_series=sum(r['distinct_source_rows'] > 1 for r in relevant),
                                   relationship=('shared_positioning_source' if p['point_id'] in (1, 3, 4) else
                                                 'shared_power_source' if p['point_id'] in (5, 7) else
                                                 'shared_weather_source' if p['point_id'] in (2, 9) else
                                                 'same_instrument_overlap_and_other_legs' if p['point_id'] == 13 else 'context_or_transmission'),
                                   admission='exploratory_declared_asof_only'))
    save('all-13-point-coverage.csv', point_coverage)
    base = opportunities.set_index('instance')
    values = values.reindex(base.index)
    targets = base[['flow1', 'flow60', 'touch_imbalance', 'root.depth_imbalance_full', 'prior_mid1']].astype(float)
    for h in (1, 20, 300):
        y = outcomes[outcomes.horizon_s.eq(h)].set_index('instance').change
        targets[f'future_signed_{h}s'] = y
        targets[f'future_absolute_{h}s'] = y.abs()
    results = []
    # Descriptive quarter splits, not model validation. Preserve all signs and Ns.
    quarter = pd.Series(np.minimum(np.arange(len(base)) * 4 // len(base), 3) + 1, index=base.index)
    subsets = [('all', np.ones(len(base), dtype=bool)), ('original50', base.cohort.eq('original'))]
    subsets += [(f'quarter{q}', quarter.eq(q)) for q in range(1, 5)]
    for subset, mask in subsets:
        for feature in values:
            x = values.loc[mask, feature]
            for target in targets:
                pair = pd.concat([x.rename('x'), targets.loc[mask, target].rename('y')], axis=1).dropna()
                n = len(pair)
                valid = n >= 10 and pair.x.nunique() > 1 and pair.y.nunique() > 1
                results.append(dict(subset=subset, feature=feature, target=target, n=n,
                                    distinct_x=pair.x.nunique(), distinct_y=pair.y.nunique(),
                                    spearman=pair.x.rank().corr(pair.y.rank()) if valid else None,
                                    disposition='descriptive' if valid else 'insufficient_or_constant'))
    save('all-field-relationships.csv.gz', results)
    # Retain source coordinates for both case projections; no invented values.
    save('case-375-391-measurements.csv', measurements[measurements.instance.isin(['375', '391'])])
    save('case-375-391-external.csv.gz', [r for r in ext if r['sample_id'] in ('375:before_start', '391:before_start')])
    dump('relationship-method.json', dict(source_revision=REV, numeric_features=len(values.columns),
                                          attempted_comparisons=len(results), n_planes=len(coverage), n_points=len(point_coverage),
                                          scope='Selected family starts; descriptive ranks only. No p-values or significance selection. No new model admission.',
                                          restrictions=['Missing/invalid states excluded pairwise, denominators retained.',
                                                        'External rows use declared publication cutoff; some curve updates occur after the frozen prior completed book close. The flag is retained; these are not admitted to four-arm prediction.',
                                                        'Shared source and derived transform correlations are not independent corroboration.',
                                                        'External context can follow session drift; pooled or quarter correlations do not establish a release effect.',
                                                        'Exact inverse stack has zero support because all 749 full books are bid-heavy.']))


def original_messages(opportunities):
    import databento as db
    tape_rev = '1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202'
    tape_path = 'data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_20231018.dbn.zst'
    cases = opportunities[opportunities.instance.isin(['375', '391'])]
    spans = [(r.instance, int(r.anchor_ns) - NS, int(r.anchor_ns) + 5 * NS) for r in cases.itertuples()]
    output = []
    raw = subprocess.check_output(['git', 'show', f'{tape_rev}:{tape_path}'])
    for index, record in enumerate(db.DBNStore.from_bytes(raw)):
        if record.ts_recv > max(s[2] for s in spans):
            break
        for case, lo, hi in spans:
            if lo <= record.ts_recv <= hi:
                output.append(dict(instance=case, utc_member_record_index=index, session_cursor=index + 17375,
                                   event_ns=record.ts_event, receive_ns=record.ts_recv, action=str(record.action),
                                   side=str(record.side), order_id=record.order_id, price_raw=record.price,
                                   size=record.size, flags=int(record.flags), sequence=record.sequence,
                                   instrument_id=record.instrument_id))
    save('case-original-messages.csv.gz', output)
    dump('original-message-source.json', dict(revision=tape_rev, path=tape_path,
                                              utc_member_to_session_cursor_offset=17375, rows=len(output),
                                              spans=[dict(instance=c, start_receive_ns=lo, end_receive_ns=hi) for c, lo, hi in spans],
                                              scope='Original messages only; no producer replay. T summaries and F passive fills are distinct and must not be added as separate executed volume.'))


def setup_details(opportunities, outcomes):
    o = opportunities.copy()
    o['inverse_flow_only'] = (o.flow1 > 0) & (o.flow5 > 0) & (o.flow60 < 0)
    o['touch_relation'] = np.where(o.flow1 * o.touch_imbalance > 0, 'aligned',
                                  np.where(o.flow1 * o.touch_imbalance < 0, 'opposed', 'flat_or_missing'))
    joined = o.merge(outcomes, on='instance', validate='one_to_many')
    records = []
    for name, mask in [('original50', joined.cohort.eq('original')),
                       ('inverse_flow_only', joined.inverse_flow_only)]:
        for (h, relation), g in joined[mask].groupby(['horizon_s', 'touch_relation']):
            valid = g[g.outcome_disposition.eq('available')]
            signed = valid.change * np.sign(valid.flow1)
            records.append(dict(setup=name, horizon_s=h, touch_relation_to_recent_flow=relation,
                                n=len(g), available=len(valid), with_recent_flow=int((signed > 0).sum()),
                                against_recent_flow=int((signed < 0).sum()), flat=int((signed == 0).sum()),
                                mean_recent_flow_oriented_change=signed.mean(),
                                instances=';'.join(g.instance)))
    save('setup-crosstabs.csv', records)


def main():
    opportunities = pd.read_csv(OUT / 'opportunities.csv.gz', dtype={'instance': str, 'anchor_ns': str, 'cutoff_ns': str})
    outcomes = pd.read_csv(OUT / 'outcomes.csv.gz', dtype={'instance': str})
    field_screen(opportunities, outcomes)
    original_messages(opportunities)
    setup_details(opportunities, outcomes)
    print('Relationship screen and original message extracts saved.')


if __name__ == '__main__':
    main()
