"""JEV REPORT #N: Jev's per-trade-day report (Greg, 2026-09-29: "make sure Jev does one per trade day"; "There will be
(3) #1's and so on"; "Write plain language interpreters to their code. I don't want you making interpretations").

Runs on the GitHub runner, called by launch.py --jev after it has collected the day's outputs from
clm-sidecar/<stamp>/jev/ into ./clm-sidecar-out/ (claims.json JEV_CLAIMS_V1, comparison.json JEV_COMPARISON_V1,
receipt.json JEV_SIT_IN_RECEIPT_V1, report.md). Nothing here calls a model, and nothing of the sit-in changes: Jev's
prompts, sit_in.py and the blind wall are untouched. Jev's claims, his comparison and his report are HIS words, shown
verbatim under fixed plain labels; only the numbering, the labels and the layout are this file's. Every recorded field
is a fixed sentence or line defined here, so the same files always give the same text; anything absent is stated as
"not recorded" with the recorded reason where there is one; the glossary is constant text; hashes and keys appear only in
the Evidence section; the sit-in's own report.md follows verbatim as an appendix.

NUMBERING. One number per trade day, shared with that day's CLASSROOM REPORT #N and FRANKIE REPORT #N (the box step
deploy/aws/box/frankie_box_experiment_day_reports.py assigns it; the Jev Pod dispatch carries it as REPORT_NUMBER=N).
The numbers are claimed on S3 with create-only writes (IfNoneMatch '*'), one object per number:
clm-sidecar/jev-reports/numbers/NNNN.json = {number, day, stamp}. A number already claimed for this day is reused; a
number claimed for another day is never reused (a given REPORT_NUMBER that belongs to another day is not used: the next
free number is taken and the report says so). Without REPORT_NUMBER the day's existing claim is used, or the next free
number: 1 + the highest number claimed or named by a report under clm-sidecar/*/jev/. The report is written create-only
to clm-sidecar/<stamp>/jev/jev-report-NNNN.md (a rerun of the same stamp with other bytes becomes -r2, -r3, ...; never
overwritten), to ./clm-sidecar-out/jev-report.md, and printed in full; the last two printed lines are REPORT_NUMBER=N and
a receipt JSON.
"""
import hashlib
import json
import re
import time
from pathlib import Path

NUMBERS = 'clm-sidecar/jev-reports/numbers'
REPORT_KEY_RE = re.compile(r'^clm-sidecar/[^/]+/jev/jev-report-(\d{4,})(?:-r\d+)?\.md$')
SCHEMA = 'JEV_REPORT_RECEIPT_V1'
NOT_RECORDED = 'not recorded'
GLOSSARY = (
    ('Jev', 'the blind outside student: a language model on his own GPU Pod (the model name is recorded in his claims '
            'file). He reads the day\'s classroom material and files claims. He never speaks in the classroom and never '
            'questions Granite.'),
    ('material', 'the day\'s classroom material Jev reads: the classroom as Frankie is shown it, and the search\'s '
                 'survivor list so far.'),
    ('claim', 'a statement Jev files for the scientific teacher (the experiment\'s search) to test on the data. A claim '
              'is not a result. Kinds: mechanism, novel_finding, test_next; "unstated:<kind>" when his answer named '
              'another kind.'),
    ('blind wall', 'his claims are filed, with their sha256 and time, before any of Frankie\'s outputs are read.'),
    ('comparison', 'after his claims are filed, Jev lists where they and Frankie\'s classroom findings agree, differ or '
                   'contradict, and what only one side has. The sit-in records it as orientation for the search, not a '
                   'verdict.'),
    ('unparsed answer', 'an answer of his that was not JSON after one retry; kept whole, never dropped.'),
    ('repeated claim', 'a claim in the same words as an earlier one of the same day; kept and marked.'),
    ('brain', 'his earlier days\' claims and the scientific teacher\'s lessons on them, carried whole into his next day; '
              'never Frankie\'s answers and never the comparison.'),
    ('report number', 'one number per trade day, shared by that day\'s CLASSROOM, FRANKIE and JEV reports.'),
)


def rec(value):
    return NOT_RECORDED if value is None else str(value)


def listing(items):
    items = [str(x) for x in (items or [])] if isinstance(items, (list, tuple)) else ([str(items)] if items else [])
    return '; '.join(items) if items else 'none'


def yn(value):
    return 'yes' if value is True else 'no' if value is False else NOT_RECORDED


def fenced(text):
    """His raw text verbatim inside a code fence that no run of backticks in it can close."""
    text = str(text)
    ticks = max([len(run) for run in re.findall('`+', text)] + [2]) + 1
    return ['`' * ticks, text, '`' * ticks]


