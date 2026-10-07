# Legacy filename (the Pod era): the marker that routes frankie_box_run.yml to the AWS CPU Linux lane controller
# (research/kalshi/frankie_boss/pod_root/controller.py) on the GitHub runner. Pods are retired; the experiment uses two
# main-box lanes plus ONE Linux worker lane (i-0d17573dbce871520, 16 CPUs, SLOTS=1). Dispatching this script runs NO
# command on the box: the workflow step "AWS CPU Linux lane controller" runs the controller on the runner, a BOUNDED job.
# VARIABLES: ACTION=plan|status|loop|resume|stop RUN=<saved run> CODE_ROOT=<staged main checkout>
#   BOXES=i-0d17573dbce871520@us-east-1 SLOTS=1 [DATA_WORKERS=15] [BUDGET_MINUTES=330] [JOB=<RUN>-YYYYMMDD-aN]
# plan/status are read-only. loop/resume require Greg's explicit AWS compute go; a loop's budget end is recorded as
# budget_expired (never completion). JOB is required for resume/stop and refused otherwise. Retired Pod inputs refuse.
# The controller's LIFETIME beyond the bounded runner is the main-box route: script=deploy/aws/box/frankie_box_cpu_controller.sh
# (ACTION=preflight|start|status|stop|clear_stop), a run-bound systemd unit from the staged checkout; an S3 lease keeps a
# runner loop and a main-box service off the same run.
echo "frankie_box_pod_root_loop.sh is carried out by the workflow on the runner; it never runs on the box" >&2
exit 2
