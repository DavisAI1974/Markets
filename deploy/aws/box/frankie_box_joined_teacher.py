"""The joined teacher data (Greg, 2026-09-28: "Give the teachers the bedrock tables instead of Frankie"; spec
research/kalshi/frankie_boss/SPEC-joined-teachers.md).

The teachers read the calculations the box already made. Nothing is recalculated by the producers and nothing is
copied: every layer file named by the Monday root's derive.json (the 43 bedrock layers and the 5 legacy layers) is read
in place, and each row stays whole in its own file. This module builds, beside them:

  1. the JOIN: one time-ordered axis of F_LAST groups (the member rows' group_index), every numeric leaf of every layer
     placed on it as a series (member rows by their group; lifecycle and legacy rows by their time into the group window
     that contains it, as the count of rows in the window and as the last value known at the group's F_LAST time;
     per-second legacy series by their second). A value is never averaged or normalized. A row with no group and no
     time is not dropped: it is counted and named by (layer, field, position) in unplaced.jsonl. Two different values
     for one group in one layer are not dropped: both are named in conflicts.jsonl.
  2. the COUPLINGS: for every dipole series against every other series, in every cell (the whole day, and each value
     of each cell column the members carry: session phase, continuity segment, source day, source role), the sign of
     each series' step from one group to the next is compared at every lag within +-LAGS groups. What is reported is
     COUNTS, never a coefficient (D37: a correlation is an average): at the best lag, how many steps moved the same way
     and how many moved opposite; and its null, by circular shift: over every shift far from zero, how many shifts
     reach the same largest-in-window count difference, out of how many. Every pair in every cell is written
     (couplings.jsonl), whatever its null says.
  3. the teacher sources: the series inventory (every series with its present, missing and moving counts), every coupling
     beyond its null, and the counts per cell of the ones within it, all as whole text files with sha256 and bytes in
     MANIFEST.json. The full coupling list stays beside them.

Resumable (Greg: save progress whenever anything stops): every extract part, every series and every coupling block is
saved as it completes, with a done marker; a restart skips what is saved. Progress lines go to progress.log.
No model call. Frankie's decisions are not read (rule 1): the inputs are the calculation layers only."""
import argparse
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

BOX = Path(__file__).resolve().parent
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))

SCHEMA = 'FRANKIE_JOINED_TEACHER_V1'
LAGS = 20
CELL_NAMES = ('session_phase', 'continuity_segment', 'source_day', 'source_role')
DIPOLE_RE = re.compile(r'dipole|roll20|polarity|signed_flow|imbalance|flow_substrate|aggressor', re.I)
TIME_FIELDS = ('f_last_ts_recv_ns', 'group_ts_recv_ns', 'ts_recv_ns', 'recv_ns', 'released_recv_ns', 'event_recv_ns',
               'decision_ts_recv_ns')
GROUP_TIME_FIELDS = ('f_last_ts_recv_ns', 'group_ts_recv_ns', 'ts_recv_ns')
CATEGORY_LIMIT = 4096        # a string column with more distinct values than this is an identifier, not a cell
ROWS_PER_JOB = 200_000
MIN_FREE_BYTES = int(float(os.environ.get('JOINED_MIN_FREE_GB', '40')) * 1e9)   # stop and save below this


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def witness(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha256_file(path))


def atomic_bytes(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp-%d' % os.getpid())
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False).encode())


class Log:
    """progress.log lines, and the box's standard work probe (progress.json, read by frankie_box_progress.sh)."""
    def __init__(self, out):
        self.path = Path(out) / 'progress.log'
        from frankie_box_progress import Probe
        self.probe = Probe(out, phase='joined-teacher')

    def stage(self, stage, completed=0, total=None, state='running'):
        self.probe.update(stage, completed, total, state=state)

    def __call__(self, text):
        line = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + text
        print(line, flush=True)
        with open(self.path, 'a') as f:
            f.write(line + '\n')


# ---- stage A: read every row of every layer in place, one job per fragment batch --------------------------------
def _flatten(value, prefix, out):
    """Leaves of one row. Numbers and booleans are kept as they are; a string is a category; a list is its length
    (the list itself stays whole in the layer file); a mapping is walked by dotted key."""
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(v, prefix + '.' + str(k) if prefix else str(k), out)
    elif isinstance(value, bool):
        out[prefix] = ('n', 1.0 if value else 0.0)
    elif isinstance(value, (int, float)):
        out[prefix] = ('n', float(value))
    elif isinstance(value, str):
        out[prefix] = ('s', value)
    elif isinstance(value, list):
        out[prefix + '#len'] = ('n', float(len(value)))
    elif value is None:
        out[prefix] = ('z', None)


