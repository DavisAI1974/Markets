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
  external    (ingest/day-external.json, FRANKIE_DAY_EXTERNAL_V1)  Frankie's 13 historical points (COT, MOS per cycle,
              EIA-930 hourly, observed weather, storage, the calendar count, the futures curve per settlement and per
              trade), each known from its own publication stamp, read through the file's as-of reader at the halt.
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
Pairs: x under transform T against y under EVERY transform (all T x T' combinations; y_transforms). The statistic and the
chance check are the same for every pair of transforms; each row names x_transform and y_transform. Steps a transform
could not classify (an unknown value) are counted per series and transform, never filled.
Cells: whole-day, plus every text column of every source placed on the axis (the spools' text fields, the last event's
action and side at the close, the day file's text columns per entity); each distinct value is a cell.
Step #3 (2026-10-06): the per-event quantity fields of the INPUT spool (events.last.<field>, the last event's value at
the group close) and every column of every day-file table per native entity (external.<table>.<column>.entity=...) are
series too; identities and clocks are listed, not searched; a column equal to one of the thirteen aliases is covered.

LISTED, NOT SEARCHED (never dropped), each named in the MANIFEST's not_searched list with its reason: identity/clock
fields, numeric-state conditions, new targets, the bedrock planes the experiment ROOT does not derive (bedrock off),
the native journal ordinal axis (the surface helper, unwired), the teacher's Dipole rows where the teacher has not run,
and claims (tested by the scientific teacher on these counts). The MANIFEST's `planes` entry says, per plane of the
existing inventory, whether this search consumed it, listed it, or whether no producer runs for it in the experiment.

WALLS. The day must be declared a discovery day; a confirmation day is refused unless a frozen survivor list is given
(--frozen-survivors), and then only the pairs on it are run. One day per run; days are never pooled. A day already
searched declines (duplicate data). Needs numpy, pyarrow and duckdb in the box venv (duckdb 1.5.5 with its bundled
extensions; a box change on Greg's go).

RECOVERY. FRANKIE_LANE_STOP_FILE requests an orderly save. Source preparation and a currently running transform finish
their operation; prepared arrays and every completed transform are retained locally. Pair workers stop before their
next partner and save all emitted rows, the exact next partner cursor, predictor FFTs and counts. Submitted workers
drain before exit 75. Resume reuses these source/code-bound states in the same .partial directory. A hard-killed
operation without matching state is retained and refused, never silently overwritten or represented as recovered.
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
# Identity and clock fields of a raw MBO record: an order id, a sequence number or a timestamp is not a quantity whose
# steps mean anything, so they are listed, never searched (every quantity field of the record is searched, below).
EVENT_IDENTITY_FIELDS = ('order_id', 'sequence', 'channel_id', 'instrument_id', 'publisher_id', 'ts_recv_ns', 'ts_event_ns',
                         'ts_in_delta_ns', 'ts_recv', 'ts_event', 'rtype', 'hd')
# Step #3 (2026-10-06, CCode): what is and is not searched, kept truthful per plane. The map behind it:
# research/kalshi/frankie_boss/CCODE_STEP3_SOURCE_COVERAGE_20261006.md.
NOT_SEARCHED = (
    ('root/work/derived/.rows/input-*.jsonl identities', 'per-event identity and clock fields (%s) are listed, not searched; '
     'every quantity field of each record is searched as events.last.<field> (its value at the group close) beside the '
     'per-group counts and sizes by action and side' % ', '.join(EVENT_IDENTITY_FIELDS)),
    ('conditions beyond the text cells', 'conditioning on a numeric state (e.g. the sign of a book series at the decision row): '
     'frankie_box_experiment_surface.state_masks builds such masks but is not wired; which states condition the count is '
     'a design decision (every series x 3 signs would multiply the jobs by hundreds)'),
    ('targets', 'targets other than the series themselves (e.g. the mid N groups ahead, fills, exhaustion); a lagged series '
     'is already the y side at lag k, a fill count is already events.F_* per group; new target definitions are a '
     'mathematical decision'),
    ('per-level FIFO queue, order age, rolling activity and integrity at each F_LAST close',
     'the pinned V4 adapter produces them in every event frame (book.bid_levels[i]/ask_levels[i]: size, order_count, '
     'front_order_size, front_order_age_s, queue_age_median_s, queue_age_p90_s, largest_order_share; activity.<1|5|20|'
     '60|300>.*; integrity.*) and the sealed journal keeps that frame in each APPLIED entry; the ROOT legacy pass spools '
     'only best/mid/depth_imbalance_n and the eight BOOK_FIELDS of it (frankie_box_boss_session.py, the frames spool), so '
     'no spool this search reads carries them: produced, not carried (the required change is named in the Step #3 map)'),
    ("the D chain's own state and the Dipole rows' state reasons",
     'c15_dstate.DState (anchor_dir, armed, broken, E, pull_depth, n_ext, m_last/m_prev, p_last/p_prev, g_E, age, '
     'duration_last) is computed inside the pinned teacher and retained only as the six chain columns searched as '
     'dipole.*; each row keeps every column\'s state (PRESENT/MISSING/INVALID/ABLATED) and raw_reason (CHAIN_BROKEN, '
     'NO_COMPLETED_STEP, DEGENERATE_STEP, ...), which this search counts in the manifest and does not use as cells'),
    ('structure identity lists', 'structures.order_ids[i] and structures.fill_disposition.*_order_ids[i] are order '
     'identities flattened by position; they are searched as numeric series like every other leaf (listed here so the '
     'count of searched series is read correctly; an identity has no steps of its own)'),
    ('bedrock-only layers', 'the cross-group forms that only the bedrock traversal and projection produce (order identity '
     'transitions and per-order lifecycles, contract/session roll state, bootstrap receipts, family lineage across groups, '
     'open-world predecessor state, ancestry gaps, the bedrock replenishment/absorption and episode rows, v4 mechanics '
     'fifo features, book-regime paths, feature-availability stamps, the five pre-birth layers, the discovery/evaluation/'
     'lock clocks) are not derived by the experiment ROOT (bedrock off, Greg 2026-09-29) and are excluded from the export '
     '(BEDROCK); their per-group forms that the legacy pass and the teacher DO produce are searched (plane receipt); '
     're-enabling the rest is a producer-activation decision, not a search change'),
    ('ROOT failures spool', 'root/work/derived/.rows/failures.jsonl (records the legacy pass could not apply) is not a '
     'series; it is listed in the ROOT receipt, not searched'),
    ('native journal ordinal axis', 'frankie_box_experiment_surface.journal_axis reads every INPUT/APPLIED entry of the sealed '
     'journal (full book, FIFO order ids, APPLIED frame fields) on the native ordinal; it is not wired: it materializes '
     'every entry whole (the full-book observation per APPLIED entry) and changes the axis from group closes to entries, '
     'which is a mathematical decision on step counts, lags and the chance check'),
    ('dipole where the teacher has not run', "the teacher's Dipole rows (the per-day teacher step, or a launch's) are searched "
     'when exported; a day whose teacher rows are not exported yet is listed missing, never searched without them'),
    ('claims', "Frankie's, Jev's and the historical claims are not searched here: frankie_box_scientific_teacher.py tests "
     'them on these counts (its lessons files)'),
)



def directive_witness():
    """The experiment's directive (Greg, 2026-09-29), named in this step's record: what the run is shooting for.
    research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json, whole text in the receipt."""
    path = Path(__file__).resolve().parents[3] / 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), directive=json.loads(data))

