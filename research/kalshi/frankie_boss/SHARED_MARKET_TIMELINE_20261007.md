# Shared market timeline — 2026-10-07

Status: source-built bounded input/view slice; runtime unverified. No project imports, tests, data/scientific/model runs, installation, AWS calls or launches were performed. AST parsing and diff whitespace inspection only. This does **not** establish all 99 registry entries ingested/computed, native Frankie training, every adviser consuming the same view, or an E2E success.

Greg's accepted requirement is one faithful shared market picture immediately before/as evidence reaches Frankie and those influencing him, within existing answer/private/Jev roles. Calculations can finish in any order; presentation follows the original INPUT/journal order, with exact event and receive clocks, original ties and actual availability. The contract never creates empty nanosecond rows, fabricates zeros, changes target formulas, or backfills completed knowledge into earlier events.

## Missing-coverage correction (Greg, 2026-10-07; source-built on the d6af990 core, runtime unverified, review required)

Greg's rule supersedes every earlier completeness wording: no day or time is rejected from the reconstruction because data is missing; the instant stays in with a thinner picture. The core now implements it as follows. `binding()` carries `required_native=False` and `missing_coverage=every_authentic_boundary_kept_with_thinner_explicit_picture`; because the binding includes the implementation SHA256, a ROOT built under the d6af990 binding is refused explicitly and needs a successor ROOT (none has been built; nothing ran).

