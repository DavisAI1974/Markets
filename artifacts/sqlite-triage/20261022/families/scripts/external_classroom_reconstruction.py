"""Reconstruct the original external classroom scope from saved primary rows.

This reproduces the original source-file-relative series definitions. Expanded
history features must use separate, explicitly reconciled target/vintage keys.
"""
import ast
import bisect
import hashlib
import json
import math
import os
import pathlib
import re
import sqlite3


def value_state(value):
    if value is None:
        return 1, None, 'VALUE_IS_NULL_IN_DAY_FILE'
    if isinstance(value, bool):
        return 2, None, 'NOT_NUMERIC: '+repr(value)
    if isinstance(value, (int, float, str)):
        try:
            number = float(value)
        except ValueError:
            return 2, None, 'NOT_NUMERIC: '+repr(value)
        if math.isfinite(number):
            return 0, number, None
        return 2, None, 'NOT_FINITE: '+repr(value)
    return 2, None, 'NOT_NUMERIC: '+type(value).__name__


def select_known(rows, column, where, cutoff):
    known = []
    for ordinal, row in enumerate(rows):
        stamp = row['published_ns']
        assert type(stamp) is int
        if stamp > cutoff or not all(row[k] == v for k, v in (where or {}).items()):
            continue
        code, value, reason = value_state(row[column])
        known.append(dict(published_ns=stamp, state=code, value=value,
                          reason=reason, source_ordinal=ordinal, row=row))
    # Python's stable ordering preserves source ordinal within equal stamps.
    return sorted(known, key=lambda k: k['published_ns'])


def align_known(known, timestamp):
    index = bisect.bisect_right([k['published_ns'] for k in known], timestamp)-1
    return (index, known[index]['state'], known[index]['value']) if index >= 0 else (-1, 1, None)


def claim_relation(premise):
    match = re.search(r'end this window (SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED) first-to-last', premise)
    if not match:
        raise ValueError('Claim does not declare its endpoint relation')
    return match[1]


def main():
    base = pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR', '/opt/frankie-box/work/family-research-20261022'))
    audit = base/'full-context-audit'
    out = base/'external-classroom-audit-v1'
    out.mkdir(exist_ok=True)
    target = out/'original_series_known_values.json'
    assert not target.exists(), 'Reconstruction inputs are immutable'
    source = pathlib.Path('/opt/frankie-box/work/source-indexed-consumers-20261021/research/kalshi/frankie_boss/operations/frankie_day_external.py')
    raw = source.read_bytes()
    tree = ast.parse(raw)
    assignments = [n for n in tree.body if isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id == 'SEARCH_SERIES' for t in n.targets)]
    assert len(assignments) == 1
    specs = list(ast.literal_eval(assignments[0].value))
    assert len(specs) == 30
    # Receipt source is retained without importing/activating any runtime.
    (out/source.name).write_bytes(raw)
    cutoff = 1697662799696377528
    db = sqlite3.connect('file:'+str(base/'alignment.sqlite')+'?mode=ro', uri=True)
    tables = {r[0]: json.loads(r[1]) for r in db.execute('SELECT name,columns_json FROM external_point')}
    rows = {}
    for point in tables:
        rows[point] = [json.loads(r[0]) for r in db.execute(
            'SELECT row_json FROM external_row WHERE point_name=? ORDER BY source_ordinal', (point,))]
    assert sum(map(len, rows.values())) == 329658
    stations = sorted({r['station'] for r in rows['weather.obs_hourly'] if r['published_ns'] <= cutoff}, key=str)
    specs += [('weather.tmpf.'+str(station), 'weather.obs_hourly', 'tmpf', {'station':station}) for station in stations]
    series = []
    for name, point, column, where in specs:
        known = select_known(rows[point], column, where, cutoff) if point in rows and column in tables[point] else []
        series.append(dict(name=name, table=point, column=column, where=where, known=known,
                           absent_reason=None if point in tables and column in tables[point] else 'TABLE_OR_COLUMN_UNAVAILABLE'))
    assert len(series) == 48 and sum(len(s['known']) for s in series) == 211055
    claims = json.loads((audit/'runtime-knowledge/external_classroom_claims.json').read_text())
    for claim in claims:
        claim['declared_endpoint_relation'] = claim_relation(claim['premise'])
    assert len(claims) == 441
    target.write_text(json.dumps(dict(series=series, claims=claims), separators=(',', ':'), allow_nan=False)+'\n')
    receipt = dict(schema='ORIGINAL_EXTERNAL_CLASSROOM_RECONSTRUCTION_V1', status='complete', coverage_gate='NOT_PASSED',
                   cutoff_ns=cutoff, primary_day_file_sha256='d006252d605432994909a52e75fcbfe7cec3e42990a98c02e91e1f65212f0bc7',
                   series=len(series), values_known=sum(len(s['known']) for s in series), claims=len(claims),
                   reader_source_path=str(source), reader_source_sha256=hashlib.sha256(raw).hexdigest(),
                   input_bytes=target.stat().st_size, input_sha256=hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),
                   source='existing primary external_row; original stable source order and source-file-relative SEARCH_SERIES',
                   rule='published_ns <= cutoff; per Dipole row published_ns <= receive_ns; equal stamps retain last original source row',
                   limitations=['No expanded external history is substituted into original classroom reproduction.',
                                'Source publication stamps are historical declarations, not proof of live capture.',
                                'These reconstructed inputs have not been fitted.'])
    (out/'reconstruction_input_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__': main()
