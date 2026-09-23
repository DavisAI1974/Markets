"""Receipt-bound delivery for the existing readiness and principal workflows.

Only the CLI is a host entry point: it verifies a pinned clean tooling checkout,
takes the existing host session lock and revalidates WAIT before any publication.
Delivery is never permission to resume, start a job, or release an owner hold.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

_spec = importlib.util.spec_from_file_location('_frankie_delivery_wait', Path(__file__).with_name('workflow_wait.py'))
_wait = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wait)
read_wait_receipt = _wait.read_wait_receipt
_directory, _open_file, _read = _wait._directory, _wait._open_file, _wait._read

DELIVERED = ('service-pins.json', 'pod-info.json', 'startup-intent.json',
             'run.json', 'service-ready.json', 'observer.json')
CONTEXT_FIELDS = {'configuration_path', 'configuration_sha256', 'wait_receipt_path',
                  'wait_receipt_sha256', 'tools_root', 'tools_commit', 'python',
                  'request_id', 'request_sha256'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_path(path):
    path = Path(path).absolute()
    for member in (path, *path.parents):
        if member.exists() or member.is_symlink():
            value = member.lstat()
            if stat.S_ISLNK(value.st_mode) or getattr(value, 'st_file_attributes', 0) & 1024:
                raise ValueError('linked or reparse delivery path refused')
    return path


def read_bytes(path):
    return _read(checked_path(path))


def publish_bytes(path, body):
    """Publish through a retained flushed temporary; an exact replay resyncs the final file."""
    path = checked_path(path)
    directory = _directory(path.parent, create=True)
    try:
        if not path.exists():
            temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
            fd = _open_file(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, directory=directory)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary.name if directory is not None else temporary,
                        path.name if directory is not None else path,
                        src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            except FileExistsError:
                pass
        fd = _open_file(path, directory=directory)
        with os.fdopen(fd, 'rb') as stream:
            if stream.read() != body:
                raise ValueError('retained delivery bytes differ')
            os.fsync(stream.fileno())
        if directory is not None:
            os.fsync(directory)
    finally:
        if directory is not None:
            os.close(directory)


def validate_context(context):
    if type(context) is not dict or set(context) != CONTEXT_FIELDS:
        raise ValueError('exact explicit delivery context required')
    if any(type(v) is not str or not v for v in context.values()):
        raise ValueError('string delivery context required')
    for name in ('configuration_sha256', 'wait_receipt_sha256', 'request_sha256', 'tools_commit'):
        if not re.fullmatch('[0-9a-f]{40}' if name == 'tools_commit' else '[0-9a-f]{64}', context[name]):
            raise ValueError('full delivery identity required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', context['request_id']):
        raise ValueError('bare request identity required')
    return context


def admit(context, kind):
    validate_context(context)
    cfg_raw = read_bytes(context['configuration_path'])
    if digest(cfg_raw) != context['configuration_sha256']:
        raise ValueError('configuration bytes changed')
    cfg = json.loads(cfg_raw)
    wait = read_wait_receipt(context['wait_receipt_path'], context['wait_receipt_sha256'], cfg)
    if (wait['kind'] != kind or wait['state'] != 'WAIT'
            or wait['run_id'] != cfg['run_id']
            or Path(wait['run_directory']).resolve() != Path(cfg['run_directory']).resolve()
            or wait['request_id'] != context['request_id']):
        raise ValueError('delivery differs from retained waiting request')
    cycle = f"execution/cycle-{wait['cycle_index']:02d}"
    request = cycle + ('/actual-critic-request.json' if kind in ('readiness', 'service_resume') else
                       '/principal/classroom-correction-request.json' if kind == 'principal_correction' else
                       '/principal/session-request.json')
    if wait['artifacts'].get(request, {}).get('sha256') != context['request_sha256']:
        raise ValueError('delivery request digest differs from WAIT')
    root = checked_path(cfg['run_directory'])
    if digest(read_bytes(root/request)) != context['request_sha256']:
        raise ValueError('retained request bytes changed')
    return cfg, wait


def payload_files(payload, names):
    root = checked_path(payload)
    return {name: read_bytes(root/name) for name in names}


def publication(context, cfg, kind, files):
    root = checked_path(Path(cfg['run_directory'])/'workflow-deliveries'/kind/context['request_id'])
    intent = dict(schema='FRANKIE_WORKFLOW_DELIVERY_INTENT_V1', context=context, kind=kind,
                  files={name: dict(bytes=len(body), sha256=digest(body)) for name, body in files.items()})
    return root, intent


def publish_readiness(context, payload):
    validate_context(context)
    cfg_raw = read_bytes(context['configuration_path'])
    if digest(cfg_raw) != context['configuration_sha256']:
        raise ValueError('configuration bytes changed')
    preliminary = json.loads(cfg_raw)
    retained = read_wait_receipt(context['wait_receipt_path'], context['wait_receipt_sha256'], preliminary)
    kind = retained['kind']
    if kind not in ('readiness', 'service_resume'):
        raise ValueError('readiness delivery requires a readiness WAIT')
    cfg, wait = admit(context, kind)
    files = payload_files(payload, DELIVERED)
    pins = json.loads(files['service-pins.json'])
    if (pins.get('request_sha256') != context['request_sha256']
            or pins.get('admission', {}).get('request_sha256') != context['request_sha256']
            or json.loads(files['service-ready.json']).get('inference_sent') is not False):
        raise ValueError('readiness differs from exact admitted request')
    directory, intent = publication(context, cfg, kind, files)
    ready_directory = directory
    trigger_schema = 'FRANKIE_ACTUAL_EXECUTE_V1'
    if kind == 'service_resume':
        from research.kalshi.frankie_boss.c15_journal import unpack
        service_path = Path(cfg['run_directory'])/f"execution/cycle-{wait['cycle_index']:02d}"/'host-service.c15.json'
        service = unpack(json.loads(read_bytes(service_path)))
        ready_directory = checked_path(service['directory'])
        if digest(files['service-pins.json']) != service['pins_sha256'] or set(service['files']) != set(DELIVERED)-{'service-pins.json'}:
            raise ValueError('same-service resume pins differ')
        for name, body in files.items():
            if read_bytes(ready_directory/name) != body or (name != 'service-pins.json' and digest(body) != service['files'][name]):
                raise ValueError('same-service resume readiness changed')
        trigger_schema = 'FRANKIE_ACTUAL_RESUME_JOB_V1'
    trigger = checked_path(Path(cfg['host_runtime']['pod_credential_ssm']['trigger_directory'])
                           / context['request_id'] / (trigger_schema+'.json'))
    intent_path = directory/'intent.json'
    if trigger.exists() and not intent_path.exists():
        raise ValueError('existing trigger has no matching delivery intent')
    trigger_value = dict(schema=trigger_schema, service_pins_sha256=digest(files['service-pins.json']))
    trigger_value.update(dict(request_id=context['request_id']) if kind == 'service_resume'
                         else dict(readiness_directory=str(ready_directory)))
    trigger_body = canonical(trigger_value)
    # Refuse every conflict before filling an interrupted publication.
    for path, body in [(intent_path, canonical(intent)), (trigger, trigger_body),
                       *((directory/name, body) for name, body in files.items())]:
        if path.exists() and read_bytes(path) != body:
            raise ValueError('retained readiness publication differs')
    publish_bytes(intent_path, canonical(intent))
    if kind == 'readiness':
        for name, body in files.items():
            publish_bytes(directory/name, body)
    admit(context, kind)
    for name, body in files.items():
        if read_bytes(ready_directory/name) != body:
            raise ValueError('readiness changed before trigger')
    publish_bytes(trigger, trigger_body)
    receipt = dict(schema='FRANKIE_WORKFLOW_DELIVERY_V1', kind=kind,
                   request_id=context['request_id'], request_sha256=context['request_sha256'],
                   wait_receipt_sha256=context['wait_receipt_sha256'],
                   configuration_sha256=context['configuration_sha256'],
                   readiness_directory=str(ready_directory), trigger=str(trigger),
                   intent_sha256=digest(canonical(intent)), receipt_path=str(directory/'receipt.json'))
    publish_bytes(directory/'receipt.json', canonical(receipt))
    return receipt


def actual_recorder(configuration, response_path, attestation_path, cycle_index, turn):
    from research.kalshi.frankie_boss.operations import record_actual_frankie_response
    argv = sys.argv
    try:
        sys.argv = ['record_actual_frankie_response',
                    '--configuration', configuration['configuration_path'],
                    '--configuration-sha256', configuration['configuration_sha256'],
                    '--response', str(response_path), '--response-sha256', digest(read_bytes(response_path)),
                    '--host-attestation', str(attestation_path),
                    '--host-attestation-sha256', digest(read_bytes(attestation_path)),
                    '--cycle-index', str(cycle_index), '--turn', turn]
        record_actual_frankie_response.main()
    finally:
        sys.argv = argv


def record_principal(context, payload, *, turn, recorder=actual_recorder):
    if turn not in ('initial', 'correction'):
        raise ValueError('known principal turn required')
    kind = 'principal' if turn == 'initial' else 'principal_correction'
    cfg, wait = admit(context, kind)
    files = payload_files(payload, ('response.json', 'host-attestation.json', 'host-session-record.json'))
    response = json.loads(files['response.json'])
    attestation = json.loads(files['host-attestation.json'])
    principal = checked_path(Path(cfg['run_directory'])/f"execution/cycle-{wait['cycle_index']:02d}"/'principal')
    record_target = principal/('host-session-record.json' if turn == 'initial' else 'host-correction-record.json')
    record_pin = attestation.get('host_record', {})
    if (set(record_pin) != {'path', 'bytes', 'sha256'}
            or record_pin['sha256'] != digest(files['host-session-record.json'])
            or type(record_pin['bytes']) is not int or record_pin['bytes'] != len(files['host-session-record.json'])):
        raise ValueError('attestation does not pin exact delivered record')
    # Retain the original attestation byte-for-byte; only the admitted copy changes its path.
    admitted = json.loads(files['host-attestation.json'])
    admitted['host_record']['path'] = str(record_target)
    final = principal/('session-response.json' if turn == 'initial' else 'classroom-correction-response.json')
    expected = dict(response=response, host_attestation=admitted)
    if final.exists() and read_bytes(final) != canonical(expected):
        raise ValueError('existing principal response differs from incoming exact envelope')
    directory, intent = publication(context, cfg, kind, files)
    publish_bytes(directory/'intent.json', canonical(intent))
    for name, body in files.items():
        publish_bytes(directory/name, body)
    publish_bytes(directory/'admitted-attestation.json', canonical(admitted))
    publish_bytes(record_target, files['host-session-record.json'])
    admit(context, kind)
    # The existing recorder reruns all adapter admission checks even for exact duplicate delivery.
    recorder(context, directory/'response.json', directory/'admitted-attestation.json', wait['cycle_index'], turn)
    if read_bytes(final) != canonical(expected):
        raise ValueError('recorder did not publish the exact admitted envelope')
    admit(context, kind)
    receipt = dict(schema='FRANKIE_WORKFLOW_DELIVERY_V1', kind=kind,
                   request_id=context['request_id'], request_sha256=context['request_sha256'],
                   wait_receipt_sha256=context['wait_receipt_sha256'],
                   configuration_sha256=context['configuration_sha256'],
                   intent_sha256=digest(canonical(intent)), session_response_sha256=digest(read_bytes(final)),
                   receipt_path=str(directory/'receipt.json'))
    publish_bytes(directory/'receipt.json', canonical(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context-base64', required=True)
    parser.add_argument('--kind', choices=('validate', 'readiness', 'principal'), required=True)
    parser.add_argument('--payload')
    parser.add_argument('--turn', choices=('initial', 'correction'), default='initial')
    args = parser.parse_args()
    context = validate_context(json.loads(base64.b64decode(args.context_base64, validate=True)))
    root = checked_path(context['tools_root'])
    if root.resolve() != Path(__file__).resolve().parents[4]:
        raise ValueError('delivery code is not the pinned tools checkout')
    if Path(context['python']).resolve() != Path(sys.executable).resolve():
        raise ValueError('delivery interpreter differs')
    current = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if current != context['tools_commit']:
        raise ValueError('delivery tools commit differs')
    subprocess.run(['git', '-C', str(root), 'diff', '--exit-code', 'HEAD', '--',
                    'research/kalshi/frankie_boss', 'research/refrag'], check=True, stdout=subprocess.DEVNULL)
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all',
                                '--', 'research/kalshi/frankie_boss', 'research/refrag'], text=True).strip():
        raise ValueError('delivery tooling checkout is not clean')
    cfg = json.loads(read_bytes(context['configuration_path']))
    run = checked_path(cfg['run_directory'])
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive
    with _exclusive(run/'actual-host-session.lock'):
        kind = 'readiness' if args.kind == 'readiness' else ('principal' if args.turn == 'initial' else 'principal_correction')
        if args.kind == 'validate':
            wait = read_wait_receipt(context['wait_receipt_path'], context['wait_receipt_sha256'], cfg)
            admit(context, wait['kind'])
            print(json.dumps(dict(status='delivery_context_verified', run_directory=str(run))))
            return
        if args.kind == 'readiness':
            with _exclusive(run/'actual-host.lock'):
                receipt = publish_readiness(context, args.payload)
        else:
            receipt = record_principal(context, args.payload, turn=args.turn)
        print('RECEIPT ' + json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(status='delivery_refused', error_type=type(error).__name__)))
        raise SystemExit(1)
