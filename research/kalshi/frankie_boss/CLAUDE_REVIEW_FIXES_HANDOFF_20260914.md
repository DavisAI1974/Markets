# Claude review corrections and next-chat handoff — 2026-09-14

This is the successor to CLAUDE_NATIVE_FORECAST_REVIEW_HANDOFF_20260914.md.
The owner authorized all of Claude's required and optional fixes and explicitly
authorized parallel work. No further approval is required to finish that scope.
Earlier handoffs remain historical records; do not restart their completed work.

## Repository checkpoint and verification

- Repository: DavisAI1974/Markets.
- Remote branch: codex/boss-full-evidence-20260907.
- Local branch: codex/boss-forecast-build-20260914.
- Checkout: C:/Users/A/Documents/Codex/2026-09-14/b1-s-required-checks-passed-on/work/Markets-forecast-verify.
- Prior completed native/consumer checkpoint: 2b44b4e09374bf13d43088cccb996e71eb3e4056.
- Verified implementation/timing checkpoint: 39c8c026f32a80a96c42d0437f210a6950d2954a.
  This handoff is in a descendant documentation closeout commit. Resolve the
  current remote tip before continuing rather than assuming the earlier software tip.
- Final broad synthetic suite: **982 passed, one CUDA-only skip** in 190.32 seconds.
- Isolated checkpoint suite: **11 passed** in a separate process.
- Combined verification: **993 passed, one skipped** across the two processes.
  The 31 new review regressions are included in these totals, not added again.
- Independent reviews closed every required finding for each implementation slice
  and the timing harness. Python compilation and Git whitespace checks passed.
  The control fixture remains LF; the historical workbook hash is unchanged.

Closeout is complete for these software review corrections. The descendant
documentation commit is the final closeout; verify its current local/remote tip
and clean-tree state before continuing. Never force-push.
The older work/Markets checkout is stale; E:/Markets is unrelated protected work.

## What was already built

The prior stage implemented native gap, path and endogenous timestamp/STOP heads;
causal session manifests; exact frozen artifacts; same-forward B1 rolling generation;
and an opt-in category-free Frankie adapter and verified publication consumer.
The consumer was completed after the range Claude reviewed. Its implementation is
230c6480; its completed handoff is at 2b44b4e0. Claude's original review covered
9582660 through bdd7663 and explicitly made no consumer verdict.

The existing exact native mapping, context receipts, C15R2 and governed QSV
attachment, reliability diagnostics, comparable-candidate selection and retry-safe
rolling revisions were retained. They do not need rebuilding.

## Constraints that remain in force

Publish the sole valid candidate or the highest-ranked comparable candidate. No
low/medium/high categories, invented calibrated probability or absolute score floor
has been added. Missing calibration alone does not suppress a valid forecast.
Every horizon retains its original absolute target and earlier immutable revisions.
Ordinary source updates remain separate from versioned model changes.

The owner-approved opt-in interface still has exactly twelve payload fields and
confidence null. Original BLD-1 and its legacy confidence enum are unchanged. The
transport stamp is outside the payload. The default-disabled path still invokes
the exact legacy callback without model imports or enabled-route validation.

Protected Frankie, S121, B0/B1 controls, raw evidence, replay and Memory A are
preserved. Training, provider/market-data runs, held-out/OSS evaluation and live
execution remain parked. Tests and timing here use synthetic software fixtures.
No fitted weights, calibration, predictive accuracy, empirical coverage, production
throughput or completed production B2_GATED acceptance is claimed.

## Correction map

