"""The experiment's search, first slice: series on one causal axis per day, and sign-step couplings with a chance check.

Greg, 2026-09-29 ("build the bedrock off switch and start the search"). Spec: research/kalshi/frankie_boss/
SPEC-experiment-orchestrator.md (steps 5-6) and SPEC-scientific-teacher.md (the search IS the scientific teacher).
Reads ONE day's exported data (frankie_box_experiment_data.py: /opt/frankie-box/work/experiment-data/<day>/cycle-<NN>/)
in place. Nothing is re-derived and no copy is written: the ROOT's row spools are streamed through the journal's own
codec (c15_journal.unpack) into Arrow columns held in memory, and DuckDB aligns them.

SERIES (step 5). The axis is the F_LAST group closes (the ROOT's book-frame spool, in its order). Each source is placed
on the axis AS OF the moment it was knowable, never later information:
  frames      (root/work/derived/.rows/frames.jsonl)      each numeric book field, at its own group close;
  structures  (root/work/derived/.rows/structures.jsonl)  each numeric structure field, at its group close;
  trades      (root/work/derived/.rows/prices.jsonl)      last trade price and size known at the group close;
  per-second  (legacy_native_signed_flow, legacy_per_second_roll20)  buy, sell and roll20 of second s, known at the
              start of second s+1.
Receive clocks can run backwards, so the axis time is the running maximum of the frames' ts_recv_ns (order is the
spool's order, which is the ROOT's ordinal order). Alignment is a DuckDB ASOF join (value known_at <= axis time).
Every series passes odcore.leakage.assert_no_leakage in its own row order before it is searched: its value as of a
row must not change when every later row of its source is scrambled. A series that fails is listed and not searched.

SEARCH (step 6, this slice). For every ordered pair (x, y) of series and every cell: the sign of each step of x and y
on the axis, and at each lag k in -L..L the count D[k] = sum_t sx[t]*sy[t+k] (x leads y at k > 0) with B[k] the steps
where both move; at the lag with the largest |D|: same_way, opposite, both_moving. The chance check: every circular
shift farther than max(2L+1, m/10) steps gives the windowed maximum |D| a shuffled-in-time pairing reaches; the row
reports how many shifts there were and how many reached the observed |D| (the same statistic and null as the joined-
teacher builder, dfe08ca7). Results are COUNTS per pair, cell, lag and day, never a coefficient or an average (D37).
A pair is "beyond chance" only when shifts > 0 and none reached it; that label is orientation, the counts are the result.
TRANSFORMS (frankie_box_experiment_transforms.TRANSFORMS): every series is turned into a step series by each chosen
transform (sign_of_step, run_length, magnitude_class, level_crossing, acceleration; all causal, -1/0/+1, same length).
Pairs: x under transform T against y under the same T, and x under T against y's sign_of_step (does T of x lead the
direction of y). The statistic and the chance check are the same for every transform; each row names x_transform and
y_transform. Steps a transform could not classify (an unknown value) are counted per series and transform, never filled.
Cells: whole-day, plus every text column whose name ends in session_phase / continuity_segment / source_day /
source_role (the joined teacher's cell names); every other text column is listed as a cell not yet used.

LISTED, NOT YET SEARCHED (never dropped): the INPUT record spool (every record), transform pairs other than the two
above, other cells, conditions, targets beyond the series themselves, the teacher's Dipole source, claims
(Frankie's and Jev's) - each named in the MANIFEST's not_searched list.

WALLS. The day must be declared a discovery day; a confirmation day is refused unless a frozen survivor list is given
(--frozen-survivors), and then only the pairs on it are run. One day per run; days are never pooled. A day already
searched declines (duplicate data). Needs numpy, pyarrow and duckdb in the box venv (duckdb 1.5.5 with its bundled
extensions; a box change on Greg's go).
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_SEARCH_V1'
ROOT = Path('/opt/frankie-box/work/experiment-search')
CELL_NAMES = ('session_phase', 'continuity_segment', 'source_day', 'source_role')
F_LAST = 128                       # the exchange record flag that closes a group (the same close the frames spool marks)
NOT_SEARCHED = (
    ('root/work/derived/.rows/input-*.jsonl fields', 'per-event prices, order ids, queue positions, sequence gaps (only per-group '
     'counts and sizes by action and side are searched)'),
    ('transform pairs', 'x under transform T against y under a different transform other than sign_of_step (only T vs T '
     'and T vs sign_of_step are run); transforms not in frankie_box_experiment_transforms.TRANSFORMS'),
    ('conditions', 'conditioning on a state (e.g. book regime) before counting'),
    ('targets', 'targets other than the series themselves (e.g. the mid N groups ahead, fills, exhaustion)'),
    ('dipole on search-only days', "the teacher's Dipole measurements exist only where a launch ran (the classroom-arm days); "
     'on other days they are listed missing (running the teacher alone on CPU is possible but not built)'),
    ('claims', "Frankie's and Jev's claims (the scientific teacher's turn tests them; built next)"),
)


def unpack_spool(path):
    """Every row of a ROOT row spool, decoded by the journal's own codec, in file order (streamed)."""
    from research.kalshi.frankie_boss.c15_journal import unpack
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            yield unpack(json.loads(line))