- **Layers are optional, listed, never blocking.** `SharedMarketTimeline` opens with whatever the completed ROOT published: `root.frames`, `root.prices`, `root.structures` (each from its pin, or listed absent when the ROOT recorded `status: absent` or no pin), `native.member`/`native.lifecycle` (absent with bedrock off, since `selected_files` returns nothing), `external` (absent when no day file was attached). `report['coverage']['layers']`, `absent_layers`, `present_layers` and `identity['absent_layers']` name them. Every picture carries `coverage` (absent layers, source status, exact-clock placement, readable record, normalized evidence).
- **Integrity stays a distinct visible failure.** A pin that names another path, pinned bytes/hashes that differ on read, a derived row contradicting its INPUT boundary, journal counts that disagree with the sealed source, a native ledger whose identities/clocks disagree, or a day file for another day still raise; they are never listed as missing coverage. A bedrock-on ROOT with incomplete or altered native artifacts raises inside `selected_files`.
- **`report['complete']` is source exhaustion only**: every journal envelope, every pinned layer row and every external row read with bytes, hashes and counts verified. `report['completeness']` says so in words; `report['coverage']['inputs']` counts applied/failed/unpaired/unreadable/unplaceable inputs and `all_inputs_applied`; `coverage['all_layers_present']` is separate. Thinner coverage never withholds `complete`.
- **`iter_applied()` refuses nothing.** Every instant is yielded with `arithmetic = {status: present}` (the unchanged original APPLIED payload) or `{status: absent, reason}` (failed, unpaired_input, input_without_readable_observation, applied_with_unknown_outcomes); `evidence` is `None` in the absent case. `report['arithmetic']` lists the absent ordinals by status. No replacement operand is derived and no teacher label changes.
- **The teacher runs its existing equation only where its operands exist.** `frankie_box_experiment_teacher._teach` feeds the pinned R3 pass the contiguous APPLIED prefix (every adapter cursor from zero, which `c15_teacher_r3.iter_raw` requires) and lists every other instant in the receipt's `shared_market_arithmetic` (`rows`, `through_applied_cursor`, `absent[]` with ordinal/cursor/reason, `ended_at` for a cursor gap). The day's identity scope (`through_cursor = record_count - 1`, the learner binding) is unchanged; the computed-row count is reported beside it. The receipt's `shared_market_read.complete` is checked as exhaustion of the shared read, nothing more. A day with zero applied rows still produces the complete shared read; the pinned `PT.finish` then refuses with its own "nonempty complete prefix" message, which is the equation's refusal, not the day's.
- **ROOT**: `--shared-market-policy` no longer requires `--bedrock on`; `frankie_box_experiment_root.sh` takes `BEDROCK` (on | off; default on under the shared policy, the published route). `shared_market_sources` pins now carry `path` (the d6af990 pin had bytes/sha256 only, which the reader's `pin['path']` check would have rejected at runtime), and a spool the legacy pass did not publish is recorded `status: absent` instead of failing the receipt.
- **Unchanged**: no dense grid, no retrograde event-time sort, no future backfill, no waiting for all 99 entries; native GROUP_CLOSE/member identity and FINALIZE post-stream status stay source-bound; lifecycle rows are never promoted to persistent entity state; completed signed-flow/roll20 aggregates stay completed-only; `SharedFrameView` still requires the exact ROOT group membership because the existing F_LAST search axis is that membership (an absent frame spool leaves the search without its axis; that is the search equation's operand, reported, not a rejected day).

**One-day test reports (Greg, 2026-10-07).** The core report now carries what the inspection reporter needs: received (`identity` with every source pin, journal bytes/sha256, external, `absent_layers`), used (`coverage` with layers and input dispositions, `completeness`, `arithmetic`, `journal.dispositions`, `sources[*].dispositions`, `completed_sources`, `unplaceable_input_clocks`, `closed_source_without_root_frame`), produced (`outputs`: pictures yielded, exact/extracted/envelope placements, updates and publications presented, invalidations, final `publication_frontier_ns`, cursor-domain extents for source INPUT index, extracted cursor, adapter cursor and journal ordinal; `external_publications`; `integrity_failure` when a pin/count/identity contradiction stopped the read, recorded before re-raising; `stopped` when a consumer closed the iterator early). The teacher receipt carries the whole read under `shared_market_read` plus `shared_market_arithmetic`. `deploy/aws/box/frankie_box_workflow_inspection.py` (Codex's reporter, extended, not duplicated) gained `--write` (one `<run-dir>/days/<day>/inspection/<piece>.md` per canonical piece plus `index.md`), a received/used/produced projection of every opened metadata object (recursing into `shared_market_read`), and the new field names in `FIELDS`. Invoking it after the one-day test belongs to the orchestrator's owner. The files are temporary operator review only.

Consumers outside this core that still pair `complete` with all-success or all-layer requirements (requests to their owners, not edited here): `frankie_box_adviser_market.AdviserMarketContext.read` requires the APPLIED picture at exactly `record_count - 1` (a failed or unpaired final INPUT leaves no cutoff picture; it should select the last APPLIED picture at or before the cutoff and list the thinner tail); `frankie_box_experiment_classroom_v2` refuses a ROOT whose `external.status != 'attached'` (an absent day file should thin the classroom's external evidence, not stop the day) and `frankie_box_classroom_code` binds `through_cursor == record_count - 1` as scope (correct as identity; it must not read it as "every cursor applied"). `frankie_box_classroom_code` reads `report['complete']` together with its own anchor requirement, which is an operand check and acceptable.

## Implementation boundary

`deploy/aws/box/frankie_box_market_timeline.py` owns `FRANKIE_SHARED_MARKET_TIMELINE_V1`, the source-policy binding, exact F_LAST membership contract, `SharedMarketTimeline` and `SharedFrameView`. It reuses retained calculation rows and existing verified parallel source decoding; it performs no new scientific replay.

`SharedMarketTimeline(calculations, day=..., workers=15).iter_pictures()` is the full source interface. Each item contains the unchanged matched APPLIED payload (or `None`) and the complete picture. The picture retains original INPUT and outcomes, source status, ROOT extracted INPUT index, original journal ordinal, original adapter cursor, source member/session identity, exact normalized clocks when a successful APPLIED exists, and original raw clock representations separately. Extracted INPUT index and adapter cursor are not conflated after a failure. An original unknown/unpaired envelope remains diagnostic evidence, never a fabricated normalized event.

Pictures include all currently retained source/instrument snapshots, a separate active-instrument selector, all changes emitted at the current boundary, and external publication state. Snapshot references are read-only caller inputs; classroom copies selected pictures before retaining them. Prior snapshots keep their original source cursor/clock and are explicitly last-observed state, not invented intermediate books. Reset and source-scope transitions invalidate affected instrument snapshots. Lifecycle ledger rows are ordered changes; an arbitrary last lifecycle row is not falsely promoted to an entity-state snapshot.

The full reader's completion report distinguishes original failures/unpaired/unknown outcomes, unreadable INPUTs, unplaceable clock/identity updates, source groups without a matched closing APPLIED, successful source closes missing a ROOT frame, and producer FINALIZE rows. Original pinned sources remain retained. Full-source byte/hash/count checks and producer row identity/clock checks must finish before `complete=True`; `complete` means that exhaustion and nothing about layer or input coverage (see the correction section). A contradictory pin is an error; an absent layer is a listed thinner picture, not an error and not a substitution. Old retained source identities are not upgraded in place.

## Layer and role mapping

| Input/role | Shared view built in this slice | Consumption and limit |
|---|---|---|
| Raw INPUT/APPLIED and diagnostic envelopes | Original journal order and original records; successful normalized coordinates and raw clocks both retained | Full picture reader and classroom source scan; teacher equations receive the original APPLIED unchanged. Failed/unpaired/unreadable evidence is visible in the generic reader and passes through `iter_applied()` as an explicit absent arithmetic disposition; the pinned teacher equation runs on its contiguous applied prefix and lists the rest rather than invent targets. |
| ROOT full-depth book/FIFO/activity/integrity/native frame/observation/raw group records | Pinned `frames.jsonl`, exact original emitting INPUT and instrument | Last-observed state across all instruments, plus exact current updates. No reconstructed book between producer snapshots. |
| Legacy price/projection rows | Pinned `prices.jsonl`; V2 origin provenance retained, availability at explicit group-close INPUT | Raw trade timestamp never mistaken for the later row's emission time. |
| Legacy structure observables | Pinned `structures.jsonl`, exact cursor/instrument/receive tuple | Ordered full source rows; no new structure formula. |
| Native exact member rows | Completed native producer when the ROOT ran bedrock on: pinned ledger and source policy, full row identity and clock crosschecks; listed absent with bedrock off | Same-boundary member updates and last-observed member snapshot when present; a thinner picture without them, never a blocked day. Existing search placement still uses its original F_LAST science. |
| Native lifecycle rows | Required exact ledger; GROUP_CLOSE identity/clock bound to same-boundary member | Full ordered changes. FINALIZE stays explicit post-stream evidence. A generic event row does not imply a persistent entity state. |
| External historical points/curve tables | Every original column/row and explicit entity key; publication clock checked with existing day-file contract | Release at first original market boundary whose observed receive frontier reaches publication time; preserve publication timestamp, table ordinal and row ordinal for ties. Earlier receive-clock ticks are not reordered. Remaining unpublished rows, missing points and after-halt counts remain explicit. |
| Legacy signed flow and roll20 | Retained exact completed source references listed in picture identity/report | Shared live reader does not invent contributing-cursor provenance for completed second aggregates. Existing search second-end/as-of formulas are unchanged. A common exact live placement under retrograde input clocks still needs source provenance; this is an explicit remaining gap. |
| Native compressed sections 4.2/4.4, result/receipt, legacy observable alias, finalization | Exact completed native artifact selection retained in report; authoritative live ledgers used above | These completed references are not claimed as consumed target arithmetic or earlier live features. Existing scientific-teacher completed-evidence reader remains its own consumer. No giant Markdown rendering added. |
| Dipole target/control/answer/mask products | Existing original raw teacher and Dipole/F_LAST consumers preserved | Shared market context augments their interface; no new labels, dimensions, controls, loss or model parameters. Host answer keys are not source inputs. |
| Control/knowledge/arm inputs, sealed answer roles, disabled shadows, append-only outputs | Existing roles and walls preserved | They are not forced into numeric market planes. Memory A remains historical/not_bound; disabled shadow producers remain disabled. |

The retained 99-ID registry crosswalk groups are 6 raw + 49 calculation/clock + 23 control/knowledge/arm + 9 sealed answers + 2 disabled shadows + 10 append-only outputs. These are registry roles, **not** 99 independent numerical planes or a count of complete computations. The crosswalk is `audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json`, pinned registry SHA256 `239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1`. Its originally pinned registry file is not present in this checkout. Prior `ROOT_PLANE_COVERAGE_20261006.md`, `KNOWLEDGE_CONSUMER_COVERAGE_20261006.md` and the workflow inspection map remain source/audit evidence, not runtime completeness proof.

## Actual consumer connections

- `frankie_box_experiment_root.calculate_day/_calculate_day`: optional **new-request** shared policy binds the versioned timeline implementation into source identity and pins the actual frame/price/structure spools (with `path`) in completion, recording an unpublished spool as `status: absent`. Bedrock on is the published route and no longer a precondition; with bedrock off the native layers are listed absent by the reader. Existing recovery/source identity comparisons refuse incompatible reuse.
- `frankie_box_experiment_teacher._teach`: supplied shared policy and ROOT must match the same ingestion/journal/external inputs. Its actual raw walk consumes `iter_applied()` and feeds the pinned pass only the contiguous applied prefix, listing every other instant in `shared_market_arithmetic`; at every computed handoff the control teacher and R3 raw teacher receive the identical full `market_picture` context. These are concrete internal `JournalTeacherR3.control` and `raw_teacher` objects in the teacher-only Dipole row pass, not two independently proven user-facing teacher seats. Their APPLIED argument, evidence hashes, measurements, targets and equations remain unchanged. This establishes that row pass's shared view availability, **not** a claim that fixed equations use every derived field or that BOSS/scientific/Dipole exchange transports the richer context in every selected field. Raw recovery and the completed receipt bind the exact shared identity/read report. Completed raw recovery can reuse its matching complete read, never claim a new iterator ran.
- `frankie_box_classroom_reader.read_day`: SOCRATIC/VERIFY learner-owned reading uses the same ROOT policy/reader with a separate learner state/recovery namespace. It does not import the host answer snapshot. Teacher/reader producer hashes now include the timeline implementation.
- `frankie_box_experiment_journal._frame_index` and `frankie_box_experiment_native.read_columns`: share one original membership/cursor/instrument/receive contract. Native row emission clocks, row identities and FINALIZE semantics are checked, not inferred from timestamp proximity.
- `frankie_box_experiment_search.build_series`: for a selected shared policy, its actual final numeric/cell mappings pass through `SharedFrameView`, which validates common exact frame identity/axis and exposes original-order row pictures. Existing raw/native/price/structure/Dipole/external readers and disposition reports feed these mappings. Transform/lag/chance mathematics and running-maximum F_LAST lag axis are unchanged. This is the existing F_LAST scientific projection, **not** a claim that all raw-input timestamps became separate target rows or that legacy aggregate provenance gaps disappeared.

Classroom code integration (source-built, runtime-unverified): the V2 caller requires the exact shared teacher/ROOT/ingestion/external publication identity, then consumes one complete ordered picture stream. It binds original adapter cursors to existing first/last/min/max PRESENT anchors, retains their complete untrimmed pictures in its saved phase, and passes an exact-source context to actual component and summary answers. The context also exposes the full `iter_pictures` interface; anchors supplement rather than replace that source. Component evidence carries full typed pictures preserving clocks, bytes and float bits; summary carries complete read/disposition context. Existing Dipole mathematics, targets, raw source hashes and teacher-key wall are unchanged. Failed/unpaired/unknown and unclosed input dispositions remain visible; they are not invented target measurements. At most four anchor selections per component are retained; no runtime memory/performance result is claimed. Jev's governed material remains Dipole/external/directive only and does not receive the new full picture. Lawful precomparison Jev/adviser full-view wiring remains an explicit gap; this classroom slice does not establish all-agent, every-field computation or native training.

## Required caller wiring and retained fast paths

CCode owns `experiment.py`, queue/cores/controller and `pod_root_loop.sh`; this slice does not edit them.

1. **Run.root:** persist `shared_market_policy=FRANKIE_SHARED_MARKET_TIMELINE_V1` for authorized new request identity; pass shell `SHARED_MARKET_POLICY=FRANKIE_SHARED_MARKET_TIMELINE_V1`. `frankie_box_experiment_root.sh` forwards `--shared-market-policy ...` and `--bedrock $BEDROCK` (default on under the policy; `BEDROCK=off` is a lawful thinner native-absent picture). Native selection must not be silently appended to an old saved plan/request/result. ROOT retained fast-path must match the selected versioned policy/source receipt before accepting old completion.
2. **Run.teacher and owner-lane teacher:** pass `SHARED_MARKET_POLICY=FRANKIE_SHARED_MARKET_TIMELINE_V1` and `CALCULATION_ROOTS` as an equal-length comma list of absolute completed owner-local ROOT directories, in the exact order of `DAYS` and `INGESTION_RECEIPTS`. The teacher shell forwards `--calculations ROOT --shared-market-policy ...` per day. It refuses partial/mismatched policy arguments. A copied remote owner's absolute path is not a local source. Both scientific/source consumer and retained paths must remain on the appropriate owning lane.
3. **Teacher retained fast-path:** a new shared-policy request cannot reuse a legacy teacher receipt. Require exact teacher `shared_market_identity` equal to the selected ROOT reader identity, matching `shared_market_read.identity`, `shared_market_read.complete=True`, exact ingestion receipt SHA and identical external presence/SHA. Preserve incompatible results and use an explicitly identified successor. V2 enforces this consumer boundary too.
4. **Classroom:** new shared-policy ROOT is detected from its source binding; the V2 caller validates teacher/shared/external equality before any retained or new shared classroom read. Old no-policy sources remain explicitly legacy. No fallback from a required shared source to a raw-only or host-key reader.

## Remaining work and decisions

The shared input requirement is not fully closed. Caller activation/fast-path wiring above must be integrated by its owner, followed by source review; no run is authorized by this document. Jev's comparison/scoring material remains intentionally governed by its existing schema; its lawful raw-market view and Granite's bounded post-class adviser view have not been expanded by this core slice. The separate adviser integration owner is actively wiring those boundaries. Scientific/BOSS teacher exchange still requires an exact selected-field transport trace; assignment of a `market_picture` to two internal raw equation objects does not establish all teacher seats received it. Principal/brain/native representation and checkpoint consumption of the new view also remains unproven. A path or receipt is not proof of that consumption.

Completed second aggregates need exact contribution/availability provenance before a shared live reader can safely place them through arbitrary receive-clock reversals. The existing F_LAST search rule is preserved and disclosed, not silently replaced. Source-group closure, lifetime/member snapshots and lifecycle events are represented honestly; further persistent lifecycle-entity state requires the original producer's explicit entity semantics, not “carry the last row.”

Reconnecting original native representation/training requires the retained applicable model/checkpoint lineage and the existing target/mask/control interfaces. This slice does not choose new scientific objectives, convert IDs/dates to numerical signals, revive Memory A, invent missing labels, initialize new weights or claim classroom code equals native training. Questions about target equations are separate from the now-built shared input availability interface.

## 2026-10-07 evening: the stopped WIP finished, the stages instrumented, the efficiency pass (source-built, runtime unverified, review required)

Greg resumed the workflow_reports role (relayed by the parent). This section records what the source now does after the pass; nothing ran, no account call was made, no AWS resource was created or changed. Every change is source-built and runtime-unverified; a fresh independent review is required before integration.

**The WIP hunks of the stage pass (checkpointed `ec1b6420..85173aee`, never returned) are finished, none reverted.**

- `frankie_box_market_timeline.SharedFrameView` keeps the finished hunk: a frame spool without the exact ROOT membership columns no longer refuses the search; the F_LAST axis stands in spool order with its receive clocks, `report['exact_membership']` is `present` or `absent` with the reason, every yielded picture carries `membership`, and a spool whose membership columns contradict each other still raises inside `frame_index` (corruption, not missing coverage). New in this pass: `SharedMarketTimeline(..., input_witness=None)`. A caller that measured the sealed journal's bytes and sha256 in the same process hands them in; when they equal the ROOT's container pin the reader skips its own full re-read and records `report['input_verification'] = {basis: caller_measured_witness_equal_to_pin, re_read: False}`; an absent, malformed or different witness falls back to the reader's own full hash (`basis: full_read_by_this_reader`). The pin, the identity and the raise on a mismatch are unchanged; the compact reader still verifies the chained head hash as it reads. Because the file's bytes changed, `binding()['implementation_sha256']` changed: a ROOT built under an earlier binding is refused explicitly and needs a successor ROOT (none exists; nothing ran).
- `frankie_box_experiment_teacher._teach` keeps the finished equation_not_run paths (a journal without the full-book observation, or a day on which no original APPLIED operand reaches the pinned equation, publishes a receipt with `status: equation_not_run`, `equation_not_run: {reason, operand, rows: 0}`, no rows file, exit 5; the day goes on) and the `workflow_report` on every receipt. The dead retained-receipt `pass` block is gone (its rule stands as a comment: a retained equation_not_run receipt is not a duplicate publication, the walk is attempted again). New: `phase_timings` in every receipt (`verify_ingestion_receipt`, `verify_sealed_journal`, `open_shared_picture`, `retained_receipt_checks`, `first_input_entity`, `raw_pass_rows`, `finish_attachment`, `close_walk`, `snapshot_rows_attachment`, `external_section`), the journal witness measured once and handed to the shared reader, and `workflow_report.use.sealed_journal_verification` naming both measurements.
- `frankie_box_experiment_teacher.sh`: per-day exit 4 (rows published, external section listed) and 5 (equation_not_run) are LISTED outcomes with a published receipt, not failures; any other nonzero code is a failed day; the step exits 3 only when a day failed, and prints `failed / listed / days` at the end.
- `frankie_box_experiment_data.py` keeps the finished hunk (`_pin_all` process pool, largest file first; `--workers`; `workflow_report` in MANIFEST). New: `_pin` returns seconds per file, `hashing` carries `bytes_per_second` and `slowest_files` (top five), and the sealed journal's producer pin from `ingestion-receipt.json` (`journal_bytes`, `journal_sha256`) is set as the linked journal's `expected` so a measured difference raises `linked artifact differs from its producer pin (...)` with both values named (the same check the native artifacts already had); `hashing.producer_pins_checked` and `workflow_report.use.producer_pins_checked` list them. `frankie_box_experiment_data.sh` accepts `DATA_WORKERS` as the orchestrator's name for `WORKERS`.
- `frankie_box_experiment_search.py`: new `workflow_report` in the search MANIFEST (inputs: the export manifest pin and every source with path/bytes/sha256/rows, the directive, the code pins, workers; use: the axis, `exact_membership` from the shared view, every leakage gate, every excluded/missing/listed disposition, `not_searched`, `cells_not_counted`, transforms and lags, the chance check, `phase_timings`, `fft_cache`; outputs: the coupling parts with pins, the counts, the planes receipt, the refusals and the save/resume wait), `phase_timings` (`identity_and_recovery`, `prepare_series` or `prepare_series_loaded_from_recovery`, `transform_steps`, `cells_and_jobs`, `couplings`, `publish`), and the per-worker partner FFT cache (below).
- `frankie_box_workflow_inspection.py`: the finished hunk (nested workflow reports, the classroom projection's `received`/`pinned`/`phase_timings`, the school/teacher/search/brain-entry artifact paths, the extended FIELDS) is united with every Step 8 change of `origin/ccode/teacher-tasks-20261006b-step8-corrections` (`5f111885`): the `inspection`-object docstring, `QUEUE_DIR`/`CONTROLLER_DIR`/`LANE_ENTRY_FIELDS`, the Step 8 FIELDS block, `FOLLOW`/`FOLLOW_DEPTH`/`pins()`, `lane_records()` for the preflight piece, the successor-chain follow loop in the per-piece section, the Jev `request`/`status_file` artifact paths. The Step 8 side's `contextlib`/`io` capture is not used because this file already captures every section through `emit()`/`_OUT`; `lane_records` emits through the same path. Added projections for this pass: `input_verification`, `producer_pins_checked`, `slowest_files`, `bytes_per_second`, `walk_seconds`, `dipole_missing`, `dipole`, `exported_from`, `this_root`, and the Step 8 teacher-caller names (`rows_missing`, `rows_refused`, `rows_waiting`, `external_waiting`, `refused_days`, `root_waiting`, `retries`, `waited_seconds`) under `USED`.

**Efficiency and data processing (Greg, 2026-10-07; source-built, estimated from the data shape, not measured).**

| Change | Mechanism reused | Estimated effect | Canary measurement |
|---|---|---|---|
| Teacher: one full hash of the sealed journal per process (`input_witness`) | the teacher's own receipt check | one sequential read of the journal saved per teacher day (23.7 GB on the gold-standard big day; the volume's read throughput sets the seconds) | `phase_timings.verify_sealed_journal` vs `open_shared_picture` on a one-day teacher run |
| Export: parallel hashing, largest first, per-file seconds | the held lane's 15 workers (`WORKERS`/`DATA_WORKERS`) | wall bounded below by the largest file (the journal) instead of the sum of all files | `hashing.seconds`, `bytes_per_second`, `slowest_files` |
| Search: partner FFT cache per worker, per cell, capped (`FRANKIE_SEARCH_FFT_CACHE_BYTES`, default 512 MiB) | the existing `transforms()`/`couple()` split and the cell-ordered job list | of the four FFTs per pair (two rffts of y, two irffts of the products) the two rffts of y vanish on a hit: up to half the FFT work of the coupling phase when a cell's partners fit the cap; a prefix otherwise; rows, counts and parts invariant | `fft_cache` (hits/misses/not_cached) and `phase_timings.couplings` with and without the cache |
| Export: producer pin of the journal checked | the ingestion receipt's pin | no speed effect; a changed journal is a visible integrity failure instead of a silently re-pinned identity | the raise, if any |

AWS mechanisms checked against these stages through the live `Aws` connector (`retrieve_skill`: `aws-compute` with `references/instance-selection.md`, `aws-storage` with `references/ebs-knowledge.md`, `querying-aws-s3`, `querying-data-lake`, `creating-data-lake-table`, `ingesting-into-data-lake`, `aws-billing-and-cost-management`; `search_documentation` with `topics: ["agent_skills"]` on the stages' own words returned those and off-topic skills only). None applies to these three stages' hot paths, which read owner-local files on the box (the sealed journal, the ROOT spools, hard links under `/opt/frankie-box/work`), never S3: S3 byte-range or conditional reads, multipart or parallel transfer belong to the ingest fetch (not this role); S3 Select or Athena over the tape cannot verify the compact container's chained head hash or return the exact ordered envelopes the invariants require; S3 Metadata/Storage Lens tables replace list/head calls at scale and these modules make none; Glue/Iceberg copies of the receipts or day files would be a second build of pinned bytes that are identity-compared byte for byte; EC2 instance choice and SSM belong to the lane operator. What those references did settle for the code: the work directory must stay on EBS (instance store is lost on stop), and the hashing walls are bounded by the volume's read throughput, which is why `hashing.bytes_per_second` is recorded. No account call was made and nothing costs more.

**Cross-owner requests (precise).** (1) `deploy/aws/box/frankie_box_experiment.py`, `Run.teacher` (CCode): a day whose `experiment-teacher-rows/<day>/receipt.json` has `status: equation_not_run` is a listed day without Dipole rows, not a failed batch; record it as such and let the day advance (export and search already list the rows missing). (2) `Run.data`: pass `DATA_WORKERS=self.cores.DAY_RUN_CPUS - 1` (or `WORKERS`) to `frankie_box_experiment_data.sh`; today the export hashes serially. (3) `Run.search`: a day without a ROOT frame spool has no causal axis; the search refuses before its manifest (exit nonzero) and the step records `failed`; record it as `not_run` with the reason and let the day go on. (4) `frankie_box_adviser_market`, `frankie_box_experiment_classroom_v2`, `frankie_box_classroom_code`: the requests of the correction section above stand.

**Open in these stages.** The `frames_pin is None` refusal in `build_series` (no axis without the frame spool; the day's search is the equation that lacks its operand, the orchestrator decides the day). Completed signed-flow/roll20 provenance under reversing clocks (unchanged, completed-only). The F_LAST membership-absent view has never been exercised by the downstream readers (`frankie_box_experiment_journal.read_columns` already lists `unsupported_root_group_membership`; `native.read_columns` is bound to the ROOT axis length). No runtime figure in this section is measured.

## 2026-10-07 late: one 99-entry registry, the 99 through the core, the native-only 18, symbolic discovery (source-built, runtime unverified, review required)

Greg resumed workflow_reports ("respawn and finish"). Source only: nothing ran, nothing installed, no account call.
Skills: `api-and-interface-design` (first), `context-engineering`, `experiment-orchestrator`. Review findings of
`REVIEW_20261007_EVENING_SLICES_AND_READINESS.md` addressed here: B4 (adviser), the registry table, entry-granular
arrival, N1, N7.

### One registry and one shared field
- `frankie_box_all99_coverage.py` is the single source of the 99 entries (`REGISTRY`, `GROUP_ROLES`, `entries()`,
  `registry()`), bound to the crosswalk (`CROSSWALK_PATH`, `CROSSWALK_SHA256` ece9c624..., `CROSSWALK_BYTES` 112545,
  `REGISTRY_SHA256` 239a1480...). The classroom (`ALL99_REGISTRY`, the loop of `all99_coverage`) and the adviser
  (`ROLES`, `registry_layers`) import their entry list from it; their routes and entry names are unchanged.
- The shared per-piece field FRANKIE_ALL99_COVERAGE_V1: `field(piece, day, rows)` builds it (exactly 99 entries in
  crosswalk order, each `{entry, group, role, disposition, reason, consumer, piece_disposition, class}`); unknown
  names, duplicates, missing entries ('unrouted') and group contradictions are `integrity` findings, never relabelled.
  `derive_field` builds a piece's field from another's (the teacher from the core's); `validate` re-checks a field
  read back from a receipt.
- Settled in the registry: ONE vocabulary (`VOCABULARY`, 16 words incl. `integrity_failure` and `unknown`) with
  `LEGACY_WORDS` mapping every piece's old word; `FIXED_WORDS` settles the sealed nine (`withheld_by_role`), the two
  shadows (`disabled`), Memory A (`retired`), A-clean (`not_applicable`, not Memory A) and
  `selected_same_arm_profile` (`control`, a delivered binding control); causal_clocks role `clock`; the current
  brain entries are `not_read_by_this_piece` unless a piece reads their own content; `CLASS_OF` / `WORD_CLASS` kept
  for the day reports.
- Settled carriers: `MARKET_CARRIERS` (entry -> carrier, thinner carrier), `CARRIER_ELEMENTS`, `NOT_MARKET_CARRIED`
  (the teacher's Dipole state; the lock clock) and `NATIVE_SERIES` (the 18 native-only entries' own member fields and
  lifecycle sections, transcribed from the retained crosswalk's producer carriers; at runtime the ROOT projection
  plan's own producers' crosswalk is used when present).

### The core carries the 99
- `SharedMarketTimeline.report['layer_entries']`: per carrier (the six layers, `input`, `clock`, `availability`,
  `opening`, `completed`, `external`) its picture element, the entries it yields, the entries it carries thinner,
  presence and reason. Every picture carries the same map as `coverage.carried_entries`.
- Every update names its entries (`update['entries']`, `ALL99.update_entries`): a ROOT row its layer's entries; a
  native member row each native entry whose own field it holds; a native lifecycle row the entries of its
  `emitting_section`. At the update's own GROUP_CLOSE emission; FINALIZE stays post-stream; nothing backfilled.
- `report['all99_coverage']` is the day's FRANKIE_ALL99_COVERAGE_V1 (made at open, replaced at exhaustion with the
  per-entry update counts): `yielded` / `yielded_no_rows` / `thin` / `absent` / `completed_only` with the ROOT's own
  derive.json record of each native layer in the reason.
- `opening_state` (report and every picture): `canonical_predecessor_bootstrap_objects` as an identity element (the
  opening book descriptor from derive.json, else the source binding; tail members) with
  `initial_last_observed_state`; pictures carry `coverage.last_observed_state` / `active_instrument_state` saying
  whether rows exist yet. Never re-derived, never an empty book filled in.
- `legacy_native_signed_flow` and `legacy_per_second_roll20` are `completed_only` (blocked on contributing-cursor
  provenance, not on the reader).
- N1: `input_witness` must name the pinned file (path resolving to the pin or `os.path.samefile`, current size; device
  and inode when given); otherwise the reader hashes the file itself. The teacher and the classroom code pass
  path/dev/ino.

### The native-only 18 to Frankie and both teachers
- Core: yielded per update with entry ids (above). Export: `selected_files` adds the projection plan
  (`work/derived/.projection-v2/plan.json`, checked to name the selected ledgers); the export links each entry's
  projected layer file with its derive.json pin, lists any not produced with the ROOT's reason, adds
  `work/native-layer-records.json`, and writes `native_entries` in the MANIFEST. Search: the exact ledgers are placed as
  before (exact emission cursor on the F_LAST axis); `plane_summary` gives each of the 18 its own row (series/cells of
  its own carriers, or `native_carrier_without_rows` with the native dispositions of its sections). BOSS teacher: the
  18 are in `teacher.market_picture` with their entry ids (exposed within its role; the pinned equations unchanged).
- Searched for production: `frankie_box_bedrock.py` (`project`, `crosswalk_records`), `frankie_box_projection.py`
  (`project`, plan.json), `frankie_box_boss_session._derive_bedrock`, the pin's bedrock groups and the retained
  crosswalk. None of the 18 is reported unproduced by this code; absence is the ROOT's own recorded reason.

### Entry-granular arrival in the scientific lists
- `day_coverage` counts a test row for an entry only when it read a series of THAT entry (`EXPLICIT_SERIES`, the plane
  table's own series names, the native carriers), never merely the same source; a clock arrives only when the
  operation read at least one test row (N7); policy entries are `not_read_by_this_piece`, Memory A `retired`.
  `search_coverage` is the search's own list (MANIFEST `all99_coverage`).

### Symbolic discovery (stage 7)
- `frankie_box_experiment_search.discovery`: per cell and target, features = every (x, lag k > 0) a coupling row of
  that cell found beyond chance with x leading; rows y[t], x[t-k]; odcore.leakage on every lag construction; the
  existing `odcore.symbolic._regressor` (unchanged configuration, discover() defaults 40/12), one fit per seed
  (`FRANKIE_DISCOVERY_SEEDS`, default 0), every Pareto front kept; nothing averaged. Writes `discovery/INDEX.json`
  (FRANKIE_SEARCH_DISCOVERY_INDEX_V1, with its workflow report), `discovery/problems/<id>.json` and
  `nominations.json`. An absent PySR engine lists `equation_not_run` per problem (installing it is a box change on
  Greg's go). Confirmation days: `not_run_confirmation_day`.

### Inspection
- `frankie_box_workflow_inspection.py`: `candidates` binds `('survivors',)` and renders the survivor receipt
  (`candidates_projection`, coverage-file pins only); every piece's all-99 list renders as its own section
  (`all99_section`: shared counts, integrity, every row); classroom failures show reason/listed/saved_phases and
  `phase-progress.json` last_event; `keep-running.json` is projected in preflight; FIELDS/USED/PRODUCED gain the
  all-99, survivor, native and school-list fields.

### Later requests folded into the same pass
- Frankie's 13 points tied to the 99: the day file declares per point (table metadata or a per-row column) the entries
  it feeds (`EXTERNAL_ENTRY_KEYS`), `registry_mapping` exact/closest with its reason, `event_time_ns` /
  `event_time_basis` (default_1400 for a value without an intrinsic time) / `as_of` / note (`external_point_mapping`;
  an undeclared point and a name outside the 99 are listed findings, never guessed). The core places each point at
  max(event time, publication) once the receive frontier reaches it (never earlier, never backfilled), names its
  entries on the update and records `placement` (publication, event time, basis, mapping); the core field marks a
  declared entry arrived only when the point's value was presented. Export: MANIFEST `external.registry_entries`;
  search: the external source's `registry_entries` / `registry_mapping` and a per-entry `external` slot in the planes
  (series of that point and its aliases); the adviser marks a fed entry arrived only when the point is in its picture;
  the BOSS teacher sees the points in `teacher.market_picture` (exposed, within its role). The search still places the
  points through the day file's own `AsOfReader` / `search_series` (owned by the day-file piece): the event-time rule
  must be applied there too for the search to match the core (request).
- `TEACHER_FORMS` is one table in the registry (fills, modifies, queue concentration, queue age/survival, depletion,
  resilience, chain trajectory, chain extension, missingness, the Dipole state); the teacher list and the search's
  entry patterns read it.
- `clock_model_evaluation`: `model_clock_row` (frankie_box_model_clock.coverage_row); the adviser route `model_clock`;
  `day_coverage(model_clock=...)`; the native member field stays the declared null.
- `clock_prospective_discovery_confirmation` at the survivor update: `confirmation_clock_row(receipt)` and
  `day_coverage(confirmation_clock=...)` (stamped_at_boundary / stamped_not_committed / discovery_only).
- `USE_WORDS` (computed / context / absent) validated on rows that carry `use`; `exposed` is a shared word.

### Open
- Runtime: nothing ran. PySR is not installed. The step form and autoregressive features are listed, not run.
- Cross-owner: day_reports `reach_of` should read `piece_disposition` for its REACH_REFINE words; classroom A-clean
  word (`retired`) is corrected by FIXED_WORDS in the shared field (the classroom's own list keeps it);
  `frankie_box_experiment_classroom_v2.py` should pass `path` in its `input_witness`; experiment.py
  `all99_admission` should build its field with `ALL99.field` (step8).
- A fresh independent review is required before integration.