| Finding | Implementation checkpoint | Result |
|---|---|---|
| R1: runtime drift prevents historical reads | 9b31b77b735336b530397b4a8e5569f15ab9da24 | Structural reads and stored-point projection separated from locked-runtime queries/reproduction. |
| R2: proposal supplies its own trust root and mutable metadata | fbf8e9a89c38b146f0533545573172efa8b77783 | Independent expected artifact/publication identities and defensive caller-metadata snapshot; explicit unverified metadata stamp. |
| R3: exact global-cutoff price anchor | 014e8c3a8b4574c0de673bf27600e0c5b53aab20 | Last certified mark anchors the path; cutoff controls future emissions; anchor age conditions the decoder. |
| R4: preopen gap lacks a reference price | 014e8c3a8b4574c0de673bf27600e0c5b53aab20 | New generation requires a causal certified prior close; archived reads are not retroactively rejected. |
| R5: nonfatal gaps cannot accompany CALL | 4eebf5852d039c28a016213baefc7e118c454e58 | Existing defects list explicitly fatal-only; nonfatal gaps are preserved in reasoning. |
| O1: repeated reconstruction and journal scaling | Timing closeout pending below | Reproducible bounded diagnostic measures journal growth and full refresh/consumer costs; no production claim. |
| O2: S121 boundary crossing | 4eebf5852d039c28a016213baefc7e118c454e58 | Explicit diagnostic rejects sessions crossing the 20:00 ET boundary; no protected clock change. |
| O3: one-dollar standalone accounting slack | fbf8e9a89c38b146f0533545573172efa8b77783 | Category-free records require exact net = gap + terminal equality. |
| O4: safety abstention loses play history | 4eebf5852d039c28a016213baefc7e118c454e58 | Pre-abstention fired/stood-down metadata retained in reasoning while safety execution fields stay empty. |
| O5: tick size only conditions decoder | 014e8c3a8b4574c0de673bf27600e0c5b53aab20 | New generation validates certified prices on the declared uniform zero-origin grid. |
| O6: two-point path and linearity rule | 4eebf5852d039c28a016213baefc7e118c454e58 | Explicit regression preserves native immediate-STOP open/close paths as valid. |

## R1: historical evidence versus current reproduction

NativeForecastArtifact.from_payload now defaults to structural and digest validation.
It checks canonical bytes, exact expected digest, tensor encodings/shapes/finite
values, quantile ordering, causal observed prefixes, future point order/quantum/budget,
receipt linkage and exact net accounting. It does not instantiate today's decoder
or require today's runtime identity to read already-published points.

verify_reproduction() and from_payload(..., verify_reproduction=True) are explicit
runtime-locked operations. query() retains the same runtime lock. A source edit,
Torch/Python change or thread-count drift can therefore block a new computation
without blocking an audit read or Frankie projection of already-stored values.
Structural validity is not proof that today's decoder reproduced those values.

freeze_forecast verifies reproduction before returning a newly generated artifact.
When it has context receipts it then adds a publication-validation attestation,
binding the reproduced artifact hash and snapshot runtime. The transport reports
publisher_verified only when this marker is present; otherwise it reports unknown.
This is a publisher attestation trusted through the retained ledger publication,
not a claim that the current reader reproduced the forecast. Self-supplied hashes
or markers do not authenticate a publisher.

The archived bdd7663 V1 fixture preserves its original bytes and digest, including
its old four-coordinate snapshot and missing preopen reference. Parsing does not
backfill history, silently reinterpret the old forecast or fabricate an attestation.
Tests cover archived projection without decoder restoration, source/runtime drift,
thread drift, malformed dimensions and structurally sound but nonreproducible data.

## R2 and O3: trust and accounting at the adapter

route_frankie_forecast takes expected_digest, publication_hash and metadata as
separate enabled-route arguments. The loader supplies only a proposal. The consumer
obtains the selected artifact identity and publication identity from its verified
retained ledger receipt; they are no longer accepted solely from the draft.

Caller metadata is deeply copied and validated before invoking the loader. Projection
is regenerated from stored verified points and the independent metadata snapshot,
then compared against the proposal. This catches coherent numeric changes, metadata
replacement and nested-list mutation during proposal loading.

There is not yet an authenticated protected Frankie metadata-origin record. The
stamp therefore says metadata_verification = caller_supplied_unverified and includes
a metadata_hash. That hash detects identity changes; it does not make metadata
authoritative. This deliberate limitation is visible rather than hidden. Production
wiring must decide how its actual population record supplies an authenticated origin.

CategoryFreeRecord validation now requires exact net = gap + terminal accounting,
including direct construction. The old protected BLD-1 tolerance is untouched.
Constructing a record directly is still not a substitute for using the verified
publication consumer; the record class alone cannot authenticate a ledger.

## R3, R4 and O5: usable causal sessions without rewriting history

