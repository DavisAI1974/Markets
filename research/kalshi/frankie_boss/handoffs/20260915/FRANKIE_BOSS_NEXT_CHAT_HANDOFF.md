# Frankie + BOSS + Granite: continuation handoff

Updated September 15, 2026. This file is the current continuation checkpoint. Read it before older launch notes, which describe superseded failures and a previously running Pod.

## User direction and honest status

Finish connecting the actual full Sunday 2021-10-03 Frankie run to native BOSS B1 and frozen Granite. These are development/training runs. No more standalone smoke or warmup runs, no rerunning already-passing checks. Reuse completed work; test only new or changed behavior. User now wants a clean handoff for a new chat.

**The controller connection, source-mapping implementation, native learning callback, and saved training-state implementation exist. The operational feedback-to-training coordinator is NOT yet implemented. The full source mapping has NOT yet been executed. No full Sunday principal run or real BOSS training has started.** Do not report the complete system as wired or ready merely because component tests pass.

Granite startup was accepted by the user. The Pod was stopped with its model files retained. Do not repeat its acceptance run. New paid execution must have a bounded lifecycle; the expired 30-minute window is not an indefinite extension.

## Preserve these requirements

- Full raw MBO, full-depth order book and FIFO, dipoles, brain, memory, and every applicable existing plane. No silent sampling or dropped records. Approximately “100+” was not an exact numerical gate: the inventory is 99 registered layers, with 98 applicable to A_MEMORY.
- Frankie independently computes every current contract section (18+). Runners deliver, retain, validate and instrument; their market calculations cannot substitute for Frankie-authored findings.
- BOSS is the native reasoning core. Granite is the frozen required critic. Native BOSS can start from explicitly recorded initialization and learn from attested Frankie feedback. Do not require a previously trained new-BOSS checkpoint to start training.
- Preserve frozen Memory A. Write new lessons separately. Persist model/decoder, optimizer, RNG, cursor, objective receipt and feedback evidence so completed calls or gradient updates are not repeated.
- Model updates happen BETWEEN completed controller requests. A controller's native pin must remain fixed during its request. Construct the next controller with the newly committed model identity.
- Probes report actual phase, progress with real denominators, stalls/errors, recovery and saved completion. A heartbeat is not proof that work advanced.
- Technical role/configuration questions should first be resolved from the Excel build plan, not asked of the user again.
- No additional comparative-control runs are implied by this request. Do not claim comparative performance or trading readiness from development training.

## Workspace and source lineages

Current task root:
`C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2`

Active BOSS worktree:
`C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie`

Branch: `codex/full-frankie-boss-connection-20260915` in `DavisAI1974/Markets`.
Code and specification pushed at `a9e460ce139bbff5153d67cfc408985a9e47e885`; remote SHA verified. Tracked files are clean; untracked local `work/` scratch remains preserved. All delegated work completed. Read `HANDOFF_CODE_STATE.json` alongside this document for exact test evidence. Do not confuse that commit with the accepted hosting workflow's code.

Actual frozen Frankie receiver:
`C:/Users/A/Documents/Codex/2026-09-14/continue-the-frankie-build-in-parallel/work/Markets-source`

Receiver branch `codex/frankie-attachment-preparation-20260914`, commit `b4f364f0812cd964c68faf3cef948b28d4603c90`. It has `prepare_boss_attachment.py` and no BOSS package. Keep the separate lineages connected through their verified file boundary; do not wholesale merge them or edit the frozen checkout. Use a new worktree if changes are needed.

Accepted launch worktree: current root's `work/Markets-smoke`, branch `codex/granite-runpod-launch-20260915`, commit `1fb894b6f68a048a5ccd67684e4c9bf7d61af671`.

Windows PowerShell. Approval policy never: omit `sandbox_permissions`. Do not print secrets, full Pod environment responses, or GitHub secret values. Credentials are already bound in GitHub Actions. Only use exact file sets when committing; the active worktree has unrelated local `work/` scratch files.

