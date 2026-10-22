#!/bin/sh
set -eu
B=/opt/frankie-box/work/family-research-20261022
export FAMILY_RESEARCH_DIR="$B" JULIA_DEPOT_PATH="$B/julia-depot" OPENBLAS_NUM_THREADS=1
export JOINT_MODEL_OUT="$B/joint-models-v4-candidate-20261022"
J="$B/julia-runtime/julia-1.13.2/bin/julia"
S="$JOINT_MODEL_OUT/scripts"
"$J" --startup-file=no --project="$B/julia-model-env" "$B/full-context-audit/scripts/build_expanded_candidate.jl" > "$JOINT_MODEL_OUT/build.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/test_model_rules.jl" > "$JOINT_MODEL_OUT/one-pass-tests.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/run_joint_models.jl" > "$JOINT_MODEL_OUT/models.log" 2>&1 &
core=$!
"$J" --startup-file=no --project="$B/julia-neural-env" "$S/run_neural_models.jl" > "$JOINT_MODEL_OUT/neural.log" 2>&1 &
neural=$!
printf 'core_pid=%s neural_pid=%s\n' "$core" "$neural" > "$JOINT_MODEL_OUT/fit-pids.txt"
cs=0;ns=0
wait "$core" || cs=$?
wait "$neural" || ns=$?
printf 'core_exit=%s neural_exit=%s\n' "$cs" "$ns" > "$JOINT_MODEL_OUT/fit-exit-status.txt"
test "$cs" -eq 0 && test "$ns" -eq 0
"$J" --startup-file=no --project="$B/julia-model-env" "$S/summarize_joint_models.jl" > "$JOINT_MODEL_OUT/summary.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/analyze_joint_interactions.jl" > "$JOINT_MODEL_OUT/interactions.log" 2>&1
"$J" --startup-file=no --project="$B/julia-model-env" "$S/analyze_observed_price_paths.jl" > "$JOINT_MODEL_OUT/price-paths.log" 2>&1
printf 'all_requested_existing_models_finished; coverage_gate=NOT_PASSED\n' > "$JOINT_MODEL_OUT/complete-candidate.txt"
