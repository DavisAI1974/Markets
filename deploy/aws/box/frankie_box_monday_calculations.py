"""Run the existing complete producer stages on the independently sealed Monday source.

This is the missing pre-request calculation entry, not a controller or ingestion
route. It retains actual results for the existing principal/host/session to use.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import read_pin, require_checkout, save_new, witness
from frankie_box_author_monday_launch import fresh, sync_directory

PARENT = Path('/opt/frankie-box/work/monday-calculations')


def calculate(commit, authorship_path, authorship_sha256, output_root):
    require_checkout(commit)
    authorship_pin = witness(Path(authorship_path))
    if authorship_pin['sha256'] != authorship_sha256:
        raise ValueError('Monday authorship receipt differs')
    authorship = read_pin(authorship_pin)
    launch = read_pin(authorship['launch'])
    if launch.get('forecast_mode') != 'whole_day_next_session' or launch.get('trading_day') != '20211004':
        raise ValueError('whole Monday source authoring is required')
    from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
    recovered = load_recovered_ingestion(launch['ingestion_receipt'])
    output = fresh(output_root, PARENT)
    PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    sync_directory(PARENT)
    source = dict(trading_day='20211004', manifest_hash=recovered.manifest['manifest_hash'],
        container=recovered.container, completion=recovered.descriptor['completion'],
        source_prefix_hash=recovered.completion['source_prefix_hash'],
        record_count=recovered.completion['record_count'])
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
    document = dict(schema='FRANKIE_WHOLE_DAY_CALCULATION_PIN_V1',
        forecast_mode='whole_day_next_session', source_binding=source, pin=pin, groups=groups,
        historical_definition_file=witness(historical_path),
        rule='One complete Monday delivery; all registry groups and all three bedrock groups. Historical definitions carry no execution-cycle roster.')
    save_new(output / 'calculation-pins.json', document)
    binding = dict(schema='FRANKIE_MONDAY_CALCULATION_SOURCE_V1', source=source,
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
    result = session.derive(source=recovered)
    if result['failure_count']:
        raise ValueError('Monday producer failures are retained in derive.json; no completion is declared')
    receipt = dict(schema='FRANKIE_MONDAY_CALCULATIONS_V1', commit=commit,
        source_binding=witness(output / 'source-binding.json'),
        calculation_pins=witness(output / 'calculation-pins.json'),
        derivation=witness(session.work / 'derive.json'),
        result=result['bedrock']['result'], ledgers=result['bedrock']['ledgers'],
        digest=witness(session.work / 'derivation-digest-full.md'),
        digest_proof=witness(session.work / 'digest-proof.json'),
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
    args = parser.parse_args()
    print(json.dumps(calculate(args.commit, args.authorship, args.authorship_sha256, args.output_root), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
