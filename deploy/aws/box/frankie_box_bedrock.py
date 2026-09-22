"""Cycle 0's bedrock on the box (SPEC_CYCLE0_BEDROCK_20260921.md, box-bedrock-derive; Greg, 2026-09-21: "All 3").

The bedrock layers (derived_geometry 8, prebirth_opportunity 5, causal_clocks 7) are derived by the PINNED producers'
own traversal, `native_replay_driver.NativeReplayDriver` at lineage ccode/frankie-receiver-feed-20260916 commit 2ebb8ce8
(the checkout the box holds at /opt/frankie-box/producers; the in-repo worktree .producers-2ebb8ce8 for tests), built
with the canonical arguments `native_a_arm_launch.launch` names, and projected into layer files by the producers' own
`native_layer_crosswalk`. Nothing here computes a layer: this module stamps the records, runs the driver, files its
exact ledgers whole, and copies what the crosswalk names. Stdlib only; torch is never imported on this path.

Rules: nothing deleted (an earlier bedrock is moved aside with a receipt); every file written whole with a witness;
a zero-row layer says WHY (never an empty `derived`); the BOSS is not invoked inside the traversal (NeverInvoke).
"""
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

PIN_COMMIT = '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'
PIN_LINEAGE = 'ccode/frankie-receiver-feed-20260916'
V4_ADAPTER = 'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py'
V4_ADAPTER_MODULE = 'research.ng_exhaustion_mbo_v4_state_adapter_20260820'
# the launcher's identity inputs (native_a_arm_launch.MISSION_PATH / CONTRACT_PATH / KNOWLEDGE_MANIFEST_PATH); named here
# so the receipt can say which files were hashed even before the launcher is imported
MISSION_PATH = 'research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md'
CONTRACT_PATH = 'research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md'
KNOWLEDGE_MANIFEST_PATH = 'research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json'
LEDGER_FILES = ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl')
NS = 1_000_000_000


class NeverInvoke:
    """A declared CadencePolicy that never fires: the BOSS is invoked by the session's own stages (reading, classroom,
    teach, writing), never inside the traversal. The receipt records `cadence_policy: NeverInvoke`."""

    def should_invoke(self, **_kwargs):
        return False


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def witness(path):
    path = Path(path)
    return dict(bytes=path.stat().st_size, sha256=sha256_file(path))


