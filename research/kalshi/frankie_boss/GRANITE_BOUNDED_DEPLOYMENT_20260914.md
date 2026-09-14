# Bounded Granite deployment lifecycle

`granite_deployment.py` contains resource lifecycle helpers only. It never invokes
Granite or performs Frankie/native calculations. The integration harness continues
to use the existing controller and real SageMaker service.

The caller must complete immutable model/bootstrap staging and exact complete
prompt token admission BEFORE `make_plan`/`create_resources`. Generate the plan in
the same Linux checkout as the bootstrap staging: Windows line endings produce
different honest source hashes and cannot be substituted for staged Linux bytes.
The currently verified bootstrap prefix from run34902805329 is
`models/bootstrap/5ccbb86c3aa6c47f315f3aad2ec887658f6b245dfc9b9fdf8886542b029b5f64/`.
All four staged objects were uploaded and streaming-readback verified. Real model
weight staging is separate and must return status=verified for all13 artifacts.

## One explicit run

`make_plan(account_sha_checked=..., run_id=..., max_model_len=...,
served_model=..., now=time.time())` enforces the approved private account SHA256
commitment, exact one ml.g6e.2xlarge, pinned model/image/bootstrap and fixed budgets:
45-minute deletion deadline, 60-minute final cleanup deadline, 20-minute startup
wait and USD2.10195 estimated45-minute compute at USD2.8026/hour. The plan is private
operational JSON containing resource ARNs/bucket name. Keep it outside Git.

`create_resources(client, plan, ledger_path)` rejects mutated policy/configuration
and pre-existing resource names. It saves exact plan+SHA256 and each creation intent
before making an AWS mutation. Existing ledgers require inspection/cleanup; they
never implicitly start another endpoint. A lost creation response is recoverable
using the saved intent and exact names. `wait_ready` bounds startup;
`inspect_resources` compares actual model/config/endpoint descriptors against the
plan, allowing provider-added metadata but requiring the exact environment and
planned values. Unexpected or failed statuses are retained as failures.

`startup_receipt(logs_client, plan)` reads only the endpoint's exact CloudWatch log
group with bounded complete pagination. It returns the single canonical startup
receipt, None when none is visible yet, and rejects conflicting receipts or
pagination overflow. This collects evidence; the harness must validate the entire
receipt, admitted tokenizer count, source/model identity and service config before
calling the real provider. The selected startup code verifies mounted bytes and
runtime/source pins before launch. Store the complete raw logs and descriptors as
private artifacts along with the receipt.

Always run `cleanup_resources` in a Python `finally` block AND from an independent
CI `if: always()` cleanup step using the same saved plan/ledger. It confirms each
owned resource still matches, deletes the exact endpoint, waits for confirmed
absence, and only then deletes configuration/model. Lost delete acknowledgements
are reconciled with describe calls. Deletion failure or exceeding the cleanup
deadline stays a recorded failure; it is not a successful bounded run. A failed
cleanup requires operator intervention immediately. The CI workflow must retain
plan/ledger/receipts even on failure/cancellation and report endpoint absence.
No helper can guarantee cloud cleanup after simultaneous CI/operator loss.

## Selected-image tokenizer/runtime package evidence

The whole3,461,257,375-byte dependency layer was streamed and SHA256-verified again
while retaining package METADATA; digest:
`sha256:65d6e8ef197d1716a17a0d495d1ee8f8e24765c0ccbe724682b113c2193f17dd`.
It contains transformers5.8.0, tokenizers0.22.2 and torch2.11.0+cu130. The selected
image is vLLM0.20.2; its exact supervisor0.1.15 source is separately pinned.
Use transformers==5.8.0 and tokenizers==0.22.2 for CI admission with the verified
local tokenizer files, local_files_only=True and trust_remote_code=False.
Apply the actual single-user chat template with enable_thinking=False and
add_generation_prompt=True. Preserve full token IDs or their digest and count;
compare the result to actual provider usage.prompt_tokens. Actual startup package
versions remain authoritative and must match the admitted implementation.

Synthetic lifecycle tests cover one-GPU/config/deadline policy, saved intents,
pre-existing resources, expired plans, uncertain create/delete acknowledgements,
cleanup ordering/deadline failure and conflicting log receipts. They perform no
AWS mutations or model calls. The first actual integrated run remains pending
verified full model staging, runtime readiness and the real controller harness.
