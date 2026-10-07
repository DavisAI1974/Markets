"""The experiment's search, first slice: series on one causal axis per day, and sign-step couplings with a chance check.

Greg, 2026-09-29 ("build the bedrock off switch and start the search"; reversed 2026-10-07: the native pass is ON for
every new run). Spec: research/kalshi/frankie_boss/
SPEC-experiment-orchestrator.md (steps 5-6) and SPEC-scientific-teacher.md (the search IS the scientific teacher).
Reads ONE day's exported data (frankie_box_experiment_data.py: /opt/frankie-box/work/experiment-data/<day>/cycle-<NN>/)
in place. Nothing is re-derived and no copy is written: the ROOT's row spools are streamed through the journal's own
codec (c15_journal.unpack) into columns held in memory, and one as-of selection (asof_source_rows) aligns them.

SERIES (step 5). The axis is the F_LAST group closes (the ROOT's book-frame spool, in its order). Each source is placed
on the axis AS OF the moment it was knowable, never later information:
  frames      (root/work/derived/.rows/frames.jsonl)      each numeric book field, at its own group close;
  structures  (root/work/derived/.rows/structures.jsonl)  each numeric structure field, at its group close;
  trades      (root/work/derived/.rows/prices.jsonl)      last trade price and size known at the group close;
  per-second  (legacy_native_signed_flow, legacy_per_second_roll20)  buy, sell and roll20 of second s, known at the
              start of second s+1.
  external    (ingest/day-external.json, FRANKIE_DAY_EXTERNAL_V1)  Frankie's 13 historical points (COT, MOS per cycle,
              EIA-930 hourly, observed weather, storage, the futures curve per settlement and per
              trade), each known from its own publication stamp, read through the file's as-of reader at the halt.
              Calendar counts, dates/weekdays and entity IDs are categorical search conditions, not x/y signals.
Receive clocks can run backwards, so the axis time is the running maximum of the frames' ts_recv_ns (order is the
spool's order, which is the ROOT's ordinal order). Alignment is an as-of selection (value known_at <= axis time).
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
Cells: whole-day, market text categories and ID/calendar context placed on the axis; each distinct value is a cell.
Bookkeeping/availability/encoding metadata and execution costs/profit are excluded from series and cells, with exact
channel dispositions. Dates/weekdays/IDs group actual market signals for forecasting; the underlying market conditions
supply the prediction, not the grouping labels. The original source dates and timestamps remain associated with every
record; availability clocks and missingness masks still govern placement. Context is not an independent observation.
Step #3 (2026-10-06): the per-event quantity fields of the INPUT spool (events.last.<field>, the last event's value at
the group close) and every column of every day-file table per native entity (external.<table>.<column>.entity=...) are
series too; identities and clocks are listed. Equal values never make different entity columns aliases.
V2 ROOT frames additionally carry full-depth/FIFO snapshots and every original group INPUT record, including bytes.
Each input-record position is searched at its group close; this does not change lags to native-event units.
Event counts, known-size sums and closing-record fields use ROOT's exact input_record_indices/input_cursor,
not timestamp lookup or a global bucket across instruments. Unsupported old group membership is explicitly listed.
Dipole current components use exact journal source-cursor availability at each frame, including tied timestamps.
Every original target row additionally supplies dipole.group.rows[position].* numeric/categorical channels at its
exact owning INPUT group. Ordered slots preserve intermediate states; they are not independent observations.
Structures additionally supply structures.group.* by exact original closing INPUT, instrument and full ROOT
membership, bound to the selected derive receipt. Legacy structures.* timestamp aliases remain unchanged.
Price V2 provenance binds every declared trade-row slot to its originating INPUT and emitting group close;
unsupported V1/opening-state origins remain explicitly unplaced. Both spools' provenance.* fields are metadata,
excluded from series and cells.
Raw component numeric values in both positional and entity closing-row channels require the producer's PRESENT
state. Other states project to None with exact source-cursor/reason accounting; original snapshot evidence and
independent metadata remain intact, including incomplete annotations on PRESENT values.
The sealed ingest's complete INPUT/APPLIED envelopes additionally supply journal.group.entries[position].* at
their exact existing ROOT group membership. Intermediate effects/order/rank fields are retained; missing full
snapshots stay missing. Unknown/failed/unclosed/unmatched entries have explicit retained ordinal dispositions.

LISTED, NOT SEARCHED (never dropped), each named in the MANIFEST's not_searched list with its reason: identity/clock
fields, numeric-state conditions, new targets, the bedrock planes a ROOT did not derive (its native pass did not complete, or an older saved legacy plan ran it off),
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
Generic source reads must match the selected export's byte-count/SHA256 pins, including frames when no INPUT or
journal route is available. Spools are hashed as decoded; JSON and the optional external receipt use their checked
bytes. Prepared arrays are saved only after those checks finish and remain bound to the manifest and this source.
CPUs and dead workers (Greg, 2026-10-07 night): every pool is frankie_box_lane_pin.ordered_map, each worker pinned to its
own lane CPU (physical cores first; the coordinator pinned to its own CPU after the source preparation; no DuckDB
connection is opened, none was ever queried). A worker that dies never hangs or stops the search: its lost job is redone
(a coupling part it was writing is set aside first), the in-flight window shrinks by one, a discovery problem whose
worker dies on every try is listed `worker_died`; all of it in MANIFEST cpu_placement.pool_recovery. Values, order and
pins are unchanged.
Every remaining serial walk of the search runs the Sept 29 pattern (Greg, 2026-10-07 night; values, order and pins
unchanged, each checked against the serial result on synthetic data): columns() accumulates per channel (the leaves a
row carries, not rows x every channel seen); the frame/structure/price spools and the INPUT spool are decoded by pinned
workers in ordered line ranges with every per-record check on the coordinator in spool order; each source's leakage
gates run side by side on pinned workers; one alignment serves a source's numeric and text fields; the coupling
parts are read for discovery nominations by pinned workers and merged in part order; the parts are pinned by pinned
hashing threads. Where each pass ran: MANIFEST cpu_placement.source_passes (spool parses: each source's `parse`).
The one-day review reads workflow-report.json beside the MANIFEST (the piece's own record with every list longer than
WORKFLOW_REPORT_LIST_BYTES named by its count and exact MANIFEST location; the MANIFEST itself outgrows the reporter's
metadata ceiling on a full day).
"""
import argparse
from datetime import date
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

SCHEMA = 'FRANKIE_EXPERIMENT_SEARCH_V1'
ROOT = Path('/opt/frankie-box/work/experiment-search')
CELL_NAMES = ('session_phase', 'continuity_segment', 'source_day', 'source_role')
F_LAST = 128                       # the exchange record flag that closes a group (the same close the frames spool marks)
ROW_PROVENANCE_SCHEMA = 'FRANKIE_ROOT_ROW_PROVENANCE_V1'
PRICE_ROW_PROVENANCE_SCHEMA = 'FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2'
# Identity/metadata and absolute clocks are listed; latency provenance is not a market quantity.
# Identity relationships continue to support their existing lawful consumers.
EVENT_IDENTITY_FIELDS = ('order_id', 'sequence', 'channel_id', 'instrument_id', 'publisher_id', 'ts_recv_ns', 'ts_event_ns',
                         'ts_recv', 'ts_event', 'rtype', 'hd')
# Greg, 2026-10-06: market conditions only. Identity/clock/availability metadata still binds and places evidence;
# it is not a market quantity. IDs/dates can group market signals as search conditions. These are explicit source
# roles, not substring guesses about price, spread, flow, age, duration, market counts or net market positioning.
NON_MARKET_IDENTITIES = frozenset(EVENT_IDENTITY_FIELDS) | frozenset((
    'cursor', 'input_cursor', 'input_index', 'input_record_indices', 'input_ordinal', 'ordinal', 'group_ordinal',
    'group_index', 'source_member_index', 'legacy_row_ordinal', 'session_id', 'request_id', 'cycle_index', 'cycle_count',
    'order_ids', 'fill_order_ids', 'unresolved_order_ids', 'matched_order_ids', 'member_id', 'run_id',
    'source_day', 'source_role', 'schema', 'hash', 'sha256', 'digest', 'flags', 'is_last', 'is_snapshot',
    'byte_length', 'bytes_integer',
    'ts_in_delta_ns', 'ts_in_delta', 'independent_clocks',
))
NON_MARKET_CALENDAR = frozenset((
    'weekday', 'day_of_week', 'dayofweek', 'day_of_month', 'day_of_year', 'calendar_day', 'trading_day',
    'session_phase', 'continuity_segment', 'sessions_since_prompt_expiry', 'last_prompt_expiry',
    'date', 'day', 'year', 'month', 'week', 'day_name', 'is_weekend', 'holiday', 'is_holiday', 'expiry_date',
))
NON_MARKET_EXECUTION = frozenset((
    'fee', 'fees', 'fee_rt', 'fee_maker', 'fee_rt_bps', 'fee_per_quantity', 'maker_fee', 'taker_fee',
    'commission', 'commissions', 'slippage', 'max_slippage', 'transaction_cost', 'transaction_costs',
    'trading_cost', 'trading_costs', 'execution_cost', 'execution_costs', 'net_oos', 'net_oos_maker',
    'pnl', 'net_pnl', 'gross_pnl', 'realized_pnl', 'unrealized_pnl',
))
SEARCH_CONTEXT_IDENTITIES = frozenset((
    'order_id', 'order_ids', 'fill_order_ids', 'unresolved_order_ids', 'matched_order_ids',
    'instrument_id', 'publisher_id', 'channel_id', 'member_id', 'session_id', 'source_day', 'source_role',
    'raw_symbol', 'symbol', 'contract', 'trading_weekday',
))


def non_market_reason(name):
    """Known excluded role, 'context_only' grouping role, or None for a market channel; after joins/masks."""
    # External entity values may contain dots. The column's role precedes .entity=, not within its identity label.
    field_path = name.split('.entity=', 1)[0] if name.startswith('external.') else name
    parts = re.sub(r'\[[^\]]*\]', '', field_path).split('.')
    fields = set(parts)
    if fields & NON_MARKET_EXECUTION:
        return 'execution costs/profit accounting are not market conditions'
    if fields & {'provenance', 'frankie_emission'}:
        return 'source/emission provenance binds evidence; it is not a market condition'
    if name.startswith('journal.group.') and (fields & {'receipt', 'boundary'}
            or re.fullmatch(r'journal\.group\.entries\[\d+\]\.payload\.(record_count|group_count)', name)):
        return 'journal receipts, source boundaries and adapter progress counters are bookkeeping'
    if (fields & (NON_MARKET_CALENDAR | SEARCH_CONTEXT_IDENTITIES) or name.startswith('external.calendar.')
            or any(p.endswith('_order_ids') for p in parts)):
        return 'context_only'  # dates/weekdays/IDs group signals; never transformed or used as numerical x/y
    if fields & NON_MARKET_IDENTITIES or any(p.endswith(('_hash', '_sha256')) for p in parts):
        return 'record identity, source bookkeeping or encoded bytes are not market quantities'
    if any(p in ('as_of', 'known_at', 'published_ns', 'event_time', 'ingest_time', 'as_of_ts_recv_ns', 'emitted_at_recv_ns',
                 'first_lawful_availability_ns') or p.startswith(('ts_recv', 'ts_event')) for p in parts):
        return 'absolute availability/event clocks place evidence; elapsed market durations remain quantities'
    if 'integrity' in fields or 'book_integrity' in fields:
        return 'source/book integrity diagnostics govern usability, not market conditions'
    if name.startswith('journal.group.') and parts[-1] == 'kind':
        return 'journal envelope type is source bookkeeping'
    if name.startswith('dipole.'):
        if parts[-1] in ('reason', 'raw_reason', 'unit', 'name', 'status'):
            return 'Dipole component descriptions and availability diagnostics are not market conditions'
        if parts[-1] == 'state' and 'dstate' not in fields:
            return 'Dipole PRESENT/MISSING state is an availability mask, not a market condition'
        if 'dstate' in fields and parts[-1] in ('g_E', 'g_E_prev'):
            return 'DState absolute group references support geometry; age/duration remain market quantities'
    return None


