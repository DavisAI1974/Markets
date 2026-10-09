"""The teacher's findings from its own recorded data, for its report and Frankie's brain (Greg, 2026-10-09).

Greg's rules, binding here: no average is a verdict (an R2, a correlation and a slope are averages: a recorded
coefficient is shown only beside the counts behind it, never alone); distributions are per cell with their count, p50,
p90, max and min; the per-event records behind them are named (the files they are listed in); nothing is dropped; one
day shows, it cannot claim. Every number below is counted from the teacher's own published rows in ONE streaming pass
over its rows sidecar (frankie_box_teacher_rows.SidecarStream), or read from its receipt / teacher-knowledge.json.

compute(rows_dir) writes, beside the teacher's rows:
  teacher-findings.json                 the whole findings (every cell of every table)
  teacher-reconciliation-differences.jsonl   every book-vs-event difference, one per line (the per-event records)
publish(rows_dir, day) also writes teacher-account.json (the receipt's account with its pins) and teacher-account.md
(the teacher's own account, rendered the way the TEACHER REPORT renders it) for the brain entry <day>-teacher-account.

Percentiles are the inverted-CDF ones (numpy method 'inverted_cdf'): every p50 / p90 is a recorded value, never an
interpolation. Book-derived columns follow the joined teacher's leaf rule (frankie_box_joined_teacher._flatten): a
mapping is walked by dotted key, numbers kept, a list enters as its length (#len), strings are categories (counted, not
distributed).
"""
import hashlib
import json
from array import array
from pathlib import Path

FINDINGS_FILE = 'teacher-findings.json'
DIFFERENCES_FILE = 'teacher-reconciliation-differences.jsonl'
ACCOUNT_FILE = 'teacher-account.json'
ACCOUNT_MD = 'teacher-account.md'
SCHEMA = 'FRANKIE_TEACHER_FINDINGS_V1'
FORMAT = 1
# the state buckets (one place): the row's dstate status, these dstate.state labels, and every state_split label
DSTATE_LABELS = ('anchor_dir', 'armed', 'broken')
# a pinned column's MISSING / INVALID reason -> the data or depth that would remove it (one place; a reason not named
# here is listed as having no named want)
REASON_WANTS = (
    ('WINDOW_SHORT', 'more history before the row (a longer window: an earlier start or the previous session carried)'),
    ('NO_FLOW', 'trades in the window (flow at that interval, or a longer window)'),
    ('SIDE_UNDEFINED', 'the aggressor side on every trade (a side-coded print)'),
    ('UNKNOWN_SIDE', 'the aggressor side on every trade (a side-coded print)'),
    ('LEVEL_EMPTY', 'the level populated (the book at every level: the changes path\'s whole depth)'),
    ('ZERO_QUANTITY', 'a non-zero quantity at the level'),
    ('UNRECONCILED_FILL', 'each fill reconciled to its resting order (order-level fill records)'),
    ('MISSING_REFERENCE', 'the reference value present before the row (the anchor / prior value carried)'),
    ('RESET', 'continuity across the book reset (the book rebuilt before the row)'),
    ('NO_REMOVALS', 'removals in the window (cancels / fills at that interval)'),
    ('NO_BOOK_YET', 'the opening book seeded before the first row'),
    ('SCOPE_BOUNDARY', 'rows of one session / member scope across the window'),
)
ONE_DAY = 'one day shows; it cannot claim (the n is this day\'s)'


def want_for(reason):
    text = str(reason or '').upper()
    for token, want in REASON_WANTS:
        if token in text:
            return token, want
    return None, None


def _book_leaves(value, prefix='', out=None):
    """The joined teacher's leaf rule: numbers kept (booleans as 0/1), a list as its length, strings as categories."""
    out = {} if out is None else out
    if isinstance(value, dict):
        for key, item in value.items():
            _book_leaves(item, '%s.%s' % (prefix, key) if prefix else str(key), out)
    elif isinstance(value, list):
        out[prefix + '#len'] = float(len(value))
    elif isinstance(value, bool):
        out[prefix] = float(value)
    elif isinstance(value, (int, float)):
        out[prefix] = float(value)
    elif isinstance(value, str):
        out[prefix] = value
    return out


