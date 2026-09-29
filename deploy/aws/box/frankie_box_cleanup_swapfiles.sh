# Remove named, inactive swap files left on a worker box by older runs (Greg, 2026-09-29: "Do a disk clean before you
# put anyone else on linux"). i-08cee carried two 17 GB swap files from the August NG step-1 runs under /mnt/markets that
# no swap device uses. Deletes ONLY the files named in FILES (comma list of absolute paths); each must be a regular file
# whose name starts with .ng_step1_swap under /mnt/markets, must not be listed in /proc/swaps (active swap) and must not
# be open by any process. Anything else is refused and nothing is removed. Prints each removal with its bytes, then the
# free space. SSM runs this under sh: POSIX only.
set -u
: "${FILES:?comma list of swap files required}"
case "$FILES" in *..*) echo "no .. in FILES" >&2; exit 2;; esac
for F in $(echo "$FILES" | tr ',' ' '); do
  case "$F" in /mnt/markets/.ng_step1_swap*) ;; *) echo "refused: $F is not a /mnt/markets/.ng_step1_swap* file" >&2; exit 2;; esac
  [ -f "$F" ] && [ ! -L "$F" ] || { echo "refused: $F is not a regular file" >&2; exit 2; }
  if grep -qF "$F" /proc/swaps; then echo "refused: $F is active swap" >&2; exit 2; fi
  for P in /proc/[0-9]*/fd/*; do
    [ "$(readlink "$P" 2>/dev/null)" = "$F" ] && { echo "refused: $F is open ($P)" >&2; exit 2; }
  done
done
for F in $(echo "$FILES" | tr ',' ' '); do
  B=$(stat -c %s "$F"); rm -f -- "$F" && echo "removed $F $B bytes"
done
df -h / | tail -1
