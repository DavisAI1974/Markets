set -eu
base=$HOME/ng-root-bounded-13eb0f6ab
dir=$(mktemp -d "$base/btrfs-tools.XXXXXX")
cd "$dir"
apt-get download btrfs-progs
dpkg-deb -x ./btrfs-progs_*.deb .
./usr/sbin/mkfs.btrfs --version
printf '%s\n' "$dir/usr/sbin" > "$base/btrfs-tool-path"