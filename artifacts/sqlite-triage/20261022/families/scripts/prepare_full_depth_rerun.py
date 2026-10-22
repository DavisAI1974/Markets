"""Stage the complete, unchanged model suite against the frozen v3 inputs."""
import hashlib
import json
import os
import pathlib
import shutil


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    inputs=base/'joint-inputs-v3'; out=base/'joint-models-v3'
    receipt=json.loads((inputs/'model_input_receipt.json').read_text())
    assert receipt['status']=='completed' and receipt['all_v2_columns_values_and_missingness_unchanged']
    assert not out.exists(), 'do not overwrite an existing model run'
    out.mkdir(); scripts=out/'scripts';scripts.mkdir()
    # The input matrix stays frozen, and no fitted state is copied from v1/v2.
    for name in ['model_matrix.jls','model_sample_master.csv','model_feature_registry.csv','model_outcomes.csv','model_input_receipt.json','excluded_predictor_metadata.csv']:
        (out/name).symlink_to(inputs/name)
    for name in ['model_rules.jl','test_model_rules.jl']:
        shutil.copyfile(base/'joint-inputs-v2/scripts'/name,scripts/name)
    for name in ['run_joint_models.jl','run_neural_models.jl','summarize_joint_models.jl',
                 'analyze_joint_interactions.jl','analyze_observed_price_paths.jl','descriptive_math.jl']:
        src=base/'joint-models-v1/scripts'/name
        text=src.read_text()
        if name!='descriptive_math.jl':
            old='const OUT=joinpath(BASE,"joint-models-v1")'
            assert text.count(old)==1, name
            text=text.replace(old,'const OUT=ENV["JOINT_MODEL_OUT"]\n@assert OUT==joinpath(BASE,"joint-models-v3") "frozen rerun output required"')
        (scripts/name).write_text(text)
    review=(inputs/'scripts/review_saved_layers.jl').read_text()
    assert 'const INPUT = joinpath(BASE, "joint-models-v1")' in review
    review=review.replace('const INPUT = joinpath(BASE, "joint-models-v1")','const INPUT = joinpath(BASE, "joint-models-v3")')
    review=review.replace('const OUTPUT = joinpath(BASE, "layer-review-v1")','const OUTPUT = joinpath(BASE, "layer-review-v3")')
    review=review.replace('saved_v1_read_only_postprocessing_no_fit','saved_v3_read_only_postprocessing_no_fit')
    review=review.replace('all_626_original_corner_counts_and_contrasts_reproduced','all_original_corner_counts_and_contrasts_reproduced')
    (scripts/'review_saved_layers.jl').write_text(review)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts.iterdir()}
    plan={'input_version':'joint-inputs-v3','output_version':'joint-models-v3','input_receipt':receipt,
          'suite':'all v1 constant/ridge/EvoTrees shallow/deep/MAE/quantiles/source-group/history refits, neural_tree/residual_mlp/TabM, PCA/kmeans3/kmeans5',
          'unchanged_design':'same 749 families/3745 samples/outcomes/folds, purge and 600-second embargo, training-only preprocessing, seeds and fixed hyperparameters',
          'postprocessing':'median comparisons, phase/direction, market states, quantile coverage, observed price paths, all conditional split pairs and heldout response grids/missingness/matched contexts',
          'script_sha256':manifest,'v1_unchanged':True,'fitted_states_copied_from_old_runs':False}
    (out/'rerun_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(plan),flush=True)


if __name__=='__main__':main()
