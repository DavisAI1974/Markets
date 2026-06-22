# FNO decoder training (GPU — SageMaker or EC2 g5)

The production decoder upgrade over the deterministic tier (S39). Needs a GPU + torch (NOT in the
discovery image). The deterministic (prefill_embeds -> coef) pairs are the training set.

PREREQ — DONE (S40): `_run_alt_coeffs.py --save-embeds` persists the training pairs (X=prefill_embeds +
prefill_mask, y=coef) to `_alt_labels/coeffs/alt_train_pairs.json.gz` (gitignored, S3-bound). The committed
`alt_coeff_index.json.gz` stays LEAN (coef only) — point training at the train-pairs file, not the lean index.

Generate the pairs (cheap, in-container, ~35 s for 600):
    python _run_alt_coeffs.py --save-embeds
On AWS this happens automatically when the discovery job runs with `SAVE_EMBEDS=1` (see ../run_discovery_s3.py),
which also uploads alt_train_pairs.json.gz to s3://<bucket>/<S3_OUT_PREFIX>/.

Run (EC2 g5 example):
    pip install torch
    python aws/train_fno/train_fno.py --train-pairs alt_train_pairs.json.gz --out fno_checkpoint.pt

Contract (manifest operator_decoder.v2): FNO 4L/16modes/64w; loss spectral_coef_mse + eigenvalue
preservation; >=100 pairs; ensemble 5 / mc_dropout 0.1. Validate calibration (ECE) on held-out cells.
Then wire the checkpoint as decode_mode=fno_bayesian and compare vs the deterministic coeffs per cell.
