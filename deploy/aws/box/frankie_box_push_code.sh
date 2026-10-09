# Push route (S10, Greg 2026-10-09: "code fixes on the box the moment they are pushed"): stage one exact commit into a
# fresh checkout from a presigned S3 GET, in seconds, with no GitHub runner. The old route (frankie_box_run.yml
# ACTION=stage -> frankie_stage_code.yml -> frankie_box_stage_code.sh/.py) stays untouched as the fallback.
#
# Sent as an SSM AWS-RunShellScript body with leading literal assignments (deploy/aws/ssm_run_sh.preamble, or
# frankie_box_push_bundle.py parameters). POSIX sh. Handles no credential: the only capability is the presigned URL,
# which is never printed.
#   MARKETS_SHA    full 40-hex commit to stage
#   BUNDLE_URL     presigned https GET (an *.amazonaws.com host) of the pack frankie_box_push_bundle.py wrote
#   BUNDLE_SHA256  sha256 of that pack
#   BUNDLE_BYTES   optional: its exact byte count
#   BUNDLE_KIND    pack (default): the commit and its whole tree, the old helper's FRANKIE_SOURCE_PACK_V1 object set
#                  delta: only the objects BASE_SHA's tree lacks; the box's staged checkout of BASE_SHA supplies the rest
#                  (its pack files are hard-linked in, never referenced through alternates)
#   BASE_SHA       delta only: a commit that has a staged checkout under CODE_BASE
#   CODE_BASE      default /opt/frankie-box/code; a local test may point it elsewhere, and only then is a file:// URL taken
#
# Result, laid out exactly like a staged checkout so every consumer finds it (frankie_box_cpu_watch
# newest_staged_checkout, frankie_box_cleanup_code.sh, the CODE_ROOT gates of the runner scripts):
#   <CODE_BASE>/<MARKETS_SHA>-push-<utc stamp>/markets          git init --template=, objects by index-pack, .git/shallow,
#                                                               detached at MARKETS_SHA
#   <CODE_BASE>/<MARKETS_SHA>-push-<utc stamp>/staging-intent.json   written before the import
#   <CODE_BASE>/<MARKETS_SHA>-push-<utc stamp>/staging-receipt.json  FRANKIE_INACTIVE_CODE_STAGING_RECEIPT_V1, written
#                                                               last, by the checkout's own frankie_box_stage_code helper
#                                                               after its clean_checkout (raw bytes and modes) passes
#   <CODE_BASE>/current -> that markets directory (atomic: ln -s to a temp name, mv -T). A pointer for people and the
#                                                               parent only: safe_path refuses symlinks, so a CODE_ROOT is
#                                                               always the resolved path (readlink -f), never through it.
# The downloaded pack (<CODE_BASE>/.push-<stamp>.pack) is removed on exit, success or failure; its sha256 stays on the
# receipt. Nothing is created under CODE_BASE until the pack's bytes and sha256 match.
# Prints one line: PUSH_RECEIPT {json}. Any mismatch: PUSH_REFUSED <reason> on stderr and exit 2.
set -eu
START=$(date +%s.%N)
DEFAULT_BASE=/opt/frankie-box/code
CODE_BASE="${CODE_BASE:-$DEFAULT_BASE}"
BUNDLE_KIND="${BUNDLE_KIND:-pack}"
BUNDLE_BYTES="${BUNDLE_BYTES:-}"
BASE_SHA="${BASE_SHA:-}"
fail() { echo "PUSH_REFUSED $*" >&2; exit 2; }
hexn() { case "$1" in ""|*[!0-9a-f]*) return 1;; esac; [ "${#1}" -eq "$2" ]; }

hexn "${MARKETS_SHA:-}" 40 || fail "MARKETS_SHA must be a full 40-hex commit"
hexn "${BUNDLE_SHA256:-}" 64 || fail "BUNDLE_SHA256 must be 64 hex"
[ -n "${BUNDLE_URL:-}" ] || fail "BUNDLE_URL (presigned GET) required"
case "$BUNDLE_KIND" in
  pack) [ -z "$BASE_SHA" ] || fail "BASE_SHA is only for BUNDLE_KIND=delta" ;;
  delta) hexn "$BASE_SHA" 40 || fail "BUNDLE_KIND=delta needs BASE_SHA (full 40-hex)" ;;
  *) fail "BUNDLE_KIND must be pack or delta" ;;