def columns(rows, time_key):
    """{column: list} for a spool, whole: numeric columns kept as float (None -> NaN), text columns kept as text,
    anything else (lists, dicts) listed by name as not searched. Returns (numeric, text, other, count)."""
    numeric, text, other, count = {}, {}, set(), 0
    for row in rows:
        for key, value in row.items():
            if isinstance(value, bool):
                value = float(value)
            if isinstance(value, (int, float)) or value is None:
                numeric.setdefault(key, [float('nan')] * count)
            elif isinstance(value, str):
                text.setdefault(key, [None] * count)
            else:
                other.add(key)
        for key in numeric:
            v = row.get(key)
            numeric[key].append(float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else
                                (float(v) if isinstance(v, bool) else float('nan')))
        for key in text:
            v = row.get(key)
            text[key].append(v if isinstance(v, str) else None)
        count += 1
    for key in list(text):
        if key in numeric:                      # a column seen with both kinds is kept as text, listed
            other.add(key + ' (mixed numeric/text)')
    return numeric, text, sorted(other), count


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def asof_values(con, axis_t, known_at, values):
    """The ONE alignment used for every series and by its leakage gate: for each axis time, the value of the source row
    with the largest known_at <= that time (ties: the later row), via DuckDB ASOF. NaN where nothing is known yet."""
    import numpy as np
    import pyarrow as pa
    known_at = np.asarray(known_at, dtype=np.float64)
    order = np.argsort(known_at, kind='stable')
    con.register('q', pa.table({'g': np.arange(len(axis_t), dtype=np.int64), 't': np.asarray(axis_t, dtype=np.float64)}))
    con.register('src', pa.table({'k': known_at[order], 'r': np.arange(len(order), dtype=np.int64),
                                  'v': np.asarray(values, dtype=np.float64)[order]}))
    out = con.execute('SELECT src.v FROM q ASOF LEFT JOIN src ON q.t >= src.k ORDER BY q.g').fetchnumpy()
    con.unregister('q')
    con.unregister('src')
    return np.asarray(out['v'], dtype=np.float64)


