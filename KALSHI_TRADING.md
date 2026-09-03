# KALSHI TRADING — file index

## S121 — the raw MBO reaches the principal as it arrives in RT (D81)

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Greg, 2026-09-02: *"he gets every record
of every field for Sunday, the date and time we are running"* and *"this has to exactly mimic
how it's going to come in rt."* Mission section 5 said "the runner calculates; you interpret"
against section 3 and 55 registry layers routed `CAUSAL_GROUP_STREAM`, and every session built
to section 5; `validate_causal_group_delivery_receipt` had no caller. Now it has one.

- **`research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py`** — `CausalGroupStream`:
  forward-only delivery of the exact member ledger, one F_LAST-closed group per call in
  `ts_recv_ns` order, byte-identical to the ledger line; peek / seek / rewind / indexing raise;
  a ledger whose receive clock moves backwards, an unclosed group, or a row declaring another
  availability clock is refused. Lifecycle and legacy rows ride with a group only when their
  OWN clock is at or before its cutoff under a DECLARED rule (`lifecycle_availability`:
  close-occasion rows withheld until after exhaustion, `SECOND_COMPLETE` at `(second+1)s`,
  candidates at `available_second`, otherwise the latest named `*_recv_ns`; legacy rows by
  their float-seconds `ts_recv`); rows with no clock are withheld and COUNTED, never dropped,
  and `read == attached + withheld + pending` is proved per ledger. Every delivery is a
  `GROUP_DELIVERY_SCHEMA` receipt chained to the previous and validated through the registry.
  `stream_receipt()` = groups, bytes, sha256 over delivered bytes, the ordered cutoffs.
  `python3 -m ... --member-ledger ... --run-id ... --arm ...` prints it over a whole ledger.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_causal_stream.py`** — 27 tests:
  byte identity against the sink's own line format, refusals produced, look-ahead withheld and
  counted, receipts validated and chained, and the traversal's REAL ledgers streamed end to end
  with the member sha256 equal to the sink receipt's.
- **`research/kalshi/frankie_raw_mbo_benchmark/fetch_frankie_ledgers.py`** — a session has no
  AWS credential, so delivery is workflow-presigns -> manifest artifact -> session downloads.
  `build-manifest` (workflow side) assembles `FRANKIE_LEDGER_DELIVERY_MANIFEST_V1` from S3's
  listing, the presigned URLs and the box's `PLAIN_SIZES` / `PLAIN_SHA256SUMS`, refusing any
  hole; `fetch` (session side) downloads, checks the gzip length against S3's ContentLength,
  gunzips, checks plain bytes and sha256 against the box's receipts, and writes
  `FRANKIE_LEDGER_DELIVERY_RECEIPT_V1` with per-ledger `VERIFIED | LENGTH_MISMATCH |
  SHA_MISMATCH | MISSING` - any mismatch is a refusal. URLs never reach a log or a receipt.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_fetch_frankie_ledgers.py`** — 14
  tests, stub downloader, every refusal produced.
- **`.github/workflows/frankie_ledger_delivery_20260902.yml`** — presigns the PINNED Sunday run
  33630348943's five objects for 604800 s and publishes `frankie-ledger-delivery-<run>-<attempt>`
  (7 days); a push on this branch filtered to its own path registers it. FAILS on a run lacking
  either plain receipt. D57-verified by parse, `bash -n` on every run block, zero heredocs.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_frankie_ledger_delivery_workflow.py`**
  — the D57 checks and the step contracts, mirrored from `test_a_arm_launch_workflows.py`.
- **`research/kalshi/frankie_raw_mbo_benchmark/emit_frankie_spawn.py`** — `--delivery-receipt`
  REQUIRED; refuses unless every ledger in `EXACT_LEDGERS` is VERIFIED, the receipt's own hash
  verifies, and each delivered sha256 equals the run's sink receipt where the run carries one.
  The evidence section names the three local ledger paths and `CausalGroupStream` as THE
  evidence; he computes the sixteen sections himself in causal order; `calculation_result.json`
  is NOT his evidence and is compared AFTER he files. Return shape: `evidence_read` READ for
  every ledger, `delivery_receipt_sha256` filled, `stream_receipt_sha256` his to produce.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_staging.py`** — `load_principal_artifact`
  refuses NOT_READ on any ledger when the artifact cites `delivery_receipt_sha256`; without the
  citation the old rule stands.
- **`research/kalshi/agents/frankie_native_raw_mbo_oct45_realtime_mission_20260828.md`** —
  section 2 names the evidence; section 5 opens with "you compute the sixteen"; the table and
  the six things that follow are unchanged. `KNOWLEDGE_MANIFEST_20260828.json` re-pinned.

## S120 — section 4.0, the per-second substrate everything ran on and nothing declared

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. **1388 tests after the 4.0, 4.0b and census merges, from 1254.**

