# Durable Frankie–BOSS feedback cycle

## Scope and entry point

`feedback_cycle.CycleCoordinator` connects completed integrated controller
requests, the actual `agent_file_handoff.export_handoff` file boundary, the
independently verified frozen Frankie receiver, attested principal output,
`NativeForecastLearner.step`, and `BossTrainingCheckpoint.apply_completed`.
It does not compute market labels or turn runner calculations into authorship.
The principal adapter supplies its explicit authorized execution route.

Construct the coordinator with separate cycle and new-lesson SQLite paths,
the immutable Memory A path and its independent SHA256. `create=True` exclusively
creates both stores; a resumed run requires both existing stores. The entire
cycle is protected by a nonblocking OS process lock, released on process death.
Stores, exported artifacts and their externally retained trusted evidence must
travel together. The cycle store's self-hashes detect corruption, not malicious
replacement or rollback; deployment must retain independently trusted storage.

Call async `run` with:

- `request_id`: stable identity for this causal request.
- `controller_factory`: constructs the current pinned controller lazily.
- `controller_kwargs`: actual `controller.refresh` arguments, excluding request ID.
- `export_kwargs`: actual exporter arguments excluding request ID, or a callable
  accepting the completed result and reading its final independent checkpoints.
- `principal`: `FrankiePrincipalAdapter`, exposing synchronous `prepare`,
  `execute`, `recover`, and `verify`.
- `checkpoint`: restored `BossTrainingCheckpoint`, using its independent trusted
  checkpoint digest on restore.
- `learner_factory`: lazily creates the configured `NativeForecastLearner`.
- `learning_kwargs`: actual learner step arguments including full sessions,
  expected session hash, input/source hashes, through cursor, as-of and learning
  cutoff; exclude request ID and feedback arguments owned by the coordinator.

The runtime constructs its next controller only after a completed update, using
the newly committed model identity. The coordinator never changes a controller's
pin during its request.

The coordinator also refuses a new request while another cycle remains unfinished,
or if the new as-of time precedes any completed cycle's feedback availability.
This prevents weights learned from a later cutoff from serving an earlier one.
One new chronology regression passed after demonstrating that failure.

## Durable stages and interruption behavior

1. Bind request, controller inputs, complete learning inputs, training identities
   and frozen-memory hash. Reject changed identities on replay.
2. Return a retained completed cycle before invoking controller or learner factories.
3. Run/recover the real controller and require integrated `complete` status.
4. Export the actual retained controller/native journals using independent pins.
   Read back every member hash, complete result, source/cursor/as-of, and actual
   native artifact input hash. Partial export directories remain diagnostic
   evidence; only a completely written export is renamed into the final path.
5. Prepare the verified receiver attachment and save its receipt.
6. Persist principal intent before execution. On resume, call only `recover`;
   absent output raises `AmbiguousPrincipalCall`. Never automatically re-execute.
7. Retain raw principal output, verify its authorship and exact causal bindings,
   and persist typed feedback plus its attestation hash before any gradient.
8. Pass a lazy learner construction/step callback to `apply_completed`. Its
   existing deduplication precedes learner preparation or forward. A committed
   training update whose cycle receipt was lost returns the stored update receipt.
9. Store principal lessons separately, bound to feedback and training checkpoint.
   `lessons_available(cutoff_ns)` returns only records available at that cutoff.
10. Confirm Memory A unchanged and save completion. Named phase callbacks expose
    actual reasoning, handoff, principal calculations, learning, checkpoint and
    completion transitions; transport/data modules supply their own denominators.

Diagnostics before principal intent cannot fabricate an ambiguous remote attempt.
After an uncertain checkpoint mutation, callers close and restore the checkpoint
from its last trusted commit before resuming, as required by its existing API.

## Focused acceptance checks

New tests cover completed replay without old controller construction, a lost cycle
receipt after committed training without a second forward, ambiguous principal
recovery without resubmission, changed identity rejection, rejection of unattested
output before learning, lesson availability and diagnostic failure before intent.
They use synthetic local boundaries and the real training checkpoint store; they
are not evidence of actual Sunday principal execution or a full market run.
