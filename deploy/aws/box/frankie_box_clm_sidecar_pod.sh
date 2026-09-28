# Marker: dispatching this script runs NO command on the box. The workflow step "CLM sidecar Pod" runs
# research/kalshi/frankie_boss/clm_sidecar/launch.py on the runner instead: one GPU Pod (Runpod REST v2) learns from the
# dataset the box extract uploaded (VARIABLES: DATASET_KEY=<s3 key> STAMP=<name> [MAX_MINUTES=150]), the outputs come
# back to S3 and the run's artifact, and the Pod is always deleted. Standalone; nothing of Frankie/BOSS is touched.
echo "frankie_box_clm_sidecar_pod.sh is carried out by the workflow on the runner; it never runs on the box" >&2
exit 2