def unpack_spool(path):
    """Every row of a ROOT row spool, decoded by the journal's own codec, in file order (streamed)."""
    from research.kalshi.frankie_boss.c15_journal import unpack
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            yield unpack(json.loads(line))


def columns(rows, time_key):
    """Every scalar leaf of a spool, including all list positions; integers remain exact Python integers."""
    numeric, text, other, count = {}, {}, set(), 0
    def flatten(value, prefix=''):
        if isinstance(value, dict) and value:
            for k, v in value.items():
                yield from flatten(v, prefix + ('.' if prefix else '') + str(k))
        elif isinstance(value, (list, tuple)) and value:
            for i, v in enumerate(value):
                yield from flatten(v, '%s[%d]' % (prefix, i))
        elif isinstance(value, (bytes, bytearray)):
            yield prefix + '.byte_length', len(value)
            yield prefix + '.bytes_integer', int.from_bytes(value, 'big')
        elif isinstance(value, (dict, list, tuple)):
            yield prefix, json.dumps(value, sort_keys=True)
        elif value is None or isinstance(value, (bool, int, float, str)):
            yield prefix, value
        else:
            raise TypeError('unhandled retained field %s: %s' % (prefix, type(value).__name__))
    for row in rows:
        leaves = list(flatten(row))
        row = dict(leaves)
        if len(row) != len(leaves):
            raise ValueError('retained nested field names collide; no field may be silently overwritten')
        for key, value in row.items():
            if isinstance(value, (int, float)) or value is None:
                numeric.setdefault(key, [None] * count)
            elif isinstance(value, str):
                text.setdefault(key, [None] * count)
            else:
                raise TypeError('unhandled field %s' % key)
        for key in numeric:
            v = row.get(key)
            numeric[key].append(v if isinstance(v, (int, float)) else None)
        for key in text:
            v = row.get(key)
            text[key].append(v if isinstance(v, str) else None)
        count += 1
    for key in set(text) & set(numeric):
        other.add(key + ' (mixed kinds: numeric and text channels both retained)')
    return numeric, text, sorted(other), count


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def asof_values(con, axis_t, known_at, values):
    """The ONE alignment used for every series and by its leakage gate: for each axis time, the value of the source row
    with the largest known_at <= that time (ties: the later row). Integer stamps remain exact;
    None where nothing is known yet, and native values are retained without a float conversion."""
    import numpy as np
    valid = [i for i, t in enumerate(known_at) if isinstance(t, (int, np.integer))]
    order = sorted(valid, key=lambda i: known_at[i])  # stable ties: the last published row
    times = np.asarray([known_at[i] for i in order], dtype=np.int64)
    positions = np.searchsorted(times, np.asarray(axis_t, dtype=np.int64), side='right') - 1
    return np.asarray([values[order[i]] if i >= 0 else None for i in positions], dtype=object)


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
    recv = np.asarray(f_num.pop('ts_recv_ns'), dtype=np.int64)
    axis = np.maximum.accumulate(recv)  # exact nanoseconds; no loss of ordering above 2**53
    backwards = int(np.count_nonzero(np.diff(recv) < 0))
    notes.append(dict(axis='F_LAST group closes', groups=n, receive_clock_steps_backwards=backwards))
    series = {'frames.' + k: np.asarray(v, dtype=object) for k, v in f_num.items()}
    text_cols = {'frames.' + k: v for k, v in f_text.items()}
    con = duckdb.connect()

    gates = [dict(source='frames', passed=True, reason='the axis source itself: each value is its own group close')]

    def asof(name, known_at, values_by_col):
        """Place a source on the axis with asof_values; its leakage gate runs first, on its first numeric column."""
        for key, values in values_by_col.items():
            gate = leakage_gate(con, name + '.' + key, known_at, values)
            gates.append(gate)
            if gate['passed'] is False:
                notes.append(dict(source=name, field=key, excluded='failed the leakage gate'))
                continue
            series[name + '.' + key] = asof_values(con, axis, known_at, values)

    for spool, time_key in (('structures', 'ts_recv_ns'), ('prices', 'ts_recv')):
        path = rows_dir / (spool + '.jsonl')
        if not path.is_file():
            notes.append(dict(source=spool, missing=str(path)))
            continue
        num, text, other, count = columns(unpack_spool(path), time_key)
        sources.append(dict(source=spool, path=str(path), rows=count, sha256=sha256_file(path),
                            numeric=sorted(num), text=sorted(text), not_searched=other))
        known = num.pop(time_key)
        num.pop('ts_event_ns', None), num.pop('ts_event', None)
        asof(spool, known, num)
        for k, values in text.items():
            text_cols[spool + '.' + k] = asof_values(con, axis, known, values).tolist()
    inputs = sorted(rows_dir.glob('input-*.jsonl'))
    if len(inputs) > 1:
        raise SystemExit('%d INPUT spools in %s (%s): the same records twice would be counted twice (duplicate data '
                         'declines the run)' % (len(inputs), rows_dir, ', '.join(p.name for p in inputs)))
    if inputs:
        counts, known, records, groups, open_group, unknown = {}, [], 0, 0, {}, 0
        # Step #3: every quantity field of every INPUT record (price, size, flags, ...) is a series too, placed as of its
        # own receive time, so the group close reads the last event's value (the asof rule every source follows).
        # Identity and clock fields are listed (EVENT_IDENTITY_FIELDS); text fields (action, side) become cells.
        event_fields, event_text, event_known, event_identities, event_other = {}, {}, [], set(), set()
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
            stamp = record.get('ts_recv', record.get('ts_recv_ns'))
            event_known.append(stamp)
            for field, value in record.items():
                if field in EVENT_IDENTITY_FIELDS:
                    event_identities.add(field)
                    continue
                if isinstance(value, bool):
                    value = int(value)
                if isinstance(value, (int, float)):
                    event_fields.setdefault(field, [None] * (records - 1)).append(value)
                elif isinstance(value, str):
                    event_text.setdefault(field, [None] * (records - 1)).append(value)
                elif value is not None:
                    event_other.add(field)
            for field, values in event_fields.items():
                if len(values) < records:
                    values.append(None)
            for field, values in event_text.items():
                if len(values) < records:
                    values.append(None)
            flags = record.get('flags')
            if isinstance(flags, int) and flags & F_LAST:
                for k in set(counts) | set(open_group):
                    counts.setdefault(k, [0.0] * groups).append(float(open_group.get(k, 0)))
                known.append(record.get('ts_recv'))
                groups += 1
                open_group = {}
        sources.append(dict(source='events', path=str(inputs[0]), rows=records, groups=groups, sha256=sha256_file(inputs[0]),
                            numeric=sorted(counts), records_without_numeric_size=unknown,
                            per_event_fields=dict(searched=['events.last.' + f for f in sorted(event_fields)],
                                                  cells=['events.last.' + f for f in sorted(event_text)],
                                                  identities_and_clocks=sorted(event_identities),
                                                  not_searched=sorted(event_other)),
                            after_last_close=dict(records=sum(v for k, v in open_group.items() if not k.endswith('_size')),
                                                  note='records after the last F_LAST close belong to no closed group; counted here, not placed')))
        if groups:
            counts['total'] = [float(sum(counts[k][g] for k in counts if not k.endswith('_size'))) for g in range(groups)]
            asof('events', known, counts)
        if records and event_fields:
            asof('events.last', event_known, event_fields)
        for field, values in event_text.items():
            text_cols['events.last.' + field] = asof_values(con, axis, event_known, values).tolist()
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
            known.append(row['ts_recv_ns'])
            by_name = {c['name']: c for c in row.get('components') or ()}
            for name in names:
                c = by_name.get(name) or {}
                state = str(c.get('state'))
                states[name][state] = states[name].get(state, 0) + 1
                v = c.get('value')
                values[name].append(v if state == 'PRESENT' and isinstance(v, (int, float)) else None)
        sources.append(dict(source='dipole', path=str(dipole_paths[0]), rows=len(rows), sha256=hashlib.sha256(raw).hexdigest(),
                            schema=source.get('schema'), through_cursor=source.get('through_cursor'),
                            components=names, states_per_component=states,
                            note="the teacher's Dipole measurements (JournalTeacherR3), one row per context cursor; a value "
                                 'only where the state is PRESENT, the other states counted here'))
        if rows:
            asof('dipole', known, values)
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
            known = [(p['second'] + 1) * 10**9 for p in per]   # second s known at s+1
            asof('signed_flow', known, {'buy': [p.get('buy') for p in per], 'sell': [p.get('sell') for p in per]})
    else:
        notes.append(dict(source='legacy_native_signed_flow', missing=str(flow_path)))
    if roll_path.is_file():
        roll = json.loads(roll_path.read_bytes())
        values = roll.get('series') or []
        first = roll.get('first_second')
        sources.append(dict(source='legacy_per_second_roll20', path=str(roll_path), rows=len(values), sha256=sha256_file(roll_path)))
        if values and first is not None:
            known = [(first + i + 1) * 10**9 for i in range(len(values))]
            asof('roll20', known, {'value': [float('nan') if v is None else v for v in values]})
    else:
        notes.append(dict(source='legacy_per_second_roll20', missing=str(roll_path)))
    # Frankie's 13 historical points (FRANKIE_DAY_EXTERNAL_V1, Greg 2026-09-29: "everyone who sees his ingest should
    # see these data points too"): the day file attached beside the sealed ingest, exported with the ingest, read
    # through its one as-of reader at the day's halt (a value past it is refused, never filtered), each point a series
    # known from its own publication stamp; the leakage gate runs on each as on every other source.
    external = day_dir / 'ingest' / 'day-external.json'
    external_receipt = day_dir / 'ingest' / 'day-external-receipt.json'
    if external.is_file():
        from research.kalshi.frankie_boss.operations.frankie_day_external import AsOfReader, search_series
        body = json.loads(external.read_bytes())
        reader = AsOfReader.open(external, body['halt_ns'], external_receipt if external_receipt.is_file() else None)
        ext, absent = search_series(reader)
        for name, (known, values) in sorted(ext.items()):
            asof('external.' + name, known, {'value': values})
        # Step #3: every other column of every table of the day file, per native entity (station, model, contract, ...),
        # at its own publication stamp (frankie_box_experiment_surface.external_fields, built 2026-10-06, uncalled until
        # now). A column whose stamps and values are exactly an alias series above is covered by it (never searched
        # twice); the stamp column and the entity identities are clocks/identities, listed; text columns become cells.
        # SEARCH_EXTERNAL_FIELDS=aliases keeps the thirteen aliases only (a runtime decision, recorded in the manifest).
        mode = os.environ.get('SEARCH_EXTERNAL_FIELDS', 'all')
        covered, text_fields, mixed, searched_fields, identity_fields = [], [], [], [], []
        if mode == 'all':
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import frankie_box_experiment_surface as SURFACE
            alias_arrays = {(tuple(k), tuple(v)) for k, v in ext.values()}
            identity_columns = {'model', 'station', 'respondent', 'raw_symbol', 'symbol', 'instrument_id', 'publisher_id',
                                'horizon_days', 'rank', 'target_day', 'contract'}
            for key, (stamps, values) in sorted(SURFACE.external_fields(reader).items()):
                column = key.split('.entity=')[0].rsplit('.', 1)[-1]
                if column == 'published_ns' or column in identity_columns:
                    identity_fields.append(key)
                    continue
                if (tuple(stamps), tuple(values)) in alias_arrays:
                    covered.append(key)
                    continue
                kinds = {type(v) for v in values if v is not None and not isinstance(v, bool)}
                if kinds and kinds <= {int, float}:
                    asof('external.' + key, stamps, {'value': values})
                    searched_fields.append(key)
                elif kinds <= {str}:
                    text_cols['external.' + key] = asof_values(con, axis, stamps, values).tolist()
                    text_fields.append(key)
                else:
                    mixed.append(dict(field=key, kinds=sorted(k.__name__ for k in kinds)))
        sources.append(dict(source='external', path=str(external), sha256=sha256_file(external), schema=body.get('schema'),
                            receipt=str(external_receipt) if external_receipt.is_file() else None,
                            series=sorted(ext), absent=absent, missing=body.get('missing'),
                            all_fields=dict(mode=mode, searched=searched_fields, cells=text_fields, covered_by_alias=covered,
                                            identities_and_clocks=identity_fields, not_searched_mixed_or_nested=mixed)))
    else:
        notes.append(dict(source='external', missing=str(external),
                          reason="no day file of Frankie's 13 points beside the ingest (frankie_box_day_external.sh)"))
    cells, unused = {}, []
    for k, v in text_cols.items():
        cells[k] = v
    notes.append(dict(cells_not_yet_used=unused))
    log('series: %d on %d groups (%d receive-clock steps backwards), %d cell columns' % (len(series), n, backwards, len(cells)))
    return axis, series, cells, sources, notes, gates