anchor_ns is the latest certified mark's event time, or the certified opening when
no later mark exists. The anchor may precede the shared event cutoff. Every mark
must still satisfy causal event/receive availability and strict observed ordering.
Two instruments can share a cutoff while having different last observation times.

There is no interpolation or invented observation in the interval from the anchor
through the cutoff. Queries for uncertified historical times still fail. Generated
future knots lie strictly after the cutoff on the declared timestamp quantum; a
cutoff need not itself lie on that quantum. The residual path remains anchored to
the actual certified price movement.

The decoder gains a fifth session coordinate: elapsed time from anchor to event
cutoff, normalized by one day. The original four coordinates remain time until open,
session duration, USD conversion and tick size. Anchor age reaches gap, path and
time heads through session conditioning. This is a model change: new five-coordinate
weights, source/runtime identity and snapshot digest flow through model identity.
It is not presented as an ordinary forecast refresh. Archived four-coordinate
snapshots remain structurally readable; they are not converted into new weights.

validate_for_publication is called for new generation and requires a certified prior
close, including preopen. The reference observation is retained in the immutable
session/artifact and therefore in their identity. A reference change changes that
identity. No requirement that the decoder condition on the absolute reference level
or a claim of fitted predictive behavior was introduced.

The same current-generation validation checks prior close, opening and known marks
against a uniform, zero-origin price grid using exact decimal-rational arithmetic.
Negative prices on the grid are valid. Variable tick schedules or nonzero-origin
grids need a separately defined convention; do not guess one. These new generation
requirements do not retroactively invalidate structurally valid old V1 payloads.

## R5, O2, O4 and O6: reporting and protected semantics

The twelve-field category-free payload uses state_defects_and_gaps_reported for
fatal integrity or causal failures. Nonfatal missingness is recorded in reasoning.
report_nonfatal_gaps(metadata, gaps) preserves the existing metadata and appends
explicit nonfatal descriptions without changing CALL to ABSTAIN or adding a field.
This implements Claude's option (b) within the owner's authorized twelve-field
decision. No thirteenth field, revised protected interface or new approval is needed.

The helper does not classify severity. Callers must not downgrade unavailable
required evidence, corrupted receipts or causal violations to nonfatal prose.
Calibration missingness can be reported while a valid candidate is still published.
Optional context missingness is nonfatal only when the governed arm actually permits
that absence; required QSV or source evidence cannot be bypassed by labeling it optional.

Safety abstention remains complete: ABSTAIN, zero net/gap, zero safety curve and empty
execution play fields. Previously supplied fired/stood-down play metadata is appended
to reasoning for audit context. It does not become an instruction to execute a play.

The bridge now explicitly identifies a session crossing S121's 20:00 ET boundary.
Its prior rejection of offset changes and sessions longer than 24 hours remains.
Futures-style 18:00-to-17:00 sessions need an approved session split or separately
specified clock before they can be bridged. No clock wrapping, silent split or S121
modification was added. A session ending exactly at the permitted boundary is not
treated as crossing past it.

A native immediate-STOP decoder can produce only open and true close. That is a
valid two-point path; the A-86 check does not turn it into an interpolation violation.
The regression distinguishes it from fabricated interior points on a straight line.

## O1: bounded software timing

Script: tests/benchmark_native_forecast_software.py.
Result artifact: artifacts/CLAUDE_O1_SOFTWARE_TIMING_20260914.json.
The result artifact is complete with zero failures in its three measured cases.
Timing implementation reviewed and committed:
39c8c026f32a80a96c42d0437f210a6950d2954a.

The diagnostic uses new scratch directories, synthetic evidence rows, a small native
decoder and three targets. It separately times context preparation, the event-cutoff
journal scan, full refresh, structural parse, explicit reproduction and consumption
including ledger verification. A separate instrumented pass counts visited evidence
and forecast entries plus decoder capture/restoration calls, keeping instrumentation
overhead out of the latency samples. Runtime, CPU/thread configuration, payload size,
journal size and raw timing samples are recorded with the output.

Observed medians in milliseconds, five samples after one untimed warmup per operation:

| Evidence rows | Context preparation | Cutoff scan | Three-target refresh | Structural parse | Reproduction | Verified consume |
|---:|---:|---:|---:|---:|---:|---:|
| 32 | 147.08 | 125.17 | 563.93 | 2.41 | 7.41 | 39.53 |
| 128 | 522.10 | 514.79 | 1353.36 | 2.59 | 7.24 | 40.68 |
| 512 | 2090.26 | 2133.95 | 4569.28 | 2.46 | 8.97 | 45.54 |

This run used Python 3.13.7, Torch 2.9.1+cpu, Windows, AVX2, four Torch threads
and four interop threads, an eight-row context and approximately 42 KB artifacts.
The instrumented refresh visited four times the evidence-row count in each case,
with ten decoder captures and six restorations. Timed and instrumented consumption
both used 24 forecast journal entries and performed no decoder captures/restorations.
The separately instrumented extra refresh then increased the ledger to 28 entries,
which is recorded separately from the timed ledger size. Its publication
ledger size was held comparable across cases; this does not measure consumption
against an independently growing publication ledger.

The observed journal work grows with retained evidence despite the fixed context
window. This makes journal verification/scanning the demonstrated scaling concern
in these fixtures. R1 removes decoder reconstruction from historical consumption;
no protected evidence-journal optimization or checkpoint weakening was introduced.
The reported p95 uses nearest rank and is simply the largest of five observations,
not a stable tail-latency estimate.

At a hypothetical one refresh cycle per second, the measured 512-row workload's
4.57-second median already exceeds that budget on this fixture. This is a workload
comparison, not a proposed live cadence or capacity estimate for real market data.
Production wiring must separately resolve the cost of full retained-journal scans
without dropping evidence or weakening trusted checkpoint verification.

Two initial harness attempts failed on fixture cadence coverage and instrumentation
syntax; those were corrected before the final successful report. A first successful
timing pass also exposed a ledger-size mismatch between timed and instrumented reads.
The final report reruns the corrected harness with matching read workloads. Failed
scratch attempts are retained outside the repository; only the final report is committed.

This addresses the request to measure journal size against refresh cost before
production wiring. It is a diagnostic, not a production throughput benchmark or
acceptance gate. Do not extrapolate a few small synthetic samples into market-load
capacity or accuracy. Read the actual result artifact for measurements; no timing
has been inferred from Claude's different Python/Torch environment. Protected journal
or replay storage must not be optimized by discarding evidence or weakening verification.

## Verification and reproduction

Focused regressions are in test_claude_artifact_review.py,
test_claude_session_review.py and test_claude_bridge_review.py, with corresponding
updates to the existing native-head, session, bridge and consumer tests. The fixes
were split into independently reviewed increments before integration. Final aggregate
results belong in the checkpoint section above; earlier totals are historical.

Run from the checkout in PowerShell:

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests --ignore=research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
python -m pytest research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
```

The checkpoint tests require a separate Python process because they verify that
Torch was not imported. CUDA-only skips on this CPU machine are not CUDA validation.
The timing script accepts --work-dir and --output; use a new scratch path and read its
bounded --rows/--repeats options. It must not invoke providers or production training.

## Remaining build and useful independent review

Native forecast software, the category-free consumer and the corrections above do
not activate production controller/service wiring. spawn.py has not been switched
over. Production feed/QSV and throughput acceptance, teacher-column work, Granite
serving, paired experiments/reveal and execution controls still require their planned
work and evidence. Training and empirical/live activities remain parked.

For the next agent: run using-agent-skills first, verify repository/remote state, read
this successor and the production plan/todo, and continue the next unfinished software
increment. Do not redo native mapping, rolling revisions, the nullable interface or
Claude's completed corrections. Preserve the workbook and earlier closeout as historical
evidence. Do not treat missing calibration as a publication cutoff or declare B2_GATED
complete because software tests pass.

For Claude's next pass, focus on the corrected trust boundary and metadata limitation;
archived reads versus explicit reproduction; publisher attestation semantics; stale
anchors and future timestamp quantization; five-coordinate model identity; old V1
byte preservation; current-generation reference/grid rules; nonfatal reporting and
safety play history; and the measured journal scaling. Review the consumer beyond
bdd7663 as well, since that module was outside the original review range.