def build_series(day_dir, log):
    """The axis and every series on it. Returns (axis_time, series {name: np.ndarray}, cells {name: list}, sources, notes)."""
    import numpy as np
    import pyarrow as pa
    import duckdb
    rows_dir = day_dir / 'root' / 'work' / 'derived' / '.rows'
    sources, notes = [], []
    frames_path = rows_dir / 'frames.jsonl'
    if not frames_path.is_file():
        raise SystemExit('no book-frame spool at %s: the ROOT legacy pass did not run for this day' % frames_path)
    f_num, f_text, f_other, n = columns(unpack_spool(frames_path), 'ts_recv_ns')
    sources.append(dict(source='frames', path=str(frames_path), rows=n, sha256=sha256_file(frames_path),
                        numeric=sorted(f_num), text=sorted(f_text), not_searched=f_other))
    recv = np.asarray(f_num.pop('ts_recv_ns'), dtype=np.float64)
    axis = np.fmax.accumulate(np.nan_to_num(recv, nan=-np.inf))        # the running maximum: clocks can go backwards
    backwards = int(np.count_nonzero(np.diff(recv) < 0))
    notes.append(dict(axis='F_LAST group closes', groups=n, receive_clock_steps_backwards=backwards))
    series = {'frames.' + k: np.asarray(v, dtype=np.float64) for k, v in f_num.items()}
    text_cols = {'frames.' + k: v for k, v in f_text.items()}
    con = duckdb.connect()

    gates = [dict(source='frames', passed=True, reason='the axis source itself: each value is its own group close')]

    def asof(name, known_at, values_by_col):
        """Place a source on the axis with asof_values; its leakage gate runs first, on its first numeric column."""
        first = next(iter(values_by_col))
        gate = leakage_gate(con, name, known_at, values_by_col[first])
        gates.append(gate)
        if gate['passed'] is False:
            notes.append(dict(source=name, excluded='failed the leakage gate; not placed, not searched'))
            return
        for key, values in values_by_col.items():
            series[name + '.' + key] = asof_values(con, axis, known_at, values)

    for spool, time_key in (('structures', 'ts_recv_ns'), ('prices', 'ts_recv')):
        path = rows_dir / (spool + '.jsonl')
        if not path.is_file():
            notes.append(dict(source=spool, missing=str(path)))
            continue
        num, text, other, count = columns(unpack_spool(path), time_key)
        sources.append(dict(source=spool, path=str(path), rows=count, sha256=sha256_file(path),
                            numeric=sorted(num), text=sorted(text), not_searched=other))
        known = np.asarray(num.pop(time_key), dtype=np.float64)
        num.pop('ts_event_ns', None), num.pop('ts_event', None)
        asof(spool, known, num)
        for k in text:
            notes.append(dict(source=spool, text_column=k, placed='not placed as a cell (asof of text is the next step)'))
    inputs = sorted(rows_dir.glob('input-*.jsonl'))
    if len(inputs) > 1:
        raise SystemExit('%d INPUT spools in %s (%s): the same records twice would be counted twice (duplicate data '
                         'declines the run)' % (len(inputs), rows_dir, ', '.join(p.name for p in inputs)))
    if inputs:
        counts, known, records, groups, open_group, unknown = {}, [], 0, 0, {}, 0
        for record in unpack_spool(inputs[0]):
            records += 1
            action, side = str(record.get('action')), str(record.get('side'))
            key = '%s_%s' % (action, side)
            open_group[key] = open_group.get(key, 0) + 1
            size = record.get('size')
            if isinstance(size, (int, float)) and not isinstance(size, bool):
                open_group[key + '_size'] = open_group.get(key + '_size', 0) + size
            else:
                unknown += 1
            flags = record.get('flags')
            if isinstance(flags, int) and flags & F_LAST:
                for k in set(counts) | set(open_group):
                    counts.setdefault(k, [0.0] * groups).append(float(open_group.get(k, 0)))
                known.append(float(record.get('ts_recv')) if record.get('ts_recv') is not None else float('nan'))
                groups += 1
                open_group = {}
        sources.append(dict(source='events', path=str(inputs[0]), rows=records, groups=groups, sha256=sha256_file(inputs[0]),
                            numeric=sorted(counts), records_without_numeric_size=unknown,
                            after_last_close=dict(records=sum(v for k, v in open_group.items() if not k.endswith('_size')),
                                                  note='records after the last F_LAST close belong to no closed group; counted here, not placed')))
        if groups:
            counts['total'] = [float(sum(counts[k][g] for k in counts if not k.endswith('_size'))) for g in range(groups)]
            asof('events', np.asarray(known, dtype=np.float64), counts)
    else:
        notes.append(dict(source='events', missing=str(rows_dir / 'input-*.jsonl')))
    dipole_paths = sorted((day_dir / 'run' / 'execution').glob('cycle-*/host-dipole-classroom-source*.json')) + \
        sorted((day_dir / 'teacher').glob('host-dipole-classroom-source*.json'))   # the launch's, or the teacher-only step's
    if len(dipole_paths) > 1:
        raise SystemExit('%d Dipole classroom sources for one day (%s): duplicate data declines the run'
                         % (len(dipole_paths), ', '.join(str(p) for p in dipole_paths)))
    if dipole_paths:
        from research.kalshi.frankie_boss.c15_journal import unpack
        raw = dipole_paths[0].read_bytes()
        source = unpack(json.loads(raw))
        rows = source.get('rows') or ()
        names = list(source.get('coverage_columns') or ())
        values = {name: [] for name in names}
        states = {name: {} for name in names}
        known = []
        for row in rows:
            known.append(float(row['ts_recv_ns']))
            by_name = {c['name']: c for c in row.get('components') or ()}
            for name in names:
                c = by_name.get(name) or {}
                state = str(c.get('state'))
                states[name][state] = states[name].get(state, 0) + 1
                v = c.get('value')
                values[name].append(float(v) if state == 'PRESENT' and isinstance(v, (int, float)) else float('nan'))
        sources.append(dict(source='dipole', path=str(dipole_paths[0]), rows=len(rows), sha256=hashlib.sha256(raw).hexdigest(),
                            schema=source.get('schema'), through_cursor=source.get('through_cursor'),
                            components=names, states_per_component=states,
                            note="the teacher's Dipole measurements (JournalTeacherR3), one row per context cursor; a value "
                                 'only where the state is PRESENT, the other states counted here'))
        if rows:
            asof('dipole', np.asarray(known, dtype=np.float64), values)
    else:
        notes.append(dict(source='dipole', missing=str(day_dir / 'run' / 'execution' / 'cycle-*' / 'host-dipole-classroom-source*'),
                          reason='no launch ran for this day (only the classroom-arm days have the teacher\'s Dipole rows)'))
    derived = day_dir / 'root' / 'work' / 'derived'
    flow_path, roll_path = derived / 'legacy_native_signed_flow.json', derived / 'legacy_per_second_roll20.json'
    if flow_path.is_file():
        flow = json.loads(flow_path.read_bytes())
        per = flow.get('per_second') or []
        sources.append(dict(source='legacy_native_signed_flow', path=str(flow_path), rows=len(per), sha256=sha256_file(flow_path)))
        if per:
            known = np.asarray([(p['second'] + 1) * 1e9 for p in per], dtype=np.float64)   # second s known at s+1
            asof('signed_flow', known, {'buy': [p.get('buy') for p in per], 'sell': [p.get('sell') for p in per]})
    else:
        notes.append(dict(source='legacy_native_signed_flow', missing=str(flow_path)))
    if roll_path.is_file():
        roll = json.loads(roll_path.read_bytes())
        values = roll.get('series') or []
        first = roll.get('first_second')
        sources.append(dict(source='legacy_per_second_roll20', path=str(roll_path), rows=len(values), sha256=sha256_file(roll_path)))
        if values and first is not None:
            known = np.asarray([(first + i + 1) * 1e9 for i in range(len(values))], dtype=np.float64)
            asof('roll20', known, {'value': [float('nan') if v is None else v for v in values]})
    else:
        notes.append(dict(source='legacy_per_second_roll20', missing=str(roll_path)))
    cells, unused = {}, []
    for k, v in text_cols.items():
        (cells.__setitem__(k, v) if k.endswith(CELL_NAMES) else unused.append(k))
    notes.append(dict(cells_not_yet_used=unused))
    log('series: %d on %d groups (%d receive-clock steps backwards), %d cell columns' % (len(series), n, backwards, len(cells)))
    return axis, series, cells, sources, notes, gates


