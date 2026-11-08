set -eu
base=/home/greg/ng-root-bounded-13eb0f6ab
tool="$base/btrfs-tools.x8Y0r4"
out=/mnt/e/tmp/ng-root-bounded-13eb0f6ab/compression
work=$(mktemp -d "$base/btrfs-canary.XXXXXX")
image="$work/only-scratch.img"
scratch="$work/mount"
test -d "$work" && test ! -e "$image"
mkdir "$scratch"
truncate -s 4G "$image"
"$tool/sbin/mkfs.btrfs" -q "$image"
mount -o loop,compress=zstd:1 -- "$image" "$scratch"
trap 'umount -- "$scratch"' EXIT
chown greg:greg "$scratch"
chmod 755 "$work"
findmnt -n -o FSTYPE,OPTIONS --target "$scratch" > "$out/btrfs-mount.txt"
cd "$base"
run () {
  name=$1
  shift
  /usr/bin/time -v -o "$out/$name.time" runuser -u greg -- env     PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1     FRANKIE_ROOT_LEGACY_FRAME_SHARDS=on     venv/bin/python bounded_root.py 20231002 "$scratch/$name" "$@"
}
run btrfs-fresh
run btrfs-resume --save
mv "$out/btrfs-resume.time" "$out/btrfs-save.time"
run btrfs-resume
for mode in btrfs-fresh btrfs-resume; do
  cmp out/02-healthy/spool-comparison.json "$scratch/$mode/spool-comparison.json"
  file="$scratch/$mode/work/derived/.rows/frames.jsonl"
  sync -f "$file"
  stat -c '%s %b %B' "$file" > "$out/$mode-stat.txt"
done
runuser -u greg -- env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1   venv/bin/python check_sqlite.py 20231002 "$scratch/btrfs-resume" "$scratch/checked-clock.sqlite"   > "$out/btrfs-sqlite.json"
"$tool/bin/btrfs" filesystem usage -b "$scratch" > "$out/btrfs-usage.txt"
cat "$out/btrfs-mount.txt" "$out/btrfs-fresh-stat.txt" "$out/btrfs-resume-stat.txt" "$out/btrfs-sqlite.json"