# Sunday native development runtime and retained Granite monitoring

This is an explicit development choice, not evidence of previous approval of
numeric training settings or of a fitted model. The supplied source is its own
source; no additional source date or Oct 1 mechanics run is required.

## Native initialization

`sunday_native_runtime.DEVELOPMENT` selects seed 20260915; native B1 float64 CPU,
256 dimensions, four heads, four layers, attention window 128, active delta
memory, fixed recurrence depth eight, and a 128-wide forecast decoder. Native
context remains 4096 records. The complete evidence journal is retained.

R3 teacher uses every causal prefix row with an initially empty UPDATING
normalizer: 4096 history, 256 warmup observations, original scale floors, clip
eight. This is online causal normalization inside the requested run, not an
extra warmup run. Missing/cold-start labels remain masked. NG tick is 0.001 at
DBN scale 1e9, consistent with the existing NG convention in build_anchor_block.py.
QSV is explicitly unavailable until a lawful governed mapping is supplied; the
original optional QSV surface remains off, never replaced by invented MBO bars.

AdamW owns exactly native plus decoder parameters: learning rate 0.0001,
betas (0.9, 0.999), epsilon 1e-8, weight decay 0.01, and explicit false values
for amsgrad, maximize, foreach, capturable, differentiable and fused. Initial
stage is timing with presence/delay weights one and gap/path weights zero.
All supplied sessions have weight one. Actual optimizer identity is saved.
Timing policy, query policy and chronological split must have attested hashes;
the runtime supplies no hidden precision or label policy.

The principal must certify actual anchors and the session convention. A
development interval inside the sole supplied source can use an explicitly
declared own-source reference, but it must not be represented as an exchange
prior close or whole-session forecast. A final-prefix input cannot forecast an
already completed same-day interval. Select a closed interior source prefix and
keep later rows out of input, making them available to feedback at the learning
cutoff. The full source still goes through the existing principal handoff.

## Actual request path

1. Restore the complete C15 journal from its trusted checkpoint.
2. Call `initialize(builder)` only for a fresh training run; save initial state
   with `BossTrainingCheckpoint`. On continuation restore the committed state.
3. Supply attested sessions, the current training checkpoint/optimizer and its
   independently retained checkpoint hash to `assemble_request`, then supply the resulting
   bridge and request to `build_runpod_controller`. Controller pins must reflect
   the checkpoint's current native/decoder state. Assembly compares live weights
   and optimizer bytes to that committed checkpoint. Each new arm identity binds
   the current checkpoint/native state, preserving initialization separately.
4. `prepare_critic_request` prepares the complete actual compact payload without
   a model forward, inference call, shortened context or synthetic source.
   Apply `LocalTokenizerAdmission` to these exact bytes before resuming compute.
5. Use `CycleCoordinator` for completed controller, actual receiver/principal,
   feedback, lazy learner and atomic checkpoint ordering.

## Retained compute

The current user policy has no elapsed startup or runtime stop budget.
`make_startup` binds the exact admitted request, retained Pod receipt, and actual
local input-admitted witness. `start_once` records intent before one start;
a later observer returns `observe_existing_start` and never submits another.
Startup and run receipts explicitly carry null deadlines. The historical bounded
lease helpers remain available for prior evidence; the operational host does
not call them.

After fresh provider container timestamps, all thirteen model-file witnesses,
and authenticated health pass, `make_run` creates the open run identity.
`verified_service_inputs(..., startup_intent=startup, request_timeout=None)`
binds that identity to the native controller transport. Health responsiveness is
reported separately from progress. New startup/disk receipts and a newly verified
service-ready receipt are observable milestones; repeated identical receipts or
successful health polls are not advancing progress. Absent progress or temporary
observation failure is an attention state, never an automatic restart or stop.

The independent GitHub observer has the platform's unavoidable six-hour job
maximum. It writes `observer_handoff_required` before runner exhaustion and
preserves the Pod and request-specific journal. A replacement observer reads
that same journal and start intent. This observer horizon is not a model startup
or runtime deadline. See [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits).

Successful completion remains a stop-retain event: the exact
`retained-finished.json` marker contains the current `startup_sha256`; the
observer uses `stop_owned_once` and retains confirmed cleanup. Explicit user
stop also uses that owned-Pod operation. Verified fatal model/runtime integrity
failure triggers cached-ownership cleanup independently of S3. Healthy startup,
long inference, missing progress, or observer exhaustion never triggers cleanup.
No Pod creation, deletion, model download, or inference occurs in the host driver.

## Online preparation

`online_source_prefix` copies exact original journal envelopes through a chosen
completed zero-based F_LAST group. It uses short paged read-only source queries,
decodes after releasing each cursor, and marks the destination query-only. It
retains original hashes, validates the complete selected chain, and explicitly
does not claim a full-source checkpoint or completed ingestion. This permits
actual request capacity preparation while the full source remains in progress.

The retained first cutoff is group 2281 / source cursor 3261: 3262 records are
available naturally under the configured 4096 context. The second cutoff is
group 4562 / source cursor 6053 and therefore supplies a full 4096 active rows.
The schedule preserves all nineteen cutoffs and terminal delivery, and permits
feedback only through the following cutoff before the next model update.

## Capacity evidence available so far

The retained config SHA256
85611f4e34633d4e148e6a5f64bc2d3a23ebbc2b014bc87fbda764eecf261cd9
declares 131072 maximum positions. The accepted serving configuration and
current service/tokenizer contract remain 4096, with a 1 MiB request ceiling.
Actual first-cutoff preparation completed using the retained 3262-record prefix,
without truncation or inference. Its compact request is 1,884,734 bytes and the
exact accepted tokenizer measures 929,730 input tokens plus 1,200 output tokens:
930,930 total. Request SHA256:
`e65c33161a6ff3bfe02fa368dc30d29115dbb56aed8d358a05671891c473536c`.
It exceeds both the service limits and the model's 131,072-position limit.
Raising only the service limit cannot admit this complete request. A reviewed
architecture change is required; the runtime must not silently truncate it.

New retained-lifecycle interruption/admission/deadline tests: four passed.
Historical passing tests and accepted Granite startup were not rerun.
New review deltas separately passed: current checkpoint/model identity, actual
tokenizer and watchdog admission, and concurrent writer during prefix decoding.