def leakage_gate(con, source, known_at, values):
    """odcore.leakage on the REAL alignment (asof_values), in the source's own row order: the value aligned as of the
    moment row i became known must not change when every later row of the source is scrambled. Checked at 65 rows
    spread over the source, each the last row of its timestamp (rows known at the same instant are not "later")."""
    import numpy as np
    from odcore.leakage import assert_no_leakage
    order = np.argsort(np.asarray(known_at, dtype=np.float64), kind='stable')
    ts = np.asarray(known_at, dtype=np.float64)[order]
    p = np.asarray(values, dtype=np.float64)[order]
    n = len(p)
    last_of_time = np.nonzero(np.append(ts[1:] != ts[:-1], True))[0]
    if n < 2 or last_of_time.size < 2:
        return dict(source=source, passed=None, reason='fewer than two distinct knowledge times')
    idxs = sorted(set(int(last_of_time[k]) for k in np.linspace(0, last_of_time.size - 1, 65).astype(int)))

    def signal_at(i, ts_, p_, bv_, sv_):
        v = asof_values(con, [ts_[i]], bv_, p_)[0]
        return None if np.isnan(v) else float(v)
    passed, fails = assert_no_leakage(signal_at, ts, p, ts.copy(), np.zeros(n), idxs)
    return dict(source=source, passed=bool(passed), checked=len(idxs), fails=len(fails),
                fail_rows=[dict(row=int(i), clean=a, scrambled=b) for i, a, b in fails])


