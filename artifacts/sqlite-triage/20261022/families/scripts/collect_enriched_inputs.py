"""One indexed extraction batch for all agreed additions, before the final Julia run.

Uses existing verified sources read-only. No reconstruction, whole-ledger scans,
forecast backdating, terminal-to-birth backfill, or source-null zero imputation.
"""
import bisect
import collections
import csv
import gzip
import hashlib
import json
import os
import pathlib
import sqlite3
import statistics
import struct
from concurrent.futures import ThreadPoolExecutor
from enrichment_rules import eligible, flatten

BASE = pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR', '/opt/frankie-box/work/family-research-20261022'))
OLD = BASE / 'descriptive-v1'
OUT = BASE / 'enriched-v2'
OUT.mkdir(exist_ok=True)
db = sqlite3.connect(f'file:{BASE / "alignment.sqlite"}?mode=ro', uri=True)
db.row_factory = sqlite3.Row


def readcsv(name):
    return list(csv.DictReader((OLD / (name + '.csv')).open()))


def writecsv(name, fields, rows):
    with (OUT / (name + '.csv')).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class Indexed:
    def __init__(self, name):
        self.pin = dict(db.execute('SELECT * FROM source_registry WHERE name=?', (name,)).fetchone())
        self.fd = os.open(self.pin['path'], os.O_RDONLY)
        self.ix = os.open(self.pin['offset_index'], os.O_RDONLY)
        with open(self.pin['offset_index'], 'rb') as f:
            self.header = json.loads(f.readline())
            self.head = f.tell()
        assert self.header['byteorder'] == 'little'

    def read(self, ordinal):
        pair = os.pread(self.ix, 16, self.head + 8 * ordinal)
        if len(pair) != 16:
            raise ValueError('source ordinal outside pinned index')
        lo, hi = struct.unpack('<QQ', pair)
        raw = os.pread(self.fd, hi - lo, lo)
        assert len(raw) == hi - lo
        return json.loads(raw), lo, hi - lo, hashlib.sha256(raw).hexdigest()


samples = readcsv('samples')
samplemap = {r['sample_id']: r for r in samples}
contexts = readcsv('group_context_receipts')
second = os.open('/opt/frankie-box/work/experiment-teacher-rows/20231018/host-dipole-classroom-source.c15.rows.jsonl', os.O_RDONLY)
offsets = sorted({int(c['source_offset']) for c in contexts})
ix = {o: dict(db.execute('SELECT * FROM second_set_clock WHERE source_offset=?', (o,)).fetchone()) for o in offsets}


def second_read(offset):
    r = ix[offset]
    raw = os.pread(second, r['source_length'], offset)
    assert hashlib.sha256(raw).hexdigest() == r['row_sha256']
    j = json.loads(raw)
    assert j['key']['input_cursor'] == r['input_cursor']
    assert j['clocks']['clock_event_known_by'] == r['known_by_ns']
    return offset, {'key': j['key'], 'clocks': j['clocks'],
                    'flow_substrate': j.get('flow_substrate'),
                    'lifecycle_refs': [x for x in j['clocks']['clock_feature_availability'] if x[0] == 'native.lifecycle'],
                    'source_keys': list(j)}


with ThreadPoolExecutor(max_workers=8) as pool:
    source = dict(pool.map(second_read, offsets))
os.close(second)
print('Second-set clocks and lifecycle references extracted:', len(source), flush=True)
lifecycle = Indexed('native.lifecycle')
member = Indexed('native.member')
ordinals = sorted({int(ref[1]) for r in source.values() for ref in r['lifecycle_refs']})
with ThreadPoolExecutor(max_workers=8) as pool:
    life = dict(zip(ordinals, pool.map(lifecycle.read, ordinals)))
with gzip.open(OUT / 'lifecycle_original_rows.jsonl.gz', 'wt') as f:
    for ordinal, (row, offset, length, digest) in life.items():
        f.write(json.dumps({'source_ordinal': ordinal, 'source_path': lifecycle.pin['path'],
                            'source_offset': offset, 'source_length': length,
                            'row_sha256': digest, 'row': row}, separators=(',', ':')) + '\n')