def load(local, name):
    path = Path(local) / name
    if not path.is_file():
        return None, 'the file %s was not collected from the sit-in\'s outputs' % name
    try:
        return json.loads(path.read_bytes()), None
    except ValueError as error:
        return None, 'the file %s is not readable JSON (%s)' % (name, error)


# ------------------------------------------------------------------------------------------------------ the numbering
def claims_on_s3(s3, bucket):
    """{number: claim body} of every claimed number."""
    out = {}
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=NUMBERS + '/'):
        for item in page.get('Contents', []):
            m = re.fullmatch(re.escape(NUMBERS) + r'/(\d{4,})\.json', item['Key'])
            if m:
                out[int(m.group(1))] = json.loads(s3.get_object(Bucket=bucket, Key=item['Key'])['Body'].read())
    return out


def numbers_in_reports(s3, bucket):
    found = set()
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix='clm-sidecar/'):
        for item in page.get('Contents', []):
            m = REPORT_KEY_RE.match(item['Key'])
            if m:
                found.add(int(m.group(1)))
    return found


def put_new(s3, bucket, key, body, content_type):
    """Create-only write: True when written, False when the key exists already (never overwritten)."""
    from botocore.exceptions import ClientError
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body, IfNoneMatch='*', ServerSideEncryption='AES256',
                      ContentType=content_type)
        return True
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') in ('PreconditionFailed', '412') or \
                error.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 412:
            return False
        raise


def claim_number(s3, bucket, day, stamp, given):
    """(number, how) for this trade day; see NUMBERING in the module docstring."""
    notes = []
    for _ in range(64):
        claimed = claims_on_s3(s3, bucket)
        mine = sorted(n for n, c in claimed.items() if str(c.get('day')) == str(day))
        if given:
            owner = claimed.get(given)
            also = ' (S3 also holds number %s for this day, claimed earlier without the box number)' % ', '.join(
                str(n) for n in mine if n != given) if [n for n in mine if n != given] else ''
            if owner is not None and str(owner.get('day')) == str(day):
                return given, 'REPORT_NUMBER=%d from the box reports step (already claimed for this day)%s' % (given, also)
            if owner is None:
                body = json.dumps(dict(number=given, day=day, stamp=stamp, at=time.time(),
                                       source='REPORT_NUMBER from the box reports step'), sort_keys=True).encode()
                if put_new(s3, bucket, '%s/%04d.json' % (NUMBERS, given), body, 'application/json'):
                    return given, 'REPORT_NUMBER=%d from the box reports step%s' % (given, also)
                continue                                           # claimed meanwhile: read again
            notes.append('REPORT_NUMBER=%d was given but S3 holds that number for day %s (a number is never reused '
                         'for another day)' % (given, owner.get('day')))
            given = None
        if mine:
            return mine[0], '; '.join(notes + ['the number already claimed on S3 for this day'])
        used = set(claimed) | numbers_in_reports(s3, bucket)
        number = (max(used) if used else 0) + 1
        body = json.dumps(dict(number=number, day=day, stamp=stamp, at=time.time(), source='next free number on S3'),
                          sort_keys=True).encode()
        if put_new(s3, bucket, '%s/%04d.json' % (NUMBERS, number), body, 'application/json'):
            return number, '; '.join(notes + ['the next free number on S3 (no REPORT_NUMBER was given)'
                                              if not notes else 'the next free number on S3'])
    raise SystemExit('no report number could be claimed on S3 after 64 attempts')


# ------------------------------------------------------------------------------------------------------ the rendering
def claim_lines(i, c):
    L = ['### Jev\'s claim %d (id %s, kind %s)' % (i, rec(c.get('id')), rec(c.get('kind'))), '',
         'In his words: %s' % rec(c.get('statement')), '',
         '- Series he named: %s' % listing(c.get('series')),
         '- Cells he named: %s' % listing(c.get('cells')),
         '- Condition, in his words: %s' % rec(c.get('condition')),
         '- Lag, in his words: %s' % rec(c.get('lag')),
         '- Target, in his words: %s' % rec(c.get('target')),
         '- Direction, in his words: %s' % rec(c.get('direction')),
         '- Evidence he quoted:']
    evidence = c.get('evidence')
    L += ['  - %s' % x for x in evidence] if isinstance(evidence, list) and evidence else ['  - %s' % rec(evidence or None)]
    L.append('- Note pack he filed it from (recorded): %s' % rec(c.get('pack')))
    if c.get('duplicate_of'):
        L.append('- Recorded as a repeat, in the same words, of claim id %s.' % c['duplicate_of'])
    return L + ['']


