"""Owner-local native evidence selection and exact F_LAST placement, without a replay.

The authoritative ledgers are read once. Existing compressed section products remain
completed-knowledge evidence; they are not repeated observations or early live features.
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_NATIVE_SEARCH_INPUTS_V1'
EMISSION_SCHEMA = 'FRANKIE_NATIVE_EMISSION_V1'
LEDGERS = ('exact_member_rows.jsonl', 'exact_lifecycle_rows.jsonl', 'legacy_observable_rows.jsonl')
SECTIONS = ('bedrock_section_4_2', 'bedrock_section_4_4')


def evidence_contract(role):
    """Describe existing evidence roles; this does not admit a new consumer."""
    common = dict(schema='FRANKIE_NATIVE_EVIDENCE_ROLE_V1', role=role,
                  artifact_identity=['sha256', 'bytes'], additional_independent_observation=False)
    if role in LEDGERS[:2]:
        return dict(common, representation='exact_ordered_ledger_rows',
                    row_identity=['artifact_sha256', 'zero_based_ledger_ordinal'],
                    group_join=['input_cursor', 'instrument_id', 'ts_recv_ns'],
                    availability='GROUP_CLOSE at checked emission time; FINALIZE is post-stream knowledge only',
                    entity_identity='original row identities retained; section/list slots are not entity trajectories',
                    consumer='existing exact ROOT F_LAST placement; per-row dispositions state actual use')
    if role == LEDGERS[2]:
        return dict(common, representation='exact_ordered_ledger_rows',
                    row_identity=['artifact_sha256', 'zero_based_ledger_ordinal'],
                    availability='original row clocks retained; no new live placement',
                    consumer='retained source alias; not an additional live search observation')
    if role in ('receipt', 'result', *SECTIONS):
        return dict(common, representation=('completion_receipt' if role == 'receipt'
                                           else 'completed_calculation_product'),
                    availability='completed calculation; no whole-day backfill onto earlier live groups',
                    consumer='retained metadata or completed evidence; no new scientific consumer supplied')
    raise ValueError('unknown native evidence role')


def _witness(path):
    from frankie_box_durable import witness
    return witness(path)


def _check(path, pin):
    if _witness(path) != {k: pin[k] for k in ('bytes', 'sha256')}:
        raise ValueError('selected native evidence changed: ' + str(path))


def selected_files(root, day):
    """Only completed, source-bound scientific artifacts, never checkpoints/staging."""
    root = Path(root).resolve()
    binding_path, calculation_path = root / 'source-binding.json', root / 'calculations-receipt.json'
    if not binding_path.is_file():
        return []
    binding = json.loads(binding_path.read_bytes())
    policy = binding.get('native_calculation_policy') or {}
    if policy.get('bedrock') is not True:
        return []
    if not calculation_path.is_file():
        raise ValueError('selected native ROOT has no completed calculation receipt')
    calculation = json.loads(calculation_path.read_bytes())
    if (str(calculation.get('day')) != str(day)
            or calculation.get('native_calculation_policy') != policy
            or calculation.get('status') not in ('calculations_retained', 'calculations_retained_with_failures')):
        raise ValueError('selected native ROOT completion or source policy differs')
    _check(binding_path, calculation['source_binding'])
    derive_path = root / 'work' / 'derive.json'
    _check(derive_path, calculation['derivation'])
    derive = json.loads(derive_path.read_bytes())
    if derive.get('source_binding') != binding:
        raise ValueError('native derivation belongs to another source binding')
    native = derive.get('bedrock') or {}
    if native.get('skipped') or not native.get('result') or set(native.get('ledgers') or {}) != set(LEDGERS):
        raise ValueError('native derivation lacks its completed authoritative ledgers')
    selected = []

    def take(role, pin, name, directory):
        path = Path(pin['path'])
        if (not path.is_absolute() or '..' in path.parts
                or any(p.is_symlink() for p in (path, *path.parents))):
            raise ValueError('native artifact path is not a regular owner-local path')
        relative = path.relative_to(root)
        if path.name != name or not relative.is_relative_to(directory):
            raise ValueError('native artifact is outside its selected scientific directory')
        _check(path, pin)
        selected.append(dict(stage='root', path=str(relative), source=str(path),
            pattern='completed native derivation:' + role, what='existing exact native calculation evidence',
            native_role=role, evidence_contract=evidence_contract(role),
            expected={k: pin[k] for k in ('bytes', 'sha256')}))

    take('receipt', native['receipt'], 'receipt.json', 'work/bedrock')
    take('result', native['result'], 'result.json', 'work/bedrock')
    run = json.loads(Path(native['receipt']['path']).read_bytes())
    if run.get('result') != native['result'] or run.get('ledgers') != native['ledgers']:
        raise ValueError('native completion and derivation disagree on scientific artifacts')
    if run.get('emission') != native.get('emission') or native.get('emission') != policy.get('emission'):
        raise ValueError('native emission implementation is not bound by the selected source policy')
    for name in LEDGERS:
        take(name, native['ledgers'][name], name, 'work/bedrock')
    for name in SECTIONS:
        entry = derive['layers'].get(name)
        if not entry or not entry.get('bedrock') or entry.get('encoding') != 'gzip-json':
            raise ValueError('native derivation lacks its exact compressed section product: ' + name)
        take(name, entry, name + '.json.gz', 'work/derived/.projection-v2')
    return selected


def _ranges_add(ranges, ordinal):
    if ranges and ranges[-1][1] + 1 == ordinal:
        ranges[-1][1] = ordinal
    else:
        ranges.append([ordinal, ordinal])


def read_columns(day_dir, columns, frame_numeric, receive_times):
    """Return native numeric/text columns on the unchanged ROOT frame axis and receipts.

    Lifecycle slots retain emission order within each section/group. A slot is not
    a persistent entity track. All entity identifiers and row fields remain present.
    Unplaced/post-stream rows stay in their hash-bound original ledger, with exact
    ordinal ranges reported; none are silently assigned an earlier timestamp.
    """
    day_dir = Path(day_dir)
    manifest = json.loads((day_dir / 'MANIFEST.json').read_bytes())
    selected = {}
    for item in manifest['files']:
        if item.get('native_role'):
            role = item['native_role']
            if role in selected or item['stage'] != 'root':
                raise ValueError('duplicate or non-ROOT native export role')
            # Older exports have no role descriptor. Keep their existing read
            # path; a supplied descriptor must describe this same interpretation.
            if ('evidence_contract' in item
                    and item['evidence_contract'] != evidence_contract(role)):
                raise ValueError('native export evidence role contract differs')
            path = Path(item['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('native export path escapes the owning export')
            selected[role] = (day_dir / 'root' / path, item)
    if not selected:
        return {}, {}, [], [dict(source='native', reason='no selected completed native evidence in this export')]
    required = {'receipt', 'result', *LEDGERS, *SECTIONS}
    if set(selected) != required:
        raise ValueError('native export has an incomplete or unknown artifact set')
    n = len(receive_times)
    cursors = frame_numeric.get('input_cursor')
    instruments = frame_numeric.get('native_frame.instrument_id')
    index = {}
    if cursors is not None and instruments is not None:
        for position, (cursor, instrument, stamp) in enumerate(zip(cursors, instruments, receive_times)):
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (cursor, instrument)):
                raise ValueError('ROOT frame identity is not exact integer provenance')
            key = (cursor, instrument, int(stamp))
            if key in index:
                raise ValueError('ROOT frame provenance is duplicated')
            index[key] = position
    members = {}
    numeric, text, sources, notes = {}, {}, [], []

    def load(ledger, source):
        path, pin = selected[ledger]
        report = dict(source=source, schema=SCHEMA, path=str(path), sha256=pin['sha256'],
            bytes=pin['bytes'], rows=0, searched_rows=0, dispositions={}, sections={},
            evidence_contract=evidence_contract(ledger),
            export_contract_present='evidence_contract' in pin,
            placement='exact emitting INPUT cursor + instrument + receive time on existing F_LAST axis',
            entity_rule='all identities retained; section/list positions are not identity-linked trajectories')
        sources.append(report)

        def disposition(reason, ordinal, row):
            target = report['dispositions'].setdefault(reason, dict(rows=0, ordinal_ranges=[]))
            target['rows'] += 1
            _ranges_add(target['ordinal_ranges'], ordinal)
            section = str(row.get('emitting_section') or 'member')
            counts = report['sections'].setdefault(section, {})
            counts[reason] = counts.get(reason, 0) + 1

        def rows():
            hashed, size, previous = hashlib.sha256(), 0, -1
            with path.open('rb') as handle:
                for ordinal, raw in enumerate(handle):
                    hashed.update(raw)
                    size += len(raw)
                    row = json.loads(raw)
                    if not isinstance(row, dict):
                        raise ValueError('native ledger row is not an object')
                    report['rows'] += 1
                    provenance = row.get('frankie_emission')
                    if not isinstance(provenance, dict) or provenance.get('schema') != EMISSION_SCHEMA:
                        disposition('unsupported_emission_provenance', ordinal, row)
                        continue
                    phase = provenance.get('phase')
                    if phase == 'FINALIZE':
                        if (provenance.get('group_index') is not None
                                or provenance.get('instrument_id') is not None):
                            raise ValueError('finalization falsely names a live group')
                        if row.get('emitted_at_recv_ns') != provenance.get('ts_recv_ns'):
                            raise ValueError('finalization row and emission clocks disagree')
                        disposition('post_stream_knowledge_only', ordinal, row)
                        continue
                    if phase != 'GROUP_CLOSE':
                        disposition('unsupported_emission_phase', ordinal, row)
                        continue
                    values = [provenance.get(k) for k in ('group_index', 'input_cursor', 'instrument_id', 'ts_recv_ns')]
                    if any(isinstance(v, bool) or not isinstance(v, int) for v in values) or min(values[:2]) < 0:
                        raise ValueError('native emission provenance is not exact integer identity')
                    group, cursor, instrument, stamp = values
                    key = (cursor, instrument, stamp)
                    if ledger == LEDGERS[0]:
                        if (group != ordinal or row.get('group_index') != group
                                or row.get('instrument_id') != instrument or row.get('ts_recv_ns') != stamp
                                or (row.get('clocks') or {}).get('first_lawful_availability_ns') != stamp):
                            raise ValueError('native member and emission identities disagree')
                        members[group] = key
                    elif members.get(group) != key:
                        raise ValueError('native lifecycle emission does not name its exact member')
                    elif row.get('emitted_at_recv_ns') != stamp:
                        raise ValueError('native lifecycle availability and emission clocks disagree')
                    position = index.get(key)
                    if position is None:
                        disposition('no_matching_root_frame', ordinal, row)
                        continue
                    if position < previous:
                        raise ValueError('native emission order moves backwards on the ROOT axis')
                    previous = position
                    disposition('searched', ordinal, row)
                    report['searched_rows'] += 1
                    yield position, row
            if size != pin['bytes'] or hashed.hexdigest() != pin['sha256']:
                raise ValueError('native exported ledger changed during its single read')

        def aligned():
            iterator = iter(rows())
            pending = next(iterator, None)
            for position in range(n):
                bucket = {}
                while pending is not None and pending[0] == position:
                    row = pending[1]
                    if ledger == LEDGERS[0]:
                        if bucket:
                            raise ValueError('two native members claim one ROOT frame')
                        bucket = {'row': row}
                    else:
                        bucket.setdefault(str(row['emitting_section']), []).append(row)
                    pending = next(iterator, None)
                yield bucket
            if pending is not None:
                raise ValueError('native row placement is outside the ROOT frame axis')

        nums, strings, mixed, count = columns(aligned(), '')
        if count != n:
            raise ValueError('native reader changed the ROOT axis length')
        # columns preserves an empty mapping as a categorical leaf. Here the
        # empty outer mapping is only our absent-group placeholder, not a native
        # observation. Original member fields are nested under row; lifecycle
        # rows under their section, so no original field is removed here.
        nums.pop('', None)
        strings.pop('', None)
        numeric.update({source + '.' + k: v for k, v in nums.items()})
        text.update({source + '.' + k: v for k, v in strings.items()})
        report.update(numeric=sorted(nums), text=sorted(strings), mixed=mixed)

    load(LEDGERS[0], 'native.member')
    load(LEDGERS[1], 'native.lifecycle')
    for role in ('result', 'receipt', LEDGERS[2], *SECTIONS):
        path, item = selected[role]
        notes.append(dict(source='native', retained=str(path), sha256=item['sha256'], bytes=item['bytes'],
            role=role, disposition='retained_not_live_search',
            evidence_contract=evidence_contract(role),
            export_contract_present='evidence_contract' in item,
            reason=('legacy row evidence aliases the shared source; no duplicate observation' if role == LEDGERS[2]
                    else 'completed calculation/section evidence; no whole-day summary backfill or duplicate projected rows')))
    return numeric, text, sources, notes
