"""Receipt-bound pending returns for the existing actual host; import is inert."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

SCHEMA = 'FRANKIE_WORKFLOW_WAIT_V1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _directory(path, create=False):
    path = Path(path).absolute()
    if os.name == 'nt':
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            if create:current.mkdir(exist_ok=True)
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & 0x400:
                raise ValueError('workflow directory must not be a reparse point')
        return None
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_file(path, flags=os.O_RDONLY, *, directory=None):
    path = Path(path)
    before = path.lstat() if os.name == 'nt' and path.exists() else None
    if before is not None and (not stat.S_ISREG(before.st_mode) or before.st_file_attributes & 0x400):
        raise ValueError('workflow file must not be a reparse point')
    fd = os.open(path.name if directory is not None else path,
                 flags | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_BINARY',0),
                 0o600, dir_fd=directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or (before is not None and
            (before.st_dev,before.st_ino) != (info.st_dev,info.st_ino)):
        os.close(fd)
        raise ValueError('retained workflow artifact must be a regular file')
    return fd


def _read(path):
    path = Path(path)
    directory = _directory(path.parent)
    try:
        fd = _open_file(path,directory=directory)
        with os.fdopen(fd,'rb') as stream:return stream.read()
    finally:
        if directory is not None:os.close(directory)


def witness(path):
    path = Path(path)
    directory = _directory(path.parent)
    try:
        fd = _open_file(path,directory=directory)
        h = hashlib.sha256()
        with os.fdopen(fd,'rb') as stream:
            before=os.fstat(stream.fileno())
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                h.update(block)
            after=os.fstat(stream.fileno())
            if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError('workflow artifact changed while hashing')
        return {'sha256': h.hexdigest(), 'bytes': after.st_size}
    finally:
        if directory is not None:os.close(directory)


def _publish(path, value):
    raw = canonical(value)
    path = Path(path)
    directory = _directory(path.parent,create=True)
    try:
        if not path.exists():
            temporary = path.with_name(path.name + '.partial-' + uuid.uuid4().hex)
            fd = _open_file(temporary,os.O_WRONLY | os.O_CREAT | os.O_EXCL,directory=directory)
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            # Keep prepublication evidence after both successful and uncertain publication.
            try:
                os.link(temporary.name if directory is not None else temporary,
                        path.name if directory is not None else path,
                        src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
            except FileExistsError:pass
        fd = _open_file(path,directory=directory)
        with os.fdopen(fd,'rb') as stream:
            if stream.read()!=raw:raise ValueError('retained workflow receipt changed')
            os.fsync(stream.fileno())
        if directory is not None:os.fsync(directory)
    finally:
        if directory is not None:os.close(directory)


def _artifacts(configuration, cycle, kind):
    root = Path(configuration['run_directory']).resolve()
    required = [root / 'host-identity.c15.json', cycle / 'host-preparation.c15.json',
                cycle / 'actual-critic-request.json']
    if kind in ('principal', 'principal_correction'):
        required += [cycle / 'request-plan.c15.json', cycle / 'principal/session-request.json']
    if kind == 'principal_correction':
        required.append(cycle / 'principal/classroom-correction-request.json')
    if kind == 'service_resume':required.append(cycle / 'host-service.c15.json')
    paths = set(required)
    for member in ('host-instance.c15.json','native-host-runtime.json','execution/execution-identity.c15.json'):
        if (root / member).exists():paths.add(root / member)
    for pattern in ('host-prefix*.c15.json', 'host-service.c15.json', 'request-plan.c15.json',
                    'principal/*request.json', 'critic-spool/*/dispatch.json'):
        paths.update(cycle.glob(pattern))
    result = {}
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        if path.resolve() != root / relative:
            raise ValueError('workflow artifact escapes retained run')
        result[relative] = witness(path)
    return result


def write_wait_receipt(configuration, cycle_directory, kind, *, state='WAIT', job_id=None):
    if kind not in ('readiness', 'service_resume', 'principal', 'principal_correction', 'same_job') or state not in ('WAIT', 'ATTENTION'):
        raise ValueError('known workflow wait required')
    if (kind == 'same_job') != (state == 'ATTENTION'):
        raise ValueError('same-job uncertainty requires attention')
    if kind == 'same_job' and job_id is None:
        raise ValueError('same-job attention requires exact durable job identity')
    if job_id is not None and (type(job_id) is not str or not re.fullmatch('[0-9a-f]{64}', job_id)):
        raise ValueError('exact durable job identity required')
    root = Path(configuration['run_directory']).resolve()
    cycle = Path(cycle_directory).resolve()
    match = re.fullmatch(r'cycle-(\d{2,})', cycle.name)
    if not match or cycle.parent != root / 'execution':
        raise ValueError('retained execution cycle required')
    index = int(match[1])
    if cycle.name != f'cycle-{index:02d}':
        raise ValueError('canonical execution cycle required')
    receipt = dict(schema=SCHEMA, state=state, kind=kind, run_id=configuration['run_id'],
        run_directory=str(root), cycle_index=index,
        request_id=f"{configuration['run_id']}-cycle-{index:02d}",
        configuration_sha256=digest(configuration),
        boss_commit=configuration['host_runtime']['boss_commit'],
        schedule_sha256=configuration['host_runtime']['schedule']['sha256'],
        job_id=job_id, artifacts=_artifacts(configuration, cycle, kind))
    receipt['receipt_id'] = digest(receipt)
    path = cycle / 'workflow-wait' / (kind + '.json')
    if path.exists():
        old = read_wait_receipt(path, configuration=configuration)
        # Evidence can grow after a WAIT; retained members may never change.
        for key in receipt:
            if key not in ('artifacts', 'receipt_id') and receipt[key] != old[key]:
                raise ValueError('existing workflow wait identity differs')
        receipt = old
    _publish(path, receipt)
    return outcome(path, receipt)


def read_wait_receipt(path, expected_sha256=None, configuration=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('workflow receipt must not be a link')
    raw = _read(path)
    receipt = json.loads(raw)
    fields = {'schema','state','kind','run_id','run_directory','cycle_index','request_id',
              'configuration_sha256','boss_commit','schedule_sha256','job_id','artifacts','receipt_id'}
    if (type(receipt) is not dict or set(receipt) != fields or canonical(receipt) != raw or
            receipt['schema'] != SCHEMA or receipt['receipt_id'] != digest({k:v for k,v in receipt.items() if k != 'receipt_id'}) or
            (expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256)):
        raise ValueError('canonical exact workflow receipt required')
    for name, pattern in (('receipt_id','[0-9a-f]{64}'),('configuration_sha256','[0-9a-f]{64}'),
                          ('schedule_sha256','[0-9a-f]{64}'),('boss_commit','[0-9a-f]{40}'),
                          ('run_id','[A-Za-z0-9_-]{1,128}')):
        if type(receipt[name]) is not str or not re.fullmatch(pattern,receipt[name]):
            raise ValueError('workflow identity field differs')
    job_id=receipt['job_id']
    if ((receipt['kind']=='same_job' and job_id is None) or
            (job_id is not None and (type(job_id) is not str or not re.fullmatch('[0-9a-f]{64}',job_id)))):
        raise ValueError('exact retained job identity required')
    index = receipt['cycle_index']
    if (type(index) is not int or index < 0 or receipt['state'] not in ('WAIT','ATTENTION') or
            receipt['kind'] not in ('readiness','service_resume','principal','principal_correction','same_job') or
            (receipt['kind'] == 'same_job') != (receipt['state'] == 'ATTENTION') or
            receipt['request_id'] != f"{receipt['run_id']}-cycle-{index:02d}"):
        raise ValueError('workflow receipt identity differs')
    root = Path(receipt['run_directory'])
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError('absolute retained run required')
    cycle = root / 'execution' / f'cycle-{index:02d}'
    if path.resolve() != cycle / 'workflow-wait' / (receipt['kind'] + '.json'):
        raise ValueError('workflow receipt belongs to another cycle')
    if configuration is not None and (
            digest(configuration) != receipt['configuration_sha256'] or
            configuration['run_id'] != receipt['run_id'] or Path(configuration['run_directory']).resolve() != root or
            configuration['host_runtime']['boss_commit'] != receipt['boss_commit'] or
            configuration['host_runtime']['schedule']['sha256'] != receipt['schedule_sha256']):
        raise ValueError('workflow configuration differs')
    if type(receipt['artifacts']) is not dict or not receipt['artifacts']:
        raise ValueError('retained workflow artifacts required')
    required = {'host-identity.c15.json', f'execution/cycle-{index:02d}/host-preparation.c15.json',
                f'execution/cycle-{index:02d}/actual-critic-request.json'}
    if receipt['kind'] in ('principal','principal_correction'):
        required |= {f'execution/cycle-{index:02d}/request-plan.c15.json',
                     f'execution/cycle-{index:02d}/principal/session-request.json'}
    if receipt['kind'] == 'principal_correction':
        required.add(f'execution/cycle-{index:02d}/principal/classroom-correction-request.json')
    if receipt['kind'] == 'service_resume':required.add(f'execution/cycle-{index:02d}/host-service.c15.json')
    if not required <= receipt['artifacts'].keys():
        raise ValueError('required retained workflow artifacts missing')
    for name, expected in receipt['artifacts'].items():
        if (type(name) is not str or type(expected) is not dict or set(expected)!={'sha256','bytes'} or
                type(expected['bytes']) is not int or expected['bytes']<0 or
                type(expected['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',expected['sha256'])):
            raise ValueError('exact artifact witness required')
        member = root / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or member.resolve() != member or
                member.relative_to(root).as_posix() != name or witness(member) != expected):
            raise ValueError('retained workflow artifact changed')
    return receipt


def outcome(path, receipt=None):
    path = Path(path)
    receipt = receipt if receipt is not None else read_wait_receipt(path)
    return dict(status='workflow_wait' if receipt['state'] == 'WAIT' else 'workflow_attention',
                receipt_path=str(path.resolve()), receipt_sha256=witness(path)['sha256'], wait_receipt=receipt)


class WorkflowPending(Exception):
    def __init__(self, result):
        self.result = result
        self.exit_code = 4 if result['wait_receipt']['state'] == 'ATTENTION' else 3
        super().__init__('retained workflow pending')


def pending_receipts(configuration, cycle_directory):
    directory = Path(cycle_directory) / 'workflow-wait'
    result = []
    for path in sorted(directory.glob('*.json')):
        if path.name.endswith('.resolved.json'):
            continue
        receipt = read_wait_receipt(path, configuration=configuration)
        resolved = path.with_name(path.stem + '.resolved.json')
        if resolved.exists():
            if resolved.is_symlink():raise ValueError('workflow resolution must not be a link')
            marker = json.loads(_read(resolved))
            if (type(marker) is not dict or set(marker) != {'wait_sha256','admitted_artifacts'} or
                    marker['wait_sha256'] != witness(path)['sha256'] or
                    canonical(marker) != _read(resolved) or
                    type(marker['admitted_artifacts']) is not dict or not marker['admitted_artifacts']):
                raise ValueError('workflow resolution differs')
            root=Path(configuration['run_directory']).resolve()
            for name, expected in marker['admitted_artifacts'].items():
                member=root / name
                if (type(name) is not str or Path(name).is_absolute() or '..' in Path(name).parts or
                        member.resolve()!=member or member.relative_to(root).as_posix()!=name or
                        witness(member)!=expected):
                    raise ValueError('admitted workflow artifact changed')
            continue
        result.append(outcome(path, receipt))
    return result


def resolve_wait(result, admitted_paths):
    receipt = read_wait_receipt(result['receipt_path'], result['receipt_sha256'])
    root = Path(receipt['run_directory'])
    artifacts = {Path(p).resolve().relative_to(root).as_posix(): witness(p) for p in admitted_paths}
    if not artifacts:
        raise ValueError('actual admitted artifact required to resolve wait')
    path = Path(result['receipt_path'])
    _publish(path.with_name(path.stem + '.resolved.json'),
             dict(wait_sha256=result['receipt_sha256'], admitted_artifacts=artifacts))

def resume_admission(configuration, expected_sha256=None):
    """An event may resume exactly its retained cycle, never authorize a new one."""
    root = Path(configuration['run_directory'])
    paths = sorted(root.glob('execution/cycle-*/workflow-wait/*.json'))
    paths = [p for p in paths if not p.name.endswith('.resolved.json')]
    if expected_sha256 is not None:
        if type(expected_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
            raise ValueError('exact resume receipt SHA256 required')
        matches = [p for p in paths if witness(p)['sha256'] == expected_sha256]
        if len(matches) != 1:
            raise ValueError('unique retained resume receipt required')
        receipt = read_wait_receipt(matches[0], expected_sha256, configuration)
        if receipt['state'] != 'WAIT':
            raise ValueError('attention is not automatic retry authority')
        # A later unresolved boundary cannot be bypassed with an older event.
        pending = []
        for directory in sorted({p.parent.parent for p in paths}):
            pending.extend(pending_receipts(configuration, directory))
        if pending and any(p['receipt_sha256'] != expected_sha256 for p in pending):
            raise WorkflowPending(pending[-1])
        return receipt['cycle_index'] + 1
    for directory in sorted({p.parent.parent for p in paths}):
        pending = pending_receipts(configuration, directory)
        if pending:
            raise WorkflowPending(pending[-1])
    return None