- **`research/kalshi/frankie_raw_mbo_benchmark/native_mbo_field_census.py`** — F-10 / mission
  9a. The raw-MBO drop question was unanswerable because nothing measured the retained
  fields: the member ledger stays on the box and the result carried a row COUNT. `MboFieldCensus`
  walks every member row the runner's sink receives (`note_member_row`) and reports per field
  path: observations, rows-with-field, nulls, distinct values (capped at 64), types, numeric
  range, DEGENERATE (one value throughout) and ALWAYS_NULL. List positions collapse to `[]`
  because a ladder position is not a field. Emitted as `layers.exact_member_ledger.field_census`
  and rendered into the spawn prompt. A MEASUREMENT, never a recommendation (D60/D76); its
  `basis` says so.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_mbo_field_census.py`** — the
  census's own tests: absent vs null counted separately, list collapse, cap, bool excluded from
  range, read-only on its input.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_flow_substrate.py`** — section 4.0,
  Frankie's item (a). The per-second roll20 substrate the candidate detector and 4.12 run on
  was `traversal.legacy_per_second_roll20` - a counters block, not a section: no declaration,
  no stratum, no denominator, no gate - which is why the 51.6% NO_DIRECTION share had to be
  reconstructed from counters. One exact row per COMPLETED second (own-second buy/sell volume
  and trade dispositions, the quote the last classifiable trade was judged against, the roll20
  value and window signed flow downstream consumed); exactly one of six classes per second, so
  a second that cannot be classified is a CLASS, never a gap; INCOMPLETE seconds at a boundary
  are retained with partial tallies and kept outside every denominator. The midpoint rule is
  not restated: dispositions are read as counter deltas off a `SecondBinner` of the same class
  the traversal feeds, and the section RECONCILES its volumes against the traversal's binner on
  every second and refuses on disagreement. Averaged rows are a census only - per-class shares
  with the completed-second denominator. Fed from `native_replay_driver` at group close (rows,
  AFTER the mark, so a new segment's first group is not released by the old segment's close)
  and in `_advance_candidates` (one completed second at a time, phase from the second's OWN
  instant - D75's shape refused). Registered FIRST in the runner's section map;
  `sections_fed["4.0_flow_seconds_completed"]`. The contract gains `### 4.0` before 4.1 and the
  knowledge manifest is re-pinned to the edited contract.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_flow_substrate.py`** — the
  calculator's own tests. The driver-level proof that the section is FED lives in
  `test_native_replay_driver.py` (`FlowSubstrateIsFedByTheTraversalTest`,
  `DarkSectionRegressionTest.test_the_per_second_substrate_reaches_section_4_0`), because a
  calculator's tests passing while the driver never calls it is S119's recorded mistake.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_render_frankie_report.py`** — the
  render's tests; named here for the index, which had it tracked and unnamed.
## S120 — section 4.0b: the selection function that creates the candidate population is governed

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`.

- **`research/kalshi/frankie_raw_mbo_benchmark/native_detector_coverage.py`** — section 4.0b,
  detector coverage and rejection accounting: Frankie's proposal (b) from run 33605852433,
  where **91 were promoted of 4,462 considered** and the 4,371 rejected lived in
  `traversal.candidate_detection`, a counter block no section owned - which is what made
  4.11's `detection_share = 1.0` unfalsifiable. It reads the detector's own integer counters
  after every second the traversal feeds it and proves two identities at every segment close:
  every judged second is in exactly one NAMED outcome (a residual REFUSES, never "other"), and
  the section's totals equal the detector's counters key for key. Every detector constant
  rides on every row; a rate is a ratio of exact counts with both integers beside it;
  `summary()` gives 4.10-4.16 their true denominator. Fed from
  `native_replay_driver._account_detector_second`, closed by `_retain_detector_close` after
  `finish()`, reported as `sections_fed["4.0b_detector_seconds_accounted"]`.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_candidate.py`** — accounting counters
  only, no selection change: emissions are identical on 80 of 80 replays against the pristine
  module. `seconds_judged`, `seconds_without_finite_flow`, and
  `rejected_in_refractory_at_release` - a REAL uncounted exit, a peak judged at exactly
  `window_open + refractory` that was outside the window's group and inside the winner's
  shadow. The pre-existing counters summed to 289 against 290 judged seconds on the fixture
  and fell short on 35 of 80 random streams. `counters()` and `parameters()` are the surfaces
  4.0b reads; `summary()` keeps every key it had.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_stratum.py`** — `CountPartition`, the
  `COUNT_PARTITION` measure kind: exact counts over a declared, closed set of outcomes, every
  outcome emitted even at zero, an undeclared outcome refused, no arithmetic mean formed -
  section 3's "counts are not silently called arithmetic means" as structure.
- **`research/kalshi/agents/frankie_native_raw_mbo_calculation_contract_20260828.md`** — gains
  `### 4.0b` before 4.1, average decision NO. The contract is registered VAULT and hash-bound
  into every run identity; `KNOWLEDGE_MANIFEST_20260828.json` was regenerated with
  `refresh_native_frankie_knowledge.py` (it was already invalid on disk from the mission edit
  at 34a0c16), and `emit_frankie_spawn` will refuse, by design, for any run bound to the
  previous contract hash until a run binds the new one. Greg's go is the versioned event.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_detector_coverage.py`** — new;
  every refusal is PRODUCED, on a real detector. `test_native_replay_driver.DetectorCoverageFedTest`
  proves the traversal feeds the section with real promotions AND rejections and reconciles its
  summary against `traversal.candidate_detection`; `DarkSectionRegressionTest` enumerates
  `4.0b`. Also carried here for the index: `test_render_frankie_report.py`.

## S120 — the principal's report is a render of his findings

- **`research/kalshi/frankie_raw_mbo_benchmark/render_frankie_report.py`** — the report is
  generated FROM `frankie_principal_findings.json` and can no longer be authored apart from
  it. Run 33605852433 produced **44 findings** - chain depths, family crosswalks, exhaustion
  runways, prebirth recognition, dipole decoupling - beside a separately hand-written
  assessment, so what reached Greg was a verdict on whether each section earned its place and
  none of the findings. The findings artifact is the STORE and this is the RENDER, as
  `DECISIONS.md` and `RUN_SOP.md` already are. It writes `frankie_findings_report.md` and
  NEVER touches `frankie_calculation_assessment.md`, which is a hand-authored record.
  Wired into `native_staging.load_principal_artifact` - the one gate every artifact must
  pass - so it generates automatically and cannot be forgotten; a render failure is reported
  and swallowed, because the findings are the deliverable and the report is how they are read.


## S120 — the token reducer applied, and 4.16's event-driven half given its first caller

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. **1223 tests, from 1162 at S119.**

- **`research/kalshi/frankie_raw_mbo_benchmark/native_key_alias.py`** — D78. Key-name
  aliasing for the averaged companion rows, plus `measure_key_names`, which turns the S119
  prose measurement into a function that reports the saving in ACTUAL serialized bytes
  rather than from name lengths. Key names are 49.5% of that section on run 33605852433 and
  aliasing removes about a third of it; it saves nothing on the ledgers, where `book_full`
  swamps every name, which is the scope D67 was right about and this is not. Applied at
  SERIALIZATION only, so the gates run on unaliased rows and no verdict can move under it.
  `read_averaged_rows` is the only supported way to read the rows: a direct lookup on an
  aliased layer succeeds, returns the right count, and reports every row under `None`.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py`** — D80. Now carries
  `_observe_change_points`, the FIRST caller `native_response.observe_change_point` has ever
  had. The trigger is the observable state's fingerprint moving, never the clock: the
  contract requires emission at change points AND at fixed horizons, so a per-second call
  would collapse the two and retain (open tracks x seconds) for readings the horizons
  already carry. Off by default, because retained volume becoming (open tracks x changes) is
  a size decision.
- **`research/kalshi/frankie_raw_mbo_benchmark/report_ledger_size.py`** — gains the READ
  SURFACE section. The disk tables could not see aliasing at all, so a run with it on would
  have reported a saving of exactly zero. It also states why the two reducers cannot
  confound: one changes a layer in the result JSON, the other changes rows on disk.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_key_alias.py`** — new.
  Round-trip, key-only renaming, no ambiguous codes, and one recorded LIMIT: a foreign alias
  code is indistinguishable from a name that was never aliased, so the legend travelling in
  the same layer is the structural answer rather than a guard that could never fire.


## S119 — the sixteen-defect register closed, and the gate that would have caught it

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. **1162 tests, from 552 at S115.**

- **`research/kalshi/frankie_raw_mbo_benchmark/native_cross_section_agreement.py`** — D72, the
  NINTH section-6 gate and the only HORIZONTAL one. The eight existing gates each check a
  section against ITSELF, and a one-sided book satisfies every one of them: 4.9 returned
  exactly +/-1.0 on **152 of 154** readings while 4.12 computed the identical formula and
  returned **[0.0116, 0.1109] on 3,454**, and all eight passed. The test is DISTRIBUTIONAL,
  because 4.9's range CONTAINS 4.12's. A review found the first version evadable by the exact
  defect class it was built for - mean and extreme share both cancel under sign symmetry - so
  it now leads on the population-weighted **second moment**, which does not cancel and does
  not move under re-stratification: **0.9871 against 0.0031** on the real artifact.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_book_regime.py`** — section 4.2, which
  did not exist. Its absence left `book_full` - **10.13 GB, 93.47% of the exact member
  ledger** - with no consumer anywhere in the artifact. Reads the book already on the row: no
  new capture, no new pass. A one-sided book has an UNDEFINED spread and an empty book has no
  imbalance, both excluded and counted, while zero DEPTH is a real measurement and is kept.
  Its `relative_imbalance` is the THIRD computation of the estimand the gate above watches.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py`** — the run entry point.
  Now selects horizon version `a-arm-h2` (1 ms / 10 ms / 100 ms beneath the frozen
  1 s / 10 s / 60 s) and the four feedable response channels.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_candidate.py`** /
  **`native_candidate_adapter.py`** — the causal candidate detector and the adapter that
  drives 4.10, 4.11 and 4.12 off it. The adapter had NO test file, which is why three defects
  survived a full run; `tests/test_native_candidate_adapter.py` is new.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py`** — the per-second roll20 /
  dipole substrate the registry requires as `CAUSAL_STREAM_REQUIRED`.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_row_sink.py`** — D60 streamed retention:
  the exact ledgers are held ON DISK rather than in RAM, and nothing is dropped.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_queue_adapter.py`** /
  **`native_replenishment_adapter.py`** — the group-to-section adapters for 4.6 and 4.7.
- **`research/kalshi/frankie_raw_mbo_benchmark/report_ledger_size.py`** — the sink's own
  byte accounting, which is what `verify_ledger_size_witness.py` exists to second.
- **`research/kalshi/frankie_raw_mbo_benchmark/tests/`** — 1162 tests. New this session:
  `test_native_candidate_adapter.py`, `test_native_book_regime.py`,
  `test_native_cross_section_agreement.py`. Also carried here for the index:
  `test_a_arm_launch_workflows.py`, `test_box_volume_rescue_workflow.py`,
  `test_emit_frankie_spawn.py`, `test_native_a_arm_launch.py`, `test_native_candidate.py`,
  `test_native_queue_adapter.py`, `test_native_replenishment_adapter.py`,
  `test_native_roll20.py`, `test_native_row_sink.py`,
  `test_native_row_sink_differential.py`, `test_report_ledger_size.py`,
  `test_verify_ledger_size_witness.py`.

## S119 — Frankie ran, and the token surface was measured

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`.

- **`research/kalshi/frankie_raw_mbo_benchmark/emit_frankie_spawn.py`** — the A-arm `spawn.py`,
  and the piece whose absence is why Frankie had never been run: staging existed, validation
  existed, nothing rendered the prompt between them. Every slot is a LOOKUP from a committed
  artifact and an unresolved slot HALTS the emission naming the failed lookup. **Refuses if the
  mission on disk no longer hashes to what the run bound** - section 10's first bullet made
  mechanical, and it fired on its own author within the hour. Also refuses a verdict that is not
  ACCEPTED, a run that staged zero cutoffs, and a moved contract. States the cutoff SPAN and the
  session phases covered, because on an 88-minute window "October 1" reads as a day. Tests: 12.
- **`research/kalshi/frankie_raw_mbo_benchmark/principal_runs/33605852433/`** — the first
  principal output this programme has produced. 44 findings over the complete Sunday session,
  gate-accepted against `evidence_result_hash cb685e0e...`, artifact sha256 `147c6485...`, with
  the emitted prompt beside it as the receipt for what he was run against.
- **`research/kalshi/FRANKIE_MEASURED_TOKEN_REDUCTION_20260902.md`** — D71. Key names are
  **49.5%** of the averaged companions at all depths, 56 names repeated 788,868 times, and
  aliasing saves **33.8%**. Scopes D67 rather than overturning it: aliasing saves nothing on the
  ledgers, where `book_full` dominates, and a third of the surface a principal actually reads.
  The per-day extrapolation is deliberately left as an upper bound - strata saturate.

## S119 — the independent size witness and the volume rescue

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`.

- **`research/kalshi/frankie_raw_mbo_benchmark/verify_ledger_size_witness.py`** — D69. The
  SECOND PARTY on a size figure. `ledger_retention[*].bytes` is the sink counting its own
  writes; S3 recorded a `ContentLength` for the same objects at PUT time with no stake in the
  answer. Compares them per ledger, checks the DENOMINATOR from three places that must agree,
  and compares a downloaded ledger's sha256 to the receipt so content is witnessed and not just
  length. Three outcomes, three exit codes - **WITNESS_UNAVAILABLE is red on purpose**, because
  a packet that never landed or landed gzipped produces a legitimate mismatch that must never
  read as the sink being wrong. Emits a bytes-per-record figure ONLY with both quantities
  independently sourced, and REFUSES otherwise. Tests: 16, including the case that drove out the
  first violation - two of three record counts agreeing while the third was absent.
- **`.github/workflows/frankie_run_size_report_20260902.yml`** (changed) — carries the witness
  ahead of the self-reported table. Its default run is now PINNED rather than "newest": the
  first live run reported CONFIRMED against a push-CI canary because newest is not the same as
  the run in question, and nothing on the page named which run had been read. `newest` must now
  be asked for by name. The witness markdown is echoed to the LOG, because a step summary cannot
  be read back through the API.
- **`.github/workflows/frankie_box_volume_rescue_20260902.yml`** — recovers the box by moving its
  DISK rather than by talking to it. After the S118 reboot the SSM agent reports ConnectionLost,
  which removes RunCommand and Session Manager both. Stops the instance, detaches the root
  volume, mounts it on a throwaway t3.micro, reports `df` and `du` BEFORE clearing anything -
  the first independent test of the full-disk diagnosis - clears `/opt/frankie-a-arm-run`, then
  reattaches and proves the box executes a command. One script under one EXIT trap, because
  between detach and reattach the box has no root disk. `action` defaults to a read-only report
  and every acting step additionally requires a dispatch, so a push cannot reach one.

## S116 — the RT book, the full-capture adapter, and the prior-work recovery

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`.

- **`research/kalshi/FRANKIE_A_ARM_PRIOR_WORK_RECOVERY_20260829.md`** — **READ BEFORE ANY BUILD ON
  4.10/4.11/4.12/4.16.** What the prior exhaustion program (2026-08-16 to 2026-08-25, ~200 files,
  in places frozen and hash-bound) already defines: t0 as a dipole flow spike, the `TIMING_LADDER`,
  the persistence-run call with its two timestamps, SAME/FLIP as polarity versus the latest
  predecessor, the side-swap mirror, and `t` as a PRICE TICK. Plus the six collisions between that
  frozen learning and the new modules, and the reason the sections were never fed: the per-second
  roll20/dipole substrate the registry requires does not exist in the benchmark.
- **`research/kalshi/FRANKIE_A_ARM_ESTIMAND_PROPOSALS_20260829.md`** — **WITHDRAWN.** Retained as
  the record of what was proposed and why it was wrong, per the rule that a superseded value is a
  deliberate record.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_rt_book.py`** — the REAL-TIME view (Greg:
  *"we should see it like it would be seen in rt"*). A FIFO book advanced one action at a time, so
  section 4.6 reads `orders_ahead` as a live feed saw it rather than as the closed group left it -
  the shared book mutates on every record while the frame arrives only at F_LAST, so reading there
  reports a level AFTER the add it describes. Mirrors `InstrumentBook` on every mutation and
  refuses only a negative size. `view_with_basis` carries the basis on the value. Tests: 38, plus
  `tests/test_native_rt_book_differential.py` driving both books in lockstep over 12,024 records
  with zero divergence and mutation-testing its own comparator.
- **`research/kalshi/frankie_raw_mbo_benchmark/native_full_capture_adapter.py`** — D61. Keeps
  everything the HASH-LOCKED V4 adapter computes and discards: the per-record `ApplyEffect`, the
  reconstructed FIFO queue, the book below level ten, per-side event counts, touch quantity for
  T/F/M, and every anomaly magnitude. **Never edit the locked adapter** - doing so broke six
  supply-chain locks in one commit. Tests: 12, each a differential against the locked adapter.

## S115 A-ARM — the Frankie raw-MBO benchmark: the group adapters, the CME calendar, the box probes

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Distinct from the S115 platform-audit section
below, which is a different line of work on a different branch.

- **`research/kalshi/frankie_raw_mbo_benchmark/native_group_adapters.py`** — **the missing layer
  under sections 4.6-4.16.** Every ingest point in the calculation tree takes a CONSTRUCTED domain
  object (`LadderTransition`, `Sequence[Occurrence]`, `LineageNode`, `RunwayPressure`) and nothing
  built those from raw MBO; the contract specifies the CALCULATION, never the input event. Builds
  them from one **F_LAST group** (D53). Covers 4.14 recurrence, 4.9 ladder, 4.8 absorption, 4.13
  lineage — each verified against the REAL calculator, not in isolation. Declares its scope ON the
  value: `LADDER_SCOPE = GROUP_LOCAL_DELTA`, because a group cannot see liquidity it never touched
  and a caveat living only in a docstring expires. Lineage depth accumulates ACROSS groups.
  Negative size raises rather than clamping; the undefined-price sentinel is dropped, not treated
  as a level. Tests: `tests/test_native_group_adapters.py` (20).
- **`research/kalshi/frankie_raw_mbo_benchmark/native_session.py`** (extended) — now consults the
  **CME trading-day calendar** (D52). `is_trading_day` / `holiday_class` read classes from
  `plant_calendar`'s RULES rather than a date table, because the roster year is 2021 and
  `flow_calendar.CME_HOLIDAYS` starts 2025-09-01. `phase_within` **REFUSES** on a
  `partial_session` / `early_close` instead of answering from ordinary hours.
- **`research/kalshi/frankie_raw_mbo_benchmark/corrected_a_arm_execution_gate_20260828.py`**
  (changed, load-bearing) — **now FILE-BASED, not provider-attested.** It previously required
  `provider` / `requested_model` / `served_model` / `principal_invocation_id` / token `usage`,
  none of which exist in an agent-session run, so it would have REJECTED a correct Sol run. Now
  checks a committed staged request plus a committed artifact, hash-bound.
- **`.github/workflows/frankie_box_sizing_probe_20260829.yml`** — read-only. Settled D55:
  `r6i.2xlarge`, 8 cores, 61.8 GiB, 32 GiB swap (the recorded `t3.xlarge` was stale).
- **`.github/workflows/frankie_box_monitor_20260829.yml`** — **LIVE.** Installs a capped,
  self-trimming /proc sampler on the box; reports MIN_MEM_AVAILABLE and PEAK_SWAP_USED, never a
  mean. Bump its RUN MARKER for a reading. **Does not survive a resize reboot — re-fire after.**
- **`.github/workflows/frankie_box_resize_20260829.yml`** — **ARMED, NOT FIRED.** Targets
  `r6i.8xlarge`. Refuses on a non-EBS root, refuses if the box is busy, full rollback on every
  failure path. An EC2 type cannot change while running; there is no live resize.
- **REMOVED:** `ng_exhaustion_step1_receipt_count_20260823.yml` and
  `ng_exhaustion_step1_oom_continue_v2_20260827.yml` — invalid YAML, so GitHub emitted a JOBLESS
  startup-failure run on every push to every branch, ignoring their branch filters. Zero jobs, so
  no step1 data was ever exposed. Both duplicated on their home branch. The other 47 step1
  workflows were deliberately KEPT.


## S115 — the pre-paper-trade platform audit: the blind wall, the brain view, and the D47 failure

- **`research/kalshi/brain_onedoc_fix_s115.py`** — closes the ONE-DOC holes in the brain (Greg:
  *"merge the reasoning file"*, *"is there another hidden doc somewhere"*). Merges the last
  un-merged field of `knowledge/refinement_architecture_doctrine.md` (which had been merged at S103
  and left in RFN-1's read list for twelve sessions), repairs four dead `.md` citations inside
  served sections (`blind_class_C/D/E.md` + `blind_shared.md`, all deleted at S105 BY DESIGN under
  D7), and reframes the doctrine entry that deferred substance to an external file. Dry-run
  default, backup before write, refuses to shrink the brain. Paired gate:
  `brain_schema.check_cited_files` — a `.md` named in a role-served section must EXIST, hard fail,
  skipping citations that declare their own death.
- **`research/kalshi/storage_restage_repair.py`** — grafts the correct EIA-weekly family (`storage`,
  `stor_surprise`/`_sign`/`_basis`, `storage_regional`) onto a committed group state instead of
  re-staging it. Built because the g24 refine needed a correct storage lane across the block's two
  EIA prints (07-23, 07-30) while a full re-stage off the current S3 plane would have EMPTIED three
  other blocks (`storage_consensus`, `weather_forecast_cycle`, `freeze_risk` — all stale on S3).
  Dry-run default, idempotent, and every repaired day declares itself in `storage_repair_basis` (the
  S109 `session_b_share_basis` pattern). Selftest ALL PASS. g24: 12 hard -> 0 hard.
- **`creds.py` (rewritten resolution order)** — `MARKETS_<NAME>` env vars resolve FIRST, a namespace
  the container's `proxy-injected` placeholders cannot shadow. Set the two AWS names once in the
  Claude Code environment configuration and every future session restores the data plane with ZERO
  pasting; Databento + EIA follow from SSM. `status()` now reports EFFECTIVE resolution (it probes
  SSM) instead of file presence, ending the false "no keys" alarm on every fresh session.
- **`brain_view.py` (S115)** — the blind wall now covers `meta` and the group's own name forms (a
  served g24 view carried `"g24 blind (6/10, sum|err| 4,890)"` in `meta.changelog`, past a full
  redaction pass, because the string holds no date); the evaluability resolver supports `[N]` list
  indexing; and the working view gains `play_index` + two declared provenance cuts, taking it from
  ~420k to ~338k tokens with all 90 plays, 661 instances and 90 falsifiers intact.
- **`SESSION_HANDOFF_2026-08-06_S115.md`**, **`DROP_IN_S116.md`** — the session record and next box.

## S114 — the A-24 paper dissected per event; the two-sided lane MERGED; the decision order and the failure taxonomy

- **`reasoning_method.decision_order` (brain s105.4)** — the seven-step order finally served to
  specialists: classify -> inventory served/broken -> **pre-influence read then independent chain,
  before any handed-down read** -> gates/damps/guards -> falsifier + pre-mortem + anti-default ->
  **disposition {commit, abstain, override}** -> commit and hand off. Provenance D25 (S110, Greg).
  Measured cause for building it: the canonical rule files carry ZERO occurrences of D23/D25/D31/
  D32/D37/D39 or 'NO CALL', so none of this had ever reached a specialist by any channel. Carries
  its own known gap - step 6 names ABSTAIN and the machinery cannot emit it (A-2/A-40).
- **`agents/failure_judge.md` + `store/failure_judge.json` + `failure_localization.py`** — the
  interaction-centric failure taxonomy (arXiv:2607.28802, Scale AI): every failure gets an
  interaction EDGE and a FAULT SIDE naming which end owns the repair, plus the root-cause rule
  (label the EARLIEST unrecovered failure; later errors are consequences). Applied to our own
  history it inverts the headline - **context 16, model 8, owner 2, tool 2**. The role file is a
  RENDER of its store, gated by `store.py check`. Registered as A-41.

- **Brain s105.0 -> s105.4, 90 plays** — the two-sided winter/summer lane discovery lives in the
  brain, NOT in a standalone doc (Greg: "Everything lives in the store now... put it where it can
  be used"; an S114 standalone md was created and deleted the same session). Seven plays, all
  PROVISIONAL with g24 forward tests registered in `research/kalshi/store/forward_tests.json`:
  `weather.winter_heating_size_term`, `weather.renewables_masking_flip`,
  `weather.freeze_conjunction_class2`, `weather.hydro_winter_buffer`,
  `weather.summer_burn_lane_exclusion`, `weather.revision_seasonal_sign_map`,
  `weather.month_tail_gates` (the full 12-month tail map, s105.2).
- `forecasts/S114_TWO_SIDED_LANE_MERGE_PROPOSAL.json` — the D8 proposal + Greg's verbatim
  adjudication + merge_gate admit verdicts with the PARK examination recorded. Backup:
  `research/kalshi/knowledge/ng_brain_s105.0_backup_pre_s105.1.json`. Incumbents 82/82
  byte-identical.
- `research/kalshi/data_records/us48_hydro_daily_S114.csv` — 1,093 days of national hydro from the
  keyless EIA-930 six-month files (2021H1, 2024, 2025, 2026H1); definition column marks the 2021
  pre-split vintage.
- `research/kalshi/data_records/walk_census_g18_g23_S114.csv` — all 60 modern scored walk days:
  error, CDD/HDD revisions, model disagreement, computed ages, tape integrity panel. The dissection's
  census artifact.

## S111 (2026-08-05) — the reframe, the schema, three briefings

- `research/kalshi/FORECAST_ARCHITECTURE_S111.md` — **READ FIRST.** The target: the product is a price
  curve, the walk is a library build, the analog renders the forecast rather than making it. D32.
- `research/kalshi/brain_schema.py` — the brain's schema: validate / migrate / sections / report.
  Dry-run default, backup first, lossless round-trip enforced. D29.
- `research/kalshi/condition_audit.py` — can a brain condition change state inside a block. D28.
  Report-only. Carries an inline correction to its own original wording (D28.1).
- `research/kalshi/condition_rate_experiment.py` — the rate/reference-window experiment. Its
  information layer is superseded; its Q0 quantity triage (block-constant census) stands.
- `research/kalshi/GAS_SIGNAL_BRIEFING_S111.md` (+ `_SYNTHESIS_`) — horizon, the dimension budget,
  ranked signal gaps, folklore to drop.
- `research/kalshi/GAS_OPTIONS_SYNTHESIS_S111.md` (+ `_BRIEFING_`) — contract mechanics, the gas vol
  surface, and why our forecaster does not support an options business yet.
- `research/kalshi/COMPETITIVE_BRIEF_S111.md` (+ `_FULL_`) — who is on the other side, where the
  machines are weak, and whether the lag edge is crowded.
- `SESSION_HANDOFF_2026-08-05_S111.md`, `DROP_IN_S112.md`.


## NEW IN S110 (2026-08-02, current) — the plant's operating system, two group cycles, the dock

**THE SPEC BOOK AND THE PLANT (read these first; RUN_SOP is binding)**
- `research/kalshi/agents/RUN_SOP.md` — **THE SPEC BOOK, v1.6.** Every station of the group cycle with
  VERBATIM spawn templates (AUD-1 auditor, BLD-1/BLD-2 blind + bridge, RFN-1/RFN-2 refine); slots are
  lookups, never judgment. Change control: nothing runs off-SOP, a gap stops the line, changes are
  versioned diffs on Greg's go, deviations are recorded nonconformances.
- `DECISIONS.md` — the append-only binding-decision ledger (27 entries) with the instance-inline rule.
  D23-D27 are Greg's open design calls.
- `research/kalshi/plant_status.py` — the ANDON BOARD: one read-only command, PASS/WARN/FAIL per area.
- `research/kalshi/agents/QC_CHECKLIST.md` — the small-model conformance sweep, report-only, 7 items.
- `research/kalshi/decision_trace.py` — binds REASONING to the DECISION it produced (decision_id
  changes the instant a number changes; `--embed` writes the self-contained record; `verify` fails any
  unresolved id and names unbound ledgers).
- `research/kalshi/batch_record.py` — the traveler on the pallet: one record per group, appended at
  every station with session + SOP version + brain version.
- `PLANT_MAP.md` (what runs where), `KEYS.md` (inventory, names only), `.gitattributes` (the CRLF trap
  that false-flagged the whole gold vault as tampered).

**THE REASONING LEDGERS (action beside reasoning; corpus state per D24)**
- `research/kalshi/G22_REFINE_LEDGER_S110.md`, `G23_BLIND_LEDGER_S110.md`,
  `G23_REFINE_LEDGER_S110.md` — every specialist's decision with the reasoning that produced it, each
  bound by a DECISION CLAIMS table. `G22_REASONING_LEDGER_S109.md` is legacy-declared (pre-binding).

**THE MERGES**
- `research/kalshi/S110_MERGE_PROPOSAL.json` (s104.0) and `S110_MERGE_PROPOSAL_G23.json` (s105.0, and
  the first RETIREMENT: the burn gate, with the dissent recorded in full).
- `research/kalshi/adjudicate_g20_merge.py` — now carries the declared RETIREMENT class (may mutate
  `status` only, must add its refuting evidence as a new key, before/after printed).
- `research/kalshi/S110_MERGE_ADDENDUM_G22.md` — the G22 refine's twelve proposal items.

**THE DOCK (paper trading)**
- `research/kalshi/kalshi_auth.py` — signed REST client (RSA-PSS SHA256); prod + demo both verified.
- `research/kalshi/kalshi_paper_ledger.py` — append-only paper ledger, four risk caps, 11/11 selftest.
- `research/kalshi/ng_paper_loop.py` — the daily loop skeleton (public-API quotes, no keys needed).
- `research/kalshi/KALSHI_DOCK_S110.md` — the full endpoint/auth/FIX reference and the routing decision.
- `research/kalshi/tropical_feed.py` — the NHC tropical feed (the named summer gap), live-smoked.

**REPAIRS AND MEASUREMENTS**
- `research/kalshi/state_repair_s110.py` (audit f1/f3/f4/f5), `state_repair_s110b.py` (the CDD-ladder
  artifact graft, identity-proven), `promotion_review.py`, `WINTER_RESIDUAL_S110.md` (the residual
  tested in COLD at last: inert as a day timer, alive as a slope instrument).
- `TURNAROUND_MEMO_S110.md` — the platform audit and the paper-trading go-plan.

## NEW IN S109 (2026-08-01, current) — G22 blind, holes #9/#10/#11, the AUDITOR role, brain s103.7

**THE SIXTH AGENT ROLE (audit and forecast are now separate jobs)**
- `research/kalshi/agents/state_auditor.md` — CANONICAL, static, drop into every group unchanged. Reads
  the WHOLE block before the blind spawns and hunts inputs that would mislead a specialist; emits NO
  forecasts. Resolves hole #11's tension: cross-day reading is how eleven holes were found, but a
  forecaster reading across days acquires information past its own decision point. The auditor
  cross-compares freely (nothing to contaminate); the specialists run on causal slices. Carries the five
  known KINDS of silently wrong input, the declared-vs-silent split, the findings schema, and a FIX-PHASE
  contract. Trialled blind on G21: found the off-instrument defect S108 called the hardest of eight,
  WITHOUT the scored-leg reconciliation S108 used.

**CAUSALITY (hole #11 — the state let every specialist read past its own decision point)**
- `research/kalshi/build_causal_slices.py` — cuts ONE SLICE PER DAY: every block <= day X, later blocks
  dropped. A day's tape is served under the NEXT day's key, so the whole block in one file let a
  specialist read its own outcome. All three first-run G22 specialists reached forward and all three
  declared it. Self-audits; `forward_stamps()` also reports capture stamps past the decision point.
- `research/kalshi/merge_perday.py` — joins per-day posteriors into the per-specialist `days[]` shape the
  coordinator reads, GUARDED on owner_map: a mis-owned or missing day fails at the join.

**DATA-INTEGRITY GUARDS (the enemy has now worn FIVE faces: empty, wrong-value, off-instrument, wrong-ENCODING, frozen-but-LIVE)**
- `research/kalshi/state_health.py` — two new RECONCILIATION guards, not presence checks:
  the b_share identity (`session_b_share == session_b_share_two_sided * (1 - unsided_volume_frac)`) HARD
  at >0.002 (hole #9), and `squeeze_watch._live` vs `flow_calendar` (hole #10). Both negative-tested
  against the real defect and across all 17 groups for false positives.
- `research/kalshi/bshare_restage_repair.py` — HOLE #9. Recovers `session_b_share` by algebraic identity
  without a data plane; idempotent, dry-run by default, declares each repair via `session_b_share_basis`.
- `research/kalshi/squeeze_watch_live_repair.py` — HOLE #10. Re-derives the `_live` calendar limbs from
  `flow_calendar` and the dead-sponsor arm from the block's own expiry calendar. Nulls
  `calendar_limb_satisfied_live` rather than emitting a confident false — a derived boolean whose input
  is masked must not be served as `false`.
- `research/kalshi/build_anchor_block.py` — the anchor was NEVER DELIVERED to the agents (only g15 ever
  had an anchor file). VERIFIES rather than asserts: each anchor must equal the PRIOR group's actual
  last-day close (chain holds exactly G17->G23) and `anchor_lasthr_dir` is re-derived from the price
  path. Carries `direction_caveat` / `close_in_range` / `net_ticks` — both G22 and G23 anchors sit at the
  price RESOLUTION FLOOR.

**THE WEATHER / DEMAND STACK (rebuilt on Greg's desk knowledge)**
- `research/kalshi/gas_call_residual.py` — `demand - solar - wind - nuclear` (coal deliberately NOT
  subtracted: that reproduces `gas_mwh` by construction). Two alignments, mechanism and decision-time.
  Result: **UNTESTED IN ITS CLAIMED REGIME** — every block carrying `grid_stack` is WARM (mean gw_hdd
  0.12-0.72) and Greg scopes the residual to cold/turning-cold. Prints its own power warning.
- `research/kalshi/forecast_harness.py` — CDD FORWARD LADDER served (`forecast_gw_cdd`, `d_gw_cdd`,
  `fwd7_gw_cdd_span`), `gw_cdd_d0` + `d_gw_cdd` on `sunday_reopen`, a `seam_delta_warning` (run deltas
  baseline run-over-run, so across a seam difference the LEVELS) and a `ladder_basis_note` (an
  unreachable absolute HDD bar is UNEVALUABLE in summer, not satisfied and not refuted).

**THE RECORD (Greg, S109: "if you only have actions without context, it's tough to learn and to replicate")**
- `research/kalshi/G22_REASONING_LEDGER_S109.md` — WHY each specialist decided what it did, attributed:
  the right calls with their reasoning, the catches, and the after-the-fact corrections — including
  Greg's four corrections and the places I was wrong.
- `research/kalshi/S109_MERGE_PROPOSAL_G22.md` — P0 through P0.8, each with a falsifier. P0 weather as
  hill+spike; P0.5 seasonal station weights (OHIO HAS NO STATION); P0.6 coal headroom; P0.7 the renewable
  subtractor; P0.8 the residual's cold-only scope.
- `SESSION_HANDOFF_2026-08-01_S109.md` + `DROP_IN_S110.md`.

## S108 (2026-08-01) — G20 done, G21 walked, holes #7/#8, brain s103.6

**Data-integrity guards (the recurring enemy has now worn THREE faces: empty, wrong-value, off-instrument)**
- `research/kalshi/tape_reconcile.py` — HOLE #8. Asserts `tape_conditions` measures the CONTRACT BEING
  FORECAST by reconciling its trade count against the scored leg; hard-fails outside [0.95, 1.05]. Wired
  into `stage_group` after `state_health`. Presence is not enough and internal consistency is not enough -
  only reconciliation settles it. Also carries `load_leg_trades`, the leg reader the harness now uses.
- `research/kalshi/state_health.py` — extended: a `provisional_tail` weather day is now HARD (hole #7).
- `research/kalshi/archive_blind.py` — THE FILENAME COLLISION (3rd occurrence). Archives the blind's
  posteriors by MOVE, not copy, so a specialist that fails to write hard-fails the guard instead of
  silently serving blind numbers at the refine's filename.
- `research/kalshi/group_coordinate_refine.py` — `assert_not_the_blind()`: hashes every round-1 posterior
  against its blind archive and refuses a byte-identical match. Negative-tested. Also renders
  blind-vs-refine-vs-price.
- `research/kalshi/group_coordinate_blind.py` — speaks the ENGINE schema natively (accepts
  `expected_magnitude_usd`/`path_p50_curve` as well as the legacy names), killing a per-run hand-built
  alias that lived in the scratchpad and did not survive a session. Regression-proven byte-identical.

**Session bootstrap**
- `research/kalshi/session_bootstrap.py` — one command from empty to ready: keys chmod 600, STS verify
  (prints only the account tail), restore, then the completeness gate. `--verify-only` reports without
  writing. Strips the container's PLACEHOLDER creds on every AWS call.
- `scripts/session_start.sh` — extended to restore automatically when creds are present and to NO-OP
  LOUDLY when they are not.

**Measurement / scoring tools (all read committed artifacts only - no restore, no creds)**
- `research/kalshi/blind_score_nonpooled.py` — **the scoring view doctrine now requires**: per-day errors,
  `sum|err|`, drift AND the survival ratio together, because drift is a sum of SIGNED errors and cancels.
- `research/kalshi/blind_drift_trend.py` — forward-curve drift group over group.
- `research/kalshi/blind_lean_decomp.py` — is the blind's error a LEVEL bias or SHAPE? (answer: shape).
- `research/kalshi/bshare_normalization_probe.py` — the probe that found the b_share defect.
- `research/kalshi/blind_input_audit.py` — what the BLIND actually sees in a staged state.

**Harness fixes**
- `research/kalshi/flow_read.py` — two-sided b_share series + `unsided_volume_frac` + `phase_volume_lots`
  / `phase_n_trades`; reads the SCORED LEG when a group context is supplied.
- `research/kalshi/forecast_harness.py` — `prior_full_session` (the Monday stub fix), the two-sided
  copy-through, `squeeze_watch`'s live calendar limb, `--group` on decision-state, leg-targeted tape read.
- `research/kalshi/nws_temp_feed.py` — flags `provisional_tail` on the last day of any fetch range.
- `research/kalshi/group_he24_he1_handoff.py` — stage-time exit-state precompute + `chain_regime_age_sessions`.
- `research/kalshi/stage_group.py` — passes `--group`, runs the reconciliation, precomputes exit states.

**Brain + merge record**
- `research/kalshi/knowledge/ng_brain.json` — **s103.6, 67 plays** (backups s103.2/.3/.4/.5).
- `research/kalshi/G20_MERGE_PROPOSAL_S108.json`, `BSHARE_NORMALIZATION_PROPOSAL_S108.json`,
  `BSHARE_REPOINT_COMPLETION_S108.json`, `G21_MERGE_PROPOSAL_S108.json`,
  `BSHARE_REPOINT_GAP_S108.md` — the four merges and the gap C found in the first b_share fix.
- `research/kalshi/adjudicate_g20_merge.py` — takes ANY proposal path; verifies strictly-additive.
- `SESSION_HANDOFF_2026-08-01_S108.md` / `DROP_IN_S109.md` — the record + the next box (the branch box
  is BOX 1 there, to be pasted alone first).

## NEW IN S104 (2026-07-21, current) — Friday->Monday cascade cleanup, G15 MBO round 2, coordinator guard

- `research/kalshi/agents/mbo_refine_shared.md` + `mbo_specialist_{A,B,C,D,E}.md` — CANONICAL MBO
  5-specialist causal-refinement files (A weekend/B Monday/C core/D Thu-EIA/E Fri-expiry), incl. the
  round-2 HE24->HE1 handoff protocol + output contract. Registered in agents/README.md.
- `research/kalshi/coordinate_g15_mbo.py` — now GUARDED (SELECT/ASSEMBLE only; hard-fails on any
  day-move no specialist owns) + `--r2` round-2 mode + actual-curves-only render (own p50 path,
  no re-anchored/scaled lines, no gap bridges). The guard + render pattern to port to every coordinator.
- `research/kalshi/forecasts/grp15_mbo_specialist_{A..E}_r2.json` + `grp15_mbo_refined_r2.json` +
  `renders/ng_refine_s95/g15_mbo_comparison_r2.json` — G15 MBO round 2: 12/12 dir, mean abs err 66.
- `research/kalshi/knowledge/ng_brain.json` — **s102.5, 46 plays** (backup ng_brain_s102.4_backup.json;
  the three cleanup proposals kept as review artifacts: ng_brain_{friday,midweek,monday}_proposal.json).
- `research/kalshi/CASCADE_S104_friday_cleanup_summary.md` / `CASCADE_S104_monday_fix_summary.md` —
  the per-day cascade tables (committed copies of the specialists' analyses).
- `SESSION_HANDOFF_2026-07-21_S104.md` / `DROP_IN_S105.md` — the record + the next box.

## NEW IN S101 (2026-07-21) — G12+G13 walked, day-class doctrine, rest-of-year data machine

- `research/kalshi/run_g12_rt_s101.py` / `run_g13_rt_s101.py` — G12/G13 actuals (rt.json) +
  continuous renders on the walked NG.n.0 basis from the local n0 store (the run_g11 precedent).
- `research/kalshi/pull_july_2026_cl.py` — CL July 2026 raw top-up (CL year store ended 06-30).
- `deploy/aws/pull_rest_2026.py` — THE REST-OF-YEAR DATA MACHINE (detached box job): NG.n.0/n.1
  trades Mar->present, NG.FUT + ON/LNE.OPT + CL.FUT + LO.OPT statistics/definitions raw, CL.n.0/n.1
  full year. Resumable, cost-guarded ($1.10 total measured).
- `deploy/aws/cl_redecode_runner.py` — the 51 CL stub-Monday FREE redecode from done Databento
  jobs (box-detached; window closes ~Aug 12-14).
- `research/kalshi/knowledge/ng_brain.json` — s101.6, 27 plays (backups: s101.2/s101.5;
  proposals: s101.3/s101.6 kept as review artifacts).
- forecast_harness.py additions: `--mask-after` one-shot masking fix; squeeze_watch prompt-expiry
  fields + unwind_watch.
- Extended stores (S3-pushed): storage_consensus (hole closed, 47 reports), steo_vintage (11
  vintages), flow_calendar + solar_calendar (-> 2026-12-31), vol_regime (-> Mar 13), n0 tape
  (-> Mar 13 local; box extends to present on S3).
- `SESSION_HANDOFF_2026-07-21_S101.md` / `KICKOFF_2026-07-21_S102.md` — the record + the next box.

## NEW IN THE DASHBOARD SESSION (2026-07-20, current)

- `dashboard/` — the Mission Control READ PLANE (dashboard wiring session, branch
  `claude/dashboard-wiring-rgvahe`): FastAPI server (`dashboard/server.py`) + read-only
  adapters over the signal core (brain / decision_state / lag map / fees / kalshi candles /
  nymex minute bars / data-plane health) + the S100 prototype frontend wired with
  REAL DATA / AWAITING DATA / SIMULATED truth badges. Executor lane deliberately NOT built
  (last, per Greg). See `dashboard/README.md`; landing pad `DASHBOARD_HANDOFF_S100.md`.

## NEW IN S100 (2026-07-20, current)

- `research/kalshi/mos_cycle_feed.py` — feed A ph1: cycle-level MOS as-of (00z/06z/12z/18z,
  weekend cycles; availability wall runtime+4.5h). Store S3 `weather/mos_cycle/`.
- `research/kalshi/freeze_risk_feed.py` — feed E: basin freeze-off MIN temps (MAF/OKC/PIT/SHV),
  thresholds-as-data. Store S3 `weather/mos_freeze/`.
- `research/kalshi/lag_execution_map.py` + `kalshi_fill_model.py` — feed M: the lag execution
  map on the KXNATGASD life + verified fee/spread model. Store S3 `kalshi_echo/`. Findings:
  `research/kalshi/KALSHI_ECHO_MAP_S100.md` (maker-first verdict).
- `research/kalshi/TWO_COACH_SPEC_S100.md` — Tier 3 item 6, printed (approval pending).
- `research/kalshi/pull_july_2026.py` — the July 1-18 NG tape pull (done, idempotent).
- `research/kalshi/LIVE_TELEMETRY_S100.md` — the live loop's first datum (7.7ms median).
- `research/kalshi/vendor/` — verbatim vendor references: Databento raw-API example, the
  IV/Black-76 tutorial (feed I ph ii pattern), `DATABENTO_LIVE_OPS_NOTES_S100.md` (M5 collector
  design constraints: replay/snapshot/limits/reconnect).
- `DASHBOARD_HANDOFF_S100.md` (repo root) — the parallel dashboard session's landing pad.
- Brain: `knowledge/ng_brain.json` = **s101.2** (Tier 3 doctrine merged; s100.3 backup kept).

> **TODO — FORECAST WORKFLOW (Greg S87, not built).** Build a workflow that runs the daily NYMEX
> path-forecast lifecycle automatically:
> 1. **By 5PM the day before** — score and LOAD tomorrow's forecast (pick the analog/expected-path
>    curve for the next session, ready to trade against at open).
> 2. **In the morning** — RECALC it (refresh with overnight state: updated curve shape, news,
>    weather, storage, regime) before the session.
> 3. **Through the day** — if RT NYMEX ISN'T TRACKING the loaded forecast, FIND A NEW ONE
>    (re-match analogs / roll the forecast mid-session — the adaptive re-forecast). Distinguish
>    "analog was wrong -> re-forecast" from "move reversing -> exit."
> See `research/kalshi/PATH_FORECAST_RESEARCH_S87.md` for the methods.
>
> **HOW IT RUNS DAILY (Greg S90, "how do we remember to do this daily?").** The SAME daily lifecycle
> covers the WEATHER-DISTRIBUTION trade (KXHIGH*: score tomorrow's ladder by ~5PM, recalc in the AM,
> re-check intraday) AND the NYMEX path forecast. Do NOT rely on memory — the cadence must be a DURABLE
> DAILY TRIGGER. Mechanism: a GitHub Actions daily `cron` (matches the existing durable collectors;
> Greg dispatches/holds the secrets) OR a Claude Routine (`create_trigger`, daily cron, fires into a
> session). Wire the trigger once the forecaster EMIT (per the interface spec) + the per-cell scoring
> SCRIPT exist; until then this is recorded, not scheduled (a trigger firing into an empty pipeline is
> premature). See `WEATHER_FORECAST_INTERFACE_S90.md`.

The map of every Kalshi file: what it is, where it lives, and whether it's part of the CURRENT
pipeline or an OLD/completed piece. Keep this current — add new files to the top section, move
superseded ones down. (Started S81, 2026-07-12.)

## S99 — four gate feeds + the Monday repair (CURRENT)
- **`research/kalshi/steo_vintage.py`** + S3 `steo_vintage/` — FEED T (WIRED): the 7 frozen STEO
  vintage workbooks (sep25..mar26), all 37 Table-5a series, MEASURED release-date joins
  (knowable_from = release+1; Last-Modified never used), per-workbook column-origin detection,
  revision deltas vs prior vintage (the freeze re-mark readable from 2026-02-11). Selftest 22/22.
  `STEO_VINTAGE_NOTES_S99.md`.
- **`research/kalshi/nuclear_outages.py`** + S3 `nuclear_outages/` — FEED R arm 1 (WIRED): EIA
  daily US nuclear capacity-out 2007->present, wall period+1 strictly-prior, gaps stay gaps; the
  freeze's 1.8->3.2 GW jump at D+1. `NUCLEAR_OUTAGES_NOTES_S99.md` — ALSO carries the Pyth
  reckoning (NGD feeds never published; NATGAS 24/7 = Pyth Pro; FREE HERMES DIES 2026-07-31 ->
  pyth_collector sunset decision) and the KXNATGASD settlement verification (Pyth per-contract
  NGD 1-min close 17:00 EDT; 5bd-forward underlying roll; expiration_value = the settle print).
- **`research/kalshi/grid_stack.py`** + S3 `grid_stack/` — FEED Q (WIRED): EIA-930 daily per-BA
  demand + DAY-AHEAD demand forecast (DF) + gen by fuel + shares + labeled US48 burn estimate;
  wall period+2; Eastern framing; freeze ramp 28.3->41.1 Bcf/d decision-time-visible.
  `GRID_STACK_NOTES_S99.md`.
- **`research/kalshi/options_surface.py`** + S3 `options_ng/` — FEED I phase i (WIRED; G13 gate
  item CLOSED): NG options OI pin map off GLBX definition+statistics, BOTH roots (ON+LNE — the
  "NG.OPT resolves to nothing" symbology trap), 81 sessions, top-5 OI walls / P/C / OI-weighted
  strike / opex clock; opex anchors cross-check flow_calendar exactly. $4.67 substrate; monthly
  chunking beats the 4-month 504. `OPTIONS_SURFACE_NOTES_S99.md`.
- **`research/kalshi/databento_live_smoke.py`** — one-shot validation of the Bento LIVE plan
  (Standard $179/mo, SUBSCRIBED S99 close; smoke test = S100 opener).
- **`research/kalshi/renders/settle_delta_sweep_s99.json`** — Kalshi settle vs NYMEX 17:00 tape,
  full KXNATGASD life: matched days median 0.1c; all big deltas = 5bd roll-window contract
  mismatch (calendar spread, not oracle error).
- **`research/kalshi/redownload_mondays.py`** (pre-existing S92 script, re-run S99) — repaired
  the 22 NG stub Mondays Feb 2 - Jun 29 2026 found by the sweep (incl. ALL G12/G13 Mondays). CL's
  51 stubs HELD for Greg (paid ~$130-165 vs free redecode before job expiry ~Aug 12-14).

## S98 — the rewritten DATA GATE (the build list before any new group runs)
- **`research/kalshi/knowledge/ng_brain.json`** — **s100.3, 23 plays** (MERGED 2026-07-20, Greg
  approved: the C2 measurement - ratio reformulation REFUTED on comparable data, 0120 0.714 vs 0107
  0.718; C2 kept + scoped per-instance, flip confirm completes as C1+C3+C4 on the modern tape
  class; forward test rides G12). Backup `ng_brain_s100.2_backup.json`; record
  `C2_RATIO_FINDINGS_S98.md` + `run_g11_fingerprints_s98.py` (all 12 G11 sessions fingerprinted on
  NG.n.0, series_basis-tagged, pre-G11 counts reproduced exactly).
- **`research/kalshi/storage_consensus.py`** + S3 `consensus/` — FEED D (WIRED): the EIA weekly
  storage SURVEY CONSENSUS (the number the market is positioned against, vs the seasonal proxy),
  29/29 weeks Sep 2025-Mar 5 2026, per-house rows + disagreement exposed, holiday-shifted prints
  verified (incl. the Dec 29+31 double-print week), 0 blind-wall violations, named forward hole
  Mar-Jul 2026. `STORAGE_CONSENSUS_NOTES_S98.md` = sources/caveats; 17 weeks of as-printed vs
  current-vintage diffs handed to feed K.
- **`research/kalshi/platform_sync.py`** — the ONE door between local cache and the S3 data plane
  (M2): list / pull / push with per-prefix manifests, dry-run default, post-push verify.
- **`research/kalshi/kalshi_ng_backfill.py`** + **`data/kalshi_ng/`** (local, gitignored; S3 push
  pending) — FEED L: Kalshi NG family backfill off the public API's live+historical endpoint split
  (`/historical/cutoff` = the moving boundary, 2026-05-21 at build). Full raw definitions + trades +
  1-min candles for KXNATGASD/KXNATGASW/KXNATGASMON life and the winter annual NG markets.
  `--selftest`, `--coverage`. HEADLINE FINDING: KXNATGASD did not exist before 2026-03-27 — the
  walked winter has NO Kalshi NG daily market (Jan-Feb 2026: zero NG-linked Kalshi markets at all);
  feed M's winter echo replay is structurally impossible, its lag/fill work runs on the Mar 30+
  life instead. Dailies skip FRIDAYS (the weekly market owns Friday).
- **`research/kalshi/KALSHI_NG_COVERAGE_S98.md`** — feed L's deliverable: branch-bins inventory
  (collector born 2026-07-12; one named 12h outage Jul 16-17), the two-worlds API map + S80 code
  drift, the 119-date winter coverage table (every date a named gap for the family), what
  live-forward capture provides that history cannot (books, sub-minute).
- **`research/kalshi/DATA_GATE_S98.md`** — THE AUTHORITATIVE DATA PLAN (Greg 2026-07-20: "this is what
  we're doing before we do any more runs"). Supersedes the GATE section of
  `SESSION_HANDOFF_2026-07-19_S97.md`. Organized by regime family (DEMAND / POSITIONING / DELIVERY):
  Tier 0 = wire the three landed S97 feeds + `squeeze_watch` + the information clock; Tier 1 = G11
  fingerprints on `.n.0` -> the C2 ratio reformulation (the G12 critical path); Tier 2 = feeds A-M
  (model-cycle timing, vol regime, model disagreement, storage CONSENSUS, freeze-off risk, flow
  calendar, cash basis, COT combined, options surface [required for G13], LNG feedgas sizing spike +
  paid-data survey, revision-vintage audit, Kalshi NG data restore [L], lag echo replay + Kalshi
  fill/fee model [M]); Tier 3 = brain doctrine (usage guidance, flip driver checklist, evidence-day
  registry, two-books scoring split, squeeze-regime doctrine, the TWO-COACH spec). Section 0c = the
  TWO-COACH ARCHITECTURE (Greg 2026-07-20): Kalshi = initial primary vehicle, NYMEX dailies quickly
  after, one shared signal core, two separately-scored coaches; the lag is the Kalshi edge.
  Gate-closure condition at the bottom defines when G12/G13 may run.
- **`deploy/aws/AWS_PLATFORM_S98.md`** — the platform consolidation + AWS migration plan (Greg
  2026-07-20: end the data sprawl; platform lives in AWS, hybrid with git). git = CODE, S3 = ALL
  DATA one bucket + manifests, local = cache, live loop us-east-1 co-region with Kalshi.
  Execution-speed verdict: the established 7-20s+ futures->Kalshi lag needs SUB-SECOND not sub-ms;
  LLM never in the hot path; lag telemetry per fire (decay watch, never a retest). M1-M6 steps;
  M1 = key rotation (Greg) blocks all pushes.
- **S97 feed modules (landed S97, indexed here):** `research/kalshi/cot_feed.py` +
  `data/cot/` (CFTC COT, publication-time blind wall); `research/kalshi/storage_regional.py` +
  `data/storage_regional/` (EIA five-region + salt/non-salt); `research/kalshi/contract_structure.py`
  + `data/contract_structure/` (49 fields incl. the CALENDAR-FRONT block that sees what the
  OI-continuous front hides). WIRED into decision_state in S98 Tier 0 (audit-joins: 0 violations,
  101 days).

## S96 — G7 winter block + per-group refine + the settled protocol (CURRENT)
- **PROTOCOL (Greg S96):** one-shot block-blind = the CANONICAL skill test; refine after EVERY group
  (iterate until refined curves track via GENERAL rules only, n>=2 spanning groups; irreducibles declared);
  renders PRINTED (sent to Greg) before each refine.
- **`research/kalshi/forecast_harness.py`** — S96 BLIND FIX (storage/surprise joins strictly-prior-day; the
  old `<=` leaked a storage Thursday's own 10:30 print) + **`reveal` subcommand** (day-sequential rolling-anchor
  reveal packages: per-day actuals + per-leg fingerprint counts; kept for the LIVE-coach mode).
- **`research/kalshi/forecasts/grp7.json`** — G7 blind + refined fields per day; `grp7_seq_experiment.json` —
  the paused 3-day day-sequential experiment (its 1106 +1450g/+1350a hit = the day-boundary-turn evidence).
- **`research/kalshi/knowledge/ng_brain.json`** — **s99.2, 21 plays** (S96 arc added: giveback_exhaustion_
  boundary, mature_swing_alternation, giveback_origin_shelf, catalyst_continuity_frontrun,
  chain_polarity_flip [four-condition confirm], failed_rally_tell, crash_regime_bands,
  post_parabolic_bleed). Backups + all proposals alongside.
- **`research/kalshi/forecasts/grp{7,8,9,10}.json`** — blind + refined fields per day for the four winter
  blocks; `grp9` = the December surplus-collapse crash (lean-miss 1 -> polarity flip); `grp10` = the January
  bleed (lean-miss 2, the false flip -> the hardened confirm + the bleed class).
- **`research/kalshi/renders/ng_refine_s95/`** — g{7,8,9,10}_{continuous,overlay}.png + *_refined_*.png +
  rt/score jsons + grp*_state.json + grp7_reveals.json; fingerprints.json spans Nov 4 -> Jan 16
  (52 characterized days).

## S95 — continuous-curve + roll-adjustment + refinement machinery (CURRENT)
- **`research/kalshi/continuous_rt.py`** — THE RENDER FILE (canonical, date-parameterized): real-price RT
  curve + optional `--guess` forecast overlay, rolls marked, weekend bridges broken. Use for any window.
- **`research/kalshi/roll_adjust.py`** — contract-roll detection (instrument_id change) + back-adjust offsets.
- **`research/kalshi/fast_tape.py`** — fast trade-price loader (grep-prefilter + npz cache, ~7x).
- **`research/kalshi/precache_window.py`** — pre-decode a date window to npz.
- **`research/kalshi/continuous_score.py`** — per-event scorecard + roll-adjusted skill overlay.
- **`research/kalshi/characterize_turns.py`** — merge per-leg fingerprints into `fingerprints.json`.
- **`research/kalshi/extract_guesses.py`** — pull guess-vs-actual scalars from the brain -> `guesses.json`.
- **`research/kalshi/AGENT_RUNBOOK_S95.md`** — the two agent prompts (blind forecaster + unblinded refine).
- **`research/kalshi/forecasts/`** — committed per-group forecast records (guess curve + reasoning) grp{3,4,5,6}.
- **`research/kalshi/renders/ng_refine_s95/`** — committed renders (g3g4g5_continuous.png, g6_continuous.png,
  *_rt.json, fingerprints.json, guesses.json, *_state.json) so they need no regeneration.
- **`research/kalshi/knowledge/ng_brain.json`** — the ONE-FILE brain (s95.1; + s95.2 proposal to merge).

> **FILE DISCIPLINE (Greg S87, load-bearing).** EDIT existing live files first; only create a NEW
> file if one does not already exist for that purpose. Do not spin up a parallel file that
> re-implements what a live file does — extend the live one with a flag/mode. (S87 lesson: a separate
> `lag_join_intraday.py` duplicated ~80% of `lag_join.py` and was folded back in.) Check this index
> before creating any file.

Data stores are LOCAL/gitignored (too big for git): `data/kalshi_hist_trades/` (historical trades),
`data/pyth_ticks/` (Pyth + Databento NYMEX trades ticks), `data/nymex_mbp10/` (S86: MBP-10 trade+book
depth tape), `data/kalshi/` (live bins + consensus). **S90: ALL Databento (bento) tapes now live on AWS S3,
NOT git** — bucket `bento-568968024170-us-east-2-an` (us-east-2), prefix `nymex/`: the continuous full-raw
YEAR corpus at `nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz`, the S85 trades tape at `nymex/nymex_tape/`, the
S86 depth tape at `nymex/nymex_mbp10/`. `kalshi-session-start` restores the tapes from S3 (needs AWS creds);
the continuous corpus streams on demand via `event_move_baseline.load_cont_day(..., source="s3")`. The
`data/nymex-ticks` git branch is retired for bento data (tapes removed S90; `nymex_cont/` wiped S89). Other
durable data still on branches: `data/kalshi-bins`, `data/pyth-ticks` (Pyth, non-bento). See
`research/kalshi/AWS_INGEST_SETUP_S89.md`. AWS + Databento keys are session-pasted SECRETS.

**S93 changes (detail in `SESSION_HANDOFF_2026-07-14_S93.md`):** — the coach agent moved INTO AWS.
- `deploy/aws/COACH_AGENT_SETUP_S93.md` — **NEW**: reproducible box-agent setup (SSM access, Bedrock in us-east-1
  vs S3 in us-east-2, Node+Claude Code install, `/etc/markets/coach.env`) + the THREE pluggable LLM backends —
  Claude Code+Bedrock, Anthropic API direct, and **OpenAI** (Greg S93). The open Claude-Code model-preflight snag.
- `SESSION_HANDOFF_2026-07-14_S93.md` / `KICKOFF_2026-07-15_S94.md` — the S93 record + S94 priorities (JOB 1 =
  make the agent LLM invoke on the box; JOB 2 = run the loop on the box; brain still s92.1, not advanced).
- `scratchpad/ssm_run.py` (gitignored) — SSM send+poll helper to drive the box `i-08cee...` from a session.
- AWS access state: `Claude` IAM user (acct 568968024170) = S3Full + EC2 + SSMFull + BedrockFull + inline
  `pass-ssm-role`; no permissions boundary. Bedrock model access enabled in **us-east-1 ONLY**. Box instance
  profile = `Ssm` (SSM-only role); coach uses static `Claude` keys for S3+Bedrock.

**S92 code changes (detail in `SESSION_HANDOFF_2026-07-14_S92.md`):** — the NG intraday FORECASTER program.
- `research/kalshi/month_characterize.py` — FULL-TOOLBOX per-leg characterizer: added the **exhaustion suite**
  (`depth_pieces` -> aligned_imb_push/exhaustion/far_thinning/spread_ratio, reuses `event_move_baseline.depth_features`),
  the **dipole** (`dipole_pieces` -> dip_imb_level/dip_aligned_flow/..., reuses `odcore.info_dipole`; Lee-Ready side),
  the **turning-point fingerprint** (`turn_pieces` -> turn_* measured entry->peak), and the **storage-surprise** +
  live **curve** joins. This is the per-leg fingerprint the forecaster/coach agents read.
- `research/kalshi/knowledge/ng_brain.json` (+ `knowledge/README.md`) — the machine BRAIN: versioned PLAYS
  (direction.flow_nowcast, ride.magnitude_staircase, exit.recruitment_reversal, shape.grind_vs_spike, daytype.*) +
  mechanisms + open frontier + ruled-out-by-target. The coach loads + applies it; the loop merges into it.
- `research/kalshi/NG_BEHAVIOR_KNOWLEDGE.md` — living, status-tagged knowledge base (grows every pass; the human view).
- `research/kalshi/NG_FORECAST_LOG_S92.md` — the blind-forecaster's reasoning + magnitude-scaling + the data-gap plan.
- `research/kalshi/FORECASTER_RUNBOOK_S93.md` — **VERBOSE operating manual** for the loop: the vision, the plays,
  the machinery, the exact loop commands, JOB 2 (net-of-fee coach replay), the guard, and the NYMEX-OPTIONS
  trading-vehicle survey (Greg S92: "look at nymex options for actual trading very soon"). Read this to run S93.
- `research/kalshi/coach_replay.py` — **executable playbook backtest** (the rigid baseline the adaptive coach must
  beat): applies ng_brain.json plays per leg net-of-fee, per-event, no pooling. Canary-side + indicative for now;
  real fill model + Kalshi/NYMEX-option venue = S93. `--selftest` PASS.
- `research/kalshi/forecast_harness.py` — turn-key loop helpers: `decision-state` (blind-safe group state),
  `overlay` (guess-vs-actual render), `brain-show`. `--selftest` PASS.
- `research/kalshi/redownload_mondays.py` — the Monday re-download tool (2-day [Mon,Wed) batch, upload clean over
  the stub). Re-run for the FINAL Monday sweep after the box finishes (it minted new corrupt Mondays past Sep).
- `research/kalshi/renders/ng_learn_s92/` — 12 learn-day curve grid + 12 individual day PNGs + the blind guess-vs-actual
  overlay + the forecasts JSON (for the intraday-curve grapher).
- `research/kalshi/databento_backfill.py` — **`_flush` fix: 'wb' -> 'ab' (append)** — the every-Monday-corruption
  root cause (Tue->Tue weeks made Monday the last batch day; a straggler re-created a 1-row file that the 'wb' final
  flush clobbered). Concatenated gzip members decompress as one; the reader sorts by ts.
- `research/kalshi/pull_year_mbp10.py` — **DOW naming** ({ROOT}_{YYYYMMDD}_{dow}.jsonl.gz) + **calendar-aware
  stub/marker** (`_expected_full`: weekends + CME full-closure holidays are legit-tiny, not corruption) + a
  **`--reconcile-names`** repair mode (rename date-only -> dow + write week markers; run after the box DONE) + `--selftest`.
- `research/kalshi/event_move_baseline.py` — `_s3_fetch_cont_gz` reads the dow-labeled name (legacy fallback).
- `research/kalshi/nws_temp_feed.py` — `--overwrite` flag (forward-collector top-up of the trailing months).
- `.github/workflows/nymex_mbp10_ingest_durable.yml` — rewritten git->S3 + `--weekly` (AWS+Databento GH secrets).
- `.github/workflows/nws_hourly_collector_durable.yml` — NEW RT NWS-hourly collector (trailing-2-months --overwrite -> S3).

**S91 code changes (detail in `SESSION_HANDOFF_2026-07-14_S91.md`):**
- `pull_year_mbp10.py` — **`--weekly`** (week-at-a-time S3 pull: 53 fresh per-week Databento batch jobs, per-week
  publish, marker-based resume `nymex_cont/_done/{root}_{ws}.done`) + **stub-aware resume-skip** (`_s3_month_present`
  treats a month with any sub-5KB stub or <15 days as ABSENT -> re-pulled). Runs on the durable box.
- `kalshi_collector.py` — added METALS (`KXGOLDD`, `KXSILVERD`) to the watchlist.
- `pyth_collector.py` — added Pyth `XAU`/`XAG` spot feeds (gold/silver settle number + fast underlying).
- `research/kalshi/GOLD_SILVER_LAG_FINDINGS_S91.md` — gold/silver depth-add: LAG confirmed (free Pyth), cross-strike NG-only.
- `research/kalshi/NYMEX_PRODUCTS_SURVEY_S91.md` + `KALSHI_PRODUCT_RANKING_S91.md` — the two S91 agent surveys (KXGOLDD #1).

**S90 code changes (detail in `SESSION_HANDOFF_2026-07-13_S90.md`):**
- `databento_backfill.py` — FIXED the flush bug (80% loss; hold-days-until-complete); `_download_decode_flush`
  + `redecode_job(jid)` re-decode an already-paid done job FREE.
- `pull_year_mbp10.py` — `--reuse-done-jobs` recovery mode (rebuild corrupt months from paid jobs, no re-charge).
- `event_move_baseline.py` — `load_cont_day(root, day, source="s3"|"local")` + `normalize_mbp10_row` (the JOB 2
  S3 tape reader: trade-filter + ladder-aggregate at READ time; S3 stream + local gz cache).
- `month_characterize.py` — `load_cont_full` routes through the shared reader + `--source s3|local`.
- `nws_temp_feed.py` — RAW HOURLY ingestion `--ingest-hourly` (`fetch_asos_raw`/`ingest_hourly_raw` -> every
  field/ob to `s3://.../weather/nws_hourly/`, NO roll-up); daily rollup now S3-synced (derived, not the store).
- `deploy/aws/` — the durable-box deploy kit (setup.sh + systemd units + runbook). The S90 EC2 box was launched
  ad-hoc via boto3 (AMI/SG/run_instances) with a self-configuring boot script pulling code from S3.
- `research/kalshi/WEATHER_FORECAST_INTERFACE_S90.md` — the forecaster emit-contract (per-cell distributions).

---

## CURRENT KALSHI FILES

### Collectors & data feeds
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_collector.py` | Live public-API order-book snapshot collector (28-series watchlist: weather/macro/energy/electricity). Unified YES book. → `data/kalshi/*_bins.jsonl`. |
| `research/kalshi/kalshi_history.py` | Historical settled-market trade puller — per-ticker fills WITH signed `taker_side` (real signed flow) + candles. → `data/kalshi_hist_trades/` (local). |
| `research/kalshi/pyth_collector.py` | **[S81]** Pyth Hermes sub-second tick collector for the NYMEX/ICE futures Kalshi settles on. SSE stream, dedup on advancing publish-time. → `data/pyth_ticks/`. NOTE (S84): the `NGDQ6` feed id is BOGUS (Pyth has no natgas) — fix pending; WTI works, Brent live-only. |
| `research/kalshi/pull_year_mbp10.py` | **[S87/S89]** The durable YEAR driver: pull continuous full-raw MBP-10 (CL+NG) month-at-a-time via `databento_backfill.batch_pull`, gzip each day AS IT LANDS + delete raw (local bounded to 1 day), resume-skip months already in the store. **`--dest`**: `git` (worktree of data/nymex-ticks) OR `s3://BUCKET/PREFIX` (boto3 -> PREFIX/nymex_cont/, standard AWS env auth). `--worktree`/`--scratch` to run anywhere. **S89: the tick corpus now lives on AWS S3** (`bento-568968024170-us-east-2-an`, us-east-2, prefix `nymex/`), NOT git; AWS + Databento keys are session-pasted SECRETS. |
| `research/kalshi/AWS_INGEST_SETUP_S89.md` | **[S89]** Runbook: bucket + IAM setup, the `--dest s3://…` run commands, the 6/6 disjoint-month split, resume, and end-to-end verify (download a gz, confirm 76-field raw rows). The live target + how a new session resumes the year pull. |
| `research/kalshi/databento_backfill.py` | **[S84/S85/S86]** TRUE-TICK historical NYMEX backfill from Databento (`GLBX.MDP3`): CL crude AND NG natgas at the `trades` schema (every print, nanosecond) — fixes Pyth's NG gap + 1-sec undersampling. Modes: cost / window (sync) / batch (large/cheap) / **defs** (S85: `definition` schema → `{ROOT}_definitions.jsonl` point-in-time tick size/value). **S86/S88: `--schema mbp-10`** → `_write_mbp10_df`. **S88 (Greg): keeps ALL RAW info** — every message (trades AND book updates) + every column (all 10 price levels + sizes + counts per side + action/side/depth/flags/ts_event/ts_recv/...), zero filtering/reduction/derived-fields (`_json_safe` normalizes without losing info). We paid for the full dataset, we store the full dataset; the agent sifts raw for driver→price correlations; gates ONLY on the trade side. → `data/nymex_mbp10/` (or `nymex_cont/`). `metadata.get_cost` gate. Needs `DATABENTO_API_KEY` secret. PRIMARY historical source. |
| `research/kalshi/pyth_backfill.py` | **[S84]** HISTORICAL per-second NYMEX backfill from Pyth's timestamp endpoint — windows around past releases, throttled (429/5xx backoff), dedup, → `data/pyth_ticks/` (tagged `src=pyth_hist_1s`). WTI only (Pyth has no NG; Brent-historical 404s). 1-sec UNDERSAMPLES — a lower bound, never the full tape. |
| `research/kalshi/consensus_poll.py` | Polls the free ForexFactory weekly JSON for release forecasts (Crude/NatGas/CPI/NFP/FOMC). → `data/kalshi/consensus.jsonl`. |
| `research/kalshi/month_characterize.py` | **[S88]** Per-(commodity, MONTH) CONTINUOUS-tape characterizer — the workflow's per-agent tool. Reads `data/nymex_cont/` all-session tape, detects EVERY sustained intraday move (reuses `lag_join.scan_moves`), tabulates per intraday cell (tod x dir x book {support\|oppose}; coiled/curve/temp tags) the forward-path distribution (peak_usd $/c, fast_capture, sustain_s, retention, continuation). The intraday complement to `bucket_continuation.py` (which is release-windows only). Leakage-safe (cell features pre/at-entry, invariant to future price), `--selftest` PASS. One month = one regime (anti-lock-in). |
| `research/kalshi/forecaster_month_pass.workflow.js` | **[S88]** The corpus-characterization WORKFLOW (coin-style fan-out, Greg S88). Per (commodity x month): agent runs `month_characterize.py` blind to other months -> SYNTHESIS accumulates + separates stable-across-months vs month-specific -> adversarial VERIFY kills one-month-only patterns. Structurally enforces the anti-lock-in rule. STAGED (not fired); run in waves as `nymex_cont/` fills: `Workflow({scriptPath, args:{items:[{root,month},...]}})` for months whose tape is restored. |
| `research/kalshi/bucket_continuation.py` | **[S88]** The BUCKET CONTINUATION TABLE — forecaster method #1, the honest baseline every fancier method must beat OOS. Per cell, tabulates the forward-path DISTRIBUTION off the release windows: peak_usd quantiles, fast_capture (S85 front-loaded fraction), peaked_fast, retention, sustain_s, time_to_peak, continuation rate, + curve/temp regime mix. Cell keys (from GRAPH_LEARN_FINDINGS): NG = surprise sign x mag x coiled-volume {quiet\|active}; CL = surprise sign x mag x aligned_imb_push {support\|oppose}; temp/curve stored as conditioning tags (split on the year). `forecast()` matches a new day's decision-time state to its cell. Reuses `event_move_baseline.build`. Leakage-gated (cell assignment invariant to forward outcomes), per-cell distributions, $/c never bps. `--selftest` PASS; `--run` leakage_pass 12/12 both. Ran on the 24 warm-season tapes = machinery-validation only; re-run on the year library. Table -> `data/forecast/` (gitignored). |
| `research/kalshi/GRAPH_LEARN_FINDINGS_S88.md` | **[S88]** The forecaster's exploratory graph-and-learn pass (directive method step 2) on the 24 weekly tapes. Honest corpus caveat: weekday/curve-regime/temp all collapse or collinear with the Apr-Jul calendar ramp at n=12; only surprise sign/mag + microstructure are orthogonal. CL: release weak catalyst, slow-bleed (fast_capture 0.27), hold key = aligned_imb_push->sustain +0.52. NG: release IS catalyst, front-loaded (0.66), surprise-MAGNITUDE selects shape (big->spike+short, small->grind+long), coiled-volume->magnitude per-cell. The empirical basis for `bucket_continuation.py`'s cell keys. Warm-season/n=12 provisional. |
| `research/kalshi/forward_curve.py` | **[S88]** The NYMEX forward-CURVE reader — backwardation/contango + prompt-vs-term conditioning axis (directive priority 2). Pulls Databento continuous CALENDAR-RANK bars `{ROOT}.c.0..c.11` (ohlcv-1d, ~$0.07/yr both) → per-date curve features {front, slope_1, slope_back, curvature, regime} in $ never bps. `curve_asof(D)` = leakage-safe D-1 settle (the curve the morning of D knows). `--selftest` PASS. Ran on the year: CL backwardation 311/312 (Hormuz-tight); NG summer-contango→winter-premium hump→backwardation (213/99). Cache → `data/nymex_curve/` (gitignored, $0.07 re-pull). |
| `research/kalshi/nws_temp_feed.py` | **[S88]** The gas-demand TEMPERATURE feed for the NG path forecaster (Greg S88 directive sec 6). Realized historical hourly temp+precip from the NWS ASOS network via IEM (path A, labeling/scoring) → national population/gas-weighted **HDD/CDD + precip** daily index (16 demand metros, first-cut weights, base-65, central-US gas-day boundary) + `regime_bucket` (hard_heat/mod_heat/shoulder/mod_cool/hard_cool). `forecast_index_today` = decision-time NWS-API forecast (path B, forward/live only — no historical forecast archive, so historical conditioning uses the regime-bucket proxy). Leakage-gated (day value invariant under appended future obs). `--selftest` PASS. Cache → `data/nws_temp/` (gitignored). NOTE: national demand-weighted, NOT Henry Hub's Louisiana weather; per-hub local weather = the deferred basis stack. |
| `research/kalshi/eia_surprise.py` | **[S86]** Historical release SURPRISE (seasonal PROXY: actual weekly change − 5-yr same-ISO-week avg) from EIA API v2 (DEMO_KEY): NG working gas + crude ex-SPR. → `data/eia_surprise.json`, consumed by `event_move_baseline.py --surprise-file` to split cells beat/miss×big/small. `--selftest` PASS. Forward real consensus (consensus.jsonl) preferred when present. |
| `.github/workflows/kalshi_collectors_durable.yml` | 6h durable cron: restore→collect bins + poll consensus→gzip+push to `data/kalshi-bins`. |
| `.github/workflows/pyth_collector_durable.yml` | **[S81]** 6h durable cron: restore→stream Pyth ticks→gzip+push to `data/pyth-ticks`. |
| `.github/workflows/nymex_mbp10_ingest_durable.yml` | **[S89]** Durable RAW-INGESTION cron for the continuous MBP-10 YEAR (CL+NG, 2025-07..2026-07). Runs `pull_year_mbp10.py` a MONTH AT A TIME as a Databento batch; keeps ALL raw (zero filtering); gzips each day as it lands (local never holds >1 day); ADDITIVE push to `data/nymex-ticks:nymex_cont/` (never orphan-force-push); RESUMABLE (skips months already on branch) so it survives across 6h runs. Needs the `DATABENTO_API_KEY` secret + Greg's first "Run workflow" click. |
| `research/kalshi/pull_year_mbp10.py` | **[S87/S89]** The month-at-a-time year driver behind the durable workflow: batch-pull each (month, root) → `databento_backfill.batch_pull(flush_dir=…)` gzips each day into the `data/nymex-ticks` worktree as it lands + deletes raw → commit+additive-push the month → skip months already on branch (resumable). Full-raw, zero reduction. |

### Event-move baseline (S85) — the canary-move expectation-setter [RAN ON REAL TICKS]
| file | what it does |
|------|--------------|
| `research/kalshi/event_move_baseline.py` | **[S85]** Per-EVENT move MAGNITUDE + DURATION on the true-tick futures tape (the NYMEX canary), per surprise-cell. Anchors a strictly-pre-release baseline, measures the forward peak in TICKS/$/bps (tick size POINT-IN-TIME from the `definition` store, source aggregated per-event) + duration (time_to_peak, sustain_s, retention → run/blip/fade) + the **FAST (60s) window** (`--fast`): the sub-minute lag-scalp ceiling (fast_bps/$/capture, peaked_fast). Distributions not means, per-cell, leakage-gated. Expectation-setting, sizes the hold time. `--selftest` PASS. RAN on 12 NG + 12 CL real release windows (S85). |
| `research/kalshi/EVENT_MOVE_FINDINGS_S85.md` | **[S85]** First real result: per-contract HOLD-TIME map. NG front-loaded (60s captures 66% of the move, ~$310/contract); CL slower (60s=27%, a longer hold gets the rest — e.g. $2,640 built over 17min). Both KEPT, different hold windows; EV-net-of-fee is the gate not frequency. Futures move = the CEILING, not Kalshi P&L (lag join next). Cost map + MBP-10 schema decision. |
| `research/kalshi/event_move_baseline.py --depth` | **[S86]** MBP-10 depth read: per-event resting-book imbalance at R (pre-event, leakage-gated) + at the initial push (`aligned_imb_push`, `exhaustion`, `far_thinning`), contrasted against run length. `load_tape_depth`/`depth_features`/`_depth_summary`. `--selftest` PASS (depth math + leakage). Consumes `data/nymex_mbp10/`. |
| `research/kalshi/DEPTH_RUNLENGTH_FINDINGS_S86.md` | **[S86]** Book run-length read on the canary (24 windows, leakage PASS 12/12). Logged per-cell correlation of push-book one-sidedness vs run length: **NG −0.17, CL +0.52** (opposite-signed). Provisional, n=12, Apr-Jul window only (seasonality confound — no generalization). `aligned_imb_push` = candidate hold-time signal for the lag join. |
| `research/kalshi/EVENT_STATE_DESIGN_S86.md` | **[S86]** Design sketch (Greg's driver model): events stack on prior + anticipated state. Three pillars (news / storage / market-capacity), shared drivers with per-market/per-period weights, weather split (NG temps-demand / CL adverse-supply), news in three tenses + persistent geopolitical regime, storage = physical confirmation node, human/emotion = herd run, pre-release volume = first buildable primed detector. Eyeball-validated (06-17 = Hormuz crisis). |
| `research/kalshi/PREVOL_FINDINGS_S86.md` | **[S86]** First build off the event-state model: pre-release VOLUME primed/coiled detector (leakage-safe, no new feeds). NG — quieter pre-release precedes a bigger move, consistent sign across all 3 cells (Spearman -0.5..-1.0); CL weak/mixed (consistent with CL trading Hormuz not the EIA print in-window). Per-contract normal (same scaffold, different values). Provisional n=12. |
| `research/kalshi/EVENT_SURPRISE_FINDINGS_S86.md` | **[S86]** Surprise-cell split (seasonal-proxy, 12/12 matched). Logged: NG beat|big cell (n=3) all down + fast; CL |surprise| negatively correlated with move size (the $2,640 day was a −3.1 small surprise). Opposite-signed surprise/move relation NG vs CL, Apr-Jul only — no cause claimed, no generalization. |
| file | what it does |
|------|--------------|
| `research/kalshi/futures_kalshi_lag.py` | Per-contract futures→Kalshi lead-lag (S19 operator + time-slide null). Result: futures lead, Kalshi never leads; ~half of contracts reprice a full minute late. |
| `research/kalshi/lag_exploit_backtest.py` | **[S81]** Turns the measured lag into a net-of-toll backtest. Modes: `futures` (economic gate + maker/taker exit) and `crossstrike`. `score_hold` = fire-quick-then-hold trailing exit. Per-trade, per-cell, no averaging. |
| `research/kalshi/LAG_EXPLOIT_FINDINGS_S81.md` | **[S81]** The lag findings: direction predictable (sharpens with move size, 0.77 on big moves), edge is size-vs-fee, real but rare at 1-min → needs sub-minute (Pyth). |

### Level-hit continuation thread (S82) — the per-trade continuation predictor
| file | what it does |
|------|--------------|
| `research/kalshi/level_hit_dataset.py` | **[S82]** The per-trade LEVEL-HIT dataset: one row per 1¢ level transition — pre-hit context {moneyness, side, velocity, herd/whale, exhaustion, tod, release} + forward trailing-exit outcome {continued, big-run, net taker/maker}. Per-cell (moneyness×side×velocity×release), distributions not means, leakage-gated. → `data/level_hits_*.json` (local). |
| `research/kalshi/LEVEL_HIT_FINDINGS_S82.md` | **[S82]** Findings: level-hits mean-revert at 1¢ (cont 0.38); NO cell pays even at maker fees (confirms S81 size-vs-fee); the internal flow context is a weak predictor → the edge is EXTERNAL (futures lag). Next: join Pyth futures move onto each level-hit. |

### Release / book signals
| file | what it does |
|------|--------------|
| `research/kalshi/release_book_signal.py` | Live release-triggered book signal: direction = book-imbalance sign, magnitude/fade = imbalance + dipole exhaustion. Calendar-gated. Leakage PASS 0/30. |
| `research/kalshi/release_signal_history.py` | Historical release-signal test on real signed flow. Carries the SETTLE_UTC settlement-window guard + leakage gate. (Pooled hit-rate first pass superseded by the per-trade reframe; the harness + settle filter stay current.) |

### Coupling / scoring / weather
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_coupling_adapter.py` | Feeds Kalshi mid-probability into the signed-edge-vs-placebo coupling engine (asset=series, venue=market). |
| `research/kalshi/kalshi_score.py` | Settlement + forecast SCORING harness. Realized settlement vs market-implied ladder; Brier/log-loss/edge; lead-time market baseline. The scoreboard the OD-weather thread plugs into. |
| `research/kalshi/kalshi_weather_forecast.py` | EIA storage-number baselines (climatology/persistence, walk-forward) + a (value,sigma)→kalshi_score bridge. NOTE: the weather forecaster itself is Greg's own spec — this is just the bridge/scoreboard. |
| `research/kalshi/weather_regime_score.py` (+ `weather_regime.json`) | **[S84]** Per-REGIME weather scoreboard runner: walk-forward persistence + climatology `(value,sigma)`, scored PER CELL (city × regime × swing) as DISTRIBUTIONS not means, leakage-gated (PASS 66/66). Drop-in for the OD operator's `(value,sigma)`. Forecaster HANDS OFF. |
| `research/kalshi/WEATHER_BASELINE_S82.md` | **[S82]** Daily-high temp (`KXHIGH*`) scoreboard reference: the naive baseline bar the OD operator must beat (persistence/climatology Brier ~1.1–1.3; the edge is on frontal/transition days), the market structure (6×~2°F re-centered ladder), + a worked trade example (real KXHIGHNY-26JUN29, realized 88°F) with fees/payout. |
| `research/kalshi/NYMEX_CANARY_NOTES_S84.md` | **[S84]** Load-bearing: NYMEX is the CANARY, Kalshi the delayed follower (gather NYMEX, fire on Kalshi). Resolution reality (1-min useless, 1-sec floor UNDERSAMPLES = lower bound). Data-source inventory: Pyth WTI historical works, NO natgas feed (bogus `NGDQ6` id), Brent-historical 404s; NG/Brent need Yahoo. |
| `research/kalshi/WEATHER_REGIME_FINDINGS_S84.md` | **[S84]** Distributions-not-means sharpening of S82: the naive bar is REGIME-CONDITIONAL (persistence wins calm, climatology wins transition); climatology's transition edge is COOLING mean-reversion into wide tail buckets, NOT a front forecast; WARMING-spike cells are where both baselines (and the market) go blind = the operator's real room. NY transition-rich, DEN ridge-thin. |

### Shared engines (not Kalshi-only, but the pipeline runs on them)
| file | what it does |
|------|--------------|
| `news_ingest_rss.py` | RSS ingest → contract tagging (EIA/Fed/NHC feeds → `CONTRACT_KEYWORDS` per Kalshi series; ENERGY/INFLATION/JOBS/… categories). |
| `news_coupling_research.py` | Signed-edge-vs-placebo coupling engine (`--source kalshi`). NOTE: `--events` is a BASENAME joined onto `--data-dir`. |
| `regime_classifier.py` | Regime classifier (shared). |
| `odcore/leadlag.py` · `odcore/info_dipole.py` · `odcore/leakage.py` | The operator tools the lag/signal work is built on (lead-lag, flow-dipole divergence/exhaustion, the mandatory leakage gate). |

### Skills (session rituals — `.claude/skills/`, added S83)
| skill | what it does |
|-------|--------------|
| `kalshi-session-start` | Session-start ritual: stale-tip branch check → read handoff/kickoff/index → materialize `data/kalshi-bins` + `data/pyth-ticks` locally → verify accrual (newest timestamp, not existence). |
| `kalshi-backtest` | The mandatory backtest discipline: leakage gate → settle-window exclusion → per-cell never pooled → distributions/fingerprints never means → net-of-fee at maker AND taker. |
| `kalshi-roll` | Re-point Pyth front-month feeds at contract expiry (FEEDS dict + docstring in `pyth_collector.py`, sanity-stream, push to trunk; old-symbol history kept, roll boundary = separate cells). |

### Current docs
| file | what it is |
|------|-----------|
| `KALSHI_TRADING.md` | This index. |
| `CLAUDE.md` | The lean live operating doc (S83 split; the pre-split OD/crypto/physics master is archived verbatim in `CLAUDE_ARCHIVE_OD.md`). |
| `KALSHI_BUILD_SCOPE.md` | The Kalshi build scope / thesis. |
| `research/kalshi/FORECAST_AGENT_DESIGN_S87.md` | **[S87]** Greg's spec for the path-forecasting agent (the job, structure, self-improving method). |
| `research/kalshi/PATH_FORECAST_RESEARCH_S87.md` | **[S87]** Cited methods survey for the NYMEX hold-length signal (bucket-continuation baseline first, then event-time anchor + tracking, GBT, FPCA, HMM gate). |
| `research/kalshi/FORECAST_AGENT_DIRECTIVE_S88.md` | **[S88]** OPERATIONAL directive for the forecaster-building agent — operationalizes the S87 design + research into scoped marching orders: v1 = CL+NG level only (hubs deferred); target = event-time continuation curve (magnitude+shape+continuation, never level-RMSE); blind = chronological date-cut; NG cells temp/±2wk/weekday-type (`Mon | Tue-Thu ex-storage | Storage-day | Fri | Sat | Sun`); gas-weighted HDD/CDD temp feed as a v1 build (forecast-issue for conditioning, realized for labeling); 24-weeks-then-year sequence; hold-length EV-delta output. |
| `research/kalshi/EVENT_WEIGHT_STUDY.md` (+ `event_weight_study.json`, `source_map.json`) | Per-bucket event-weight study (weather→storage strong; storage-surprise→price null). |
| `SESSION_HANDOFF_2026-07-13_S89.md` (+ S88, S87, S86, S85, S84, S83, S82, S81, S80, S79, S78) | Session handoffs (S89 latest: durable RAW ingestion BUILT + tick corpus moved to AWS S3 — zero-filter MBP-10 writer verified, `pull_year_mbp10.py --dest s3://…`, full-raw year pulling to bucket `bento-568968024170-us-east-2-an`, split container/Greg-box, resumable). |
| `KICKOFF_2026-07-14_S90.md` (+ S89, S88, S87, S86, S84, S83, S82, S81, S80, S79) | Session kickoffs (S90 next: finish/verify the full-raw year on S3, then rework the scoring scaffolding to read the raw S3 tape — pre-processing moves to the trade-signal side). |
| `research/kalshi/AWS_INGEST_SETUP_S89.md` | **[S89]** AWS ingest runbook (bucket/IAM, `--dest s3://…` commands, split, resume, verify). |
| `research/kalshi/WEATHER_FORECAST_INTERFACE_S90.md` | **[S90]** The forecast->trade INTERFACE spec: what Greg's OD temp forecaster should EMIT (per `city x regime x lead` residual DISTRIBUTION `(value,sigma[,quantiles])` + pre-hoc regime + routing, on the real KXHIGH cities not KGJT/KDDC) so it plugs into the `(value,sigma)->bucket-prob` bridge (weather-prob markets) + `nws_temp_feed` forward HDD/CDD (NG driver). Forecaster HANDS OFF; this is the scoreboard/bridge contract. |

---

## OLD / COMPLETED KALSHI PIECES

Exploratory one-off studies whose conclusions are folded into the current docs (kept for provenance,
not on the live path).

| file | what it was |
|------|-------------|
| `research/kalshi/hist/eia_bucket_study.py` (+ `eia_bucket_results.json`) | EIA storage per-bucket surprise study → folded into EVENT_WEIGHT_STUDY.md. |
| `research/kalshi/hist/event_study.py` (+ `energy_dow_results.json`) | Energy day-of-week / event study. |
| `research/kalshi/hist/intraday_study.py` (+ `intraday_results.json`) | Release-day intraday quiet→spike→decay study. |
| `research/kalshi/hist/macro_study.py` (+ `macro_results.json`) | Macro-print reaction study. |
| `research/kalshi/hist/macro_bucket_study.py` (+ `macro_bucket_results.json`) | Macro per-bucket surprise study. |
| `research/kalshi/hist/natgas_season_study.py` (+ `natgas_season_results.json`) | 4-regime natgas seasonal (degree-day) split. |
| `research/kalshi/hist/natgas_weather_chain.py` (+ `natgas_weather_results.json`) | Weather→storage→price chain study. |

### Superseded approaches (concept-level, files may still carry a current piece)
- **Pooled hit-rate / averaged-signal evaluation** — superseded by the S80 EACH-TRADE-INDIVIDUALLY /
  per-cell rule. Any surviving code (e.g. the first pass in `release_signal_history.py`) is kept only
  for its still-current parts (settle filter, leakage gate).
- **Precise surprise→move regression** — deliberately NOT built (null); replaced by the merged
  architecture (release = catalyst/coarse size; book imbalance + exhaustion = direction/magnitude).

<!-- BEGIN GENERATED FILE INVENTORY - store.py docs --write -->

## COMPLETE FILE INVENTORY (generated - do not hand-edit)

Every tracked `research/kalshi/*.py`, from git, with the opening line of its docstring.
Regenerate with `python research/kalshi/store.py docs --write`. The curated sections
above carry the judgment (current vs superseded); this carries the completeness, so a
new tool cannot go unlisted. **529 files.**

- `adjudicate_g20_merge.py` — Adjudicate G20_MERGE_PROPOSAL_S108 against the live brain.
- `agent_frankie.py` — Frankie hybrid agent entry point.
- `archive_blind.py` — move the blind's posteriors out of the refine's filenames (S108).
- `batch_record.py` — the TRAVELER on the pallet (S110 turnaround memo 2.3, lot traceability).
- `blind_drift_trend.py` — Is the BLIND improving group over group? Forward-curve drift is the scoreboard."""
- `blind_input_audit.py` — What does the BLIND actually see? Audit the price-masked state G21 will be run on."""
- `blind_lean_decomp.py` — Is the blind's error a LEVEL bias (removable by shifting the curve) or SHAPE?
- `blind_legality.py` — can this play actually FIRE on a blind slice? (A-53.)
- `blind_score_nonpooled.py` — How much of the blind's error does the DRIFT metric cancel away? (S108, Greg's rule)
- `blind_state_audit.py` — Strict blind-wall audit for NG forecaster decision-state artifacts.
- `brain_audit.py` — the 82-play audit harness, IN THE REPO. (S111, fixing an S111 defect.)
- `brain_backfill.py` — put the reasoning, the evidence and the past instances INTO the brain, and
- `brain_conditions.py` — the CONDITIONS slot: vocabulary, verification, and curation harness.
- `brain_onedoc_fix_s115.py` — close the ONE-DOC holes in the brain. (S115, Greg's go.)
- `brain_schema.py` — give the brain a schema: typed, queryable, LOSSLESS. (S111, Greg's call)
- `brain_view.py` — serve the brain to a ROLE, and DECLARE what was withheld.
- `bshare_normalization_probe.py` — Is session_b_share structurally sub-0.50 because of how it is NORMALIZED?
- `bshare_restage_repair.py` — S109: repair session_b_share in states staged on the S108 leg path, WITHOUT a data plane.
- `bshare_threshold_study.py` — Does the 0.55 big_print_b_share threshold need to float?
- `bucket_continuation.py` — the BUCKET CONTINUATION TABLE (forecaster method #1, the honest baseline).
- `build_anchor_block.py` — S109: build the per-group ANCHOR BLOCK that gets handed to the specialists at spawn.
- `build_blind_state.py` — Build the canonical blind forecaster state from the existing decision_state path.
- `build_causal_slices.py` — S109 HOLE #11: build per-day CAUSAL SLICES of a blind state, so a specialist physically cannot
- `build_realized_forcings.py` — the VALIDATION TARGET for the GEFS forcing proxies (S114).
- `burn_hh_12m_event_ledger.py` — Build an event-level US48 gas-generation vs Henry Hub spot ledger.
- `burn_hh_living_365d.py` — Rebuild the active burn/Henry Hub dataset as the latest complete 365-day window.
- `cash_basis.py` — FEED G (family DEL): Henry Hub CASH vs front-futures-settle basis (S98 data gate).
- `characterize_turns.py` — run month_characterize.characterize_day on the pivotal turn days of the
- `chatgpt_brief_split.py` — generate one self-contained hand-off file per task from CHATGPT_BRIEF.
- `chatgpt_handoff.py` — GENERATE the ChatGPT hand-off that ships with the drop-in. (Registry A-25.)
- `coach_replay.py` — deterministic backtest of the ng_brain.json PLAYBOOK on the NG canary tape (S92 build).
- `coal_commitment.py` — measure the COAL COMMITMENT CYCLE from EIA-930 (S113, registry item A-31).
- `coal_prices.py` — accrue the EIA weekly coal basin spot prices. (Registry G-11.)
- `condition_audit.py` — can each brain condition CHANGE STATE? (report-only; never fixes anything)
- `condition_rate_experiment.py` — DERIVE the condition-health thresholds instead of asserting them.
- `consensus_poll.py` — accrue forward STREET CONSENSUS (forecast) + ACTUAL for the
- `continuous_rt.py` — the CONTINUOUS actual (RT) curve for the chronological walk (S95, Greg).
- `continuous_score.py` — score a blind forecast (grpN.json) against the continuous actual (gN_rt.json),
- `contract_structure.py` — the CONTRACT STRUCTURE feed for the NG intraday forecaster (S98).
- `coordinate_g15_mbo.py` — COORDINATOR for the G15 MBO 5-specialist refine (S103; guard + render S104).
- `cot_combined_feed.py` — CFTC COT FUTURES-AND-OPTIONS COMBINED positioning feed (DATA_GATE_S98 feed H).
- `cot_feed.py` — CFTC Commitments of Traders (COT) positioning feed for the NG intraday forecaster.
- `creds.py` — credential resolution, OUTSIDE the repo (S113, Greg: "no more scratchpad. It's in the sop").
- `data_registry.py` — Canonical DavisAI Markets data-point registry (S123 reconciliation).
- `databento_backfill.py` — TRUE-TICK historical NYMEX tape from Databento (S84).
- `databento_backfill_s115.py` — M-16 safe entry point for databento_backfill.py.
- `databento_live_smoke.py` — one-shot validation that the Databento LIVE plan is active (S99).
- `decision_trace.py` — BIND the reasoning to the decision it produced (S110, Greg's question:
- `defect_timeline.py` — which groups ran on a known-broken input, and was the EVIDENCE re-measured?
- `due_gate.py` — serve the REGISTERED FORWARD TESTS into a group's run, and refuse a silent pass.
- `eia_storage_compat.py` — Build the legacy national-storage compatibility store from EIA's public WNGSR workbook.
- `eia_surprise.py` — historical EIA release SURPRISE for the NYMEX-canary release windows (S86).
- `event_move_baseline.py` — the NYMEX-canary EVENT-MOVE baseline (S85).
- `extract_guesses.py` — the per-day guess-vs-actual scorecard for G3/4/5 survived in the brain's
- `failure_localization.py` — WHERE does the repair belong? (S114)
- `fast_tape.py` — fast trade-price path loader for the continuous NG walk (S95 rebuild of the lost
- `flow_calendar.py` — Flow calendar feed (family CAL) for the NG intraday forecaster -- DATA_GATE_S98 feed F.
- `flow_read.py` — the full NON-PRICE microstructure flow read for a session (S105 data doctrine).
- `forecast_contract.py` — Versioned output contract for the existing NG blind forecaster.
- `forecast_harness.py` — turn-key helpers for the self-growing forecaster LOOP (S92 build).
- `forward_curve.py` — the NYMEX forward-CURVE reader: backwardation/contango + prompt-vs-term conditioning
- `frankie_anchor_s118.py` — Materialize ephemeral G17/G18 anchor artifacts from declared group_config values.
- `frankie_authority_knowledge_plane_20260824.py` — Lossless authority-gated knowledge plane for the blind October Frankie run.
- `frankie_aws_stage_s126.py` — Fail-closed AWS staging preflight for the current Frankie build (S126).
- `frankie_backends.py` — Pluggable slow-path reasoning backends for Frankie.
- `frankie_block_availability_matrix_20260824.py` — Machine-readable causal availability policy for every canonical S135 block."""
- `frankie_bounded_3mo_parallel.py` — Bounded three-month Frankie orchestration for the full post-V4 program.
- `frankie_bridge_preflight_s118.py` — Preflight the namespace-local E->A->B weekend bridge path for S118 G18/G19 validation.
- `frankie_causal_capture_gate_s126.py` — S126 hard gate for causal-slice capture timestamps.
- `frankie_causal_operational_context_20260824.py` — Lossless causal snapshots of Frankie's complete canonical decision-state universe.
- `frankie_causal_runtime_tools_20260824.py` — Provider-callable causal state and append-only evidence receipts.
- `frankie_claude_code_temp.py` — Temporary Claude Code operator for the existing Frankie blind/refine framework.
- `frankie_cognition.py` — Deterministic cognitive contracts for Frankie.
- `frankie_cognitive_candidates.py` — Pure SHADOW candidate components derived from Frankie's cognitive top ten.
- `frankie_cognitive_experiments.py` — Matched-budget SHADOW experiment registry for Frankie's cognitive top ten."""
- `frankie_cognitive_p0_loops.py` — Bounded SHADOW-only cognitive mechanism plumbing.
- `frankie_core.py` — Deterministic core for Frankie, the hybrid market-research agent.
- `frankie_docs_sync_20260821.py` — ---
- `frankie_effects_s115.py` — Explicit S115 falsifier reports for A-68 retention and A-62 specialist priors.
- `frankie_engine.py` — Frankie orchestration: independent reasoning lanes, deterministic adjudication, AWS queue."""
- `frankie_evaluation_controls.py` — External evaluation controls for Frankie SHADOW candidates.
- `frankie_evolution.py` — Frankie's bounded harness-evolution and release-engineering layer.
- `frankie_forecaster_s115.py` — S115 forecaster harness for Frankie.
- `frankie_full_stack_launch_gate_audit_20260824.py` — Fail-closed audit for the 15 minimum Frankie full-stack October launch gates.
- `frankie_full_stack_paired_lane_orchestrator_20260824.py` — Fail-closed two-lane orchestration for the October Frankie experiment.
- `frankie_full_stack_provisional_combined_pipeline_20260824.py` — Execute every lawful provisional ability for the combined October lane.
- `frankie_full_stack_runtime_adapter_20260824.py` — Executable provider and durable-ledger adapter for one lawful Frankie prefix.
- `frankie_full_stack_runtime_contracts_20260824.py` — Additive runtime-plane contracts for the Frankie October full-stack bridge.
- `frankie_g24_refine_render_s128.py` — Render g24 full actual RT vs immutable S127 blind vs S128 causal refine."""
- `frankie_g24_run_s127.py` — S127 packet exporter for ChatGPT-operated Frankie on sanctioned g24.
- `frankie_g24_score_render_s127.py` — Score and render the fully-frozen ChatGPT-operated Frankie g24 blind run.
- `frankie_g3_reblind_s131.py` — S131 corrected mechanical re-blind input exporter for September 2025 G3.
- `frankie_g3_reblind_s131_runner.py` — Thin S131 entrypoint for a corrected G3 current-Frankie historical replay.
- `frankie_g3_s131_freeze.py` — Actual-free S131 blind freeze coordinator for current-Frankie G3 replay.
- `frankie_g3_s131_reconcile_score.py` — Reconcile S131 score against S129 on genuinely common definitions.
- `frankie_g3_s131_score.py` — Post-freeze S131 reveal/score for current-Frankie G3 replay.
- `frankie_g3_s132_dynamic_curve_rehearsal.py` — Assemble the S132 G3 event-driven curve rehearsal without reading target outcomes.
- `frankie_g3_s134_full_refine.py` — S134 full ten-day G3 unblinded refine-to-actual curve.
- `frankie_g3_s134_full_refine_runner.py` — S134 full-refine runner repairs for event-driven node time semantics.
- `frankie_g3_s134_refine_evidence.py` — S134 full-window G3 refine evidence extractor.
- `frankie_gdl_p0_controls.py` — Deterministic GDL-derived P0 controls for provisional Frankie research.
- `frankie_group_forecast_s118.py` — Run Frankie through the current NG five-specialist forecast path on walked groups.
- `frankie_hipporag_p0_retrieval.py` — Bounded HippoRAG-inspired retrieval-to-reader plumbing for Frankie.
- `frankie_historical_hydrate_s130.py` — S130 historical hydration utility for current Frankie decision states.
- `frankie_idempotency.py` — At-least-once delivery protection for Frankie evidence.
- `frankie_improve.py` — Bounded self-improvement for Frankie.
- `frankie_kitchen_sink_audit_s121.py` — S121 kitchen-sink causal completeness gate for Frankie blind recreations.
- `frankie_lane_aware_context_router_20260824.py` — Two-lane, identity-bound context routing for the blind October experiment.
- `frankie_lats_p0_search.py` — Bounded, callback-injected SHADOW LATS/MCTS plumbing for Frankie.
- `frankie_m13_recover_s126.py` — M-13 S126: recover the three stale Frankie stores without inventing replacement feeds.
- `frankie_market_p0_controls.py` — Fail-closed market/temporal evidence controls for Frankie.
- `frankie_meta_loop_agents_20260821.py` — Two isolated research/build-redteam lanes for the Frankie metacognitive sidecar."""
- `frankie_meta_loop_coordinator_s138.py` — Frankie coordinator integration for the bounded post-evidence metacognitive loop.
- `frankie_meta_loop_s138.py` — Bounded post-evidence metacognitive sidecar for Frankie and specialists A-E.
- `frankie_microstructure_p0_baselines.py` — Causal Level-I OFI and resiliency baselines for provisional Frankie research.
- `frankie_nova_optimizer.py` — Frankie-specific NOVA token optimizer and external-state harness.
- `frankie_october_knowledge_inventory_20260824.py` — Production source-spec builder for the corrected October knowledge plane.
- `frankie_p0_real_evidence_plan.py` — Immutable precommit contract for Frankie's six real P0 empirical receipts.
- `frankie_p0_registry.py` — Fail-closed inventory and readiness receipts for provisional Frankie P0 work.
- `frankie_packet_compact_s120.py` — Lossless transmission compaction for the S120 Frankie canary.
- `frankie_progress_compress_p0.py` — Bounded Progress & Compress SHADOW lifecycle for Frankie.
- `frankie_progress_lock_s122.py` — Machine-enforced S122 progress lock.
- `frankie_provider_knowledge_tools_20260824.py` — Bounded provider-callable access to the lawful Frankie knowledge plane.
- `__init__.py` — Controller-neutral raw-MBO benchmark contracts and restart utilities."""
- `a_clean_forecaster_prepare_20260828.py` — (no docstring summary)
- `a_clean_forecaster_replay_20260828.py` — (no docstring summary)
- `a_clean_forecaster_resume_20260828.py` — Verify the complete chain and every continuation/adapter sibling."""
- `a_clean_rt_replay_20260828.py` — (no docstring summary)
- `a_memory_member_first_recalculation_20260828.py` — A-memory member-first recalculation over the hash-bound native ledger.
- `a_memory_prepare_20260828.py` — (no docstring summary)
- `a_memory_rt_resume_20260828.py` — (no docstring summary)
- `a_memory_rt_resume_latest_20260828.py` — Resume the existing A-memory diagnostic replay from its latest closed checkpoint.
- `benchmark_checkpoint.py` — Restart-safe, controller-neutral checkpoints for the raw-MBO blind benchmark."""
- `build_a_memory_seed.py` — Build the A-memory SEED: every committed output of the past runs, hashed, labelled, UNVERIFIED.
- `chat_packet_seam.py` — Native raw-MBO contract boundary for the Chat-controlled Frankie benchmark arms.
- `corrected_a_arm_execution_gate_20260828.py` — Fail-closed execution and lock gates for corrected native-MBO A-arm runs."""
- `emit_frankie_spawn.py` — Fill every Frankie spawn slot BY LOOKUP and emit the exact prompt. The A-arm `spawn.py`.
- `fetch_frankie_ledgers.py` — Bring the exact ledgers into a session and PROVE they are the box's ledgers. D81.
- `mbo_resume_state.py` — Exact external snapshot/restore for the proven V4 native-MBO adapter.
- `native_a_arm_launch.py` — The A-arm launch path: gates, traversal, checkpoints, artifacts. One entrypoint.
- `native_absorption.py` — Section 4.8: absorption, withdrawal, and delivered pressure.
- `native_book_regime.py` — Section 4.2: the daily book regime companion, which did not run.
- `native_calculation_runner.py` — Sections 5 and 6: the seven artifact layers and the eight fail-closed gates.
- `native_candidate.py` — The A-arm candidate unit: a causally-detected dipole flow event (D66).
- `native_candidate_adapter.py` — Sections 4.10, 4.11 and 4.12 on the D66 candidate unit, as ONE vocabulary.
- `native_causal_stream.py` — The raw MBO delivered to the principal exactly as it would arrive in real time. D81.
- `native_clocks.py` — Section 4.5: formation, serialization, and observation clocks.
- `native_cross_section_agreement.py` — Two sections computing one estimand cannot both be right. The gate that says so.
- `native_detector_coverage.py` — Section 4.0b: detector coverage and rejection accounting - the denominator nobody carried.
- `native_dipole.py` — Section 4.12: dipole and opposing-pressure runway.
- `native_discovery.py` — Section 4.15: open-world cluster and new-structure discovery.
- `native_evidence_bundle.py` — Lossless native-MBO evidence ledger for the Chat-controlled Frankie arms.
- `native_exhaustion.py` — Section 4.10: exhaustion state, birth, persistence, and completion.
- `native_flow_substrate.py` — Section 4.0: the per-second flow and quote substrate, which fed everything and reported to nothing.
- `native_frankie_knowledge_registry.py` — Hash-bound, role-routed knowledge registry for native raw-MBO Frankie runs."""
- `native_full_capture_adapter.py` — Keep everything the V4 adapter computes and then throws away, without editing it.
- `native_group_adapters.py` — Construct section-4 domain objects from one F_LAST group (decision D53, 2026-08-29).
- `native_ingestion_layer_registry.py` — Versioned, fail-closed ingestion-layer gates for corrected Frankie A arms."""
- `native_key_alias.py` — Key-name aliasing for the averaged companion rows, and the measurement that scopes it.
- `native_knowledge_delivery.py` — The knowledge Frankie receives: classified from the inventory, bound to real files, receipted.
- `native_ladder.py` — Section 4.9: price-ladder topology.
- `native_layer_crosswalk.py` — The 99-layer crosswalk: registry layer -> producing code -> carrier -> delivery evidence.
- `native_lineage.py` — Section 4.13: chain families and D-depth lineages.
- `native_mbo_field_census.py` — Per-field census of the retained raw MBO, so the drop question can be answered at all.
- `native_mirror.py` — Section 4.4's one mechanically defined mirror key, and the matcher that uses it.
- `native_principal_outputs.py` — The principal's OUTPUT ledgers: the required set is derived, never counted in advance.
- `native_principal_outputs_draft_20260902.py` — The principal's OUTPUT ledgers: the registry's output layers plus one per contract section.
- `native_queue.py` — Section 4.6: queue position, priority, and order survival.
- `native_queue_adapter.py` — Section 4.6 from one F_LAST group: queue position, priority, order survival (D53).
- `native_recognition.py` — Section 4.11: prebirth prediction and continuous H+N recognition.
- `native_recurrence.py` — Section 4.14: recurrence, bursts, and transition graphs.
- `native_replay_driver.py` — The driver: walks the native stream once and feeds every calculation section.
- `native_replenishment.py` — Section 4.7: replenishment and liquidity resilience.
- `native_replenishment_adapter.py` — Section 4.7's OBSERVATION half: what tells `ReplenishmentCalculator` a level moved.
- `native_response.py` — Section 4.16: fixed causal future-response table.
- `native_roll20.py` — Feed inventory section 8: recreate the legacy per-second `roll20` from the native stream.
- `native_row_sink.py` — Append-only on-disk retention for the exact ledgers. Nothing is dropped; it moves.
- `native_rt_book.py` — A FIFO order book advanced one action at a time, so every read is the REAL-TIME view.
- `native_session.py` — Section 2 session segmentation and trading-day assignment (decision D6a, 2026-08-29).
- `native_staging.py` — The spawn contract: how Frankie is actually called, and how its output gets back.
- `native_stratum.py` — Section 3 of the native calculation contract, as a function rather than a sentence.
- `periodic_checkpointer.py` — Periodic save points for long native raw-MBO runs.
- `raw_mbo_source_manifest.py` — Hash-bound native raw-MBO source manifest and exact progress denominator.
- `rebind_registry_knowledge_layers.py` — Rebind the registry's knowledge layers from the inventory DOCUMENT to their KEEP FILES.
- `refresh_native_frankie_knowledge.py` — Regenerate promoted Frankie capsules and their hash-bound knowledge manifest."""
- `register_a_memory_knowledge.py` — Register the KEEP set in the knowledge sources spec BY SCRIPT, routed to the arm that runs.
- `render_frankie_report.py` — Render the principal's report FROM his findings, so the two cannot diverge.
- `render_source_inventory_addendum.py` — Render the DATED classification addendum to the 2026-08-24 source-file inventory.
- `report_ledger_size.py` — Which calculation is the size. The table that replaces an opinion.
- `__init__.py` — Focused tests for the native raw-MBO Chat benchmark seam."""
- `manifest_fixture.py` — Shared source-manifest fixture for the A-arm test suites.
- `outputs_bundle_fixture.py` — A lawful output bundle with a configurable identity, for the staging and read-back tests.
- `test_a_arm_launch_workflows.py` — T4: the A-arm launch workflows dispatch compute, and neither can fire the box by push.
- `test_a_clean_forecaster_resume_latest.py` — (no docstring summary)
- `test_a_memory_member_first_recalculation.py` — (no docstring summary)
- `test_a_memory_rt_resume_latest.py` — (no docstring summary)
- `test_box_volume_rescue_workflow.py` — Does the box get its disk back after a failure at every point of the rescue?
- `test_build_a_memory_seed.py` — The A-memory seed: every committed output of the past runs, hashed, provenance-labelled, UNVERIFIED.
- `test_chat_packet_seam.py` — (no docstring summary)
- `test_corrected_a_arm_execution_gate.py` — (no docstring summary)
- `test_emit_frankie_spawn.py` — The stop rule, and the hash check that makes the mission uneditable mid-flight.
- `test_fetch_frankie_ledgers.py` — The ledgers reach the session and are proven to be the ledgers the box reconciled.
- `test_frankie_ledger_delivery_workflow.py` — D57 on the delivery workflow: parse the YAML, `bash -n` every run block, compile any
- `test_knowledge_delivery_receipt.py` — The knowledge delivery receipt, produced FROM the existing pipeline, consumed by the crosswalk.
- `test_native_a_arm_launch.py` — T2/T3/T5: the launch path gates, traverses, checkpoints and finalizes.
- `test_native_absorption.py` — Tests for section 4.8 absorption, withdrawal, and delivered pressure."""
- `test_native_book_regime.py` — Section 4.2, which did not run at all on the delivered artifact.
- `test_native_calculation_runner.py` — Tests for sections 5 and 6: artifact layers and fail-closed acceptance gates."""
- `test_native_candidate.py` — The causal candidate detector: it may never see past the second it is judging.
- `test_native_candidate_adapter.py` — The adapter that drives 4.10, 4.11 and 4.12 - which had no test file at all.
- `test_native_causal_stream.py` — The raw MBO reaches the principal the way it arrives in real time, and nothing else.
- `test_native_clocks.py` — Tests for section 4.5 formation, serialization, and observation clocks."""
- `test_native_cross_section_agreement.py` — The horizontal gate, tested against the defect that got past all eight vertical ones.
- `test_native_detector_coverage.py` — Section 4.0b: the accounting for the search that creates the candidate population.
- `test_native_dipole.py` — Tests for section 4.12 dipole and opposing-pressure runway."""
- `test_native_discovery.py` — Tests for section 4.15 open-world cluster and new-structure discovery."""
- `test_native_evidence_bundle.py` — (no docstring summary)
- `test_native_exhaustion.py` — Tests for section 4.10 exhaustion runways."""
- `test_native_flow_substrate.py` — Section 4.0, the per-second flow and quote substrate.
- `test_native_frankie_knowledge_registry.py` — The hash-bound knowledge manifest: validation, the model-visible context, and the knowledge-use gate.
- `test_native_full_capture_adapter.py` — Tests for the full-capture adapter (D60).
- `test_native_group_adapters.py` — Tests for the section-4 group adapters (D53: the F_LAST group is the unit).
- `test_native_ingestion_layer_registry.py` — (no docstring summary)
- `test_native_key_alias.py` — Tests for the key-name aliaser: it must be lossless, stable and self-describing.
- `test_native_knowledge_delivery.py` — The knowledge Frankie receives is classified from the inventory, bound to real files, receipted.
- `test_native_ladder.py` — Tests for section 4.9 price-ladder topology."""
- `test_native_layer_crosswalk.py` — The 99-layer crosswalk: every registry layer to the code that produces it and the carrier
- `test_native_lineage.py` — Tests for section 4.13 chain families and D-depth lineages."""
- `test_native_mbo_field_census.py` — The field census measures the retained raw MBO; it never judges it."""
- `test_native_mirror.py` — Section 4.4's mirror key and matcher: one mechanical definition, one implementation.
- `test_native_principal_outputs.py` — The principal's OUTPUT ledgers: the required set is DERIVED, the chain is append-only.
- `test_native_queue.py` — Tests for section 4.6 queue position, priority, and order survival."""
- `test_native_queue_adapter.py` — Tests for the section-4.6 queue adapter (D53: the F_LAST group is the unit).
- `test_native_recognition.py` — Tests for section 4.11 prebirth prediction and continuous H+N recognition."""
- `test_native_recurrence.py` — Tests for section 4.14 recurrence, bursts, and transition graphs."""
- `test_native_replay_driver.py` — Tests for the traversal driver.
- `test_native_replenishment.py` — Tests for section 4.7 replenishment and liquidity resilience."""
- `test_native_replenishment_adapter.py` — Tests for section 4.7's observation half.
- `test_native_response.py` — Tests for section 4.16 fixed causal future-response table."""
- `test_native_roll20.py` — Section 8 of the feed inventory: recreate the legacy per-second roll20 from native.
- `test_native_row_sink.py` — Byte attribution on the exact ledgers: which calculation is the size.
- `test_native_row_sink_differential.py` — B, proved rather than claimed: streaming the exact ledgers changes no science.
- `test_native_rt_book.py` — Tests for the real-time replay book (Greg: "We should see it like it would be seen in rt").
- `test_native_rt_book_differential.py` — Differential tests: `ReplayBook` must MIRROR `InstrumentBook` on every book mutation.
- `test_native_session.py` — Tests for section 2 continuity segmentation and trading-day assignment (D6a).
- `test_native_staging.py` — The spawn contract: how Frankie is actually called.
- `test_native_staging_handoff.py` — S121 slice 4: the V2 workmode handoff machinery is re-fed from a VALIDATED output bundle.
- `test_native_stratum.py` — Tests for the parallel-view rule as enforced structure."""
- `test_open_world_growth.py` — The carried vocabulary is where discovery starts, not what it is validated against.
- `test_periodic_checkpointer.py` — Tests for periodic save points on long native raw-MBO runs."""
- `test_raw_mbo_source_manifest_roles.py` — Tests for the single-role roster and the identity/manifest hash split."""
- `test_refresh_native_frankie_knowledge.py` — (no docstring summary)
- `test_register_a_memory_knowledge.py` — The KEEP set reaches the knowledge manifest BY SCRIPT, routed to the one arm that runs.
- `test_render_frankie_report.py` — The principal's report is a RENDER of his findings, never a separately authored document.
- `test_report_ledger_size.py` — Turning a finished run into the table the drop decision needs.
- `test_verify_ledger_size_witness.py` — What a witness must refuse to say.
- `verify_ledger_size_witness.py` — The independent witness for a run's size, because the sink counting its own writes is not one.
- `frankie_reflect.py` — Scheduled reflection over resolved Frankie evidence.
- `frankie_reflect_runner.py` — Nightly bounded reflection runner for Frankie; generates proposals, never applies them."""
- `frankie_render_s115.py` — A-59: NOOA-style render target over the existing canonical store.
- `frankie_role_context_profiles_20260824.py` — Validated native-context profiles for the uniform two-Frankie build."""
- `frankie_s114_separation_metadata_s126.py` — S126 metadata-only repair for the already-verified S114 GEFS forcing store.
- `frankie_s115.py` — S115 Frankie contract layer.
- `frankie_s115_status.py` — Report readiness against FRANKIE_BUILD_BRIEF_S115.md without pretending missing data is ready."""
- `frankie_s118_redo.py` — S118/S120 clean-redo guards for the Frankie validation canary boundary.
- `frankie_s121_curve_restore.py` — Frankie S121: restore the established kitchen-sink blind curve contract.
- `frankie_s128_contract_repairs.py` — S128 narrow serving/contract repairs learned from the g24 blind+refine run.
- `frankie_s128_decision_state.py` — S128 decision-state entrypoint with contract-only serving repairs installed."""
- `frankie_s128_handoff.py` — S128 HE24->HE1 handoff entrypoint with typed forecast-vs-realized exit state."""
- `frankie_s132_dynamic_curve.py` — S132 event-driven curve contract for Frankie.
- `frankie_s132_runtime.py` — Canonical S132 runtime install seam.
- `frankie_s133_reasoning_runtime.py` — S133 reasoning-authority runtime seam.
- `frankie_s135_current_runtime.py` — S135 canonical CURRENT-FRANKIE runtime seam.
- `frankie_s135_date_driver.py` — Permanent thin driver for S135 date-window ChatGPT sessions.
- `frankie_s135_date_render.py` — Render a completed S135 date session from its resolved S136 date plan.
- `frankie_s135_date_session.py` — Date-driven ChatGPT transport for the existing S135 CURRENT-FRANKIE state machine.
- `frankie_s135_group_runner.py` — Canonical S135 sequential CURRENT-FRANKIE group runner.
- `frankie_s135_handoff.py` — S135 current HE24->HE1 handoff wrapper.
- `frankie_s135_preflight.py` — Fail-closed S135 preflight for every new CURRENT-FRANKIE group run.
- `frankie_s135_specialist_authority.py` — S135 specialist authority/sequencing contracts.
- `frankie_s135_substrate_descriptor_20260824.py` — Seal and validate the complete restore_substrate S135 data-plane staging receipt."""
- `frankie_s136_date_plan.py` — Resolve date intent to one exact, already-declared Frankie historical window.
- `frankie_s136_date_refine_prep.py` — Prepare a post-reveal REFINE packet for a completed S135 date session.
- `frankie_s136_state_stage.py` — Targeted S136 state-plane staging for date-driven Frankie runs.
- `frankie_s136_target_brain_wall.py` — S136 target-session brain wall for CURRENT-FRANKIE historical learning runs.
- `frankie_s137_cognitive_experiment_runner.py` — Paired freeze-before-reveal runner for Frankie's ten S137 SHADOW arms.
- `frankie_s137_cognitive_runtime.py` — S137 SHADOW-only cognitive-candidate wrapper for CURRENT FRANKIE S135.
- `frankie_source_inventory_cross_reference_20260824.py` — Cross-reference the pushed 148-path Frankie inventory against live wiring.
- `frankie_specialist_parity_s126.py` — S126 specialist parity guard for the current Frankie packet.
- `frankie_stage_group_s128.py` — S128 staging wrapper: original stage_group with repaired decision-state construction.
- `frankie_storage_preflight.py` — Frankie storage preflight: build and verify the weekly EIA storage stores with no API key.
- `frankie_target_cell_manifest_s122.py` — Compile and validate the exact target-cell kitchen-sink manifest for Frankie.
- `frankie_temporal_graph_p0_adapter.py` — Causal batch-size-1 temporal-graph adapter plumbing for Frankie.
- `frankie_temporal_p0_controls.py` — Fail-closed temporal P0 controls for provisional Frankie research.
- `frankie_two_group_run_s118.py` — Reproducible S118 two-group Frankie validation entrypoint.
- `frankie_two_group_smoke_s118.py` — S118 matched-artifact smoke check for G15/G16.
- `frankie_v4_authority_runtime_validation_20260824.py` — Fail-closed runtime receipt for every governing H module and I record.
- `frankie_v4_follow_on_agents_20260821.py` — Isolated follow-on build-agent receipts for unfinished V4 preparation work.
- `frankie_v4_governing_runtime_execution_20260824.py` — Execute governing H contracts on each corrected marked prefix.
- `frankie_validation_s115.py` — S115 architecture validation for Frankie (A-67, A-69, A-42/FJ-1 adapter).
- `free_ng_data_collector.py` — Collect free public drivers for Henry Hub NG and CME event-contract research.
- `freeze_risk_feed.py` — FEED E (S100, DATA_GATE_S98) - freeze-off risk: producing-basin forecast MIN temps, cycle as-of.
- `futures_kalshi_lag.py` — measure the LAG between the futures market (the price-discovery venue) and
- `g15_mbo_engine.py` — G15 MBO causal REFINE engine (S103, ChatGPT audit branch).
- `g17_actual.py` — build the G17 two-leg ACTUAL curve from per-contract MBO trades.
- `g17_coordinate.py` — COORDINATOR for the G17 5-specialist BLIND panel (S105).
- `g17_mbo_engine.py` — G17 MBO causal evidence for the refine (S105). Same extraction as
- `g17_refine_coordinate.py` — COORDINATOR for the G17 MBO 5-specialist REFINE (round 1, S105).
- `gas_call_residual.py` — S109 P0.7: the GAS CALL RESIDUAL - weather-driven load net of what renewables and baseload absorb.
- `gefs_ensemble.py` — the GEFS ensemble through OUR gas-weighted degree days, to a DENSITY. (G-5.)
- `gefs_validate.py` — does the GEFS forward forcing proxy TRACK realized US48 output? (S114, G-5.)
- `grid_stack.py` — FEED Q (family D/power): EIA-930 grid stack - daily demand, day-ahead demand
- `group_actual.py` — build ANY group's two-leg ACTUAL curve from per-contract MBO trades, config-driven.
- `group_config.py` — per-group turnkey config for the NG forecaster walk (S105).
- `group_coordinate_blind.py` — GENERIC blind coordinator (S105), config-driven:
- `group_coordinate_refine.py` — GENERIC refine coordinator (S105), config-driven:
- `group_he24_he1_handoff.py` — GENERIC HE24->HE1 day-boundary handoff chain (S105). Config-driven:
- `group_mbo_engine.py` — GENERIC MBO causal evidence engine (S105). Config-driven off group_config;
- `he24_he1_handoff.py` — build the HE24->HE1 day-boundary handoff chain for the G15 MBO refine (S103).
- `eia_bucket_study.py` — CONDITIONAL per-bucket event study (founder methodology correction).
- `event_study.py` — Event-weight study: measure how much recurring scheduled releases move the
- `intraday_study.py` — Intraday release-window event study using Yahoo 60m futures bars (~730d).
- `macro_bucket_study.py` — PHASE-2 / WEAK-PROXY macro bucketing (NFP). LABELLED WEAK: the real consensus is
- `macro_study.py` — Macro event-weight study. Explicit release-date lists (FOMC) + derived (NFP
- `natgas_season_study.py` — (1) REGIME-SPLIT natgas bucketing - DATA-DISCOVERED regimes, NOT calendar months.
- `natgas_weather_chain.py` — (2) WEATHER-DRIVER CHAIN: weather -> heating/cooling demand -> storage draw/build -> price.
- `kalshi_auth.py` — the Kalshi signed-request client (G0 closure, S110). CLASSIC + margin lanes.
- `kalshi_collector.py` — public-API snapshot collector for Kalshi prediction markets.
- `kalshi_coupling_adapter.py` — feed Kalshi JSONL bins into news_coupling_research.py.
- `kalshi_fill_model.py` — FEED M part 2 (S100, DATA_GATE_S98) - the Kalshi fill/fee model. Execution economics ONLY;
- `kalshi_history.py` — pull HISTORICAL Kalshi trade + candlestick data around past scheduled releases.
- `kalshi_ng_backfill.py` — FEED L (DATA_GATE_S98): Kalshi-side NG market data - inventory / backfill.
- `kalshi_paper_ledger.py` — G1 of the paper-trading dock (S110 turnaround memo Part 3).
- `kalshi_rule_canonicalizer.py` — Canonicalize Kalshi market rules and find duplicated contingent claims.
- `kalshi_score.py` — settlement + scoring harness for Kalshi contracts (S78 Option A).
- `kalshi_weather_forecast.py` — wire the OD-weather storage-NUMBER forecaster into the kalshi_score
- `lag_execution_map.py` — FEED M part 1 (S100, DATA_GATE_S98) - the lag's NG-specific EXECUTION SHAPE on the KXNATGASD
- `lag_exploit_backtest.py` — turn the MEASURED futures->Kalshi lag into a MEASURED, net-of-toll edge.
- `lag_join.py` — the FUTURES->KALSHI lag join (realized-EV of the echo, net-of-fee), two modes.
- `level_hit_dataset.py` — the PER-TRADE LEVEL-HIT dataset (S82; the continuation predictor).
- `live_dipole_update.py` — Apply the existing live dipole as a likelihood update to a locked blind prior.
- `merge_gate.py` — unattended adjudication for SOP gates 2 and 3. (Registry M-3 + A-7.)
- `merge_perday.py` — S109: assemble per-DAY blind posteriors into the per-SPECIALIST shape the coordinator reads.
- `model_disagreement.py` — FEED C (DATA_GATE_S98): MODEL DISAGREEMENT as a forecast-uncertainty proxy.
- `month_characterize.py` — per-(commodity, MONTH) CONTINUOUS-tape characterizer. The per-agent TOOL the S88
- `mos_cycle_feed.py` — FEED A PHASE 1 (S100, DATA_GATE_S98) - cycle-level MOS as-of, hour resolution.
- `ng_exhaustion_frankie_causal_data_plane_20260824.py` — Protected continuous causal data-plane contracts for the Frankie V4 bridge.
- `ng_exhaustion_frankie_continuous_stream_20260824.py` — Continuous V4 replay-envelope to protected Frankie causal-second stream.
- `ng_exhaustion_frankie_fullstack_october_20260824.py` — Fresh full-stack October Frankie runner.
- `ng_exhaustion_frankie_post_freeze_paired_evaluation_20260824.py` — Post-freeze paired evaluation for the October Frankie full-stack experiment.
- `ng_exhaustion_october_frankie_v4_bridge_20260824.py` — Blind raw-MBO -> V4-native -> GPT-5.6 Sol canary bridge.
- `ng_exhaustion_step1_3mo_completion_gate.py` — Fail-closed completion gate for the exact Sep-Nov 2021 bounded Step-1 run.
- `ng_exhaustion_step1_completion_gate.py` — Pure fail-closed gates shared by Step-1 launch/completion verification."""
- `ng_exhaustion_step1_recovery.py` — Prepare an exact no-raw-replay finalization contract for Step-1."""
- `ng_exhaustion_step1_to_v4_registry.py` — Freeze verified Step-1 outputs as non-result-bearing V4 pilot inputs."""
- `ng_exhaustion_two_day_step1_transfer_verify_20260824.py` — Fail-closed receipt artifact verification for the two-day transfer recovery."""
- `ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.py` — Run exactly Real-Time Frankie then Forecaster Frankie on the prior Oct-4/5 surface.
- `ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py` — Freeze sequential Work-mode Frankie outputs without provider/API receipts."""
- `ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py` — Build blind-safe Work-mode packets for the exact Oct-4/5 two-Frankie run.
- `ng_exhaustion_v4_adapter_integration.py` — End-to-end isolated V4 adapter integration contract.
- `ng_exhaustion_v4_causal_clock.py` — Isolated V4 causal discovery-clock contract.
- `ng_exhaustion_v4_causal_entry_adapter.py` — Isolated bridge from a causal discovery receipt to the frozen runway engine.
- `ng_exhaustion_v4_detector_intensity.py` — Detector-intensity semantic boundary for NG Exhaustion V4.
- `ng_exhaustion_v4_detector_intensity_semantics.py` — Fail-closed detector-intensity semantic resolver for NG Exhaustion V4.
- `ng_exhaustion_v4_end_to_end_adapter.py` — Isolated end-to-end NG Exhaustion V4 adapter pipeline.
- `ng_exhaustion_v4_exact_candidate_freeze.py` — Exact-candidate engineering regression/freeze contract for NG Exhaustion V4.
- `ng_exhaustion_v4_gate_verifier.py` — Recompute the nine V4 clean-source prelaunch gates from typed artifacts.
- `ng_exhaustion_v4_history_support.py` — Provenance/coverage contracts for additive V4 outside chronology.
- `ng_exhaustion_v4_lock_outcome.py` — Complete lock-outcome recomputation for the isolated V4 ledger.
- `ng_exhaustion_v4_mechanics.py` — Isolated, fail-closed mechanics for NG Exhaustion V4.
- `ng_exhaustion_v4_pilot_chunk_guard.py` — Fail-closed pilot-manifest / D-year-chunk guard for NG Exhaustion V4.
- `ng_exhaustion_v4_pilot_chunk_guardrail.py` — Fail-closed V4 pilot manifest and D/year chunk guardrail.
- `ng_exhaustion_v4_state_assembler.py` — Causal, missingness-safe immutable state assembler for NG Exhaustion V4.
- `ng_exhaustion_v4_unified_runtime.py` — Single-registry / single-engine / single-reconciler V4 runtime contract.
- `ng_historical_manifest.py` — Manifest contract for historical NG L1/trades and MBO replay.
- `ng_historical_replay.py` — Deterministic G15 L1/trades + MBO replay through the live operator.
- `ng_live_collector.py` — Durable live prompt-Henry-Hub collector, isolated from historical jobs.
- `ng_live_exhaustion_collector.py` — Drop-in NG live collector entrypoint with the exact exhaustion roll-20 tap.
- `ng_live_operator.py` — Causal NG live onset, divergence, exhaustion, and MBO queue telemetry.
- `ng_live_recover.py` — Best-effort upload of live NG DBN files left by an abrupt prior exit.
- `ng_live_watchdog.py` — Restart the live NG collector when its process or heartbeat becomes stale.
- `ng_mbo_5y_job_consolidator.py` — Fence and consolidate Databento NG.v.0 MBO batch jobs for the approved 5Y archive.
- `ng_mbo_5y_native_to_s3.py` — Lossless five-year NG.v.0 MBO batch acquisition -> existing Markets AWS S3 bucket.
- `ng_mbo_5y_native_to_s3_safe.py` — Compatibility guard for the 5Y NG MBO acquisition.
- `ng_mbo_5y_s3_compact_audit.py` — Read-only expected-vs-actual audit for the approved five-year NG.v.0 MBO archive.
- `ng_paper_loop.py` — G2 of the paper-trading dock (S110): the DAILY PAPER LOOP skeleton.
- `ng_rt_feature_state.py` — Causal feature-state contract for the NG Real-Time Refine Agent.
- `ngwu_feed.py` — FEED N (family D/supply): the EIA weekly natural gas S/D balance, from the
- `nrc_reactor_collector.py` — Collect NRC daily commercial reactor power status for NG power-burn research.
- `nuclear_outages.py` — FEED R arm 1 (family D+S): U.S. nuclear capacity offline, daily (S99).
- `nws_temp_feed.py` — the gas-demand TEMPERATURE feed for the NG path forecaster (S88, Greg's directive).
- `options_iv_surface.py` — FEED I phase ii: the NG settle-IV surface (OPTIONS_COACH_RESEARCH_S100.1 E2 items 1-3).
- `options_md_measures.py` — FEED I phase MD: the free measurement program on the settle-IV surface
- `options_replay.py` — E4: the settle-IV replay of the walked winter (OPTIONS_COACH_RESEARCH_S100.1).
- `options_surface.py` — FEED I phase i (family DEL/P): NG options OI-by-strike pin map + opex clock (S99).
- `path_contract.py` — is the emitted curve actually a full-session curve? (S114)
- `per_event.py` — the reporting contract for any measurement on this desk.
- `plant_calendar.py` — the plant's clock and work cycle. RULES, not a loaded table.
- `plant_status.py` — THE ANDON BOARD (S110, turnaround memo 2.4). One command, no arguments.
- `platform_sync.py` — the ONE door between local cache and the S3 data plane (S98 M2, AWS_PLATFORM_S98.md).
- `precache_window.py` — pre-decode every NG continuous day in a date window to npz (via fast_tape), so the
- `promotion_review.py` — the play promotion/retirement REVIEW (S110 memo 1.4). Reporter only.
- `proper_scoring.py` — Proper scoring for the existing NG blind forecast artifacts.
- `pull_july_2026.py` — One-off ops (S100): pull the never-pulled July 1-18 2026 NG tape (year-pull boundary gap) into
- `pull_july_2026_cl.py` — One-off ops (S100): pull the never-pulled July 2026 CL tape (S101; CL year store ends 20260630) (year-pull boundary gap) into
- `pull_percontract_mbo.py` — pull RAW per-contract MBO (.dbn.zst, one file/day) for a specific NG monthly
- `pull_year_mbp10.py` — pull a YEAR (or any month range) of continuous MBP-10 for CL+NG, month by month,
- `pyth_backfill.py` — HISTORICAL per-second NYMEX tape from Pyth Hermes (S84).
- `pyth_collector.py` — sub-second tick collector for the NYMEX/ICE futures Kalshi settles on, via Pyth Hermes.
- `redownload_mondays.py` — One-off ops: re-download every corrupt Monday stub in nymex_cont/ (all Mondays were truncated to
- `release_book_signal.py` — the S80 release-triggered BOOK signal (the MERGED architecture).
- `release_signal_history.py` — test the S80 release-triggered signal on HISTORICAL Kalshi trade flow.
- `render_util.py` — the ONE implementation of the walk's render rules (S107).
- `replay_g15_mbo.py` — thin DRIVER (S103) that feeds historical NG MBO records through the EXISTING
- `restore_substrate.py` — rebuild a fresh container's local data plane in ONE command (S107).
- `roll_adjust.py` — contract-roll back-adjustment for the continuous NG.v.0 series (S95, Greg).
- `run_g11_fingerprints_s98.py` — DATA_GATE_S98 Tier 1 item 1: G11 per-leg fingerprints on NG.n.0.
- `run_g12_rt_s101.py` — build the G12 ACTUALS (rt.json) + continuous render on the walked NG.n.0 basis.
- `run_g13_rt_s101.py` — build the G13 ACTUALS (rt.json) + continuous render on the walked NG.n.0 basis.
- `run_g14_rt_s102.py` — build the G14 ACTUALS (rt.json) + continuous render on the DECIDED basis.
- `run_g15_rt_s102.py` — G15 ACTUALS + render on the KALSHI-UNDERLYING basis (Greg's rule).
- `session_bootstrap.py` — one command to take a fresh container from empty to ready (S108).
- `solar_calendar.py` — FEED P (S98, Greg 2026-07-20: "do we have sun up/sun down time in our feed").
- `spawn.py` — fill every SOP slot BY LOOKUP and emit the exact prompt. (Registry A-7.)
- `squeeze_watch_live_repair.py` — S109 fix phase, findings f1 and f3 (state auditor, G22): squeeze_watch's "live" limbs are frozen.
- `stage_group.py` — ONE-COMMAND staging so a group is completely ready (S105):
- `standdown_ledger.py` — the SAVES. Every time a specialist talked itself out of firing a play, with
- `state_health.py` — the stage-time COMPLETENESS ASSERTION (S107).
- `state_repair_s110.py` — the S110 fix phase for the G23 pre-blind state audit (findings f1/f3/f4/f5).
- `state_repair_s110b.py` — A11.1: the CDD-LADDER ARTIFACT repair (S110 merge addendum; Greg's go
- `steo_vintage.py` — FEED T (family D/balance): STEO monthly VINTAGES - the frozen as-of NG balance (S99).
- `storage_consensus.py` — weekly EIA natural gas storage analyst consensus as a decision-state input.
- `storage_regional.py` — REGIONAL NG working-gas storage as a decision-state INPUT (S97).
- `storage_restage_repair.py` — graft the CORRECT storage lane onto a committed group state. (S115.)
- `storage_vintage.py` — AS-FIRST-PRINTED vs CURRENT-VINTAGE EIA weekly storage (DATA_GATE_S98 feed K).
- `store.py` — ONE STORE, GENERATED VIEWS. (Registry A-7.)
- `system_inventory.py` — Durable DavisAI Markets / Frankie system inventory.
- `tape_reconcile.py` — assert tape_conditions is measuring THE CONTRACT WE ARE FORECASTING (S108).
- `test_agent_frankie.py` — (no docstring summary)
- `test_databento_s115.py` — (no docstring summary)
- `test_frankie_authority_knowledge_plane_20260824.py` — (no docstring summary)
- `test_frankie_aws_stage_s126.py` — (no docstring summary)
- `test_frankie_bounded_3mo_parallel.py` — (no docstring summary)
- `test_frankie_causal_capture_gate_s126.py` — (no docstring summary)
- `test_frankie_causal_operational_context_20260824.py` — (no docstring summary)
- `test_frankie_causal_runtime_tools_20260824.py` — (no docstring summary)
- `test_frankie_claude_code_temp.py` — (no docstring summary)
- `test_frankie_cognition.py` — (no docstring summary)
- `test_frankie_cognitive_p0_loops.py` — (no docstring summary)
- `test_frankie_data_registry_s123.py` — (no docstring summary)
- `test_frankie_effects_s115.py` — (no docstring summary)
- `test_frankie_evaluation_controls.py` — (no docstring summary)
- `test_frankie_evolution.py` — (no docstring summary)
- `test_frankie_full_stack_launch_gate_audit_20260824.py` — (no docstring summary)
- `test_frankie_full_stack_paired_lane_orchestrator_20260824.py` — (no docstring summary)
- `test_frankie_full_stack_provisional_combined_pipeline_20260824.py` — (no docstring summary)
- `test_frankie_full_stack_runtime_adapter_20260824.py` — (no docstring summary)
- `test_frankie_full_stack_runtime_contracts_20260824.py` — (no docstring summary)
- `test_frankie_g24_run_s127.py` — (no docstring summary)
- `test_frankie_gdl_p0_controls.py` — (no docstring summary)
- `test_frankie_hipporag_p0_retrieval.py` — (no docstring summary)
- `test_frankie_idempotency.py` — (no docstring summary)
- `test_frankie_kitchen_sink_s121.py` — (no docstring summary)
- `test_frankie_lane_aware_context_router_20260824.py` — (no docstring summary)
- `test_frankie_lats_p0_search.py` — (no docstring summary)
- `test_frankie_m13_recover_s126.py` — (no docstring summary)
- `test_frankie_market_p0_controls.py` — (no docstring summary)
- `test_frankie_meta_loop_coordinator_s138.py` — (no docstring summary)
- `test_frankie_meta_loop_s138.py` — (no docstring summary)
- `test_frankie_microstructure_p0_baselines.py` — (no docstring summary)
- `test_frankie_nova_optimizer.py` — (no docstring summary)
- `test_frankie_october_knowledge_inventory_20260824.py` — (no docstring summary)
- `test_frankie_p0_real_evidence_plan.py` — (no docstring summary)
- `test_frankie_p0_registry.py` — (no docstring summary)
- `test_frankie_progress_compress_p0.py` — (no docstring summary)
- `test_frankie_progress_lock_s122.py` — (no docstring summary)
- `test_frankie_provider_knowledge_tools_20260824.py` — (no docstring summary)
- `test_frankie_role_context_profiles_20260824.py` — (no docstring summary)
- `test_frankie_s114_separation_metadata_s126.py` — (no docstring summary)
- `test_frankie_s115.py` — (no docstring summary)
- `test_frankie_s120_canary_boundary.py` — (no docstring summary)
- `test_frankie_s120_packet_compact.py` — (no docstring summary)
- `test_frankie_s121_curve_restore.py` — (no docstring summary)
- `test_frankie_s128_contract_repairs.py` — (no docstring summary)
- `test_frankie_s137_cognitive_experiment_runner.py` — (no docstring summary)
- `test_frankie_s137_cognitive_runtime.py` — (no docstring summary)
- `test_frankie_source_inventory_cross_reference_20260824.py` — (no docstring summary)
- `test_frankie_specialist_parity_s126.py` — (no docstring summary)
- `test_frankie_target_cell_manifest_s122.py` — (no docstring summary)
- `test_frankie_temporal_graph_p0_adapter.py` — (no docstring summary)
- `test_frankie_temporal_p0_controls.py` — (no docstring summary)
- `test_frankie_v4_authority_runtime_validation_20260824.py` — (no docstring summary)
- `test_frankie_v4_follow_on_protected_baseline.py` — (no docstring summary)
- `test_ng_exhaustion_frankie_causal_data_plane_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_frankie_continuous_stream_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_frankie_fullstack_october_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_frankie_post_freeze_paired_evaluation_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_october_frankie_v4_bridge_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_step1_completion_gate.py` — (no docstring summary)
- `test_ng_exhaustion_step1_recovery.py` — (no docstring summary)
- `test_ng_exhaustion_step1_recovery_workflow.py` — (no docstring summary)
- `test_ng_exhaustion_step1_to_v4_registry.py` — (no docstring summary)
- `test_ng_exhaustion_step1_to_v4_workflow.py` — (no docstring summary)
- `test_ng_exhaustion_two_day_step1_transfer_recovery_20260824.py` — (no docstring summary)
- `test_ng_exhaustion_v4_adapter_integration.py` — (no docstring summary)
- `test_ng_exhaustion_v4_causal_clock.py` — (no docstring summary)
- `test_ng_exhaustion_v4_causal_entry_adapter.py` — (no docstring summary)
- `test_ng_exhaustion_v4_detector_intensity.py` — (no docstring summary)
- `test_ng_exhaustion_v4_detector_intensity_semantics.py` — (no docstring summary)
- `test_ng_exhaustion_v4_end_to_end_adapter.py` — (no docstring summary)
- `test_ng_exhaustion_v4_exact_candidate_freeze.py` — (no docstring summary)
- `test_ng_exhaustion_v4_gate_verifier.py` — (no docstring summary)
- `test_ng_exhaustion_v4_history_support.py` — (no docstring summary)
- `test_ng_exhaustion_v4_lock_outcome.py` — (no docstring summary)
- `test_ng_exhaustion_v4_mechanics.py` — (no docstring summary)
- `test_ng_exhaustion_v4_pilot_chunk_guard.py` — (no docstring summary)
- `test_ng_exhaustion_v4_pilot_chunk_guardrail.py` — (no docstring summary)
- `test_ng_exhaustion_v4_state_assembler.py` — (no docstring summary)
- `test_ng_exhaustion_v4_unified_runtime.py` — (no docstring summary)
- `test_ng_historical_replay.py` — (no docstring summary)
- `test_ng_rt_feature_state.py` — (no docstring summary)
- `test_storage_consensus_causal_s126.py` — (no docstring summary)
- `test_system_inventory.py` — (no docstring summary)
- `tropical_feed.py` — the TROPICAL / HURRICANE feed (S110; the named summer gap, memo 1.4).
- `databento_options_iv_black76_example.py` — VENDOR REFERENCE - Databento official 'Estimate implied volatility' tutorial (verbatim,
- `verify_gold.py` — THE CONCRETE WALLS around the refine gold master (S105, Greg).
- `vol_regime.py` — DATA_GATE_S98 feed B: VOL / RANGE REGIME per date (family: tape conditioner).
- `weather_regime_score.py` — per-REGIME weather scoreboard (S84).

<!-- END GENERATED FILE INVENTORY -->
