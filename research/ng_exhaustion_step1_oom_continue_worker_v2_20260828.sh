#!/usr/bin/env bash
set -euo pipefail

status_file="$CONT_ROOT/WORKER_STATUS.json"
success_marker="$CONT_ROOT/FINALIZATION_SUCCESS"

write_status() {
  rc="$1"
  RC="$rc" "$BASE/venv/bin/python" - <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ['CONT_ROOT'])
rc = int(os.environ['RC'])
tar = root / 'results.tar.gz'
manifest = root / 'results' / 'RESULT_FILE_MANIFEST.json'
receipt = root / 'results' / 'STEP1_DUAL_FULL_MBO_RECEIPT.json'
marker = root / 'FINALIZATION_SUCCESS'
finalization_complete = marker.is_file() and tar.is_file() and manifest.is_file() and receipt.is_file()
body = {
    'schema': 'NG_EXHAUSTION_STEP1_OOM_CONTINUE_WORKER_STATUS_V2_20260828',
    'status': 'SUCCESS' if rc == 0 and finalization_complete else 'FAILURE',
    'exit_code': rc,
    'finalization_complete': finalization_complete,
    'receipt_present': receipt.is_file(),
    'result_manifest_present': manifest.is_file(),
    'results_tar_present': tar.is_file(),
}
if rc == 0 and not finalization_complete:
    body['failure_reason'] = 'FINALIZATION_INCOMPLETE_DESPITE_ZERO_EXIT'
if tar.is_file():
    body['results_tar_sha256'] = hashlib.sha256(tar.read_bytes()).hexdigest()
if manifest.is_file():
    data = json.loads(manifest.read_text())
    body['result_file_manifest_sha256'] = data.get('manifest_sha256')
if receipt.is_file():
    data = json.loads(receipt.read_text())
    body['step1_receipt_sha256'] = data.get('receipt_sha256')
(root / 'WORKER_STATUS.json').write_text(json.dumps(body, indent=2, sort_keys=True) + '\n')
PY
  curl --fail --silent --show-error --request PUT --upload-file "$status_file" "$STATUS_PUT_URL" || true
}

finish() {
  rc=$?
  trap - EXIT
  write_status "$rc"
  exit "$rc"
}
trap finish EXIT

cd "$CONT_ROOT/repo"
MPLCONFIGDIR="$CONT_ROOT/matplotlib" PYTHONPATH=research \
  /usr/bin/time -v -o "$CONT_ROOT/resource.txt" \
  "$BASE/venv/bin/python" "$WRAPPER" \
    --parent-manifest research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json \
    --baseline-results "$SOURCE_RUN_ROOT/baseline" \
    --baseline-results-tar-sha256 "$PRIOR_ARCHIVE_SHA256" \
    --raw-mbo "$SOURCE_RUN_ROOT/raw/glbx-mdp3-20211001.mbo.dbn.zst" \
              "$SOURCE_RUN_ROOT/raw/glbx-mdp3-20211003.mbo.dbn.zst" \
              "$SOURCE_RUN_ROOT/raw/glbx-mdp3-20211004.mbo.dbn.zst" \
              "$SOURCE_RUN_ROOT/raw/glbx-mdp3-20211005.mbo.dbn.zst" \
    --resume-native-seconds "$RESUME_NATIVE_SECONDS" \
    --out-dir "$CONT_ROOT/results" | tee "$CONT_ROOT/run.log"

cp "$CONT_ROOT/resource.txt" "$CONT_ROOT/results/RESOURCE_USAGE.txt"
cp "$CONT_ROOT/run.log" "$CONT_ROOT/results/RUN.log"

"$BASE/venv/bin/python" - "$CONT_ROOT/results" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
rows = []
for path in sorted(p for p in root.rglob('*') if p.is_file()):
    rows.append({
        'relative_path': path.relative_to(root).as_posix(),
        'bytes': path.stat().st_size,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    })
manifest = {
    'schema': 'NG_EXHAUSTION_TWO_DAY_FULL_MBO_RESULT_FILE_MANIFEST_V1_20260825',
    'files': rows,
}
manifest['manifest_sha256'] = hashlib.sha256(
    json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
).hexdigest()
(root / 'RESULT_FILE_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print('TWO_DAY_FULL_MBO_RESULT_MANIFEST_SHA256=' + manifest['manifest_sha256'])
PY

tar -C "$CONT_ROOT/results" -czf "$CONT_ROOT/results.tar.gz" .
curl --fail --silent --show-error --request PUT --upload-file "$CONT_ROOT/results.tar.gz" "$RESULT_PUT_URL"
printf 'FINALIZATION_SUCCESS\n' > "$success_marker"
echo TWO_DAY_FULL_MBO_WORKER=PASS
