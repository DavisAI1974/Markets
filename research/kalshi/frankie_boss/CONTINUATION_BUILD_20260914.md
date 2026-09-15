# Frankie build continuation — September 14, 2026

## Authority and status

Read the incoming `FRANKIE_BUILD_HANDOFF_20260914_CURRENT.md` before older reports. using-agent-skills ran first. The original combined workbook Current Snapshot and Source Crosswalk supplied the reconciled baseline. This continuation advances software; the whole build remains incomplete and Sunday remains on hold.

No new hosted endpoint, venue order, market-data acquisition, production training, held-out reveal or actual Frankie session ran. All model-shaped test fixtures are synthetic. Keep C3/C4/O7/O9 deferred under the incoming sequence.

## Reviewed increments

### Granite diagnostics

BOSS integration commit `abad0043` imports worker `89c4f08f1ec3c4f70409a636c4002fb2144bde64`. Every startup poll now retains a timestamped endpoint descriptor before validation. Startup/CloudWatch/cleanup failures retain full sanitized SDK service messages and request IDs. Coordinator exception evidence includes sanitized tracebacks. Runtime admission consumes original responses, not sanitized copies. Existing budget and startup deadlines are unchanged.

Root independently ran deployment, coordinator, startup and run-artifact tests: **100 passed in 5.11s**. No hosted retry occurred. Historical attempt `34906771361` remains a startup failure with confirmed cleanup; its provisioning cause remains unknown. Discarded historical descriptors and full deletion messages cannot be reconstructed from the retained files. The worker found no straightforward configured local AWS CLI/credential-file route for read-only provisioning recovery; this does not assert that all possible account access is absent.

### BOSS attachment preparation

Separate receiver commit `899cbe4a71b74cfde0945f7a3b9bfb39e3e5b607` adds the coordinator-side `prepare_boss_attachment` command, its documentation and tests. Follow-up `b4f364f0812cd964c68faf3cef948b28d4603c90` normalizes two appended lines in new files to LF; it changes no behavior. The command consumes an independently SHA-pinned coordinator record, existing verified delivery, exact committed BOSS export, and an explicit caller-attested mapping. The unchanged authoritative receiver verifies the inputs; the command exclusively creates a source crosswalk, existing AttachmentRequest and preparation receipt outside the code checkout and exported attachment.

Root reviewed all three added files and independently ran **23 tests in 4.16s**. Tests include prepared input through the existing emitter and ordinary read-back/citation. The author additionally exercised the actual command line with unmocked committed execution identity and explicitly synthetic files. Authentic source equivalence and population metadata origin are not established by preparation.

Receiver broad suite initially recorded **2,140 passed and 9 failed in 415.34s**. All failures were byte-reproduction checks affected by Windows CRLF checkout conversion, not changes to the receiver implementation. Exact HEAD bytes were restored in this isolated worktree only, including source inventory/registry/manifest and the historical principal findings file used as a seed provenance input. No findings or seed were regenerated. The affected-module rerun narrowed this to three seed provenance failures, then the seed rerun passed after its final exact-byte input restoration. Root independently ran all three affected modules plus preparation at final `b4f364f0`: **105 passed in 4.95s**. The entire 415-second directory suite was not repeated after the encoding correction; these are distinct scoped receipts, not an invented fresh full-suite pass count.

Byte audits record 76/76 manifest-listed artifacts exactly matching HEAD and 37 additional inspected paths (29 restored). No historical content was committed; the receiver commits touch only the three new preparation files. `git diff --quiet HEAD -- research` and the real `_executing_commit()` passed despite stale normalized-file status entries.

### Concrete execution providers

BOSS integration commit `baef303063879c6283805f0687540f8f8becc58d` imports worker `63e0847ce69651eeff439426f1069bba2257dfd3`. The slice adds a direct stdlib HTTPS exchange and an explicit local secret-file provider. Independent review found and corrected a slow-connect path that could outlast the ready lease before transmission. The HTTP timeout is now capped by remaining lease time; a delayed connect test confirms no transmission and no lease reuse.

The author ran the full explicit execution selection: **284 passed in 28.57s**, comprising 250 existing and 34 new provider tests. Root independently reran providers plus transport on the combined branch: **69 passed in 5.86s**. Tests include generated-certificate loopback TLS, exact request bytes, redirect retention without follow, bounded/truncated responses, secret binding/redaction and expiry. An initial independent TLS fixture failure was traced to this workstation's injected truststore server wrapper and fixed in test setup; production TLS verification remains enabled.

The provider refuses redirects, retries, environment proxy discovery and debug logging. OS DNS can delay function return, but an expired connect refuses before transmission. A hard process-return deadline still requires a runtime boundary. The file provider requires explicit binding and a bounded regular JSON file; private ACLs, encryption, provisioning and rotation remain operator/deployment responsibilities. Account ownership, valuation, reflection and venue acceptance are not established by these adapters.

