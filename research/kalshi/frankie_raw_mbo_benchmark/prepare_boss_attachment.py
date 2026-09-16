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
from research.kalshi.frankie_raw_mbo_benchmark.native_staging import StagingError, _validate_outputs

PIN_SCHEMA = 'FRANKIE_BOSS_PREPARATION_PINS_V1'
#: Greg, 2026-09-16: "Enforce the output-bundle gate after the run instead of trusting the cited
#: receipt hash." Measured before this: the attachment receipt's `agent` block carried the
#: delivery receipt and the result hash and nothing about the principal's output bundle, so the
#: BOSS path never validated the 30 ledgers Frankie filed. The gate is the one staging already
#: uses (`native_staging._validate_outputs`): the artifact's `outputs_receipt_sha256` must equal
#: the receipt the validator computes over the bundle on disk, or the preparation is refused.
OUTPUT_BUNDLE_GATE_NOT_PRESENTED = 'NOT_PRESENTED'
OUTPUT_BUNDLE_GATE_VALIDATED = 'VALIDATED'
RECEIPT_SCHEMA = 'FRANKIE_BOSS_PREPARATION_RECEIPT_V1'


def _witness(raw):
    return {'sha256': receiver._sha(raw), 'bytes': len(raw)}


def _pinned_file(path, expected):
    receiver._digest(expected, 'independent input file pin')
    raw = receiver._plain_file(Path(path))
    if receiver._sha(raw) != expected:
        raise receiver.AttachmentError(f'{Path(path).name}: independent file pin differs')
    return raw


def output_bundle_gate(*, principal_artifact, outputs_dir, delivery_receipt_sha256, expected_run_id, expected_arm):
    """Validate the principal's bundle on disk against the artifact that cites it, or refuse.

    Both paths given: the artifact must name the run and arm the pins name, cite the delivery
    receipt the attachment binds, and cite an `outputs_receipt_sha256` equal to the receipt
    the validator recomputes over the ledgers. Neither given: the gate is recorded as
    NOT_PRESENTED, never silently passed, and a downstream carry refuses that. One without
    the other is refused here.
    """
    if principal_artifact is None and outputs_dir is None:
        return {'status': OUTPUT_BUNDLE_GATE_NOT_PRESENTED}
    if principal_artifact is None or outputs_dir is None:
        raise receiver.AttachmentError('the output-bundle gate needs both the principal artifact and its outputs directory')
    artifact_path = Path(principal_artifact)
    artifact_raw = receiver._plain_file(artifact_path)
    try:
        artifact = json.loads(artifact_raw)
    except ValueError as exc:
        raise receiver.AttachmentError(f'principal artifact is not JSON: {exc}') from exc
    if not isinstance(artifact, dict):
        raise receiver.AttachmentError('principal artifact must be a JSON object')
    for key, expected in (('run_id', expected_run_id), ('arm', expected_arm)):
        if artifact.get(key) != expected:
            raise receiver.AttachmentError(f'principal artifact {key} {artifact.get(key)!r} is not the pinned {expected!r}')
    if artifact.get('delivery_receipt_sha256') != delivery_receipt_sha256:
        raise receiver.AttachmentError('principal artifact cites a delivery receipt other than the one the attachment binds')
    if artifact.get('outputs_receipt_sha256') is None:
        raise receiver.AttachmentError('principal artifact cites no outputs_receipt_sha256; a delivered run without its outputs is a failed spawn')
    try:
        cited, receipt = _validate_outputs(artifact, cited_delivery=delivery_receipt_sha256, outputs_dir=Path(outputs_dir),
                                           knowledge_receipt_sha256=artifact.get('knowledge_receipt_sha256'))
    except StagingError as exc:
        raise receiver.AttachmentError(f'output-bundle gate refused: {exc}') from exc
    return {'status': OUTPUT_BUNDLE_GATE_VALIDATED, 'principal_artifact': _witness(artifact_raw),
            'outputs_receipt_sha256': cited, 'required_ledger_ids': list(receipt['required_ledger_ids']),
            'ledgers': {lid: dict(summary) for lid, summary in receipt['ledgers'].items()},
            'knowledge_receipt_sha256': artifact.get('knowledge_receipt_sha256')}


def prepare(*, pins_path, expected_pins_sha256, directory, result_path,
            delivery_receipt, mapping_artifact, output_directory,
            principal_artifact=None, outputs_dir=None):
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
    gate = output_bundle_gate(principal_artifact=principal_artifact, outputs_dir=outputs_dir,
                              delivery_receipt_sha256=accepted.receipt['agent']['delivery_receipt_sha256'],
                              expected_run_id=pins['agent']['run_id'], expected_arm=pins['agent']['arm'])
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
        'output_bundle_gate': gate,
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
    parser.add_argument('--principal-artifact', default=None, help='the run principal findings artifact citing outputs_receipt_sha256')
    parser.add_argument('--outputs-dir', default=None, help='the run principal_outputs directory the artifact cites')
    parser.add_argument('--without-output-bundle', action='store_true',
                        help='explicitly prepare with no output bundle; the receipt records the gate as NOT_PRESENTED')
    args = parser.parse_args(argv)
    without = args.__dict__.pop('without_output_bundle')
    if not without and (args.principal_artifact is None or args.outputs_dir is None):
        parser.exit(2, 'attachment preparation refused: the output-bundle gate needs --principal-artifact and --outputs-dir, or --without-output-bundle stated explicitly\n')
    try:
        receipt = prepare(**vars(args))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'attachment preparation refused: {exc}\n')
    print(receipt['receipt_sha256'])
    print('output bundle gate: ' + receipt['output_bundle_gate']['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