def leakage_gate(con, source, known_at, values):
    """odcore.leakage on the REAL alignment (asof_values), in the source's own row order: the value aligned as of the
    moment row i became known must not change when every later row of the source is scrambled. Checked at 65 rows
    spread over the source, each the last row of its timestamp (rows known at the same instant are not "later")."""
    import numpy as np
    from odcore.leakage import assert_no_leakage
    valid = [i for i, t in enumerate(known_at) if isinstance(t, (int, np.integer))]
    order = sorted(valid, key=lambda i: known_at[i])
    ts = np.asarray([known_at[i] for i in order], dtype=np.int64)
    p = np.asarray([values[i] for i in order], dtype=object)
    n = len(p)
    last_of_time = np.nonzero(np.append(ts[1:] != ts[:-1], True))[0]
    if n < 2 or last_of_time.size < 2:
        return dict(source=source, passed=None, reason='fewer than two distinct knowledge times')
    idxs = sorted(set(int(last_of_time[k]) for k in np.linspace(0, last_of_time.size - 1, 65).astype(int)))

    def signal_at(i, ts_, p_, bv_, sv_):
        v = asof_values(con, [ts_[i]], bv_, p_)[0]
        return v
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


def _stop_requested():
    path = os.environ.get('FRANKIE_LANE_STOP_FILE')
    return bool(path and Path(path).is_file())

