"""Assemble Frankie's retained principal inputs for the Monday cycle-0 run on the Linux box (Greg, 2026-09-23).

Memory A is valid (Greg, 2026-09-17): the retained principal files are the frozen Memory A run, committed at
research/kalshi/frankie_boss/monday_20211004_principal/retained (byte-exact copies of the receiver-commit git blobs).
This writes one fresh directory holding: the retained-witnesses file re-pointed at those staged files, the frozen
memory, the delivery receipt, the member mapping (mapping.json + its index.jsonl) and the calculation result, the
last two fetched through the workflow's presigned map. Every byte is checked against its pinned hash; nothing is
recomputed. No model call, ingestion or source write.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request

REPOSITORY = Path(__file__).resolve().parents[3]
FB = REPOSITORY / 'research/kalshi/frankie_boss/sunday_20260915_package/FB'
RETAINED = REPOSITORY / 'research/kalshi/frankie_boss/monday_20211004_principal/retained'
PARENT = Path('/opt/frankie-box/work/principal-inputs')
FETCHED = {  # name -> (presigned-map key, bytes, sha256)
    'index.jsonl': ('host-deliveries/20211003/mapping/index.jsonl', 16121079,
                    'f62c522dcc00a4d3e1caeac7a8e1e4e534a437ef53be200e991508236c027ca6'),
    'calculation_result.json': ('nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/'
                                '7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1/calculation_result.json',
                                29089413, '91e47d0d1533b6745888bcc17e4231f998ed78dc9735c7e2f0dcab8bd65971a9'),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def pin(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def checked(path, size, digest):
    got = pin(path)
    if (got['bytes'], got['sha256']) != (size, digest):
        raise ValueError('%s differs from its pin: %s' % (path, got))
    return got


def write(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    with open(path, 'xb') as f:
        f.write(raw)
    return pin(path)


def assemble(output):
    output = Path(output)
    if output.parent != PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(PARENT))
    PARENT.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    (output / 'mapping').mkdir()
    # The two bulk files, through the workflow's private presigned map (URLs never printed).
    mapping_urls = json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=120).read())
    fetched = {}
    for name, (key, size, digest) in FETCHED.items():
        target = output / ('mapping' if name == 'index.jsonl' else '.') / name
        with urllib.request.urlopen(mapping_urls[key]['url'], timeout=600) as response, open(target, 'xb') as out:
            shutil.copyfileobj(response, out, 1 << 20)
        fetched[name] = checked(target, size, digest)
    shutil.copyfile(FB / 'source-execution-20260915/mapping/mapping.json', output / 'mapping/mapping.json')
    mapping = checked(output / 'mapping/mapping.json', 1063, '55cccc238a15b76528d60220e8a236204bf244ef4e33948e9ef6b74a03656e21')
    shutil.copyfile(FB / 'delivery-plain/local_delivery_receipt.json', output / 'local_delivery_receipt.json')
    delivery = checked(output / 'local_delivery_receipt.json', 4853, 'db773478c80f28619bdf16abb76ccf6ebedbacc6a65894ba624ed6d82fad0f11')
    memory = checked(RETAINED / 'FROZEN_MEMORY_A_20211003.json', 166700,
                     '4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a')
    # The retained witnesses, re-pointed from the Windows paths to the staged byte-exact copies.
    original = json.loads((FB / 'retained-principal/retained-witnesses.json').read_bytes())
    files = {}
    for name, entry in original['files'].items():
        files[name] = dict(checked(RETAINED / name, entry['bytes'], entry['sha256']))
    retained = write(output / 'retained-witnesses.json', dict(original, files=files,
        relocated=dict(from_sha256='d4c03cee0524961813daf7f223425236a7edbb03c68468cc42defedec1dc008b',
                       reason='Windows retained paths re-pointed to the staged byte-exact copies on the Linux box')))
    result = dict(schema='FRANKIE_MONDAY_PRINCIPAL_INPUTS_V1', output=str(output), memory=memory, mapping=mapping,
                  mapping_index=fetched['index.jsonl'], retained_witnesses=retained, delivery_receipt=delivery,
                  calculation_result=fetched['calculation_result.json'], model_calls=0, source_writes=0)
    write(output / 'principal-inputs-receipt.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    print(json.dumps(assemble(parser.parse_args().output_root), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
