"""The scientific teacher's turn: every claim tested on the search's counts, day by day, and the lessons written.

Greg, 2026-09-29. Spec: research/kalshi/frankie_boss/SPEC-scientific-teacher.md (the scientific teacher IS the
experiment's search; no model seat, rule R17) and SPEC-experiment-orchestrator.md (sections "Jev" and "His brain").
Code only; no model call.

Takes, each labelled with its author (rule R11: claims, never truth):
  - Jev's claims: JEV_CLAIMS_V1 (clm_sidecar/sit_in.py), each naming its series, direction, lag and cells;
  - Frankie's claims: ONLY the novel findings of his classroom ledgers (dipole_novel_findings). The rest of his ledgers,
    his analysis and his answers are his reasoning and are never read here (rule R09);
  - the historical Dipole claims: HISTORICAL_CLAIMS_V1 (frankie_box_historical_claims.py, committed), author 'historical'.
and the search's results for every DISCOVERY day given (frankie_box_experiment_search.py outputs; a confirmation day is
refused: R15). A claim made on one day is tested on every discovery day given, and each day is reported on its own
(never pooled).

For each claim: its series names are matched to the search's series (normalized names; every match listed, an unmatched
name listed as "not in the search"); for each matched pair and each day, the coupling rows (whole-day and every cell)
are read whole and reported as their counts: same_way, opposite, both_moving, best lag, the chance check's shifts and
how many reached the observed count. Where the claimed direction is stated in a testable form, each day is marked:
  held       beyond chance and moving the claimed way;
  shown_otherwise  beyond chance and moving the other way -> the challenge, worded "the data is showing this instead";
  unresolved not beyond chance, or no claimed direction to compare.
  counts_only  a row on another transform pair than the claim's (x_transform, y_transform; default sign_of_step on
             both sides): its counts are reported, it is never marked.
The disposition word (SUPPORTED_SCOPED, CONTRADICTED_SCOPED, PLAUSIBLE_UNRESOLVED, INSUFFICIENT_EVIDENCE, the words of
dipole_scientific_review) is orientation only (R14); the counts and days are the finding. Lags outside the search's
window, cells the search did not run, transforms it did not run and series it does not carry are listed under
untested / cannot_test_yet, never dropped.

Writes, per author, one lessons file bound to the exact claims it answers (claims_sha256):
  JEV_LESSONS_V1      -> Jev's brain (clm-sidecar/jev-brain/lessons/<day>-<stamp>.json; uploaded through the presigned
                         slot in MAP_URL when given, since the box writes nothing in S3), read on his next day;
  FRANKIE_LESSONS_V1  -> kept under /opt/frankie-box/work/experiment-teacher/ and filed into Frankie's brain as the entry
                         <brain>/<day>-lessons/ (frankie_box_brain.write_lessons_entry), read by every later cycle.
  HISTORICAL_LESSONS_V1 -> kept under /opt/frankie-box/work/experiment-teacher/historical/<days>-<catalog sha12>.json,
                         the historical catalog's claims (frankie_box_historical_claims.py) tested on the days given;
                         into nobody's brain here (which material carries it is the classroom step's).
                         Neither ever carries the other's claims.
"""
import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path('/opt/frankie-box/work/experiment-teacher')
DISPOSITIONS = ('SUPPORTED_SCOPED', 'PLAUSIBLE_UNRESOLVED', 'CONTRADICTED_SCOPED', 'INSUFFICIENT_EVIDENCE')
SAME_WORDS = ('same', 'together', 'positive', 'aligned', 'co-move', 'comove', 'both rise', 'both fall', 'with')
OPPOSITE_WORDS = ('opposite', 'inverse', 'negative', 'against', 'contrary', 'diverge')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def norm(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def claimed_direction(text):
    """'same' | 'opposite' | None, from the claim's own words; None = not stated in a testable form (listed)."""
    t = str(text or '').lower()
    opposite = any(w in t for w in OPPOSITE_WORDS)
    same = any(w in t for w in SAME_WORDS)
    return 'opposite' if opposite and not same else 'same' if same and not opposite else None


def claimed_lag(text):
    match = re.search(r'-?\d+', str(text or ''))
    return int(match.group(0)) if match else None


def jev_claims(path):
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'JEV_CLAIMS_V1':
        raise SystemExit('%s is not a JEV_CLAIMS_V1' % path)
    claims = [dict(id=c['id'], statement=c.get('statement'), kind=c.get('kind'), series=list(c.get('series') or []),
                   direction=claimed_direction(c.get('direction')), direction_text=c.get('direction'),
                   lag=claimed_lag(c.get('lag')), cells=list(c.get('cells') or []), day_made=doc.get('day'))
              for c in doc.get('claims') or []]
    return dict(author='jev', stamp=doc.get('stamp'), day=doc.get('day'), claims_sha256=sha256_bytes(raw),
                source=str(path), claims=claims)


def historical_claims(path):
    """HISTORICAL_CLAIMS_V1 (frankie_box_historical_claims.py): the catalog's claims, author 'historical'; only its
    claims are tested, its not_testable list travels with the lessons by reference (claims_source)."""
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'HISTORICAL_CLAIMS_V1':
        raise SystemExit('%s is not a HISTORICAL_CLAIMS_V1' % path)
    claims = [dict(id=c['id'], statement=c['statement'], kind='historical', series=list(c['series']),
                   direction=c.get('direction') if c.get('direction') in ('same', 'opposite') else None,
                   direction_text=c.get('direction'), lag=claimed_lag(c.get('lag')), cells=list(c.get('cells') or []),
                   condition=c.get('condition'), x_transform=c.get('x_transform', 'sign_of_step'),
                   y_transform=c.get('y_transform', 'sign_of_step'), source=c.get('source'), day_made=None)
              for c in doc.get('claims') or []]
    return dict(author='historical', stamp=doc['catalog_sha256'][:12], day=None, claims_sha256=sha256_bytes(raw),
                source=str(path), claims=claims)


def frankie_claims(path, day):
    """Only the novel findings of Frankie's classroom ledgers (R09: nothing else of his is read)."""
    raw = Path(path).read_bytes()
    ledgers = json.loads(raw)
    findings = ledgers.get('dipole_novel_findings') or []
    claims = []
    for f in findings:
        refs = f.get('evidence_refs') or []
        series = [x for r in refs for x in (r.get('left'), r.get('right')) if x]
        premise = f.get('premise') or ''
        same = re.search(r'same way (\d+) times', premise)
        opposite = re.search(r'opposite way (\d+) times', premise)
        direction = None
        if same and opposite:
            s, o = int(same.group(1)), int(opposite.group(1))
            direction = 'same' if s > o else 'opposite' if o > s else None
        claims.append(dict(id=f.get('finding_id'), statement=premise, kind='novel_finding', series=series,
                           direction=direction, direction_text='step counts in the finding: same %s, opposite %s' % (
                               same.group(1) if same else '?', opposite.group(1) if opposite else '?'),
                           lag=None, cells=[], day_made=day))
    return dict(author='frankie', stamp=None, day=day, claims_sha256=sha256_bytes(json.dumps(findings, sort_keys=True).encode()),
                source=str(path), source_note='only dipole_novel_findings read (R09)', claims=claims)


def load_searches(dirs):
    days = []
    for d in dirs:
        d = Path(d)
        manifest = json.loads((d / 'MANIFEST.json').read_bytes())
        if manifest.get('day_role') != 'discovery':
            raise SystemExit('%s is a %s search: the teacher works on discovery days only (R15)' % (d, manifest.get('day_role')))
        days.append(dict(dir=d, day=manifest['day'], cycle=manifest['cycle'], lags=manifest['lags'],
                         series=manifest['series'], cells=[tuple(c) for c in manifest['cells']],
                         parts=[d / p['path'] for p in manifest['couplings']['parts']],
                         manifest_sha256=sha256_bytes((d / 'MANIFEST.json').read_bytes())))
    if len({x['day'] for x in days}) != len(days):
        raise SystemExit('the same day was given twice (duplicate data declines the run)')
    return days


def match(name, series):
    """Every search series the claimed name matches (normalized: equal to the whole name, to its part after the source,
    or contained in it); [] = not in the search."""
    n = norm(name)
    if not n:
        return []
    out = []
    for s in series:
        whole, tail = norm(s), norm(s.split('.', 1)[-1])
        if n in (whole, tail) or (len(n) >= 4 and (n in whole)):
            out.append(s)
    return out


def test(claims_doc, days):
    wanted = {}
    per_claim = []
    for c in claims_doc['claims']:
        matched, missing = {}, []
        for name in c['series']:
            hits = sorted({s for d in days for s in match(name, d['series'])})
            (matched.__setitem__(name, hits) if hits else missing.append(name))
        pairs = sorted({(a, b) for i, x in enumerate(c['series']) for y in c['series'][i + 1:]
                        for a in matched.get(x, []) for b in matched.get(y, []) if a != b})
        for a, b in pairs:
            wanted[(a, b)] = wanted[(b, a)] = True
        per_claim.append((c, matched, missing, pairs))
    rows = {}
    for d in days:
        for part in d['parts']:
            with open(part) as handle:
                for line in handle:
                    r = json.loads(line)
                    if (r['x'], r['y']) in wanted:
                        rows.setdefault((d['day'], r['x'], r['y']), []).append(r)
    results = []
    for c, matched, missing, pairs in per_claim:
        tests, verdicts, challenges = [], [], []
        for d in days:
            for a, b in pairs:
                for x, y in ((a, b), (b, a)):
                    for r in rows.get((d['day'], x, y), []):
                        observed = 'same' if r['same_way'] > r['opposite'] else 'opposite' if r['opposite'] > r['same_way'] else 'even'
                        tx, ty = r.get('x_transform', r.get('transform', 'sign_of_step')), r.get('y_transform', 'sign_of_step')
                        if (tx, ty) != (c.get('x_transform', 'sign_of_step'), c.get('y_transform', 'sign_of_step')):
                            mark = 'counts_only'          # another transform pair than the claim's: reported, not marked
                        elif c['direction'] is None or not r['beyond_chance']:
                            mark = 'unresolved'
                        elif observed == c['direction']:
                            mark = 'held'
                        else:
                            mark = 'shown_otherwise'
                            challenges.append(
                                'the data is showing this instead: on %s (%s%s), %s and %s moved the same way %d times and '
                                'the opposite way %d times at lag %d (x leads y at a positive lag), beyond all %d far shifts; '
                                'the claim said %s' % (d['day'], r['cell'], '' if r['cell_value'] is None else '=%s' % r['cell_value'],
                                                     x, y, r['same_way'], r['opposite'], r['best_lag'], r['null_shifts'], c['direction']))
                        verdicts.append(mark)
                        tests.append(dict(day=d['day'], x=x, y=y, cell=r['cell'], cell_value=r['cell_value'],
                                          transform=r['transform'], x_transform=tx, y_transform=ty,
                                          lag=r['best_lag'], steps=r['steps'],
                                          counts=dict(same_way=r['same_way'], opposite=r['opposite'], both_moving=r['both_moving'],
                                                      x_moves=r['x_moves'], y_moves=r['y_moves']),
                                          chance_check=dict(shifts=r['null_shifts'], reached=r['null_at_or_beyond'],
                                                            largest=r['null_largest'], exclusion=r['null_exclusion']),
                                          mark=mark, days_named=[d['day']]))
        held, other = verdicts.count('held'), verdicts.count('shown_otherwise')
        disposition = ('INSUFFICIENT_EVIDENCE' if not tests else 'SUPPORTED_SCOPED' if held and not other
                       else 'CONTRADICTED_SCOPED' if other and not held else 'PLAUSIBLE_UNRESOLVED')
        untested = []
        if c['lag'] is not None and days and abs(c['lag']) > min(d['lags'] for d in days):
            untested.append('the claimed lag %d is outside the searched window of +-%d' % (c['lag'], min(d['lags'] for d in days)))
        for cell in c['cells']:
            if not any(norm(cell) in norm('%s %s' % cv) for d in days for cv in d['cells']):
                untested.append('the claimed cell "%s" was not a cell of the search' % cell)
        if c.get('condition'):
            untested.append('the claimed condition "%s" is not applied by the search (conditions not searched yet): the '
                            'counts are over every step of the cell' % c['condition'])
        if c['direction'] is None:
            untested.append('no direction stated in a testable form ("%s"): counts reported, nothing marked held' % c['direction_text'])
        claimed = (c.get('x_transform', 'sign_of_step'), c.get('y_transform', 'sign_of_step'))
        if not any(t['x_transform'] == claimed[0] and t['y_transform'] == claimed[1] for t in tests):
            untested.append('no search row carries the claimed transform pair %s -> %s on the days given' % claimed)
        results.append(dict(claim_id=c['id'], statement=c['statement'], author=claims_doc['author'], day_made=c['day_made'],
                            series_matched=matched, cannot_test_yet=[dict(series=m, reason='not in the search (no series of this '
                                                                         'name on any day given)') for m in missing],
                            tests=tests, counts=dict(tests=len(tests), held=held, shown_otherwise=other,
                                                     unresolved=verdicts.count('unresolved'),
                                                     counts_only=verdicts.count('counts_only')),
                            days_tested=sorted({t['day'] for t in tests}), disposition=disposition,
                            disposition_note='orientation only (R14); the counts and days above are the finding',
                            challenge=challenges, untested=untested))
    return results


def write(doc, days, results, out_dir, map_url=None, log=print, brain_dir='/opt/frankie-box/brain'):
    schema = {'jev': 'JEV_LESSONS_V1', 'frankie': 'FRANKIE_LESSONS_V1', 'historical': 'HISTORICAL_LESSONS_V1'}[doc['author']]
    if doc['author'] == 'historical':
        doc = dict(doc, day='-'.join(sorted(d['day'] for d in days)))      # the days tested, each still on its own
    lessons = dict(schema=schema, author=doc['author'], day=doc['day'], stamp=doc['stamp'], claims_sha256=doc['claims_sha256'],
                   claims_source=doc['source'], written_by='scientific_teacher', at=time.time(),
                   searches=[dict(day=d['day'], cycle=d['cycle'], dir=str(d['dir']), manifest_sha256=d['manifest_sha256'])
                             for d in days],
                   results=results, model_calls=0,
                   rule='each day on its own, never pooled; counts are the finding, the disposition word is orientation')
    data = json.dumps(lessons, indent=1, sort_keys=True).encode()
    name = '%s-%s.json' % (doc['day'], doc['stamp'] or 'frankie')
    path = Path(out_dir) / doc['author'] / name
    if path.exists():
        raise SystemExit('%s exists: these claims were already taught (duplicate data declines the run)' % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    log('%s lessons: %d claims, %s -> %s' % (doc['author'], len(results),
                                              json.dumps({k: sum(r['disposition'] == k for r in results) for k in DISPOSITIONS}), path))
    if doc['author'] == 'jev' and map_url:
        key = 'put:clm-sidecar/jev-brain/lessons/%s' % name
        entries = json.loads(urllib.request.urlopen(map_url, timeout=60).read())
        if key not in entries:
            raise SystemExit('no presigned slot %s in MAP_URL (dispatch with presign=put:frankie-granite42-568968024170-us-east-1/%s)'
                             % (key, key[4:]))
        request = urllib.request.Request(entries[key]['url'], data=data, method='PUT')
        with urllib.request.urlopen(request, timeout=300) as response:
            log('uploaded to Jev\'s brain: %s HTTP %d' % (key[4:], response.status))
    if doc['author'] == 'frankie':
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import frankie_box_brain as brain
        m = brain.write_lessons_entry(brain_dir, doc['day'], path)
        log('into Frankie\'s brain: %s (%d lessons files for %s)' % (Path(brain_dir) / (doc['day'] + '-lessons'),
                                                                    len(m['entries']), doc['day']))
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--search', action='append', required=True, help='a discovery-day search directory (repeat per day)')
    p.add_argument('--jev-claims', help='a JEV_CLAIMS_V1 file (Jev\'s claims of one day)')
    p.add_argument('--jev-stamp', help='fetch clm-sidecar/<stamp>/jev/claims.json through MAP_URL (presign getprefix) instead')
    p.add_argument('--frankie-ledgers', help='Frankie\'s classroom ledgers.json of one day (only its novel findings are read)')
    p.add_argument('--frankie-day', help='the day of those ledgers (YYYYMMDD)')
    p.add_argument('--historical-claims', help='a HISTORICAL_CLAIMS_V1 file (frankie_box_historical_claims.py)')
    a = p.parse_args()
    if a.jev_stamp and not a.jev_claims:
        key = 'clm-sidecar/%s/jev/claims.json' % a.jev_stamp
        entries = json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read())
        if key not in entries:
            raise SystemExit('no presigned GET for %s in MAP_URL (dispatch with presign=getprefix:frankie-granite42-'
                             '568968024170-us-east-1/clm-sidecar/%s/jev/)' % (key, a.jev_stamp))
        target = ROOT / 'inputs' / ('%s-claims.json' % a.jev_stamp)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(urllib.request.urlopen(entries[key]['url'], timeout=300).read())
        a.jev_claims = str(target)
    if a.frankie_ledgers and not (a.frankie_day and len(a.frankie_day) == 8 and a.frankie_day.isdigit()):
        raise SystemExit('--frankie-day YYYYMMDD required with --frankie-ledgers')
    if not (a.jev_claims or a.frankie_ledgers or a.historical_claims):
        raise SystemExit('give --jev-claims / --jev-stamp, --frankie-ledgers and/or --historical-claims')
    days = load_searches(a.search)
    for doc in ([jev_claims(a.jev_claims)] if a.jev_claims else []) + \
               ([frankie_claims(a.frankie_ledgers, a.frankie_day)] if a.frankie_ledgers else []) + \
               ([historical_claims(a.historical_claims)] if a.historical_claims else []):
        write(doc, days, test(doc, days), ROOT, os.environ.get('MAP_URL'))


if __name__ == '__main__':
    main()
