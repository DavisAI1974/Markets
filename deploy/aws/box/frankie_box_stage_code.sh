# Inactive source inventory/staging only. Reviewed helper bytes arrive from the
# dispatch checkout through ssm_run_sh.py literal assignments; no box code is imported.
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${ACTION:?inventory or stage required}"
: "${CODE_B64:?reviewed helper bytes required}"
: "${CODE_SHA256:?reviewed helper sha256 required}"
case "$MARKETS_SHA" in *[!0-9a-f]*) echo "invalid commit" >&2; exit 2;; esac
[ "${#MARKETS_SHA}" -eq 40 ] || { echo "full commit required" >&2; exit 2; }
case "$CODE_SHA256" in *[!0-9a-f]*) echo "invalid helper hash" >&2; exit 2;; esac
[ "${#CODE_SHA256}" -eq 64 ] || { echo "helper hash required" >&2; exit 2; }
GOT=$(printf '%s' "$CODE_B64" | base64 -d | sha256sum | cut -d ' ' -f 1)
[ "$GOT" = "$CODE_SHA256" ] || { echo "reviewed helper hash differs" >&2; exit 2; }
CODE=$(printf '%s' "$CODE_B64" | base64 -d) || { echo "helper decoding refused" >&2; exit 2; }
case "$ACTION" in
  inventory)
    exec python3 -I -S -B -c "$CODE" inventory --commit "$MARKETS_SHA"
    ;;
  stage)
    : "${RUN_ID:?unique staging id required}"
    : "${PACK_SHA256:?source pack hash required}"
    : "${PACK_BYTES:?source pack size required}"
    : "${MAP_URL:?private source capability map required}"
    export MAP_URL
    exec python3 -I -S -B -c "$CODE" stage --commit "$MARKETS_SHA" --run-id "$RUN_ID" \
      --pack-sha256 "$PACK_SHA256" --pack-bytes "$PACK_BYTES"
    ;;
  *) echo "ACTION must be inventory or stage" >&2; exit 2;;
esac
