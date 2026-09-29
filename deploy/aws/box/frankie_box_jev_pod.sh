# Marker: dispatching this script runs NO command on the box. The workflow step "Jev Pod" runs
# research/kalshi/frankie_boss/clm_sidecar/launch.py --jev on the runner instead: one GPU Pod serves Jev's Qwen3-8B chat
# and runs sit_in.py for one classroom-arm discovery day (VARIABLES: STAMP=<name> DAY=YYYYMMDD [MAX_MINUTES=480]
# [WAIT_MINUTES=360] [REPORT_NUMBER=N]); his claims, comparison, report and receipt come back to S3
# (clm-sidecar/<STAMP>/jev/) and the run's artifact, and the Pod is always deleted. No Granite. After the Pod the runner
# writes JEV REPORT #N (clm_sidecar/jev_report.py; N = REPORT_NUMBER, the day's number from the box reports step, else the
# next free number on S3) and prints it in full. Spec: SPEC-experiment-orchestrator.md, section "Jev".
echo "frankie_box_jev_pod.sh is carried out by the workflow on the runner; it never runs on the box" >&2
exit 2
