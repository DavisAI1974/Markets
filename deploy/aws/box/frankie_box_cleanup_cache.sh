# Explicit cache cleanup only; work, brain, checkpoints, receipts and checkouts are excluded.
set -eu
: "${CODE_ROOT:?staged checkout required}"
case "$CODE_ROOT" in /opt/frankie-box/code/*/markets) ;; *) exit 2;; esac
/opt/frankie-box/venv/bin/python -m pip cache purge
export PYTHONDONTWRITEBYTECODE=1
/opt/frankie-box/venv/bin/python -B - "$CODE_ROOT" <<'PY'
import json, os, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(sys.argv[1])/'deploy/aws/box'))
from frankie_box_stage_code import safe_path, digest, clean_checkout
from frankie_box_prepare_trading_day import save_new
root = safe_path('/opt/frankie-box/code')
removed = []
for transfer in sorted(root.glob('transfer-*')):
    intent_path = safe_path(transfer/'transfer-intent.json')
    pack = safe_path(transfer/'source.pack')
    if not intent_path.is_file() or not pack.is_file():
        continue
    intent = json.loads(intent_path.read_bytes())
    staged = safe_path(root/(intent['commit']+'-'+intent['run_id']))
    receipt_path = safe_path(staged/'staging-receipt.json')
    if not receipt_path.is_file():
        continue
    receipt = json.loads(receipt_path.read_bytes())
    if (receipt.get('status') != 'staged' or receipt['commit'] != intent['commit'] or
            receipt['pack_sha256'] != intent['sha256'] or digest(pack) != intent['sha256']):
        raise ValueError('staged pack identity differs; nothing at this path removed')
    clean_checkout(staged/'markets', intent['commit'])
    removal = dict(path=str(pack), bytes=pack.stat().st_size, sha256=intent['sha256'],
                   retained_checkout=str(staged/'markets'), reason='redundant completed source transfer cache')
    save_new(transfer/'cache-removal-receipt.json', removal)
    pack.unlink()
    descriptor = os.open(transfer, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    removed.append(removal)
print(json.dumps(dict(removed=removed, bytes_reclaimed=sum(x['bytes'] for x in removed)), sort_keys=True))
PY
df -h /