def _time_of(row):
    for name in TIME_FIELDS:
        v = row.get(name)
        if isinstance(v, int) and not isinstance(v, bool):
            return name, v
    for name, v in row.items():
        if name.endswith('_ns') and isinstance(v, int) and not isinstance(v, bool) and v >= 10 ** 18:
            return name, v
    return None, None


def _group_of(row):
    v = row.get('group_index')
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def _rows_to_part(rows, layer, field, start, part_path):
    """One batch of rows -> a part file: per row its placement (group, time, or unplaced), per column its values."""
    import numpy as np
    n = len(rows)
    groups = np.full(n, -1, dtype=np.int64)
    has_group = np.zeros(n, dtype=bool)
    times = np.zeros(n, dtype=np.int64)
    has_time = np.zeros(n, dtype=bool)
    sections = []
    numeric, strings, time_names, unplaced = {}, {}, {}, []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            row = {'value': row}
        g = _group_of(row)
        if g is not None:
            groups[i], has_group[i] = g, True
        name, t = _time_of(row)
        if t is not None:
            times[i], has_time[i] = t, True
            time_names[name] = time_names.get(name, 0) + 1
        if g is None and t is None:
            unplaced.append(start + i)
        sec = row.get('emitting_section')
        sections.append(sec if isinstance(sec, str) else '')
        leaves = {}
        _flatten(row, '', leaves)
        for col, (kind, v) in leaves.items():
            if kind == 'n':
                if not math.isfinite(v):
                    strings.setdefault(col, {})[i] = repr(v)      # nan/inf stay named, never silently a number
                    continue
                arr = numeric.get(col)
                if arr is None:
                    arr = numeric[col] = np.full(n, np.nan)
                arr[i] = v
            elif kind == 's':
                strings.setdefault(col, {})[i] = v
    payload = dict(groups=groups, has_group=has_group, times=times, has_time=has_time)
    names = sorted(numeric)
    for j, col in enumerate(names):
        payload['n%d' % j] = numeric[col]
    meta = dict(layer=layer, field=field, start=start, rows=n, numeric=names, sections=sorted(set(sections)),
                time_names=time_names, unplaced=unplaced,
                strings={col: {str(i): v for i, v in vals.items()} for col, vals in strings.items()})
    payload['section_index'] = np.array([meta['sections'].index(s) for s in sections], dtype=np.int32)
    tmp = str(part_path) + '.tmp.npz'
    np.savez(tmp, **payload)
    os.replace(tmp, str(part_path) + '.npz')
    atomic_json(str(part_path) + '.json', meta)
    return n


def _job_published(job):
    """Consecutive fragments of one published gzip-json layer (projection layout), each row whole from its fragment."""
    path, layer, field, fragments, start, part = job
    rows = []
    with open(path, 'rb') as handle:
        for offset, width, digest, count in fragments:
            handle.seek(offset)
            raw = handle.read(width)
            if len(raw) != width or hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('%s: published fragment differs from its range receipt' % layer)
            d = zlib.decompressobj(31)
            text = d.decompress(raw) + d.flush()
            lines = text.split(b'\n') if text else []
            if len(lines) != count:
                raise ValueError('%s: fragment row count differs from its range receipt' % layer)
            for i, line in enumerate(lines):
                if i + 1 < len(lines):
                    line = line[:-1]
                rows.append(json.loads(line))
    return _rows_to_part(rows, layer, field, start, part)


def _job_stream(job):
    """One layer read sequentially (a plain JSON layer, or a gzip-json one without the projection receipts): every
    top-level array of rows is written in batches; the scalars and the per-second series are kept in the layer's meta."""
    path, layer, encoding, parts_dir = job
    from frankie_box_digest_sources import _JSON
    opener = gzip.open if encoding == 'gzip-json' else open
    parts_dir = Path(parts_dir)
    meta, written = {}, []
    with opener(path, mode='rt', encoding='utf-8') as handle:
        parser = _JSON(handle)
        parser.expect('{')
        while parser.peek() != '}':
            key = parser.value()
            parser.expect(':')
            if parser.peek() == '[':
                batch, start, index, scalars = [], 0, 0, []
                for element in parser.array():
                    if isinstance(element, (dict, list)):
                        batch.append(element)
                    else:
                        scalars.append(element)      # None stays in place: a per-second series keeps its positions
                    if len(batch) >= ROWS_PER_JOB:
                        name = parts_dir / ('%s--%s--%09d' % (layer, key, start))
                        if not Path(str(name) + '.json').exists():
                            _rows_to_part(batch, layer, key, start, name)
                        written.append(str(name))
                        start += len(batch)
                        batch = []
                    index += 1
                if batch:
                    name = parts_dir / ('%s--%s--%09d' % (layer, key, start))
                    if not Path(str(name) + '.json').exists():
                        _rows_to_part(batch, layer, key, start, name)
                    written.append(str(name))
                if scalars:
                    meta[key] = dict(series=scalars)      # a per-second (or per-index) scalar series, whole
            else:
                meta[key] = parser.value()
            if parser.peek() == '}':
                break
            parser.expect(',')
    atomic_json(parts_dir / ('%s--layer-meta.json' % layer), dict(layer=layer, meta=meta, parts=written))
    return layer, len(written)