def comparison_item(item, numbers, fields):
    """One comparison entry, each of his fields under a fixed label, verbatim."""
    if not isinstance(item, dict):
        return '- In Jev\'s words: %s' % item
    cid = item.get('jev_claim_id')
    parts = ['Jev\'s claim %s (id %s)' % (numbers.get(cid, 'not matched to a filed claim'), rec(cid))] if 'jev_claim_id' in item else []
    for key, label in fields:
        if key in item:
            parts.append('%s: %s' % (label, listing(item[key]) if isinstance(item[key], list) else rec(item[key])))
    other = sorted(set(item) - {'jev_claim_id'} - {k for k, _ in fields})
    parts += ['%s, in Jev\'s words: %s' % (k, rec(item[k])) for k in other]
    return '- ' + '. '.join(parts) + '.'


def render(number, how, day, stamp, outcome, local, bucket):
    claims_doc, claims_why = load(local, 'claims.json')
    comparison, comparison_why = load(local, 'comparison.json')
    receipt, receipt_why = load(local, 'receipt.json')
    report_path = Path(local) / 'report.md'
    claims = (claims_doc or {}).get('claims') or []
    unparsed = (claims_doc or {}).get('unparsed') or []
    numbers = {c.get('id'): i for i, c in enumerate(claims, 1)}
    kinds = {}
    for c in claims:
        kinds[c.get('kind')] = kinds.get(c.get('kind'), 0) + 1
    L = ['# JEV REPORT #%d' % number, '', 'Trade day: %s. Sit-in stamp: %s.' % (day, stamp),
         'Report number: %d (%s).' % (number, how),
         'The other reports for this trade day: CLASSROOM REPORT #%d and FRANKIE REPORT #%d (written on the box).' % (
             number, number),
         'Pod outcome (recorded by the launcher): %s.' % rec(outcome), '', '## Summary (recorded counts)', '']
    if claims_doc is None:
        L.append('- Claims: not recorded (%s).' % claims_why)
    else:
        L += ['- Claims filed: %d (%s). Unparsed answers: %d. Claims repeated in the same words: %d.' % (
            len(claims), listing('%s %d' % (k, v) for k, v in sorted(kinds.items(), key=lambda kv: str(kv[0]))),
            len(unparsed), sum(1 for c in claims if c.get('duplicate_of'))),
              '- Frankie read before the claims were filed (recorded): %s.' % yn(
                  (claims_doc.get('blind') or {}).get('frankie_read')),
              '- Model (recorded): %s.' % rec(claims_doc.get('model'))]
    if comparison is None:
        L.append('- Comparison with Frankie: not recorded (%s).' % comparison_why)
    elif not comparison.get('available'):
        L.append('- Comparison with Frankie available (recorded): no. Recorded reason: %s.' % rec(comparison.get('reason')))
    else:
        L.append('- Comparison with Frankie available (recorded): yes. Agree: %d. Differ: %d. Contradict: %d. Only Jev: %d. '
                 'Only Frankie: %d. Unparsed comparison answers: %d.' % tuple(
                     len(comparison.get(k) or []) for k in ('agree', 'differ', 'contradict', 'only_jev', 'only_frankie',
                                                            'unparsed')))
    if receipt is None:
        L.append('- Sit-in receipt: not recorded (%s).' % receipt_why)
    else:
        L.append('- Jev model calls (recorded): %s. Granite calls (recorded): %s. Brain files carried in (recorded): %s. '
                 'Sit-in status (recorded): %s.' % (rec(receipt.get('jev_model_calls')), rec(receipt.get('granite_calls')),
                                                    rec(receipt.get('brain_carried')), rec(receipt.get('status'))))
    unavailable = (claims_doc or {}).get('unavailable') or []
    L += ['- Not available in the day\'s material (recorded): %s.' % listing(
        '%s (%s)' % (rec(u.get('item')), rec(u.get('reason'))) if isinstance(u, dict) else u for u in unavailable), '']

    L += ['## Jev\'s claims, in his words', '']
    if claims_doc is None:
        L += ['Not recorded: %s.' % claims_why, '']
    elif not claims:
        L += ['Claims filed: 0.', '']
    for i, c in enumerate(claims, 1):
        L += claim_lines(i, c)

    L += ['## Jev\'s comparison with Frankie, in his words', '']
    if comparison is None:
        L += ['Not recorded: %s.' % comparison_why, '']
    elif not comparison.get('available'):
        L += ['Not available. Recorded reason: %s.' % rec(comparison.get('reason')), '']
    else:
        L += ['The sit-in records this comparison as orientation for the search, not a verdict (orientation_only: %s).' % yn(
            comparison.get('orientation_only')), '',
              'Frankie\'s files Jev read (recorded): %s.' % listing(sorted(comparison.get('frankie_files') or {})),
              'Frankie\'s files not available to him (recorded): %s.' % listing(
                  '%s (%s)' % (rec(u.get('item')), rec(u.get('reason'))) if isinstance(u, dict) else u
                  for u in comparison.get('frankie_unavailable') or []), '']
        for key, title, fields in (
                ('agree', 'Where Jev says they agree', (('frankie', 'Frankie, as Jev quoted'), ('why', 'Why, in Jev\'s words'))),
                ('differ', 'Where Jev says they differ', (('frankie', 'Frankie, as Jev quoted'), ('how', 'How, in Jev\'s words'))),
                ('contradict', 'Where Jev says they contradict', (('frankie', 'Frankie, as Jev quoted'),
                                                                   ('values', 'Values, in Jev\'s words'))),
                ('only_jev', 'What Jev says only he has', ()),
                ('only_frankie', 'What Jev says only Frankie has', ())):
            items = comparison.get(key) or []
            L += ['### %s: %d' % (title, len(items)), '']
            L += [comparison_item(x, numbers, fields) for x in items]
            L += [''] if items else []
        for i, text in enumerate(comparison.get('unparsed') or [], 1):
            L += ['### Unparsed comparison answer %d, verbatim' % i, ''] + fenced(text) + ['']
    if unparsed:
        L += ['## Unparsed answers to the claims step, verbatim', '']
        for u in unparsed:
            L += ['Note pack %s:' % rec(u.get('pack') if isinstance(u, dict) else None), '']
            L += fenced(u.get('text') if isinstance(u, dict) else u) + ['']

    L += ['## Glossary (fixed text)', ''] + ['- %s: %s' % (t, m) for t, m in GLOSSARY] + ['']
    L += ['## Evidence', '', '- bucket: %s' % bucket, '- sit-in outputs: clm-sidecar/%s/jev/' % stamp,
          '- report number claim: %s/%04d.json' % (NUMBERS, number)]
    if claims_doc is not None:
        L.append('- material sha256 (recorded): %s' % rec((claims_doc.get('material') or {}).get('sha256')))
    if receipt is not None:
        L += ['- claims sha256 (recorded): %s' % rec((receipt.get('claims') or {}).get('sha256')),
              '- sit-in report.md sha256 (recorded): %s' % rec((receipt.get('report') or {}).get('sha256')),
              '- brain entry (recorded): %s' % rec((receipt.get('brain_entry') or {}).get('key')),
              '- brain entry sha256 (recorded): %s' % rec((receipt.get('brain_entry') or {}).get('sha256'))]
    if comparison is not None and comparison.get('available'):
        L.append('- claims sha256 the comparison was bound to (recorded): %s' % rec(comparison.get('claims_sha256')))
    L.append('')
    L += ['## Appendix: the sit-in\'s own report.md, verbatim', '']
    if report_path.is_file():
        L += fenced(report_path.read_text(encoding='utf-8', errors='replace'))
    else:
        L.append('Not recorded: report.md was not collected from the sit-in\'s outputs.')
    return ('\n'.join(L).rstrip('\n') + '\n').encode('utf-8')