def _save_state(path, body):
    from research.kalshi.frankie_boss.parallel_teacher import _save_raw_state
    _save_raw_state(Path(path), body)

def _load_state(path, identity):
    from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
    state = _load_raw_state(Path(path))
    if state['identity'] != identity:
        raise ValueError('saved search state belongs to different inputs or search code: %s' % path)
    return state

def _run_pending(context, workers, function, jobs):
    """Keep only the held lane's workers in flight; a stop drains each submitted operation."""
    from collections import deque
    pending, source = deque(), iter(jobs)
    with context.Pool(workers) as pool:
        def fill():
            while len(pending) < workers and not _stop_requested():
                job = next(source, None)
                if job is None:
                    break
                pending.append((job, pool.apply_async(function, (job,))))
        fill()
        while pending:
            job, result = pending.popleft()
            yield job, result.get()
            fill()

def _step_job(args):
    identity = dict(search=_JOB['identity'], job=args)
    path = _JOB['recovery'] / ('step-' + hashlib.sha256(json.dumps(args).encode()).hexdigest() + '.pkl')
    if path.is_file():
        return _load_state(path, identity)['result']
    result = _step_job_compute(args)
    _save_state(path, dict(identity=identity, result=result))
    return result


def _step_job_compute(args):
    """One series under one transform: its step series and the steps it could not classify (an unknown value)."""
    import frankie_box_experiment_transforms as T
    name, tname = args
    values = _JOB['series'][name]
    steps = T.TRANSFORMS[tname](values)
    return tname, name, steps, T.unclassified(values, steps)


def y_transforms(tx):
    """The y-side transforms paired with x under tx: every transform (all T x T' pairs are run; the manifest's
    transforms.pairs records exactly this roster)."""
    import frankie_box_experiment_transforms as T
    return tuple(T.TRANSFORMS)