def extract(derive_path, out, workers, log):
    """Every row of every layer into part files, in parallel; resumes from saved parts."""
    from frankie_box_digest_sources import _published_layout, _range_receipts, FRAGMENTS_PER_JOB
    derive = json.loads(Path(derive_path).read_bytes())
    entries = derive.get('layers') or {}
    parts = Path(out) / 'parts'
    parts.mkdir(parents=True, exist_ok=True)
    layers = {}
    for name, entry in entries.items():
        path = entry.get('path')
        if not path or not Path(path).is_file():
            layers[name] = dict(status=entry.get('status'), read='absent', reason=entry.get('reason'))
            continue
        layers[name] = dict(status=entry.get('status'), path=path, encoding=entry.get('encoding'), bytes=Path(path).stat().st_size)
    jobs_pub, jobs_stream = [], []
    receipts = {}
    for name, info in layers.items():
        if info.get('read') == 'absent':
            continue
        path = Path(info['path'])
        projection = path.resolve().parent.parent
        located = None
        if info.get('encoding') == 'gzip-json' and (projection / 'plan.json').is_file():
            try:
                if projection not in receipts:
                    receipts[projection] = _range_receipts(projection)
                document, arrays = _published_layout(path, name, receipts[projection])
                located = arrays
                atomic_json(parts / ('%s--layer-meta.json' % name), dict(layer=name, meta={k: v for k, v in document.items() if k not in arrays}, parts=[]))
            except ValueError as error:
                log('%s: published layout not readable (%s); read sequentially' % (name, error))
                located = None
        if located is None:
            if not (parts / ('%s--layer-meta.json' % name)).exists():
                jobs_stream.append((str(path), name, info.get('encoding'), str(parts)))
            info['read'] = 'sequential'
            continue
        info['read'] = 'fragments'
        for key, fragments in located.items():
            start = 0
            for i in range(0, len(fragments), FRAGMENTS_PER_JOB):
                batch = fragments[i:i + FRAGMENTS_PER_JOB]
                part = parts / ('%s--%s--%09d' % (name, key, start))
                if not Path(str(part) + '.json').exists():
                    jobs_pub.append((str(path), name, key, batch, start, str(part)))
                start += sum(f[3] for f in batch)
    log('extract: %d layers (%d by fragments, %d sequential), %d fragment jobs and %d layer jobs to run' % (
        len(layers), sum(1 for v in layers.values() if v.get('read') == 'fragments'),
        sum(1 for v in layers.values() if v.get('read') == 'sequential'), len(jobs_pub), len(jobs_stream)))
    import multiprocessing
    done = 0
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        futures = [pool.submit(_job_published, j) for j in jobs_pub] + [pool.submit(_job_stream, j) for j in jobs_stream]
        for future in as_completed(futures):
            future.result()
            done += 1
            log.stage('extract', done, len(futures))
            free = os.statvfs(out).f_bavail * os.statvfs(out).f_frsize
            if free < MIN_FREE_BYTES:
                for f in futures:
                    f.cancel()
                raise SystemExit('extract stopped: %.1f GB free under %s (floor %.0f GB); every finished part is saved, '
                                 'a rerun resumes' % (free / 1e9, out, MIN_FREE_BYTES / 1e9))
            if done % 50 == 0 or done == len(futures):
                log('extract: %d of %d jobs done' % (done, len(futures)))
    return layers


# ---- stage B: the join -------------------------------------------------------------------------------------------
def _parts(out):
    parts = Path(out) / 'parts'
    for meta_path in sorted(parts.glob('*--*--[0-9]*.json')):
        yield meta_path, json.loads(meta_path.read_bytes())


def _safe(name):
    return hashlib.sha256(name.encode()).hexdigest()[:24]


