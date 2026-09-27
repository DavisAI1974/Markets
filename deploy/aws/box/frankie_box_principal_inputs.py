"""Assemble one Monday run from completed calculations and accumulated knowledge.

Reuses retained source bindings; no A-arm, source traversal or historical S3 delivery.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
FB = REPOSITORY / 'research/kalshi/frankie_boss/sunday_20260915_package/FB'
RETAINED = REPOSITORY / 'research/kalshi/frankie_boss/monday_20211004_principal/retained'
PARENT = Path('/opt/frankie-box/work/principal-inputs')
BRAIN = Path('/opt/frankie-box/brain')


def pin(path):
    from research.kalshi.frankie_boss.frankie_principal_adapter import file_witness
    return dict(path=str(Path(path).resolve()), **file_witness(path))


def checked(witness):
    if pin(witness['path']) != witness:
        raise ValueError('retained input differs: ' + witness['path'])
    return Path(witness['path']).read_bytes()


def write(path, value):
    from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
    with Path(path).open('xb') as handle:
        handle.write(canonical(value))
    return pin(path)


def assemble(output, calculations_path, calculations_sha256):
    from research.kalshi.frankie_boss.dipole_shared_knowledge import build_snapshot, _body, _hash
    from research.kalshi.frankie_boss.frankie_principal_adapter import load_cycle_calculation_pin, SECTIONS
    import frankie_box_brain as brain
    calculation_witness = pin(calculations_path)
    if calculation_witness['sha256'] != calculations_sha256:
        raise ValueError('independent completed-calculations receipt hash required')
    calculations = json.loads(checked(calculation_witness))
    if (calculations.get('schema') != 'FRANKIE_MONDAY_CALCULATIONS_V1'
            or calculations.get('status') != 'calculations_retained'):
        raise ValueError('completed Monday calculations required')
    source = json.loads(checked(calculations['source_binding']))
    calculation_pin = load_cycle_calculation_pin(0, calculations['calculation_pins']['path'])
    if (source['source'] != calculation_pin['source_binding']
            or source['source']['trading_day'] != '20211004'):
        raise ValueError('calculation source and pin differ')
    for key in ('calculation_pins', 'derivation', 'result', 'digest', 'digest_proof'):
        witness = calculations[key]
        if pin(witness['path']) != witness:
            raise ValueError('retained calculation evidence changed: ' + key)
    if json.loads(checked(calculations['derivation'])).get('failure_count') != 0:
        raise ValueError('calculation failures remain')
    output = Path(output)
    if output.parent != PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(PARENT))
    output.mkdir(parents=True, mode=0o700)
    original = json.loads((FB / 'retained-principal/retained-witnesses.json').read_bytes())
    files = {}
    for name, entry in original['files'].items():
        if '/contract_section_' not in name:
            continue
        witness = pin(RETAINED / name)
        if any(witness[k] != entry[k] for k in ('bytes', 'sha256')):
            raise ValueError('historical section changed: ' + name)
        files[name] = witness
    if {n.split('contract_section_')[1].removesuffix('.json') for n in files} != set(SECTIONS):
        raise ValueError('all 18 historical sections required')
    retained = write(output / 'retained-witnesses.json', dict(files=files))
    base = brain.pin_session_base(BRAIN, calculations['source_binding']['sha256'],
                                  output / 'knowledge-base-receipt.json')
    catalog = json.loads((REPOSITORY / 'research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json').read_bytes())
    catalog['version'] += '-accumulated-' + pin(base)['sha256']
    local = {}
    for label, manifest, directory in brain.snapshot_entries(BRAIN, base):
        for entry in manifest['entries']:
            if not entry.get('include'):
                continue
            source_id = label + ':' + entry['name']
            local[source_id] = directory / entry['name']
            catalog['sources'].append(dict(id=source_id, path='brain/' + label + '/' + entry['name'],
                revision=pin(base)['sha256'], sha256=entry['sha256'], bytes=entry['bytes'],
                status='RETAINED_PRIOR_KNOWLEDGE', required=True, access='SHARED_RESEARCH',
                explanation='Complete retained prior findings, including uncertainty and corrections; historical claims keep their provenance.',
                provenance={'brain_base': pin(base), 'entry_manifest': pin(directory / 'MANIFEST.json')},
                supersedes=[]))
    for name, witness in files.items():
        source_id = 'preserved-section:' + name.split('contract_section_')[1].removesuffix('.json')
        local[source_id] = Path(witness['path'])
        catalog['sources'].append(dict(id=source_id, path='preserved/' + name,
            revision=witness['sha256'], sha256=witness['sha256'], bytes=witness['bytes'],
            status='HISTORICAL_SECTION', required=True, access='SHARED_RESEARCH',
            explanation='Exact original section evidence, retained with its historical hash.',
            provenance={'retained_witnesses': retained}, supersedes=[]))
    destination = Path('/opt/frankie-box/request/shared-knowledge') / _hash(_body(catalog))
    def resolve(entry):
        if entry['id'] in local:
            return local[entry['id']].read_bytes()
        current = REPOSITORY / entry['path']
        if current.is_file() and pin(current)['sha256'] == entry['sha256']:
            return current.read_bytes()
        if (entry['provenance'].get('repository') != 'DavisAI1974/Markets'
                or not re.fullmatch('[0-9a-f]{40}', entry['revision'])):
            raise ValueError('immutable repository research source required')
        url = 'https://raw.githubusercontent.com/DavisAI1974/Markets/' + entry['revision'] + '/' + entry['path']
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    snapshot = build_snapshot(catalog, resolve, destination)
    shared = dict(directory=str(snapshot.directory), snapshot_hash=snapshot.snapshot_hash)
    single = dict(calculations_receipt=calculation_witness, source_binding=calculations['source_binding'],
                  knowledge_base=pin(base), shared_knowledge=shared)
    result = dict(schema='FRANKIE_MONDAY_SINGLE_RUN_INPUTS_V1', output=str(output),
        retained_witnesses=retained, calculation_result=calculations['result'],
        calculation_pins=calculations['calculation_pins'], shared_knowledge=shared, single_run=single,
        principal_admission={'mode': 'single_run', 'output_validation': 'after_execution'},
        model_calls=0, source_writes=0, source_traversals=0)
    write(output / 'principal-inputs-receipt.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--calculations-receipt', required=True)
    parser.add_argument('--calculations-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.output_root, args.calculations_receipt, args.calculations_sha256),
                     sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
