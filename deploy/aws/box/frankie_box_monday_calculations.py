"""Run the existing complete producer stages on the independently sealed Monday source.

This is the missing pre-request calculation entry, not a controller or ingestion
route. It retains actual results for the existing principal/host/session to use.
"""
import argparse
import copy
import json
import fcntl
import sqlite3
import time
import uuid
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import read_pin, require_checkout, save_new, witness, safe_path
from frankie_box_author_monday_launch import fresh, sync_directory

PARENT = Path('/opt/frankie-box/work/monday-calculations')


def load_retained_layers(session):
    """The completed legacy layers and spools as ROOT retained them; no journal read, no recalculation. Shared by
    resume_legacy and the render-only step (frankie_box_render_digest.py)."""
    from frankie_box_digest_sources import _JSON
    import frankie_box_bedrock as B
    pin = session._pin()
    derived = session.work / 'derived'
    candidates = list((derived / '.rows').glob('input-*.jsonl'))
    if len(candidates) != 1:
        raise ValueError('one retained complete INPUT spool required')
    records = B.RowSpool.reopen(candidates[0])
    if len(records) != session.source_binding['record_count']:
        raise ValueError('retained INPUT spool count differs')
    prices, frames, structures, failures = [B.RowSpool.reopen(derived / '.rows' / (n + '.jsonl'))
                                            for n in ('prices', 'frames', 'structures', 'failures')]
    if len(failures):
        raise ValueError('retained legacy stage has failures; cannot certify complete reuse')
    names = list(dict.fromkeys(['legacy_price', 'legacy_native_signed_flow', 'legacy_per_second_roll20',
        'legacy_book_imbalance', 'legacy_structure_observables'] + list(pin['registry_layers'])))
    layers, entries = {}, {}
    for name in names:
        path = derived / (name + '.json')
        value = {}
        with path.open(encoding='utf-8') as stream:
            parser = _JSON(stream)
            parser.expect('{')
            while parser.peek() != '}':
                key = parser.value()
                parser.expect(':')
                if key in ('frames', 'groups'):
                    count = sum(1 for _ in parser.array())
                    spool = frames if key == 'frames' else structures
                    if count != len(spool):
                        raise ValueError('retained legacy layer and spool counts differ')
                    value[key] = spool
                else:
                    value[key] = parser.value()
                if parser.peek() == '}':
                    break
                parser.expect(',')
            parser.expect('}')
            if parser.peek():
                raise ValueError('trailing legacy layer bytes')
        session.note('reusing retained legacy layer ' + name)
        layers[name] = value
        entries[name] = dict(status=value['status'], producer=value.get('producer'),
                            reason=value.get('reason'), **witness(path))
    return pin, derived, records, prices, frames, structures, failures, layers, entries


def write_retained_digest(session, receipt, layers, prices, frames, structures, bedrock=True):
    """The digest from the retained layers, exactly as ROOT's assembly writes it (the roll series and per-second flow).
    bedrock=False: no bedrock sources or tables (the render-only step; Granite's read stops at the bedrock heading)."""
    flow = layers['legacy_native_signed_flow']['per_second']
    roll_layer = layers['legacy_per_second_roll20']
    session._work_probe.update('root-digest')
    session._write_digest(receipt, layers, prices, frames, structures,
        [float('nan') if v is None else v for v in roll_layer['series']], roll_layer['first_second'],
        [r['buy'] for r in flow], [r['sell'] for r in flow], bedrock=bedrock)


