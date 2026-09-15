# Sunday execution boundary

## Scope

`sunday_execution.SundayExecution` composes the actual nineteen chronological Sunday cycles. It does not provision a Pod, initialize a model implicitly, or dispatch a principal session on import. The authorized host supplies an admitted native runtime and a guarded real critic factory. With `session_executor=None`, an actual exported request becomes a durable pending host handoff.

## Host interface

Construct `SundayExecution` with keyword arguments:

- `directory`, `run_id`, and the durable `CycleCoordinator` instance.
- `contract_path`, `expected_contract_sha256`, `schedule_path`, and `expected_schedule_sha256`. The schedule is a JSON list or an object with `steps`; all nineteen steps retain their original increasing cursor and clock values.
- `runtime_factory(binding, cycle_directory, retained_plan)`, returning `SundayRuntime`. The retained plan is `None` on first execution.
- `principal_configuration`, `boss_commit`, `agent_commit`, and the explicit `state_defects_and_gaps_reported` sequence.

Call `await run_cycle(index)` or `await run_remaining()`. A pending actual principal request propagates `PrincipalPending`; the host records the actual session response and its independent host attestation before resuming the same cycle.

`SundayRuntime` requires `context`, `decoder`, `optimizer`, `checkpoint`, `expected_checkpoint_hash`, `development_identity`, `refresh_policy`, `input_hash`, `expected_native_hash`, `expected_critic_config_hash`, `expected_critic_identity_hash`, `critic_factory`, `source_journal_path`, and `source_journal_checkpoint`. Optional fields are `context_encoding`, `controller_event`, and `release`. The input hash must come from the actual admitted request. Model and checkpoint identities must come from explicit initialization or verified restoration. The critic factory owns its real tokenizer and startup guard.

`principal_configuration` supplies the keyword arguments `mapping_directory`, `expected_mapping_sha256`, `receiver_root`, `receiver_commit`, `python`, `retained_directory`, `expected_retained_witnesses_sha256`, `delivery_receipt`, `expected_delivery_file_sha256`, `result_path`, and optionally `session_executor`. The driver adds the actual exported manifest hash, source journal checkpoint, cycle binding, and per-cycle output directory. Delivery file SHA means the hash of the exact receipt bytes, not its internal self-hash.

## Durable order and recovery

1. Look up the coordinator's completed cycle before contract binding or the runtime factory. Require the preceding cycle to be complete.
2. Bind the verified source prefix to the principal-authored source contract. Preserve the original source clocks and single-day development convention.
3. Restore each cycle's controller and native book against independently retained append witnesses. Save the exact next append hash before its SQLite commit. Recovery accepts only the last witnessed before/after state.
4. Save the full planned controller and learning arguments, admitted input hash, actual model and critic pins, source journal path/checkpoint, and initial training checkpoint before calling the coordinator.
5. Let the coordinator own the native request, critic request, export, principal intent and response, learning callback, and lessons. The driver does not apply feedback independently.
6. Read and retain the actual controller/native checkpoints after refresh. Construct the receiver only after the actual export manifest exists. Resume an existing principal request without redispatch.
7. Serve each following cycle only after the preceding feedback/update completes. The contract limits each feedback horizon to the next retained cutoff; the final source tail remains censored without independent closure evidence.

A single-writer process lock protects the execution directory. Evidence files are immutable and installed from fsynced temporary files. An arbitrary self-consistent journal suffix, disappeared journal, changed request plan, or mismatched checkpoint is rejected. A retained ambiguous critic intent remains subject to the controller's existing recovery rules.

The caller owns runtime resource lifecycle through `release`; the driver closes the per-cycle controller journal and native book. Host evidence is a local trust boundary, not a provider signature.

## Validation

Four new bounded tests verify precommit journal recovery, rejection of unwitnessed journal suffixes, completed-cycle lookup before any runtime factory, and full plan persistence before the coordinator is invoked. These use synthetic seam dependencies and perform no model forward, cloud request, training, or market evaluation. They do not establish end-to-end Sunday completion.
