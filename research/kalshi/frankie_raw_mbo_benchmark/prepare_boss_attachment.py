"""Prepare caller-attested BOSS inputs from independently pinned local evidence.

No mapping inference, acquisition, principal execution or population generation.
The pin record is trusted by the coordinator, not authenticated by this command.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile

from research.kalshi.frankie_raw_mbo_benchmark import native_boss_attachment as receiver
from research.kalshi.frankie_raw_mbo_benchmark.emit_frankie_spawn import EXACT_LEDGERS
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import canonical_hash

PIN_SCHEMA = 'FRANKIE_BOSS_PREPARATION_PINS_V1'
RECEIPT_SCHEMA = 'FRANKIE_BOSS_PREPARATION_RECEIPT_V1'


def _witness(raw):
    return {'sha256': receiver._sha(raw), 'bytes': len(raw)}


def _pinned_file(path, expected):
    receiver._digest(expected, 'independent input file pin')
    raw = receiver._plain_file(Path(path))
    if receiver._sha(raw) != expected:
        raise receiver.AttachmentError(f'{Path(path).name}: independent file pin differs')
    return raw


def prepare(*, pins_path, expected_pins_sha256, directory, result_path,
            delivery_receipt, mapping_artifact, output_directory):
    """Verify fresh local bytes and exclusively create the three preparation files.

    The externally supplied SHA256 must pin the canonical coordinator record.
    Its source/agent facts and mapping witness must come from independent review.
    Receipt self-hashes and plain-file SHA256 values occupy different domains.
    """
    pins_path, directory, result_path, delivery_receipt, mapping_artifact, output = map(
        lambda p: Path(p).absolute(),
        (pins_path, directory, result_path, delivery_receipt, mapping_artifact, output_directory))
    root = Path(__file__).resolve().parents[3]
    if output.resolve().is_relative_to(root):
        raise receiver.AttachmentError('preparation evidence must be outside the executing checkout')
    if output.resolve().is_relative_to(directory.resolve()):
        raise receiver.AttachmentError('preparation output must not mutate the exported attachment')
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if not output.parent.is_dir():
        raise receiver.AttachmentError('output parent must already exist')
    pins, pins_raw = receiver._canonical_file(pins_path, expected_pins_sha256)
    receiver._keys(pins, 'schema pin_origin expected_manifest_sha256 expected_boss_commit expected_agent_commit controller_checkpoint native_checkpoint boss_source agent provenance result_file_sha256 delivery_file_sha256 mode', 'preparation pins')
    if pins['schema'] != PIN_SCHEMA or pins['mode'] != 'attributed_input':
        raise receiver.AttachmentError('explicit attributed-input preparation pins required')
    receiver._keys(pins['pin_origin'], 'authority method reference', 'pin origin')
    if any(not isinstance(v, str) or not v.strip() for v in pins['pin_origin'].values()):
        raise receiver.AttachmentError('independent pin origin must name authority, method and reference')
    executing_commit = receiver._executing_commit()
    result_raw = _pinned_file(result_path, pins['result_file_sha256'])
    delivery_raw = _pinned_file(delivery_receipt, pins['delivery_file_sha256'])
    binding_raw = receiver._bytes({'schema': receiver.BINDING_SCHEMA,
        'boss_source': pins['boss_source'], 'agent': pins['agent'], 'provenance': pins['provenance']})
    request = receiver.AttachmentRequest(directory=directory,
        expected_manifest_sha256=pins['expected_manifest_sha256'],
        expected_boss_commit=pins['expected_boss_commit'], expected_agent_commit=pins['expected_agent_commit'],
        controller_checkpoint=pins['controller_checkpoint'], native_checkpoint=pins['native_checkpoint'],
        crosswalk_path=output / 'source-binding.json', expected_crosswalk_sha256=receiver._sha(binding_raw),
        mapping_artifact=mapping_artifact, mode=pins['mode'],
        expected_result_sha256=pins['result_file_sha256'])
    # The unchanged receiver remains authoritative. Stage only our new crosswalk;
    # no output directory or completion receipt exists until verification passes.
    with tempfile.TemporaryDirectory(prefix='frankie-prepare-', dir=output.parent) as temporary:
        staged = Path(temporary) / 'source-binding.json'
        staged.write_bytes(binding_raw)
        accepted = receiver.verify_attachment(replace(request, crosswalk_path=staged),
            result_path=result_path, delivery_receipt=delivery_receipt)
    # Detect changed pin/input files during verification, and a changed code HEAD.
    _pinned_file(pins_path, expected_pins_sha256)
    _pinned_file(result_path, pins['result_file_sha256'])
    _pinned_file(delivery_receipt, pins['delivery_file_sha256'])
    if receiver._executing_commit() != executing_commit:
        raise receiver.AttachmentError('executing agent commit changed during preparation')
    request_body = asdict(request)
    for name in ('directory', 'crosswalk_path', 'mapping_artifact'):
        request_body[name] = str(request_body[name])
    request_raw = receiver._bytes(request_body)
    delivery = json.loads(delivery_raw)
    receipt = {'schema': RECEIPT_SCHEMA, 'pin_origin': pins['pin_origin'],
        'pins_path': str(pins_path), 'pins_file': _witness(pins_raw),
        'executing_agent_commit': executing_commit,
        'mapping_status': accepted.receipt['mapping_status'], 'attachment_receipt': accepted.receipt,
        'input_paths': {'directory': str(directory), 'result': str(result_path),
                        'delivery_receipt': str(delivery_receipt), 'mapping': str(mapping_artifact)},
        'inputs': {'manifest': _witness(accepted.manifest_bytes), 'mapping': _witness(accepted.mapping_bytes),
                   'result': _witness(result_raw), 'delivery_receipt': _witness(delivery_raw)},
        'ledger_witnesses': {name: {'path': entry['local_path'],
            'sha256': entry['plain_sha256_observed'], 'bytes': entry['plain_bytes_observed']}
            for name, entry in delivery['ledgers'].items()
            if name in EXACT_LEDGERS},
        'outputs': {'source-binding.json': _witness(binding_raw), 'attachment-request.json': _witness(request_raw)}}
    receipt['receipt_sha256'] = canonical_hash(receipt, omit='receipt_sha256')
    output.mkdir()  # exclusive reservation; concurrent/prior evidence is never replaced
    for name, raw in (('source-binding.json', binding_raw), ('attachment-request.json', request_raw),
                      ('preparation-receipt.json', receiver._bytes(receipt))):
        with (output / name).open('xb') as handle:
            handle.write(raw)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pins-path', 'expected-pins-sha256', 'directory', 'result-path',
                 'delivery-receipt', 'mapping-artifact', 'output-directory'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = prepare(**vars(args))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'attachment preparation refused: {exc}\n')
    print(receipt['receipt_sha256'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
