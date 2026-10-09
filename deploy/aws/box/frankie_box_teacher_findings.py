"""The teacher's findings from its own recorded data, for its report and Frankie's brain (Greg, 2026-10-09).

Greg's rules, binding here: no average is a verdict (an R2, a correlation and a slope are averages: a recorded
coefficient is shown only beside the counts behind it, never alone); distributions are per cell with their count, p50,
p90, max and min; the per-event records behind them are named (the files they are listed in); nothing is dropped; one
day shows, it cannot claim. Every number below is counted from the teacher's own published rows in ONE streaming pass
over its rows sidecar (frankie_box_teacher_rows.SidecarStream), or read from its receipt, teacher-state-split.json or
teacher-knowledge.json.

The inputs, as their producers write them (verified against the producer code, 2026-10-09):
  rows sidecar (frankie_box_experiment_teacher._write_rows_sidecar): line 1 the header, then one snapshot row per line:
    components   [{name, unit, value (None unless PRESENT), state (PRESENT / MISSING / INVALID / ABLATED), raw_reason}]
                 (dipole_classroom._target_row)
    dstate       {schema FRANKIE_TEACHER_DSTATE_ROWS_V1, status GROUP_STATE | NOT_F_LAST, state: asdict(DState) on a
                 GROUP_STATE row (anchor_dir -1 / 1 / None, armed, broken, ...) else None} (parallel_teacher._dstate_row)
    state_labels {'<plane>|<field>': the plane's own value (a list for several rows of the plane)}
                 (teacher_second_set.state_labels); the teacher's own split buckets these by teacher_book_read.label_key
                 and a field the instant does not carry goes to teacher_book_read.STATE_UNKNOWN
    book_columns teacher_book_read.assemble's entry per row: status GROUP | NOT_F_LAST | GROUP_NOT_READ, group =
                 book_group (sides.<A|B>.{book, events, differs.<measure>.{book, events, reasons {reason: count}},
                 incomplete}, depth.<A|B> = [[price, size, count] per level] or None, touches, listing), windows.<slot>
                 (value dicts {value, state (int), reason}), with the state split moved to its own row key state_split
                 (each window's 64-group split: not a per-row bucket, so it is not bucketed here)
  The state buckets of a row are therefore the teacher's own split dimensions: teacher.dstate|status,
  teacher.dstate|state.<anchor_dir|armed|broken> and every plane label field, each value label_key-encoded exactly as
  in teacher-state-split.json, STATE_UNKNOWN when the row does not carry it.

compute(rows_dir) writes, beside the teacher's rows:
  teacher-findings.json                      the whole findings (every cell of every table)
  teacher-reconciliation-differences.jsonl   every book-vs-event difference, one per line (the per-event records)
publish(rows_dir, day) also writes teacher-account.json (the receipt's account with its pins) and teacher-account.md
(the teacher's own account, rendered the way the TEACHER REPORT renders it) for the brain entry <day>-teacher-account.

Percentiles are the inverted-CDF ones (numpy method 'inverted_cdf': the value at sorted index ceil(q n) - 1): every p50 /
p90 is a recorded value, never an interpolation. Book-derived columns follow the joined teacher's leaf rule
(frankie_box_joined_teacher._flatten): a mapping is walked by dotted key, numbers kept, a list enters as its length
(#len), strings are categories (counted, not distributed); a value dict {value, state, reason} enters its value only
when its state is PRESENT (a MISSING value's 0.0 placeholder is never a number), its state and reason as categories.
Nothing here caps, samples or truncates: every failure is listed in the findings and in the report, never fatal.
"""
import hashlib
import json
import math
import os
from array import array
from pathlib import Path

