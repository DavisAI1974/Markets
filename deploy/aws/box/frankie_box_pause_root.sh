# Explicit user-authorized checkpoint handoff of one identified native ROOT.
# No source writes, evidence deletion, instance control or calculation launch.
set -eu
: "${DIRECTORY:?existing Monday calculation root required}"
: "${CHECKPOINT_DIR:?existing recovery checkpoint directory required}"
: "${EXPECTED_PID:?recorded ROOT PID required}"
: "${EXPECTED_PROCESS_TOKEN:?recorded boot and process-start identity required}"
: "${BINDING_SHA256:?original source binding hash required}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /opt/frankie-box/venv/bin/python -I -S -B - "$DIRECTORY" "$CHECKPOINT_DIR" \
  "$EXPECTED_PID" "$EXPECTED_PROCESS_TOKEN" "$BINDING_SHA256" "${HANDOFF:-parallel-boundary}" <<'PY'
import gzip
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import sys
import time

root = Path(sys.argv[1]).resolve(strict=True)
checkpoint_dir = Path(sys.argv[2]).resolve(strict=True)
pid = int(sys.argv[3])
expected = sys.argv[4]
binding_hash = sys.argv[5]
mode = sys.argv[6]
terminal = mode in ('terminal-finalize', 'terminal-projection', 'terminal-digest')
terminal_stage = {'terminal-projection': 'root-projection', 'terminal-digest': 'root-digest'}.get(mode, 'root-native-finalize')
target = 464000
if (not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations'))
        or not checkpoint_dir.is_relative_to(root / 'work' / 'bedrock') or pid <= 0
        or mode not in ('parallel-boundary', 'native-workers', 'terminal-finalize', 'terminal-projection', 'terminal-digest')):
    raise SystemExit('explicit existing Monday root, checkpoint generation and handoff mode required')
binding_raw = (root / 'source-binding.json').read_bytes()
if hashlib.sha256(binding_raw).hexdigest() != binding_hash:
    raise SystemExit('original source binding hash differs')
control_receipt = root / ('pause-for-' + mode + '-' + str(pid) + '.json')
if control_receipt.exists():
    raise SystemExit('pause receipt already exists; inspect it instead of repeating process control')
deadline = time.monotonic() + 720
while True:
    progress = json.loads((root / 'progress.json').read_text())
    saved = json.loads((root / 'checkpoints.json').read_text())
    if terminal:
        if (saved.get('pid') != pid or saved.get('process_token') != expected
                or saved.get('last_event') != 'read_verified'):
            raise SystemExit('verified checkpoint must belong to the live ROOT')
        candidate = checkpoint_dir / saved['name']
        if candidate.parent != checkpoint_dir:
            raise SystemExit('checkpoint path differs')
        if json.loads(candidate.read_bytes()).get('locked') is True:
            break
    elif mode != 'native-workers' or (
            saved.get('last_event') == 'read_verified' and time.time()-saved.get('at',0) <= 90):
        break
    if (progress.get('pid') != pid or progress.get('process_token') != expected
            or progress.get('failed') != 0 or progress.get('stage') != (terminal_stage if terminal else 'root-native-records')
            or time.monotonic() >= deadline):
        raise SystemExit('fresh checkpoint unavailable; ROOT remains running')
    time.sleep(5)
if (progress.get('pid') != pid or progress.get('process_token') != expected
        or progress.get('failed') != 0
        or progress.get('stage') != {'parallel-boundary':'root-native-reconstruct', 'native-workers':'root-native-records', 'terminal-finalize':'root-native-finalize', 'terminal-projection':'root-projection', 'terminal-digest':'root-digest'}[mode]
        or (mode == 'parallel-boundary' and progress.get('completed', target) >= target)
        or saved.get('pid') != pid or saved.get('process_token') != expected
        or saved.get('last_event') != 'read_verified'):
    raise SystemExit('live native process and verified checkpoint identity required')
if mode == 'native-workers' and time.time() - saved.get('at', 0) > 90:
    raise SystemExit('worker handoff waits for a fresh read-verified checkpoint; ROOT remains running')
checkpoint_path = checkpoint_dir / saved['name']
if checkpoint_path.parent != checkpoint_dir or not checkpoint_path.name.startswith('checkpoint-'):
    raise SystemExit('checkpoint path differs')
