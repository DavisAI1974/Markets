"""Assemble one Monday run from completed calculations and accumulated knowledge.

Reuses retained source bindings; no A-arm, source traversal or historical S3 delivery.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
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


def pins(paths):
    """Hash several files at once, one thread each (hashlib releases the GIL on the 1 MB blocks), so the wall time is
    the largest file's hash, not the sum. A single file's sha256 cannot be split."""
    paths = list(paths)
    with ThreadPoolExecutor(max(1, min(16, len(paths)))) as pool:
        return list(pool.map(pin, paths))


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
    # Staggered (Greg, 2026-09-27): ROOT's evidence files (the digest dominates) are hashed on background threads while
    # the sections, the brain base and the shared-knowledge snapshot are assembled; they are checked before the receipt.
    keys = ('calculation_pins', 'derivation', 'result', 'digest', 'digest_proof')
    evidence_pool = ThreadPoolExecutor(len(keys))
    evidence = [evidence_pool.submit(pin, calculations[key]['path']) for key in keys]
    evidence_pool.shutdown(wait=False)
    if json.loads(Path(calculations['derivation']['path']).read_bytes()).get('failure_count') != 0:
        raise ValueError('calculation failures remain')
    output = Path(output)
    if output.parent != PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(PARENT))
    output.mkdir(parents=True, mode=0o700)
    original = json.loads((FB / 'retained-principal/retained-witnesses.json').read_bytes())
    files = {}
    names = [name for name in original['files'] if '/contract_section_' in name]
    for name, witness in zip(names, pins(RETAINED / name for name in names)):
        entry = original['files'][name]
        if any(witness[k] != entry[k] for k in ('bytes', 'sha256')):
            raise ValueError('historical section changed: ' + name)
        files[name] = witness
    if {n.split('contract_section_')[1].removesuffix('.json') for n in files} != set(SECTIONS):
        raise ValueError('all 18 historical sections required')
    retained = write(output / 'retained-witnesses.json', dict(files=files))
    identity = calculations['source_binding']['sha256']
    # The request's knowledge base is pinned once (the first principal-inputs root of this request keeps its receipt).
    # A later root (a re-rendered digest, same request) carries that receipt forward; pin_session_base re-checks it
    # against the snapshot's bytes and sha256, so a changed base is still refused.
    if (BRAIN / 'bases' / identity / 'MANIFEST.json').exists():
        earlier = sorted(p for p in PARENT.glob('*/knowledge-base-receipt.json')
                         if p.parent != output and json.loads(p.read_bytes()).get('request_identity') == identity)
        if earlier:
            (output / 'knowledge-base-receipt.json').write_bytes(earlier[0].read_bytes())
            print('knowledge base receipt carried from ' + str(earlier[0]), file=sys.stderr, flush=True)
    base = brain.pin_session_base(BRAIN, identity, output / 'knowledge-base-receipt.json')
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
    for key, measured in zip(keys, evidence):
        if measured.result() != calculations[key]:
            raise ValueError('retained calculation evidence changed: ' + key)
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