def _dist(np, values):
    values = values[~np.isnan(values)]
    if not len(values):
        return dict(count=0)
    pick = lambda q: float(np.percentile(values, q, method='inverted_cdf'))
    return dict(count=int(len(values)), p50=pick(50), p90=pick(90), max=float(values.max()), min=float(values.min()))


def compute(rows_dir):
    """One streaming pass over the teacher's rows sidecar: the per-bucket distributions of every pinned and every
    book-derived column, the bucket-by-state co-occurrence of the pinned columns, the book depth per side, and every
    book-vs-event difference (written whole to DIFFERENCES_FILE). Writes FINDINGS_FILE; returns the findings."""
    import numpy as np
    import frankie_box_teacher_rows as TR
    rows_dir = Path(rows_dir)
    side = TR.sidecar_of(rows_dir)
    if not side.is_file():
        findings = dict(schema=SCHEMA, format=FORMAT, status='not_computed',
                        reason='no rows sidecar beside the teacher rows (a teacher before the second set)')
        _write_json(rows_dir / FINDINGS_FILE, findings)
        return findings
    stream = TR.SidecarStream(side)
    columns, book_columns, labels, cooc = {}, {}, {}, {}
    book_categories = {}
    depth = {}
    n = 0
    diff_path = rows_dir / DIFFERENCES_FILE
    pending = diff_path.with_name(diff_path.name + '.pending')
    diff_classes, diff_count, largest = {}, 0, []
    digest = hashlib.sha256()
    with pending.open('wb') as diffs:
        for row in stream:
            # the row's buckets
            dstate = row.get('dstate') if isinstance(row.get('dstate'), dict) else None
            mine = {'all rows': 'all', 'dstate.status': (dstate or {}).get('status') or 'NO_DSTATE'}
            state = (dstate or {}).get('state') if isinstance((dstate or {}).get('state'), dict) else {}
            for label in DSTATE_LABELS:
                mine['dstate.state.' + label] = str(state.get(label)) if label in state else 'NOT_CARRIED'
            split = row.get(TR.ROLE_KEYS['state_split'])
            if isinstance(split, dict):
                for key, value in split.items():
                    mine['state_split.' + key] = str(value)
            for dim, value in mine.items():
                labels.setdefault(dim, ['NOT_CARRIED'] * n).append(value)
            for dim, seq in labels.items():
                if len(seq) < n + 1:
                    seq.append('NOT_CARRIED')
            # the pinned columns
            for comp in row.get('components') or ():
                name = comp.get('name')
                col = columns.get(name)
                if col is None:
                    col = columns[name] = array('d', [float('nan')] * n)
                col.append(float(comp['value']) if comp.get('state') == 'PRESENT' and comp.get('value') is not None
                           else float('nan'))
                key = (comp.get('state'), comp.get('raw_reason') or '')
                for dim, value in mine.items():
                    cell = cooc.setdefault(dim, {}).setdefault(value, {}).setdefault(name, {})
                    cell[key] = cell.get(key, 0) + 1
            for col in columns.values():
                if len(col) < n + 1:
                    col.append(float('nan'))
            # the book-derived columns
            book = row.get(TR.ROLE_KEYS['book_columns'])
            leaves = _book_leaves(book) if isinstance(book, dict) else {}
            for name, value in leaves.items():
                if isinstance(value, str):
                    slot = book_categories.setdefault(name, {})
                    slot[value] = slot.get(value, 0) + 1
                    continue
                col = book_columns.get(name)
                if col is None:
                    col = book_columns[name] = array('d', [float('nan')] * n)
                col.append(value)
            for col in book_columns.values():
                if len(col) < n + 1:
                    col.append(float('nan'))
            group = (book or {}).get('group') if isinstance(book, dict) else None
            if isinstance(group, dict):
                for side_name, levels in (group.get('depth') or {}).items():
                    depth.setdefault(side_name, array('d')).append(float(len(levels)) if isinstance(levels, list) else float('nan'))
                for side_name, part in (group.get('sides') or {}).items():
                    for measure, found in ((part or {}).get('differs') or {}).items():
                        record = dict(cursor=row.get('cursor'), side=side_name, measure=measure,
                                      book=found.get('book'), events=found.get('events'), reasons=found.get('reasons'))
                        line = (json.dumps(record, sort_keys=True, default=str) + '\n').encode()
                        diffs.write(line)
                        digest.update(line)
                        diff_count += 1
                        for reason in found.get('reasons') or ['no reason recorded']:
                            klass = '%s:%s' % (measure, reason)
                            diff_classes[klass] = diff_classes.get(klass, 0) + 1
                        try:
                            size = abs(float(found.get('book')) - float(found.get('events')))
                        except (TypeError, ValueError):
                            size = None
                        if size is not None:
                            largest.append((size, record))
                            if len(largest) > 400:
                                largest.sort(key=lambda item: -item[0])
                                del largest[200:]
            n += 1
    pending.replace(diff_path)
    largest.sort(key=lambda item: -item[0])
    # the distributions, per bucket dimension and value
    distributions = {}
    for dim, seq in labels.items():
        values = np.array(seq, dtype=object)
        for value in sorted(set(seq), key=str):
            mask = values == value
            cell = distributions.setdefault(dim, {}).setdefault(value, dict(rows=int(mask.sum()), pinned={}, book={}))
            for name, col in columns.items():
                cell['pinned'][name] = _dist(np, np.frombuffer(col, dtype=np.float64)[mask])
            for name, col in book_columns.items():
                cell['book'][name] = _dist(np, np.frombuffer(col, dtype=np.float64)[mask])
    co = {dim: {value: {name: [dict(state=s, reason=r, rows=c) for (s, r), c in sorted(cells.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))]
                        for name, cells in by_name.items()}
                for value, by_name in by_value.items()} for dim, by_value in cooc.items()}
    findings = dict(
        schema=SCHEMA, format=FORMAT, status='computed', rows=n, sidecar=stream.record(),
        percentile_method='inverted_cdf (a recorded value, never interpolated)',
        bucket_dimensions=sorted(labels), dstate_labels=list(DSTATE_LABELS),
        distributions=distributions, cooccurrence=co, book_categories=book_categories,
        depth={s: _dist(np, np.frombuffer(a, dtype=np.float64)) for s, a in depth.items()},
        reconciliation=dict(differences=diff_count, classes=dict(sorted(diff_classes.items())),
                            largest=[r for _, r in largest[:20]],
                            file=dict(path=str(diff_path), sha256=digest.hexdigest(), lines=diff_count),
                            rule='every difference is a line of the file; the 20 largest by |book - events| are shown'),
        rule=('counted from the teacher\'s own rows in one pass; per-cell distributions with count, p50, p90, max, min; '
              'no average reported as a finding; ' + ONE_DAY))
    _write_json(rows_dir / FINDINGS_FILE, findings)
    return findings