**Local C: had only 4.77 GB free. Do not materialize the 10.7 GB plaintext member ledger locally.** Stream the preserved gzip on a GitHub runner or a suitably sized execution host. Do not delete unrelated user files to make room.

## Excel authority

Workbook:
`C:/Users/A/Documents/Codex/2026-09-14/continue-the-frankie-build-in-parallel/outputs/combined-build-round2/Frankie_BOSS_Combined_Build_Round2_20260915.xlsx`

SHA256 `9a22b8fb79c4920ca8a1d56b19a8adaba67b1d7b5e0ba0ea2d0a98f7bc1f9cac`.
All cells were already extracted read-only to current root's `work/build-plan-round2.json`. The workbook was not modified.

- Build Plans D9:J9 / Experiment Arms B13:J13: B2_GATED/B2-memory, native B1 plus required frozen Granite critique and protected Memory A.
- Components E24:J29: native B1 authoritative; Granite has no broker or memory-write authority. Failed critique preserves native work but leaves integrated result incomplete.
- Components E7:J7: frozen prior immutable, new lessons separate.
- Components E31:J31: exact resume; identities cannot silently change.
- Current Snapshot E9:F10: attributed_input delivery selected; actual population/cutoff/source handoff still needs binding.
- Current Snapshot B12:F15 / Source Crosswalk A59:D59: numeric training settings and fitted artifacts are pending, not provided by this workbook. Make explicit development choices consistent with the existing native forecast training specification; do not invent prior approval or a completed training configuration.
- Current Snapshot supersedes historical software-status tabs. User's no-warmup / Oct 1 waiver supersedes older roadmap sequencing.
- Inventory: 99 layers after six obsolete roles retired. A_MEMORY 98 = 22 static + 55 causal + 9 sealed + 2 optional shadow + 10 append-only output. Separate 1940 leaves/46 blocks/24 surfaces is a different taxonomy, not proof all historical inputs exist. Keep unavailable external inputs explicit and future answers sealed.

## Accepted Granite and cleanup evidence

GitHub run 34928264918: https://github.com/DavisAI1974/Markets/actions/runs/34928264918

- Pod `jvs75m56w8f73q`, name `granite-smoke-4e2ecee03d7b2bb77da16180aba4f98d`, owner nonce `4e2ecee03d7b2bb77da16180aba4f98d`.
- L40S; observed $1.09/hour; 100 GB container plus 50 GB persistent mounted `/opt/ml`.
- Created 04:18:47Z; service ready 04:30:24.601Z, 11m42.6 after intent.
- All 13 model files / 17,592,970,510 bytes verified. Authenticated health 200. No inference POST or Sunday workload.
- Watchdog completed 04:48:49Z. `outputs/granite-diagnostic-34928264918/watchdog/watchdog-cleanup.json` says `confirmed_stopped`, exact Pod ID, `data_retained=true`. Last independent API read returned EXITED with the retained mount.
- No active watchdog/automation or live model work remains. Do NOT terminate/delete this retained Pod. Reuse intact `/opt/ml/model`; no needless model redownload.
- Stopped storage remains billed (prior estimate about $0.33/day); final provider billing total not established.

Runtime: transformers 5.8.0, tokenizers 0.22.2, vLLM 0.20.2, torch 2.11.0+cu130, Python 3.12.13, CUDA 13 / driver 580.159.03. Model ibm-granite/granite-4.2-8b at `f8de16cdcdbc6c779ca517604e050d82cc119e44`; context 4096; served `granite42-smoke`.

