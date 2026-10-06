# Legacy filename for the AWS CPU worker controller, run on the GitHub runner.
# The current experiment uses two main-box lanes plus ONE Linux worker lane. Pods are retired.
# VARIABLES: ACTION=plan|status|loop RUN=<saved run> CODE_ROOT=<staged main checkout>
#   BOXES=i-0d17573dbce871520@us-east-1 SLOTS=1 DATA_WORKERS=15 BUDGET_MINUTES=330
# plan/status are read-only. loop requires Greg's explicit AWS compute go.
# Final three-lane launch wiring is still pending; consult HANDOFF_20261006_CHAT_RESET.md.
echo "frankie_box_pod_root_loop.sh is carried out by the workflow on the runner; it never runs on the box" >&2
exit 2