def _write_json(path, value):
    import os
    path = Path(path)
    pending = path.with_name(path.name + '.pending')
    with pending.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


def load_or_compute(rows_dir):
    path = Path(rows_dir) / FINDINGS_FILE
    if path.is_file():
        try:
            return json.loads(path.read_bytes())
        except ValueError:
            pass
    return compute(rows_dir)


def correlations(rows_dir):
    """The teacher key's recorded pair structure (teacher-knowledge.json, the measured outputs of
    dipole_classroom.build_teacher_key): per pair the direction relation, the Pearson with the overlap count it was
    computed over, and the co-movement step and state-pair counts. (pairs, None) or (None, why)."""
    path = Path(rows_dir) / 'teacher-knowledge.json'
    if not path.is_file():
        return None, 'no teacher-knowledge.json beside the rows (the key\'s pair measurements are not published yet)'
    body = json.loads(path.read_bytes())
    pairs = [f['measurement'] for f in body.get('findings') or [] if str(f.get('finding_id', '')).startswith('teacher-pair:')]
    return pairs, None


# ---------------------------------------------------------------------------------------------------- rendering
def _c(source, *path):
    return ' [%s#%s]' % (source, '.'.join(str(p) for p in path))


def _show(value):
    if value is None:
        return 'not recorded by my step'
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)


def _table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    return out + ['| ' + ' | '.join(str(c).replace('|', '\\|').replace('\n', ' ') for c in row) + ' |' for row in rows]


def _dist_row(d):
    return [d.get('count', 0)] + [_show(d.get(k)) if d.get('count') else '-' for k in ('p50', 'p90', 'max', 'min')]


