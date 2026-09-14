# Exact Granite artifact staging and current AWS evidence

This increment implements the artifact portion of SPEC-granite-live-run.md. It
contains no endpoint provisioning, inference, training, replay or order submission.
The mounted-file verifier is implemented, but still must be connected to the
selected image's actual startup path before readiness. Running the verifier on a
local directory does not prove a deployed model identity.

## Reviewed runtime set

`granite_artifacts_manifest.json` is canonical JSON for revision
`f8de16cdcdbc6c779ca517604e050d82cc119e44` of `ibm-granite/granite-4.2-8b`.
Its SHA256 is `adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a`.
It contains 13 files, including all four BF16 shards totaling 17,583,228,032 bytes.
The optional thinking parser, repository README, git attributes and signature
file are explicitly excluded. No remote model code executes. The supplied spec's
hash table is unchanged; immutable HF metadata supplied exact sizes.

`granite_run_artifacts.py` rejects incomplete/extra rosters, symlinks, corruption,
invalid index shard references, duplicate JSON keys and nonfinite JSON values.
Downloads use immutable revision URLs. A resume requires the same saved strong
ETag and exact Content-Range, and the complete file is rehashed before promotion.
An interrupted or corrupt partial is never promoted. No silent download retries.

Staging handles one artifact at a time: verify local size/hash, upload, stream the
whole object back and verify size/hash, save the per-object receipt, then release
only that task-owned local file. Existing objects are reverified and never
silently replaced. The exact model prefix is `models/<manifest digest>/`; the
receipt is outside it. Final prefix listing must match all 13 names and sizes.
S3 ETags and reported version IDs are retained as metadata, not content proofs.
Startup must independently rehash the mounted files; storage immutability is not
claimed. Failed staging retains earlier completed objects and receipt for restart.

The staging workflow is triggered only by a reviewed change to its own workflow
file on the integration branch. It runs tests before exposing AWS credentials to
one staging step, compares the caller account to the private account's reviewed
SHA256 commitment before deriving the exact approved bucket name, and creates
that bucket only after a true absent result. Other access errors
stop. The job is bounded to 180 minutes and creates no chargeable GPU resources.
Staged S3 model objects are retained intentionally for deployment; they incur
storage costs. Verification receipts are retained as CI artifacts for 30 days.

## Fresh AWS check

Read-only run `34900575529` at integration commit `bcea9b92` returned a complete
SageMaker inventory on 2026-09-14:

- Exact quota L-F8D7F460, ml.g6e.2xlarge endpoint usage: 2.
- Exact us-east-1 Hosting on-demand compute: USD 2.8026000000 per instance hour.
- Complete endpoint listing for the exact `frankie-granite42-` prefix: empty.
- Candidate vLLM digest unchanged:
  `sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.
- Exact Docker V2 manifest bytes retained and their SHA256 verified.

The workflow's later, unrelated Bedrock inventory failed. That does not negate
the complete SageMaker report; Bedrock is not the chosen deployment route. Private
account IDs/ARNs remain in restricted operational artifacts, outside this record.

Nine real small artifacts were downloaded locally from the immutable revision
and verified, including tokenizer/config/index/template files. This is not weight
verification. Full weights become verified only when the staging run receipt
records successful whole-file download AND S3 readback for every shard.

## Verification and remaining integration

Synthetic tests cover exact bytes and file roster, malformed manifests/indexes,
S3 corruption/extra keys, resume identity/range changes, partial promotion,
nonoverwrite restart, local release after readback and scoped bucket behavior.
The suite runs on Windows; a missing symlink privilege uses a targeted filesystem
predicate simulation, while Linux creates the actual symlink. No test is skipped.

Before real Granite calls: bind the verifier to the actual pinned image startup,
retain Python/PyTorch/Transformers/tokenizers/vLLM/CUDA/GPU runtime identities,
freeze/admit the real controller's complete prompt using the pinned tokenizer,
and create a one-GPU deployment with explicit deadline/spend and verified cleanup.
A tag, an S3 receipt, or a tokenizer diagnostic alone is not a running model test.

Primary sources:
- https://huggingface.co/ibm-granite/granite-4.2-8b/tree/f8de16cdcdbc6c779ca517604e050d82cc119e44
- https://docs.aws.amazon.com/sagemaker/latest/dg/large-model-inference-uncompressed.html
- https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/upload_file.html
- https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html
- https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html
- https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ListEndpoints.html
- https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_BatchGetImage.html
