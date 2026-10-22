#!/bin/sh
set -eu
B=/opt/frankie-box/work/family-research-20261022
export FAMILY_RESEARCH_DIR="$B"
export JULIA_DEPOT_PATH="$B/julia-depot"
export JOINT_MODEL_OUT="$B/joint-models-v3"
J="$B/julia-runtime/julia-1.13.2/bin/julia"
S="$JOINT_MODEL_OUT/scripts"
python3 "$B/joint-inputs-v3/scripts/resume_core_parallel.py" > "$JOINT_MODEL_OUT/parallel-resume.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/summarize_joint_models.jl" > "$JOINT_MODEL_OUT/summary.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/analyze_joint_interactions.jl" > "$JOINT_MODEL_OUT/interactions.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/analyze_observed_price_paths.jl" > "$JOINT_MODEL_OUT/price-paths.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/review_saved_layers.jl" > "$JOINT_MODEL_OUT/layer-review.log" 2>&1
python3 - <<'PY'
import json,pathlib
b=pathlib.Path('/opt/frankie-box/work/family-research-20261022/joint-models-v3')
for filename in ['model_run_receipt.json','neural_run_receipt.json']:
    r=json.loads((b/filename).read_text());assert r['status']=='completed' and r['error_rows']==0,(filename,r)
assert json.loads((b/'model_summary_receipt.json').read_text())['all_heldout_alignment_checks_passed']
(b/'complete.json').write_text(json.dumps({'status':'complete','input_version':'joint-inputs-v3','all_models_refit':True,'errors':0,'postprocessing_complete':True,'execution':'committed serial prefix plus isolated parallel remaining tasks; unchanged numerical model configuration'})+'\n')
PY
LAYER_REVIEW_VERSION=v3 python3 "$B/joint-inputs-v3/scripts/summarize_layer_review.py" > "$JOINT_MODEL_OUT/review-summary.log" 2>&1
LAYER_REVIEW_VERSION=v3 python3 "$B/joint-inputs-v3/scripts/flag_research_contradictions.py" > "$JOINT_MODEL_OUT/research-flags.log" 2>&1
python3 "$B/joint-inputs-v3/scripts/compare_full_depth_models.py" > "$JOINT_MODEL_OUT/v1-v3-comparison.log" 2>&1
printf 'models_and_reviews_complete\n'
