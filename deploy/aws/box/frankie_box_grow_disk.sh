# Expand only the already enlarged canonical root filesystem; no stop or deletion.
set -eu
[ "${DISK_GIB:-}" = 2048 ] || { echo "DISK_GIB=2048 required"; exit 2; }
ROOT_DEVICE=$(findmnt -n -o SOURCE /)
[ "$(readlink -f "$ROOT_DEVICE")" = /dev/nvme0n1p1 ] || { echo "unexpected root device"; exit 2; }
[ "$(findmnt -n -o FSTYPE /)" = ext4 ] || { echo "expected ext4 root"; exit 2; }
[ "$(blockdev --getsize64 /dev/nvme0n1)" -ge 2199023255552 ] || { echo "EBS expansion not visible"; exit 2; }
# The root is full: growpart temporary files must use RAM-backed /run.
export TMPDIR=/run
growpart /dev/nvme0n1 1 || {
  [ "$(blockdev --getsize64 /dev/nvme0n1p1)" -ge 2196875771904 ] || exit 1
}
resize2fs /dev/nvme0n1p1
df -B1 --output=source,size,used,avail,target /
lsblk -b -o NAME,SIZE,TYPE,MOUNTPOINT /dev/nvme0n1