def publish(s3, bucket, stamp, day, local, outcome, report_number=None):
    """Number, render, write (S3 create-only and ./clm-sidecar-out/jev-report.md) and print the day's JEV REPORT."""
    number, how = claim_number(s3, bucket, day, stamp, report_number or None)
    raw = render(number, how, day, stamp, outcome, local, bucket)
    digest = hashlib.sha256(raw).hexdigest()
    key, existing = None, False
    for revision in range(1, 100):
        candidate = 'clm-sidecar/%s/jev/jev-report-%04d%s.md' % (stamp, number, '' if revision == 1 else '-r%d' % revision)
        if put_new(s3, bucket, candidate, raw, 'text/markdown'):
            key = candidate
            break
        if s3.get_object(Bucket=bucket, Key=candidate)['Body'].read() == raw:
            key, existing = candidate, True
            break
    if key is None:
        raise SystemExit('no free report key under clm-sidecar/%s/jev/ for number %d' % (stamp, number))
    out = Path(local) / 'jev-report.md'
    out.write_bytes(raw)
    print('=' * 100)
    print(raw.decode('utf-8'), end='')
    print('=' * 100)
    receipt = dict(schema=SCHEMA, day=day, stamp=stamp, report_number=number, number_from=how, key=key, existing=existing,
                   sha256=digest, bytes=len(raw), local=str(out), model_calls=0)
    print('REPORT_NUMBER=%d' % number)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return receipt
