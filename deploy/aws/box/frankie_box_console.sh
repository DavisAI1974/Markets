# Read-only marker: dispatching this script runs NO command on the box. The workflow instead reads the instance's
# system console log (EC2 GetConsoleOutput, latest) and its status checks from the EC2 API, which work when the box's
# command runner cannot (for example a full disk). The kernel log shows out-of-memory kills and filesystem errors.
echo "frankie_box_console.sh is read through the EC2 API by the workflow; it never runs on the box" >&2
exit 2