# Step #3 plane receipt (CCode, 2026-10-06). One row per registry layer of the complete registry (49, the pin
# knowledge/CYCLE_CALCULATION_PINS.md) plus the categories the calculations themselves find (action-string families, mirror
# identity, fill disposition, discovery status, the D chain's reasons) and the day file. Each row: the status of the plane
# on the experiment path, the exact series/cells this search consumes it through (or nothing), and what remains of it.
#   consumed            every retained form of the layer the path produces is a series or cell of this search
#   consumed_partial    a per-group or teacher form is searched; a cross-group or per-level form of it is not (named)
#   produced_not_carried the pinned producer computes it at every F_LAST close (it is in the journal's APPLIED frame) but
#                       the ROOT legacy pass does not spool it, so no file this search reads carries it
#   computed_not_retained the pinned teacher computes it and retains only a projection of it (named)
#   built_not_called    an implementation exists in the repository and nothing on the experiment path calls it
#   not_produced        only the bedrock traversal/projection (ROOT processes 2 and 3, off) produces it
#   clock               a timestamp or availability rule; it places the series, it is not searched as one
# The source keys name this search's own sources, so 'consumed' is downgraded to listed_missing / not_in_this_export when
# the run did not read that source: the receipt says what this run read, never a claim of coverage.
PLANE_COVERAGE = (
    # registry group: legacy (5)
    ('legacy_price', 'prices', 'consumed', 'prices.price, prices.size, prices.bid_px_00, prices.ask_px_00 (trades, as-of)', None),
    ('legacy_native_signed_flow', 'legacy_native_signed_flow', 'consumed', 'signed_flow.buy, signed_flow.sell (per second, as-of)', None),
    ('legacy_per_second_roll20', 'legacy_per_second_roll20', 'consumed', 'roll20.value (per second, as-of)', None),
    ('legacy_book_imbalance', 'frames', 'consumed', 'frames.best_bid/best_ask/mid/depth_imbalance_n, frames.spread, '
     'depth_imbalance_full, bid/ask_depth_full, bid/ask_order_count_full, bid/ask_price_level_count_full (the axis); '
     'cell frames.transition (the sign signature)', None),
    ('legacy_structure_observables', 'structures', 'consumed', 'structures.* per F_LAST group (describe_structure): '
     'action_counts.<action>, side_counts.<side>, component_count, distinct_price_count, distinct_order_id_count, '
     'price_raw_min/max/span, matches_carried_native_family, fill_disposition.*_count; cells action_string, side_string, '
     'terminal_action, terminal_side, candidate_family_id, discovery_status, carried_native_family, mirror.side_string, '
     'mirror.mirror_side_string, mirror.mirror_pair_key, mirror.orientation, fill_disposition.class, '
     'fill_disposition.signature', None),
    ('legacy_observable_crosswalk', None, 'clock', 'registry bookkeeping (which legacy observable maps to which native '
     'layer); not a data plane', None),
    # registry group: derived geometry (8)
    ('derived_d_family_geometry', 'structures', 'consumed_partial', 'the per-group family descriptor above (every '
     'action-string family the calculation finds, carried seed or open-world candidate, its mirror identity and fill '
     'disposition) as structures.* series and cells', 'the cross-group family lineage rows (bedrock projection) are not produced'),
    ('derived_roll20_and_dipole_state', 'legacy_per_second_roll20', 'consumed_partial', 'roll20.value',
     'the per-second dipole state (native_flow_substrate.complete_second, bedrock) is not produced'),
    ('derived_unresolved_age_chain_trajectory', 'dipole', 'consumed_partial', "the teacher's six chain columns "
     'dipole.unresolved_age_groups_log, extension_count_log, step_ratio_log, pullback_ticks_last_log, '
     'step_duration_groups_log, pullback_ticks_prev_log (4.10 exhaustion in its teacher form)',
     "the chain's own state (c15_dstate.DState) is computed, not retained; the bedrock episode rows are not produced"),
    ('derived_open_world_predecessor_state', 'structures', 'consumed_partial', 'cell structures.discovery_status '
     '(CARRIED_SEED_MATCH / OPEN_WORLD_CANDIDATE per group)', 'predecessor state across groups (bedrock) is not produced'),
    ('derived_ancestry_gaps', None, 'not_produced', None, 'bedrock projection only'),
    ('derived_price_flow_book_paths', 'frames', 'consumed_partial', 'the legacy path: prices.*, frames.*, signed_flow.*',
     'the book-regime path (native_book_regime.observe_snapshot, bedrock) is not produced'),
    ('derived_v4_mechanics_fifo_features', None, 'produced_not_carried', None, 'the V4 window extras exist per frame '
     '(native_full_capture_adapter._window_extras, bedrock) and the per-level fields below; neither is spooled'),
    ('derived_feature_availability_timestamps', None, 'clock', 'the as-of placement of every series at its own '
     'receive stamp (asof_values) is this layer applied, per source', None),
    # registry group: pre-birth (5)
    ('prebirth_predecessor_at_risk_state', None, 'not_produced', None, 'bedrock projection only'),
    ('prebirth_unresolved_chain_extension_state', 'dipole', 'consumed_partial', 'dipole.extension_count_log, '
     'step_ratio_log, pullback_ticks_* (the teacher form of the extension state)', 'the pre-birth layer itself is not produced'),
    ('prebirth_ancestry_successor_opportunity', None, 'not_produced', None, 'bedrock projection only'),
    ('prebirth_stopped_chain_false_context_controls', None, 'not_produced', None, 'bedrock projection only'),
    ('prebirth_negative_opportunity_cases', None, 'not_produced', None, 'bedrock projection only'),
    # registry group: causal clocks (7)
    ('clock_event_time', None, 'clock', 'ts_event / ts_event_ns of every row: read, popped before the search (a clock)', None),
    ('clock_receive_time', 'frames', 'clock', 'ts_recv_ns: the axis (running maximum of the frames\' receive clock) and '
     'the known-at stamp of every source', None),
    ('clock_event_known_by', None, 'clock', 'the as-of rule: a value is read at the first group close at or after its '
     'receive stamp', None),
    ('clock_feature_availability', None, 'clock', 'the leakage gate (odcore.leakage.assert_no_leakage) on every source', None),
    ('clock_prospective_discovery_confirmation', None, 'not_produced', None, 'a host/bedrock clock; the experiment\'s '
     'confirmation is the scientific teacher\'s lessons, not a series'),
    ('clock_model_evaluation', None, 'not_produced', None, 'host clock, not on the experiment path'),
    ('clock_lock_time', None, 'not_produced', None, 'host clock, not on the experiment path'),
    # registry group: order lifecycle (9)
    ('order_lifecycle_adds', 'events', 'consumed_partial', 'events.<action>_<side> per-group counts and sizes; '
     'events.last.* (price, price_raw, size, flags, is_last, is_snapshot and every other quantity field) at the close; '
     'cells events.last.action, events.last.side', 'per-order linking (bedrock) is not produced'),
    ('order_lifecycle_cancels', 'events', 'consumed_partial', 'as adds', 'per-order linking (bedrock) is not produced'),
    ('order_lifecycle_modifies', 'events', 'consumed_partial', 'as adds; the teacher\'s far_priority_loss_rate_64/1024',
     'per-order linking (bedrock) is not produced'),
    ('order_lifecycle_replaces', 'events', 'consumed_partial', 'as adds', 'per-order linking (bedrock) is not produced'),
    ('order_lifecycle_trades', 'prices', 'consumed_partial', 'prices.*, events.T_*, signed_flow.*', 'per-order linking is not produced'),
    ('order_lifecycle_fills', 'structures', 'consumed_partial', 'structures.fill_disposition.fill_id_count, '
     'cancelled_fill_id_count, modified_fill_id_count, same_id_cancel_modify_count, unresolved_fill_id_count; cells '
     'fill_disposition.class, fill_disposition.signature; events.F_* counts; the teacher\'s far_absorption_share_64/1024',
     'the per-order fill disposition across groups (bedrock) is not produced'),
    ('order_lifecycle_clears', 'events', 'consumed_partial', 'events.R_* / events.last.action == R and is_snapshot',
     'the clear/bootstrap receipts (bedrock) are not produced'),
    ('order_identity_transitions', None, 'not_produced', None, 'bedrock traversal only'),
    ('contract_session_roll_state', None, 'not_produced', None, 'bedrock traversal only'),
    # registry group: full-book FIFO queue (8)
    ('full_bid_ask_depth', 'frames', 'consumed_partial', 'frames.bid_depth_full, frames.ask_depth_full',
     'per-level size (book.bid_levels[i].size / ask_levels[i].size, top 10 each side) is produced per frame, not spooled'),
    ('price_level_and_order_counts', 'frames', 'consumed_partial', 'frames.bid/ask_price_level_count_full, '
     'frames.bid/ask_order_count_full', 'per-level order_count is produced per frame, not spooled'),
    ('fifo_queues', None, 'produced_not_carried', None, 'the FIFO order of every level is in the journal\'s APPLIED '
     'observation (c15_observer.observe_book) and the frame\'s levels; not spooled; the teacher consumes it internally'),
    ('queue_age_and_survival', 'dipole', 'consumed_partial', 'the teacher\'s far_front_age_log, far_queue_age_p90_log, '
     'far_identity_survival_64/1024, far_size_retention_64/1024 (far-side top-three cohort)',
     'per-level front_order_age_s, queue_age_median_s, queue_age_p90_s for the top 10 levels each side are produced per '
     'frame, not spooled'),
    ('queue_concentration', 'dipole', 'consumed_partial', 'the teacher\'s far_size_hhi',
     'per-level largest_order_share and front_order_size are produced per frame, not spooled'),
    ('orders_and_volume_ahead', None, 'produced_not_carried', None, 'volume_ahead per resting order is derivable from the '
     'APPLIED observation\'s FIFO ids and sizes; not spooled'),
    ('spread_and_depth_imbalance', 'frames', 'consumed', 'frames.spread, frames.depth_imbalance_n, frames.depth_imbalance_full', None),
    ('complete_state_reset_bootstrap_receipts', 'events', 'consumed_partial', 'events.last.is_snapshot (the record flag)',
     'the bootstrap receipts (bedrock) are not produced'),
    # registry group: microstructure mechanics (7)
    ('mechanics_actions_by_side_and_level', 'structures', 'consumed_partial', 'structures.action_counts.*, side_counts.*, '
     'events.<action>_<side>', 'by level: the frame\'s rolling activity windows (1/5/20/60/300 s: action_count, '
     'action_qty, action_side_qty, top_level_add/cancel_qty_derived) are produced per frame, not spooled'),
    ('aggressor_and_native_signed_flow', 'legacy_native_signed_flow', 'consumed_partial', 'signed_flow.buy/sell per second',
     'the frame\'s trade_buy/sell_aggressor_qty and trade_aggressor_imbalance per window are produced, not spooled'),
    ('depletion_and_replenishment', 'dipole', 'consumed_partial', 'the teacher\'s far_replenish_log1p_64/1024, '
     'far_absorption_share_64/1024', 'the bedrock replenishment/absorption rows (native_replay_driver) are not produced'),
    ('resilience_and_recovery', 'dipole', 'consumed_partial', 'the teacher\'s far_identity_survival_64/1024, '
     'far_size_retention_64/1024', 'the bedrock recovery rows are not produced'),
    ('churn_and_queue_turnover', None, 'produced_not_carried', None, 'the frame\'s add_cancel_churn and '
     'priority_lost_modify_count per window are produced, not spooled'),
    ('price_and_book_path', 'prices', 'consumed', 'prices.*, frames.* on the axis', None),
    ('missingness_and_integrity_flags', 'dipole', 'consumed_partial', 'the Dipole rows\' states are counted per column in '
     'the manifest (states_per_component); a value is used only where PRESENT',
     'the frame\'s integrity counters (missing_level_on_remove, duplicate_add_order_id, cancel_missing_order, '
     'modify_missing_treated_as_add, modify_side_change, add_invalid_side, sequence_regression, ...) are produced, not '
     'spooled; the ROOT failures spool is not read; the rows\' raw_reason categories are retained, not cells'),
    # categories the calculations find, beyond the registry names
    ('action-string families (CARRIED_NATIVE_ACTION_FAMILIES and every open-world candidate)', 'structures', 'consumed',
     'cells structures.action_string, structures.candidate_family_id, structures.carried_native_family, '
     'structures.discovery_status; series structures.matches_carried_native_family', None),
    ('mirror identity (canonical / mirror orientation, pair key)', 'structures', 'consumed',
     'cells structures.mirror.orientation, structures.mirror.mirror_pair_key, structures.mirror.mirror_side_string', None),
    ("the D chain's reasons (CHAIN_BROKEN, NO_COMPLETED_STEP, DEGENERATE_STEP) and every column's state", 'dipole',
     'computed_not_retained', 'counted in the manifest only', 'retained per row as state/raw_reason; not used as cells '
     '(the exact change is named in the Step #3 map)'),
    ("the teacher's 19 Dipole columns", 'dipole', 'consumed', 'dipole.<column> for every column whose state is PRESENT', None),
    ('odcore.info_dipole divergence / exhaustion (signed_flow_features, divergence, cell_signal)', None, 'built_not_called',
     None, 'referenced only as the construction of historical claims H01/H02 (frankie_box_historical_claims.py); '
     'computing it on the day\'s signed flow is a new derived series (a mathematical decision)'),
    ("Frankie's 13 historical points (27 aliases)", 'external', 'consumed', 'external.<alias>.value', None),
    ('day-file tables, every column per entity', 'external', 'consumed',
     'external.<table>.<column>.entity=<id> (numeric), cells for text columns (SEARCH_EXTERNAL_FIELDS=all)', None),
    ('sealed journal INPUT entries (every record, every field)', 'events', 'consumed',
     'events.* per-group counts and events.last.<field>; identities and clocks listed (EVENT_IDENTITY_FIELDS)', None),
    ('sealed journal APPLIED entries (the V4 frame and the full-book observation)', None, 'produced_not_carried', None,
     'read whole by the BOSS teacher (JournalTeacherR3); frankie_box_experiment_surface.journal_axis reads them on the '
     'native ordinal and is not called (a change of axis); the frame\'s per-level and activity fields are the '
     'produced_not_carried rows above'),
)


