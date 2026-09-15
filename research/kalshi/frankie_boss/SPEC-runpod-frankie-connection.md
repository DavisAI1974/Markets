# Runpod connection to the existing Frankie forecast controller

This is connection software for the B2_GATED candidate. It does not constitute an
actual combined principal session or a training loop. The source is the combined
Round 2 build workbook, SHA256
9a22b8fb79c4920ca8a1d56b19a8adaba67b1d7b5e0ba0ea2d0a98f7bc1f9cac:
Build Plans D9:J9, Experiment Arms B13:J13, Components E24:J31 and Current Snapshot
E9:F15. The user now wants the full candidate with protected memory, direct Sunday
training and diagnostic probes, without another standalone smoke or repeat of
passing checks. Frozen Granite remains the required critic; native B1 remains the
reasoning core. Frankie independently computes his existing market findings.

## Assembly

`build_runpod_controller` returns the existing `FrankieForecastController` with a
`RunpodShadowService`. It accepts an existing source-bound native bridge, durable
controller journal, independently trusted native/config/identity pins, actual
runtime receipt, private proxy key and exact per-request admission callback. It
does not build a model or fixture, infer expected pins, refresh, or allocate a Pod.
Disabled mode preserves the caller's legacy route.

`LocalTokenizerAdmission(directory, served_model_name=...)` verifies the exact
eight tokenizer files and pinned transformer/tokenizer versions, loads local-only
once and measures the complete chat template on each canonical request. Use its
`tokenizer_sha256` in `GraniteIdentity`. Its tokenizer manifest uses the established
production invocation including `message_roles=['user']`. Input plus output must
fit the verified 4096 context. No character estimate, truncation, or frozen smoke
receipt substitutes for this measurement. Injected dependencies are synthetic.

The transport preserves the selected native or compact prompt exactly. It sends
one bounded request to the owned Pod's HTTPS proxy, with at most 1200 output tokens,
temperature zero and thinking disabled. Responses are bounded to 4 MiB. Provider
bytes are retained in the existing receipt shape with credential redaction. No
automatic retry occurs. Caller timeout retains busy capacity until the underlying
worker exits; no POST begins after admission/DNS consumes the remaining time.

The controller commits native results and critic intent before POST. Completed
request replay and trusted journal reopening reuse durable results without an
extra native forward or POST. Failed critique leaves native publications intact
and the integrated result incomplete. Diagnostics run before committing critic
intent so a diagnostic failure cannot create a false unknown remote attempt.

## Diagnostics

`RunProbe` writes append-only `progress.jsonl` and atomically replaces `progress.json`.
Use one owner process and directory per run. The context manager runs a heartbeat.
`controller_event=probe.controller_event` records source validation, native
reasoning, critic and output boundaries. Other owners call `advance` for data
delivery, actual Frankie calculation sections, training and checkpoint phases.
Those additional application call sites are not connected by the assembly alone.

Only an explicit denominator produces a percentage. Heartbeats never advance the
work cursor. An unchanged phase emits a possible-stall warning at the configured
threshold and repeats it each threshold interval; real progress emits recovery.
Counts and cursors cannot regress within a phase. Exceptions emit only safe error
classes. Background persistence failure surfaces before the next foreground
advance or successful context exit. Diagnostic callbacks may stop further work;
the operation journals retain completed work.

These are operational observations, not source/authorship attestations or model
checkpoints. Diagnostic `resume=True` preserves previous events but does not
restore computation. Existing trusted operation journals determine what work can
be reused. Filesystem and DNS operations have no hard process-return guarantee.

## Remaining operational connection

Use the existing attributed-input exporter/receiver on their separate code
lineages. Bind the actual source bytes, causal cursor and population origin before
claiming authentic combined delivery. Preserve all existing Frankie input layers
and his principal outputs; do not substitute runner-derived calculation results.

The workbook still lists concrete training configuration and fitted artifacts as
pending. Beginning training does not require an already-trained native model, but
it does require explicit initialization, objective, causal labels and persisted
learning state. Current controller pins deliberately reject model mutation during
a request. An online update must therefore occur between completed requests and
produce a new recorded model version, with corresponding model/optimizer/RNG and
data-cursor custody. Ordinary Granite critique does not itself update model weights.

The next hosted work should reuse the stopped retained Pod and go directly into
the real Sunday workload once this operational connection is ready. No repeat
standalone qualification or old test-suite rerun is required.
