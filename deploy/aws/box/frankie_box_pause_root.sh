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
target = 464000
if (not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations'))
        or not checkpoint_dir.is_relative_to(root / 'work' / 'bedrock') or pid <= 0
        or mode not in ('parallel-boundary', 'native-workers')):
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
    if mode != 'native-workers' or (
            saved.get('last_event') == 'read_verified' and time.time()-saved.get('at',0) <= 90):
        break
    if (progress.get('pid') != pid or progress.get('process_token') != expected
            or progress.get('failed') != 0 or progress.get('stage') != 'root-native-records'
            or time.monotonic() >= deadline):
        raise SystemExit('fresh checkpoint unavailable; ROOT remains running')
    time.sleep(5)
if (progress.get('pid') != pid or progress.get('process_token') != expected
        or progress.get('failed') != 0
        or progress.get('stage') != ('root-native-reconstruct' if mode == 'parallel-boundary' else 'root-native-records')
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
if (checkpoint.get('controller_state_hash') is None or checkpoint.get('locked')
        or (mode == 'parallel-boundary' and checkpoint.get('completed_mbo_records', target) >= target)
        or checkpoint.get('completed_mbo_records', -1) > progress.get('completed', -1)):
    raise SystemExit('nonterminal full-state checkpoint at or before live cursor required')
proc = Path('/proc') / str(pid)
handle = os.pidfd_open(pid)
owned = []
for child in (proc / 'task' / str(pid) / 'children').read_text().split():
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
    unsaved_tail_may_require_reconstruction=True)
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