checkpoint = json.loads(checkpoint_path.read_bytes())
terminal_verification = None
if terminal:
    def canonical(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    def checked_path(value):
        path = Path(value)
        if (not path.is_absolute() or '..' in path.parts
                or not path.is_relative_to(checkpoint_dir)
                or any(p.is_symlink() for p in (path, *path.parents))):
            raise SystemExit('terminal checkpoint path escapes retained generation')
        return path
    chain = [json.loads(checked_path(p).read_bytes()) for p in sorted(
        checkpoint_dir.glob('checkpoint-[0-9][0-9][0-9][0-9][0-9][0-9].json'))]
    previous = None
    for sequence, item in enumerate(chain):
        if (item['sequence'] != sequence or item['event_group_open']
                or item['previous_checkpoint_hash'] != (previous['checkpoint_hash'] if previous else None)
                or item['checkpoint_hash'] != canonical({k:v for k,v in item.items() if k != 'checkpoint_hash'})):
            raise SystemExit('terminal checkpoint chain verification failed')
        if previous and (previous['locked'] or item['completed_mbo_records'] < previous['completed_mbo_records']
                or any(item[k] != previous[k] for k in (
                    'run_id','controller','memory_mode','source_manifest_hash','total_mbo_records'))):
            raise SystemExit('terminal checkpoint chain identity or cursor differs')
        previous = item
    binding = json.loads(binding_raw)
    if (not chain or chain[-1] != checkpoint or checkpoint.get('locked') is not True
            or checkpoint['completed_mbo_records'] != 2032203
            or checkpoint['total_mbo_records'] != 2032203
            or checkpoint['source_manifest_hash'] != binding['source']['manifest_hash']
            or checkpoint['run_id'] != root.name + '-cycle-00'):
        raise SystemExit('complete terminal Monday checkpoint required')
    sequence = checkpoint['sequence']
    descriptor = json.loads(checked_path(checkpoint_dir / ('controller-state-%06d.json' % sequence)).read_bytes())
    runtime = descriptor['runtime']
    if (canonical(descriptor) != checkpoint['controller_state_hash']
            or descriptor.get('schema') != 'FRANKIE_NATIVE_FULL_STATE_V1'
            or descriptor.get('finalized') is not True
            or descriptor['completed_mbo_records'] != 2032203
            or descriptor['driver_identity']['run_id'] != checkpoint['run_id']
            or descriptor['driver_identity']['source_manifest_hash'] != checkpoint['source_manifest_hash']
            or runtime['python'] != sys.version or runtime['cloudpickle'] != '3.1.2'
            or runtime['serializer_sha256'] != ('e2ff73c9d6e6a76fb6ae1e3d712c337adf72c2845dbc15d41e94dc2d957f3cac' if mode in ('terminal-projection', 'terminal-digest') else '629b1355de7539e84fb8142343b182dc06cfe5033aaa3f6bf837962317a5cf76')
            or (mode in ('terminal-projection', 'terminal-digest') and runtime.get('finalization_sha256') != '15164b4521f1bacbdf678354780fe24ca75f0aab4030b00b6b7815411054dc34')
            or runtime['ledger_storage_sha256'] != 'b66361659495d787329a6097384df10bf4f27fc3056b511ee46f53bb7119c760'):
        raise SystemExit('terminal full-state descriptor or deployed runtime differs')
    if set(descriptor['ledgers']) != {'member','lifecycle','legacy'} or any(
            entry['attributes'].get('_closed') is not True or 'storage_schema' in entry
            for entry in descriptor['ledgers'].values()):
        raise SystemExit('all terminal ledgers must be closed and materialized')
    with gzip.open(checked_path(checkpoint_dir / ('adapter-state-%06d.json.gz' % sequence)), 'rb') as stream:
        adapter = json.load(stream)
    if canonical({k:v for k,v in adapter.items() if k != 'state_hash'}) != checkpoint['adapter_state_hash']:
        raise SystemExit('terminal adapter readback differs')
    state = descriptor['driver_state']
    state_path = checked_path(state['path'])
    with state_path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    if (before.st_size != state['bytes'] or actual_hash != state['sha256']
            or identity(before) != identity(after) or identity(after) != identity(state_path.stat())):
        raise SystemExit('terminal full-state bytes failed fresh readback')
    terminal_verification = dict(at=time.time(), checkpoint_hash=checkpoint['checkpoint_hash'],
                                 driver_state=state, completed_mbo_records=2032203,
                                 chain_and_adapter_verified=True, full_state_readback_verified=True)
elif (checkpoint.get('controller_state_hash') is None or checkpoint.get('locked')
        or (mode == 'parallel-boundary' and checkpoint.get('completed_mbo_records', target) >= target)
        or checkpoint.get('completed_mbo_records', -1) > progress.get('completed', -1)):
    raise SystemExit('nonterminal full-state checkpoint at or before live cursor required')
proc = Path('/proc') / str(pid)
handle = os.pidfd_open(pid)
owned = []
# Children of EVERY thread: the digest's helper pools are started from worker threads (bedrock-sources, the table
# jobs), and /proc lists a child only under the thread that created it.
children = set()
for task in (proc / 'task').iterdir():
    try:
        children.update((task / 'children').read_text().split())
    except FileNotFoundError:
        pass
for child in sorted(children, key=int):
    child_pid = int(child)
    child_proc = Path('/proc') / child
    try:
        command = (child_proc / 'cmdline').read_bytes()
        fields = (child_proc / 'stat').read_text().rsplit(')', 1)[1].split()
        if (int(fields[1]) == pid and b'multiprocessing.spawn' in command and b'spawn_main' in command):
            owned.append((child_pid, os.pidfd_open(child_pid)))
    except FileNotFoundError:
        pass
try:
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    actual = Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + fields[19]
    if actual != expected or fields[0] in ('Z', 'X'):
        raise SystemExit('PID no longer identifies the authorized ROOT process')
    if terminal:
        fresh = json.loads((root / 'progress.json').read_bytes())
        if (fresh.get('pid') != pid or fresh.get('process_token') != expected
                or fresh.get('stage') != terminal_stage or fresh.get('failed') != 0
                or (root / 'calculations-receipt.json').exists()):
            raise SystemExit('ROOT advanced; terminal handoff refused without process control')
    signal.pidfd_send_signal(handle, signal.SIGINT)
    signals = ['SIGINT']
    stopped = bool(select.select([handle], [], [], 15)[0])
    if not stopped:
        signal.pidfd_send_signal(handle, signal.SIGTERM)
        signals.append('SIGTERM')
        stopped = bool(select.select([handle], [], [], 15)[0])
    if not stopped:
        raise SystemExit('ROOT did not exit; do not stage a duplicate calculation')
    for child_pid, child_handle in owned:
        if not select.select([child_handle], [], [], 0)[0]:
            signal.pidfd_send_signal(child_handle, signal.SIGTERM)
            if not select.select([child_handle], [], [], 10)[0]:
                raise SystemExit('owned native child remains alive; do not resume')
finally:
    os.close(handle)
    for _, child_handle in owned:
        os.close(child_handle)
# Full checkpoint validation is performed by the existing resume reader. Preserve
# every file and tail here; record the actual pause and the available candidates.
candidates = sorted(checkpoint_dir.glob('checkpoint-[0-9][0-9][0-9][0-9][0-9][0-9].json'))
receipt = dict(
    schema='FRANKIE_ROOT_CHECKPOINT_HANDOFF_PAUSE_V1', at=time.time(),
    pid=pid, process_token=expected, signals=signals, process_exited=True,
    owned_native_child_pids=[child_pid for child_pid,_ in owned], owned_children_exited=True,
    source_binding_sha256=binding_hash, handoff_mode=mode,
    parallel_activation_boundary=target if mode == 'parallel-boundary' else None,
    last_reported_completed=progress['completed'],
    previously_read_verified_checkpoint=str(checkpoint_path),
    previously_read_verified_completed=checkpoint['completed_mbo_records'],
    latest_checkpoint_candidate=str(candidates[-1]) if candidates else None,
    checkpoint_validation='required before resume', preserved_existing_evidence=True,
    terminal_verification=terminal_verification,
    unsaved_tail_may_require_reconstruction=not terminal)
raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
with control_receipt.open('xb') as stream:
    stream.write(raw)
    stream.flush()
    os.fsync(stream.fileno())
if control_receipt.read_bytes() != raw:
    raise SystemExit('pause receipt readback differs')
print(json.dumps(dict(receipt_path=str(control_receipt),
                      bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                      receipt=receipt), sort_keys=True), flush=True)
PY