Model manifest SHA256 `adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a`.
Image `public.ecr.aws/deep-learning-containers/vllm@sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.

The former 19+16 token smoke receipt is NOT admission evidence for a Sunday request. The actual exact payload must pass current tokenizer admission. Native 4096-row context can exceed Granite's 4096-token context; never silently truncate or substitute a one-row test fixture to make it fit.

## Verified real Sunday source and preserved ledgers

Source-copy GitHub run 34931181246 succeeded:
https://github.com/DavisAI1974/Markets/actions/runs/34931181246

Local compressed source: current root's `work/sunday-source/glbx-mdp3-20211003.mbo.dbn.zst`.

- 973,355 bytes, SHA256 `4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88`.
- DBNv3 GLBX.MDP3 MBO, no ts_out; 3,193,872 plaintext bytes; 57,027 records, all rtype 160 / 56 bytes; publisher 1 / instrument 111313.
- Framing inspection only, no market calculation. Receipts: `outputs/SUNDAY_SOURCE_COPY.json`, `outputs/SUNDAY_SOURCE_FRAMING.json`.
- S3 bucket `bento-568968024170-us-east-2-an`.
- Source key `nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211003.mbo.dbn.zst`.

Preserved full Frankie delivery prefix:
`nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1`

- `ledgers/exact_member_rows.jsonl.gz`: gzip 1,705,613,663 bytes; plain 10,756,276,521 bytes; plain SHA256 `f73e95378c04f117863b173bd389675029006fffc309a07992edcc4de4ad5325`.
- `ledgers/exact_lifecycle_rows.jsonl.gz`: gzip 25,581,893; plain 300,309,453; plain SHA256 `1e511353a6f82a667f43129bba6ffa5d7dc4c61441adcd8c321a43453e03baee`.
- `ledgers/legacy_observable_rows.jsonl.gz`: gzip 2,198,595; plain 29,329,182; plain SHA256 `3c75f8b4b779c0ab1e59f9ea28fe12739b7b668edb3763a0c1aecaac3dc7bafa`.
- `calculation_result.json`: 29,089,413 bytes; SHA256 `91e47d0d1533b6745888bcc17e4231f998ed78dc9735c7e2f0dcab8bd65971a9`.
- Delivery manifest SHA256 `d6455e85d495af91fc92321bb5c966eec47fbcd5e2d0f6d50ede359329937b17`; receipt self-hash `3420045aecc9c225ce77bf47a184cc2b262685177998f51ff94585b0b3149d1b`.
- Frozen receiver receipt: `research/kalshi/frankie_raw_mbo_benchmark/principal_runs/frankie-a-memory-rt-33746436209-1/delivery_receipt.json`.
- Historical stream 43,569 groups / 395,447 lifecycle attachments. Historical prompt does not contain the new BOSS attachment.

Format inspection run 34931730385 succeeded. The real first member row is already local at active BOSS worktree `work/member-format/member-row-preview.json` (ignored scratch). Its 245 raw actions preserve all 13 variable MBOMsg fields, but do not have modern `source_record.wire_bytes_hex`. The pinned SDK re-encoded all 245 records to exactly the original 56 bytes, ordered through F_LAST. This is explicitly `normalized_fields_reencoded`, not a claim that the old row stored original wire bytes. Full mapping is still pending; do not infer it from this first group.

## Existing completed connection components

All paths below are under active BOSS worktree `research/kalshi/frankie_boss/`.

- `granite_runpod_service.py`: real Runpod critic transport, exact native/compact prompt, one bounded HTTP attempt, strict runtime/model/config/request/tokenizer binding, late-call busy exclusion, safe phase events.
- `granite_runpod_tokenizer.py`: `LocalTokenizerAdmission`, exact eight files, pinned versions, local-only complete chat-template measurement without truncation. Dedicated directory must contain exactly the expected files. No new production tokenizer files were downloaded in this turn.
- `granite_runpod_controller.py`: `build_runpod_controller` assembles the real existing native bridge/journal with frozen Runpod critic, caller-owned pins and runtime/admission.
- `frankie_controller.py`: phase callbacks. Diagnostic emission happens before CRITIC_INTENT so a failed diagnostic cannot fabricate an ambiguous remote attempt. Durable intent still precedes POST.
- `full_run_progress.py`: RunProbe durable JSONL + latest snapshot, explicit owners/counts, recurring stalls/errors/recovery. Only existing connected callsites are proven; do not claim every Frankie stage has been wired yet. Single owner process per diagnostic directory.
- Prior distinct focused results: service 21; tokenizer 36; controller assembly 8; diagnostics 8; one later diagnostic-order regression. These were already passed and must not be rerun just to demonstrate them again. Old 43/640 baselines remain separate, not additive current totals.

## Newly saved components and APIs

Exact final commit/test/review status is in `HANDOFF_CODE_STATE.json`.

### `frankie_source_mapping.py`

`build_mapping(source_path, source_member, extraction_pin, member_ledger_path, member_ledger_witness, output_directory)` streams the entire gzip once; verifies every full ordered source wire, every closed group and independently pinned plain byte witness. Writes an index plus mapping receipt outside the executing checkout. Does not run market calculations.

`bind_prefix(mapping_directory, expected_mapping_sha256, boss_journal_path, journal_checkpoint, boss_source, output_path)` binds the selected closed source prefix to the actual independently pinned BOSS journal and full hash chain. Checks source index/SHA, extraction identity, raw wire, causal clocks and terminal prefix. It does not mint principal authorship.

CLI has `build` and `bind`. New workflow `.github/workflows/frankie_boss_ledger_mapping.yml` prepares the fixed source/member mapping remotely and returns small evidence. Read final code-state notes before triggering: a workflow may be prepared but not executed. The prepared workflow is manual-dispatch only; publishing this handoff must not launch it. Its fixed request JSON names the full mapping operation. It has not been executed.

### `boss_training_checkpoint.py`

`BossTrainingCheckpoint(path, models={'native': ..., 'decoder': ..., optional 'teacher': ...}, optimizer=..., identities={training_config_hash,code_hash,source_hash,model_hash}, create=False, expected_checkpoint_hash=None)`.

Models are caller-created CPU modules; no executable pickle load. Initial seed state is committed at cursor -1. Saves exact model tensors, optimizer integer-key state and group order, Python/NumPy/Torch RNG, module modes, requires_grad and gradient buffers. `model_hash` identifies initial model/architecture; changed weights get a new checkpoint digest.

`apply_completed(request_id, controller_result_hash=..., training_cursor=..., update=local_gradient_callback)` atomically commits completed update and callback result. Replayed request returns the original receipt without invoking callback; changed result/cursor or non-increasing new cursor refuses. Failed/uncertain mutation poisons instance; close and restore known committed state. `.checkpoint_hash`, `.training_cursor`, `.close()`.

Retain trusted checkpoint hash separately and use it on production restore. A replaceable journal with no independent checkpoint is not rollback protection. The callback may perform local gradient work only, never remote calls.

### `native_forecast_learning.py`

`NativeForecastLearner(context, decoder, optimizer, config).step(request_id, as_of, through_cursor, source_hash, input_hash, sessions, expected_sessions_hash, feedback, expected_feedback_hash, learning_cutoff_ns)` performs real native B1/decoder autograd and optimizer updates from separately attested Frankie feedback. Full prepared context, QSV masks and typed teacher inputs are preserved. Does not create market labels or update Granite.

`LearningConfig`: explicit timing/path_gap stage; presence/delay/gap/path weights; full session weights; timing-policy, query-policy, split and optimizer hashes. `optimizer_identity` binds effective settings.

Typed feedback: `FrankieFeedback(request_id,input_hash,source_hash,available_ns,principal_receipt_hash,sessions)`; `SessionFeedback(session_id,timing,gap,path)`; `TimingLabel(previous_ns,previous_delay_ns,next_ns or None,observed_through_ns,available_ns,evidence_hash)` and `ValueLabel(query_ns,value_usd or None,observed_through_ns,available_ns,evidence_hash)`. Timing/query positions are offsets from session open; availability times are absolute UTC nanoseconds. None stays missing/masked, never becomes zero.

Timing stage trains native B1 plus timing and session projection with STOP/presence BCE and median delay pinball. Path/gap stage freezes native B1, timing and projection while fitting median value heads, preserving timing behavior. This is a callback implementation, not a completed actual Sunday training configuration or principal feedback attestation.

## What the next chat must finish

1. Read final code-state receipt, git status and current commits. Do not redo passing component checks. No live background tasks should need waiting after handoff.
2. First align extraction-runtime identities: current bind_prefix requires identical DBN extraction hash, including the installed native binary. The prepared GitHub runtime is Linux/Python 3.11; a different OS/Python on the training host may produce a different identity despite equal source wire. Use the same pinned extraction runtime, or design and review explicit independent source/BOSS extraction pins retaining both identities and exact wire proof. Do not bypass the equality check silently. Then execute the prepared full source mapping once on a host with space, using fixed S3 objects and independent byte witnesses; retain mapping/index/runtime receipts. Inspect errors, never skip records. Its observed runtime hash is bootstrap/environment evidence, not independently reproduced prior-runtime identity.
3. Build the actual Sunday BOSS source journal and honest selected-day source scope. `mbo_source.ingest_sources` has NOT run on actual Sunday yet. Do not relabel a PROBE_ONLY scope as result-bearing or silently substitute the original four-date raw-manifest scope. Bind actual journal prefix with the full mapping.
4. Implement the durable cycle coordinator tying completed controller result → real `agent_file_handoff.export_handoff` → verified actual receiver attachment → principal-authored feedback → `NativeForecastLearner.step` inside `BossTrainingCheckpoint.apply_completed` → new lesson persistence and completion. This coordinator does NOT exist yet.
5. Coordinator must return already-completed cycle BEFORE constructing/validating an old controller whose model pin predates training. Persist feedback and its attestation before updating. Training callback must be lazy so deduplication runs before preparation/forward. If the checkpoint committed but the cycle completion did not, recover stored update receipt with no second gradient step.
6. Journal intent before any actual principal call. An ambiguous interrupted call must recover its existing output or remain explicit; never silently resubmit. All causal availability and source/request/input bindings must remain exact. New lessons become usable only after their availability cutoff, separate from immutable Memory A.
7. Resolve actual principal execution through the existing authorized Frankie route. `emit_frankie_spawn.py` only renders a prompt; it does not run an API call. A historical `claude-fable-5-1` session ID is not proof of current principal execution. Runner `calculation_result.json` cannot be substituted for Frankie-authored findings.
8. Connect probes at actual data delivery, inventory, full causal handoff, Frankie calculations, reasoning, learning, checkpoint/readback and completion. Add focused integration checks only for the newly composed seams and interruption cases.
9. Verify actual full request admission/configuration before paid relaunch. Current 4096-token Granite ceiling is a real capacity question; no silent truncation to fit. Keep the actual native forecast/session architecture and complete causal evidence.
10. Once the actual connection is ready, reuse the stopped Pod and go directly into the Sunday run with a new bounded lifecycle and independent cleanup. Do not schedule another smoke. Preserve completed artifacts and progress on any failure.

Existing frozen boundary: `agent_file_handoff.export_handoff` verifies executing clean BOSS commit, actual controller/native journals and independently trusted checkpoints, then emits a deterministic file bundle. Frozen receiver `prepare_boss_attachment.py` independently binds exact result/delivery/mapping/pin files and attributed_input mode. Source-binding `CALLER_ATTESTED_WITH_BYTE_WITNESS` is explicit interim provenance, not invented authorship.

Frozen pre-Sunday memory: 166,700 bytes, SHA256 `4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a`. Do not use the refreshed post-Sunday prior from old runs.

## Suggested first message in the new chat

> Continue from FRANKIE_BOSS_NEXT_CHAT_HANDOFF.md and HANDOFF_CODE_STATE.json in the previous task's outputs folder. Finish the actual Frankie-to-BOSS feedback coordinator and full Sunday data handoff, then proceed directly into the Sun run when ready. Reuse the retained Granite Pod and all completed evidence. No more smoke runs or repetition of passing tests. Do not claim the connection is complete before the actual seams are wired.