def join(out, log):
    """The group axis and every series on it, saved one file per series (float64, NaN = no value at that group)."""
    import numpy as np
    out = Path(out)
    series_dir = out / 'series'
    series_dir.mkdir(exist_ok=True)
    index_path = out / 'series-index.json'
    if index_path.exists():
        log('join: series already saved; reused')
        return json.loads(index_path.read_bytes())
    log.stage('join')
    metas = list(_parts(out))
    # the group axis: every group_index a member row carries, and each group's F_LAST time from the first layer that has it
    keys, times = [], {}
    for meta_path, meta in metas:
        with np.load(str(meta_path)[:-5] + '.npz') as z:
            g = z['groups'][z['has_group']]
            if g.size:
                keys.append(np.unique(g))
    axis = np.unique(np.concatenate(keys)) if keys else np.zeros(0, dtype=np.int64)
    n = axis.size
    group_time = np.full(n, -1, dtype=np.int64)
    time_source = None
    for meta_path, meta in metas:
        cols = meta['numeric']
        for name in GROUP_TIME_FIELDS:
            if name in cols and (time_source in (None, name)):
                with np.load(str(meta_path)[:-5] + '.npz') as z:
                    has = z['has_group']
                    pos = np.searchsorted(axis, z['groups'][has])
                    vals = z['n%d' % cols.index(name)][has]
                    ok = np.isfinite(vals) & (group_time[pos] < 0)
                    group_time[pos[ok]] = vals[ok].astype(np.int64)
                    time_source = name
                break
    timed = group_time >= 0
    log('join: %d F_LAST groups on the axis; %d carry a time (%s)' % (n, int(timed.sum()), time_source))
    np.save(out / 'axis-groups.npy', axis)
    np.save(out / 'axis-times.npy', group_time)
    order_times = group_time.copy()
    if timed.any():
        order_times[~timed] = np.maximum.accumulate(np.where(timed, group_time, 0))[~timed]   # an untimed group keeps its place
    backwards = int((np.diff(order_times) < 0).sum()) if n > 1 else 0
    if backwards:
        log('join: %d groups carry an F_LAST time earlier than the group before them; the window search uses the running '
            'latest time (the group times themselves are saved unchanged in axis-times.npy)' % backwards)
    order_times = np.maximum.accumulate(order_times) if n else order_times
    layer_meta = {}
    for meta_path in sorted((out / 'parts').glob('*--layer-meta.json')):
        lm = json.loads(meta_path.read_bytes())
        layer_meta[lm['layer']] = lm['meta']
    series, unplaced, conflicts, categories = {}, [], 0, {}
    conflict_file = open(out / 'conflicts.jsonl', 'w')
    buffers = {}

    def put(name):
        arr = buffers.get(name)
        if arr is None:
            arr = buffers[name] = np.full(n, np.nan)
        return arr

    totals, unplaced_totals = {}, {}
    for meta_path, meta in metas:
        key = (meta['layer'], meta['field'])
        totals[key] = totals.get(key, 0) + meta['rows']
        unplaced_totals[key] = unplaced_totals.get(key, 0) + len(meta['unplaced'])
    by_position = {key for key, total in totals.items() if total == n and unplaced_totals[key] == total}
    for key in sorted(by_position):
        log('join: %s/%s carries neither group nor time on any row and has exactly one row per group: placed by position' % key)
    # a row array with neither group nor time in a layer that declares its first second is one row per second: row p is
    # second first_second + p, complete (knowable) at the start of the next second
    by_second = {key for key, total in totals.items() if key not in by_position and unplaced_totals[key] == total
                 and isinstance((layer_meta.get(key[0]) or {}).get('first_second'), (int, float))}
    for key in sorted(by_second):
        log('join: %s/%s carries neither group nor time and its layer declares first_second: one row per second' % key)
    for meta_path, meta in metas:
        layer, field = meta['layer'], meta['field']
        with np.load(str(meta_path)[:-5] + '.npz') as z:
            has_group, groups, has_time, row_times = z['has_group'], z['groups'], z['has_time'], z['times']
        if (layer, field) in by_position:
            groups = axis[meta['start']:meta['start'] + meta['rows']].copy()
            has_group = np.ones(meta['rows'], dtype=bool)
            meta = dict(meta, unplaced=[])
        elif (layer, field) in by_second:
            first = int(layer_meta[layer]['first_second'])
            row_times = (first + meta['start'] + np.arange(meta['rows'], dtype=np.int64) + 1) * 1_000_000_000
            has_time = np.ones(meta['rows'], dtype=bool)
            meta = dict(meta, unplaced=[])
        with np.load(str(meta_path)[:-5] + '.npz') as z:
            section_index = z['section_index']
            numeric = {col: z['n%d' % j] for j, col in enumerate(meta['numeric']) if col != 'group_index'}
        for pos_row in meta['unplaced']:
            unplaced.append(dict(layer=layer, field=field, position=pos_row))
        sections = meta['sections']
        for s_i, section in enumerate(sections):
            in_section = section_index == s_i
            prefix = layer + '/' + field + ('/' + section if section else '')
            # rows placed by their group
            by_group = in_section & has_group
            if by_group.any():
                pos = np.searchsorted(axis, groups[by_group])
                for col, vals in numeric.items():
                    v = vals[by_group]
                    present = np.isfinite(v)
                    if not present.any():
                        continue
                    arr = put(prefix + '/' + col)
                    p, v = pos[present], v[present]
                    clash = np.isfinite(arr[p]) & (arr[p] != v)
                    for a, b, gi in zip(arr[p][clash], v[clash], p[clash]):
                        conflicts += 1
                        conflict_file.write(json.dumps(dict(series=prefix + '/' + col, group_index=int(axis[gi]), kept=float(a), other=float(b))) + '\n')
                    empty = ~np.isfinite(arr[p])
                    arr[p[empty]] = v[empty]
            # rows placed by their time: the group window that contains each (first group whose F_LAST time >= it)
            by_time = in_section & ~has_group & has_time
            if by_time.any() and timed.any():
                w = np.searchsorted(order_times, row_times[by_time], side='left')
                after = w >= n
                for rpos in np.nonzero(by_time)[0][after]:
                    unplaced.append(dict(layer=layer, field=field, position=meta['start'] + int(rpos), reason='after the last group'))
                w = w[~after]
                counts = put(prefix + '/#rows')
                counts[np.isnan(counts)] = 0
                np.add.at(counts, w, 1)
                idx = np.nonzero(by_time)[0][~after]
                for col, vals in numeric.items():
                    v = vals[idx]
                    present = np.isfinite(v)
                    if not present.any():
                        continue
                    arr = put(prefix + '/' + col + '@last')
                    ww, vv = w[present], v[present]
                    _, first_from_end = np.unique(ww[::-1], return_index=True)
                    last = ww.size - 1 - first_from_end       # rows in order: the last row of a window is what is known at its F_LAST
                    arr[ww[last]] = vv[last]
            elif by_time.any():
                for rpos in np.nonzero(by_time)[0]:
                    unplaced.append(dict(layer=layer, field=field, position=meta['start'] + int(rpos), reason='no group times on the axis'))
        for col, vals in meta['strings'].items():
            if col.endswith(CELL_NAMES) or any(col.split('.')[-1] == c for c in CELL_NAMES):
                bucket = categories.setdefault(layer + '/' + field + '/' + col, {})
                for i, v in vals.items():
                    i = int(i)
                    if has_group[i]:
                        bucket[int(groups[i])] = v
    conflict_file.close()
    # the last-known values carry forward from the window they were set in (what is known at each later F_LAST)
    for name, arr in buffers.items():
        if name.endswith('@last'):
            idx = np.where(np.isfinite(arr), np.arange(n), -1)
            np.maximum.accumulate(idx, out=idx)
            filled = np.where(idx >= 0, arr[np.maximum(idx, 0)], np.nan)
            arr[:] = filled
    index = {}
    for name, arr in buffers.items():
        path = series_dir / (_safe(name) + '.f8')
        arr.astype('<f8').tofile(path)
        present = int(np.isfinite(arr).sum())
        index[name] = dict(file=path.name, present=present, missing=n - present)
    # per-second legacy series (a scalar array beside a first_second): placed by the second of each group's F_LAST
    for layer_name, lmeta in sorted(layer_meta.items()):
        first = lmeta.get('first_second')
        for key, value in lmeta.items():
            if isinstance(value, dict) and 'series' in value and isinstance(first, (int, float)) and timed.any():
                raw = np.array([np.nan if v is None else float(v) if isinstance(v, (int, float)) else np.nan for v in value['series']])
                # the last COMPLETE second at each group's F_LAST (the group's own second is not finished yet)
                seconds = order_times // 1_000_000_000 - int(first) - 1
                ok = (seconds >= 0) & (seconds < raw.size)
                arr = np.full(n, np.nan)
                arr[ok] = raw[seconds[ok]]
                name = layer_name + '/' + key + '@second'
                path = series_dir / (_safe(name) + '.f8')
                arr.astype('<f8').tofile(path)
                present = int(np.isfinite(arr).sum())
                index[name] = dict(file=path.name, present=present, missing=n - present, per_second=raw.size)
    cells = {}
    for col, mapping in categories.items():
        values = sorted(set(mapping.values()))
        if len(values) > CATEGORY_LIMIT:
            continue
        codes = np.full(n, -1, dtype=np.int32)
        keys_arr = np.fromiter(mapping.keys(), dtype=np.int64, count=len(mapping))
        vals = [values.index(v) for v in mapping.values()]
        codes[np.searchsorted(axis, keys_arr)] = vals
        path = out / 'series' / ('cell-' + _safe(col) + '.i4')
        codes.astype('<i4').tofile(path)
        cells[col] = dict(file=path.name, values=values)
    with open(out / 'unplaced.jsonl', 'w') as f:
        for u in unplaced:
            f.write(json.dumps(u) + '\n')
    result = dict(groups=n, group_time_field=time_source, timed_groups=int(timed.sum()), series=index, cells=cells,
                  unplaced=len(unplaced), conflicts=conflicts)
    atomic_json(index_path, result)
    log('join: %d series, %d cell columns, %d rows unplaced (listed), %d conflicts (listed)' % (
        len(index), len(cells), len(unplaced), conflicts))
    return result


