"""Exact retained-state intake/return for the existing Granite CPU runner.

No fetch, model call or owner publication occurs here. Archive witnesses are supplied
by the original dispatch owner; missing prior state is never treated as a fresh run.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from frankie_box_durable import write_json, write_bytes
from frankie_box_granite_meeting import witness_file

SCHEMA = 'FRANKIE_GRANITE_RUNNER_STATE_V1'


HASH_THREADS_MAX = 8      # whole-file sha256 side by side on pinned threads (hashlib and reads release the GIL)


def files(root):
    """{relative path: {bytes, sha256}} of every runner-state file, in sorted path order. The walk and the symlink refusal
    are serial and come first (the same first error as before); the hashes then run side by side on threads pinned to
    the lane (frankie_box_lane_pin.executor, the Sept-29 primitive) and are assembled in the same sorted order. One file,
    one CPU or no lane helper: hashed in order as before. Values and order unchanged; placement only."""
    names = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('runner state contains a symbolic link')
        if path.is_file() and path.name != '.meeting.lock':
            names.append(path)

    def one(path):
        return {k: v for k, v in witness_file(path).items() if k != 'path'}
    witnesses = None
    if len(names) > 1:
        try:
            import frankie_box_lane_pin as LP
            lane = LP.lane_cpus()
            workers = max(1, min(HASH_THREADS_MAX, len(lane), len(names)))
            if workers > 1:
                with LP.executor('thread', workers, cpus=lane) as pool:
                    witnesses = list(pool.map(one, names))
        except (ImportError, OSError, ValueError, RuntimeError):
            witnesses = None      # no lane helper here: the serial hashes below (same values, same first error)
    if witnesses is None:
        witnesses = [one(path) for path in names]
    return {path.relative_to(root).as_posix(): value for path, value in zip(names, witnesses)}


def prepare(exchange, expected_sha, commit, out, *, archive=None, archive_sha=None, attempt=1, reuse=False):
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('runner needs exact exchange SHA256 and dispatched commit')
    raw = Path(exchange).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('downloaded exchange differs from owner dispatch')
    doc = json.loads(raw)
    if doc.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or doc.get('view') != 'frankie':
        raise ValueError('runner requires the governed Frankie exchange view')
    owner = dict(schema='FRANKIE_GRANITE_RUNNER_OWNER_V1', commit=commit,
                 exchange_sha256=expected_sha, run=doc['run'], day=doc['day'])
    out = Path(out)
    populated = out.exists() and any(out.iterdir())
    if any(p.is_symlink() for p in (out, *out.parents)) or populated and not (reuse and archive):
        raise ValueError('runner intake requires an empty regular output directory')
    if bool(archive) != bool(archive_sha) or attempt > 1 and not archive:
        raise ValueError('runner retry requires its retained archive and exact SHA256; unknown work cannot restart fresh')
    if archive:
        if (not re.fullmatch('[0-9a-f]{64}', archive_sha)
                or witness_file(archive)['sha256'] != archive_sha):
            raise ValueError('retained runner archive differs from owner witness')
        with zipfile.ZipFile(archive) as saved:
            names = saved.namelist()
            if len(names) != len(set(names)) or 'state.json' not in names:
                raise ValueError('retained runner archive repeats or lacks its manifest')
            state = json.loads(saved.read('state.json'))
            if state.get('schema') != SCHEMA or state.get('owner') != owner:
                raise ValueError('retained runner state belongs to another exchange/run/day/commit')
            expected = {'out/' + name for name in state['files']} | {'state.json'}
            if set(names) != expected:
                raise ValueError('retained runner archive is not its complete declared file set')
            for name, pin in state['files'].items():
                relative = PurePosixPath(name)
                info = saved.getinfo('out/' + name)
                if (relative.is_absolute() or '..' in relative.parts or str(relative) != name
                        or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('retained runner archive contains a non-regular owner path')
                content = saved.read(info)
                if len(content) != pin['bytes'] or hashlib.sha256(content).hexdigest() != pin['sha256']:
                    raise ValueError('retained runner file differs: ' + name)
            if json.loads(saved.read('out/runner-owner.json')) != owner:
                raise ValueError('retained runner owner file differs')
            if populated:
                existing = files(out)
                if any(state['files'].get(name) != pin for name, pin in existing.items()):
                    raise ValueError('retained import intake differs from its original archive')
            for name in state['files']:
                if not (out / name).exists():
                    write_bytes(out / name, saved.read('out/' + name))
    else:
        write_json(out / 'runner-owner.json', owner)
    return owner


def seal(out, target):
    out, target = Path(out), Path(target)
    owner = json.loads((out / 'runner-owner.json').read_bytes())
    state = dict(schema=SCHEMA, owner=owner, files=files(out))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('runner return archive already exists; preserve its original witness')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED) as saved:
        saved.writestr('state.json', json.dumps(state, sort_keys=True))
        for name, pin in state['files'].items():
            path = out / name
            with saved.open('out/' + name, 'w') as dest, path.open('rb') as source:
                hashed, size = hashlib.sha256(), 0
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    hashed.update(chunk)
                    size += len(chunk)
                    dest.write(chunk)
            if size != pin['bytes'] or hashed.hexdigest() != pin['sha256']:
                raise ValueError('runner state changed during its return: ' + name)
    result = dict(schema=SCHEMA, owner=owner, archive=witness_file(target),
                  rule='restore complete state before another attempt; owner import still verifies meeting.json')
    write_json(target.with_suffix('.json'), result)
    return result


ADMISSION_SCHEMA = 'FRANKIE_VOICE_ADMISSION_V1'


def admit(out, admission, github_run_id, github_run_attempt, expected_sha, commit, prior_state_sha=None):
    """The owning lane's admission of THIS exact GitHub run, verified before any model setup or call (Step 6 caller
    contract, item 3; CCode's Run.voice_dispatched writes it). Every binding must hold: schema, run/day equal to the
    retained runner-owner.json, exchange sha256 and dispatched commit equal to this run's, github_run_id and
    github_run_attempt equal to GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT, and the predecessor: an admission naming one requires
    the same prior archive sha256 this run restored (a continuation), an admission naming none requires no prior state (a
    fresh run). A durable copy lands in the output tree (sealed with it). Any mismatch raises: the workflow fails before
    setup. GITHUB_RUN_ATTEMPT or concurrency alone never admit."""
    out = Path(out)
    raw = Path(admission).read_bytes()
    value = json.loads(raw)
    owner = json.loads((out / 'runner-owner.json').read_bytes())
    checks = [
        ('schema', value.get('schema'), ADMISSION_SCHEMA),
        ('run', value.get('run'), owner['run']),
        ('day', value.get('day'), owner['day']),
        ('exchange_sha256', value.get('exchange_sha256'), expected_sha),
        ('commit', value.get('commit'), commit),
        ('github_run_id', str(value.get('github_run_id')), str(github_run_id)),
        ('github_run_attempt', str(value.get('github_run_attempt')), str(github_run_attempt)),
    ]
    failed = ['%s: admission %r, this run %r' % (name, got, want) for name, got, want in checks if got != want]
    predecessor = value.get('predecessor')
    if prior_state_sha:
        bound = ((predecessor or {}).get('archive') or {}).get('sha256')
        if bound != prior_state_sha:
            failed.append('predecessor: admission binds archive %r, this run restored %r' % (bound, prior_state_sha))
    elif predecessor is not None:
        failed.append('predecessor: the admission names attempt %r, this run restored no prior state (a fresh run is not '
                      'that continuation)' % predecessor.get('attempt'))
    if failed:
        raise ValueError('owner admission does not admit this exact GitHub run: ' + '; '.join(failed))
    write_bytes(out / 'admission.json', raw)
    return dict(schema=ADMISSION_SCHEMA, admitted=True, github_run_id=str(github_run_id),
                github_run_attempt=str(github_run_attempt), exchange_sha256=expected_sha, commit=commit,
                predecessor=predecessor, admission=witness_file(out / 'admission.json'),
                rule='admitted for this exact run only; model setup/start may follow; nothing here calls a model')


def completed_record(out, exchange):
    """Check recorded config/binding witnesses, not actual execution of a remote host."""
    from frankie_box_brain import read_meeting_record
    from frankie_box_granite_meeting import load_config
    out = Path(out)
    record = read_meeting_record(out / 'meeting.json', exchange_path=exchange, complete=True)
    binding_path = out / 'meeting-binding.json'
    binding = json.loads(binding_path.read_bytes())
    config, config_pin = load_config()
    def same_pin(left, right):
        return all(left.get(k) == right.get(k) for k in ('bytes', 'sha256'))
    if (record['binding']['sha256'] != witness_file(binding_path)['sha256']
            or not same_pin(binding['input'], witness_file(out / 'meeting-input.json'))
            or not same_pin(binding['runtime_config'], config_pin)
            or not same_pin(record['runtime_config'], config_pin)
            or binding['exchange'] != record['exchange']
            or binding['parameters'] != config['proposed_runtime_parameters']
            or record['runtime']['parameters'] != binding['parameters']
            or not same_pin(record['runtime']['binary'], binding['binary'])
            or not same_pin(record['runtime']['model'], binding['model'])
            or binding['binary']['sha256'] != config['pins']['llama_server_sha256']
            or binding['model']['sha256'] != config['pins']['model_sha256']):
        raise ValueError('returned complete meeting differs from its frozen runtime/input binding')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'seal', 'import', 'replay-complete', 'admit'])
    p.add_argument('--out', required=True)
    p.add_argument('--exchange')
    p.add_argument('--exchange-sha256')
    p.add_argument('--commit')
    p.add_argument('--archive')
    p.add_argument('--archive-sha256')
    p.add_argument('--attempt', type=int, default=1)
    p.add_argument('--admission', help='admit: the owning lane\'s FRANKIE_VOICE_ADMISSION_V1 file fetched for this run')
    p.add_argument('--github-run-id', help='admit: this run\'s GITHUB_RUN_ID')
    p.add_argument('--github-run-attempt', help='admit: this run\'s GITHUB_RUN_ATTEMPT')
    p.add_argument('--prior-state-sha256', help='admit: the prior archive sha256 this run restored (a continuation)')
    a = p.parse_args()
    if a.action == 'admit':
        if not (a.admission and a.github_run_id and a.github_run_attempt and a.exchange_sha256 and a.commit):
            p.error('admit requires --admission, --github-run-id, --github-run-attempt, --exchange-sha256 and --commit')
        result = admit(a.out, a.admission, a.github_run_id, a.github_run_attempt, a.exchange_sha256, a.commit,
                       prior_state_sha=a.prior_state_sha256 or None)
    elif a.action == 'replay-complete':
        record = Path(a.out) / 'meeting.json'
        if not record.is_file() or json.loads(record.read_bytes()).get('status') != 'complete':
            p.error('remote model work requires durable owner admission for this exact GitHub run; '
                    'only an existing completed meeting may be replayed until that caller contract is wired')
        from frankie_box_granite_meeting import meeting
        completed_record(a.out, a.exchange)
        # meeting's completed-record branch only repairs publication; it never
        # constructs a server or repeats a model call.
        result = meeting(a.exchange, a.out, inputs_only=True)
    elif a.action == 'seal':
        result = seal(a.out, a.archive)
    else:
        if a.action == 'import' and not a.archive:
            p.error('import requires the complete returned archive and its owner SHA256')
        result = prepare(a.exchange, a.exchange_sha256, a.commit, a.out, archive=a.archive,
                         archive_sha=a.archive_sha256, attempt=a.attempt, reuse=a.action == 'import')
        if a.action == 'import':
            from frankie_box_lane_state import import_meeting_record
            record = Path(a.out) / 'meeting.json'
            if json.loads(record.read_bytes()).get('status') == 'complete':
                completed_record(a.out, a.exchange)
            # The existing importer checks owning plan/ROOT/exchange/currentness,
            # record shape and exact publication destination. The archive binds
            # returned bytes; it is not an attestation that a runtime was executed.
            result = import_meeting_record(a.exchange, record, witness_file(record)['sha256'])
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