FINDINGS_FILE = 'teacher-findings.json'
DIFFERENCES_FILE = 'teacher-reconciliation-differences.jsonl'
ACCOUNT_FILE = 'teacher-account.json'
ACCOUNT_MD = 'teacher-account.md'
STATE_SPLIT_FILE = 'teacher-state-split.json'       # frankie_box_experiment_teacher.STATE_SPLIT_FILE
KNOWLEDGE_FILE = 'teacher-knowledge.json'           # Run.teacher_knowledge, written before Run.teacher_account_entry
SCHEMA = 'FRANKIE_TEACHER_FINDINGS_V1'
FORMAT = 2
ALL_ROWS = 'all rows'
STATE_UNKNOWN = '__state_unknown__'                 # teacher_book_read.STATE_UNKNOWN (one value, both sides)
STATE_LABELS_KEY = 'state_labels'                   # the sidecar row key (header row_keys) of the planes' state labels
DSTATE_KEY = 'dstate'                               # the snapshot row key of the teacher row's own DState
DSTATE_STATUS = 'teacher.dstate|status'             # the teacher's split field names (_group_labels)
DSTATE_FIELDS = ('anchor_dir', 'armed', 'broken')
DSTATE_DIMS = (DSTATE_STATUS,) + tuple('teacher.dstate|state.' + name for name in DSTATE_FIELDS)
STATE_NAMES = {0: 'PRESENT', 1: 'MISSING', 2: 'INVALID', 3: 'ABLATED'}    # c15_normalizer.State
CELL_FIELDS = ('count', 'p50', 'p90', 'max', 'min')
# The md renders every pinned cell of every bucket of every dimension. The book-derived cells and the co-occurrence per
# bucket are rendered for these dimensions (all rows and the teacher's own DState); for the plane state-label dimensions
# they are every one in teacher-findings.json, named with their cell counts. True renders every cell in the md too.
MD_EVERY_CELL = False
MD_CELL_DIMS = (ALL_ROWS,) + DSTATE_DIMS
# A pinned column's MISSING / INVALID reason -> the data or depth that would remove it (one place). Matched exactly
# first, then by the longest token the reason contains; a reason not named here is listed as having no named want.
# The reasons are the producers' own: c15_teacher, c15_teacher_r3, teacher_changes, c15_dstate, c15_normalizer,
# teacher_book_read.
REASON_WANTS = (
    ('NOT_F_LAST', 'nothing in the data: the pinned columns are computed on the row that closes an event group '
                   '(F_LAST); this row closes none (structural, not a gap)'),
    ('WINDOW_SHORT', 'more history before the row (fewer than the window\'s groups on the key so far: an earlier start '
                     'or the previous session carried)'),
    ('NO_FLOW', 'trades in the window (flow at that interval, or a longer window)'),
    ('SIDE_UNDEFINED', 'a clear aggressor imbalance in the window (buy and sell within 5% of each other leave the far '
                       'side undefined): more flow or a longer window'),
    ('UNKNOWN_SIDE', 'the aggressor side on every trade (a side-coded print)'),
    ('LEVEL_INTEGRITY', 'an intact book at the row (no integrity flag, not crossed, every level\'s orders present)'),
    ('BOOK_INTEGRITY', 'an intact book at the row (no integrity flag and a far best price)'),
    ('LEVEL_EMPTY', 'the level populated (the book at every level: the changes path\'s whole depth)'),
    ('LEFT_CENSORED', 'the front order\'s origin inside the journal (it was added before the data begins: an earlier '
                      'journal start)'),
    ('MISSING_REFERENCE_OR_RESET', 'continuity: every event\'s order reference present and no book reset in the window'),
    ('MISSING_REFERENCE', 'the reference value present before the row (the anchor / prior value carried)'),
    ('RESET', 'continuity across the book reset (the book rebuilt before the row)'),
    ('UNRECONCILED_FILL', 'each fill reconciled to its resting order (order-level fill records)'),
    ('RANK_UNAVAILABLE', 'the order\'s queue rank at the event (the whole level queue at every event)'),
    ('NO_MODIFIES', 'modifies in the window (no modify, no rate: more flow or a longer window)'),
    ('ZERO_QUANTITY', 'a non-zero quantity at the level'),
    ('NO_REMOVALS', 'removals in the window (cancels / fills at that interval)'),
    ('SCOPE_BOUNDARY', 'rows of one session / member scope across the window'),
    ('COHORT_EMPTY', 'orders in the top-three cohort'),
    ('CHAIN_BROKEN', 'an unbroken D chain (the chain broke and restarts at the next anchor)'),
    ('NO_COMPLETED_STEP', 'a completed extension step of the D chain (more groups in one anchor direction)'),
    ('DEGENERATE_STEP', 'a non-zero previous step (a zero step leaves the ratio undefined)'),
    ('TICK_UNKNOWN', 'the instrument\'s tick size (its definition record)'),
    ('UNBUILT_B2_C1', 'the column built (ablated: B2 / C1 not built)'),
    ('NORM_WARMUP', 'the normalizer warmed up (more rows before this one)'),
    ('NO_BOOK_YET', 'the opening book seeded before the first row'),
    ('NO_GROUP_READ', 'a group read in the window'),
)
ONE_DAY = 'one day shows; it cannot claim (the n is this day\'s)'


def want_for(reason):
    text = str(reason or '').upper()
    for token, want in REASON_WANTS:
        if token == text:
            return token, want
    for token, want in sorted(REASON_WANTS, key=lambda item: -len(item[0])):
        if token in text:
            return token, want
    return None, None


def label_key(value):
    """teacher_book_read.label_key: the bucket of a label value, exactly as the teacher's split keys it."""
    return json.dumps(value, sort_keys=True, default=repr)


def _hkey(value):
    """A hashable stand-in of a JSON label value (codes are looked up by it; label_key runs once per distinct value)."""
    kind = type(value)
    if kind is list:
        return (list, tuple(_hkey(item) for item in value))
    if kind is dict:
        return (dict, label_key(value))
    if kind is float and value != value:
        return (float, 'nan')
    return (kind, value)


class _Dim:
    """One bucket dimension: a code per row (0 = STATE_UNKNOWN) and the label of every code."""
    __slots__ = ('codes', 'index', 'labels')

    def __init__(self, rows_before):
        self.codes = array('i', bytes(4 * rows_before))
        self.index, self.labels = {}, [STATE_UNKNOWN]

    def code(self, value):
        key = _hkey(value)
        code = self.index.get(key)
        if code is None:
            code = self.index[key] = len(self.labels)
            self.labels.append(label_key(value))
        return code


def _is_value_dict(value):
    return 'value' in value and type(value.get('state')) is int and value['state'] in STATE_NAMES


def _book_leaves(value, prefix, numbers, categories):
    """The joined teacher's leaf rule with the pinned value-dict rule (see the module note)."""
    if isinstance(value, dict):
        if _is_value_dict(value):
            state = STATE_NAMES[value['state']]
            categories[prefix + '.state' if prefix else 'state'] = state
            if state == 'PRESENT' and type(value['value']) in (int, float) and math.isfinite(value['value']):
                numbers[prefix + '.value' if prefix else 'value'] = float(value['value'])
            if value.get('reason'):
                categories[prefix + '.reason' if prefix else 'reason'] = str(value['reason'])
            rest = {k: v for k, v in value.items() if k not in ('value', 'state', 'reason')}
        else:
            rest = value
        for key, item in rest.items():
            _book_leaves(item, '%s.%s' % (prefix, key) if prefix else str(key), numbers, categories)
    elif isinstance(value, list):
        numbers[prefix + '#len'] = float(len(value))
    elif isinstance(value, bool):
        numbers[prefix] = float(value)
    elif isinstance(value, (int, float)):
        if math.isfinite(value):
            numbers[prefix] = float(value)
        else:
            categories[prefix] = repr(value)                  # nan / inf stay named, never a number
    elif isinstance(value, str):
        categories[prefix] = value


class _Column:
    """A numeric column held sparsely: (row, value) for the rows that carry a number."""
    __slots__ = ('rows', 'values')

    def __init__(self):
        self.rows, self.values = array('i'), array('d')

    def add(self, row, value):
        self.rows.append(row)
        self.values.append(value)


def _sorted_column(np, column):
    """(row indices, values) of the column's values sorted ascending (stable)."""
    rows = np.frombuffer(column.rows, dtype=np.int32) if len(column.rows) else np.zeros(0, dtype=np.int32)
    values = np.frombuffer(column.values, dtype=np.float64) if len(column.values) else np.zeros(0)
    order = np.argsort(values, kind='stable')
    return rows[order], values[order]