## Dipole teacher status

**The dipole teacher software is built.** `teacher.py` contains the auxiliary TeacherHead and controlled training harness. The typed dipole target, masks, six B2/C1 R3 columns, preserved R2 control, plain/shuffled/random controls and paired machinery are implemented. The teacher supplies training supervision for BOSS hidden states; it is not a separately accepted inference service.

Fresh root regression of `test_teacher_controls.py`, `test_c15_teacher_r3.py`, `test_c15_teacher_attachment.py` and `test_dipole_target.py`: **119 passed, 1 skipped in 77.77s** on Python 3.13, PyTorch 2.9.1+cpu. The skip requires CUDA for a non-CPU generator. This is synthetic software evidence. Real fitted artifacts, complete production inputs, declared experiments and D0–D5 empirical acceptance remain absent.

## Population-origin finding

See `FRANKIE_POPULATION_ORIGIN_AUDIT_20260914.md`. A legacy day-output path produces the eight required field shapes, but its saved JSON lacks the current BOSS request/source/cursor/cutoff/arm and independent admission binding. The raw-MBO finding schema remains distinct. No new receipt authority or fabricated population fields were invented. A response to an attachment cannot retroactively authenticate metadata used to build that attachment.

## Remaining readiness prerequisites

1. Authentic source mapping, independent operational pins, and causally admitted population metadata producer/receipt.
2. Real source/QSV mapping, masks, session configuration and declared-load throughput/recovery evidence. Existing producers and assembly should be reused.
3. Actual fitted native/decoder/scorer/calibration artifacts and separately authorized empirical experiments. Synthetic snapshots do not satisfy this.
4. Authentic account, valuation, order/fill and reflection collection; deployed secret/access governance; heartbeat/drift, cancel/flatten and recovery drills; private incident/budget packet. Do not invent risk/P&L formulas or infer reflection from matching IDs.
5. Actual hosted Granite runtime/controller acceptance, required context/capacity/repeatability/failure/latency evidence; then actual combined agent operation.
6. After initial-sheet work, review/adopt preserved C3/C4/O7/O9 under the existing sequence.

## Preservation and eventual Sunday

Root authority/protected legacy-output tests: **18 passed in 5.25s**. Preserve separate BOSS and agent histories, Memory A, protected prompt bytes, OPEN_ITEMS terminal states and all previous evidence. E:/Markets and the deferred predecessor checkout remain outside this work.

Eventual Sunday remains 2021-10-03, anchor `33746436209`, frozen pre-Sunday prior 166,700 bytes / SHA256 `4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a`. Preserve the prior 44 findings. October 1 remains explicitly waived. Use frozen `fetch_frankie_ledgers` → `emit_frankie_spawn` → actual agent session and separate evidence worktree once ready. No Sunday run is scheduled here.

## Workspace

Current task root: `C:/Users/A/Documents/Codex/2026-09-14/continue-the-frankie-build-in-parallel`.

- BOSS integration: `work/Markets-integration`, branch `codex/frankie-continuation-20260914`, based on incoming `211c10134bc3399fec8a19735626e6243a49a1ab`.
- Receiver: `work/Markets-source`, separate lineage based on `2b4bae18d5bc34e4d08135631fac315be94130c4`.
- Receiver branch: `codex/frankie-attachment-preparation-20260914`; tip `b4f364f0812cd964c68faf3cef948b28d4603c90`.
- Knowledge audit: `work/source-knowledge-byte-audit.json`.
- Additional exact-byte audit: `work/source-extra-byte-audit.json`.
- Receiver run logs: `work/source-tests.log`, `work/source-affected-tests.log`, `work/source-seed-recheck.log`; the root final 105-test result is also recorded in this task's tool output.
- Synthetic command-line evidence: `work/source-cli-synthetic/cli-result.json` and `prepared/`.
- Task plan/checklist: `work/tasks/plan.md`, `work/tasks/todo.md`.

## Reconciled workbook

Updated derivative: `outputs/combined-build-continuation/Frankie_BOSS_Combined_Build_Continuation_20260914.xlsx`.
SHA256: `a72b35d7fcdf5f43e72296fdb0e5496629c3b777bafc737162659c0dffc19bb4`.
Software baseline is BOSS `baef3030` / receiver `b4f364f0`; documentation-only closeout can follow without changing these implementation identities.

Artifact Tool authored and reimport-verified 27 changed cells. Five changed views and the final corrected header were visually inspected. Only Current Snapshot and Source Crosswalk XML changed; all 39 other ZIP parts remain byte-identical, including the eight historical sheets, eleven table parts, chart, styles and shared strings. The original baseline workbook remains untouched at its recorded SHA256. Audit and verification files accompany the derivative.

Reviewed implementation identities are recorded above. Publish only fast-forward updates to the existing BOSS and receiver remote branches. Preserve the source/worker checkouts and all diagnostic evidence; no old worktree cleanup is needed.
