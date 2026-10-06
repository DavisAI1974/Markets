"""Search candidates as claims for the scientific teacher: the discovery row projected, never re-read as its own check.

CCode step #4 (HANDOFF_20261006_CCODE_STEP4.md). `Run.search_knowledge` (frankie_box_experiment.py) retains every
beyond-chance coupling row of a day's search individually, with its part/row provenance, as FRANKIE_SEARCH_FINDINGS_V1
(`knowledge-findings.json` beside the search MANIFEST, carried into the brain entry <day>-search). Those rows are
CANDIDATES: a count beyond its own chance check on one day. Nothing in the repository turned them into claims the
scientific teacher could test on another owner's complete search; this module is that projection and nothing more.

Each candidate becomes one claim in the exact shape `frankie_box_scientific_teacher.test` already consumes for Jev's,
Frankie's and the historical claims, with these differences made explicit:
  - series are the search's own names and are matched EXACTLY (`series_exact`); the fuzzy matcher that reads free-text
    claim names must not broaden `frames.mid` to every series containing it;
  - the direction, lag, transform pair and cell are the row's own: direction = the way the counts pointed (same_way
    versus opposite), lag = the row's best_lag in the row's x -> y orientation, cell = '<column>=<value>' or 'whole-day';
  - `origin` names the discovery day, its search manifest, part and row hashes. The scientific teacher lists the origin
    day's rows as ORIGIN EVIDENCE, never as a test: reading the discovery row again is not an independent check, and a
    second use of the same evidence is not another occurrence (Greg, 2026-10-06).
No chance threshold, formula, pooling, rarity gate or acceptance rule is added here: the counts travel in `source_claim`,
the test is the existing one, and acceptance/survivor treatment is the pending step #5 discussion.
The claims_sha256 binds the exact findings file bytes, so a lessons file answers exactly these candidates.
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_SEARCH_FINDINGS_V1'
AUTHOR = 'search'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def cell_label(cell, cell_value):
    """The cell exactly as the scientific teacher's row labels spell it (row_scope_reasons)."""
    return str(cell) if cell_value is None else '%s=%s' % (cell, cell_value)


def candidate_claims(path):
    """The claims document (author 'search') of one FRANKIE_SEARCH_FINDINGS_V1 file: one claim per retained row.

    Same keys as jev_claims/frankie_claims/historical_claims, plus series_exact and origin. Raises on another schema or
    on a row whose part/row provenance is missing; a candidate without exact provenance is not projected.
    """
    path = Path(path)
    raw = path.read_bytes()
    return candidate_claims_doc(json.loads(raw), claims_sha256=sha256_bytes(raw), source=str(path))


def candidate_claims_doc(doc, *, claims_sha256, source):
    """The same projection from an already loaded document, e.g. the findings carried inline in the brain entry
    <day>-search (FRANKIE_STAGE_KNOWLEDGE_V1 sources[i].content); claims_sha256 is that source's recorded sha256."""
    if doc.get('schema') != SCHEMA:
        raise ValueError('%s is not a %s' % (source, SCHEMA))
    day = str(doc['day'])
    manifest_sha256 = doc['manifest_sha256']
    claims = []
    for finding in doc.get('findings') or []:
        row = finding['content']
        for key in ('part', 'part_sha256', 'row', 'row_sha256'):
            if finding.get(key) is None:
                raise ValueError('search candidate without %s provenance on %s' % (key, day))
        if not row.get('beyond_chance'):
            raise ValueError('a retained search finding is not beyond its own chance check: %s row %s' % (finding['part'], finding['row']))
        x, y = row['x'], row['y']
        same, opposite = int(row['same_way']), int(row['opposite'])
        direction = 'same' if same > opposite else 'opposite' if opposite > same else None
        tx, ty = row.get('x_transform', row.get('transform', 'sign_of_step')), row.get('y_transform', 'sign_of_step')
        cell = cell_label(row['cell'], row.get('cell_value'))
        claim_id = 'search:%s:%s:%d' % (day, finding['part_sha256'][:12], int(finding['row']))
        statement = ('Search candidate of %s (%s): %s (%s) and %s (%s) moved the same way %d times and the opposite way '
                     '%d times at lag %d (x leads y at a positive lag) over %d steps, with %d of %d far shifts reaching the '
                     'count; a count on one day, not a finding by itself' % (
                         day, cell, x, tx, y, ty, same, opposite, int(row['best_lag']), int(row['steps']),
                         int(row['null_at_or_beyond']), int(row['null_shifts'])))
        claims.append(dict(
            id=claim_id, statement=statement, kind='search_candidate', series=[x, y], series_exact=True,
            direction=direction,
            direction_text='search counts on %s: same %d, opposite %d' % (day, same, opposite),
            lag=int(row['best_lag']), cells=[cell], condition=None, x_transform=tx, y_transform=ty,
            day_made=day,
            origin=dict(day=day, search_manifest_sha256=manifest_sha256, part=finding['part'],
                        part_sha256=finding['part_sha256'], row=int(finding['row']), row_sha256=finding['row_sha256'],
                        rule='the discovery row is origin evidence; the scientific teacher never counts it as a test'),
            source_claim=row))
    ids = [c['id'] for c in claims]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate search candidate identity in %s' % source)
    return dict(author=AUTHOR, stamp='candidates-' + manifest_sha256[:12], day=day, claims_sha256=claims_sha256,
                source=str(source), source_manifest_sha256=manifest_sha256,
                source_note='every beyond-chance row of the day search, individually; counts retained in source_claim; '
                            'the origin day is evidence, not a test (R06, R15)',
                claims=claims)
