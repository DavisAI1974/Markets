# Marker: dispatching this script runs NO command on the box over SSM (a full disk stops the SSM agent from running
# anything). The workflow step "Disk rescue" does it through the EC2 API instead, only with
# VARIABLES=CONFIRM=GREG_GO_DISK_RESCUE_TABLE_0007 (Greg's go: it is a box power action): stop the instance, add the
# one-time boothook deploy/aws/box/frankie_box_disk_rescue_boothook.sh to the user-data beside the existing user-data
# (kept byte for byte), start it, wait for SSM Online, and print the boothook's console lines (the table-0007 stage
# file sizes before deletion, and free disk before and after).
echo "frankie_box_disk_rescue.sh is carried out by the workflow through the EC2 API; it never runs on the box" >&2
exit 2
