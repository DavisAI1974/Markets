# Marker: dispatching this script runs NO command on the box. The frankie_box_run.yml step "Pod ROOT loop" runs
# research/kalshi/frankie_boss/pod_root/controller.py on the runner instead (SPEC-pod-day-runner.md): the experiment's
# per-day ROOT on A100 Pods (one day per Pod, every CPU), each finished ROOT moved into the main box's
# /opt/frankie-box/work/experiment-roots/<run>-<day>-a<N> with every file sha256-checked, the Pod cleaned for the next day.
# VARIABLES: ACTION=plan|status|create|loop RUN=<orchestrator run> CODE_ROOT=<staged checkout on the main box>
#   [PODS=id,id,..] [BOXES=i-..@region] [COUNT=n CONFIRM=CREATE_<n>_PODS] [SLOTS=1] [DATA_WORKERS=48] [BUDGET_MINUTES=330]
#   [DATA_CENTERS=..] [VOLUME_GB=500]. plan and status are read-only; create needs CONFIRM; loop never stops or deletes a Pod.
echo "frankie_box_pod_root_loop.sh is carried out by the workflow on the runner; it never runs on the box" >&2
exit 2