def plane_summary(sources, notes):
    """Per registry layer and found category (PLANE_COVERAGE): its status on this run, the series/cells it reaches this
    search through, and what remains. Read from this search's own sources and notes: a plane whose source this run did
    not read is reported listed_missing or not_in_this_export, never consumed."""
    read = {s['source'] for s in sources}
    missing = {n['source'] for n in notes if 'missing' in n}
    out = {}
    for name, source, status, consumed_by, remaining in PLANE_COVERAGE:
        if source is not None and status in ('consumed', 'consumed_partial', 'clock') and source not in read:
            status = 'listed_missing' if source in missing else 'not_in_this_export'
        out[name] = dict(status=status, source=source, consumed_by=consumed_by, remaining=remaining)
    return out


def _cell_job(args):
    """One cell/x job; retain its exact next partner and all completed candidate rows on save."""
    part, cell_col, cell_value, tx, x, lags, survivors, header = args
    identity = dict(search=_JOB['identity'], job=args)
    state_path, partial = Path(part + '.state.pkl'), Path(part + '.tmp')
    saved = _load_state(state_path, identity) if state_path.is_file() else None
    if saved and saved.get('complete'):
        if saved['sha256'] is not None and (not Path(part).is_file() or sha256_file(part) != saved['sha256']):
            raise ValueError('completed search part changed: %s' % part)
        return saved['result']
    if saved and saved.get('ready_to_publish'):
        source = partial if partial.is_file() else Path(part)
        if not source.is_file() or source.stat().st_size != saved['bytes'] or sha256_file(source) != saved['sha256']:
            raise ValueError('search part differs from its retained result: %s' % source)
        if source == partial:
            os.replace(partial, part)
        result = (part, saved['count'], saved['beyond'], None)
        _save_state(state_path, dict(identity=identity, complete=True, result=result, sha256=saved['sha256']))
        return result
    steps, idx = _JOB['steps'], _JOB['cells'][(cell_col, cell_value)]
    pick = (lambda v: v) if idx is None else (lambda v: v[idx])
    if saved:
        sx, fx = saved['sx'], saved['fx']
        count, beyond, cursor = saved['count'], saved['beyond'], saved['cursor']
        if not partial.is_file() or partial.stat().st_size != saved['bytes'] or sha256_file(partial) != saved['sha256']:
            raise ValueError('unfinished search part differs from saved cursor: %s' % partial)
    else:
        if Path(part).exists() or partial.exists():
            raise ValueError('search part has no matching continuation; retained for recovery: %s' % part)
        sx = pick(steps[tx][x])
        if sx.size < 2:
            result = (part, 0, 0, dict(cell=[cell_col, str(cell_value)], transform=tx, series=x, steps=int(sx.size),
                                     reason='fewer than 2 steps of this series in this cell: no step pair to count'))
            _save_state(state_path, dict(identity=identity, complete=True, result=result, sha256=None))
            return result
        fx = transforms(sx)
        count = beyond = cursor = 0
    partners = [(ty, y) for ty in y_transforms(tx) if ty in steps for y in sorted(steps[ty])
                if y != x and (survivors is None or (tx, x, ty, y, cell_col, cell_value) in survivors)]
    with partial.open('a' if saved else 'x') as out:
        for partner_index in range(cursor, len(partners)):
            if _stop_requested():
                out.flush()
                os.fsync(out.fileno())
                _save_state(state_path, dict(identity=identity, complete=False, sx=sx, fx=fx,
                                            count=count, beyond=beyond, cursor=partner_index,
                                            bytes=partial.stat().st_size, sha256=sha256_file(partial)))
                return None
            ty, y = partners[partner_index]
            row = dict(header, x=x, y=y, cell=cell_col, cell_value=cell_value, transform=tx, x_transform=tx,
                       y_transform=ty, **couple(fx, transforms(pick(steps[ty][y])), lags))
            out.write(json.dumps(row, sort_keys=True) + '\n')
            count += 1
            beyond += row['beyond_chance']
        out.flush()
        os.fsync(out.fileno())
    # Save the completed result before publication. A stop never requires redoing these pair calculations.
    result = (part, count, beyond, None)
    digest = sha256_file(partial)
    _save_state(state_path, dict(identity=identity, complete=False,
                                count=count, beyond=beyond, cursor=len(partners),
                                bytes=partial.stat().st_size, sha256=digest, ready_to_publish=True))
    os.replace(partial, part)
    _save_state(state_path, dict(identity=identity, complete=True, result=result, sha256=digest))
    return result


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
    staging = target.parent / (target.name + '.partial')
    recovery = staging / 'recovery'
    recovery.mkdir(parents=True, exist_ok=True)
    (staging / 'couplings').mkdir(parents=True, exist_ok=True)
    identity = dict(schema='FRANKIE_SEARCH_CONTINUATION_V1', day=day, cycle=cycle, role=day_role,
                    data_manifest_sha256=sha256_file(day_dir / 'MANIFEST.json'), lags=lags,
                    transforms=transform_names, frozen_sha256=sha256_file(frozen) if frozen else None,
                    code_sha256=sha256_file(__file__), transform_sha256=sha256_file(T.__file__),
                    directive=directive_witness())
    identity_path = recovery / 'identity.pkl'
    if identity_path.is_file():
        _load_state(identity_path, identity)
    else:
        _save_state(identity_path, dict(identity=identity))
    # A publication interrupted after its final manifest resumes without reopening any scientific operation.
    if (staging / 'MANIFEST.json').is_file():
        manifest = json.loads((staging / 'MANIFEST.json').read_bytes())
        os.replace(staging, target)
        return manifest
    prepared_path = recovery / 'prepared.pkl'
    if prepared_path.is_file():
        prepared = _load_state(prepared_path, identity)['prepared']
    else:
        if _stop_requested():
            raise SystemExit(75)
        # This existing source preparation is one operation. A requested stop lets it finish and retains every array.
        prepared = build_series(day_dir, log)
        _save_state(prepared_path, dict(identity=identity, prepared=prepared))
    axis, series, cells, sources, notes, gates = prepared
    if _stop_requested():
        raise SystemExit(75)
    names = sorted(series)
    import multiprocessing
    context = multiprocessing.get_context('fork')                # the workers share the arrays, no copy
    _JOB.clear()
    _JOB.update(series=series, identity=identity, recovery=recovery)
    steps, unclassified = {t: {} for t in transform_names}, {t: {} for t in transform_names}
    step_jobs = [(n, t) for t in transform_names for n in names]
    for _, result in _run_pending(context, workers, _step_job, step_jobs):
        tname, name, st, n_unknown = result
        steps[tname][name] = st
        unclassified[tname][name] = n_unknown
    if _stop_requested():
        raise SystemExit(75)       # all submitted transforms have drained and saved their full results
    cells_path = recovery / 'cells.pkl'
    if cells_path.is_file():
        cell_index = _load_state(cells_path, identity)['cells']
    else:
        cell_index = {('whole-day', None): None}
        for col, values in sorted(cells.items()):
            arrived = np.asarray(values[1:], dtype=object)          # a step belongs to the cell of the group it arrives at
            for value in sorted({v for v in arrived if v is not None}):
                cell_index[(col, value)] = np.nonzero(arrived == value)[0]
        _save_state(cells_path, dict(identity=identity, cells=cell_index))
    header = dict(day=day, cycle=cycle, day_role=day_role)
    jobs = [(str(staging / 'couplings' / ('%04d-%s-%s.jsonl' % (c, tx, hashlib.sha256(x.encode()).hexdigest()[:16]))),
             col, value, tx, x, lags, survivors, header)
            for c, (col, value) in enumerate(sorted(cell_index, key=lambda k: (k[0] != 'whole-day', k[0], str(k[1]))))
            for tx in transform_names for x in names]
    jobs_path = recovery / 'jobs.pkl'
    if jobs_path.is_file():
        if _load_state(jobs_path, identity)['jobs'] != jobs:
            raise ValueError('saved search job order changed')
    else:
        _save_state(jobs_path, dict(identity=identity, jobs=jobs))
    _JOB.update(steps=steps, cells=cell_index)
    started = time.time()
    parts, count, beyond, not_counted = [], 0, 0, []
    for _, result in _run_pending(context, workers, _cell_job, jobs):
        if result is None:
            continue                # this worker saved its exact next pair on the cooperative stop
        part, n_rows, n_beyond, short = result
        if short:
            not_counted.append(short)
        parts.append(part)
        count += n_rows
        beyond += n_beyond
    if _stop_requested():
        raise SystemExit(75)         # every submitted pair worker has saved; no child is left running
    if len(parts) != len(jobs):
        raise ValueError('search workers stopped before every job was retained; resume with the stop request cleared')
    part_pins = [dict(path=str(Path(p).relative_to(staging)), rows=None, sha256=sha256_file(p)) for p in sorted(parts)
                 if Path(p).exists()]
    cell_specs = [(c, v, None) for c, v in cell_index]
    manifest = dict(schema=SCHEMA, day=day, cycle=cycle, day_role=day_role, at=time.time(), seconds=time.time() - started,
                    data=str(day_dir), data_manifest_sha256=sha256_file(day_dir / 'MANIFEST.json'),
                    experiment_directive=directive_witness(),
                    sources=sources, notes=notes, leakage=gates, lags=lags,
                    series=names, cells=[(c, v) for c, v, _ in cell_specs],
                    transforms=dict(names=transform_names, pairs={t: list(y_transforms(t)) for t in transform_names},
                                    module_sha256=sha256_file(Path(T.__file__)),
                                    unclassified_steps=unclassified),
                    couplings=dict(parts=part_pins, rows=count, beyond_chance=beyond, jobs=len(jobs), workers=workers),
                    cells_not_counted=sorted(not_counted, key=lambda d: (d['cell'], d['transform'], d['series'])),
                    not_searched=[dict(item=a, what=b) for a, b in NOT_SEARCHED],
                    planes=plane_summary(sources, notes),
                    rule='counts per pair, cell, lag and day; never pooled across days; never a coefficient or an average '
                         'as the finding (D37); a confirmation day runs only the frozen survivor list',
                    frozen_survivors=str(frozen) if frozen else None, model_calls=0)
    manifest_path = staging / 'MANIFEST.json'
    with manifest_path.with_suffix('.json.pending').open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(manifest_path.with_suffix('.json.pending'), manifest_path)
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
