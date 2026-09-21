# Read-only: print part of one file under /opt/frankie-box (logs, receipts, session out). Inputs: FILE (path under
# /opt/frankie-box, e.g. logs/producer-tests.log), MODE (tail | head | grep), LINES (default 120), PATTERN (grep
# mode: an extended regex; prints matches with 3 lines of context). Refuses paths outside /opt/frankie-box.
set -u
ROOT=/opt/frankie-box
FILE="${FILE:-logs/producer-tests.log}"; MODE="${MODE:-tail}"; LINES="${LINES:-120}"; PATTERN="${PATTERN:-}"
case "$FILE" in *..*|/*) echo "FILE must be relative to $ROOT without .."; exit 2;; esac
P="$ROOT/$FILE"; [ -f "$P" ] || { echo "no such file: $P"; ls -la "$(dirname "$P")" 2>/dev/null; exit 2; }
echo "### $P ($(wc -c < "$P") bytes, $(wc -l < "$P") lines, $MODE $LINES)"
case "$MODE" in
  tail) tail -n "$LINES" "$P" ;;
  head) head -n "$LINES" "$P" ;;
  grep) [ -n "$PATTERN" ] || { echo "PATTERN required"; exit 2; }; grep -nE -C 3 -- "$PATTERN" "$P" | head -n "$LINES" ;;
  *) echo "MODE must be tail, head or grep"; exit 2 ;;
esac | cut -c1-400