# ---- stage C: the couplings --------------------------------------------------------------------------------------
def _signs(values):
    import numpy as np
    step = np.diff(values)
    s = np.sign(step)
    s[~np.isfinite(s)] = 0
    return s


def _cell_index(series, cell_file, code):
    import numpy as np
    if cell_file is None:
        return None
    codes = np.fromfile(series / cell_file, dtype='<i4')[1:]    # a step belongs to the cell of the group it arrives at
    return np.nonzero(codes == code)[0]


def _x_transforms(job):
    """One dipole series: its step signs' transforms in every cell, saved once (the pair jobs read them)."""
    import numpy as np
    out, x_name, x_file, cell_specs, path = job
    if Path(path).exists():
        return x_name
    series = Path(out) / 'series'
    sx_all = _signs(np.fromfile(series / x_file, dtype='<f8'))
    tmp = Path(str(path) + '.tmp')
    tmp.mkdir(exist_ok=True)
    moves = {}
    for c, (cell_col, cell_file, cell_value, code) in enumerate(cell_specs):
        idx = _cell_index(series, cell_file, code)
        sx = sx_all if idx is None else sx_all[idx]
        if sx.size == 0:
            continue
        np.save(tmp / ('s%d.npy' % c), np.fft.rfft(sx))          # separate .npy files: the pair jobs map them, no copy
        np.save(tmp / ('a%d.npy' % c), np.fft.rfft(np.abs(sx)))
        moves[c] = int(np.count_nonzero(sx))
    atomic_json(tmp / 'moves.json', moves)
    os.replace(tmp, path)
    return x_name