# Step #3 (2026-10-06, CCode): what is and is not searched, kept truthful per plane. The map behind it:
# research/kalshi/frankie_boss/CCODE_STEP3_SOURCE_COVERAGE_20261006.md.
NOT_SEARCHED = (
    ('root/work/derived/.rows/input-*.jsonl identities', 'in events.last only, identity and clock fields (%s) are listed rather than searched; '
     'events.last.<field> uses only the closing INPUT record of each matched F_LAST group. New V2 frames also carry '
     'every original record as frames.input_records[position].<field> at its own group close, including bytes; '
     'positions are within groups, not a native-event lag axis. Existing per-group counts/sizes are retained' % ', '.join(EVENT_IDENTITY_FIELDS)),
    ('conditions beyond the text cells', 'conditioning on a numeric state (e.g. the sign of a book series at the decision row): '
     'frankie_box_experiment_surface.state_masks builds such masks but is not wired; which states condition the count is '
     'a design decision (every series x 3 signs would multiply the jobs by hundreds)'),
    ('targets', 'targets other than the series themselves (e.g. the mid N groups ahead, fills, exhaustion); a lagged series '
     'is already the y side at lag k, a fill count is already events.F_* per group; new target definitions are a '
     'mathematical decision'),
    ('full-depth identity/history interpretation and legacy exports',
     'V2 experiment frames carry every level/FIFO order through book.*_levels_full, every resting-order field through '
     'observation, and all original group INPUT records through input_records. Scalar leaves reach the existing search '
     'at the group close. List-position channels are not an order-identity lifecycle calculation; the same rank may '
     'hold another order next group. Old ROOT spools are not retrofilled; inspect sources[frames].frame_sections'),
    ("the D chain's own state",
     'new experiment teacher rows retain all DState fields at the existing group update under '
     'dipole.group.rows[position].dstate.*, including exact rational numerator/denominator leaves. '
     'The source report states actual retained/searched coverage; older teacher sources are not backfilled. '
     'This is the same teacher evidence, not another observation or native model supervision'),
    ('non-market fields', 'bookkeeping/hash/clock/availability/encoding and execution-cost/profit fields are removed '
     'from series AND cells after lawful binding/placement/mask use. Dates/weekdays/entity IDs remain categorical '
     'search conditions grouping market signals, never numerical x/y signals themselves. Each excluded or moved '
     'channel is listed in notes; original evidence is unchanged. Market price/spread, FIFO rank/age, '
     'flow/depth, derived geometry and market positioning remain quantities; action/side and structure labels remain '
     'market categories. Context can condition the search without becoming a measured market quantity'),
    ('price/structure row provenance', 'provenance.* is retained identity metadata, not a numerical series or cell. '
     'structures.group.* requires the selected derive receipt schema and exact ROOT closing INPUT, instrument and '
     'full member list. prices.group.rows[slot].* requires price V2 originating INPUT plus the emitting group close, '
     'instrument and declared group-row slot; V1 never supplies exact trade identity. Every unsupported original spool '
     'ordinal has a disposition. Exact projections and legacy aliases are duplicate evidence, not independent observations'),
    ('native evidence boundaries', 'selected completed native member/lifecycle ledgers with exact emission provenance '
     'enter the existing F_LAST axis, every leaf and ordered per-section emission slot. Native producers remain opt-in; '
     'old provenance-free rows, unmatched ROOT frames and FINALIZE rows have explicit retained dispositions. '
     'Whole-day summaries and duplicate projected aliases are not earlier live features. Positional emission slots '
     'preserve all entity IDs but do not establish identity-linked trajectories or full teacher consumption'),
    ('ROOT failures spool', 'root/work/derived/.rows/failures.jsonl (records the legacy pass could not apply) is not a '
     'series; it is listed in the ROOT receipt, not searched'),
    ('native journal ordinal axis', 'frankie_box_experiment_surface.journal_axis reads every INPUT/APPLIED entry of the sealed '
     'journal (full book, FIFO order ids, APPLIED frame fields) on the native ordinal; it is not wired: it materializes '
     'every entry whole (the full-book observation per APPLIED entry) and changes the axis from group closes to entries, '
     'which is a mathematical decision on step counts, lags and the chance check'),
    ('journal envelope boundaries', 'journal.group carries complete normal INPUT/APPLIED envelopes on existing exact '
     'ROOT group membership. Failed, unknown, unpaired and unclosed or mismatched groups remain in the sealed ingest '
     'with explicit ordinal dispositions. Intermediate observation=None is not a reconstructed full-book snapshot; '
     'positional slots and duplicate source representations are not independent observations'),
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

def unpack_spool(path, pin):
    """Decode every row; exhaustion must verify the consumed bytes against the selected export."""
    from research.kalshi.frankie_boss.c15_journal import unpack
    hashed, size = hashlib.sha256(), 0
    with open(path, 'rb') as handle:
        for line in handle:
            hashed.update(line)
            size += len(line)
            yield unpack(json.loads(line.decode('utf-8')))
    if size != pin['bytes'] or hashed.hexdigest() != pin['sha256']:
        raise ValueError('search spool differs from the selected export: ' + str(path))


def _flatten(value, prefix, out):
    """Append every (leaf name, scalar) of `value` to `out`, depth first in mapping/list order (the leaves columns()
    has always produced, built by appending instead of nested generators)."""
    if isinstance(value, dict) and value:
        for k, v in value.items():
            _flatten(v, prefix + ('.' if prefix else '') + str(k), out)
    elif isinstance(value, (list, tuple)) and value:
        for i, v in enumerate(value):
            _flatten(v, '%s[%d]' % (prefix, i), out)
    elif isinstance(value, (bytes, bytearray)):
        if prefix.rsplit('.', 1)[-1] in ('action', 'side'):
            out.append((prefix, bytes(value).decode('ascii')))  # market category, not its arbitrary byte encoding
        else:
            out.append((prefix + '.byte_length', len(value)))
            out.append((prefix + '.bytes_integer', int.from_bytes(value, 'big')))
    elif isinstance(value, (dict, list, tuple)):
        out.append((prefix, json.dumps(value, sort_keys=True)))
    elif value is None or isinstance(value, (bool, int, float, str)):
        out.append((prefix, value))
    else:
        raise TypeError('unhandled retained field %s: %s' % (prefix, type(value).__name__))


def columns(rows, time_key):
    """Every scalar leaf of a spool, including all list positions; integers remain exact Python integers.

    Result per channel: one entry per row, the row's value where the row carries the channel in its kind (numeric:
    int/float/bool or None; text: str), None otherwise; channels in first-appearance order. Accumulated per channel
    as it appears (rows and values), so the work is the leaves the rows carry rather than rows x every channel seen
    so far (the positional full-depth/FIFO and envelope slots made that product the search's largest serial cost);
    a channel present in every row from its first appearance stays one plain list. Same lists, values and order."""
    numeric_at, text_at, count = {}, {}, 0          # key -> [first row, values, rows or None while contiguous]
    for row in rows:
        leaves = []
        _flatten(row, '', leaves)
        row = dict(leaves)
        if len(row) != len(leaves):
            raise ValueError('retained nested field names collide; no field may be silently overwritten')
        for key, value in row.items():
            if isinstance(value, (int, float)) or value is None:
                slots = numeric_at
            elif isinstance(value, str):
                slots = text_at
            else:
                raise TypeError('unhandled field %s' % key)
            slot = slots.get(key)
            if slot is None:
                slots[key] = [count, [value], None]
                continue
            values, at = slot[1], slot[2]
            if at is None:
                if slot[0] + len(values) != count:  # a gap: from here on the rows are listed
                    slot[2] = at = list(range(slot[0], slot[0] + len(values)))
                    at.append(count)
                values.append(value)
            else:
                at.append(count)
                values.append(value)
        count += 1

    def materialize(slots):
        out = {}
        for key, (first, values, at) in slots.items():
            if at is None:
                tail = count - first - len(values)
                out[key] = values if not first and not tail else [None] * first + values + [None] * tail
            else:
                column = [None] * count
                for position, value in zip(at, values):
                    column[position] = value
                out[key] = column
        return out
    numeric, text = materialize(numeric_at), materialize(text_at)
    other = {key + ' (mixed kinds: numeric and text channels both retained)' for key in set(text) & set(numeric)}
    return numeric, text, sorted(other), count


# ---- the spool parse on the held lane (Greg, 2026-10-07: every piece uses the lane's CPUs) --------------------------
# columns(unpack_spool(...)) decodes and flattens one row at a time on one CPU; the frame spool carries full-depth books,
# observations and the group's INPUT records per F_LAST close, so it is the largest decode of the search. The rows are
# independent: the file is cut at line boundaries into ordered byte ranges, each range is decoded and flattened by the
# unchanged columns() in a forked worker, and the parts are joined in file order with exactly columns()'s rules (a key's
# list starts with None for every earlier row; a row without the key appends None; first-appearance key order). The
# bytes are hashed in file order beside the workers and checked against the pin after every row decoded, as
# unpack_spool does. Same channels, same values, same order, same errors; below SPOOL_PARALLEL_MIN_BYTES or with one
# worker it is the serial call itself.
SPOOL_PARALLEL_MIN_BYTES = 64 << 20
SPOOL_RANGES_PER_WORKER = 4          # several ranges per worker: a dense range does not trail a drained pool


def _spool_range_columns(args):
    path, start, end = args
    from research.kalshi.frankie_boss.c15_journal import unpack
    def rows():
        position = start
        with open(path, 'rb') as handle:
            handle.seek(start)
            for line in handle:
                if position >= end:
                    break
                position += len(line)
                yield unpack(json.loads(line.decode('utf-8')))
    numeric, text, _, count = columns(rows(), None)
    return numeric, text, count


def _spool_ranges(path, size, pieces):
    """Ordered [start, end) byte ranges of the file, each starting at a line start."""
    cuts = [0]
    with open(path, 'rb') as handle:
        for k in range(1, pieces):
            nominal = size * k // pieces
            if nominal <= cuts[-1]:
                continue
            handle.seek(nominal - 1)
            handle.readline()                      # ends just after the newline at or after byte nominal - 1
            cut = handle.tell()
            if cuts[-1] < cut < size:
                cuts.append(cut)
    cuts.append(size)
    return [(path, a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


class FrontierHasher:
    """sha256 of one file in file order on a daemon thread, at most `lead` bytes past the decode frontier (stacks pass,
    2026-10-07 night: every spool read ONCE). The decode workers read the in-flight ranges just past the frontier; the
    hasher reads the same pages within that window, so one of the two reads comes from the disk and the other from the
    page cache instead of the hasher racing the whole file ahead (a second disk pass on a spool larger than the cache,
    e.g. the ~430 GB frames spool of 20231018). The digest is of every byte in file order, exactly hashlib.sha256 of
    the file: placement of the reads changes nothing hashed. Stops are bounded: stop() wakes the thread, which returns
    within one block read, and is joined with a timeout (a still-running hasher is reported, never waited on forever;
    the shard exit hang of a2 came from an unbounded join). The digest is compared only after the last range."""
    BLOCK = 16 << 20

    def __init__(self, path, lead, name='spool-sha256'):
        import threading
        self.path, self.lead = str(path), max(self.BLOCK, int(lead))
        self.sha256, self.bytes, self.error, self.frontier = hashlib.sha256(), 0, None, 0
        self.stopped, self.throttle_waits, self.started_at, self.seconds = False, 0, None, None
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._run, name=name, daemon=True)

    def _run(self):
        self.started_at = time.time()
        try:
            with open(self.path, 'rb', buffering=0) as handle:
                while True:
                    with self.condition:
                        while not self.stopped and self.bytes >= self.frontier + self.lead:
                            self.throttle_waits += 1
                            self.condition.wait(1.0)
                        if self.stopped:
                            return
                    block = handle.read(self.BLOCK)
                    if not block:
                        return
                    self.sha256.update(block)
                    self.bytes += len(block)
        except BaseException as error:  # noqa: BLE001 - re-raised by finish()
            self.error = error
        finally:
            self.seconds = round(time.time() - self.started_at, 3)

    def start(self, *_):
        self.thread.start()

    def advance(self, offset):
        """The decode frontier moved to byte `offset` (the end of the last range consumed in file order)."""
        with self.condition:
            if offset > self.frontier:
                self.frontier = offset
                self.condition.notify_all()

    def stop(self, timeout=60.0):
        """Abort (an error or an early close upstream): bounded; True when the thread has ended."""
        with self.condition:
            self.stopped = True
            self.condition.notify_all()
        if self.thread.ident is not None:
            self.thread.join(timeout)
        return not self.thread.is_alive()

    def finish(self):
        """Let the hasher read to the end, then (bytes, hexdigest); its own read error is raised here."""
        self.advance(float('inf'))
        if self.thread.ident is not None:
            self.thread.join()
        if self.error is not None:
            raise self.error
        return self.bytes, self.sha256.hexdigest()

    def report(self):
        return dict(mode='frontier-throttled thread (the decode and the hash share one disk read via the page cache)',
                    lead_bytes=self.lead, throttle_waits=self.throttle_waits, seconds=self.seconds,
                    stopped_early=self.stopped)


# The column spools are cut into ranges of about SPOOL_COLUMN_RANGE_BYTES (at least SPOOL_RANGES_PER_WORKER per
# worker) with at most two ranges per worker in flight, so the decode reads a bounded window just past the frontier
# and the hasher reads the same pages (FrontierHasher). The cut count never changes the joined columns (parts are
# joined in file order with columns()'s rules; proven by the toy self-test in the stacks-pass record).
SPOOL_COLUMN_RANGE_BYTES = 256 << 20
SPOOL_WINDOW_PER_WORKER = 2


def spool_columns(path, pin, time_key, workers=1, report=None):
    """columns(unpack_spool(path, pin), time_key) with the decode on the lane's workers (see above)."""
    started = time.time()
    size = Path(path).stat().st_size
    if workers <= 1 or size < SPOOL_PARALLEL_MIN_BYTES:
        result = columns(unpack_spool(path, pin), time_key)
        if report is not None:
            report.update(mode='serial', workers=1, ranges=1, bytes=size, seconds=round(time.time() - started, 3),
                          reason=('one worker' if workers <= 1 else
                                  'spool below SPOOL_PARALLEL_MIN_BYTES (%d): the serial call itself' % SPOOL_PARALLEL_MIN_BYTES))
        return result
    import multiprocessing
    ranges = _spool_ranges(str(path), size, max(workers * SPOOL_RANGES_PER_WORKER, size // SPOOL_COLUMN_RANGE_BYTES + 1))
    count = min(workers, len(ranges))
    window = count * SPOOL_WINDOW_PER_WORKER
    hasher = FrontierHasher(path, window * max(b - a for _, a, b in ranges), name='spool-sha256')
    numeric, text, rows, done, finished = {}, {}, 0, 0, False
    try:
        # in file order; pinned; hasher started after the workers are forked (no thread is copied into them); a dead
        # worker's range is decoded again, never a hang (frankie_box_lane_pin.ordered_map)
        for job, (part_numeric, part_text, part_count) in _lane_pin().ordered_map(
                _spool_range_columns, ranges, count, context=multiprocessing.get_context('fork'),
                cpus=lane_cpus(), window=window, on_start=hasher.start, report=POOL_RECOVERY):
            for merged, part in ((numeric, part_numeric), (text, part_text)):
                for key, values in part.items():
                    if key in merged:
                        merged[key].extend(values)
                    else:                      # first seen in this range: None for every earlier row, as columns()
                        merged[key] = [None] * rows
                        merged[key].extend(values)
                for key, values in merged.items():
                    if key not in part:
                        values.extend([None] * part_count)
            rows += part_count
            done += 1
            hasher.advance(job[2])
            _progress('search: decode %s' % Path(path).name, done, len(ranges), 'byte ranges', bytes_done=job[2],
                      bytes_total=size, rows=rows)
        finished = True
    finally:
        if not finished:
            ended = hasher.stop()
            if report is not None:
                report.update(aborted=True, hasher_ended=ended)
    hashed_bytes, digest = hasher.finish()
    if hashed_bytes != pin['bytes'] or digest != pin['sha256']:
        raise ValueError('search spool differs from the selected export: ' + str(path))
    other = sorted(key + ' (mixed kinds: numeric and text channels both retained)' for key in set(text) & set(numeric))
    if report is not None:
        report.update(mode='fork_pool_line_ranges', workers=count, ranges=len(ranges), window=window, bytes=size,
                      seconds=round(time.time() - started, 3), hashing=hasher.report(),
                      basis='ordered byte ranges cut at line starts; parts joined in file order with columns() rules; '
                            'bytes hashed in file order and checked against the pin')
    return numeric, text, other, rows


# ---- the INPUT spool read on the held lane (the Sept 29 pattern, item 3: batch decode, every per-record check kept) ---
# unpack_spool decodes one record at a time (json + c15_journal.unpack) on the coordinator, and the INPUT spool carries
# every source record of the day. Its records are independent until the consumer's per-record checks, so above
# SPOOL_PARALLEL_MIN_BYTES the file is cut at line starts into ordered ranges of about SPOOL_RANGE_BYTES; pinned forked
# workers decode the ranges (the same json.loads + unpack of the same bytes) and the coordinator receives the records
# range by range IN FILE ORDER and runs every check of its loop unchanged and in order. A line that does not decode
# ends its range's records there; the records before it are consumed first, then the same error is raised (the serial
# point of failure). The bytes are hashed in file order beside the workers and checked against the pin after the last
# record, as unpack_spool does. At most two ranges per worker are in flight (bounded memory). A dead worker's range is
# decoded again (frankie_box_lane_pin.ordered_map). One worker or a small spool: unpack_spool itself.
SPOOL_RANGE_BYTES = 16 << 20


def _spool_range_rows(args):
    """(the range's records decoded in order, the first decode error or None)."""
    path, start, end = args
    from research.kalshi.frankie_boss.c15_journal import unpack
    out, position = [], start
    with open(path, 'rb') as handle:
        handle.seek(start)
        for line in handle:
            if position >= end:
                break
            position += len(line)
            try:
                out.append(unpack(json.loads(line.decode('utf-8'))))
            except Exception as error:  # noqa: BLE001 - re-raised by the coordinator after the records before it
                return out, error
    return out, None


def decoded_spool(path, pin, workers=1, report=None):
    """unpack_spool(path, pin) with the decode on the lane's workers (see above): the same records in the same order,
    the same pin check after the last one."""
    started = time.time()
    size = Path(path).stat().st_size
    if workers <= 1 or size < SPOOL_PARALLEL_MIN_BYTES:
        yield from unpack_spool(path, pin)
        if report is not None:
            report.update(mode='serial', workers=1, ranges=1, bytes=size, seconds=round(time.time() - started, 3))
        return
    import multiprocessing
    ranges = _spool_ranges(str(path), size, max(workers * SPOOL_RANGES_PER_WORKER, size // SPOOL_RANGE_BYTES + 1))
    count = min(workers, len(ranges))
    hasher = FrontierHasher(path, count * 2 * max(b - a for _, a, b in ranges), name='input-spool-sha256')
    decoded = _lane_pin().ordered_map(_spool_range_rows, ranges, count, context=multiprocessing.get_context('fork'),
                                      cpus=lane_cpus(), window=count * 2, on_start=hasher.start,
                                      report=POOL_RECOVERY)
    finished, done = False, 0
    try:
        for job, (records, error) in decoded:
            yield from records
            if error is not None:
                raise error
            done += 1
            hasher.advance(job[2])
            _progress('search: decode %s' % Path(path).name, done, len(ranges), 'byte ranges', bytes_done=job[2],
                      bytes_total=size)
        finished = True
    finally:
        decoded.close()                    # an early check failure in the consumer stops the workers now
        if not finished:
            ended = hasher.stop()          # bounded: never waits on the rest of the file after a failure
            if report is not None:
                report.update(aborted=True, hasher_ended=ended)
    hashed_bytes, digest = hasher.finish()
    if hashed_bytes != pin['bytes'] or digest != pin['sha256']:
        raise ValueError('search spool differs from the selected export: ' + str(path))
    if report is not None:
        report.update(mode='fork_pool_line_ranges', workers=count, ranges=len(ranges), bytes=size,
                      seconds=round(time.time() - started, 3), hashing=hasher.report(),
                      basis='ordered line ranges decoded by pinned workers; every per-record check on the coordinator '
                            'in spool order; bytes hashed in file order against the pin')


# ---- probes (FRANKIE_STAGE_PHASE_V1 via frankie_box_stage_progress.report_phase; the heartbeat adds units/min and the
# 600 s stall flag on the reader side). A probe never changes the stage; a probe write that fails is COUNTED here and
# the count lands on the MANIFEST (cpu_placement.probe_failures), so nothing is swallowed quietly.
PROBE_FAILURES = dict(count=0, last=None)


def _progress(phase, done=None, total=None, unit=None, every=10, **extra):
    try:
        try:
            import frankie_box_stage_progress as SP
        except ImportError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import frankie_box_stage_progress as SP
        SP.report_phase(phase, units_done=done, units_total=total, unit=unit, every=every, **extra)
    except Exception as error:  # noqa: BLE001 - counted, recorded on the manifest
        PROBE_FAILURES['count'] += 1
        PROBE_FAILURES['last'] = '%s: %s' % (type(error).__name__, str(error)[:200])


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def known_time_rows(known_at):
    """Exact integer-clock rows plus inclusive original-ordinal ranges that cannot be placed."""
    import numpy as np
    valid, unavailable = [], []
    for ordinal, stamp in enumerate(known_at):
        if isinstance(stamp, (int, np.integer)) and not isinstance(stamp, (bool, np.bool_)):
            valid.append(ordinal)
        elif unavailable and unavailable[-1][1] + 1 == ordinal:
            unavailable[-1][1] = ordinal
        else:
            unavailable.append([ordinal, ordinal])
    return valid, unavailable


def asof_source_rows(axis_t, known_at):
    """Original source ordinals chosen by the existing timestamp alignment; -1 means no available row."""
    import numpy as np
    valid, _ = known_time_rows(known_at)
    order = sorted(valid, key=lambda i: known_at[i])  # stable ties: the last published row
    times = np.asarray([known_at[i] for i in order], dtype=np.int64)
    positions = np.searchsorted(times, np.asarray(axis_t, dtype=np.int64), side='right') - 1
    for position in positions:
        yield order[position] if position >= 0 else -1


def asof_values(con, axis_t, known_at, values):
    """The ONE alignment used for every series and by its leakage gate: for each axis time, the value of the source row
    with the largest known_at <= that time (ties: the later row). Integer stamps remain exact;
    None where nothing is known yet, and native values are retained without a float conversion."""
    import numpy as np
    return np.asarray([values[i] if i >= 0 else None for i in asof_source_rows(axis_t, known_at)], dtype=object)


def root_row_columns(spool, numeric, text, count, frames, owners, axis_rows, producer_schema):
    """Place structures and V2 prices by exact INPUT membership and declared emission identity.

    V1 prices currently stamp the closing INPUT, not necessarily the INPUT that supplied the trade. Do not
    reinterpret that input_index contract. Provenance and clocks remain in the pinned source, not features.
    """
    buckets, dispositions, seen = {}, {}, set()
    schema = PRICE_ROW_PROVENANCE_SCHEMA if spool == 'prices' else ROW_PROVENANCE_SCHEMA
    identities = sorted(k for k in set(numeric) | set(text) if k == 'provenance' or k.startswith('provenance.'))
    member_slots = sorted((int(m.group(1)), key) for key in numeric
                          if (m := re.fullmatch(r'provenance\.input_record_indices\[(\d+)\]', key)))

    def value(key, ordinal):
        for mapping in (text, numeric):
            if key in mapping and mapping[key][ordinal] is not None:
                return mapping[key][ordinal]
        return None

    def disposition(reason, ordinal):
        item = dispositions.setdefault(reason, dict(rows=0, ordinal_ranges=[]))
        item['rows'] += 1
        ranges = item['ordinal_ranges']
        if ranges and ranges[-1][1] + 1 == ordinal:
            ranges[-1][1] = ordinal
        else:
            ranges.append([ordinal, ordinal])

    previous = None
    for ordinal in range(count):
        if producer_schema != schema:
            disposition('no_bound_row_provenance_producer', ordinal)
            continue
        if value('provenance.schema', ordinal) != schema:
            disposition('missing_or_unsupported_row_provenance', ordinal)
            continue
        index = value('provenance.input_index' if spool == 'prices' else 'provenance.input_cursor', ordinal)
        instrument = value('provenance.instrument_id', ordinal)
        if spool == 'prices' and value('provenance.origin', ordinal) == 'open_group_before_this_source':
            if index is not None:
                raise ValueError('opening-state price row claims an INPUT in this source')
            disposition('opening_group_origin_outside_source', ordinal)
            continue
        if any(type(v) is not int for v in (index, instrument)) or index < 0:
            disposition('unusable_input_or_instrument_identity', ordinal)
            continue
        slot, close = 0, index
        identity, emission = index, index
        if spool == 'prices':
            slot = value('provenance.group_row_ordinal', ordinal)
            close = value('provenance.group_close_input_index', ordinal)
            local = value('provenance.legacy_row_ordinal', ordinal)
            kind = value('provenance.row_kind', ordinal)
            origin = value('provenance.origin', ordinal)
            if (any(type(v) is not int or v < 0 for v in (slot, close, local)) or index > close
                    or kind not in ('trade', 'projection_at_event_group_end')
                    or origin not in ('this_source', 'this_source_apply_failed')):
                raise ValueError('V2 price row has inconsistent source/emission identity')
            if kind == 'projection_at_event_group_end' and index != close:
                raise ValueError('price projection must name the INPUT that emitted it at the group close')
            identity, emission = (index, local), (close, slot)
        if identity in seen or (previous is not None and emission <= previous):
            raise ValueError(spool + ' original identities repeat or emissions run backwards')
        seen.add(identity)
        previous = emission
        if frames is None:
            disposition('unsupported_root_group_membership', ordinal)
            continue
        position = owners.get(index)
        if position is None:
            disposition('no_exact_root_group', ordinal)
            continue
        frame = frames[position]
        if instrument != frame['instrument']:
            raise ValueError(spool + ' instrument differs from its exact ROOT group')
        if close != frame['cursor']:
            raise ValueError(spool + ' emission close differs from its originating INPUT group')
        if spool == 'structures':
            if index != frame['cursor']:
                raise ValueError('structure does not name its owning group closing INPUT')
            members, ended = [], False
            for member_slot, key in member_slots:
                member = value(key, ordinal)
                if member is None:
                    ended = True
                    continue
                if ended or member_slot != len(members) or type(member) is not int:
                    raise ValueError('structure INPUT membership has noninteger members or positional gaps')
                members.append(member)
            if not members:
                disposition('missing_structure_group_membership', ordinal)
                continue
            if members != sorted(frame['members']):
                raise ValueError('structure INPUT membership differs from its exact ROOT frame')
        slots = buckets.setdefault(position, {})
        if slot in slots:
            raise ValueError(spool + ' duplicates a declared row slot within the same ROOT group')
        slots[slot] = ordinal
        disposition('placed', ordinal)

    # Preserve all existing value/text leaves; only explicit identity metadata and absolute clocks are listed.
    clocks = {'ts_recv', 'ts_recv_ns', 'ts_event', 'ts_event_ns'}
    excluded = set(identities) | clocks
    out_numeric, out_text = {}, {}
    for source, target in ((numeric, out_numeric), (text, out_text)):
        for key, values in source.items():
            if key in excluded or not buckets:
                continue
            for slot in sorted({slot for group in buckets.values() for slot in group}):
                name = ('structures.group.' if spool == 'structures' else 'prices.group.rows[%d].' % slot) + key
                target[name] = [values[buckets[position][slot]]
                    if slot in buckets.get(position, {}) else None for position in range(axis_rows)]
    report = dict(schema=schema, source_rows=count,
                  placed_rows=dispositions.get('placed', {}).get('rows', 0),
                  matched_root_frames=len(buckets), frames_without_source_rows=axis_rows - len(buckets),
                  dispositions=dispositions, identities_and_clocks=sorted(set(identities) | (clocks & (set(numeric) | set(text)))),
                  numeric=sorted(out_numeric), text=sorted(out_text),
                  rule='structures equal the original closing INPUT cursor, instrument and full ROOT member list. '
                       'V2 prices require originating INPUT membership, instrument and the emitting group close; '
                       'every declared group-row slot is retained without compression. V1 prices remain unsupported. '
                       'No timestamp/ordinal join, fill or interpolation. '
                       'Group projections and legacy timestamp aliases are the same evidence, not independent observations; '
                       'positions are not identity-linked trajectories or a change to F_LAST lag units')
    return out_numeric, out_text, report


def build_series(day_dir, log, external_fields_mode=None, workers=15, *, data_manifest_sha256=None):
    """The axis and every series on it. Returns (axis_time, series {name: np.ndarray}, cells {name: list}, sources, notes)."""
    import numpy as np
    import pyarrow as pa
    import duckdb
    day_dir = Path(day_dir)
    manifest_raw = (day_dir / 'MANIFEST.json').read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    if data_manifest_sha256 is not None and manifest_sha256 != data_manifest_sha256:
        raise ValueError('selected export manifest differs from the search continuation')
    exported = {}
    export_manifest = json.loads(manifest_raw)
    for item in export_manifest['files']:
        stage, relative = Path(item['stage']), Path(item['path'])
        if (stage.is_absolute() or len(stage.parts) != 1 or '..' in stage.parts
                or relative.is_absolute() or '..' in relative.parts):
            raise ValueError('export path escapes its selected stage')
        key = str(stage / relative)
        if key in exported:
            raise ValueError('duplicate exported artifact identity: ' + key)
        exported[key] = item

    def source_pin(path):
        relative = str(path.relative_to(day_dir))
        pin = exported.get(relative)
        if any(value.is_symlink() for value in (path, *path.parents)):
            raise ValueError('search evidence must be an owner-local regular artifact: ' + relative)
        if pin is None:
            if path.exists():
                raise ValueError('search evidence is not selected by the export: ' + relative)
            return None
        if not path.is_file():
            raise ValueError('selected search evidence is missing: ' + relative)
        return pin

    def read_json(path, pin):
        raw = path.read_bytes()
        if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('search evidence differs from the selected export: ' + str(path))
        return json.loads(raw)

    binding_path = day_dir / 'root' / 'source-binding.json'
    binding_pin = source_pin(binding_path)
    shared_policy = (read_json(binding_path, binding_pin).get('shared_market_policy')
                     if binding_pin is not None else None)
    rows_dir = day_dir / 'root' / 'work' / 'derived' / '.rows'
    sources, notes = [], []
    frames_path = rows_dir / 'frames.jsonl'
    frames_pin = source_pin(frames_path)
    if frames_pin is None:
        raise SystemExit('no book-frame spool at %s: the ROOT legacy pass did not run for this day' % frames_path)
    frames_parse = {}
    f_num, f_text, f_other, n = spool_columns(frames_path, frames_pin, 'ts_recv_ns', workers, frames_parse)
    sources.append(dict(source='frames', path=str(frames_path), rows=n, parse=frames_parse,
                        bytes=frames_pin['bytes'], sha256=frames_pin['sha256'],
                        numeric=sorted(f_num), text=sorted(f_text), not_searched=f_other,
                        frame_sections={section: dict(numeric=sorted(k for k in f_num if k.startswith((section + '.', section + '['))),
                                                      text=sorted(k for k in f_text if k.startswith((section + '.', section + '['))))
                                        for section in ('book', 'activity', 'integrity', 'native_frame', 'observation',
                                                        'input_records', 'input_record_indices')}))
    recv = np.asarray(f_num.pop('ts_recv_ns'), dtype=np.int64)
    axis = np.maximum.accumulate(recv)  # exact nanoseconds; no loss of ordering above 2**53
    backwards = int(np.count_nonzero(np.diff(recv) < 0))
    notes.append(dict(axis='F_LAST group closes', groups=n, receive_clock_steps_backwards=backwards))
    series = {'frames.' + k: np.asarray(v, dtype=object) for k, v in f_num.items()}
    text_cols = {'frames.' + k: v for k, v in f_text.items()}
    gates = [dict(source='frames', passed=True, reason='the axis source itself: each value is its own group close')]

    import frankie_box_experiment_native as NATIVE
    native_numeric, native_text, native_sources, native_notes = NATIVE.read_columns(day_dir, columns, f_num, recv,
                                                                                    workers=workers)
    series.update({name: np.asarray(values, dtype=object) for name, values in native_numeric.items()})
    text_cols.update(native_text)
    sources.extend(native_sources)
    notes.extend(native_notes)
    for native_source in native_sources:
        gates.append(dict(source=native_source['source'], passed=True,
                          reason='only exact emitting INPUT/instrument/receive matches placed; dispositions retain all other rows'))

    import frankie_box_experiment_journal as JOURNAL
    journal_numeric, journal_text, journal_sources, journal_notes = JOURNAL.read_columns(
        day_dir, columns, f_num, recv, workers=workers, frame_sha256=sources[0]['sha256'])
    series.update({name: np.asarray(values, dtype=object) for name, values in journal_numeric.items()})
    text_cols.update(journal_text)
    sources.extend(journal_sources)
    notes.extend(journal_notes)
    for journal_source in journal_sources:
        placed = bool(journal_source.get('searched_rows'))
        gates.append(dict(source=journal_source['source'], passed=True if placed else None,
                          reason=('exact journal INPUT pairing and existing group membership; no timestamp-asof or invented intermediate state'
                                  if placed else 'no journal rows placed; unsupported or incomplete source groups remain explicitly retained')))
    # No DuckDB connection is opened: no query of this preparation runs on one (the alignment is asof_source_rows, the
    # numpy as-of; asof_values and leakage_gate accept a connection argument and never use it). The connection used to
    # open here started a lane-sized thread pool that served nothing and sat in every process the leakage-gate pools
    # below fork from. duckdb stays imported above, so a venv without it still stops at the same point.

    def asof(name, known_at, values_by_col, gates_of_fields=None):
        """Account for source-row selection, then place each numeric column through its existing leakage gate (the
        gates of its fields, in field order, when the caller computed them in a batch with other sources)."""
        valid, unavailable = known_time_rows(known_at)
        if unavailable:
            notes.append(dict(source=name, source_rows=len(known_at), rows_with_integer_clock=len(valid),
                              unplaced_clock_ordinal_ranges=unavailable,
                              reason='missing or non-integer publication/receive clock; original rows retained in '
                                     'the named source; no guessed timestamp or placement; booleans are not clocks'))
        # Placement depends only on these unchanged clocks, not the field values.
        # Reuse the exact original ordinals for every leaf; each field still runs
        # its own leakage gate before gathering any values.
        source_rows = np.fromiter(asof_source_rows(axis, known_at), dtype=np.int64, count=len(axis))
        selected = {int(i) for i in source_rows if i >= 0}
        unselected, unselected_count = [], 0
        for ordinal in valid:
            if ordinal in selected:
                continue
            unselected_count += 1
            if unselected and unselected[-1][1] + 1 == ordinal:
                unselected[-1][1] = ordinal
            else:
                unselected.append([ordinal, ordinal])
        if unselected:
            notes.append(dict(source=name, source_rows=len(known_at), rows_with_integer_clock=len(valid),
                              selected_source_rows=len(selected), unselected_clocked_rows=unselected_count,
                              unselected_clocked_ordinal_ranges=unselected,
                              reason='existing timestamp-asof alignment selects no frame position for these '
                                     'clocked source rows, including overwritten ties or rows between/after frame '
                                     'times; original rows remain in the pinned source. Selection counts describe '
                                     'this alias before per-field leakage gates, not exact ROOT membership, '
                                     'valid observations or additional independent evidence'))
        # every field's gate (independent of the others; the same gate, results in field order) on the lane's workers
        if gates_of_fields is None:
            gates_of_fields = leakage_gates(name, known_at, values_by_col, workers)
        if len(gates_of_fields) != len(values_by_col):
            raise ValueError('leakage gate batch does not match the fields of ' + name)
        for (key, values), gate in zip(values_by_col.items(), gates_of_fields):
            gates.append(gate)
            if gate['passed'] is False:
                notes.append(dict(source=name, field=key, excluded='failed the leakage gate'))
                continue
            series[name + '.' + key] = np.asarray([values[i] if i >= 0 else None for i in source_rows], dtype=object)
        return source_rows

    root_frames, root_owners = JOURNAL._frame_index(f_num, recv)
    derive_path = day_dir / 'root' / 'work' / 'derive.json'
    derive_pin = source_pin(derive_path)
    derive = read_json(derive_path, derive_pin) if derive_pin is not None else {}
    for spool, time_key in (('structures', 'ts_recv_ns'), ('prices', 'ts_recv')):
        path = rows_dir / (spool + '.jsonl')
        pin = source_pin(path)
        if pin is None:
            notes.append(dict(source=spool, missing=str(path)))
            continue
        parse = {}
        num, text, other, count = spool_columns(path, pin, time_key, workers, parse)
        notes.append(dict(source=spool, parse=parse))
        group_numeric, group_text, group_report = root_row_columns(
            spool, num, text, count, root_frames, root_owners, n,
            derive.get('price_row_provenance_schema' if spool == 'prices' else 'row_provenance_schema'))
        group_report.update(frames_sha256=frames_pin['sha256'], membership_implementation=JOURNAL.binding(),
                            producer_receipt=dict(path=str(derive_path), bytes=derive_pin['bytes'], sha256=derive_pin['sha256'])
                            if derive_pin is not None else None)
        aliases = {spool + '.' + key for key in set(num) | set(text)}
        if aliases & (set(group_numeric) | set(group_text)):
            raise ValueError(spool + ' legacy aliases collide with exact group channel names')
        series.update({key: np.asarray(values, dtype=object) for key, values in group_numeric.items()})
        text_cols.update(group_text)
        for mapping in (num, text):
            for key in list(mapping):
                if key == 'provenance' or key.startswith('provenance.'):
                    del mapping[key]
        sources.append(dict(source=spool, path=str(path), rows=count, bytes=pin['bytes'], sha256=pin['sha256'],
                            placement='group projections use exact ROOT membership; legacy aliases keep timestamp-asof selection',
                            identity_limit='price V1/opening-state origins cannot establish exact trade INPUT membership; '
                                           'legacy asof aliases do not establish it either; inspect exact_group_join dispositions',
                            exact_group_join=group_report,
                            numeric=sorted(num), text=sorted(text), not_searched=other))
        gates.append(dict(source=spool + '.group', passed=True if group_report['placed_rows'] else None,
                          reason='only exact original INPUT/group membership placed; no timestamp selection or future fill'))
        if group_report['placed_rows'] != count:
            notes.append(dict(source=spool + '.group', reason='rows without supported exact ROOT membership remain in '
                              'the pinned source; no guessed join; see exact_group_join dispositions',
                              dispositions=group_report['dispositions']))
        if not count:
            notes.append(dict(source=spool, rows=0, reason='empty retained source spool; no observations to place'))
            continue
        # Missing/text clocks remain source evidence but cannot place a row. The
        # common alignment reports every such ordinal rather than raising KeyError.
        known = num.pop(time_key, [None] * count)
        num.pop('ts_event_ns', None), num.pop('ts_event', None)
        rows = asof(spool, known, num)
        for k, values in text.items():            # the same alignment rows as asof_values(con, axis, known, values)
            text_cols[spool + '.' + k] = np.asarray([values[i] if i >= 0 else None for i in rows], dtype=object).tolist()
    # Include selected-but-missing INPUTs so disappearance cannot turn into an optional-source absence.
    inputs = sorted(set(rows_dir.glob('input-*.jsonl')) | {
        day_dir / relative for relative in exported
        if Path(relative).parent == Path('root/work/derived/.rows')
        and Path(relative).match('input-*.jsonl')})
    if len(inputs) > 1:
        raise SystemExit('%d INPUT spools in %s (%s): the same records twice would be counted twice (duplicate data '
                         'declines the run)' % (len(inputs), rows_dir, ', '.join(p.name for p in inputs)))
    if inputs:
        input_pin = source_pin(inputs[0])
        input_sha256 = input_pin['sha256']
        # Reuse ROOT's actual per-instrument membership. A global F_LAST bucket
        # mixes interleaved instruments; timestamp asof can select a later tie.
        event_frames, event_owners = root_frames, root_owners
        group_counts = [{} for _ in range(n)] if event_frames is not None else []
        group_unknown = [0] * n if event_frames is not None else []
        seen_members = [0] * n if event_frames is not None else []
        records, unknown, unplaced = 0, 0, []
        event_fields, event_text, event_identities, event_other = {}, {}, set(), set()
        event_closes = []
        input_parse = {}
        for record in decoded_spool(inputs[0], input_pin, workers, input_parse):
            index = records
            records += 1
            action, side = (v.decode('ascii') if isinstance(v, bytes) else str(v)
                            for v in (record.get('action'), record.get('side')))
            key = '%s_%s' % (action, side)
            size = record.get('size')
            has_size = isinstance(size, (int, float)) and not isinstance(size, bool)
            if not has_size:
                unknown += 1
            stamp = record.get('ts_recv', record.get('ts_recv_ns'))
            position = event_owners.get(index) if event_owners is not None else None
            if position is None:
                JOURNAL._range_add(unplaced, index)
            else:
                frame = event_frames[position]
                if type(record.get('instrument_id')) is not int or record['instrument_id'] != frame['instrument']:
                    raise ValueError('event INPUT instrument differs from its exact ROOT group')
                if index == frame['cursor'] and (stamp != frame['stamp']
                        or type(record.get('flags')) is not int or not record['flags'] & F_LAST):
                    raise ValueError('event closing INPUT differs from its exact ROOT frame')
                counts = group_counts[position]
                counts[key] = counts.get(key, 0) + 1
                if has_size:
                    counts[key + '_size'] = counts.get(key + '_size', 0) + size
                else:
                    group_unknown[position] += 1
                seen_members[position] += 1
            for field, value in record.items():
                if field in EVENT_IDENTITY_FIELDS:
                    event_identities.add(field)
                    continue
                if isinstance(value, bool):
                    value = int(value)
                if isinstance(value, (int, float)) or value is None:
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
                event_closes.append(records - 1)
        matched_closes = event_frames is not None
        if matched_closes and any(seen != len(frame['members']) for seen, frame in zip(seen_members, event_frames)):
            raise ValueError('event INPUT spool does not cover every exact ROOT group member')
        selected_closes = [frame['cursor'] for frame in event_frames] if matched_closes else []
        keys = sorted({key for counts in group_counts for key in counts})
        counts = {key: [group.get(key, 0) for group in group_counts] for key in keys}
        if matched_closes:
            counts['total'] = [sum(value for key, value in group.items() if not key.endswith('_size'))
                               for group in group_counts]
        sources.append(dict(source='events', path=str(inputs[0]), rows=records, groups=len(selected_closes),
                            bytes=input_pin['bytes'], sha256=input_sha256, parse=input_parse,
                            numeric=sorted(counts), records_without_numeric_size=unknown, raw_f_last_closes=len(event_closes),
                            group_binding=dict(schema='FRANKIE_EVENT_GROUP_SEARCH_V2',
                                frames_sha256=sources[0]['sha256'], implementation=JOURNAL.binding(),
                                grouped_records=sum(seen_members), input_index_ranges_without_root_group=unplaced,
                                records_without_numeric_size_per_group=group_unknown,
                                rule='exact ROOT input_record_indices and closing input_cursor; no timestamp asof or '
                                     'cross-instrument accumulator; integer counts/sizes remain exact; size sums include '
                                     'only numeric sizes, with unknown-size counts retained separately; records without '
                                     'ROOT membership remain in the pinned INPUT source, not assigned another close'),
                            per_event_fields=dict(numeric_fields=sorted(event_fields), text_fields=sorted(event_text),
                                                  placement='closing INPUT per matching F_LAST frame',
                                                  coverage_scope='events.last only; V2 frames.input_records separately carries all closed-group members',
                                                  frame_binding_matched=matched_closes,
                                                  selected_records=len(selected_closes),
                                                  individually_unsearched_records=records - len(selected_closes),
                                                  identities_and_clocks=sorted(event_identities),
                                                  not_searched=sorted(event_other)),
                            after_last_close=dict(records=records - (event_closes[-1] + 1 if event_closes else 0),
                                                  note='tail after the last raw F_LAST; all unplaced INPUT indices are listed in group_binding')))
        if matched_closes:
            series.update({'events.' + key: np.asarray(values, dtype=object) for key, values in counts.items()})
            for field, values in event_fields.items():
                series['events.last.' + field] = np.asarray([values[i] for i in selected_closes], dtype=object)
            for field, values in event_text.items():
                text_cols['events.last.' + field] = [values[i] for i in selected_closes]
            gates.append(dict(source='events', passed=True,
                              reason='exact ROOT INPUT membership and closing cursor/instrument/receive stamp; no asof tie selection'))
        else:
            notes.append(dict(source='events', excluded='ROOT lacks exact INPUT group membership; counts and closing-record '
                              'projection unavailable, original records and index dispositions preserved'))
    else:
        notes.append(dict(source='events', missing=str(rows_dir / 'input-*.jsonl')))
    dipole_paths = sorted(set((day_dir / 'run' / 'execution').glob('cycle-*/host-dipole-classroom-source*.json')) |
        set((day_dir / 'teacher').glob('host-dipole-classroom-source*.json')) | {
            day_dir / relative for relative in exported
            if (Path(relative).match('run/execution/cycle-*/host-dipole-classroom-source*.json')
                or Path(relative).match('teacher/host-dipole-classroom-source*.json'))})
    if len(dipole_paths) > 1:
        raise SystemExit('%d Dipole classroom sources for one day (%s): duplicate data declines the run'
                         % (len(dipole_paths), ', '.join(str(p) for p in dipole_paths)))
    if dipole_paths:
        source_pin(dipole_paths[0])   # a selected-but-missing source is not an optional absence
        import frankie_box_experiment_dipole as DIPOLE
        dipole_numeric, dipole_text, dipole_sources, dipole_notes = DIPOLE.read_columns(
            day_dir, dipole_paths[0], columns, journal_numeric, journal_text, recv)
        series.update({name: np.asarray(values, dtype=object) for name, values in dipole_numeric.items()})
        text_cols.update(dipole_text)
        sources.extend(dipole_sources)
        notes.extend(dipole_notes)
        gates.append(dict(source='dipole', passed=True if dipole_sources[0]['searched_rows'] else None,
                          reason='exact APPLIED cursor/prefix placement and source-cursor availability; '
                                 'no receive-time tie selection or invented target'))
    else:
        notes.append(dict(source='dipole', missing=str(day_dir / 'run' / 'execution' / 'cycle-*' / 'host-dipole-classroom-source*'),
                          reason='no exported teacher-only or classroom Dipole source for this day'))
    derived = day_dir / 'root' / 'work' / 'derived'
    flow_path, roll_path = derived / 'legacy_native_signed_flow.json', derived / 'legacy_per_second_roll20.json'
    flow_pin = source_pin(flow_path)
    if flow_pin is not None:
        flow = read_json(flow_path, flow_pin)
        per = flow.get('per_second') or []
        sources.append(dict(source='legacy_native_signed_flow', path=str(flow_path), rows=len(per),
                            bytes=flow_pin['bytes'], sha256=flow_pin['sha256']))
        if per:
            known = [(p['second'] + 1) * 10**9 for p in per]   # second s known at s+1
            asof('signed_flow', known, {'buy': [p.get('buy') for p in per], 'sell': [p.get('sell') for p in per]})
        else:
            notes.append(dict(source='legacy_native_signed_flow', rows=0,
                              reason='empty retained per-second source; no observations to place'))
    else:
        notes.append(dict(source='legacy_native_signed_flow', missing=str(flow_path)))
    roll_pin = source_pin(roll_path)
    if roll_pin is not None:
        roll = read_json(roll_path, roll_pin)
        values = roll.get('series') or []
        first = roll.get('first_second')
        sources.append(dict(source='legacy_per_second_roll20', path=str(roll_path), rows=len(values),
                            bytes=roll_pin['bytes'], sha256=roll_pin['sha256']))
        if values and type(first) is int:
            known = [(first + i + 1) * 10**9 for i in range(len(values))]
            asof('roll20', known, {'value': [float('nan') if v is None else v for v in values]})
        elif values:
            notes.append(dict(source='legacy_per_second_roll20', source_rows=len(values),
                              unplaced_clock_ordinal_ranges=[[0, len(values) - 1]],
                              reason='missing or non-integer first_second; every original row retained in the '
                                     'pinned source; no guessed clock or placement; booleans are not clocks'))
        else:
            notes.append(dict(source='legacy_per_second_roll20', rows=0,
                              reason='empty retained roll20 source; no observations to place'))
    else:
        notes.append(dict(source='legacy_per_second_roll20', missing=str(roll_path)))
    # Frankie's 13 historical points (FRANKIE_DAY_EXTERNAL_V1, Greg 2026-09-29: "everyone who sees his ingest should
    # see these data points too"): the day file attached beside the sealed ingest, exported with the ingest, read
    # through its one as-of reader at the day's halt (a value past it is refused, never filtered), each point a series
    # known from its own publication stamp; the leakage gate runs on each as on every other source.
    # The export catalog admits nested ingest paths; select its actual day file, not a guessed top-level alias.
    external_paths = sorted(set((day_dir / 'ingest').rglob('day-external.json')) | {
        day_dir / relative for relative, item in exported.items()
        if item['stage'] == 'ingest' and Path(item['path']).name == 'day-external.json'})
    if len(external_paths) > 1:
        raise ValueError('more than one external day file; no selection or merge may be guessed: ' +
                         ', '.join(str(path) for path in external_paths))
    external = external_paths[0] if external_paths else day_dir / 'ingest' / 'day-external.json'
    external_receipt = external.with_name('day-external-receipt.json')
    external_pin = source_pin(external)
    if external_pin is not None:
        from research.kalshi.frankie_boss.operations.frankie_day_external import (
            AsOfReader, search_series, SEARCH_SERIES, StagingRefused)
        body = read_json(external, external_pin)
        # the stamp shape of the file read (the classroom's one test, dipole_classroom_external.stamp_shape): READER_STAMP
        # = every table carries event_time_ns and published_ns is the reader stamp max(event time, publication) with the
        # 14:00 ET default, so this search and the shared reader place every point alike; PUBLICATION_STAMP = a superseded
        # file stamped at publication (its placement is not in the file): read as stamped, named as a visible finding
        from research.kalshi.frankie_boss.dipole_classroom_external import (
            stamp_shape, STAMP_SHAPE_READER)
        shape, without_event_time = stamp_shape(body)
        if shape != STAMP_SHAPE_READER:
            notes.append(dict(source='external.stamp_shape', finding='superseded_publication_stamp_file', stamp_shape=shape,
                              tables_without_event_time=without_event_time,
                              reason='read as stamped (publication); the reader-stamp placement is not in this file'))
        receipt_pin = source_pin(external_receipt)
        if receipt_pin is not None:
            receipt = read_json(external_receipt, receipt_pin)
            if receipt['sha256'] != external_pin['sha256']:
                raise StagingRefused('%s differs from its receipt sha256' % external)
        else:
            notes.append(dict(source='external.receipt', missing=str(external_receipt),
                              reason='no selected companion receipt; day-file bytes remain bound to the export'))
        # Same AsOfReader validation/clock policy as open(), consuming the exact checked bytes above.
        reader = AsOfReader(body, body['halt_ns'])
        ext, absent = search_series(reader)
        # the aliases' gates in one batch on the lane's workers (each is the gate asof() would run), then asof() in order
        alias_gates = leakage_gate_batch([('external.' + name + '.value', known, values)
                                          for name, (known, values) in sorted(ext.items())], workers, what='external aliases')
        for (name, (known, values)), gate in zip(sorted(ext.items()), alias_gates):
            asof('external.' + name, known, {'value': values}, [gate])
        # Keep each entity's fields even when another entity/alias has identical values. Reuse columns() so nested,
        # boolean, missing and mixed numeric/text leaves follow the same exact-value rule as the existing spools.
        mode = external_fields_mode or os.environ.get('SEARCH_EXTERNAL_FIELDS', 'all')
        if mode not in ('all', 'aliases'):
            raise ValueError('SEARCH_EXTERNAL_FIELDS must be all or aliases')
        text_fields, mixed, searched_fields, identity_fields = [], [], [], []
        if mode == 'all':
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import frankie_box_experiment_surface as SURFACE
            # Two passes over the same sorted fields: the first decides each field's role and flattens its values
            # (pure), so every field's leakage gates run in one batch on the lane's workers; the second is the
            # original per-field placement in the original order with those gates.
            planned = []
            for key, (stamps, values) in sorted(SURFACE.external_fields(reader).items()):
                qualified, _, _entity = key.rpartition('.entity=')
                point, column = qualified.rsplit('.', 1)
                # identities and clocks (entity keys, event_time_ns, storage.estimate's print_ns): never a numeric signal
                if column == reader.body['points'][point]['stamp_column'] or \
                        column in SURFACE.identity_and_clock_columns(point):
                    planned.append((key, None, None))
                    continue
                planned.append((key, stamps, columns(({'value': value} for value in values), '')))
            field_gates = iter(leakage_gate_batch(
                [('external.' + key + '.' + leaf, stamps, leaf_values)
                 for key, stamps, flat in planned if flat is not None for leaf, leaf_values in flat[0].items()],
                workers, what='external day-file fields'))
            for key, stamps, flat in planned:
                if flat is None:
                    identity_fields.append(key)
                    continue
                numeric, text, listed, _ = flat
                rows = asof('external.' + key, stamps, numeric, [next(field_gates) for _ in numeric])
                searched_fields.extend('external.' + key + '.' + leaf for leaf in numeric
                                       if 'external.' + key + '.' + leaf in series)
                for leaf, leaf_values in text.items():
                    name = 'external.' + key + '.' + leaf
                    # the same alignment rows as asof_values(con, axis, stamps, leaf_values)
                    text_cols[name] = np.asarray([leaf_values[i] if i >= 0 else None for i in rows], dtype=object).tolist()
                    text_fields.append(name)
                mixed.extend(dict(field=key, note=item) for item in listed)
        # the registry entries each point declares it feeds (frankie_box_all99_coverage.external_point_entries); a name
        # outside the 99 is a finding, listed; a point without a declaration is outside the 99
        import frankie_box_all99_coverage as ALL99
        point_entries, point_mapping, entry_findings = {}, {}, []
        for point, table in sorted((body.get('points') or {}).items()):
            mapped = ALL99.external_point_mapping(table)
            point_entries[point] = mapped['entries']
            point_mapping[point] = {k: mapped[k] for k in ('mapping', 'mapping_reason', 'event_time_basis', 'note')}
            entry_findings.extend(dict(f, point=point) for f in mapped['findings'])
        sources.append(dict(source='external', path=str(external), bytes=external_pin['bytes'],
                            sha256=external_pin['sha256'], schema=body.get('schema'),
                            registry_entries=point_entries, registry_mapping=point_mapping,
                            registry_entry_findings=entry_findings,
                            stamp_shape=shape, tables_without_event_time=without_event_time,
                            stamp_shape_finding=(None if shape == STAMP_SHAPE_READER else dict(
                                kind='superseded_publication_stamp_file', stamp_shape=shape,
                                tables_without_event_time=without_event_time,
                                note='a superseded day file stamped at publication: read as stamped; a value with no '
                                     'intrinsic event time may be read before its 14:00 ET placement; rebuild the day '
                                     'file (frankie_box_day_external) for the reader stamp')),
                            placement_note=('the search places each point through the day file\'s own as-of reader '
                                            '(AsOfReader / search_series, owned by the day-file piece) at its stamps, '
                                            'which are the reader stamps max(event time, publication) with the 14:00 ET '
                                            'default: the same instants the shared reader uses'
                                            if shape == STAMP_SHAPE_READER else
                                            'a superseded publication-stamp file: the search reads each point at its '
                                            'publication stamp; the placement (max(event time, publication)) is not in '
                                            'the file, so the search and the shared reader may differ; listed as a '
                                            'finding'),
                            receipt=str(external_receipt) if receipt_pin is not None else None,
                            receipt_pin={key: receipt_pin[key] for key in ('bytes', 'sha256')} if receipt_pin is not None else None,
                            series=sorted(ext), absent=absent, missing=body.get('missing'),
                            all_fields=dict(mode=mode, searched=searched_fields, cells=text_fields,
                                            alias_policy='retain entity fields alongside legacy aliases; shared values are not independent evidence',
                                            alias_definitions=[dict(name=name, point=point, column=column, where=where)
                                                               for name, point, column, where in SEARCH_SERIES],
                                            identities_and_clocks=identity_fields, mixed_channels=mixed)))
    else:
        notes.append(dict(source='external', missing=str(external),
                          reason="no day file of Frankie's 13 points beside the ingest (frankie_box_day_external.sh)"))
    # The declared trading date is the source's session label, not an invented UTC date from a receive timestamp.
    # Date/weekday condition the same market observations; they are never another signal or independent evidence.
    trading_date = date.fromisoformat(export_manifest['day'])
    text_cols['context.trading_day'] = [export_manifest['day']] * n
    text_cols['context.trading_weekday'] = [('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
                                           'Sunday')[trading_date.weekday()]] * n
    sources.append(dict(source='context', path=str(day_dir / 'MANIFEST.json'), sha256=manifest_sha256,
        trading_day=export_manifest['day'], date_basis='export-declared trading/session date, not per-record UTC date',
        rule='dates and weekdays are categorical search conditions on the same market signals, not x/y quantities; '
             'each run is still one day and these cells do not provide independent evidence'))
    # Readers have finished identity/clock/mask use. Remove non-market signals before transforms/pair work;
    # keep lawful context as cells. JSON scalar labels distinguish an integer ID from a similarly spelled string.
    excluded_channels = {}
    context_channels = []
    for channel_kind, mapping in (('series', series), ('cells', text_cols)):
        for name in list(mapping):
            reason = non_market_reason(name)
            if reason == 'context_only':
                if channel_kind == 'series':
                    old = text_cols.get(name, [None] * len(mapping[name]))
                    merged = []
                    for number, label in zip(mapping[name], old):
                        if number is not None and label is not None:
                            raise ValueError('numeric and text context channels overlap: ' + name)
                        value = number if number is not None else label
                        merged.append(None if value is None else json.dumps(value, ensure_ascii=False, allow_nan=False))
                    text_cols[name] = merged
                    context_channels.append(name)
                    del mapping[name]
                continue
            if reason is not None:
                source = ('journal.group' if name.startswith('journal.group.') else
                          '.'.join(name.split('.')[:2]) if name.startswith('native.') else name.split('.')[0])
                item = excluded_channels.setdefault((source, reason), dict(source=source, excluded=reason,
                    series=[], cells=[], disposition='non_market_context_only',
                    retained='original pinned source; identities/clocks still support exact joins and causal masks'))
                item[channel_kind].append(name)
                del mapping[name]
    notes.extend(excluded_channels[key] for key in sorted(excluded_channels))
    notes.append(dict(source='context', moved_from_series_to_cells=sorted(context_channels),
        reason='IDs/calendar labels are search conditions grouping actual market signals; no numerical transforms/targets',
        numeric_label_encoding='JSON scalar, preserving original scalar type; existing text-only labels unchanged'))
    cells, unused = {}, []
    for k, v in text_cols.items():
        cells[k] = v
    # Actual placed channels, distinct from the static plane-to-source map. A read file can have no usable channels.
    prefixes = {'legacy_native_signed_flow': 'signed_flow.', 'legacy_per_second_roll20': 'roll20.'}
    for source in sources:
        prefix = prefixes.get(source['source'], source['source'] + '.')
        source['placed_series'] = sorted(name for name in series if name.startswith(prefix))
        source['placed_cells'] = sorted(name for name in cells if name.startswith(prefix))
        source['exclusions'] = [note for note in notes if 'excluded' in note and
                                (note.get('source') == source['source'] or note.get('source', '').startswith(prefix))]
    notes.append(dict(cells_not_yet_used=unused))
    if sha256_file(day_dir / 'MANIFEST.json') != manifest_sha256:
        raise ValueError('selected export manifest changed during source preparation')
    for note in notes:
        if note.get('source') and ('missing' in note or 'excluded' in note or 'reason' in note):
            log('search source disposition: %s; %s; %s (full details retained in manifest notes)' % (
                note['source'], note.get('missing', ''),
                note.get('excluded') or note.get('reason') or 'not included in the selected export'))
    log('series: %d on %d groups (%d receive-clock steps backwards), %d cell columns' % (len(series), n, backwards, len(cells)))
    if shared_policy is not None:
        from frankie_box_market_timeline import SharedFrameView
        market_view = SharedFrameView(f_num, recv, series, cells, policy=shared_policy, sources=sources)
        series, cells = market_view.series, market_view.cells
        sources.append(market_view.report)
    return axis, series, cells, sources, notes, gates


# The leakage gates of one source's fields are independent of each other (each runs odcore.leakage on its own field
# with its own fixed seed), so a source with many fields over many rows runs them on pinned forked workers, results in
# field order (the Sept 29 pattern, item 4: independent pieces side by side). Below GATE_PARALLEL_MIN_CELLS
# (rows x fields), with one field or one worker, they run in the coordinator. The gate itself is unchanged; a dead
# worker's field is gated again (frankie_box_lane_pin.ordered_map).
GATE_PARALLEL_MIN_CELLS = 1 << 16
_GATE = {}
SOURCE_PASSES = []        # where the parallel source passes ran (MANIFEST cpu_placement.source_passes); diagnostic only


def _gate_job(index):
    source, known_at, values = _GATE['jobs'][index]
    return leakage_gate(None, source, known_at, values)


def leakage_gate_batch(jobs, workers=1, what=None):
    """[leakage_gate(None, source, known_at, values) for (source, known_at, values) in jobs], in job order."""
    cells = sum(len(known_at) for _, known_at, _ in jobs)
    if workers <= 1 or len(jobs) < 2 or cells < GATE_PARALLEL_MIN_CELLS:
        return [leakage_gate(None, source, known_at, values) for source, known_at, values in jobs]
    import multiprocessing
    started, count = time.time(), min(workers, len(jobs))
    _GATE['jobs'] = jobs
    try:
        gates = [gate for _, gate in _lane_pin().ordered_map(
            _gate_job, range(len(jobs)), count, context=multiprocessing.get_context('fork'), cpus=lane_cpus(),
            report=POOL_RECOVERY)]
    finally:
        _GATE.clear()
    SOURCE_PASSES.append(dict(what='leakage gates', source=what, fields=len(jobs), rows=cells, workers=count,
                              seconds=round(time.time() - started, 3)))
    return gates


def leakage_gates(name, known_at, values_by_col, workers=1):
    """[leakage_gate(..., name + '.' + key, known_at, values) for each key of values_by_col], in key order."""
    return leakage_gate_batch([(name + '.' + key, known_at, values) for key, values in values_by_col.items()],
                              workers, what=name)


def leakage_gate(con, source, known_at, values):
    """odcore.leakage on the REAL alignment (asof_values), in the source's own row order: the value aligned as of the
    moment row i became known must not change when every later row of the source is scrambled. Checked at 65 rows
    spread over the source, each the last row of its timestamp (rows known at the same instant are not "later")."""
    import numpy as np
    from odcore.leakage import assert_no_leakage
    valid, _ = known_time_rows(known_at)
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

# The partner-side FFTs of one cell, memoized per worker process (Greg, 2026-10-07: every mechanism that makes a stage
# faster gets used). A cell/x job couples x with every (ty, y) partner of the cell; without this cache each job
# recomputes transforms(y) for every partner, so the y-side rffts are repeated once per x. The jobs are ordered by
# cell, so a worker keeps the partners of its current cell and drops them when the cell changes; when the cell's
# partners do not all fit the byte cap, the ones that fit stay (the same prefix hits on every job; no eviction thrash).
# transforms() is deterministic, so a cached value equals a recomputed one bit for bit: rows, counts and parts are
# invariant. Per-worker hits/misses are aggregated into MANIFEST.fft_cache for the one-day canary.
_FFT_CACHE = dict(cell=None, entries={}, bytes=0, hits=0, misses=0, not_cached=0)
_FFT_CACHE_BYTES = int(os.environ.get('FRANKIE_SEARCH_FFT_CACHE_BYTES', str(512 * 1024 * 1024)))   # per worker process


def _partner_transforms(cell, key, values):
    """transforms(values()) for partner `key` of `cell`, from the worker's cache when it holds it."""
    cache = _FFT_CACHE
    if cache['cell'] != cell:
        cache.update(cell=cell, entries={}, bytes=0)
    hit = cache['entries'].get(key)
    if hit is not None:
        cache['hits'] += 1
        return hit
    cache['misses'] += 1
    fy = transforms(values())
    size = fy['s'].nbytes + fy['a'].nbytes
    if cache['bytes'] + size <= _FFT_CACHE_BYTES:
        cache['entries'][key] = fy
        cache['bytes'] += size
    else:
        cache['not_cached'] += 1
    return fy


def _fft_cache_stats():
    return dict(hits=_FFT_CACHE['hits'], misses=_FFT_CACHE['misses'], not_cached=_FFT_CACHE['not_cached'],
                entries=len(_FFT_CACHE['entries']), bytes=_FFT_CACHE['bytes'], cap_bytes=_FFT_CACHE_BYTES)


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

def _lane_pin():
    """frankie_box_lane_pin (the shared lane placement of the data/search pieces), beside this file."""
    try:
        import frankie_box_lane_pin as LP
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import frankie_box_lane_pin as LP
    return LP


def lane_cpus():
    """The held lane's CPUs, never the host count: FRANKIE_LANE_CPUS or FRANKIE_BOOKED_CPUS (cores' cpu_list, e.g.
    '0-15') intersected with this process's affinity; the affinity alone when neither names a CPU of it. Read once per
    process (frankie_box_lane_pin.lane_cpus), so the coordinator pinning itself later never shrinks its workers' lane."""
    return _lane_pin().lane_cpus()


def worker_cpus(workers):
    """One lane CPU per worker (frankie_box_lane_pin.placement): the coordinator keeps the first CPU of the physical-core
    order; the workers take the other cores' threads first and the coordinator's sibling last (Greg, 2026-10-07: CPUs
    pinned to the jobs and workers, physical-core aware)."""
    return _lane_pin().placement(workers, lane_cpus())[1]


def pin_coordinator(workers):
    """Pin this (the coordinator's) thread to the placement's coordinator CPU once the source preparation (DuckDB's
    threads, the readers' own pools) is done; the CPU map for the manifest."""
    LP = _lane_pin()
    lane = lane_cpus()
    placed = LP.record(workers, lane, what='search coordinator + transform/coupling/discovery pool workers')
    # numpy's OpenBLAS settled once here, before the pools fork (each worker inherits it) and before the coordinator
    # narrows to its one CPU (the self-check's 32 OpenBLAS threads take the lane): one thread per worker with
    # the proven 32-thread reduction order for any Pearson dot product, or exactly 32 threads when the self-check fails
    # (dipole_classroom_external.blas_reduction, Greg 2026-10-07 night: N=32 on every lane). The workers' FFTs are not
    # BLAS; the discovery engine's own Julia BLAS is a separate library, not set here.
    from research.kalshi.frankie_boss.dipole_classroom_external import blas_reduction
    placed['blas_reduction'] = blas_reduction()
    placed['coordinator_pinned'] = LP.pin_thread(placed['coordinator'], lane) is not None
    return placed


def _run_pending(context, workers, function, jobs):
    """Keep only the held lane's workers in flight; a stop drains each submitted operation. Ordered, pinned, and a dead
    worker never hangs or stops the stage: its lost job is redone (frankie_box_lane_pin.ordered_map; a lost coupling
    job's half-written part is set aside first, _cell_retry), the window shrinks by one; listed in POOL_RECOVERY."""
    yield from _lane_pin().ordered_map(function, jobs, workers, context=context, cpus=lane_cpus(),
                                       stop=_stop_requested, report=POOL_RECOVERY,
                                       on_retry=_cell_retry if function is _cell_job else None,
                                       fallback=_discovery_lost if function is _discovery_job else None)


# Dead pool workers and the jobs redone for them, over every pool of this search (manifest cpu_placement.pool_recovery)
POOL_RECOVERY = dict(worker_deaths=[], redone=[])
PART_DIGESTS = {}         # coupling part -> sha256 its job recorded for the bytes it wrote (the part's pin)
PART_READS = {}           # coupling part -> (bytes, sha256) of the discovery read of it (an integrity cross-check)


def _part_digest(part):
    """The sha256 a finished coupling job recorded in its saved state (complete=True): the fsynced bytes it renamed to
    `part`, or the file it re-hashed and compared on a resume. None when the job wrote no part (fewer than 2 steps) or
    the state is not readable (then the part is hashed at publication, listed)."""
    try:
        from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state
        state = _load_raw_state(Path(part + '.state.pkl'))
    except Exception:  # noqa: BLE001 - the part is hashed at publication instead (listed in source_passes)
        return None
    return state.get('sha256') if state.get('complete') else None


def _cell_retry(args):
    """Before a coupling job whose worker died is run again: with no saved continuation state, the part (and its .tmp)
    it was writing is set aside as <name>.lost-<ts> (never deleted), so the redo starts its part fresh (as the job
    would from nothing); with saved state the redo resumes from it exactly as a resume does."""
    part = args[0]
    if Path(part + '.state.pkl').is_file():
        return
    stamp = int(time.time() * 1000)
    for name in (part + '.tmp', part):
        if Path(name).exists():
            os.replace(name, '%s.lost-%d' % (name, stamp))
            POOL_RECOVERY['redone'].append(dict(set_aside=name, to='%s.lost-%d' % (name, stamp)))


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


# Step #3 plane receipt (CCode, 2026-10-06). One row per layer in the 49-layer calculation/clock subset (the pin
# knowledge/CYCLE_CALCULATION_PINS.md) plus the categories the calculations themselves find (action-string families, mirror
# identity, fill disposition, discovery status, the D chain's reasons) and the day file. This is not the full 99-layer
# ingestion/knowledge/answer/output roster. Each row: the status of the plane
# on the experiment path, the exact series/cells this search consumes it through (or nothing), and what remains of it.
#   consumed / consumed_partial are historical map labels, not runtime proof. plane_summary emits them as
#   mapped / mapped_partial and points to actual source channels, exclusions, cells_not_counted and coupling parts.
#   produced_not_carried the pinned producer computes it at every F_LAST close (it is in the journal's APPLIED frame) but
#                       the ROOT legacy pass does not spool it, so no file this search reads carries it
#   computed_not_retained the pinned teacher computes it and retains only a projection of it (named)
#   built_not_called    an implementation exists in the repository and nothing on the experiment path calls it
#   not_produced        only the bedrock traversal/projection (ROOT processes 2 and 3, off) produces it
#   clock               a timestamp or availability rule; it places the series, it is not searched as one
# Reading a source does not establish whole-plane computation or that a usable pair was produced.
PLANE_COVERAGE = (
    # registry group: legacy (5)
    ('legacy_price', 'prices', 'consumed', 'prices.price, prices.size, prices.bid_px_00, prices.ask_px_00 (trades, as-of)', None),
    ('legacy_native_signed_flow', 'legacy_native_signed_flow', 'consumed', 'signed_flow.buy, signed_flow.sell (per second, as-of)', None),
    ('legacy_per_second_roll20', 'legacy_per_second_roll20', 'consumed', 'roll20.value (per second, as-of)', None),
    ('legacy_book_imbalance', 'frames', 'consumed', 'frames.best_bid/best_ask/mid/depth_imbalance_n, frames.spread, '
     'depth_imbalance_full, bid/ask_depth_full, bid/ask_order_count_full, bid/ask_price_level_count_full (the axis); '
     'cell frames.transition (the sign signature)', None),
    ('legacy_structure_observables', 'structures', 'consumed', 'structures.group.* at exact ROOT membership when '
     'supported; structures.* legacy timestamp aliases (describe_structure): '
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
     'new teacher sources also retain full DState through dipole.group.rows[position].dstate.*; '
     'old sources have no trajectory backfill; the bedrock episode rows are not produced'),
    ('derived_open_world_predecessor_state', 'structures', 'consumed_partial', 'cell structures.discovery_status '
     '(CARRIED_SEED_MATCH / OPEN_WORLD_CANDIDATE per group)', 'predecessor state across groups (bedrock) is not produced'),
    ('derived_ancestry_gaps', None, 'not_produced', None, 'bedrock projection only'),
    ('derived_price_flow_book_paths', 'frames', 'consumed_partial', 'the legacy path: prices.*, frames.*, signed_flow.*',
     'the book-regime path (native_book_regime.observe_snapshot, bedrock) is not produced'),
    ('derived_v4_mechanics_fifo_features', None, 'not_produced', None,
     'native_full_capture_adapter._window_extras belongs to the disabled full-capture traversal; '
     'the retained V4 frame book/activity sections are related inputs, not this derived layer'),
    ('derived_feature_availability_timestamps', None, 'not_produced', None,
     'the registry layer is not produced by this ROOT; asof placement is not a substitute for its derived stamps'),
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
    ('clock_event_known_by', None, 'clock', 'asof selects the latest known value at each group close; values superseded '
     'before a close are not individually searched; events.last is bound to its own F_LAST frame', None),
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
     'V2 frames.book.*_levels_full[i] carry every level, including FIFO; legacy ROOTs are not retrofilled'),
    ('price_level_and_order_counts', 'frames', 'consumed_partial', 'frames.bid/ask_price_level_count_full, '
     'frames.bid/ask_order_count_full; V2 frames.book.*_levels_full[i].order_count', 'legacy ROOTs are not retrofilled'),
    ('fifo_queues', 'frames', 'consumed_partial',
     'V2 frames.book.*_levels_full[i].fifo_queue[j].* and observation.levels.*[i].order_ids[j]',
     'rank-position channels preserve FIFO order, not an identity-linked lifecycle calculation; older ROOTs may lack them'),
    ('queue_age_and_survival', 'frames', 'consumed_partial',
     'V2 frames.book.*_levels_full[i] age summaries and fifo_queue[j].priority_age_s; teacher survival columns remain',
     'all-level snapshots are not an across-group order-identity survival calculation'),
    ('queue_concentration', 'frames', 'consumed_partial',
     'V2 frames.book.*_levels_full[i].largest_order_share/front_order_size; teacher far_size_hhi unchanged',
     'older ROOTs may lack full-depth fields'),
    ('orders_and_volume_ahead', 'frames', 'consumed_partial',
     'V2 frames.book.*_levels_full[i].fifo_queue[j].volume_ahead/size/order_id; observation.orders[i].*',
     'queue index is the zero-based orders-ahead position; identity linking across groups remains separate'),
    ('spread_and_depth_imbalance', 'frames', 'consumed', 'frames.spread, frames.depth_imbalance_n, frames.depth_imbalance_full', None),
    ('complete_state_reset_bootstrap_receipts', 'events', 'consumed_partial', 'events.last.is_snapshot (the record flag)',
     'the bootstrap receipts (bedrock) are not produced'),
    # registry group: microstructure mechanics (7)
    ('mechanics_actions_by_side_and_level', 'structures', 'consumed_partial', 'structures.action_counts.*, side_counts.*, '
     'events.<action>_<side>; new frames.activity.<window>.* carries the original rolling activity values',
     'no complete per-order/per-level event history is inferred from window summaries'),
    ('aggressor_and_native_signed_flow', 'legacy_native_signed_flow', 'consumed_partial', 'signed_flow.buy/sell per second',
     'V2 frames.input_records[i].* additionally carries each group member at its close; no event-axis lag search'),
    ('depletion_and_replenishment', 'dipole', 'consumed_partial', 'the teacher\'s far_replenish_log1p_64/1024, '
     'far_absorption_share_64/1024', 'the bedrock replenishment/absorption rows (native_replay_driver) are not produced'),
    ('resilience_and_recovery', 'dipole', 'consumed_partial', 'the teacher\'s far_identity_survival_64/1024, '
     'far_size_retention_64/1024', 'the bedrock recovery rows are not produced'),
    ('churn_and_queue_turnover', 'frames', 'consumed_partial',
     'frames.activity.<window>.add_cancel_churn and priority_lost_modify_count',
     'available only in ROOTs retaining frame sections; full FIFO turnover history remains unconnected'),
    ('price_and_book_path', 'prices', 'consumed', 'prices.*, frames.* on the axis', None),
    ('missingness_and_integrity_flags', 'dipole', 'consumed_partial', 'the Dipole rows\' states are counted per column in '
     'the manifest (states_per_component); a value is used only where PRESENT',
     'new frames.integrity.* carries every produced integrity counter; the ROOT failures spool is not read; '
     'dipole.<column>.state/.reason now supply as-of categorical cells'),
    # categories the calculations find, beyond the registry names
    ('action-string families (CARRIED_NATIVE_ACTION_FAMILIES and every open-world candidate)', 'structures', 'consumed',
     'cells structures.action_string, structures.candidate_family_id, structures.carried_native_family, '
     'structures.discovery_status; series structures.matches_carried_native_family', None),
    ('mirror identity (canonical / mirror orientation, pair key)', 'structures', 'consumed',
     'cells structures.mirror.orientation, structures.mirror.mirror_pair_key, structures.mirror.mirror_side_string', None),
    ("the D chain's reasons (CHAIN_BROKEN, NO_COMPLETED_STEP, DEGENERATE_STEP) and every column's state", 'dipole',
     'consumed_partial', 'dipole.<column>.state/.reason categorical cells plus state counts in the manifest',
     'all source-bound original target rows also enter dipole.group.rows[position].*; unmatched/unclosed source groups '
     'remain explicit, and full internal DState is not retained'),
    ("the teacher's 19 Dipole columns", 'dipole', 'consumed', 'dipole.<column> for every column whose state is PRESENT', None),
    ('odcore.info_dipole divergence / exhaustion (signed_flow_features, divergence, cell_signal)', None, 'built_not_called',
     None, 'referenced only as the construction of historical claims H01/H02 (frankie_box_historical_claims.py); '
     'computing it on the day\'s signed flow is a new derived series (a mathematical decision)'),
    ("Frankie's 13 historical points (27 aliases)", 'external', 'consumed', 'external.<alias>.value', None),
    ('day-file tables, every column per entity', 'external', 'consumed_partial',
     'external.<table>.<column>.entity=<id>.value (and nested leaves); text cells (SEARCH_EXTERNAL_FIELDS=all)',
     'identity/clock columns are listed; asof samples publication values at group closes; see actual channels/exclusions'),
    ('sealed journal INPUT entries (every record, every field)', 'events', 'consumed_partial',
     'events.* per-group counts and events.last.<field>; identities and clocks listed (EVENT_IDENTITY_FIELDS)',
     'events.last is closing-only; V2 frames.input_records[i].* carries every group member/field. journal.group now carries '
     'normal complete INPUT/APPLIED group envelopes; failed/unclosed/unmatched scopes and event-axis search remain explicit/open'),
    ('sealed journal APPLIED entries (the V4 frame and the full-book observation)', 'journal.group', 'consumed_partial',
     'journal.group.entries[position].* (complete normal INPUT/APPLIED envelopes at exact existing F_LAST membership)',
     'intermediate effect/order/rank fields enter at their group close; absent snapshots remain None. Failed, unknown, '
     'unpaired and unclosed/mismatched groups have explicit retained dispositions; native-event axis remains unapplied'),
)


def plane_summary(sources, notes):
    """Source mapping, not whole-plane coverage proof. Actual channels/exclusions live in sources, uncounted cells in
    cells_not_counted, and computed pair rows in couplings.parts. Do not infer computation merely from a file read."""
    read = {s['source']: s for s in sources}
    missing = {n['source'] for n in notes if 'missing' in n}
    out = {}
    for name, source, status, consumed_by, remaining in PLANE_COVERAGE:
        declared_status = status
        receipt = read.get(source)
        if source is not None and status in ('consumed', 'consumed_partial', 'clock', 'retained_not_searched') and source not in read:
            status = 'listed_missing' if source in missing else 'not_in_this_export'
        elif status in ('consumed', 'consumed_partial'):
            status = 'mapped' if status == 'consumed' else 'mapped_partial'
            if not receipt.get('placed_series') and not receipt.get('placed_cells'):
                status = 'read_without_channels'
            elif receipt.get('exclusions'):
                status = 'mapped_partial'
        if name == 'day-file tables, every column per entity' and receipt:
            fields = receipt.get('all_fields') or {}
            if fields.get('mode') != 'all':
                status = 'not_requested'
            elif not fields.get('searched') and not fields.get('cells'):
                status = 'read_without_channels'
        if name == 'churn_and_queue_turnover' and receipt:
            activity = (receipt.get('frame_sections') or {}).get('activity') or {}
            if not activity.get('numeric'):
                status = 'produced_not_carried'
        if status == 'not_produced' and 'native.member' in read:
            # The older table describes the legacy-only route. Exact native rows
            # now have their own measured field/ordinal receipts; a file read is
            # not a per-registry-layer proof, so do not invent that reconciliation.
            status = 'native_evidence_present_layer_mapping_open'
        if remaining and 'bedrock' in remaining and 'native.member' in read:
            # the legacy route's remaining text names the native (bedrock) pass; this ROOT ran it, so say so
            remaining += ('; this ROOT\'s native pass ran: its exact native rows are placed (native_exact_emission_rows; '
                          'the 18 native-only entries have their own per-entry rows below)')
        out[name] = dict(status=status, declared_status=declared_status, source=source, source_read=receipt is not None,
                         mapped_by=consumed_by, remaining=remaining,
                         evidence='sources placed_series/placed_cells/exclusions; cells_not_counted; couplings.parts')
    external = read.get('external')
    if external and external.get('registry_entries'):
        # Frankie's points tied to the 99 (2026-10-07): per entry a point declares it feeds, the series of that point the
        # search placed (external.<point>... and its legacy aliases), each at its own publication stamp (as-of placement)
        import re
        aliases = {}
        for item in (external.get('all_fields') or {}).get('alias_definitions') or []:
            aliases.setdefault(item.get('point'), []).append(item.get('name'))
        placed = list(external.get('placed_series') or []) + list(external.get('placed_cells') or [])
        by_entry = {}
        for point, entries in external['registry_entries'].items():
            patterns = ([r'^external\.' + re.escape(point) + r'(?:\.|$)']
                        + [r'^external\.' + re.escape(a) + r'(?:\.|$)' for a in aliases.get(point) or [] if a])
            series = [x for x in placed if any(re.match(p_, x) for p_ in patterns)]
            for entry in entries:
                slot = by_entry.setdefault(entry, dict(points=[], series=0, series_patterns=[]))
                slot['points'].append(point)
                slot.setdefault('mapping', {})[point] = (external.get('registry_mapping') or {}).get(point)
                slot['series'] += len(series)
                slot['series_patterns'].extend(patterns)
        for entry, slot in by_entry.items():
            prior = out.get(entry) or dict(status='not_in_this_export', declared_status=None, source=None, source_read=False,
                                           mapped_by=None, remaining=None)
            status = prior.get('status')
            if slot['series'] and status not in ('mapped', 'clock'):
                status = 'mapped_partial' if status in ('mapped_partial', 'native_carrier_without_rows') else 'mapped'
            out[entry] = dict(prior, status=status, external=dict(slot, summary='%d series of day-file point(s) %s, each at '
                                                                       'its publication stamp' % (slot['series'], slot['points'])))
    native_reports = [read[n] for n in ('native.member', 'native.lifecycle') if n in read]
    if native_reports:
        # The 18 native-only registry entries (Greg, 2026-10-07: they reach Frankie and both teachers): each entry's own
        # carriers (the projection plan's producers' crosswalk, else the retained crosswalk text; recorded by the native
        # reader as registry_entries) matched against the native series and cells this search actually placed. Exact
        # values at their GROUP_CLOSE emission frame; no new equation form; an entry with nothing placed is listed with
        # the native reader's own dispositions for its sections.
        import frankie_box_all99_coverage as ALL99
        carriers = {}
        for report in native_reports:
            carriers.update(report.get('registry_entries') or {})
        placed_series = [s for r in native_reports for s in r.get('placed_series') or []]
        placed_cells = [c for r in native_reports for c in r.get('placed_cells') or []]
        lifecycle = read.get('native.lifecycle') or {}
        for name in ALL99.NATIVE_ENTRIES:
            spec = carriers.get(name) or ALL99.NATIVE_SERIES[name]
            patterns = ALL99.native_series_patterns(name, carriers or None)
            series = [s for s in placed_series if any(p.match(s) for p in patterns)]
            cells = [c for c in placed_cells if any(p.match(c) for p in patterns)]
            prior = out.get(name) or {}
            unplaced = None
            if not series and not cells:
                unplaced = dict(member_paths=['%s: no placed native.member.row field (absent from every member row on this day, '
                                              'or excluded as an identity/clock: see exclusions)' % p for p in spec.get('member') or ()],
                                sections={s: (lifecycle.get('sections') or {}).get(s) or 'no lifecycle row of this section in the ledger'
                                          for s in spec.get('sections') or ()})
            fed = ((prior.get('external') or {}).get('series') or 0) > 0
            out[name] = dict(prior, status='mapped' if series or cells else 'mapped_partial' if fed else 'native_carrier_without_rows',
                             declared_status=prior.get('declared_status'), source_read=True,
                             legacy_route=dict(source=prior.get('source'), status=prior.get('status'), mapped_by=prior.get('mapped_by')),
                             source='native.member' if spec.get('member') else 'native.lifecycle',
                             mapped_by='native carriers: member %s, sections %s (%s)' % (
                                 list(spec.get('member') or ()), list(spec.get('sections') or ()), spec.get('source')),
                             native=dict(series=len(series), cells=len(cells), series_patterns=[p.pattern for p in patterns],
                                         unplaced=unplaced,
                                         summary='%d series / %d cells of its own native carriers placed' % (len(series), len(cells))),
                             evidence='native source placed_series/placed_cells (names matching series_patterns); '
                                      'native dispositions per section; couplings.parts')
    if 'native.member' in read:
        out['native_exact_emission_rows'] = dict(status='mapped_partial',
            sources=['native.member', 'native.lifecycle'],
            mapped_by='exact emitting INPUT cursor/instrument/receive -> unchanged F_LAST frame',
            remaining='post-stream, unsupported and unmatched rows explicitly retained; identity-linked trajectories, '
                      'full registry reconciliation and all teacher consumers remain open',
            evidence='native source row/ordinal dispositions and actual placed_series/placed_cells')
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
            fy = _partner_transforms((cell_col, cell_value), (ty, y), lambda: pick(steps[ty][y]))
            row = dict(header, x=x, y=y, cell=cell_col, cell_value=cell_value, transform=tx, x_transform=tx,
                       y_transform=ty, **couple(fx, fy, lags))
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
    # The fifth element is this worker's cache accounting at the end of a freshly computed job (never saved in the
    # retained result: a recovered job reports none); the caller aggregates it for MANIFEST.fft_cache.
    return result + (_fft_cache_stats(),)


# ------------------------------------------------------------------------------- symbolic discovery (stage 7 spec row)
# Greg, 2026-10-06: new discovery is central. Daily runs must be able to discover new nonlinear and multivariable
# relationships; a fixed catalogue of pairwise tests is not a substitute. Discovery GENERATES candidates; scientific
# checking and acceptance (the scientific teacher, the survivor update) assess them without narrowing it. The fitting
# mathematics is the existing one, unchanged: odcore.symbolic (PySR, Julia backend) with its own regressor configuration
# (_regressor: operators + - * / square cube exp log sqrt, squared loss, model_selection best) and discover()'s defaults
# (niterations 40, maxsize 12). Nothing here defines a new equation form.
#
# The problem set is the search's own result, per cell: for each cell and each target series y, the features are every
# (x, k) for which a coupling row of THIS cell found x leading y at best lag k > 0 beyond chance (every transform pair
# counts; each nomination keeps its part file and row ordinal). The rows are the cell's group closes t (a step belongs
# to the cell of the group it arrives at, as in the couplings) with target y[t] and features x[t - k]: strictly earlier
# group closes, so every feature is causal; odcore.leakage.assert_no_leakage checks each lag construction on the real
# series (the value as of row i must not change when every later row is scrambled). Values are the search's placed
# series, unchanged (float64 only because the regressor requires it). A row missing the target or any feature blocks
# only that row of that problem (counted per reason); a problem with fewer than two usable rows, or a failed leakage
# check, is listed and not fitted. Every seed's Pareto front is retained individually: nothing is averaged across
# seeds, cells, targets or days. The loss is the regressor's own objective, never a finding summary.
DISCOVERY_SCHEMA = 'FRANKIE_SEARCH_DISCOVERY_INDEX_V1'
DISCOVERY_NITERATIONS, DISCOVERY_MAXSIZE = 40, 12            # odcore.symbolic.discover defaults


def _part_nominations(args):
    """(rows read, [(key, feature, provenance)] in row order) of one coupling part (the reading discovery_nominations
    has always done, one part per call)."""
    part, staging = args
    path, found, read = Path(part), [], 0
    hashed, size = hashlib.sha256(), 0
    # read as bytes, every line hashed as read (the part's one read also checks its pin); json.loads decodes UTF-8
    # bytes exactly as the text read did (json.dumps lines carry no carriage return, so no newline translation applied)
    with path.open('rb') as handle:
        for ordinal, line in enumerate(handle):
            hashed.update(line)
            size += len(line)
            read += 1
            row = json.loads(line)
            lag = row.get('best_lag')
            if not row.get('beyond_chance') or type(lag) is not int or lag <= 0:
                continue
            found.append(((row['cell'], row.get('cell_value'), row['y']), (row['x'], lag), dict(
                part=str(path.relative_to(staging)), row=ordinal, x_transform=row.get('x_transform'),
                y_transform=row.get('y_transform'), same_way=row.get('same_way'), opposite=row.get('opposite'),
                both_moving=row.get('both_moving'), null_shifts=row.get('null_shifts'))))
    return read, found, (size, hashed.hexdigest())


def discovery_nominations(parts, staging, workers=1, context=None):
    """{(cell, cell_value, y): {(x, k): [provenance]}} from the coupling parts: rows beyond chance with x leading y.
    The parts are read side by side by the lane's pinned workers and merged in part order, so the mapping, its key
    order and every provenance list are those of one reader going through the parts in order."""
    out, read = {}, 0
    jobs = [(part, staging) for part in sorted(parts) if Path(part).is_file()]
    if workers > 1 and len(jobs) > 1:
        import multiprocessing
        started, count = time.time(), min(workers, len(jobs))
        results = _lane_pin().ordered_map(_part_nominations, jobs, count, context=context or multiprocessing.get_context('fork'),
                                          cpus=lane_cpus(), window=count * 4, report=POOL_RECOVERY)
    else:
        started, count = None, 1
        results = ((job, _part_nominations(job)) for job in jobs)
    for job, (rows, found, pinned) in results:
        read += rows
        PART_READS[job[0]] = pinned
        for key, feature, provenance in found:
            out.setdefault(key, {}).setdefault(feature, []).append(provenance)
    if started is not None:
        SOURCE_PASSES.append(dict(what='discovery nominations (coupling parts read)', parts=len(jobs), rows=read,
                                  workers=count, seconds=round(time.time() - started, 3)))
    return out, read


def _discovery_job(args):
    identity = dict(search=_JOB['identity'], job=args)
    path = _JOB['recovery'] / ('discovery-' + args[0] + '.pkl')
    if path.is_file():
        return _load_state(path, identity)['result']
    result = _discovery_compute(args)
    _save_state(path, dict(identity=identity, result=result))
    return result


def _discovery_lost(args):
    """A discovery problem whose worker process died on every try (e.g. the fitting engine crashed it): listed with that
    disposition, no result file, never fitted in the coordinator (the search goes on; missing-coverage rule)."""
    problem_id, cell_col, cell_value, y, features = args[:5]
    return dict(id=problem_id, cell=cell_col, cell_value=cell_value, target=y, rows_in_cell=None, rows_used=None,
                status='worker_died', reason='the worker process running this problem died on every try (pool recovery '
                'redid it); not fitted, listed', seconds=None, features=len(features), file=None, bytes=None, sha256=None,
                fitted_seeds=0)


def _discovery_compute(args):
    """One problem: rows, operand dispositions, the leakage check of every lag construction, then the existing regressor
    once per seed (when the engine is importable in this process); its result file is written once, then pinned."""
    import numpy as np
    import frankie_box_experiment_transforms as T
    problem_id, cell_col, cell_value, y, features, seeds, niterations, maxsize = args
    started = time.time()
    out = _JOB['discovery_dir'] / 'problems' / (problem_id + '.json')
    if out.is_file():
        # R-D (fresh review): a crash between this file and its recovery pickle leaves the written result; it is read
        # back, never recomputed (the bytes carry wall `seconds`, and a fitted problem is not reproducible across
        # processes). It stands only when it is this exact problem (id, cell, target, features, seeds, regressor
        # settings); anything else is retained and refused, as before
        data = out.read_bytes()
        try:
            prior = json.loads(data)
        except ValueError as error:
            raise ValueError('discovery result exists but is not readable JSON (retained for recovery): %s: %s' % (out, error))
        expected = dict(schema=DISCOVERY_SCHEMA + '_PROBLEM', id=problem_id, cell=cell_col, cell_value=cell_value, target=y,
                        features=[dict(name='x%d' % i, series=x, lag=k) for i, (x, k) in enumerate(features)],
                        seeds=list(seeds), regressor=dict(module='odcore.symbolic', configuration='_regressor',
                                                          niterations=niterations, maxsize=maxsize))
        expected = json.loads(json.dumps(expected, sort_keys=True, default=str))   # the file's own JSON encoding
        if not isinstance(prior, dict) or {k: prior.get(k) for k in expected} != expected:
            raise ValueError('discovery result exists for another problem definition (retained for recovery): %s' % out)
        return dict({k: prior.get(k) for k in ('id', 'cell', 'cell_value', 'target', 'rows_in_cell', 'rows_used', 'status',
                                                'reason', 'seconds')},
                    features=len(features), file=str(out.relative_to(_JOB['discovery_dir'])), bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(), fitted_seeds=len(prior.get('fits') or []),
                    read_back='the result file written before a crash, read back (not recomputed)')
    series = _JOB['series']
    idx = _JOB['cells'][(cell_col, cell_value)]
    n = len(series[y])
    rows = list(range(n)) if idx is None else [int(j) + 1 for j in idx]
    first = max(k for _, k in features)
    excluded = dict(before_first_lag=sum(1 for t in rows if t < first), target_missing=0,
                    feature_missing={'%s@%d' % (x, k): 0 for x, k in features})
    used = []
    for t in rows:
        if t < first:
            continue
        if not T.finite(series[y][t]):
            excluded['target_missing'] += 1
            continue
        missing = [(x, k) for x, k in features if not T.finite(series[x][t - k])]
        if missing:
            for x, k in missing:
                excluded['feature_missing']['%s@%d' % (x, k)] += 1
            continue
        used.append(t)
    from odcore.leakage import assert_no_leakage
    leakage = []
    for x, k in features:
        p = np.asarray(series[x], dtype=object)
        def signal_at(i, ts_, p_, bv_, sv_, k=k):
            return p_[i - k] if i - k >= 0 else None
        probe = sorted(set(used[int(j)] for j in np.linspace(0, len(used) - 1, min(65, len(used))).astype(int))) if used else []
        passed, fails = assert_no_leakage(signal_at, np.arange(n), p, np.arange(n), np.zeros(n), probe)
        leakage.append(dict(feature='%s@%d' % (x, k), passed=bool(passed), checked=len(probe), fails=len(fails)))
    result = dict(schema=DISCOVERY_SCHEMA + '_PROBLEM', id=problem_id, cell=cell_col, cell_value=cell_value, target=y,
                  features=[dict(name='x%d' % i, series=x, lag=k) for i, (x, k) in enumerate(features)],
                  rows_in_cell=len(rows), rows_used=len(used), excluded=excluded, leakage=leakage, seeds=list(seeds),
                  regressor=dict(module='odcore.symbolic', configuration='_regressor', niterations=niterations, maxsize=maxsize))
    if any(not g['passed'] for g in leakage):
        result.update(status='leakage_failed', reason='a lag construction failed odcore.leakage; not fitted (listed)')
    elif len(used) < 2:
        result.update(status='too_few_rows', reason='fewer than two rows with the target and every feature present')
    else:
        try:
            # parallelism='serial', deterministic=True: one Julia thread does the fit; the default 'auto' would start a
            # host-count thread pool in each of the lane's workers. The fits do not depend on it.
            os.environ.setdefault('PYTHON_JULIACALL_THREADS', '1')
            from odcore.symbolic import _regressor
            import pysr  # noqa: F401  (the existing Julia-backed engine; imported in this worker only)
        except Exception as error:   # noqa: BLE001 - an absent engine blocks only this equation, named
            result.update(status='equation_not_run', reason='the existing fitting engine is not importable in the box venv '
                          '(%s: %s); installing it is a box change on Greg\'s go' % (type(error).__name__, str(error)[:200]))
        else:
            X = np.asarray([[float(series[x][t - k]) for x, k in features] for t in used], dtype=np.float64)
            target = np.asarray([float(series[y][t]) for t in used], dtype=np.float64)
            fits = []
            for seed in seeds:
                model = _regressor(niterations, maxsize, seed)
                model.fit(X, target, variable_names=['x%d' % i for i in range(len(features))])
                eqs = model.equations_
                best = int(eqs['score'].idxmax())
                fits.append(dict(seed=seed, best_equation=str(eqs.loc[best, 'equation']),
                                 best_complexity=int(eqs.loc[best, 'complexity']), best_loss=float(eqs.loc[best, 'loss']),
                                 best_score=float(eqs.loc[best, 'score']),
                                 pareto=[dict(complexity=int(r.complexity), loss=float(r.loss), score=float(r.score),
                                              equation=str(r.equation)) for r in eqs.itertuples()]))
            result.update(status='fitted', fits=fits,
                          note='each seed retained individually; reproduction across seeds and acceptance are scientific '
                               'checking (not this stage)')
    result['seconds'] = round(time.time() - started, 3)
    data = (json.dumps(result, indent=1, sort_keys=True, default=str) + '\n').encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.read_bytes() != data:
        raise ValueError('discovery result exists with other bytes (retained for recovery): %s' % out)
    if not out.is_file():
        pending = out.with_suffix('.json.pending')
        with pending.open('wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, out)
    return dict({k: result.get(k) for k in ('id', 'cell', 'cell_value', 'target', 'rows_in_cell', 'rows_used', 'status',
                                             'reason', 'seconds')},
                features=len(features), file=str(out.relative_to(_JOB['discovery_dir'])), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                fitted_seeds=len(result.get('fits') or []))


def discovery(day, cycle, day_role, staging, parts, context, workers, log):
    """Write <search>/discovery/INDEX.json (DISCOVERY_SCHEMA): every problem the couplings nominate, with its result
    pin or its listed disposition; nothing silent. Runs inside the held lane's workers (the same fork context)."""
    import importlib.util
    started = time.time()
    directory = staging / 'discovery'
    directory.mkdir(parents=True, exist_ok=True)
    _JOB['discovery_dir'] = directory
    mode = os.environ.get('FRANKIE_DISCOVERY', 'on')
    seeds = tuple(int(s) for s in os.environ.get('FRANKIE_DISCOVERY_SEEDS', '0').split(',') if s.strip())
    engine = dict(module='odcore.symbolic', regressor='_regressor (operators, loss and model selection unchanged)',
                  niterations=DISCOVERY_NITERATIONS, maxsize=DISCOVERY_MAXSIZE, seeds=list(seeds),
                  pysr_findable=importlib.util.find_spec('pysr') is not None,
                  basis='found by importlib.util.find_spec in the parent; imported only inside each worker (Julia is not '
                        'initialised before the fork)')
    index = dict(schema=DISCOVERY_SCHEMA, day=day, cycle=cycle, day_role=day_role, engine=engine, mode=mode,
                 problem_definition=('per cell: target y[t] at the cell\'s group closes; features x[t-k] for every (x, k) '
                                     'a coupling row of the same cell found beyond chance with x leading y at best lag k > 0; '
                                     'values unchanged; rows missing an operand counted per reason'),
                 listed=[dict(item='step form (differences of y and x)', reason='not run: the value form is the placed series '
                              'as the couplings read them; the step form is a separate problem definition for Greg'),
                         dict(item='the target\'s own earlier values as a feature', reason='not run: autoregressive terms are '
                              'not nominated by a coupling row of x leading y'),
                         dict(item='cross-cell and cross-day problems', reason='never pooled: one cell, one day per problem'),
                         dict(item='acceptance', reason='discovery generates candidates; reproduction across seeds, '
                              'walk-forward and the tautology null are scientific checking, not this stage')],
                 rule='one problem per cell and target; every seed retained; nothing averaged; a missing operand blocks '
                      'only its row; a missing engine blocks only the fit; everything listed')
    if day_role != 'discovery':
        index.update(status='not_run_confirmation_day', problems=[], counts={},
                     reason='a confirmation day runs only the frozen survivor list; discovery is for discovery days')
    elif mode != 'on':
        index.update(status='not_run_disabled', problems=[], counts={}, reason='FRANKIE_DISCOVERY=%s' % mode)
    else:
        nominations, rows_read = discovery_nominations(parts, staging, workers, context)
        jobs = []
        for (cell_col, cell_value, y), features in sorted(nominations.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
            ordered = sorted(features)
            problem_id = hashlib.sha256(json.dumps([cell_col, cell_value, y, ordered], default=str).encode()).hexdigest()[:16]
            jobs.append((problem_id, cell_col, cell_value, y, ordered, seeds, DISCOVERY_NITERATIONS, DISCOVERY_MAXSIZE))
        provenance = {problem_id: {'%s@%d' % f: nominations[(cell, value, y)][f] for f in feats}
                      for problem_id, cell, value, y, feats, _, _, _ in jobs}
        results = []
        for _, result in _run_pending(context, workers, _discovery_job, jobs):
            results.append(result)
            _progress('search: discovery problems', done=len(results), total=len(jobs), unit='problems', every=10)   # heartbeat; failures counted

        if _stop_requested():
            raise SystemExit(75)          # every submitted problem saved its result; resume reuses them
        if len(results) != len(jobs):
            raise ValueError('discovery workers stopped before every problem was retained; resume with the stop request cleared')
        counts = {}
        for result in results:
            counts[result['status']] = counts.get(result['status'], 0) + 1
        index.update(status='indexed', coupling_rows_read=rows_read, problems=results, counts=counts,
                     nominations_file='nominations.json')
        data = (json.dumps(provenance, indent=1, sort_keys=True, default=str) + '\n').encode()
        (directory / 'nominations.json').write_bytes(data)
        index['nominations'] = dict(file='nominations.json', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                    what='every coupling row (part, row ordinal, transforms, counts) that nominated each feature')
    index['seconds'] = round(time.time() - started, 3)
    index['workflow_report'] = dict(
        schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='discovery',
        inputs=dict(day=day, cycle=cycle, day_role=day_role, coupling_parts=len(parts), engine=engine,
                    series='the search\'s placed series (leakage-gated at placement), forked to the workers unchanged'),
        use=dict(problem_definition=index['problem_definition'], mode=mode, listed=index['listed'],
                 coupling_rows_read=index.get('coupling_rows_read'), counts=index.get('counts'),
                 seconds=index['seconds'], model_calls=0),
        outputs=dict(status=index['status'], index='discovery/INDEX.json', problems=len(index.get('problems') or []),
                     nominations=index.get('nominations'),
                     brain='the search knowledge entry is filed by the orchestrator after the MANIFEST; recorded there'),
        rule='candidates only; acceptance is scientific checking; nothing averaged; missing evidence means unknown, never zero')
    data = (json.dumps(index, indent=1, sort_keys=True, default=str) + '\n').encode()
    path = directory / 'INDEX.json'
    pending = path.with_suffix('.json.pending')
    with pending.open('wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, path)
    log('discovery: %s, %d problem(s) %s in %.0f s' % (index['status'], len(index.get('problems') or []),
                                                       json.dumps(index.get('counts') or {}, sort_keys=True), index['seconds']))
    return dict(status=index['status'], counts=index.get('counts'), problems=len(index.get('problems') or []),
                index=dict(path='discovery/INDEX.json', bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))


def workflow_report(manifest, day_dir, identity, *, phase_timings, fft_cache, workers):
    """The piece's inputs / use / outputs record for the one-day review (Greg, 2026-10-07; schema shared with the
    teacher, the export and the adviser pieces so frankie_box_workflow_inspection projects it). Inputs: the export
    manifest pin and every source the series were read from (path, bytes, sha256, rows), the directive, the pinned
    code. Use: the axis, every leakage gate, every excluded/missing/listed disposition, what was not searched, the
    cells not counted, the transforms and lags, the chance check, where the time went. Outputs: the coupling parts
    with pins, the counts (rows, beyond-chance), the planes receipt. A count is a count; it is not a finding and not
    proof that the scientific teacher consumed it."""
    notes = manifest['notes']
    dispositions = [note for note in notes if any(k in note for k in ('excluded', 'missing', 'reason', 'listed'))]
    shared = [s for s in manifest['sources'] if s.get('source') == 'shared_market']
    return dict(schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='search',
                inputs=dict(day=manifest['day'], cycle=manifest['cycle'], day_role=manifest['day_role'],
                            data_manifest=dict(path=str(day_dir / 'MANIFEST.json'), sha256=identity['data_manifest_sha256'],
                                               source_binding='the governed export of this day and cycle (MANIFEST.json, '
                                                              'checked again before publication)'),
                            sources=[{k: s.get(k) for k in ('source', 'path', 'bytes', 'sha256', 'rows', 'frames', 'exact_membership')
                                      if k in s} for s in manifest['sources']],
                            frozen_survivors=manifest.get('frozen_survivors'), lags=manifest['lags'],
                            transforms=manifest['transforms']['names'],
                            experiment_directive=(manifest.get('experiment_directive') or {}).get('sha256'),
                            code_pins={k: identity.get(k) for k in ('code_sha256', 'transform_sha256', 'surface_sha256',
                                                                   'native_reader_sha256', 'journal_reader', 'dipole_reader')},
                            workers=workers, cpu_placement=manifest.get('cpu_placement')),
                use=dict(axis='F_LAST group closes of the ROOT frame spool in spool order; the running maximum of the '
                              'receive clock in exact nanoseconds; never a timestamp as-of or a dense grid',
                         exact_membership=(shared[0].get('exact_membership') if shared else
                                           'no shared-market policy on this ROOT: the legacy F_LAST view'),
                         leakage=manifest['leakage'],
                         dispositions=dispositions,
                         not_searched=manifest['not_searched'],
                         cells_not_counted=manifest['cells_not_counted'],
                         cells=len(manifest['cells']), series=len(manifest['series']),
                         transforms=dict(names=manifest['transforms']['names'], pairs=manifest['transforms']['pairs'],
                                         unclassified_steps=manifest['transforms']['unclassified_steps']),
                         chance_check='every circular shift of y outside the lag window; a pair is beyond chance only when '
                                      'no shift reached |D| at the best lag (an orientation, the counts are the result)',
                         phase_timings=phase_timings, fft_cache=fft_cache, model_calls=0,
                         all99_coverage=dict(counts=(manifest.get('all99_coverage') or {}).get('shared_counts'),
                                             integrity=(manifest.get('all99_coverage') or {}).get('integrity'),
                                             native_entries={k: dict(status=v.get('status'), native=v.get('native'))
                                                             for k, v in (manifest.get('planes') or {}).items()
                                                             if isinstance(v, dict) and v.get('native')})),
                outputs=dict(status='searched', manifest='MANIFEST.json beside the coupling parts',
                             discovery=manifest.get('discovery'),
                             all99_coverage='MANIFEST.json all99_coverage (FRANKIE_ALL99_COVERAGE_V1, piece search)',
                             couplings=manifest['couplings'], planes=len(manifest['planes']) if isinstance(manifest.get('planes'), list)
                             else manifest.get('planes'),
                             brain='knowledge-findings.json and the brain entry are filed by the orchestrator '
                                   '(Run.search_knowledge) after this manifest; recorded there, not here',
                             refusals='an existing MANIFEST declines a second search; a confirmation day without a frozen '
                                      'survivor list is refused; no ROOT frame spool means no axis: refused before this '
                                      'manifest (listed by the orchestrator, the day goes on)',
                             waits=['a requested stop (exit 75) saves every submitted operation and resumes from it']),
                rule='recorded inputs, use and outputs of this piece for the one-day review; a count is not a finding and '
                     'not proof of downstream consumption; missing evidence means unknown, never zero')


WORKFLOW_REPORT_FILE_SCHEMA = 'FRANKIE_SEARCH_WORKFLOW_REPORT_FILE_V1'
WORKFLOW_REPORT_LIST_BYTES = 256 * 1024


def compact_report(value, at):
    """The workflow report for the one-day review file: every list whose JSON exceeds WORKFLOW_REPORT_LIST_BYTES is
    named by {items, json_bytes, full_record_at} (its exact location in MANIFEST.json); everything else as recorded.
    The MANIFEST keeps every item; nothing here is a result or a gate."""
    if isinstance(value, dict):
        return {key: compact_report(item, '%s.%s' % (at, key)) for key, item in value.items()}
    if isinstance(value, list):
        size = len(json.dumps(value, sort_keys=True))
        if size > WORKFLOW_REPORT_LIST_BYTES:
            return dict(items=len(value), json_bytes=size, full_record_at=at)
        return [compact_report(item, '%s[%d]' % (at, i)) for i, item in enumerate(value)]
    return value


def search(day, cycle, day_role, lags, frozen, log, root=ROOT, data_root=None, workers=8, transform_names=None):
    if type(lags) is not int or lags < 0:
        raise ValueError('lags must be a nonnegative integer')
    # Where the time goes (Greg, 2026-10-07): seconds per phase, in the manifest as phase_timings. Diagnostic only.
    phases, phase_started = {}, [time.time()]
    def phase(name):
        now = time.time()
        phases[name] = round(phases.get(name, 0.0) + now - phase_started[0], 3)
        phase_started[0] = now
        _progress('search: %s done' % name, done=len(phases), unit='phases', every=None)   # heartbeat; failures counted
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import frankie_box_experiment_transforms as T
    import frankie_box_experiment_surface as SURFACE
    import frankie_box_experiment_native as NATIVE
    import frankie_box_experiment_journal as JOURNAL
    import frankie_box_experiment_dipole as DIPOLE
    external_fields_mode = os.environ.get('SEARCH_EXTERNAL_FIELDS', 'all')
    if external_fields_mode not in ('all', 'aliases'):
        raise ValueError('SEARCH_EXTERNAL_FIELDS must be all or aliases')
    transform_names = list(transform_names or T.TRANSFORMS)
    if len(transform_names) != len(set(transform_names)):
        raise ValueError('transform names must be unique; duplicate jobs would share retained output paths')
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
                    external_fields_mode=external_fields_mode, surface_sha256=sha256_file(SURFACE.__file__),
                    native_reader_sha256=sha256_file(NATIVE.__file__),
                    journal_reader=JOURNAL.binding(), dipole_reader=DIPOLE.binding(),
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
    phase('identity_and_recovery')
    prepared_path = recovery / 'prepared.pkl'
    if prepared_path.is_file():
        prepared = _load_state(prepared_path, identity)['prepared']
        phase('prepare_series_loaded_from_recovery')
    else:
        if _stop_requested():
            raise SystemExit(75)
        # This existing source preparation is one operation. A requested stop lets it finish and retains every array.
        prepared = build_series(day_dir, log, external_fields_mode=external_fields_mode, workers=workers,
                                data_manifest_sha256=identity['data_manifest_sha256'])
        _save_state(prepared_path, dict(identity=identity, prepared=prepared))
        phase('prepare_series')
    axis, series, cells, sources, notes, gates = prepared
    if _stop_requested():
        raise SystemExit(75)
    cpu_placement = pin_coordinator(workers)      # the coordinator on its own CPU; the pools below take the rest
    cpu_placement['pool_recovery'] = POOL_RECOVERY   # filled as the pools run; written whole with the manifest
    # where each parallel source pass ran (the spool parses also sit on their sources' `parse`); a preparation loaded
    # from recovery lists only the passes after it
    cpu_placement['source_passes'] = SOURCE_PASSES
    # visibility (stacks pass): the SIGTERM disposition every pool worker inherits by fork (a caught SIGTERM is what hung
    # a2's shard stop: terminate() then an unbounded join); default here, recorded so a change shows on day 1
    import signal
    handler = signal.getsignal(signal.SIGTERM)
    cpu_placement['sigterm_inherited_by_workers'] = ('default' if handler == signal.SIG_DFL else
                                                     'ignored' if handler == signal.SIG_IGN else
                                                     'handler %s (a pool terminate() could be caught)' % getattr(
                                                         handler, '__qualname__', repr(handler)))
    cpu_placement['probe_failures'] = PROBE_FAILURES
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
        _progress('search: transform steps', sum(len(v) for v in steps.values()), len(step_jobs), 'series x transform')
    if _stop_requested():
        raise SystemExit(75)       # all submitted transforms have drained and saved their full results
    phase('transform_steps')
    cells_path = recovery / 'cells.pkl'
    if cells_path.is_file():
        cell_index = _load_state(cells_path, identity)['cells']
    else:
        cell_index = {('whole-day', None): None}
        for col, values in sorted(cells.items()):
            if all(type(v) is str for v in values[1:] if v is not None):
                # one pass per column: the positions of each distinct text label in step order, the same arrays as
                # np.nonzero(arrived == value)[0] (str equality is the dict's), instead of one full comparison per
                # label (labels x steps; ID-valued context cells have about one label per group)
                positions = {}
                for position, value in enumerate(values[1:]):     # a step belongs to the cell of the group it arrives at
                    if value is not None:
                        positions.setdefault(value, []).append(position)
                for value in sorted(positions):
                    cell_index[(col, value)] = np.asarray(positions[value], dtype=np.intp)
                continue
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
    phase('cells_and_jobs')
    started = time.time()
    parts, count, beyond, not_counted = [], 0, 0, []
    # Per-worker FFT cache accounting: the last report from each fresh job stands in for its worker (hits and misses
    # are cumulative per process); the aggregate is the sum over the latest report of every job, an upper bound on
    # distinct workers' totals only when workers are distinguishable, so it is recorded as 'reported_by_jobs'.
    cache_reports, recovered_jobs = [], 0
    for _, result in _run_pending(context, workers, _cell_job, jobs):
        if result is None:
            continue                # this worker saved its exact next pair on the cooperative stop
        part, n_rows, n_beyond, short = result[:4]
        if len(result) > 4:
            cache_reports.append(result[4])
        else:
            recovered_jobs += 1
        if short:
            not_counted.append(short)
        parts.append(part)
        PART_DIGESTS[part] = _part_digest(part)
        count += n_rows
        beyond += n_beyond
        _progress('search: coupling cells', done=len(parts), total=len(jobs), unit='cell jobs', every=10, rows=count)   # heartbeat; failures counted
    if _stop_requested():
        raise SystemExit(75)         # every submitted pair worker has saved; no child is left running
    if len(parts) != len(jobs):
        raise ValueError('search workers stopped before every job was retained; resume with the stop request cleared')
    phase('couplings')
    fft_cache = dict(cap_bytes_per_worker=_FFT_CACHE_BYTES, fresh_jobs=len(cache_reports), recovered_jobs=recovered_jobs,
                     last_report_hits=max((r['hits'] for r in cache_reports), default=0),
                     last_report_misses=max((r['misses'] for r in cache_reports), default=0),
                     last_report_not_cached=max((r['not_cached'] for r in cache_reports), default=0),
                     basis='per-worker cumulative counters at each fresh job\'s end; the maxima are the busiest worker\'s '
                           'totals; hits/(hits+misses) is the share of partner FFTs not recomputed; measure the coupling '
                           'phase with and without FRANKIE_SEARCH_FFT_CACHE_BYTES=0 on the one-day canary')
    # Symbolic discovery (stage 7 spec row): candidates from this day's couplings, per cell, in the same held workers
    discovered = discovery(day, cycle, day_role, staging, parts, context, workers, log)
    phase('discovery')
    pinned_parts = [p for p in sorted(parts) if Path(p).exists()]
    hashing_started = time.time()
    # Every part is read and hashed ONCE (stacks pass): the worker that wrote it hashed the fsynced bytes before the
    # rename (a resumed job re-hashed the file and compared it to that digest), and that digest is its pin; when
    # discovery read the part it hashed the same bytes and must agree (a disagreement is a hard error, both named).
    # A part with no recorded digest (none expected) is hashed here on pinned threads, listed.
    rehash = [p for p in pinned_parts if not PART_DIGESTS.get(p)]
    if rehash:
        with _lane_pin().executor('thread', max(1, min(workers, len(rehash))), lane_cpus()) as hashers:
            PART_DIGESTS.update(zip(rehash, hashers.map(sha256_file, rehash)))
    for p in pinned_parts:
        read = PART_READS.get(p)
        if read is not None and read[1] != PART_DIGESTS[p]:
            raise ValueError('coupling part bytes changed after its worker pinned them: %s (worker %s, discovery read %s)'
                             % (p, PART_DIGESTS[p], read[1]))
    part_pins = [dict(path=str(Path(p).relative_to(staging)), rows=None, sha256=PART_DIGESTS[p]) for p in pinned_parts]
    SOURCE_PASSES.append(dict(what='coupling part pins (sha256)', parts=len(pinned_parts),
                              kind='write-time digests of the jobs (one read per part); re-hashed here: %d; checked '
                                   'against the discovery read: %d' % (len(rehash), sum(1 for p in pinned_parts
                                                                                      if p in PART_READS)),
                              rehashed=rehash, seconds=round(time.time() - hashing_started, 3)))
    cell_specs = [(c, v, None) for c, v in cell_index]
    if sha256_file(day_dir / 'MANIFEST.json') != identity['data_manifest_sha256']:
        raise ValueError('selected export manifest changed before search publication')
    manifest = dict(schema=SCHEMA, day=day, cycle=cycle, day_role=day_role, at=time.time(), seconds=time.time() - started,
                    data=str(day_dir), data_manifest_sha256=identity['data_manifest_sha256'],
                    experiment_directive=directive_witness(),
                    sources=sources, notes=notes, leakage=gates, lags=lags,
                    series=names, cells=[(c, v) for c, v, _ in cell_specs],
                    transforms=dict(names=transform_names,
                                    pairs={t: [ty for ty in y_transforms(t) if ty in steps] for t in transform_names},
                                    module_sha256=sha256_file(Path(T.__file__)),
                                    unclassified_steps=unclassified),
                    couplings=dict(parts=part_pins, rows=count, beyond_chance=beyond, jobs=len(jobs), workers=workers),
                    cells_not_counted=sorted(not_counted, key=lambda d: (d['cell'], d['transform'], d['series'])),
                    not_searched=[dict(item=a, what=b) for a, b in NOT_SEARCHED],
                    planes=plane_summary(sources, notes), discovery=discovered,
                    rule='counts per pair, cell, lag and day; never pooled across days; never a coefficient or an average '
                         'as the finding (D37); a confirmation day runs only the frozen survivor list',
                    frozen_survivors=str(frozen) if frozen else None, model_calls=0,
                    phase_timings=phases, fft_cache=fft_cache, workers=workers, cpu_placement=cpu_placement)
    # The 99 through the search (FRANKIE_ALL99_COVERAGE_V1, piece 'search'): the plane receipt just built, a placed series
    # of an entry counted as arriving at every coupling pair; built and validated by the one registry module
    import frankie_box_all99_coverage as ALL99
    shared_source = next((s_ for s_ in sources if s_.get('source') == 'shared_market'), None)
    manifest['all99_coverage'] = ALL99.search_coverage(
        day, manifest_sha256=identity['data_manifest_sha256'], planes=manifest['planes'], sources=sources,
        outputs=dict(output_candidate_discoveries=dict(discovered['index'], what='discovery/INDEX.json and the coupling parts')),
        code_root=str(Path(__file__).resolve().parents[3]), shared_market=shared_source)
    manifest['all99_coverage']['manifest_basis'] = 'search_manifest_sha256 here is the export MANIFEST this search read'
    manifest['workflow_report'] = workflow_report(manifest, day_dir, identity, phase_timings=phases, fft_cache=fft_cache,
                                                  workers=workers)
    # the one-day review file (frankie_box_workflow_inspection reads it; the MANIFEST outgrows its metadata ceiling)
    review = dict(schema=WORKFLOW_REPORT_FILE_SCHEMA, day=day, cycle=cycle, day_role=day_role,
                  workflow_report=compact_report(manifest['workflow_report'], 'MANIFEST.json workflow_report'),
                  leakage_failed=[gate for gate in gates if gate.get('passed') is False],
                  cpu_placement=compact_report(cpu_placement, 'MANIFEST.json cpu_placement'),
                  rule='operator review only: the piece\'s own record with long lists named by count and exact MANIFEST '
                       'location; not knowledge, not evidence, not a gate')
    review_bytes = (json.dumps(review, indent=1, sort_keys=True) + '\n').encode()
    review_path = staging / 'workflow-report.json'
    with review_path.with_suffix('.json.pending').open('wb') as handle:
        handle.write(review_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(review_path.with_suffix('.json.pending'), review_path)
    manifest['workflow_report_file'] = dict(path='workflow-report.json', bytes=len(review_bytes),
                                            sha256=hashlib.sha256(review_bytes).hexdigest(),
                                            what='the one-day review file (compact workflow report)')
    manifest_path = staging / 'MANIFEST.json'
    with manifest_path.with_suffix('.json.pending').open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(manifest_path.with_suffix('.json.pending'), manifest_path)
    os.replace(staging, target)
    phase('publish')
    log('search: %d series x %d transforms (%d sources failed the leakage gate, listed), %d cells, %d pair rows, %d '
        'beyond chance (a count, not a finding by itself) in %.0f s; phases %s' % (
            len(names), len(transform_names), sum(1 for g in gates if g['passed'] is False), len(cell_specs), count,
            beyond, manifest['seconds'], json.dumps(phases, sort_keys=True)))
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
                          not_searched=m['not_searched'], phase_timings=m.get('phase_timings'),
                          fft_cache=m.get('fft_cache')), indent=1))


if __name__ == '__main__':
    main()
