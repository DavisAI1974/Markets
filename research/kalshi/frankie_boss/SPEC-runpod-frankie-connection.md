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

### September 15 continuation checkpoint

Three additional components are implemented, with focused synthetic checks. They
are not an operational Sunday training loop:

- `frankie_source_mapping.build_mapping` streams the preserved gzip and compares
  every ordered full DBN wire record, retaining full member-row byte witnesses.
  `bind_prefix` checks the actual independently pinned BOSS journal and selected
  closed prefix. The first actual 245-record group matched exactly; the complete
  57,027-record mapping has not been executed. The mapping workflow is now manual
  only so publishing this checkpoint cannot start cloud work.
- `BossTrainingCheckpoint` atomically saves CPU native/decoder/optional teacher,
  optimizer, Python/NumPy/Torch RNG, cursor and the local update callback's receipt.
  Replayed completed IDs return saved evidence without another update. An uncertain
  mutation requires restore. Preserve its trusted hash separately for rollback
  detection. The initial model pin remains distinct from each trained-state digest.
- `NativeForecastLearner` applies actual native B1/decoder gradients from separately
  attested Frankie feedback using complete prepared inputs and exact serving packet
  identity. Timing learns STOP/presence and median delay; path/gap fitting freezes
  every timing dependency and trains median value heads. Missing labels stay masked.
  Explicit settings, principal attestation, query/split authorization and chronological
  next-request ordering are caller-owned duties. Granite is not trained.

Distinct new evidence: mapping 11 focused tests passed in 4.36s; after its progress
hook, only three affected cases passed in 3.09s. Training-state persistence passed
10 focused tests in 5.73s; its later atomic callback-result extension passed one
new test in 4.97s. Native learning passed nine focused tests in 6.26s. Mapping and
learner received independent read-only scope reviews; root reviewed persistence.
These are separate component results, not a full-suite or real Sunday execution.

The durable cycle coordinator does not yet exist. It must compose real controller
completion, file exporter/receiver, principal-authored feedback, atomic training and
separate new lessons. It must return a completed cycle before validating an old
controller pin after training, and recover an already-committed training receipt
without a second gradient update. Ambiguous principal calls require output recovery,
not automatic resubmission. Actual stage probes still need those callsites.

The mapping currently requires identical extraction identity on the mapping and BOSS
hosts, including native binary hashes. The prepared Linux/Python 3.11 runner may
differ from the future training host. Align the exact runtime, or explicitly review
a dual independently pinned extraction-identity design retaining full wire equality;
do not bypass the existing check. Local disk cannot hold the 10.7 GB plaintext
member ledger; use streaming on an adequately sized host.

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
