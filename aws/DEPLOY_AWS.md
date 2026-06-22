# AWS deployment — OD coeff discovery + durable bin storage + FNO training

Honest scope (where AWS actually helps, S39):
- The **coeff discovery is cheap** — 600 coeffs in 35 s in-container (deterministic tier + `np.fft.rfft`).
  AWS does NOT meaningfully speed that up; setup overhead > runtime. Run it locally unless you're already on AWS.
- **Real wins:** (1) **S3 durable bin storage** — the off-git answer the gzip data-branches were a ~6-week
  band-aid for; (2) **GPU FNO training** — the production-tier decoder upgrade (can't run in-container, no GPU);
  (3) **scale** — re-discovering all 15 cells × deep history × larger caps is embarrassingly parallel.
- No AWS creds live in the Claude Code container (verified). **You launch with your creds; this packages it.**

## 0. One-time setup (your creds)
```bash
export AWS_REGION=us-east-1                  # Coinbase region; match your data residency
export ACCT=$(aws sts get-caller-identity --query Account --output text)
aws s3 mb s3://davisai-markets                # bins + coeff index live here (off-git)
aws ecr create-repository --repository-name od-discovery
```

## 1. Put 1-second bins in S3 (the off-git store)
```bash
# from the markets repo with realbins/ materialized (or straight from the data/* branches):
for f in realbins/*_bins.json; do gzip -c "$f" > "/tmp/$(basename $f).gz"; done
aws s3 cp /tmp/ s3://davisai-markets/realbins/ --recursive --exclude '*' --include '*_bins.json.gz'
```
Going forward, point the durable collectors / `backfill_oneshot` at S3 instead of (or in addition to) the
gzipped data branches — that retires the 100 MiB push-cap problem permanently.

## 2. Build + push the discovery image
```bash
aws ecr get-login-password | docker login --username AWS --password-stdin $ACCT.dkr.ecr.$AWS_REGION.amazonaws.com
docker build -f aws/Dockerfile -t od-discovery .
docker tag od-discovery $ACCT.dkr.ecr.$AWS_REGION.amazonaws.com/od-discovery:latest
docker push $ACCT.dkr.ecr.$AWS_REGION.amazonaws.com/od-discovery:latest
```

## 3. Run the discovery (cheap — Fargate Batch or a tiny EC2)
The container reads bins from S3, labels + discovers coeffs (the validated `_build_alt_winner_labels` +
`_run_alt_coeffs`), and writes `coeffs/alt_coeff_index.json.gz` back to S3. Env-driven (see
`run_discovery_s3.py`): `S3_BUCKET`, `S3_BINS_PREFIX`, `S3_OUT_PREFIX`, `CELLS`, `VENUE`, `CAP`, `SIDES`.

EC2 one-liner (simplest):
```bash
docker run --rm -e AWS_REGION=$AWS_REGION \
  -e S3_BUCKET=davisai-markets -e CELLS="doge:DOGE,xrp:XRP,sol:SOL" -e CAP=100 \
  $ACCT.dkr.ecr.$AWS_REGION.amazonaws.com/od-discovery:latest
```
AWS Batch (Fargate): register a job definition pointing at the image with the same env, attach an IAM role
with S3 read/write on the bucket, submit. (Skeleton: `aws/batch_job_definition.json`.)

Local sanity (no S3): `NO_S3=1 python aws/run_discovery_s3.py` uses `./realbins` + `./_alt_labels` in place.

## 4. Bedrock (the AWS-native agent path) — and which model
For AWS data residency, run Claude Code **via Amazon Bedrock** (request model access in your account) and wire
**Bedrock Knowledge Bases** to the S3 bins + the coeff index, so the agent orchestrates discovery and reasons
over the fingerprint store without data leaving AWS.

Scope honesty: Bedrock is for the **agent/LLM layer ONLY** (orchestration + reasoning over the fingerprint
store). It does NOT train or host the FNO decoder — that is custom PyTorch on a GPU (SageMaker / EC2 g5, §5);
Bedrock Custom Model Import only ingests specific LLM families (Llama/Mistral-class), not an FNO. And the
trading signal core stays model-free (low-dim numerics; the S36b quantum-resolution logic = keep it classical).

Model choice (best-first; the model lever only matters HERE, not for §5 or the signal core):
- **Claude Opus 4.7** — `anthropic.claude-opus-4-7` (Converse/Invoke). **GA, the default.** Use this for the
  agent + Knowledge-Base reasoning.
- **Claude Mythos** — gated research *preview*, **US East (N. Virginia) only**; Anthropic's most advanced for
  cybersecurity/coding/reasoning. Use if you have preview access and want max reasoning headroom.
- If/when **Opus 4.8** reaches Bedrock GA, prefer it over 4.7. Bedrock GA lags the latest Anthropic release, so
  confirm the current GA list on Bedrock's **model cards** page (`models-supported.html` -> model cards) before
  launching — IDs/Regions change.

This is the path to running the *whole* loop on AWS: Bedrock agent (§4) + S3 data (§1) + GPU FNO training (§5).

## 5. GPU — train the production FNO decoder (the real upgrade)
The committed coeffs are the DETERMINISTIC tier (mean-of-embeds + L2-normalize). The manifest's production
decoder is an **FNO + Bayesian ensemble** (4 layers / 16 modes / width 64; loss = spectral_coefficient_mse +
eigenvalue_preservation; ≥100 training pairs; ensemble 5 / mc_dropout 0.1). Training needs a GPU → SageMaker or
an EC2 g5. The deterministic coeffs we already have are the **training pairs** (prefill-embeds → coef).

The training set (X=prefill_embeds + mask, y=coef) is produced by `python _run_alt_coeffs.py --save-embeds`
→ `_alt_labels/coeffs/alt_train_pairs.json.gz` (gitignored; the committed coeff index stays lean = coef only).
On AWS, run the discovery job with `SAVE_EMBEDS=1` and it also uploads `alt_train_pairs.json.gz` to
`s3://<bucket>/<S3_OUT_PREFIX>/`. Then train (g5/SageMaker):
```bash
pip install torch
python aws/train_fno/train_fno.py --train-pairs alt_train_pairs.json.gz --out fno_checkpoint.pt
```
See `aws/train_fno/` for the skeleton + launch doc. This is the one piece that genuinely requires AWS GPU.