esac
case "$BUNDLE_BYTES" in "") ;; *[!0-9]*) fail "BUNDLE_BYTES must be an integer" ;; esac
case "$CODE_BASE" in /*) ;; *) fail "CODE_BASE must be absolute" ;; esac
case "$CODE_BASE" in *..*|*//*|*/) fail "CODE_BASE must be a normalized path" ;; esac
case "$BUNDLE_URL" in
  https://*)
    HOST=${BUNDLE_URL#https://}; HOST=${HOST%%/*}
    case "$HOST" in *[!A-Za-z0-9.-]*|"") fail "BUNDLE_URL host refused" ;; *.amazonaws.com) ;; *) fail "BUNDLE_URL must be an S3 (amazonaws.com) presigned GET" ;; esac
    PROTO='=https' ;;
  file:///*)
    [ "$CODE_BASE" != "$DEFAULT_BASE" ] || fail "file:// URLs only with a test CODE_BASE"
    PROTO='=file' ;;
  *) fail "BUNDLE_URL must be a presigned https S3 GET" ;;
esac
for tool in git curl sha256sum python3; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool not on the box"
done

# Git with no system/global config, no hooks, no inherited GIT_* redirection (the old helper's environment).
for name in $(env | sed -n 's/^\(GIT_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$name"; done
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0
g() { git -c core.hooksPath=/dev/null -c core.fsmonitor=false -c core.autocrlf=false -c advice.detachedHead=false "$@"; }

# Session 9 rule: staging runs at high best-effort I/O priority (class 2 level 0), ahead of the digest's helpers.
IOP='{"applied":false,"reason":"ionice unavailable or refused","requested":[2,0]}'
SELF=$(exec sh -c 'echo $PPID')
if command -v ionice >/dev/null 2>&1 && ionice -c 2 -n 0 -p "$SELF" 2>/dev/null; then
  IOP='{"applied":true,"requested":[2,0],"via":"ionice"}'
fi

mkdir -p "$CODE_BASE"
[ ! -L "$CODE_BASE" ] || fail "CODE_BASE is a symlink"
RUN_ID="push-$(date -u +%Y%m%dT%H%M%S%NZ)"
ROOT_DIR="$CODE_BASE/$MARKETS_SHA-$RUN_ID"
TARGET="$ROOT_DIR/markets"
PACK="$CODE_BASE/.$RUN_ID.pack"   # beside, not inside, the run directory; removed on exit either way
trap 'rm -f "$PACK"' EXIT

# Delta: the newest staged checkout of BASE_SHA (newest receipt first) whose HEAD is BASE_SHA.
BASE_ROOT=""
if [ "$BUNDLE_KIND" = delta ]; then
  for receipt in $(ls -1t "$CODE_BASE/$BASE_SHA"-*/staging-receipt.json 2>/dev/null); do
    dir=${receipt%/staging-receipt.json}
    [ ! -L "$dir" ] && [ -d "$dir/markets/.git/objects/pack" ] || continue
    grep -q '"status":"staged"' "$receipt" || continue
    [ "$(g -C "$dir/markets" rev-parse HEAD 2>/dev/null)" = "$BASE_SHA" ] || continue
    BASE_ROOT="$dir/markets"; break
  done
  [ -n "$BASE_ROOT" ] || fail "no staged checkout of BASE_SHA $BASE_SHA under $CODE_BASE; send BUNDLE_KIND=pack"
fi

curl -fsS --proto "$PROTO" --max-redirs 0 --connect-timeout 20 --max-time 900 -o "$PACK" "$BUNDLE_URL" \
  || fail "download failed (curl exit $?)"
GOT_BYTES=$(wc -c < "$PACK" | tr -d ' ')
[ -z "$BUNDLE_BYTES" ] || [ "$GOT_BYTES" = "$BUNDLE_BYTES" ] || fail "pack is $GOT_BYTES bytes, pinned $BUNDLE_BYTES"
GOT_SHA=$(sha256sum "$PACK" | cut -d ' ' -f 1)
[ "$GOT_SHA" = "$BUNDLE_SHA256" ] || fail "pack sha256 differs from BUNDLE_SHA256"

# Only a verified pack makes a run directory; a refusal from here on leaves it without a receipt (ignored by every
# consumer, removed by frankie_box_cleanup_code.sh), like an interrupted old-route staging.
mkdir -m 700 "$ROOT_DIR" 2>/dev/null || fail "run directory $ROOT_DIR exists or cannot be made"

BASE_JSON=null; [ -z "$BASE_SHA" ] || BASE_JSON="\"$BASE_SHA\""
printf '{"base_commit":%s,"bundle_kind":"%s","code_root":"%s","commit":"%s","pack_bytes":%s,"pack_sha256":"%s","route":"push","run_id":"%s","schema":"FRANKIE_INACTIVE_CODE_STAGING_INTENT_V1"}' \
  "$BASE_JSON" "$BUNDLE_KIND" "$TARGET" "$MARKETS_SHA" "$GOT_BYTES" "$GOT_SHA" "$RUN_ID" > "$ROOT_DIR/staging-intent.json"

mkdir -m 700 "$TARGET"
g init --quiet --template= "$TARGET" || fail "git init failed"
if [ -n "$BASE_ROOT" ]; then
  for f in "$BASE_ROOT/.git/objects/pack/"pack-*; do
    [ -f "$f" ] || continue
    ln "$f" "$TARGET/.git/objects/pack/" 2>/dev/null || cp "$f" "$TARGET/.git/objects/pack/" || fail "base pack copy failed"
  done
fi
g -C "$TARGET" index-pack --stdin < "$PACK" > /dev/null || fail "index-pack refused the pack"
{ echo "$MARKETS_SHA"; [ -z "$BASE_SHA" ] || echo "$BASE_SHA"; } > "$TARGET/.git/shallow"
[ "$(g -C "$TARGET" cat-file -t "$MARKETS_SHA" 2>/dev/null)" = commit ] || fail "pack lacks commit $MARKETS_SHA"
g -C "$TARGET" checkout --quiet --detach "$MARKETS_SHA" || fail "checkout failed (a delta whose base lacks objects: send BUNDLE_KIND=pack)"
HEAD=$(g -C "$TARGET" rev-parse HEAD)
[ "$HEAD" = "$MARKETS_SHA" ] || fail "HEAD $HEAD differs from MARKETS_SHA"

# The checkout's own helper checks it exactly as a staged one (clean_checkout: HEAD, no tracked change, no untracked
# file, every blob's raw bytes and mode), fsyncs it and writes the receipt last.
FILES=$(python3 -I -S -B - "$TARGET" "$MARKETS_SHA" "$ROOT_DIR" "$GOT_SHA" "$IOP" "$BUNDLE_KIND" "$BASE_SHA" "$RUN_ID" <<'PY'
import json, sys
from pathlib import Path
target, commit, root, checksum, iop, kind, base, run_id = sys.argv[1:9]
target, root = Path(target), Path(root)
try:
    sys.path.insert(0, str(target / 'deploy/aws/box'))
    import frankie_box_stage_code as H
    H.clean_checkout(target, commit)
    _objects, files = H.tree_objects(target, commit)
    H.sync_tree(target)
    H.save_new(root / 'staging-receipt.json', dict(
        schema='FRANKIE_INACTIVE_CODE_STAGING_RECEIPT_V1', status='staged', commit=commit, code_root=str(target),
        pack_sha256=checksum, files=files, intent_sha256=H.digest(root / 'staging-intent.json'),
        active_checkout_changed=False, model_calls=0, source_replays=0, io_priority=json.loads(iop),
        route='push', bundle_kind=kind, base_commit=base or None, run_id=run_id))
except Exception as error:
    print('PUSH_REFUSED verification: %s: %s' % (type(error).__name__, error), file=sys.stderr)
    raise SystemExit(2)
print(files)
PY
) || exit 2

TMP_LINK="$CODE_BASE/.current.$SELF"
ln -s "$TARGET" "$TMP_LINK" || fail "temporary link failed"
mv -T "$TMP_LINK" "$CODE_BASE/current" || { rm -f "$TMP_LINK"; fail "could not repoint $CODE_BASE/current"; }

END=$(date +%s.%N)
SECONDS_TAKEN=$(awk -v a="$START" -v b="$END" 'BEGIN{printf "%.2f", b-a}')
printf 'PUSH_RECEIPT {"base_commit":%s,"bundle_kind":"%s","code_root":"%s","commit":"%s","current":"%s","files":%s,"pack_bytes":%s,"pack_sha256":"%s","receipt":"%s","run_id":"%s","seconds":%s}\n' \
  "$BASE_JSON" "$BUNDLE_KIND" "$TARGET" "$MARKETS_SHA" "$CODE_BASE/current" "$FILES" "$GOT_BYTES" "$GOT_SHA" \
  "$ROOT_DIR/staging-receipt.json" "$RUN_ID" "$SECONDS_TAKEN"
