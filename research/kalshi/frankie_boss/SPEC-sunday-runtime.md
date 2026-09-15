# Sunday native development runtime and retained Granite lease

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

`granite_retained_lifecycle` is restricted to Pod jvs75m56w8f73q. It reuses the
accepted `validate_resume` and `stop_owned_once` implementation. A new bounded
lease binds the admitted actual request and retained-info digest. `resume_once`
requires the real local tokenizer object to measure those exact bytes; a
caller-created admission dictionary is insufficient. An independent
runner calls `watchdog_tick` every at most ten seconds; the controller requires
a matching arm at most twenty seconds old. The arm identifies the actual GitHub
run/job and a job deadline extending at least thirty seconds beyond the lease.
Cleanup begins 120 seconds before
the lease deadline, uses only stop, and continues despite shared-journal errors.
The caller must keep the independent watchdog running through deadline+30 until
stopped, save its returned cleanup evidence locally, and report unresolved stop.

`resume_once` records start intent before a single start action. Interruption
returns `recover_existing_start` on replay; it never silently submits another
start. No model download, Pod creation/deletion or inference is performed here.
Reuse the accepted bootstrap and read fresh actual startup facts after resuming;
the old startup receipt is not evidence of current request capacity/readiness.
Start/recovery explicitly return `requires_startup_verification`. The
`verified_service_inputs` guard requires current-lease startup event/ready times,
all thirteen exact manifest file witnesses and authenticated health evidence.
Stop after the critic response when principal/CPU learning proceeds elsewhere;
a later resumed critic gets a fresh bounded lease, never an automatic extension.

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
No actual Sunday full-payload admission result is claimed yet. Increasing a
service context requires a reviewed explicit contract/configuration change and
new runtime evidence; it is not a reason to truncate the native context.

New retained-lifecycle interruption/admission/deadline tests: four passed.
Historical passing tests and accepted Granite startup were not rerun.
New review deltas separately passed: current checkpoint/model identity, actual
tokenizer and watchdog admission, and concurrent writer during prefix decoding.
