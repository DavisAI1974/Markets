# Read-only: free space and the largest directories and files under one path in /opt/frankie-box/work (default the
# Monday calculation root's derived tree). Inputs: TARGET (path relative to /opt/frankie-box/work), DEPTH (default 2),
# TOP (default 40). Prints only; never writes, never signals.
set -u
TARGET="${TARGET:-monday-calculations/full-20211004-20260927-r1-48/work/derived}"; DEPTH="${DEPTH:-2}"; TOP="${TOP:-40}"
case "$TARGET" in *..*|/*) echo "TARGET must be relative to /opt/frankie-box/work without .."; exit 2;; esac
case "$DEPTH$TOP" in *[!0-9]*) echo "DEPTH and TOP must be integers"; exit 2;; esac
P="/opt/frankie-box/work/$TARGET"
[ -d "$P" ] || { echo "no such directory: $P"; exit 2; }
echo "### free"; df -B1 --output=size,used,avail / | tail -1
echo "### largest directories under $P (depth $DEPTH, bytes)"
du -x -B1 --max-depth="$DEPTH" "$P" 2>/dev/null | sort -rn | head -n "$TOP"
echo "### largest files under $P (bytes)"
find "$P" -xdev -type f -printf '%s\t%TY-%Tm-%TdT%TH:%TM\t%p\n' 2>/dev/null | sort -rn | head -n "$TOP"