def _grouped(np, codes, K, rows, values):
    """Per bucket code: count, p50, p90, max, min of the values (inverted CDF: recorded values only)."""
    c = codes[rows]
    order = np.argsort(c.astype(np.uint16) if K <= 65536 else c, kind='stable')   # stable: values stay sorted per code
    v = values[order]
    counts = np.bincount(c, minlength=K)
    starts = np.concatenate(([0], np.cumsum(counts)[:-1])).astype(np.int64)
    out = {}
    for code in np.flatnonzero(counts).tolist():
        n, s = int(counts[code]), int(starts[code])
        out[code] = [n, float(v[s + (n * 50 + 99) // 100 - 1]), float(v[s + (n * 90 + 99) // 100 - 1]),
                     float(v[s + n - 1]), float(v[s])]
    return out


def _sidecar_stat(path):
    try:
        st = os.stat(path)
        return dict(bytes=st.st_size, mtime_ns=st.st_mtime_ns)
    except OSError:
        return None


def _read_receipt(rows_dir):
    try:
        return json.loads((Path(rows_dir) / 'receipt.json').read_bytes()), None
    except (OSError, ValueError) as error:
        return None, '%s: %s' % (type(error).__name__, error)


def compute(rows_dir):
    """One streaming pass over the teacher's rows sidecar: every pinned and every book-derived column per state bucket
    (count, p50, p90, max, min), the buckets against the pinned columns' states and reasons, the book depth per side,
    and every book-vs-event difference (written whole to DIFFERENCES_FILE). Writes FINDINGS_FILE; returns the findings.
    A failure of a part is listed in the findings (failures), never raised for the data."""
    import numpy as np
    import frankie_box_teacher_rows as TR
    rows_dir = Path(rows_dir)
    side = TR.sidecar_of(rows_dir)
    if not side.is_file():
        findings = dict(schema=SCHEMA, format=FORMAT, status='not_computed', sidecar=dict(path=str(side)),
                        reason='no rows sidecar beside the teacher rows (a teacher before the second set, or the '
                               'teacher has not published yet)')
        _write_json(rows_dir / FINDINGS_FILE, findings)
        return findings
    stat = _sidecar_stat(side)
    failures = {}

    def failed(part, error):
        key = '%s: %s: %s' % (part, type(error).__name__, error)
        failures[key] = failures.get(key, 0) + 1
    try:
        stream = TR.SidecarStream(side)
    except (OSError, ValueError) as error:
        findings = dict(schema=SCHEMA, format=FORMAT, status='failed', sidecar=dict(path=str(side), stat=stat),
                        reason='the sidecar header is unreadable (%s: %s)' % (type(error).__name__, error))
        _write_json(rows_dir / FINDINGS_FILE, findings)
        return findings
    row_keys = stream.fields('row_keys')
    labels_carried = STATE_LABELS_KEY in row_keys
    book_key = stream.role('book_columns')
    dims = {name: _Dim(0) for name in DSTATE_DIMS}
    pinned, pinned_sr, sr_index, sr_labels = {}, {}, {}, []
    book, book_categories = {}, {}
    book_status = {}
    depth = {}
    n = 0
    stream_error = None
    diff_path = rows_dir / DIFFERENCES_FILE
    pending = diff_path.with_name(diff_path.name + '.pending')
    diff_classes, diff_count, largest = {}, 0, []
    digest, diff_bytes = hashlib.sha256(), 0
    rows_without = dict(components=0, dstate=0, state_labels=0, book_columns=0)
    with pending.open('wb') as diffs:
        iterator = iter(stream)
        while True:
            try:
                row = next(iterator)
            except StopIteration:
                break
            except Exception as error:  # noqa: BLE001 - a line the reader cannot read: the rows before it stand
                stream_error = dict(after_rows=n, error='%s: %s' % (type(error).__name__, error))
                break
            # ---- the row's buckets
            touched = {}
            try:
                dstate = row.get(DSTATE_KEY)
                if isinstance(dstate, dict):
                    touched[DSTATE_STATUS] = dstate.get('status')
                    state = dstate.get('state')
                    if isinstance(state, dict):
                        for name in DSTATE_FIELDS:
                            if name in state:
                                touched['teacher.dstate|state.' + name] = state[name]
                else:
                    rows_without['dstate'] += 1
                labels = row.get(STATE_LABELS_KEY) if labels_carried else None
                if isinstance(labels, dict):
                    touched.update(labels)
                else:
                    rows_without['state_labels'] += 1
            except Exception as error:  # noqa: BLE001 - listed; the row goes to STATE_UNKNOWN
                failed('state buckets', error)
                touched = {}
            for name in touched:
                if name not in dims:
                    dims[name] = _Dim(n)
            for name, dim in dims.items():
                dim.codes.append(dim.code(touched[name]) if name in touched else 0)
            # ---- the pinned columns
            try:
                comps = row.get('components')
                if not isinstance(comps, list):
                    rows_without['components'] += 1
                    comps = ()
                for comp in comps:
                    name = comp.get('name')
                    if name not in pinned:
                        pinned[name], pinned_sr[name] = _Column(), (array('i'), array('i'))
                    state, value = comp.get('state'), comp.get('value')
                    if state == 'PRESENT' and type(value) in (int, float) and math.isfinite(value):
                        pinned[name].add(n, float(value))
                    key = (str(state), comp.get('raw_reason') or '')
                    code = sr_index.get(key)
                    if code is None:
                        code = sr_index[key] = len(sr_labels)
                        sr_labels.append(key)
                    pinned_sr[name][0].append(n)
                    pinned_sr[name][1].append(code)
            except Exception as error:  # noqa: BLE001 - listed
                failed('pinned columns', error)
            # ---- the book-derived columns
            entry = row.get(book_key) if book_key else None
            if not isinstance(entry, dict):
                rows_without['book_columns'] += 1
                n += 1
                continue
            try:
                status = str(entry.get('status'))
                book_status[status] = book_status.get(status, 0) + 1
                numbers, categories = {}, {}
                _book_leaves(entry, '', numbers, categories)
                for name, value in numbers.items():
                    column = book.get(name)
                    if column is None:
                        column = book[name] = _Column()
                    column.add(n, value)
                for name, value in categories.items():
                    slot = book_categories.setdefault(name, {})
                    slot[value] = slot.get(value, 0) + 1
            except Exception as error:  # noqa: BLE001 - listed
                failed('book-derived columns', error)
            group = entry.get('group')
            if isinstance(group, dict):
                try:
                    for side_name, levels in (group.get('depth') or {}).items():
                        if isinstance(levels, list):
                            depth.setdefault(side_name, _Column()).add(n, float(len(levels)))
                    for side_name, part in (group.get('sides') or {}).items():
                        for measure, found in ((part or {}).get('differs') or {}).items():
                            reasons = found.get('reasons') or {}
                            record = dict(cursor=row.get('cursor'), side=side_name, measure=measure,
                                          book=found.get('book'), events=found.get('events'), reasons=reasons)
                            line = (json.dumps(record, sort_keys=True, default=str) + '\n').encode()
                            diffs.write(line)
                            digest.update(line)
                            diff_bytes += len(line)
                            diff_count += 1
                            for reason in (reasons or {'no reason recorded': 1}):
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
                except Exception as error:  # noqa: BLE001 - listed
                    failed('book group (depth / differences)', error)
            n += 1
        diffs.flush()
        os.fsync(diffs.fileno())
    pending.replace(diff_path)
    stream.close()
    largest.sort(key=lambda item: -item[0])
    # ---- the distributions, per dimension and bucket
    all_codes = np.zeros(n, dtype=np.int32)
    dim_codes = {ALL_ROWS: (all_codes, 1, [ALL_ROWS])}
    for name, dim in dims.items():
        codes = np.frombuffer(dim.codes, dtype=np.int32) if len(dim.codes) else np.zeros(0, dtype=np.int32)
        dim_codes[name] = (codes, len(dim.labels), dim.labels)
    pinned_sorted = {name: _sorted_column(np, col) for name, col in pinned.items()}
    book_sorted = {name: _sorted_column(np, col) for name, col in sorted(book.items())}
    srs = {}
    for name, (where, codes) in pinned_sr.items():
        full = np.full(n, -1, dtype=np.int64)
        if len(where):
            full[np.frombuffer(where, dtype=np.int32)] = np.frombuffer(codes, dtype=np.int32)
        srs[name] = full
    distributions, cooccurrence, dimensions = {}, {}, {}
    NSR = len(sr_labels) + 1
    for dim_name, (codes, K, labels) in dim_codes.items():
        try:
            rows_per = np.bincount(codes, minlength=K) if n else np.zeros(K, dtype=np.int64)
            cells = {code: dict(rows=int(rows_per[code]), pinned={}, book={}) for code in np.flatnonzero(rows_per).tolist()}
            for name, (rows, values) in pinned_sorted.items():
                got = _grouped(np, codes, K, rows, values)
                for code, cell in cells.items():
                    cell['pinned'][name] = got.get(code, [0])
            for name, (rows, values) in book_sorted.items():
                for code, dist in _grouped(np, codes, K, rows, values).items():
                    cells[code]['book'][name] = dist
            distributions[dim_name] = {labels[code]: cell for code, cell in cells.items()}
            co = {}
            for name, full in srs.items():
                keys = codes.astype(np.int64) * NSR + (full + 1)
                unique, counts = np.unique(keys, return_counts=True)
                for key, count in zip(unique.tolist(), counts.tolist()):
                    code, sr = divmod(key, NSR)
                    state, reason = sr_labels[sr - 1] if sr else ('NOT_CARRIED', '')
                    co.setdefault(labels[code], {}).setdefault(name, []).append(
                        dict(state=state, reason=reason, rows=int(count)))
            cooccurrence[dim_name] = co
            dimensions[dim_name] = dict(buckets=len(cells), rows_state_unknown=int(rows_per[0]) if dim_name != ALL_ROWS else 0,
                                        source=('the row' if dim_name == ALL_ROWS else
                                                'dstate (the teacher row\'s own DState)' if dim_name in DSTATE_DIMS
                                                else 'state_labels (the planes\' state at the instant)'))
        except Exception as error:  # noqa: BLE001 - listed; the other dimensions stand
            failed('distributions of %s' % dim_name, error)
    depth_out = {}
    for side_name, column in depth.items():
        rows, values = _sorted_column(np, column)
        got = _grouped(np, all_codes, 1, rows, values).get(0, [0])
        depth_out[side_name] = dict(zip(CELL_FIELDS, got))
    try:
        receipt, _ = _read_receipt(rows_dir)
        check = TR.sidecar_check(stream, receipt)
    except Exception as error:  # noqa: BLE001 - listed
        check = dict(status='not_checked', reason='%s: %s' % (type(error).__name__, error))
    findings = dict(
        schema=SCHEMA, format=FORMAT, status='computed', rows=n, sidecar=dict(stream.record(), stat=stat),
        sidecar_check=check, stream_error=stream_error, failures=failures, rows_without=rows_without,
        labels_carried=labels_carried, book_key=book_key,
        percentile_method='inverted_cdf (the value at sorted index ceil(q n) - 1: a recorded value, never interpolated)',
        cell_fields=list(CELL_FIELDS),
        cell_rule=('a cell is [count, p50, p90, max, min] of the values its bucket\'s rows carry ([0] when none); a book '
                   'column a bucket\'s rows carry no number for is not listed under that bucket'),
        bucket_rule=('the teacher\'s own split dimensions: %s and every plane label field of state_labels, each value '
                     'label_key-encoded (teacher_book_read.label_key), %s when the row does not carry it'
                     % (', '.join(DSTATE_DIMS), STATE_UNKNOWN)),
        dimensions=dimensions, distributions=distributions, cooccurrence=cooccurrence,
        book_status=book_status, book_categories=book_categories, depth=depth_out,
        reconciliation=dict(differences=diff_count, classes=dict(sorted(diff_classes.items())),
                            largest=[r for _, r in largest[:20]],
                            file=dict(path=str(diff_path), sha256=digest.hexdigest(), lines=diff_count, bytes=diff_bytes),
                            rule='every difference is a line of the file; the 20 largest by |book - events| are shown '
                                 'in the report beside the file\'s count and sha256'),
        rule=('counted from the teacher\'s own rows in one pass; per-cell distributions with count, p50, p90, max, min; '
              'no average reported as a finding; ' + ONE_DAY))
    _write_json(rows_dir / FINDINGS_FILE, findings)
    return findings


def _write_json(path, value):
    path = Path(path)
    pending = path.with_name(path.name + '.pending')
    data = json.dumps(value, sort_keys=True, default=str)        # one shot: the C encoder (json.dump streams in Python)
    with pending.open('w', encoding='utf-8') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


def load_or_compute(rows_dir):
    """The findings beside the rows when they were computed by this FORMAT from the sidecar as it is now (its bytes and
    mtime unchanged); else computed again (a findings file written before the sidecar existed, by a failed pass or
    by another FORMAT is never reused)."""
    import frankie_box_teacher_rows as TR
    path = Path(rows_dir) / FINDINGS_FILE
    if path.is_file():
        try:
            body = json.loads(path.read_bytes())
        except ValueError:
            body = None
        if (isinstance(body, dict) and body.get('status') == 'computed' and body.get('format') == FORMAT
                and (body.get('sidecar') or {}).get('stat') == _sidecar_stat(TR.sidecar_of(rows_dir))):
            return body
    return compute(rows_dir)


def correlations(rows_dir):
    """The teacher key's recorded pair structure (teacher-knowledge.json, the measured outputs of
    dipole_classroom.build_teacher_key, written by Run.teacher_knowledge before the account is filed): per pair the
    direction relation, the Pearson with the overlap count it was computed over, and the co-movement step and state-pair
    counts. (pairs, None) or (None, why)."""
    path = Path(rows_dir) / KNOWLEDGE_FILE
    if not path.is_file():
        return None, 'no %s beside the rows (the key\'s pair measurements are not published yet)' % KNOWLEDGE_FILE
    try:
        body = json.loads(path.read_bytes())
        pairs = [f['measurement'] for f in body.get('findings') or []
                 if str(f.get('finding_id', '')).startswith('teacher-pair:') and isinstance(f.get('measurement'), dict)]
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as error:
        return None, '%s is unreadable (%s: %s)' % (KNOWLEDGE_FILE, type(error).__name__, error)
    return pairs, None


def state_split_day(rows_dir):
    """teacher-state-split.json (the teacher's whole-day split, written by its publication). (body, None) or (None, why)."""
    path = Path(rows_dir) / STATE_SPLIT_FILE
    if not path.is_file():
        return None, 'no %s beside the rows' % STATE_SPLIT_FILE
    try:
        body = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        return None, '%s is unreadable (%s: %s)' % (STATE_SPLIT_FILE, type(error).__name__, error)
    return body, None


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


def _cell(d):
    """A distribution cell ([count, p50, p90, max, min] or the older dict) as table columns."""
    if isinstance(d, dict):
        d = [d.get(k) for k in CELL_FIELDS] if d.get('count') else [0]
    d = list(d or [0])
    return [d[0]] + ([_show(v) for v in d[1:5]] if d[0] else ['-'] * 4)


def _whole_file(pin, source, *path):
    """'every one is a line of <file> (count N, sha256 S)' from a {file|path, count|lines, sha256} pin."""
    if not isinstance(pin, dict):
        return 'not recorded by my step%s' % _c(source, *path)
    return 'every one is a line of %s (%s lines, sha256 %s)%s' % (
        _show(pin.get('file') or pin.get('path')), _show(pin.get('count', pin.get('lines'))), _show(pin.get('sha256')),
        _c(source, *path))


def finding_lines(findings, pairs, pairs_why, account, receipt, source_findings, source_receipt):
    """Sections 1 to 4 and the one-day section, every sentence a cell with its count and its field. Never raises for a
    missing part: each is stated as not recorded, with its reason."""
    F = source_findings
    computed = isinstance(findings, dict) and findings.get('status') == 'computed'
    L = ['## What I found: discovery and correlations', '']
    # (a) the key's pair structure
    L += ['### My key\'s pair structure (each pair as recorded, with the counts behind it)', '']
    if pairs is None:
        L += ['- Not recorded by my step: %s.' % pairs_why, '']
    else:
        L += ['I measured %d pairs of my pinned columns; each row is one pair as my key recorded it: the direction '
              'relation, the Pearson coefficient with the number of rows both were PRESENT on (an average over those '
              'rows, never a verdict), and the step and state-pair counts%s:' % (
                  len(pairs), _c(KNOWLEDGE_FILE, 'findings[teacher-pair:*].measurement')), '']
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
    if not computed:
        L += ['- My per-state findings: not recorded by my step (%s: %s)%s.' % (
            _show((findings or {}).get('status')), _show((findings or {}).get('reason')), _c(F, 'status')), '']
    else:
        L += _found_lines(findings, F)
    split, split_why = state_split_day(Path(F).parent) if F else (None, 'no findings path')
    L += _split_lines(split, split_why, receipt, source_receipt)
    L += _blocks_lines(findings if computed else None, account, receipt, F, source_receipt)
    L += _depth_lines(findings if computed else None, account, receipt, F, source_receipt)
    L += _one_day_lines(findings if computed else None, pairs)
    L += _signal_lines(findings if computed else None, account, F, source_receipt)
    return L


def _found_lines(findings, F):
    L = []
    side = findings.get('sidecar') or {}
    L += ['### How I read my rows', '',
          '- I read %s rows of my rows sidecar %s (%s bytes, sha256 %s) in one pass%s.' % (
              _show(findings.get('rows')), _show(side.get('path')), _show(side.get('bytes')), _show(side.get('sha256')),
              _c(F, 'sidecar')),
          '- Against my receipt\'s rows_sidecar pin: %s%s.' % (_show(findings.get('sidecar_check')), _c(F, 'sidecar_check'))]
    if findings.get('stream_error'):
        L.append('- My sidecar stopped being readable after %s rows (%s): the findings are of the rows before it%s.' % (
            _show(findings['stream_error'].get('after_rows')), _show(findings['stream_error'].get('error')),
            _c(F, 'stream_error')))
    for part, count in sorted((findings.get('failures') or {}).items()):
        L.append('- A part I could not count: %s (%d times)%s.' % (part, count, _c(F, 'failures')))
    without = {k: v for k, v in (findings.get('rows_without') or {}).items() if v}
    if without:
        L.append('- Rows that did not carry a part (each went to %s or no cell): %s%s.' % (
            STATE_UNKNOWN, _show(without), _c(F, 'rows_without')))
    if not findings.get('labels_carried'):
        L.append('- My sidecar header lists no %s row key: the plane state buckets are not carried%s.' % (
            STATE_LABELS_KEY, _c(F, 'labels_carried')))
    L += ['- My state buckets are %s%s.' % (findings.get('bucket_rule'), _c(F, 'bucket_rule')), '']
    dims = findings.get('dimensions') or {}
    L += ['Each bucket dimension, its buckets and the rows that did not carry it (%s)%s:' % (STATE_UNKNOWN, _c(F, 'dimensions')), '']
    L += _table(['dimension', 'buckets', 'rows %s' % STATE_UNKNOWN, 'from'],
                [(name, d.get('buckets'), d.get('rows_state_unknown'), d.get('source')) for name, d in dims.items()]) + ['']
    # (b) distributions per bucket
    L += ['### My columns by state bucket (count, p50, p90, max, min of the values the bucket\'s rows carry; %s)' % (
        findings.get('percentile_method')), '']
    for dim, by_value in (findings.get('distributions') or {}).items():
        L += ['%s: every bucket with its rows and every pinned column%s:' % (dim, _c(F, 'distributions', dim)), '']
        L += _table(['bucket', 'rows', 'pinned column', 'PRESENT rows', 'p50', 'p90', 'max', 'min'],
                    [[value, cell.get('rows'), name] + _cell(d) for value, cell in by_value.items()
                     for name, d in (cell.get('pinned') or {}).items()]) + ['']
        if MD_EVERY_CELL or dim in MD_CELL_DIMS:
            book_rows = [[value, cell.get('rows'), name] + _cell(d) for value, cell in by_value.items()
                         for name, d in (cell.get('book') or {}).items()]
            if book_rows:
                L += ['%s: every book-derived column a bucket\'s rows carry a number for%s:' % (dim, _c(F, 'distributions', dim)), '']
                L += _table(['bucket', 'rows', 'book-derived column', 'rows with a value', 'p50', 'p90', 'max', 'min'],
                            book_rows) + ['']
        else:
            cells = sum(len(cell.get('book') or {}) for cell in by_value.values())
            L += ['- %s: its %d book-derived cells over %d buckets are every one in %s, distributions.%s.<bucket>.book '
                  '(not repeated on this page; MD_EVERY_CELL renders them here).' % (dim, cells, len(by_value), F, dim), '']
    if findings.get('book_status'):
        L += ['- My rows by book read status: %s%s.' % (_show(findings['book_status']), _c(F, 'book_status')), '']
    if findings.get('book_categories'):
        L += ['The book-derived categories, value by value with their rows%s:' % _c(F, 'book_categories'), '']
        L += _table(['column', 'value', 'rows'], [(name, v, c) for name, vals in findings['book_categories'].items()
                                                   for v, c in vals.items()]) + ['']
    # (c) co-occurrence
    L += ['### My state buckets against my pinned columns\' states and reasons (rows in each cell)', '']
    for dim, by_value in (findings.get('cooccurrence') or {}).items():
        if MD_EVERY_CELL or dim in MD_CELL_DIMS:
            rows = [(value, name, c['state'], c['reason'] or '-', c['rows']) for value, by_name in by_value.items()
                    for name, cells in by_name.items() for c in cells]
            L += ['%s%s:' % (dim, _c(F, 'cooccurrence', dim)), '']
            L += _table(['bucket', 'pinned column', 'state', 'reason', 'rows'], rows) + ['']
        else:
            cells = sum(len(cells) for by_name in by_value.values() for cells in by_name.values())
            L += ['- %s: its %d cells over %d buckets are every one in %s, cooccurrence.%s (not repeated on this page).' % (
                dim, cells, len(by_value), F, dim)]
    L += ['']
    # (d) reconciliation
    rc = findings.get('reconciliation') or {}
    rf = rc.get('file') or {}
    L += ['### Book against events', '',
          'Book and event counts differed %s times; every one is a line of %s (%s lines, sha256 %s)%s.' % (
              _show(rc.get('differences')), _show(rf.get('path')), _show(rf.get('lines')), _show(rf.get('sha256')),
              _c(F, 'reconciliation', 'file')), '']
    L += _table(['measure:reason', 'times'], list((rc.get('classes') or {}).items())) + ['']
    L += ['The %d largest by |book - events| (every one is in the file above)%s:' % (
        len(rc.get('largest') or []), _c(F, 'reconciliation', 'largest')), '']
    L += _table(['cursor', 'side', 'measure', 'book', 'events', 'reasons'],
                [(r.get('cursor'), r.get('side'), r.get('measure'), r.get('book'), r.get('events'), _show(r.get('reasons')))
                 for r in rc.get('largest') or []]) + ['']
    return L


def _split_lines(split, why, receipt, source_receipt):
    """The teacher's whole-day split of its sums by the state present (teacher-state-split.json), every bucket."""
    L = ['### My sums split by the state present (the whole day, every bucket)', '']
    meta = ((receipt or {}).get('teacher_second_set') or {}).get('state_split') or {}
    if split is None:
        return L + ['- Not recorded by my step: %s%s.' % (why, _c(source_receipt, 'teacher_second_set.state_split')), '']
    L += ['- The split (format %s): %s; its file\'s sha256 on my receipt is %s%s.' % (
        _show(split.get('format')), _show(split.get('summary')), _show(meta.get('day_file_sha256')),
        _c(source_receipt, 'teacher_second_set.state_split.day_file_sha256')),
        '- Rows whose short-window split summed back: %s; rows whose short-window pinned check was equal: %s; rows '
        'compared and not equal: %s (every cursor listed in my receipt)%s.' % (
            _show(meta.get('rows_all_sum_back')), _show(meta.get('rows_pinned_equal')),
            _show(len(meta['rows_pinned_not_equal']) if isinstance(meta.get('rows_pinned_not_equal'), list) else None),
            _c(source_receipt, 'teacher_second_set.state_split.rows_pinned_not_equal')), '']
    for side, body in (split.get('sides') or {}).items():
        totals = body.get('totals') or {}
        L += ['Side %s: %s groups, events %s, book %s; every field\'s buckets with their groups, parts and share of the '
              'day\'s event totals%s:' % (side, _show(totals.get('groups')), _show(totals.get('events')),
                                          _show(totals.get('book')), _c(STATE_SPLIT_FILE, 'sides', side)), '']
        rows = []
        for field, part in (body.get('fields') or {}).items():
            for bucket, b in (part.get('buckets') or {}).items():
                rows.append((field, bucket, b.get('groups'), _show(b.get('events')), _show(b.get('book')),
                             _show(b.get('share_of_day'))))
        L += _table(['field', 'bucket', 'groups', 'events', 'book', 'share of the day\'s events'], rows) + ['']
    return L


def _blocks_lines(findings, account, receipt, F, source_receipt):
    pinned = ((account or {}).get('science') or {}).get('pinned_columns') or {}
    total = ((account or {}).get('read_together') or {}).get('rows') or (findings or {}).get('rows')
    L = ['## What blocks my signal', '']
    if not pinned:
        L += ['- My pinned columns\' reasons: not recorded by my step%s.' % _c(source_receipt, 'account.science.pinned_columns'), '']
    rows, unnamed = [], set()
    for name, v in pinned.items():
        for reason, count in ((v or {}).get('reasons') or {}).items():
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
    return L


def _depth_lines(findings, account, receipt, F, source_receipt):
    L = ['## Depth I lack, and what more I want', '']
    missing = (account or {}).get('missing_or_thin') or {}
    book_read = missing.get('book_read') or {}
    L += ['- My book read: whole_day = %s, groups = %s, windows = %s%s.' % (
        _show(book_read.get('whole_day')), _show(book_read.get('groups')), _show(book_read.get('windows')),
        _c(source_receipt, 'account.missing_or_thin.book_read')),
        '- With whole_day false (no teacher changes) my history row carries the pinned R3\'s top levels only; with it '
        'true, every level: whole_day is %s on this day%s.' % (_show(book_read.get('whole_day')),
                                                              _c(source_receipt, 'account.missing_or_thin.book_read.whole_day'))]
    for side_name, d in ((findings or {}).get('depth') or {}).items():
        L.append('- Book levels I held on side %s per row: %s rows, p50 %s, p90 %s, max %s, min %s%s.' % (
            side_name, _show(d.get('count', 0)), _show(d.get('p50')), _show(d.get('p90')), _show(d.get('max')),
            _show(d.get('min')), _c(F, 'depth', side_name)))
    second = (receipt or {}).get('teacher_second_set') or {}
    lock = second.get('clock_lock_time')
    lock = lock if isinstance(lock, dict) else dict(teacher_as_of=lock)
    L.append('- clock_lock_time is my as_of, %s (%s): lock time does not exist before Frankie reads%s.' % (
        _show(lock.get('teacher_as_of', lock.get('value'))), _show(lock.get('label')),
        _c(source_receipt, 'teacher_second_set.clock_lock_time.teacher_as_of')))
    # the account's whole lists, by their files (every entry; count and sha256)
    cm = missing.get('clock_mismatches') or {}
    L.append('- My rows whose picture clocks or identity differed: %s; %s.' % (
        _show(cm.get('rows')), _whole_file(cm.get('all') or second.get('mismatches'), source_receipt,
                                           'account.missing_or_thin.clock_mismatches.all')))
    rc = missing.get('reconciliation') or {}
    L.append('- My book-vs-event differences, as my account counted them by measure and reason (one difference with '
             'several reasons counts once per reason): %s; the differences themselves: %s.' % (
                 _show(rc.get('differences')),
                 _whole_file(rc.get('all'), source_receipt, 'account.missing_or_thin.reconciliation.all')))
    unknown = ((findings or {}).get('distributions') or {}).get(DSTATE_STATUS) or {}
    for status in (label_key('NOT_F_LAST'), STATE_UNKNOWN):
        if status in unknown:
            L.append('- Rows with dstate status %s (no group state to bucket by): %d%s.' % (
                status, unknown[status]['rows'], _c(F, 'distributions', DSTATE_STATUS, status, 'rows')))
    for side, fields in (missing.get('state_unknown_groups') or {}).items():
        for name, count in sorted((fields or {}).items()):
            L.append('- Side %s: %s group(s) closed at an instant with no row of %s (state unknown)%s.' % (
                side, count, name, _c(source_receipt, 'account.missing_or_thin.state_unknown_groups', side, name)))
    return L + ['']


def _one_day_lines(findings, pairs):
    L = ['## What I can show from one day and what I cannot claim until more days', '']
    L += ['Each finding below is this day\'s, with its n; %s.' % ONE_DAY, '']
    items = []
    for p in pairs or []:
        items.append(('pair %s / %s' % (p.get('left'), p.get('right')), (p.get('correlation') or {}).get('present_overlap')))
    for dim, by_value in ((findings or {}).get('distributions') or {}).items():
        items.append(('the %d buckets of %s (each bucket\'s n is in its table above)' % (len(by_value), dim),
                      sum(cell.get('rows') or 0 for cell in by_value.values())))
    if findings:
        items.append(('book-vs-event differences', (findings.get('reconciliation') or {}).get('differences')))
    return L + _table(['finding', 'n on this day'], items) + ['']


def _signal_lines(findings, account, F, source_receipt):
    pinned = ((account or {}).get('science') or {}).get('pinned_columns') or {}
    total = ((account or {}).get('read_together') or {}).get('rows') or (findings or {}).get('rows')
    L = ['## For Frankie\'s trade signals (my view of what would help, from the counts above)', '']
    if pinned and total:
        L += ['How often each pinned column was PRESENT%s:' % _c(source_receipt, 'account.science.pinned_columns'), '']
        L += _table(['pinned column', 'PRESENT rows', 'share of rows'],
                    [(name, ((v or {}).get('states') or {}).get('PRESENT', 0),
                      '%.1f%%' % (100.0 * ((v or {}).get('states') or {}).get('PRESENT', 0) / total))
                     for name, v in pinned.items()]) + ['']
    distributions = (findings or {}).get('distributions') or {}
    spread = []
    for name in next(iter(distributions.get(ALL_ROWS, {}).values()), {}).get('pinned', {}):
        best = None
        for dim, by_value in distributions.items():
            if dim == ALL_ROWS or len(by_value) < 2:
                continue
            cells = [(value, list((cell.get('pinned') or {}).get(name) or [0])) for value, cell in by_value.items()]
            known = [d[1] for _, d in cells if d[0]]
            if len(known) < 2:
                continue
            gap = max(known) - min(known)
            if best is None or gap > best[0]:
                best = (gap, dim, cells)
        if best is not None:
            spread.append((name, best))
    if spread:
        L += ['For each pinned column, the bucket dimension where its p50 differs most between buckets, every bucket '
              'shown with its n (a difference of recorded p50s, not a verdict; a bucket of a few rows moves it most)%s:'
              % _c(F, 'distributions'), '']
        L += _table(['pinned column', 'bucket dimension', 'p50 gap', 'buckets (value: n, p50, p90, max)'],
                    [(name, dim, round(gap, 12), '; '.join('%s: %d, %s, %s, %s' % (
                        v, d[0], _show(d[1]) if d[0] else '-', _show(d[2]) if d[0] else '-', _show(d[3]) if d[0] else '-')
                        for v, d in cells))
                     for name, (gap, dim, cells) in spread]) + ['']
    if pinned:
        L += ['The reasons that block the most rows, in order, each with what would remove it, are the table under '
              '"What blocks my signal".', '']
    return L


def account_md(receipt, rows_dir, source_receipt):
    """The teacher's own account (the TEACHER REPORT's body without the day's number) for the brain."""
    import types
    L = ['# The teacher\'s own account of day %s' % _show((receipt or {}).get('day')), '',
         'Every sentence is a recorded number or a listed name, with the field it came from in brackets.', '']
    try:
        import frankie_box_experiment_day_reports as R
        d = types.SimpleNamespace(teacher=receipt, teacher_pin=dict(path=source_receipt, sha256=None, bytes=None),
                                  teacher_why=None if receipt is not None else 'the teacher receipt is unreadable')
        L += R.teacher_account_lines(d)
    except Exception as error:  # noqa: BLE001 - listed; the findings follow
        L += ['- The account section was not rendered: %s: %s.' % (type(error).__name__, error), '']
    try:
        findings = load_or_compute(rows_dir)
    except Exception as error:  # noqa: BLE001 - listed; the account-based sections still render
        findings = dict(status='failed', reason='%s: %s' % (type(error).__name__, error))
    pairs, why = correlations(rows_dir)
    try:
        L += finding_lines(findings, pairs, why, (receipt or {}).get('account'), receipt,
                           str(Path(rows_dir) / FINDINGS_FILE), source_receipt)
    except Exception as error:  # noqa: BLE001 - listed
        L += ['## What I found: discovery and correlations', '',
              '- Not rendered: %s: %s.' % (type(error).__name__, error), '']
    try:
        import frankie_box_piece_accounts as PA
        acc = PA.Account()
        PA.teacher_actions(acc, receipt, source_receipt, None, 'the teacher step heartbeat (not read here)')
        L += acc.lines()
    except Exception as error:  # noqa: BLE001 - listed
        L += ['- The actions section was not rendered: %s: %s.' % (type(error).__name__, error), '']
    return L


def publish(rows_dir, day):
    """Write teacher-findings.json, teacher-account.json and teacher-account.md beside the teacher's rows; returns
    their paths (the brain entry <day>-teacher-account carries them). Never raises for the data: a failure is written
    into teacher-account.json and the md with its reason."""
    rows_dir = Path(rows_dir)
    receipt_path = rows_dir / 'receipt.json'
    receipt, why = _read_receipt(rows_dir)
    try:
        findings = load_or_compute(rows_dir)
    except Exception as error:  # noqa: BLE001 - recorded, the account goes on without the findings
        findings = dict(schema=SCHEMA, format=FORMAT, status='failed', reason='%s: %s' % (type(error).__name__, error))
        _write_json(rows_dir / FINDINGS_FILE, findings)
    pairs, pairs_why = correlations(rows_dir)
    _, split_why = state_split_day(rows_dir)
    day = day if day is not None else (receipt or {}).get('day')
    account = dict(schema='FRANKIE_TEACHER_ACCOUNT_PUBLICATION_V1', day=str(day),
                   receipt=dict(path=str(receipt_path), status='read' if receipt is not None else 'unreadable', reason=why),
                   account=(receipt or {}).get('account'),
                   teacher_second_set=(receipt or {}).get('teacher_second_set'),
                   rows_sidecar=(receipt or {}).get('rows_sidecar'),
                   findings=dict(path=str(rows_dir / FINDINGS_FILE), status=findings.get('status'), rows=findings.get('rows'),
                                 reason=findings.get('reason'), stream_error=findings.get('stream_error'),
                                 failures=findings.get('failures')),
                   knowledge=dict(path=str(rows_dir / KNOWLEDGE_FILE), pairs=None if pairs is None else len(pairs),
                                  reason=pairs_why),
                   state_split=dict(path=str(rows_dir / STATE_SPLIT_FILE), reason=split_why),
                   rule='the teacher\'s own account (its receipt account) for Frankie; the findings and the per-event '
                        'differences are in the files named here')
    _write_json(rows_dir / ACCOUNT_FILE, account)
    md = rows_dir / ACCOUNT_MD
    try:
        text = '\n'.join(account_md(receipt, rows_dir, str(receipt_path))).rstrip('\n') + '\n'
    except Exception as error:  # noqa: BLE001 - recorded in the md; the brain still gets the account
        text = '# The teacher\'s own account\n\nNot rendered: %s: %s\n' % (type(error).__name__, error)
    pending = md.with_name(md.name + '.pending')
    pending.write_text(text, encoding='utf-8')
    pending.replace(md)
    return [rows_dir / ACCOUNT_FILE, md, rows_dir / FINDINGS_FILE, rows_dir / DIFFERENCES_FILE]
