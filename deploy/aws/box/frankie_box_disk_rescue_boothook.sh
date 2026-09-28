#cloud-boothook
#!/bin/bash
# One-time disk rescue for the Monday side builder (2026-09-28). The workflow step "Disk rescue" (frankie_box_run.yml,
# script deploy/aws/box/frankie_box_disk_rescue.sh, Greg's go only) adds this part to the instance user-data beside the
# existing user-data and starts the box. cloud-init runs boothooks on every boot, so a marker file makes it run once.
# It prints the sizes of the side builder's table-0007 stage files to the console (read without SSM by
# frankie_box_console.sh: the plan/count byte split of the 461 GB), then deletes ONLY those stage files
# (plans.sqlite, freq.sqlite, final.sqlite, part.sqlite in table-0007/part-*). passes.pkl and every other file stay.
MARK=/var/lib/frankie-disk-rescue-20260928.done
[ -e "$MARK" ] && exit 0
T=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derived/.digest-side-work/table-0007
say() { echo "frankie-disk-rescue: $*" | tee /dev/console; }
say "start $(date -u +%FT%TZ)"
say "df-before $(df -B1 --output=size,used,avail / | tail -1)"
if [ -d "$T" ]; then
  say "passes.pkl $(stat -c '%s %y' "$T/passes.pkl" 2>/dev/null || echo absent)"
  for p in "$T"/part-*; do
    [ -d "$p" ] || continue
    line=$(basename "$p")
    for f in plans freq final part; do
      line="$line $f=$(stat -c %s "$p/$f.sqlite" 2>/dev/null || echo -)"
    done
    say "$line"
  done
  for f in plans freq final part; do
    say "total $f.sqlite $(du -cb "$T"/part-*/$f.sqlite 2>/dev/null | tail -1 | cut -f1)"
  done
  rm -f "$T"/part-*/plans.sqlite "$T"/part-*/freq.sqlite "$T"/part-*/final.sqlite "$T"/part-*/part.sqlite
else
  say "no $T; nothing deleted"
fi
say "df-after $(df -B1 --output=size,used,avail / | tail -1)"
touch "$MARK"
say "done"
