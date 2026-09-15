# Frozen Runpod smoke tokenizer admission

`granite_runpod_admission.admit(tokenizer_directory)` verifies eight local tokenizer
files against the existing frozen Granite artifact manifest and requires
transformers5.8.0/tokenizers0.22.2, matching the existing live controller's image
pins. It uses AutoTokenizer with local_files_only=True and trust_remote_code=False.
No network, inference, model weight load or runtime bundle change is performed.
Missing files or versions fail closed. Existing artifact verifier APIs own exact
file size/hash checks; a lightweight constants consistency test avoids importing
the live controller's model dependencies.

The only request is canonical JSON: model granite42-smoke, one user message
`Reply exactly READY.`, temperature0, max_tokens16, streamfalse and
chat_template_kwargs.enable_thinking=false. Tokenization explicitly enables the
generation prompt and disables thinking, truncation, padding and tensor returns.
Complete nonempty nonnegative integer IDs plus the16-token output budget must fit
4096; the verified model positional limit must support that configured context.

Receipt schema GRANITE_RUNPOD_TOKEN_ADMISSION_V1 binds canonical request bytes/hash,
model repository/revision/manifest hash, tokenizer file/version/invocation manifest
and hash, exact token IDs/hash/counts, context4096 and output16. Default evidence
class is LOCAL_TOKENIZER_ADMISSION. Any injected loader/version reader/manifest
makes evidence SYNTHETIC_TOKENIZER; injection tests are not actual token measurement.

`validate_receipt(receipt, expected_receipt_sha256, allow_synthetic=False)` returns
only the frozen request bytes after checking caller-supplied independent receipt
hash and all bindings. Synthetic evidence is refused by default. The opt-in exists
only for local fake one-probe tests. The hash must come from trusted prior receipt
retention, not be inferred from an arbitrary response. This is a trusted local
producer boundary, not a signature or independent runtime attestation.

No actual tokenizer admission has been measured in this slice. The root task located a prior verified tokenizer directory and matching
libraries and will perform the real measurement separately after review. Admission does not prove a
host's effective startup model/context, GPU fit, generation behavior or controller
acceptance; those require separate evidence. No spend or Sunday run is authorized.
