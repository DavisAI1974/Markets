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
  "$EXPECTED_PID" "$EXPECTED_PROCESS_TOKEN" "$BINDING_SHA256" 464000 <<'PY'
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
target = int(sys.argv[6])
if (not root.is_relative_to(Path('/opt/frankie-box/work/monday-calculations'))
        or not checkpoint_dir.is_relative_to(root / 'work' / 'bedrock') or pid <= 0 or target != 464000):
    raise SystemExit('explicit existing Monday root, checkpoint generation and boundary required')
binding_raw = (root / 'source-binding.json').read_bytes()
if hashlib.sha256(binding_raw).hexdigest() != binding_hash:
    raise SystemExit('original source binding hash differs')
control_receipt = root / ('pause-for-parallel-' + str(pid) + '.json')
if control_receipt.exists():
    raise SystemExit('pause receipt already exists; inspect it instead of repeating process control')
progress = json.loads((root / 'progress.json').read_text())
saved = json.loads((root / 'checkpoints.json').read_text())
if (progress.get('pid') != pid or progress.get('process_token') != expected
        or progress.get('stage') != 'root-native-reconstruct'
        or progress.get('completed', target) >= target
        or saved.get('pid') != pid or saved.get('process_token') != expected
        or saved.get('last_event') != 'read_verified'):
    raise SystemExit('live reconstruction and verified checkpoint identity required')
checkpoint_path = checkpoint_dir / saved['name']
if checkpoint_path.parent != checkpoint_dir or not checkpoint_path.name.startswith('checkpoint-'):
    raise SystemExit('checkpoint path differs')
checkpoint = json.loads(checkpoint_path.read_bytes())
if (checkpoint.get('controller_state_hash') is None or checkpoint.get('locked')
        or checkpoint.get('completed_mbo_records', target) >= target):
    raise SystemExit('nonterminal full-state checkpoint before the boundary required')
proc = Path('/proc') / str(pid)
handle = os.pidfd_open(pid)
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
finally:
    os.close(handle)
# Full checkpoint validation is performed by the existing resume reader. Preserve
# every file and tail here; record the actual pause and the available candidates.
candidates = sorted(checkpoint_dir.glob('checkpoint-[0-9][0-9][0-9][0-9][0-9][0-9].json'))
receipt = dict(
    schema='FRANKIE_ROOT_CHECKPOINT_HANDOFF_PAUSE_V1', at=time.time(),
    pid=pid, process_token=expected, signals=signals, process_exited=True,
    source_binding_sha256=binding_hash, parallel_activation_boundary=target,
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
