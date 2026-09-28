# Write (or show, or remove) the Pods the session's reading lane spreads over: /opt/frankie-box/pods.json (Greg,
# 2026-09-28: several A100 Pods, "if they cut clock time"). The session (frankie_box_boss_session.py engine_reach) reads
# it at its next engine reach: the FIRST Pod is the BOSS (it must be healthy; the writing and summaries run there), every
# other healthy Pod joins the reading, merge and classroom fan-out, one call per Pod at a time; an unhealthy one is noted
# and left out. Without the file the session uses its --pod (POD_ID_DEFAULT). Inputs: PODS (comma-separated RunPod Pod
# ids, required to write), ACTION (show | write | remove; default show). Starts, stops and bills nothing.
set -u
ROOT=/opt/frankie-box; F="$ROOT/pods.json"; ACTION="${ACTION:-show}"
case "$ACTION" in
  show) [ -s "$F" ] && { echo "### $F"; cat "$F"; } || echo "no Pod list on the box (the session reads on its --pod only)";;
  remove) [ -s "$F" ] && { mv "$F" "$ROOT/receipts/pods-removed-$(date +%s).json"; echo "moved aside (nothing deleted)"; } || echo "nothing to remove";;
  write)
    PODS="${PODS:-}"
    # POSIX tests: SSM runs this under sh (dash).
    printf '%s\n' "$PODS" | grep -Eq '^[a-z0-9]{6,40}(,[a-z0-9]{6,40})*$' || { echo "PODS must be comma-separated RunPod Pod ids"; exit 2; }
    [ "$(printf '%s\n' "$PODS" | tr ',' '\n' | sort | uniq -d)" = "" ] || { echo "PODS must be distinct"; exit 2; }
    [ -s "$F" ] && mv "$F" "$ROOT/receipts/pods-replaced-$(date +%s).json"
    printf '{"schema":"FRANKIE_BOX_PODS_V1","pods":["%s"],"written_at":%s}\n' "$(printf '%s' "$PODS" | sed 's/,/","/g')" "$(date +%s)" > "$F"
    echo "### $F"; cat "$F";;
  *) echo "ACTION must be show, write or remove"; exit 2;;
esac