class RowSpool(list):
    """Append-only, replayable rows on the AWS box; no row collection in RAM.

    Every row uses the journal's exact type-preserving codec. The file is retained
    with its derivation, including after failure; a new spool never overwrites one.
    The list interface lets the streaming JSON encoder preserve existing layer bytes.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = self.path.open('x', encoding='utf-8', newline='\n')
        self._count = 0
        self._ends = []

    def __len__(self):
        return self._count

    def append(self, value):
        from research.kalshi.frankie_boss.c15_journal import pack
        self._writer.write(json.dumps(pack(value), separators=(',', ':')) + '\n')
        self._count += 1
        if not self._ends:
            self._ends = [value, value]
        else:
            self._ends[1] = value

    def close(self):
        if not self._writer.closed:
            self._writer.close()

    def __iter__(self):
        from research.kalshi.frankie_boss.c15_journal import unpack
        if not self._writer.closed:
            self._writer.flush()
        seen = 0
        with self.path.open(encoding='utf-8') as handle:
            for line in handle:
                seen += 1
                yield unpack(json.loads(line))
        if seen != self._count:
            raise ValueError('retained row spool count changed')

    def __getitem__(self, key):
        from itertools import islice
        if isinstance(key, slice):
            start, stop, step = key.indices(self._count)
            if step < 1:
                raise ValueError('reverse spool slices are not supported')
            if stop <= start:
                return []
            if start == 0 and stop == 1:
                return self._ends[:1]
            if start == self._count - 1:
                return self._ends[-1:]
            return list(islice(iter(self), start, stop, step))
        index = key + self._count if key < 0 else key
        if not 0 <= index < self._count:
            raise IndexError(key)
        if index == 0:
            return self._ends[0]
        if index == self._count - 1:
            return self._ends[-1]
        return next(islice(iter(self), index, index + 1))

    def __del__(self):
        writer = getattr(self, '_writer', None)
        if writer is not None and not writer.closed:
            writer.close()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoder = json.JSONEncoder(indent=1, sort_keys=True, default=str)
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        for chunk in encoder.iterencode(value):
            handle.write(chunk)
        handle.write('\n')
    return dict(witness(path), path=str(path))

def producers_commit(producers):
    """The checkout's commit, measured (git rev-parse HEAD); refused unless it is the pin: the pinned bytes are the ones
    that must run, and a checkout at another commit is not the producers the crosswalk and the receipts name."""
    import subprocess
    try:
        head = subprocess.run(['git', '-C', str(producers), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f'the producers checkout at {producers} has no readable git HEAD: {error}')
    if head != PIN_COMMIT:
        raise ValueError(f'the producers checkout at {producers} is at {head}, not the pinned {PIN_COMMIT}')
    return head


def loaded_modules(producers, *modules):
    """The producer modules that actually loaded, each witnessed by its own __file__ and REQUIRED to live under the pinned
    checkout: a same-named module resolved from another tree would otherwise run while the receipt swore to the pin."""
    producers = Path(producers).resolve()
    out = {}
    for module in modules:
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(producers):
            raise ValueError(f'{module.__name__} loaded from {path}, not the pinned checkout {producers}')
        out[module.__name__.rsplit('.', 1)[-1]] = dict(path=str(path), **witness(path))
    return out


def default_producers():
    value = os.environ.get('FRANKIE_BOX_PRODUCERS')
    if value:
        return Path(value)
    root = os.environ.get('FRANKIE_BOX_ROOT')
    if root:
        return Path(root) / 'producers'
    return Path(__file__).resolve().parents[3] / f'.producers-{PIN_COMMIT[:8]}'


def load_producers(producers):
    """Make the pinned checkout importable: its path on sys.path AFTER whatever is already there (markets first, as the
    session orders it), and the V4 adapter registered from the PINNED file by path, as the session's _producer_module
    does, so `research.ng_exhaustion_mbo_v4_state_adapter_20260820` is the pinned bytes wherever it is imported from.
    Refuses a checkout whose adapter is already loaded from elsewhere."""
    import importlib.util
    producers = Path(producers).resolve()
    if not (producers / V4_ADAPTER).is_file():
        raise ValueError(f'producers checkout at {producers} lacks {V4_ADAPTER}')
    if str(producers) not in sys.path:
        sys.path.append(str(producers))
    # `research` and `research.kalshi` are namespace packages in both trees; a process that already holds them (or a
    # test that registered a stand-in with a fixed __path__) does not see the checkout's subpackage until its path is
    # on the package's __path__, so it is added there too, once.
    for name, sub in (('research', 'research'), ('research.kalshi', 'research/kalshi')):
        package = sys.modules.get(name)
        path = getattr(package, '__path__', None)
        if package is not None and path is not None and str(producers / sub) not in list(path):
            try:
                path.append(str(producers / sub))
            except AttributeError:
                package.__path__ = list(path) + [str(producers / sub)]
    loaded = sys.modules.get(V4_ADAPTER_MODULE)
    if loaded is None:
        spec = importlib.util.spec_from_file_location(V4_ADAPTER_MODULE, producers / V4_ADAPTER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[V4_ADAPTER_MODULE] = module
        spec.loader.exec_module(module)
    elif Path(getattr(loaded, '__file__', '') or '').resolve() != (producers / V4_ADAPTER).resolve():
        raise ValueError(f'{V4_ADAPTER_MODULE} is loaded from {getattr(loaded, "__file__", None)}, not the pinned {producers / V4_ADAPTER}')
    return producers


def source_object(container, day):
    """The driver's source object for the box's rows: `journal:<day>:<container path>`. The driver reads the source day
    as the first 20YYMMDD in the object name (native_replay_driver._source_day), so the session day leads and the
    verified prefix container path follows; the container's sha256 is the record's source_dbn_sha256."""
    path = (container or {}).get('path')
    sha = (container or {}).get('sha256')
    if not path or not sha:
        raise ValueError('the source object is required: the verified prefix container path and sha256')
    day = str(day or '')
    if not (len(day) == 8 and day.isdigit() and day.startswith('20')):
        raise ValueError(f'the source day must be 20YYMMDD, not {day!r}')
    return f'journal:{day}:{path}', str(sha)


def iter_driver_records(records, container, day):
    """The session's INPUT observations stamped for the driver: `source_dbn_object` = journal:<day>:<verified prefix
    container path>, `source_dbn_sha256` = the container's sha256 (the driver refuses a record without a source object;
    the box's source object IS the verified container), `raw_symbol` = the observation's own raw_symbol/symbol when
    present, else None. Copies; the input is left untouched."""
    path, sha = source_object(container, day)
    for record in records:
        stamped = dict(record)
        stamped['source_dbn_object'] = path
        stamped['source_dbn_sha256'] = str(sha)
        stamped['raw_symbol'] = record.get('raw_symbol') or record.get('symbol') or None
        yield stamped


def driver_records(records, container, day):
    return list(iter_driver_records(records, container, day))


def span_seconds(records):
    """The receive-clock span of the rows, in seconds (ts_recv ns on the wire record; ts_recv_ns on a normalized one)."""
    low = high = None
    for row in records:
        value = row.get('ts_recv') if row.get('ts_recv') is not None else row.get('ts_recv_ns')
        if value is not None:
            value = int(value)
            low = value if low is None else min(low, value)
            high = value if high is None else max(high, value)
    return 0.0 if low is None else (high - low) / NS


def identity(producers, container, count, cycle, code_commit):
    from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import RunIdentity
    producers = Path(producers)
    knowledge = json.loads((producers / KNOWLEDGE_MANIFEST_PATH).read_bytes())
    return RunIdentity(run_id=f'frankie-box-cycle-{cycle}', arm='A_MEMORY',
                       mission_sha256=sha256_file(producers / MISSION_PATH),
                       calculation_contract_sha256=sha256_file(producers / CONTRACT_PATH),
                       knowledge_manifest_hash=knowledge['manifest_hash'],
                       source_manifest_hash=str(container['sha256']),
                       total_mbo_records=int(count), code_commit=str(code_commit))


def _move_aside(out_dir, siblings=(), schema='FRANKIE_BOX_BEDROCK_SUPERSEDE_RECEIPT_V1',
                reason='the bedrock is derived again (a pin change, a schema change or an operator restart); the earlier files are kept whole'):
    """An earlier bedrock under out_dir is moved beside it, receipted; nothing is deleted. `siblings` are files beside the
    directory that belong to the same derivation (its receipt, digest, measurement): they move INTO the superseded directory
    under their own names, so nothing writes over them either. The receipt's stamp is taken where neither the directory nor
    the receipt exists."""
    out_dir = Path(out_dir)
    present = out_dir.exists() and any(out_dir.iterdir())
    files = [Path(s) for s in siblings if Path(s).is_file()]
    if not present and not files:
        return None
    stamp = int(time.time())
    target = out_dir.with_name(f'{out_dir.name}-superseded-{stamp}')
    receipt = out_dir.with_name(f'{out_dir.name}-supersede-{stamp}.json')
    while target.exists() or receipt.exists():
        stamp += 1
        target = out_dir.with_name(f'{out_dir.name}-superseded-{stamp}')
        receipt = out_dir.with_name(f'{out_dir.name}-supersede-{stamp}.json')
    if present:
        out_dir.rename(target)
    else:
        target.mkdir(parents=True)
    moved_files = []
    for f in files:
        f.rename(target / f.name)
        moved_files.append(str(target / f.name))
    write_json(receipt, dict(schema=schema, at=time.time(), moved_from=str(out_dir), moved_to=str(target), moved_files=moved_files, reason=reason))
    return str(target)


def run(records, container, out_dir, producers, cycle, code_commit, day):
    """The pinned traversal on this cycle's rows: identity -> NativeCalculationRun (the launcher's canonical arguments) ->
    NativeReplayDriver(ExchangeSessionRule, NeverInvoke, LedgerSinks) -> consume -> finalize -> reconcile (a mismatch
    raises: a ledger that does not match its counter is not evidence). Files result.json (the exact rows live in the
    ledgers) and receipt.json under out_dir; returns the receipt."""
    if not hasattr(records, '__len__'):
        raise ValueError('bedrock input must be counted and replayable before traversal')
    if not records:
        raise ValueError('no INPUT records; nothing to derive')
    producers = load_producers(producers)
    from research.kalshi.frankie_raw_mbo_benchmark import native_calculation_runner, native_replay_driver, native_response, native_row_sink
    from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import NativeCalculationRun, canonical_hash
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import ExchangeSessionRule, NativeReplayDriver
    from research.kalshi.frankie_raw_mbo_benchmark.native_response import (
        FLOW_RESPONSE, FULL_BOOK_RESPONSE, PRICE_RESPONSE, QUEUE_RESPONSE, horizons_for_version)
    from research.kalshi.frankie_raw_mbo_benchmark.native_row_sink import LedgerSinks
    modules = loaded_modules(producers, native_replay_driver, native_calculation_runner, native_row_sink, native_response)
    out_dir = Path(out_dir)
    superseded = _move_aside(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamped = iter_driver_records(records, container, day)
    ident = identity(producers, container, len(records), cycle, code_commit)
    sinks = LedgerSinks(out_dir / 'ledgers')
    # the launcher's canonical arguments (native_a_arm_launch.launch): 60 s replenishment horizon, the a-arm-h2 horizons,
    # the four response values the contract's inputs reach, companion keys unaliased
    arguments = dict(replenishment_horizon_ns=60 * NS, response_horizon_version='a-arm-h2',
                     response_horizons_ns=list(horizons_for_version('a-arm-h2')),
                     response_value_names=[PRICE_RESPONSE, FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE],
                     alias_companion_keys=False, emit_change_points=True, session_rule='ExchangeSessionRule')
    calculation = NativeCalculationRun(ident, sinks=sinks, alias_companion_keys=False,
                                       replenishment_horizon_ns=arguments['replenishment_horizon_ns'],
                                       response_horizons_ns=tuple(arguments['response_horizons_ns']),
                                       response_horizon_version=arguments['response_horizon_version'],
                                       response_value_names=tuple(arguments['response_value_names']))
    driver = NativeReplayDriver(identity=ident, session_rule=ExchangeSessionRule(), cadence=NeverInvoke(), run=calculation,
                                sinks=sinks, emit_change_points=True)
    started = time.time()
    driver.consume(stamped)
    result = driver.finalize()
    result['ledger_retention'] = sinks.reconcile_all(member=calculation.member_rows_written,
                                                     lifecycle=calculation.lifecycle_rows_written,
                                                     legacy=driver.counters.legacy_rows_retained)
    # THE RESULT HASHES TO ITSELF AS WRITTEN (the launcher's F-feed-6): finalize() hashed the result before the
    # reconciliation was added, so the runner's hash keeps its own name and the declared hash is recomputed last
    result['runner_result_hash'] = result.pop('result_hash')
    result['result_hash'] = canonical_hash(result)
    result_witness = write_json(out_dir / 'result.json', result)
    ledgers = {}
    for name in LEDGER_FILES:
        path = out_dir / 'ledgers' / name
        with open(path, 'rb') as handle:
            rows = sum(1 for _ in handle)
        ledgers[name] = dict(witness(path), path=str(path), rows=rows)
    receipt = dict(schema='FRANKIE_BOX_BEDROCK_RUN_RECEIPT_V1', at=time.time(), cycle=str(cycle), seconds=round(time.time() - started, 3),
                   producers=str(producers), producers_commit=str(code_commit), producers_lineage=PIN_LINEAGE,
                   driver=modules['native_replay_driver'], modules=modules,     # the modules that actually RAN, by their own __file__
                   launcher_differences=['no PeriodicCheckpointer / seal_start (no save points; the launcher writes them for the day run)',
                                         'no stage_spawn (moot under NeverInvoke)',
                                         'the launcher\'s three pre-traversal gates (registry identity, pre-call layer receipt, RT surface '
                                         'inventory) are not run, so result.json carries no gates/evidence_identity/slice of its own',
                                         'result_hash recomputed after ledger_retention, as the launcher does (runner_result_hash kept)'],
                   identity=asdict(ident), identity_inputs=dict(mission=MISSION_PATH, contract=CONTRACT_PATH, knowledge_manifest=KNOWLEDGE_MANIFEST_PATH),
                   cadence_policy='NeverInvoke', driver_arguments=arguments,
                   candidate_warmup_seconds=driver.candidate_warmup_seconds, candidate_min_observations=driver.candidate_min_observations,
                   candidate_selection=driver.candidate_selection,
                   source_object=dict(object=source_object(container, day)[0], container=str(container['path']), sha256=str(container['sha256']), day=str(day),
                                      rule='journal:<day>:<verified prefix container path>; the driver reads the source day as the first 20YYMMDD in the object name'),
                   records=len(records), groups=result['traversal']['groups_seen'], span_seconds=span_seconds(records),
                   verdict=result.get('verdict'), failed_gates=result.get('failed_gates'),
                   sections_fed=result['traversal']['sections_fed'], reconciliation=result['ledger_retention'],
                   ledgers=ledgers, result=result_witness, superseded=superseded)
    write_json(out_dir / 'receipt.json', receipt)
    return receipt


# ---- BR-3: the projection by the producers' own crosswalk ------------------------------------------------------------

GROUP_KEY = ('group_index', 'ts_recv_ns', 'f_last_ts_recv_ns')


def status_of(count, section_dependent, span_seconds, warmup_seconds, min_observations):
    """`derived` when rows exist; otherwise `could_not` with the measured reason, never an empty `derived`."""
    if count:
        return 'derived', None
    if section_dependent:
        return 'could_not', (f'the candidate lane needs {warmup_seconds} s of warmup and {min_observations} observations '
                             f'before any candidate can be detected; this cycle\'s rows span {span_seconds:.1f} s')
    return 'could_not', 'the traversal emitted no rows for this carrier on this cycle\'s rows'


def select_path(value, path):
    """Walk a crosswalk member path: dotted keys, `*` = every key of a mapping (a mapping of the selections), `name[]` =
    every element of a list (a list of the selections). Returns (found, selection); absent anywhere = (False, None)."""
    segments = [s for s in path.split('.') if s]
    return _select(value, segments)


def _select(value, segments):
    if not segments:
        return True, value
    head, rest = segments[0], segments[1:]
    if head.endswith('[]'):
        found, items = _select(value, [head[:-2]]) if head[:-2] else (True, value)
        if not found or not isinstance(items, list):
            return False, None
        out = []
        for item in items:
            ok, picked = _select(item, rest)
            if not ok:
                return False, None
            out.append(picked)
        return True, out
    if head == '*':
        if not isinstance(value, dict):
            return False, None
        out = {}
        for key, item in value.items():
            ok, picked = _select(item, rest)
            if ok:
                out[key] = picked
        return (True, out) if out or not value else (False, None)
    if not isinstance(value, dict) or head not in value:
        return False, None
    return _select(value[head], rest)


def crosswalk_records(producers, layers):
    """The pinned crosswalk's record for each layer (native_layer_crosswalk.LAYER_PRODUCERS at the checkout): module,
    symbol, file, line, kind, carrier, member_paths, lifecycle_sections, fixture_dependent_sections, notes. Never
    restated here; a layer the crosswalk does not name is refused."""
    producers = load_producers(producers)
    from research.kalshi.frankie_raw_mbo_benchmark import native_layer_crosswalk as X
    loaded_modules(producers, X)
    out = {}
    for layer in layers:
        record = X.LAYER_PRODUCERS.get(layer)
        if record is None:
            raise ValueError(f'{layer} is not in the pinned crosswalk (native_layer_crosswalk.LAYER_PRODUCERS)')
        out[layer] = json.loads(json.dumps(record, default=list))
    return out


# ---- BR-9: sections 4.2 and 4.4 as files beside the crosswalk layers (SPEC-bedrock-section-tables.md) -----------------
# The two pieces Greg found dropped (03:2xZ 09-22): 4.2, the daily book regime companion, and 4.4, the mirror matcher.
# Both RUN at the pin (native_calculation_runner.sections registers them); the crosswalk names no layer for 4.2's companion
# rows and none whose lifecycle section is `mirror`, so project() never filed them. These two files copy the traversal's own
# numbers whole (result.json's averaged_companions rows and section summaries; the exact lifecycle ledger's `mirror` rows);
# nothing is computed here. The file shape is project()'s so bedrock.layers indexes them and status_of names a zero-row reason.
BRG = 'research/kalshi/frankie_raw_mbo_benchmark/native_book_regime.py'
MIR = 'research/kalshi/frankie_raw_mbo_benchmark/native_mirror.py'
SECTION_FILES = {
    'bedrock_section_4_2': dict(section='4.2', kind='SECTION_COMPANION', producer='native_book_regime.BookRegimeCalculator', file=BRG, line=66,
                                carrier="averaged_companions.rows[section=4.2] (one row per measure per stratum: the per-day book regime companion); "
                                        "section_summaries['4.2'].first_last_pairs (the exact first and last book of each day-segment-phase)",
                                lifecycle_sections=[]),
    'bedrock_section_4_4': dict(section='4.4', kind='SECTION_LIFECYCLE', producer='native_mirror.MirrorMatcher', file=MIR, line=270,
                                carrier="exact_lifecycle_rows.jsonl[emitting_section=mirror] (every offer at GROUP_CLOSE and every finalize row at "
                                        "STREAM_END, whole); section_summaries['4.4'].matching_rule (the rule the pairs were formed under)",
                                lifecycle_sections=['mirror']),
}


def project_sections(receipt, result_path, ledgers_dir, out_dir):
    """One file per dropped section from the traversal's own result.json and exact lifecycle ledger, copied whole. Returns
    {name: status, producer, reason, count, witness} like project(). The averages layer must be unaliased (the run passes
    alias_companion_keys=False); an aliased layer is refused rather than read through a legend."""
    ledgers_dir, out_dir = Path(ledgers_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = json.loads(Path(result_path).read_bytes())
    layers = result['layers']
    averages = layers['averaged_companions']
    if averages.get('key_alias_form') != 'PLAIN':
        raise ValueError(f"the averaged_companions layer is {averages.get('key_alias_form')!r}, not PLAIN: an alias form is not read here")
    summaries = layers['exact_lifecycle_and_runway_ledger']['section_summaries']
    span = float(receipt.get('span_seconds') or 0.0)
    warmup, minimum = receipt.get('candidate_warmup_seconds'), receipt.get('candidate_min_observations')
    traversal = dict(verdict=receipt.get('verdict'), failed_gates=list(receipt.get('failed_gates') or []), groups=receipt.get('groups'),
                     records=receipt.get('records'), span_seconds=span, candidate_warmup_seconds=warmup, candidate_min_observations=minimum)
    mirror_rows = RowSpool(out_dir / '.rows' / 'section-mirror.jsonl')
    for row in _rows(ledgers_dir / 'exact_lifecycle_rows.jsonl'):
        if row.get('emitting_section') == 'mirror':
            mirror_rows.append(row)
    mirror_rows.close()
    out = {}
    for name, spec in SECTION_FILES.items():
        section = spec['section']
        summary = summaries.get(section)
        entry = dict(layer=name, section=section, kind=spec['kind'], producer=spec['producer'], file=spec['file'], line=spec['line'],
                     carrier=spec['carrier'], member_paths=[], lifecycle_sections=list(spec['lifecycle_sections']), fixture_dependent_sections=[],
                     crosswalk_commit=PIN_COMMIT, traversal=traversal, member_rows=[], lifecycle_rows=[], companion_rows=[],
                     first_last_pairs=[], declarations=[], matching_rule=None, summary=summary, section_counts={}, absent_paths={})
        if section == '4.2':
            rows = [r for r in averages['rows'] if r.get('section') == section]
            entry['companion_rows'] = rows
            entry['first_last_pairs'] = list((summary or {}).get('first_last_pairs') or [])
            declarations = {}
            for r in rows:
                declared = dict(measure=r['measure'], kind=r.get('kind'), **(r.get('declaration') or {}))
                if r['measure'] in declarations and declarations[r['measure']] != declared:
                    raise ValueError(f"section 4.2 measure {r['measure']} carries two different declarations")
                declarations[r['measure']] = declared
            entry['declarations'] = [declarations[m] for m in sorted(declarations)]
            entry['count'] = len(rows) + len(entry['first_last_pairs'])
        else:
            entry['lifecycle_rows'] = mirror_rows
            entry['section_counts'] = dict(mirror=len(mirror_rows))
            entry['matching_rule'] = (summary or {}).get('matching_rule')
            entry['count'] = len(mirror_rows)
        entry['member_count'], entry['lifecycle_count'] = 0, len(entry['lifecycle_rows'])
        entry['status'], entry['reason'] = status_of(entry['count'], False, span, warmup, minimum)
        entry['partial'] = []
        w = write_json(out_dir / f'{name}.json', entry)
        out[name] = dict(status=entry['status'], producer=entry['producer'], reason=entry['reason'], count=entry['count'],
                         member_count=0, lifecycle_count=entry['lifecycle_count'], partial=[], carrier=entry['carrier'], **w)
    return out


def _rows(path):
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def project(receipt, ledgers_dir, layers, crosswalk, out_dir):
    """One file per layer from the exact ledgers, by the crosswalk record: member rows projected to the named
    member_paths beside the group key; lifecycle rows of the named sections, whole. One pass over each ledger.
    Status by status_of on the count; a mixed layer whose candidate-carried sections stayed empty is `derived` with
    `partial` naming those sections and the measured reason. Returns {layer: status, producer, reason, count, witness}."""
    ledgers_dir, out_dir = Path(ledgers_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    span = float(receipt.get('span_seconds') or 0.0)
    warmup = receipt.get('candidate_warmup_seconds')
    minimum = receipt.get('candidate_min_observations')
    traversal = dict(verdict=receipt.get('verdict'), failed_gates=list(receipt.get('failed_gates') or []), groups=receipt.get('groups'),
                     records=receipt.get('records'), span_seconds=span, candidate_warmup_seconds=warmup, candidate_min_observations=minimum)
    files = {}
    for layer in layers:
        record = crosswalk[layer]
        files[layer] = dict(layer=layer, kind=record.get('kind'), producer=(f"{record['module']}.{record['symbol']}" if record.get('module') else None),
                            file=record.get('file'), line=record.get('line'), carrier=record.get('carrier'),
                            member_paths=list(record.get('member_paths') or []), lifecycle_sections=list(record.get('lifecycle_sections') or []),
                            fixture_dependent_sections=list(record.get('fixture_dependent_sections') or []), ledgers=list(record.get('ledgers') or []),
                            notes=record.get('notes'), crosswalk_commit=PIN_COMMIT, traversal=traversal,
                            member_rows=RowSpool(out_dir / '.rows' / (layer + '-members.jsonl')),
                            lifecycle_rows=RowSpool(out_dir / '.rows' / (layer + '-lifecycle.jsonl')),
                            section_counts={s: 0 for s in (record.get('lifecycle_sections') or [])}, absent_paths={})
    member_layers = [l for l in layers if files[l]['member_paths']]
    if member_layers:
        for row in _rows(ledgers_dir / 'exact_member_rows.jsonl'):
            key = dict(group_index=row.get('group_index'), ts_recv_ns=row.get('ts_recv_ns'),
                       f_last_ts_recv_ns=(row.get('clocks') or {}).get('f_last_ts_recv_ns'))
            for layer in member_layers:
                projected = dict(key)
                for path in files[layer]['member_paths']:
                    found, value = select_path(row, path)
                    if found:
                        projected[path] = value
                    else:
                        files[layer]['absent_paths'][path] = files[layer]['absent_paths'].get(path, 0) + 1
                files[layer]['member_rows'].append(projected)
    section_layers = {}
    for layer in layers:
        for section in files[layer]['lifecycle_sections']:
            section_layers.setdefault(section, []).append(layer)
    if section_layers:
        for row in _rows(ledgers_dir / 'exact_lifecycle_rows.jsonl'):
            section = row.get('emitting_section')
            for layer in section_layers.get(section, ()):
                files[layer]['lifecycle_rows'].append(row)
                files[layer]['section_counts'][section] += 1
    result = {}
    for layer in layers:
        entry = files[layer]
        entry['member_rows'].close()
        entry['lifecycle_rows'].close()
        entry['member_count'] = len(entry['member_rows'])
        entry['lifecycle_count'] = len(entry['lifecycle_rows'])
        entry['count'] = entry['member_count'] + entry['lifecycle_count']
        if entry['kind'] == 'NO_PRODUCER_FOUND':
            entry['status'], entry['reason'] = 'could_not', 'NO_PRODUCER_FOUND: ' + str(entry.get('notes') or 'the crosswalk found no producer')
        else:
            dependent = bool(entry['fixture_dependent_sections'])
            entry['status'], entry['reason'] = status_of(entry['count'], dependent, span, warmup, minimum)
        entry['partial'] = [dict(section=section, rows=0, reason=status_of(0, True, span, warmup, minimum)[1])
                            for section in entry['fixture_dependent_sections']
                            if entry['status'] == 'derived' and entry['section_counts'].get(section, 0) == 0]
        path = out_dir / f'{layer}.json'
        w = write_json(path, entry)
        result[layer] = dict(status=entry['status'], producer=entry['producer'], reason=entry['reason'], count=entry['count'],
                             member_count=entry['member_count'], lifecycle_count=entry['lifecycle_count'], partial=entry['partial'],
                             carrier=entry['carrier'], **w)
    return result