def resume_legacy(session, source):
    """Reuse the completed legacy outputs and INPUT spool; no source re-ingestion."""
    import frankie_box_bedrock as B
    session._work_probe.update('root-legacy-reuse')
    pin, derived, records, prices, frames, structures, failures, layers, entries = load_retained_layers(session)
    container = dict(session.source_binding['container'])
    if witness(Path(container['path'])) != {k: container[k] for k in ('path', 'bytes', 'sha256')}:
        raise ValueError('sealed source container bytes differ')
    db = sqlite3.connect(Path(container['path']).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        fmt, count, head = db.execute('SELECT format,count,head FROM seal').fetchone()
    finally:
        db.close()
    if count != session.source_binding['journal_count'] or head != session.source_binding['journal_hash']:
        raise ValueError('sealed source metadata differs')
    # The resume never re-reads the journal, so the entry kinds come from the sealed relation (every record is one
    # INPUT and one APPLIED entry; the same kinds frankie_box_monday_read writes), checked against the sealed count
    # (2026-09-28: the digest header reads rows.kinds; the resume receipt lacked it and ROOT stopped at assembly).
    if count != 2 * len(records):
        raise ValueError('sealed journal count is not two entries per input record')
    container.update(layout='compact', format=fmt, count=count, head=head, kinds=dict(INPUT=len(records), APPLIED=len(records)),
                     record_spool=witness(records.path), head_is_request_source_hash=False)
    receipt = dict(schema='FRANKIE_BOX_DERIVATION_RECEIPT_V1', at=time.time(), cycle=session.cycle,
        pin_group=pin['group'], source_binding=session.source_binding, rows=container,
        input_records=len(records), legacy_rows=layers['legacy_native_signed_flow']['summary']['rows_seen'],
        adapter_records=len(records), f_last_groups=len(frames), failures=failures, failure_count=0,
        producers=session._producer_witnesses(pin), layers=entries)
    reuse = dict(schema='FRANKIE_LEGACY_REUSE_V1', layers=entries,
                 spools={n: witness(v.path) for n, v in [('input', records), ('prices', prices),
                         ('frames', frames), ('structures', structures), ('failures', failures)]},
                 note='Retained completed artifacts; byte witnesses measured during recovery.',
                 source_journal_traversals=0, legacy_calculation_replays=0)
    save_new(session.work / ('legacy-reuse-' + uuid.uuid4().hex + '.json'), reuse)
    session._producer_module(B.V4_ADAPTER, B.V4_ADAPTER_MODULE)
    receipt['bedrock'] = session._derive_bedrock(records, container, pin, derived, receipt['layers'])
    receipt['pin_identity'] = dict(sha256=pin['pins_witness']['sha256'], cycle_index=pin['cycle_index'],
        group=pin['group'], bedrock_layers=list(pin.get('bedrock_layers') or []))
    B.write_json(session.work / 'derive.json', receipt)
    write_retained_digest(session, receipt, layers, prices, frames, structures)
    session._work_probe.update('root-derived', state='complete', failed=0)
    return receipt


def whole_day_pin_document(source, rule='One complete Monday delivery; all registry groups and all three bedrock groups. '
                                         'Historical definitions carry no execution-cycle roster.'):
    """The whole-day calculation pin for a source: the historical groups without cycle rosters, the complete-registry
    group, and the three bedrock groups (the experiment's ROOT uses the same pin with bedrock off). Shared by the Monday
    ROOT and frankie_box_experiment_root.py so the pin is built in one place."""
    historical_path = REPOSITORY / 'research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json'
    historical = json.loads(historical_path.read_bytes())
    groups = []
    for item in historical['pins']:
        item = copy.deepcopy(item)
        item.pop('cycles', None)
        item.pop('bedrock', None)
        groups.append(item)
    pin = copy.deepcopy(next(g for g in groups if g.get('complete_registry')))
    pin['bedrock'] = [copy.deepcopy(next(g for g in groups if g['group'] == name))
                     for name in ('derived_geometry', 'prebirth_opportunity', 'causal_clocks')]
    return dict(schema='FRANKIE_WHOLE_DAY_CALCULATION_PIN_V1',
        forecast_mode='whole_day_next_session', source_binding=source, pin=pin, groups=groups,
        historical_definition_file=witness(historical_path), rule=rule)


def calculate(commit, authorship_path, authorship_sha256, output_root, data_workers=1, resume_checkpoint=None, reconstruct_missing=False, binding_sha256=None,
              bedrock=True, digest=True):
    """bedrock=False / digest=False (Greg, 2026-09-29, the experiment): skip ROOT processes 2+3 (bedrock traversal and
    projection) / 4 (the Markdown digest). Frankie's cycle keeps both on (the defaults)."""
    if resume_checkpoint and not bedrock:
        raise ValueError('a resume checkpoint belongs to the bedrock traversal; it cannot resume a bedrock-off ROOT')
    require_checkout(commit)
    from research.kalshi.frankie_boss.frankie_journal_reader import worker_budget
    worker_budget(data_workers)  # Existing reader validates and caps to available CPUs.
    authorship_pin = witness(Path(authorship_path))
    if authorship_pin['sha256'] != authorship_sha256:
        raise ValueError('Monday authorship receipt differs')
    authorship = read_pin(authorship_pin)
    launch = read_pin(authorship['launch'])
    if launch.get('forecast_mode') != 'whole_day_next_session' or launch.get('trading_day') != '20211004':
        raise ValueError('whole Monday source authoring is required')
    from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
    recovered = load_recovered_ingestion(launch['ingestion_receipt'])
    lock = None
    if resume_checkpoint:
        output = safe_path(output_root)
        if output.parent != PARENT or not output.is_dir():
            raise ValueError('existing Monday root required')
        lock = (output / 'calculation.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from frankie_box_progress import snapshot
        if snapshot(output).get('process_alive'):
            raise ValueError('calculation process is still alive')
        if (output / 'calculations-receipt.json').exists():
            raise ValueError('calculations already retained; use downstream continuation')
        binding_pin = witness(output / 'source-binding.json')
        if binding_pin['sha256'] != binding_sha256:
            raise ValueError('explicit original source-binding byte hash required')
        binding = read_pin(binding_pin)
        if binding['authorship'] != authorship_pin or binding['source']['record_count'] != 2032203:
            raise ValueError('original Monday authorship or full-day identity differs')
        checkpoint_path = safe_path(resume_checkpoint)
        if not checkpoint_path.is_relative_to(output / 'work' / 'bedrock'):
            raise ValueError('checkpoint must belong to this calculation root')
        if data_workers != binding['data_workers']:
            raise ValueError('reader configuration differs from original calculation')
    else:
        output = fresh(output_root, PARENT)
        PARENT.mkdir(parents=True, exist_ok=True)
        output.mkdir(mode=0o700)
        sync_directory(PARENT)
        source = dict(trading_day='20211004', manifest_hash=recovered.manifest['manifest_hash'],
            container=recovered.container, completion=recovered.descriptor['completion'],
            source_prefix_hash=recovered.completion['source_prefix_hash'],
            record_count=recovered.completion['record_count'])
        save_new(output / 'calculation-pins.json', whole_day_pin_document(source))
        binding = dict(schema='FRANKIE_MONDAY_CALCULATION_SOURCE_V1', source=source, data_workers=data_workers,
            authorship=authorship_pin, ingestion_receipt=launch['ingestion_receipt'],
            calculation_pins=witness(output / 'calculation-pins.json'),
            container=recovered.container, manifest=recovered.manifest,
            record_count=recovered.completion['record_count'],
            journal_count=recovered.completion['journal_count'], journal_hash=recovered.completion['journal_hash'])
        save_new(output / 'source-binding.json', binding)
    from frankie_box_boss_session import Session
    session = Session(output, '20211004', '00', None)
    session.request_sha256 = witness(output / 'source-binding.json')['sha256']
    session.phase('deriving', 'complete Monday roots and all producer groups; sealed source only')
    session.native_resume_checkpoint = resume_checkpoint
    session.native_reconstruct_missing = reconstruct_missing
    result = resume_legacy(session, recovered) if resume_checkpoint else session.derive(source=recovered, bedrock=bedrock, digest=digest)
    if result['failure_count']:
        raise ValueError('Monday producer failures are retained in derive.json; no completion is declared')
    receipt = dict(schema='FRANKIE_MONDAY_CALCULATIONS_V1', commit=commit,
        source_binding=witness(output / 'source-binding.json'),
        calculation_pins=witness(output / 'calculation-pins.json'),
        derivation=witness(session.work / 'derive.json'),
        result=result['bedrock']['result'] if bedrock else None, ledgers=result['bedrock']['ledgers'] if bedrock else None,
        digest=witness(session.work / 'derivation-digest-full.md') if digest else None,
        digest_proof=witness(session.work / 'digest-proof.json') if digest else None,
        root_processes=result.get('root_processes') or dict(legacy='run', bedrock_traversal='run', bedrock_projection='run', digest='run'),
        not_run=[dict(process=k, reason='switched off for the experiment (Greg, 2026-09-29)')
                 for k, v in (result.get('root_processes') or {}).items() if v == 'skipped'],
        recovery_checkpoint=witness(Path(resume_checkpoint)) if resume_checkpoint else None,
        reconstruction_authorized=reconstruct_missing,
        model_calls=0, source_replays=0, source_writes=0,
        status='calculations_retained', principal_binding='pending')
    save_new(output / 'calculations-receipt.json', receipt)
    probe = session._work_probe
    probe.checkpoint('saved', output / 'calculations-receipt.json')
    if read_pin(witness(output / 'calculations-receipt.json')) != receipt:
        raise ValueError('Monday calculation receipt readback differs')
    probe.checkpoint('read_verified', output / 'calculations-receipt.json')
    session.phase('derived')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--authorship', required=True)
    parser.add_argument('--authorship-sha256', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--data-workers', type=int, default=1)
    parser.add_argument('--resume-checkpoint')
    parser.add_argument('--reconstruct-missing', action='store_true')
    parser.add_argument('--binding-sha256')
    parser.add_argument('--bedrock', choices=('on', 'off'), default='on', help='off: skip ROOT processes 2 and 3 (the experiment)')
    parser.add_argument('--digest', choices=('on', 'off'), default='on', help='off: skip ROOT process 4 (the experiment)')
    args = parser.parse_args()
    print(json.dumps(calculate(args.commit, args.authorship, args.authorship_sha256, args.output_root, args.data_workers,
        args.resume_checkpoint, args.reconstruct_missing, args.binding_sha256,
        bedrock=args.bedrock == 'on', digest=args.digest == 'on'), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