def _pair_block(job):
    """One other series against every dipole series, in every cell. Counts only."""
    import numpy as np
    out, y_name, y_file, dipoles, cell_specs, lags, block_path = job
    if Path(block_path).exists():
        return y_name
    try:
        from scipy.ndimage import maximum_filter1d
    except ImportError:
        maximum_filter1d = None
    series = Path(out) / 'series'
    transforms = Path(out) / 'x-transforms'
    sy_all = _signs(np.fromfile(series / y_file, dtype='<f8'))
    class _X:
        def __init__(self, directory):
            self.directory, self.moves = directory, {int(k): v for k, v in json.loads((directory / 'moves.json').read_bytes()).items()}
        def __getitem__(self, key):
            if key[0] == 'm':
                return [self.moves[int(key[1:])]]
            return np.load(self.directory / (key + '.npy'), mmap_mode='r')
    xs = [(x_name, _X(transforms / _safe(x_name))) for x_name, _ in dipoles if x_name != y_name]
    rows = []
    for c, (cell_col, cell_file, cell_value, code) in enumerate(cell_specs):
        idx = _cell_index(series, cell_file, code)
        sy = sy_all if idx is None else sy_all[idx]
        m = sy.size
        if m == 0:
            continue
        fy_s, fy_a = np.fft.rfft(sy), np.fft.rfft(np.abs(sy))
        y_moves = int(np.count_nonzero(sy))
        exclusion = max(2 * lags + 1, m // 10)
        span = min(lags, m - 1)
        lag_values = list(range(-span, span + 1))
        window = [k % m for k in lag_values]
        k_all = np.arange(m)
        far = np.minimum(k_all, m - k_all) > exclusion
        for x_name, fx in xs:
            D = np.rint(np.fft.irfft(np.conj(fx['s%d' % c]) * fy_s, m)).astype(np.int64)   # D[k] = sum_t sx[t] * sy[t+k]
            B = np.rint(np.fft.irfft(np.conj(fx['a%d' % c]) * fy_a, m)).astype(np.int64)   # both moving at shift k
            profile = [int(D[k]) for k in window]
            best = max(range(len(window)), key=lambda i: (abs(profile[i]), -abs(lag_values[i]), lag_values[i]))
            k_best, d_best, b_best = lag_values[best], profile[best], int(B[window[best]])
            null_total, null_reach, null_largest = 0, 0, None
            if far.any():
                a = np.abs(D).astype(np.float64)
                if maximum_filter1d is not None:
                    wmax = maximum_filter1d(a, size=2 * lags + 1, mode='wrap')
                else:
                    wmax = a.copy()
                    for j in range(1, lags + 1):
                        wmax = np.maximum(wmax, np.maximum(np.roll(a, j), np.roll(a, -j)))
                null = wmax[far]
                null_total = int(null.size)
                null_reach = int((null >= abs(d_best)).sum())
                null_largest = int(null.max())
            rows.append(dict(x=x_name, y=y_name, cell=cell_col, cell_value=cell_value, steps=int(m),
                             x_moves=int(fx['m%d' % c][0]), y_moves=y_moves,
                             best_lag=k_best, same_way=int((b_best + d_best) // 2), opposite=int((b_best - d_best) // 2),
                             both_moving=b_best, difference=d_best, lag_profile=profile, lag_first=lag_values[0],
                             null_shifts=null_total, null_at_or_beyond=null_reach, null_largest=null_largest,
                             null_exclusion=exclusion))
    tmp = str(block_path) + '.tmp'
    with open(tmp, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    os.replace(tmp, block_path)
    return y_name


def couplings(out, index, workers, lags, all_pairs, log):
    out = Path(out)
    blocks = out / 'couplings'
    blocks.mkdir(exist_ok=True)
    transforms = out / 'x-transforms'
    transforms.mkdir(exist_ok=True)
    names = sorted(index['series'])
    dipoles = [(k, index['series'][k]['file']) for k in names if all_pairs or DIPOLE_RE.search(k)]
    cell_specs = [('whole-day', None, None, None)]
    for col, spec in sorted(index['cells'].items()):
        for code, value in enumerate(spec['values']):
            cell_specs.append((col, spec['file'], value, code))
    import multiprocessing
    context = multiprocessing.get_context('spawn')
    x_jobs = [(str(out), x, f, cell_specs, str(transforms / _safe(x))) for x, f in dipoles
              if not (transforms / _safe(x)).exists()]
    log('couplings: %d dipole series, %d series, %d cells; %d dipole transforms to make' % (
        len(dipoles), len(names), len(cell_specs), len(x_jobs)))
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        made = 0
        for future in as_completed([pool.submit(_x_transforms, j) for j in x_jobs]):
            future.result()
            made += 1
            log.stage('dipole-transforms', made, len(x_jobs))
    jobs = [(str(out), y, index['series'][y]['file'], dipoles, cell_specs, lags, str(blocks / (_safe(y) + '.jsonl')))
            for y in names if not (blocks / (_safe(y) + '.jsonl')).exists()]
    log('couplings: %d blocks to run (%d saved)' % (len(jobs), len(names) - len(jobs)))
    done = 0
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for future in as_completed([pool.submit(_pair_block, j) for j in jobs]):
            future.result()
            done += 1
            log.stage('couplings', done, len(jobs))
            if done % 20 == 0 or done == len(jobs):
                log('couplings: %d of %d blocks done' % (done, len(jobs)))
    return dict(dipoles=[d[0] for d in dipoles], cells=len(cell_specs), series=len(names))


# ---- stage D: the teacher sources --------------------------------------------------------------------------------
def _row_line(r):
    lead = ('x leads y by %d groups' % r['best_lag'] if r['best_lag'] > 0 else
            'y leads x by %d groups' % -r['best_lag'] if r['best_lag'] < 0 else 'same group')
    return ('- %s | %s | cell %s=%s | %s | same way %d, opposite %d (both moving %d of %d steps; x moved %d, y moved %d) | '
            'null: %d of %d far shifts reach %d (largest %s) | lag profile from %d: %s' % (
                r['x'], r['y'], r['cell'], r['cell_value'], lead, r['same_way'], r['opposite'], r['both_moving'], r['steps'],
                r['x_moves'], r['y_moves'], r['null_at_or_beyond'], r['null_shifts'], abs(r['difference']), r['null_largest'],
                r['lag_first'], ' '.join(str(v) for v in r['lag_profile'])))


def sources(out, index, layers, log):
    out = Path(out)
    src = out / 'sources'
    src.mkdir(exist_ok=True)
    # the series inventory, whole
    lines = ['# The joined data: every series on the F_LAST group axis (computed by code from the Monday layer files; exact counts)', '',
             '%d groups; group time field %s (%d groups timed); %d series; %d rows unplaced (listed in unplaced.jsonl); '
             '%d conflicting values (listed in conflicts.jsonl)' % (index['groups'], index['group_time_field'], index['timed_groups'],
                                                                     len(index['series']), index['unplaced'], index['conflicts']), '',
             '## Layers read', '']
    for name, info in sorted(layers.items()):
        lines.append('- %s: %s, read %s%s' % (name, info.get('status'), info.get('read'),
                                              ' (%s bytes)' % info['bytes'] if info.get('bytes') else ''))
    lines += ['', '## Cells', '']
    for col, spec in sorted(index['cells'].items()):
        lines.append('- %s: %d values: %s' % (col, len(spec['values']), ', '.join(spec['values'])))
    lines += ['', '## Series (name: groups with a value / groups without)', '']
    for name, info in sorted(index['series'].items()):
        lines.append('- %s: %d / %d' % (name, info['present'], info['missing']))
    inventory = '\n'.join(lines) + '\n'
    atomic_bytes(src / 'series-inventory.md', inventory.encode())
    # the couplings: beyond their null in full; within it counted per cell (every row is in couplings-all.jsonl)
    beyond, within, total = [], {}, 0
    with open(out / 'couplings-all.jsonl.tmp', 'w') as whole:
        for block in sorted((out / 'couplings').glob('*.jsonl')):
            with open(block) as f:
                for line in f:
                    whole.write(line)
                    r = json.loads(line)
                    total += 1
                    if r['null_shifts'] > 0 and r['null_at_or_beyond'] == 0:
                        beyond.append(r)
                    else:
                        key = (r['cell'], r['cell_value'])
                        within[key] = within.get(key, 0) + 1
    os.replace(out / 'couplings-all.jsonl.tmp', out / 'couplings-all.jsonl')
    beyond.sort(key=lambda r: (r['cell'], str(r['cell_value']), r['x'], -abs(r['difference']), r['y']))
    text = ['# Couplings beyond their null (counts, never coefficients; D37)', '',
            'Each line: dipole series x | other series y | cell | lead | at the best lag within +-%d groups, how many group-to-group '
            'steps moved the same way and how many opposite | the null: of the circular shifts far from zero, how many reach the same '
            'count difference (0 here: none do) | the count difference at every lag.' % LAGS,
            '%d pair-cells in all; %d beyond their null, listed below; the rest are counted per cell after them and every one is in '
            'couplings-all.jsonl.' % (total, len(beyond)), '']
    text += [_row_line(r) for r in beyond]
    text += ['', '## Within their null, per cell (pair-cells)', '']
    text += ['- %s=%s: %d' % (c, v, k) for (c, v), k in sorted(within.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))]
    atomic_bytes(src / 'couplings-beyond-null.md', ('\n'.join(text) + '\n').encode())
    listing = {name: witness(src / name) for name in ('series-inventory.md', 'couplings-beyond-null.md')}
    log('sources: %d pair-cells, %d beyond null; %s' % (total, len(beyond),
        ', '.join('%s %d bytes' % (k, v['bytes']) for k, v in listing.items())))
    return listing, total, len(beyond)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--calculations-receipt', required=True, help='the completed Monday calculations receipt')
    parser.add_argument('--calculations-sha256', required=True, help='its independently recorded sha256')
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument('--lags', type=int, default=LAGS)
    parser.add_argument('--all-pairs', action='store_true', help='every series against every series, not only the dipole series')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = Log(out)
    receipt = witness(args.calculations_receipt)
    if receipt['sha256'] != args.calculations_sha256:
        raise SystemExit('the calculations receipt differs from the recorded sha256')
    calculations = json.loads(Path(args.calculations_receipt).read_bytes())
    if calculations.get('schema') != 'FRANKIE_MONDAY_CALCULATIONS_V1' or calculations.get('status') != 'calculations_retained':
        raise SystemExit('completed Monday calculations required')
    args.derive = calculations['derivation']['path']
    derive = witness(args.derive)
    if derive['sha256'] != calculations['derivation']['sha256']:
        raise SystemExit('derive.json differs from the calculations receipt')
    manifest_path = out / 'MANIFEST.json'
    if manifest_path.exists():
        log('joined teacher already complete: ' + str(manifest_path))
        return
    started = time.time()
    log('joined teacher: derive %s (%s), %d workers' % (args.derive, derive['sha256'][:16], args.workers))
    layers = extract(args.derive, out, args.workers, log)
    index = join(out, log)
    pairs = couplings(out, index, args.workers, args.lags, args.all_pairs, log)
    listing, total, beyond = sources(out, index, layers, log)
    manifest = dict(schema=SCHEMA, calculations_receipt=receipt, derive=derive, layers=layers, groups=index['groups'], series=len(index['series']),
                    cells=sorted(index['cells']), unplaced=index['unplaced'], conflicts=index['conflicts'],
                    dipole_series=pairs['dipoles'], lags=args.lags, all_pairs=args.all_pairs,
                    pair_cells=total, beyond_null=beyond, couplings_all=witness(out / 'couplings-all.jsonl'),
                    sources=[dict(source_id='joined-teacher:' + name, file='sources/' + name, sha256=w['sha256'], bytes=w['bytes'])
                             for name, w in sorted(listing.items())],
                    seconds=round(time.time() - started, 1), model_calls=0, layer_writes=0)
    atomic_json(manifest_path, manifest)
    log.stage('complete', 1, 1, state='complete')
    log('joined teacher complete in %.0f s: %s' % (time.time() - started, manifest_path))


if __name__ == '__main__':
    main()