def finding_lines(findings, pairs, pairs_why, account, receipt, source_findings, source_receipt):
    """Sections 1 to 4 and the one-day section, every sentence a cell with its count and its field."""
    F = source_findings
    L = ['## What I found: discovery and correlations', '']
    # (a) the key's pair structure
    L += ['### My key\'s pair structure (each pair as recorded, with the counts behind it)', '']
    if pairs is None:
        L += ['- Not recorded by my step: %s.' % pairs_why, '']
    else:
        L += ['I measured %d pairs of my pinned columns; each row is one pair as my key recorded it: the direction '
              'relation, the Pearson coefficient with the number of rows both were PRESENT on (an average over those '
              'rows, never a verdict), and the step and state-pair counts%s:' % (len(pairs), _c('teacher-knowledge.json', 'findings[teacher-pair:*].measurement')), '']
        rows = []
        for p in pairs:
            corr = p.get('correlation') or {}
            co = p.get('co_movement') or {}
            rows.append((p.get('left'), p.get('right'), p.get('direction_relation'), _show(corr.get('pearson')),
                         _show(corr.get('present_overlap')), _show(corr.get('reason')) if corr.get('pearson') is None else '',
                         _show(co.get('steps_between_consecutive_both_present')), _show(co.get('steps')),
                         _show(co.get('state_pairs'))))
        L += _table(['left', 'right', 'relation', 'Pearson', 'rows both PRESENT', 'why no Pearson', 'steps',
                     'step directions (counts)', 'state pairs (counts)'], rows) + ['']
    if not findings or findings.get('status') != 'computed':
        L += ['- My per-state findings: not recorded by my step (%s)%s.' % (_show((findings or {}).get('reason')), _c(F, 'status')), '']
        return L
    # (b) distributions per bucket
    L += ['### My columns by state bucket (count, p50, p90, max, min of the PRESENT values; %s)' % findings['percentile_method'], '']
    for dim, by_value in findings['distributions'].items():
        for value, cell in by_value.items():
            L += ['In the bucket %s = %s there are %d rows%s:' % (dim, value, cell['rows'], _c(F, 'distributions', dim, value, 'rows')), '']
            L += _table(['pinned column', 'PRESENT rows', 'p50', 'p90', 'max', 'min'],
                        [[name] + _dist_row(d) for name, d in cell['pinned'].items()]) + ['']
            if cell['book']:
                L += _table(['book-derived column', 'rows with a value', 'p50', 'p90', 'max', 'min'],
                            [[name] + _dist_row(d) for name, d in cell['book'].items()]) + ['']
    if findings.get('book_categories'):
        L += ['The book-derived categories, value by value with their rows%s:' % _c(F, 'book_categories'), '']
        L += _table(['column', 'value', 'rows'], [(name, v, c) for name, vals in findings['book_categories'].items()
                                                   for v, c in vals.items()]) + ['']
    # (c) co-occurrence
    L += ['### My state buckets against my pinned columns\' states and reasons (rows in each cell)', '']
    for dim, by_value in findings['cooccurrence'].items():
        rows = [(value, name, c['state'], c['reason'] or '-', c['rows']) for value, by_name in by_value.items()
                for name, cells in by_name.items() for c in cells]
        L += ['%s%s:' % (dim, _c(F, 'cooccurrence', dim)), '']
        L += _table(['bucket', 'pinned column', 'state', 'reason', 'rows'], rows) + ['']
    # (d) reconciliation
    rc = findings['reconciliation']
    L += ['### Book against events', '',
          'Book and event counts differed %d times; every one is a line of %s (sha256 %s)%s.' % (
              rc['differences'], rc['file']['path'], rc['file']['sha256'], _c(F, 'reconciliation', 'file')), '']
    L += _table(['measure:reason', 'times'], list(rc['classes'].items())) + ['']
    L += ['The %d largest by |book - events|%s:' % (len(rc['largest']), _c(F, 'reconciliation', 'largest')), '']
    L += _table(['cursor', 'side', 'measure', 'book', 'events', 'reasons'],
                [(r['cursor'], r['side'], r['measure'], r['book'], r['events'], _show(r['reasons'])) for r in rc['largest']]) + ['']
    # 2. what blocks my signal
    pinned = ((account or {}).get('science') or {}).get('pinned_columns') or {}
    total = ((account or {}).get('read_together') or {}).get('rows') or findings.get('rows')
    L += ['## What blocks my signal', '']
    if not pinned:
        L += ['- My pinned columns\' reasons: not recorded by my step%s.' % _c(source_receipt, 'account.science.pinned_columns'), '']
    rows, unnamed = [], set()
    for name, v in pinned.items():
        for reason, count in (v.get('reasons') or {}).items():
            token, want = want_for(reason)
            if token is None:
                unnamed.add(reason)
            rows.append((name, reason, count, ('%.1f%%' % (100.0 * count / total)) if total else '-',
                         want or 'no named want for this reason (REASON_WANTS)'))
    if rows:
        L += ['Per pinned column, each reason a row was not PRESENT, its rows, its share of my %s rows, and what data or '
              'depth would remove it (REASON_WANTS)%s:' % (_show(total), _c(source_receipt, 'account.science.pinned_columns')), '']
        L += _table(['pinned column', 'reason', 'rows', 'share of rows', 'what would remove it'],
                    sorted(rows, key=lambda r: (-r[2], r[0], r[1]))) + ['']
    if unnamed:
        L += ['Reasons with no named want (listed): %s.' % ', '.join(sorted(unnamed)), '']
    # 3. depth
    L += ['## Depth I lack, and what more I want', '']
    book_read = ((account or {}).get('missing_or_thin') or {}).get('book_read') or {}
    L += ['- My book read: whole_day = %s, groups = %s, windows = %s%s.' % (
        _show(book_read.get('whole_day')), _show(book_read.get('groups')), _show(book_read.get('windows')),
        _c(source_receipt, 'account.missing_or_thin.book_read')),
        '- With whole_day false (no teacher changes) my history row carries the pinned R3\'s top levels only; with it '
        'true, every level: whole_day is %s on this day%s.' % (_show(book_read.get('whole_day')),
                                                              _c(source_receipt, 'account.missing_or_thin.book_read.whole_day'))]
    for side_name, d in (findings.get('depth') or {}).items():
        L.append('- Book levels I held on side %s per row: %d rows, p50 %s, p90 %s, max %s, min %s%s.' % (
            side_name, d.get('count', 0), _show(d.get('p50')), _show(d.get('p90')), _show(d.get('max')), _show(d.get('min')),
            _c(F, 'depth', side_name)))
    lock = (receipt or {}).get('teacher_second_set', {}).get('clock_lock_time') or {}
    L.append('- clock_lock_time is my as_of, %s: lock time does not exist before Frankie reads%s.' % (
        _show(lock.get('value') if isinstance(lock, dict) else lock), _c(source_receipt, 'teacher_second_set.clock_lock_time')))
    unknown = (findings['distributions'].get('dstate.status') or {})
    for status in ('NO_DSTATE', 'NOT_F_LAST'):
        if status in unknown:
            L.append('- Rows with dstate status %s (no group state to bucket by): %d%s.' % (
                status, unknown[status]['rows'], _c(F, 'distributions', 'dstate.status', status, 'rows')))
    L += ['']
    # the one-day limit
    L += ['## What I can show from one day and what I cannot claim until more days', '']
    L += ['Each finding below is this day\'s, with its n; %s.' % ONE_DAY, '']
    items = []
    for p in pairs or []:
        items.append(('pair %s / %s' % (p.get('left'), p.get('right')), (p.get('correlation') or {}).get('present_overlap')))
    for dim, by_value in findings['distributions'].items():
        for value, cell in by_value.items():
            items.append(('bucket %s = %s' % (dim, value), cell['rows']))
    items.append(('book-vs-event differences', rc['differences']))
    L += _table(['finding', 'n on this day'], items) + ['']
    # 4. for Frankie's trade signals
    L += ['## For Frankie\'s trade signals (my view of what would help, from the counts above)', '']
    if pinned and total:
        L += ['How often each pinned column was PRESENT%s:' % _c(source_receipt, 'account.science.pinned_columns'), '']
        L += _table(['pinned column', 'PRESENT rows', 'share of rows'],
                    [(name, (v.get('states') or {}).get('PRESENT', 0),
                      '%.1f%%' % (100.0 * (v.get('states') or {}).get('PRESENT', 0) / total)) for name, v in pinned.items()]) + ['']
    spread = []
    for name in next(iter(findings['distributions'].get('all rows', {}).values()), {}).get('pinned', {}):
        best = None
        for dim, by_value in findings['distributions'].items():
            if dim == 'all rows' or len(by_value) < 2:
                continue
            p50s = [(value, cell['pinned'].get(name) or {}) for value, cell in by_value.items()]
            known = [d['p50'] for _, d in p50s if d.get('count')]
            if len(known) < 2:
                continue
            gap = max(known) - min(known)
            if best is None or gap > best[0]:
                best = (gap, dim, p50s)
        if best is not None:
            spread.append((name, best))
    if spread:
        L += ['For each pinned column, the bucket dimension where its p50 differs most between buckets, every bucket '
              'shown with its n (a difference of recorded p50s, not a verdict)%s:' % _c(F, 'distributions'), '']
        L += _table(['pinned column', 'bucket dimension', 'p50 gap', 'buckets (value: n, p50, p90, max)'],
                    [(name, dim, round(gap, 12), '; '.join('%s: %d, %s, %s, %s' % (v, d.get('count', 0), _show(d.get('p50')),
                                                                                  _show(d.get('p90')), _show(d.get('max')))
                                                          for v, d in p50s))
                     for name, (gap, dim, p50s) in spread]) + ['']
    if rows:
        L += ['The reasons that block the most rows, in order, each with what would remove it (from the table above).', '']
    return L