with gzip.open(OUT / 'second_set_clock_flow_receipts.jsonl.gz', 'wt') as f:
    for offset, row in source.items():
        f.write(json.dumps({'source_offset': offset, **row}, separators=(',', ':')) + '\n')

measurements = []
links = []
quality = []
inventory = collections.Counter()
sections = collections.Counter()
rejected = 0


def paths(obj, prefix=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from paths(v, f'{prefix}.{k}' if prefix else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from paths(v, prefix + '[]')
    else:
        yield prefix, obj


for ordinal, (row, _, _, _) in life.items():
    sec = row.get('emitting_section', 'unknown')
    sections[sec] += 1
    for path, value in paths(row):
        inventory[(sec, path, type(value).__name__)] += 1

for c in contexts:
    s = samplemap[c['sample_id']]
    values = collections.defaultdict(list)
    selected = source[int(c['source_offset'])]
    sec_counts = collections.Counter()
    for _, ordinal, known, *_ in selected['lifecycle_refs']:
        row, offset, length, digest = life[int(ordinal)]
        emission = row.get('frankie_emission', {})
        cursor = emission.get('input_cursor', int(c['input_cursor']))
        instrument = row.get('instrument_id', emission.get('instrument_id'))
        if instrument is None:
            raise ValueError('lifecycle receipt lacks instrument')
        ok = eligible(int(known), int(cursor), int(instrument), int(c['cutoff_ns']), int(s['cursor_cap']), int(s['instrument_id']))
        # Some source rows have their own event and emission clocks; never ignore a later emission.
        own_known = max(int(known), int(row.get('emitted_at_recv_ns') or known), int(emission.get('ts_recv_ns') or known))
        ok = ok and own_known <= int(c['cutoff_ns'])
        sec = str(row.get('emitting_section', 'unknown'))
        side = str(row.get('side', 'UNSPECIFIED'))
        links.append(dict(sample_id=c['sample_id'], lag_s=c['lag_s'], cutoff_ns=c['cutoff_ns'],
                          target_family_id=s['family_id'], observed_family_id=row.get('family_id'),
                          section=sec, side=side, lifecycle_ordinal=ordinal, source_offset=offset,
                          source_length=length, known_by_ns=known, own_known_by_ns=own_known,
                          input_cursor=cursor, instrument_id=instrument, eligible=int(ok),
                          row_sha256=digest, observation_age_s=(int(c['cutoff_ns'])-own_known)/1e9))
        if not ok:
            rejected += 1
            continue
        sec_counts[sec] += 1
        for path, value in flatten(row):
            values[f'lifecycle.{sec}.{side}.{path}.mean'].append(value)
        for key in ['terminal_status', 'terminal_basis', 'censored', 'resolved', 'continuity_segment',
                    'disposition', 'observation', 'queue_scope', 'stratum_basis', 'liquidity_kind',
                    'liquidity_kind_basis', 'refill_attribution', 'self_restoration_policy',
                    'touch_disposition', 'clock', 'exit_stratum_available', 'price_relation_basis']:
            if key in row:
                quality.append(dict(sample_id=c['sample_id'], lag_s=c['lag_s'], section=sec,
                                    lifecycle_ordinal=ordinal, field=key, value=json.dumps(row[key])))
    # These are receipt emission counts, not imputed absent lifecycle measurements.
    for sec in sections:
        values[f'lifecycle.{sec}.emission_count'].append(float(sec_counts[sec]))
    for feature, observed in values.items():
        measurements.append(dict(sample_id=c['sample_id'], lag_s=c['lag_s'], feature=feature,
                                 value=statistics.mean(observed), observed_n=len(observed),
                                 age_s=c['age_s'], source_ordinal=c['source_ordinal'],
                                 reason='known_completed_group_emissions_only'))

writecsv('lifecycle_context_links', list(links[0]) if links else ['sample_id'], links)
writecsv('lifecycle_quality_dispositions', list(quality[0]) if quality else ['sample_id'], quality)
writecsv('lifecycle_field_inventory', ['section', 'path', 'source_type', 'observed_rows'],
         (dict(section=k[0], path=k[1], source_type=k[2], observed_rows=n) for k, n in sorted(inventory.items())))
writecsv('added_context_measurements', list(measurements[0]), measurements)
print('Lifecycle unique rows, links, rejected:', len(life), len(links), rejected, flush=True)

# Preserve continuity/anchor/source quality at each unique already selected native group.
member_ordinals = sorted({int(c['source_ordinal']) for c in contexts})
quality_keys = ['frankie_emission', 'continuity_segment', 'session_phase', 'source_day',
                'source_day_role', 'integrity', 'observation', 'availability', 'missing',
                'side_orientation', 'family_id', 'structure']
native_quality = {}
with gzip.open(OUT / 'native_quality_contexts.jsonl.gz', 'wt') as f:
    for ordinal in member_ordinals:
        j, offset, length, digest = member.read(ordinal)
        row = {k: j[k] for k in quality_keys if k in j}
        row['activity_anchor_quality'] = {k: {a: b for a, b in v.items() if a.startswith('anchor_') or a in ['receive_order_clean', 'side_orientation']} for k, v in j.get('activity_since', {}).items()}
        native_quality[ordinal] = row
        f.write(json.dumps(dict(source_ordinal=ordinal, source_offset=offset,
                               source_length=length, row_sha256=digest, quality=row), separators=(',', ':')) + '\n')
print('Native continuity, anchor and structural provenance retained:', len(native_quality), flush=True)

# Extended external alignment: every retained table, exact separate dimensional series,
# complete original row JSON, and immediate prior vintage as a separately named observation.
dimensions = {'mos.gw_by_cycle': ['model', 'horizon_days', 'target_day'],
              'weather.obs_hourly': ['station'],
              'curve.settled_shape': ['front_symbol', 'next_symbol', 'back_rank'],
              'curve.traded_shape': ['front_symbol', 'next_symbol', 'back_rank'],
              'curve.month_trades': ['instrument_id', 'symbol'],
              'curve.month_statistics': ['instrument_id', 'symbol']}
ext = collections.defaultdict(list)
for r in db.execute('SELECT * FROM external_row ORDER BY published_ns,source_ordinal'):
    j = json.loads(r['row_json'])
    # Unknown tables stay intact but get no numerical interpretation.
    dims = dimensions.get(r['point_name'], [])
    key = r['point_name'] + '|' + '|'.join(f'{k}={j.get(k)}' for k in dims)
    ext[key].append(dict(r))
with gzip.open(OUT / 'external_extended_asof.jsonl.gz', 'wt') as f:
    ext_n = 0
    missing_ext = collections.Counter()
    for key, rows in sorted(ext.items()):
        times = [r['published_ns'] for r in rows]
        for c in contexts:
            i = bisect.bisect_left(times, int(c['cutoff_ns'])) - 1
            for vintage in [0, 1]:
                r = rows[i-vintage] if i-vintage >= 0 else None
                if r is None:
                    missing_ext[(key, vintage)] += 1
                else:
                    assert r['published_ns'] < int(c['cutoff_ns'])
                f.write(json.dumps(dict(sample_id=c['sample_id'], lag_s=int(c['lag_s']),
                                        cutoff_ns=int(c['cutoff_ns']), series=key,
                                        vintage_offset=vintage, source=r,
                                        disposition='observed_published_row' if r else 'no_prior_publication'), separators=(',', ':'))+'\n')
                ext_n += 1
writecsv('external_extended_availability', ['series', 'vintage_offset', 'context_n', 'missing_publication_n'],
         (dict(series=k, vintage_offset=v, context_n=len(contexts), missing_publication_n=missing_ext[(k,v)]) for k in sorted(ext) for v in [0,1]))
print('External extended as-of rows:', ext_n, flush=True)

# Same-instrument quote endpoints at the already specified outcome horizons.
# Outcomes only: never appended to predictors. Exact known group and cursor AND bounds.
groups = collections.defaultdict(list)
for r in db.execute('SELECT * FROM group_event ORDER BY recv_ns,input_cursor'):
    groups[int(r['instrument_id'])].append(dict(r))
keys = {k: [(r['recv_ns'], r['input_cursor']) for r in v] for k, v in groups.items()}
cache = {}
quote_checks = 0


def quote_at(inst, t, cap):
    global quote_checks
    g = groups[inst]
    if t < g[0]['recv_ns'] or t > g[-1]['recv_ns']:
        return dict(disposition='outside_retained_group_bounds')
    i = bisect.bisect_right(keys[inst], (t, cap)) - 1
    while i >= 0 and g[i]['input_cursor'] > cap:
        i -= 1
    if i < 0:
        return dict(disposition='no_prior_same_instrument_group')
    r = g[i]
    ordinal = r['source_ordinal']
    if ordinal not in cache:
        j, offset, length, digest = member.read(ordinal)
        assert int(j['instrument_id']) == inst
        assert int(j['frankie_emission']['input_cursor']) == r['input_cursor']
        b = j['book']
        for side in ['bid_levels', 'ask_levels']:
            for level in b[side]:
                assert abs(level['price'] - level['price_raw']/1e9) < 1e-10
                quote_checks += 1
        bid, ask = b.get('best_bid'), b.get('best_ask')
        spread = b.get('spread')
        if all(isinstance(v, (int, float)) for v in [bid, ask, spread]):
            assert abs(ask-bid-spread) < 1e-10
        cache[ordinal] = dict(best_bid=bid, best_ask=ask, spread=spread,
                              mid=(bid+ask)/2 if bid is not None and ask is not None else None,
                              source_ordinal=ordinal, source_offset=offset, source_length=length,
                              row_sha256=digest, known_by_ns=r['recv_ns'], input_cursor=r['input_cursor'])
    assert r['recv_ns'] <= t and r['input_cursor'] <= cap
    return dict(cache[ordinal], age_s=(t-r['recv_ns'])/1e9, disposition='observed_quote')


with gzip.open(OUT / 'quote_endpoint_receipts.jsonl.gz', 'wt') as f:
    qn = 0
    for s in samples:
        if s['phase'] not in ['onset', 'near_before', 'near_after']:
            continue
        t, cap, inst = int(s['cutoff_ns']), int(s['cursor_cap']), int(s['instrument_id'])
        for horizon in [1, 5, 20, 60, 120, 300, 600, 1800, 3600]:
            a = quote_at(inst, t, cap)
            b = quote_at(inst, t+horizon*10**9, 2**63-1)
            f.write(json.dumps(dict(sample_id=s['sample_id'], family_id=s['family_id'], phase=s['phase'],
                                    horizon_s=horizon, instrument_id=inst,
                                    chronological_quarter=int(s['chronological_quarter']),
                                    from_quote=a, to_quote=b), separators=(',', ':'))+'\n')
            qn += 1
print('Quote endpoint windows and source unit checks:', qn, quote_checks, flush=True)
receipt = dict(schema='FAMILY_ENRICHED_INPUTS_V2', contexts=len(contexts), families=749,
               historical_points=13, plane_registry_roles=99, second_set_source_rows=771787,
               unique_second_set_offsets=len(source), lifecycle_unique_rows=len(life),
               lifecycle_context_links=len(links), rejected_future_or_instrument_links=rejected,
               lifecycle_sections=dict(sections), added_numeric_rows=len(measurements),
               native_quality_groups=len(native_quality), external_series=len(ext),
               extended_external_rows=ext_n, quote_windows=qn, quote_unit_checks=quote_checks,
               quote_unique_groups=len(cache), source_pins=[dict(r) for r in db.execute('SELECT * FROM source_registry')],
               limits=['Lifecycle measurements are observed emissions at selected completed groups, not continuous hidden state or original order births.',
                       'No emission count is distinct from a missing queue/absorption/refill measurement.',
                       'Full lifecycle rows, statuses, IDs and clocks retained as provenance; only allowlisted measurements summarized.',
                       'Source-null and unverified omitted dictionary keys are not zero-imputed.',
                       'Unverified ladder price units omitted from numerical features; original fields retained.',
                       'All 20 external tables retained; only the documented 13-concept field definitions are analytically interpreted.',
                       'No fabricated calendar history, pre-session trades, completed steps, new market days, or post-session flat returns.'])
(OUT/'enrichment_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['source_pins','limits']}), flush=True)
