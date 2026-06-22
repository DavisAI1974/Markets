# FNO decoder training (GPU — SageMaker or EC2 g5)

The production decoder upgrade over the deterministic tier (S39). Needs a GPU + torch (NOT in the
discovery image). The deterministic (prefill_embeds -> coef) pairs are the training set.

PREREQ (S40 TODO): persist `prefill_embeds` per source_id in `_run_alt_coeffs.py` so the coeff index
carries BOTH halves of each training pair (currently only the coef `y` is stored). Then re-export.

Run (EC2 g5 example):
    pip install torch
    python aws/train_fno/train_fno.py --coeff-index alt_coeff_index.json.gz --out fno_checkpoint.pt

Contract (manifest operator_decoder.v2): FNO 4L/16modes/64w; loss spectral_coef_mse + eigenvalue
preservation; >=100 pairs; ensemble 5 / mc_dropout 0.1. Validate calibration (ECE) on held-out cells.
Then wire the checkpoint as decode_mode=fno_bayesian and compare vs the deterministic coeffs per cell.