def transforms(sx):
    """The FFTs of a sign series, computed once and reused for every partner (the joined teacher's x-transforms)."""
    import numpy as np
    return dict(m=sx.size, moves=int(np.count_nonzero(sx)), s=np.fft.rfft(sx), a=np.fft.rfft(np.abs(sx)))


def couple(fx, fy, lags):
    """The joined teacher's statistic (frankie_box_joined_teacher._pair_block), exactly: counts at the best lag and the
    circular-shift chance check, from the cached transforms of the sign series of x and y (equal length m)."""
    import numpy as np
    m = fx['m']
    D = np.rint(np.fft.irfft(np.conj(fx['s']) * fy['s'], m)).astype(np.int64)      # D[k] = sum_t sx[t] * sy[t+k]
    B = np.rint(np.fft.irfft(np.conj(fx['a']) * fy['a'], m)).astype(np.int64)      # both moving at shift k
    span = min(lags, m - 1)
    lag_values = list(range(-span, span + 1))
    window = [k % m for k in lag_values]
    profile = [int(D[k]) for k in window]
    best = max(range(len(window)), key=lambda i: (abs(profile[i]), -abs(lag_values[i]), lag_values[i]))
    k_best, d_best, b_best = lag_values[best], profile[best], int(B[window[best]])
    exclusion = max(2 * lags + 1, m // 10)
    k_all = np.arange(m)
    far = np.minimum(k_all, m - k_all) > exclusion
    null_total, null_reach, null_largest = 0, 0, None
    if far.any():
        a = np.abs(D).astype(np.float64)
        try:
            from scipy.ndimage import maximum_filter1d
            wmax = maximum_filter1d(a, size=2 * lags + 1, mode='wrap')
        except ImportError:
            wmax = a.copy()
            for j in range(1, lags + 1):
                wmax = np.maximum(wmax, np.maximum(np.roll(a, j), np.roll(a, -j)))
        null = wmax[far]
        null_total, null_reach, null_largest = int(null.size), int((null >= abs(d_best)).sum()), int(null.max())
    return dict(steps=int(m), x_moves=fx['moves'], y_moves=fy['moves'], best_lag=k_best,
                same_way=int((b_best + d_best) // 2), opposite=int((b_best - d_best) // 2), both_moving=b_best,
                difference=d_best, lag_profile=profile, lag_first=lag_values[0], null_shifts=null_total,
                null_at_or_beyond=null_reach, null_largest=null_largest, null_exclusion=exclusion,
                beyond_chance=bool(null_total > 0 and null_reach == 0))


_JOB = {}


def _step_job(args):
    """One series under one transform: its step series and the steps it could not classify (an unknown value)."""
    import frankie_box_experiment_transforms as T
    name, tname = args
    values = _JOB['series'][name]
    steps = T.TRANSFORMS[tname](values)
    return tname, name, steps, T.unclassified(values, steps)


def y_transforms(tx):
    """The y-side transforms paired with x under tx: the same transform, and the direction of y (sign_of_step)."""
    return (tx,) if tx == 'sign_of_step' else (tx, 'sign_of_step')


def _cell_job(args):
    """One cell and one x series under one transform against every other series: its own part file (counts only)."""
    part, cell_col, cell_value, tx, x, lags, survivors, header = args
    steps, idx = _JOB['steps'], _JOB['cells'][(cell_col, cell_value)]
    pick = (lambda v: v) if idx is None else (lambda v: v[idx])
    sx = pick(steps[tx][x])
    if sx.size < 2:     # listed in the MANIFEST (cells_not_counted), never passed over silently (Greg, 2026-09-29)
        return part, 0, 0, dict(cell=[cell_col, str(cell_value)], transform=tx, series=x, steps=int(sx.size),
                                reason='fewer than 2 steps of this series in this cell: no step pair to count')
    fx = transforms(sx)
    count = beyond = 0
    with open(part + '.tmp', 'w') as out:
        for ty in y_transforms(tx):
            if ty not in steps:
                continue
            for y in sorted(steps[ty]):
                if y == x or (survivors is not None and (tx, x, ty, y, cell_col, cell_value) not in survivors):
                    continue
                row = dict(header, x=x, y=y, cell=cell_col, cell_value=cell_value, transform=tx, x_transform=tx,
                           y_transform=ty, **couple(fx, transforms(pick(steps[ty][y])), lags))
                out.write(json.dumps(row, sort_keys=True) + '\n')
                count += 1
                beyond += row['beyond_chance']
    os.replace(part + '.tmp', part)
    return part, count, beyond, None


def search(day, cycle, day_role, lags, frozen, log, root=ROOT, data_root=None, workers=8, transform_names=None):
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import frankie_box_experiment_transforms as T
    transform_names = list(transform_names or T.TRANSFORMS)
    unknown = [t for t in transform_names if t not in T.TRANSFORMS]
    if unknown:
        raise SystemExit('unknown transforms %s (known: %s)' % (unknown, sorted(T.TRANSFORMS)))
    data_root = Path(data_root or '/opt/frankie-box/work/experiment-data')
    day_dir = data_root / day / ('cycle-' + cycle)
    if not (day_dir / 'MANIFEST.json').is_file():
        raise SystemExit('no exported day data at %s (frankie_box_experiment_data.sh ACTION=export first)' % day_dir)
    if day_role not in ('discovery', 'confirmation'):
        raise SystemExit('--day-role discovery or confirmation required')
    survivors = None
    if day_role == 'confirmation':
        if not frozen:
            raise SystemExit('a confirmation day stays untouched until the survivor list is frozen: give --frozen-survivors')
        survivors = {(s.get('x_transform', 'sign_of_step'), s['x'], s.get('y_transform', 'sign_of_step'), s['y'],
                      s.get('cell', 'whole-day'), s.get('cell_value'))
                     for s in json.loads(Path(frozen).read_bytes())['survivors']}
        transform_names = sorted({k[0] for k in survivors} | {k[2] for k in survivors})
    target = Path(root) / day / ('cycle-' + cycle) / day_role
    if (target / 'MANIFEST.json').exists():
        raise SystemExit('%s already searched: the same day is not searched twice (duplicate data declines the run)' % target)
    axis, series, cells, sources, notes, gates = build_series(day_dir, log)
    names = sorted(series)
    import multiprocessing
    context = multiprocessing.get_context('fork')                # the workers share the arrays, no copy
    _JOB.update(series=series)
    steps, unclassified = {t: {} for t in transform_names}, {t: {} for t in transform_names}
    with context.Pool(workers) as pool:
        for tname, name, st, n_unknown in pool.imap_unordered(_step_job, [(n, t) for t in transform_names for n in names]):
            steps[tname][name] = st
            unclassified[tname][name] = n_unknown
    cell_index = {('whole-day', None): None}
    for col, values in sorted(cells.items()):
        arrived = np.asarray(values[1:], dtype=object)          # a step belongs to the cell of the group it arrives at
        for value in sorted({v for v in arrived if v is not None}):
            cell_index[(col, value)] = np.nonzero(arrived == value)[0]
    staging = target.parent / (target.name + '.partial')
    (staging / 'couplings').mkdir(parents=True, exist_ok=True)
    header = dict(day=day, cycle=cycle, day_role=day_role)
    jobs = [(str(staging / 'couplings' / ('%04d-%s-%s.jsonl' % (c, tx, hashlib.sha256(x.encode()).hexdigest()[:16]))),
             col, value, tx, x, lags, survivors, header)
            for c, (col, value) in enumerate(sorted(cell_index, key=lambda k: (k[0] != 'whole-day', k[0], str(k[1]))))
            for tx in transform_names for x in names]
    _JOB.update(steps=steps, cells=cell_index)
    started = time.time()
    parts, count, beyond, not_counted = [], 0, 0, []
    with context.Pool(workers) as pool:
        for part, n_rows, n_beyond, short in pool.imap_unordered(_cell_job, jobs):
            if short:
                not_counted.append(short)
            parts.append(part)
            count += n_rows
            beyond += n_beyond
    part_pins = [dict(path=str(Path(p).relative_to(staging)), rows=None, sha256=sha256_file(p)) for p in sorted(parts)
                 if Path(p).exists()]
    cell_specs = [(c, v, None) for c, v in cell_index]
    manifest = dict(schema=SCHEMA, day=day, cycle=cycle, day_role=day_role, at=time.time(), seconds=time.time() - started,
                    data=str(day_dir), data_manifest_sha256=sha256_file(day_dir / 'MANIFEST.json'),
                    sources=sources, notes=notes, leakage=gates, lags=lags,
                    series=names, cells=[(c, v) for c, v, _ in cell_specs],
                    transforms=dict(names=transform_names, pairs={t: list(y_transforms(t)) for t in transform_names},
                                    module_sha256=sha256_file(Path(T.__file__)),
                                    unclassified_steps=unclassified),
                    couplings=dict(parts=part_pins, rows=count, beyond_chance=beyond, jobs=len(jobs), workers=workers),
                    cells_not_counted=sorted(not_counted, key=lambda d: (d['cell'], d['transform'], d['series'])),
                    not_searched=[dict(item=a, what=b) for a, b in NOT_SEARCHED],
                    rule='counts per pair, cell, lag and day; never pooled across days; never a coefficient or an average '
                         'as the finding (D37); a confirmation day runs only the frozen survivor list',
                    frozen_survivors=str(frozen) if frozen else None, model_calls=0)
    (staging / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(staging, target)
    log('search: %d series x %d transforms (%d sources failed the leakage gate, listed), %d cells, %d pair rows, %d '
        'beyond chance (a count, not a finding by itself) in %.0f s' % (
            len(names), len(transform_names), sum(1 for g in gates if g['passed'] is False), len(cell_specs), count,
            beyond, manifest['seconds']))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--cycle', required=True)
    p.add_argument('--day-role', required=True, choices=('discovery', 'confirmation'))
    p.add_argument('--lags', type=int, default=20)
    p.add_argument('--frozen-survivors')
    p.add_argument('--workers', type=int, default=8, help='worker processes (the box has 32 CPUs)')
    p.add_argument('--transforms', help='comma list from frankie_box_experiment_transforms.TRANSFORMS (default: all)')
    a = p.parse_args()
    if not (len(a.day) == 8 and a.day.isdigit() and a.cycle.isdigit()):
        raise SystemExit('--day YYYYMMDD and --cycle NN required')
    here = Path(__file__).resolve()
    sys.path.insert(0, str(here.parents[3]))          # the checkout root: research.*, odcore.*
    m = search(a.day, a.cycle, a.day_role, a.lags, a.frozen_survivors, lambda text: print(text, flush=True),
               workers=a.workers, transform_names=[t for t in (a.transforms or '').split(',') if t] or None)
    print(json.dumps(dict(target=str(ROOT / a.day / ('cycle-' + a.cycle) / a.day_role), couplings=m['couplings'],
                          leakage_failed=[g.get('source', g.get('series')) for g in m['leakage'] if g['passed'] is False],
                          not_searched=m['not_searched']), indent=1))


if __name__ == '__main__':
    main()
