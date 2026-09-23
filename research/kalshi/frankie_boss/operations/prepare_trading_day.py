"""Build a new schedule and compact prefixes from explicitly pinned completed inputs.

This tool performs no network, model, host-control or source-write operation.
Every output is new; historical configurations and prefixes remain untouched.
"""
import argparse
from functools import partial
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from research.kalshi.frankie_boss.trading_day_schedule import require_launch_fields, build_whole_day_schedule
from research.kalshi.frankie_boss.block_source_scope import block_source_scope
from research.kalshi.frankie_boss.completed_schedule_view import open_completed_schedule_view
from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
from research.kalshi.frankie_boss.sunday_schedule import build_schedule
from research.kalshi.frankie_boss import compact_journal_snapshot, context_session, sunday_native_runtime
from research.kalshi.frankie_boss.operations.build_remaining_sunday_prefixes import (
    read_pinned, pinned, sha, save_new, witness, materialize)


def prepare(configuration_path, *, output_configuration, cycles=None):
    configuration_path = Path(configuration_path)
    configuration = json.loads(configuration_path.read_bytes())
    launch = require_launch_fields(read_pinned(configuration['trading_day_launch']))
    manifest = read_pinned(configuration['source_manifest'])
    if (manifest.get('manifest_hash') != launch['source_manifest']['manifest_hash']
            or manifest.get('trading_day') != launch['trading_day']
            or manifest.get('total_mbo_records') != launch['declared_record_count']):
        raise ValueError('source_manifest differs from the trading-day launch declaration')
    scope = block_source_scope(manifest, expected_manifest_hash=launch['source_manifest']['manifest_hash'])
    receipt_path = pinned(launch['ingestion_receipt'])
    receipt = read_pinned(launch['ingestion_receipt'])
    recovered = None
    if receipt.get('schema') == 'FRANKIE_VERIFIED_RECOVERED_INGESTION_V1':
        from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
        recovered = load_recovered_ingestion(launch['ingestion_receipt'])
        if recovered.descriptor['source_manifest'] != configuration['source_manifest']:
            raise ValueError('recovered source manifest pin differs from configuration')
        receipt = recovered.receipt
        completion = recovered.completion
        source = recovered.checkpoint_path.parent
        checkpoint = recovered.checkpoint_path
        checkpoint_sha256 = recovered.descriptor['checkpoint']['sha256']
        container = recovered.container
        journal = Path(container['path'])
    else:
        source = receipt_path.parent
        completion = json.loads((source / 'completion.json').read_bytes())
        if receipt.get('writer') != 'compact' or receipt.get('journal_file') != 'journal.compact.sqlite':
            raise ValueError('ingestion_receipt journal_file differs from the compact writer')
        journal = source / receipt['journal_file']
        container = dict(path=str(journal.resolve()), sha256=receipt['journal_sha256'], bytes=receipt['journal_bytes'])
        pinned(container)
        checkpoint = source / 'builder-checkpoint.c15.json'
        checkpoint_sha256 = receipt['checkpoint_sha256']
    if (receipt.get('session_policy') != 'cme_trading_day'
            or receipt.get('trading_day') != launch['trading_day']
            or receipt.get('manifest_hash') != scope.scope_id
            or receipt.get('record_count') != manifest['total_mbo_records']
            or receipt.get('journal_count') != 2 * receipt['record_count']
            or receipt.get('scope_hash') != scope.genesis_hash()):
        raise ValueError('ingestion_receipt is not the completed declared trading day')
    if [s['session_id'] for s in receipt['sessions']] != [launch['trading_day']]:
        raise ValueError('ingestion_receipt sessions differ from one trading day')
    if any(receipt[k] != completion[k] for k in ('record_count', 'journal_count', 'journal_hash', 'group_count', 'source_prefix_hash')):
        raise ValueError('ingestion receipt and conformance completion disagree')
    whole = launch.get('forecast_mode') == 'whole_day_next_session'
    cutoffs_path = None if whole else pinned(launch['cutoffs'])
    mapping_path = pinned(launch['mapping'])
    cutoffs = None if whole else json.loads(cutoffs_path.read_bytes())['invocation_cutoffs']
    if not whole and (type(cutoffs) is not list or not cutoffs):
        raise ValueError('cutoffs must be an explicitly authored nonempty roster')
    total = 1 if whole else len(cutoffs)
    if cycles is None:
        cycles = total
    if type(cycles) is not int or not 1 <= cycles <= total:
        raise ValueError('cycles must be within the declared cutoff roster')
    contract = read_pinned(launch['source_contract'])
    if (contract.get('schema') != 'FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1'
            or contract.get('source_manifest_hash') != manifest['manifest_hash']
            or contract.get('trading_day') != launch['trading_day']
            or contract.get('cycle_count') != total or len(contract.get('cycles', [])) != total):
        raise ValueError('source_contract must cover the declared source manifest, trading day and cutoff roster')
    view = open_completed_schedule_view(scope, journal, checkpoint,
        checkpoint_sha256, receipt['checkpoint_state_hash'], completion,
        reader_factory=FrankieCompactReader,
        recovery_descriptor=launch['ingestion_receipt'] if recovered is not None else None)
    try:
        if whole:
            if (contract.get('forecast_mode') != 'whole_day_next_session'
                    or contract.get('forecast_target') != launch['forecast_target']):
                raise ValueError('whole-day contract target differs from launch')
            schedule = build_whole_day_schedule(view, mapping_path,
                expected_index_sha256=launch['mapping']['sha256'],
                source_identity=dict(trading_day=launch['trading_day'],
                    source_manifest_hash=manifest['manifest_hash'],
                    source_partitions=[m.member_key for m in scope.members],
                    source_record_count=receipt['record_count'], journal_count=receipt['journal_count'],
                    journal_hash=receipt['journal_hash'], journal_sha256=container['sha256']),
                forecast_target=launch['forecast_target'])
        else:
            schedule = build_schedule(view, mapping_path, expected_index_sha256=launch['mapping']['sha256'],
                cutoffs_path=cutoffs_path, expected_cutoffs_sha256=launch['cutoffs']['sha256'],
                model_context_rows=launch['model_context_rows'],
                trading_day=dict(trading_day=launch['trading_day'], source_manifest_hash=manifest['manifest_hash'],
                    source_partitions=[m.member_key for m in scope.members],
                    source_record_count=receipt['record_count'], journal_count=receipt['journal_count'],
                    journal_hash=receipt['journal_hash'], journal_sha256=container['sha256'],
                    step_count=total, cutoff_rule=launch['cutoff_rule']))
    finally:
        view.journal.close()
    # Verify the authored contract against every derived cutoff before creating files.
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle
    for index, step in enumerate(schedule['steps']):
        bound = bind_cycle(launch['source_contract']['path'], launch['source_contract']['sha256'], index, step)
        feedback = step['feedback_available_through']
        if whole:
            if (feedback is not None or bound['learning_cutoff_ns'] is not None
                    or bound['learning_through_source_cursor'] is not None
                    or bound.get('feedback_status') != 'pending_target_outcomes'):
                raise ValueError('whole-day target outcomes must remain pending')
            continue
        if (bound['learning_cutoff_ns'] != feedback['as_of']
                or bound['learning_through_source_cursor'] != feedback['through_cursor']):
            raise ValueError('source_contract learning boundary differs from schedule feedback')
    h = configuration['host_runtime']
    entity = tuple(h['source_entity'])
    if len(entity) != 2 or any(type(v) is not int for v in entity):
        raise ValueError('host_runtime.source_entity must explicitly declare publisher and instrument')
    schedule_dir = Path(configuration['schedule_directory']).resolve()
    prefixes = Path(h['prefixes_directory']).resolve()
    output_configuration = Path(output_configuration).resolve()
    if (schedule_dir == prefixes or source == schedule_dir or source == prefixes
            or schedule_dir in source.parents or prefixes in source.parents
            or source in schedule_dir.parents or source in prefixes.parents
            or output_configuration == configuration_path.resolve()):
        raise ValueError('fresh output paths must be separate from source and original configuration')
    if schedule_dir.exists() or prefixes.exists() or output_configuration.exists():
        raise ValueError('fresh schedule, prefixes and output configuration required; existing evidence preserved')
    schedule_dir.mkdir(parents=True, exist_ok=False)
    prefixes.mkdir(parents=True, exist_ok=False)
    save_new(schedule_dir / 'schedule.json', schedule)
    outer = dict(schema='FRANKIE_TRADING_DAY_SCHEDULE_RECEIPT_V1', trading_day=launch['trading_day'],
        source_records=receipt['record_count'], steps=total, source_completion=completion,
        source_checkpoint_sha256=checkpoint_sha256,
        source_checkpoint_state_hash=receipt['checkpoint_state_hash'],
        schedule_sha256=schedule['schedule_sha256'], schedule_file_sha256=sha(schedule_dir / 'schedule.json'),
        ingestion_receipt=launch['ingestion_receipt'], launch=configuration['trading_day_launch'], model_calls=0)
    if recovered is not None:
        outer['recovered_ingestion'] = recovered.provenance
    save_new(schedule_dir / 'receipt.json', outer)
    binding = dict(schema='FRANKIE_TRADING_DAY_PREFIXES_V1',
        ingestion_receipt=launch['ingestion_receipt'], schedule_receipt=witness(schedule_dir / 'receipt.json'),
        schedule=witness(schedule_dir / 'schedule.json'), compact_journal=container,
        source_journal_sha256=container['sha256'], source_count=completion['journal_count'],
        source_head_hash=completion['journal_hash'], script_sha256=sha(__file__),
        copier_sha256=sha(compact_journal_snapshot.__file__), original_configuration=witness(configuration_path),
        context_selection=dict(entity=list(entity), t_ctx=launch['model_context_rows'],
            runtime_code_sha256=sha(sunday_native_runtime.__file__), selection_code_sha256=sha(context_session.__file__)),
        model_calls=0, source_replays=0)
    binding_path = prefixes / 'trading-day-prefix-binding.json'
    save_new(binding_path, binding)
    if whole:
        step = schedule['steps'][0]
        full_receipt = dict(schema='C15_SEALED_FULL_DAY_REFERENCE_V1',
            original_journal=str(journal.resolve()), snapshot_journal=str(journal.resolve()),
            snapshot_sha256=container['sha256'], through_cursor=step['through_cursor'],
            journal_count=completion['journal_count'], journal_head_hash=completion['journal_hash'],
            records_in_prefix=receipt['record_count'], source_prefix_hash=step['source_hash'],
            as_of=step['as_of'], source_as_of=step['source_as_of'],
            source_scope_hash=scope.genesis_hash(), source_records_expected=receipt['record_count'],
            ingestion_receipt=launch['ingestion_receipt'], source_replays=0, source_copies=0)
        reference = prefixes / 'prefix-00-receipt.json'
        save_new(reference, full_receipt)
        files = prefixes / 'prefix-00-witness.json'
        save_new(files, dict(snapshot=container, receipt=witness(reference)))
        results = [witness(files)]
    else:
        copier = partial(compact_journal_snapshot.snapshot_compact_prefix,
            compact_path=journal, compact_sha256=container['sha256'], workers=h.get('data_workers', 1))
        results = materialize(journal, prefixes, schedule['steps'][:cycles],
            parent_count=completion['journal_count'], parent_head_hash=completion['journal_hash'],
            binding_sha256=sha(binding_path), first_cycle=0, copier=copier,
            scope=scope, entity=entity, t_ctx=launch['model_context_rows'])
    manifest_path = prefixes / 'trading-day-prefix-witnesses.json'
    save_new(manifest_path, dict(schema='FRANKIE_TRADING_DAY_PREFIX_WITNESSES_V1',
        trading_day=launch['trading_day'], binding=witness(binding_path), witnesses=results, prefixes=cycles,
        scheduled_cycles=total, schedule_sha256=schedule['schedule_sha256'], source_records=receipt['record_count'],
        prefix_seed_witnesses={} if whole else {str(i): witness(prefixes / ('prefix-%02d-packet-seed.json' % i)) for i in range(cycles)},
        model_calls=0, source_replays=0))
    # A separate configuration selects the new evidence; do not rewrite old bindings.
    host = {k: v for k, v in h.items() if k not in ('source_lineage', 'source_progress', 'prefix_seeds')}
    host.update(ingestion_receipt=launch['ingestion_receipt'], schedule=binding['schedule'],
        schedule_receipt=binding['schedule_receipt'], compact_journal=container,
        prefix_manifest=witness(manifest_path))
    result = dict(configuration, source_directory=str(source.resolve()), host_runtime=host,
        contract=launch['source_contract'], trading_day=launch['trading_day'],
        trading_day_schedule={k: schedule[k] for k in
            ('trading_day', 'step_count', 'source_record_count', 'source_manifest_hash', 'schedule_sha256')})
    save_new(output_configuration, result)
    return dict(prefix_count=cycles, prefixes_sha256=sha(manifest_path),
        schedule_sha256=schedule['schedule_sha256'], configuration=witness(output_configuration),
        source_records=receipt['record_count'], day=launch['trading_day'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--output-configuration', required=True)
    parser.add_argument('--cycles', type=int)
    args = parser.parse_args()
    result = prepare(args.configuration, output_configuration=args.output_configuration, cycles=args.cycles)
    print('PIPELINE_RECEIPT ' + json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