def account_md(receipt, rows_dir, source_receipt):
    """The teacher's own account (the TEACHER REPORT's body without the day's number) for the brain."""
    import types
    import frankie_box_experiment_day_reports as R
    import frankie_box_piece_accounts as PA
    d = types.SimpleNamespace(teacher=receipt, teacher_pin=dict(path=source_receipt, sha256=None, bytes=None),
                              teacher_why=None)
    findings = load_or_compute(rows_dir)
    pairs, why = correlations(rows_dir)
    L = ['# The teacher\'s own account of day %s' % _show((receipt or {}).get('day')), '',
         'Every sentence is a recorded number or a listed name, with the field it came from in brackets.', '']
    L += R.teacher_account_lines(d)
    L += finding_lines(findings, pairs, why, (receipt or {}).get('account'), receipt,
                       str(Path(rows_dir) / FINDINGS_FILE), source_receipt)
    acc = PA.Account()
    PA.teacher_actions(acc, receipt, source_receipt, None, 'the teacher step heartbeat (not read here)')
    return L + acc.lines()


def publish(rows_dir, day):
    """Write teacher-findings.json, teacher-account.json and teacher-account.md beside the teacher's rows; returns
    their paths (the brain entry <day>-teacher-account carries them). Never raises for the data: a failure is written
    into teacher-account.json with its reason."""
    rows_dir = Path(rows_dir)
    receipt_path = rows_dir / 'receipt.json'
    try:
        receipt = json.loads(receipt_path.read_bytes())
    except (OSError, ValueError) as error:
        receipt, why = None, '%s: %s' % (type(error).__name__, error)
    else:
        why = None
    try:
        findings = load_or_compute(rows_dir)
    except Exception as error:  # noqa: BLE001 - recorded, the account goes on without the findings
        findings = dict(schema=SCHEMA, format=FORMAT, status='failed', reason='%s: %s' % (type(error).__name__, error))
        _write_json(rows_dir / FINDINGS_FILE, findings)
    day = day if day is not None else (receipt or {}).get('day')
    account = dict(schema='FRANKIE_TEACHER_ACCOUNT_PUBLICATION_V1', day=str(day),
                   receipt=dict(path=str(receipt_path), status='read' if receipt is not None else 'unreadable', reason=why),
                   account=(receipt or {}).get('account'),
                   teacher_second_set=(receipt or {}).get('teacher_second_set'),
                   rows_sidecar=(receipt or {}).get('rows_sidecar'),
                   findings=dict(path=str(rows_dir / FINDINGS_FILE), status=findings.get('status'), rows=findings.get('rows')),
                   rule='the teacher\'s own account (its receipt account) for Frankie; the findings and the per-event '
                        'differences are in the files named here')
    _write_json(rows_dir / ACCOUNT_FILE, account)
    md = rows_dir / ACCOUNT_MD
    try:
        text = '\n'.join(account_md(receipt, rows_dir, str(receipt_path))).rstrip('\n') + '\n'
    except Exception as error:  # noqa: BLE001 - recorded in the account file; the brain still gets the account
        text = '# The teacher\'s own account\n\nNot rendered: %s: %s\n' % (type(error).__name__, error)
    md.write_text(text, encoding='utf-8')
    return [rows_dir / ACCOUNT_FILE, md, rows_dir / FINDINGS_FILE, rows_dir / DIFFERENCES_FILE]
