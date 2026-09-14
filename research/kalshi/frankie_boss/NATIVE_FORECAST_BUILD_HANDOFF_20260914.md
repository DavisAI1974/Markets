# Native forecast software checkpoint — 2026-09-14

Historical checkpoint: the owner subsequently approved the separate versioned
twelve-field interface with null confidence. Its enabled adapter and verified
ledger consumer are described in CLAUDE_NATIVE_FORECAST_REVIEW_HANDOFF_20260914.md.
That successor supersedes the pending-decision and draft-only status below.

Continues verified `9582660584c026394ec42175487aa08922a828a8` in the LF checkout
named by NEXT_CHAT_HANDOFF_20260914.md. Repository `DavisAI1974/Markets`; remote
branch `codex/boss-full-evidence-20260907`; local branch
`codex/boss-forecast-build-20260914`. Verify the remote tip; never force-push.

## Built and reviewed

- `ba3e8141`: additive native gap, query-path and autoregressive time/STOP decoders.
- `7a285b35`: known-session conditioning for gap, path and timing.
- `ce3b6a64`: causal session manifests and immutable queryable forecast artifacts.
- `f6227b60`: same-forward B1 producer connected to the existing rolling ledger.
- `eec0ded1`: category-free Frankie draft and explicit protected-interface guard.

The decoder uses B1's final decision representation, not generic head values.
Every emitted P10/P50/P90 path point is a native time query. Initial path is exactly
zero and net is gap plus terminal, computed once. The preopen net is a coherent
central forecast, not a claim that marginal medians add. STOP emits the true close.
Duplicate/unrepresentable timestamps, nonfinite values and exhausted knot budgets
reject without truncation, sorting, endpoint interpolation or fabricated points.

Session features are time-to-open and duration in days, USD scale and tick size.
They are declared forecast coordinates, not raw-input reduction. The explicit
auxiliary-fit boundary freezes median, timing and session-projection parameters
and clears stale gradients. A bounded synthetic optimizer regression proves exact
P50 preservation; no training run or fitted checkpoint was produced.

Postopen requests require certified prior-close/open/current-mark observations
available by the causal cutoffs. Observed path points stay tagged as observations.
Missing historical marks cannot be queried by interpolation. Future queries use
the frozen residual decoder anchored to the current observed mark.

Artifacts retain exact CPU float64 native state, decoder tensors, session provenance
and native/context/recurrence identities. Later queries do not forward B1 or consume
RNG state. Restore requires a trusted digest. Architecture substitutions, weights,
runtime/code and effective CPU arithmetic (including denormal handling) are bound.

## Rolling producer and target semantics

`NativeForecastRefresh.update` accepts explicit receive/event cutoffs, source hash,
arm identity and a trusted hash of active target/session manifests. The full target
registry remains durably bound, including expired targets; only active targets need
current session manifests. Each target is one declared session close. Separate
future-session forecasts are supported; a cumulative multi-session BLD-1 net is not
invented. Other target conventions require approved manifest semantics.

Before any B1 forward, the existing durable refresh intent binds actual decoder/native
identities, effective native module settings, runtime, complete active manifests and
source/input state. Each candidate uses one forward's representation and recurrence
receipt. The producer emits one native candidate with no score or calibration value;
the existing comparable-candidate selector is unchanged. No publication floor or
categorical label is introduced. Ordinary data updates preserve model identity while
appending revisions at unchanged targets. Failed/partial retries use the existing
trusted ledger checkpoints; the ledger remains single-writer with coordinated
unknown-terminal recovery. External delivery, live scheduling and providers are absent.

## Explicit protected-interface proposal

The unchanged BLD-1 validator requires `low|med|high`. A category-free forecast
cannot honestly satisfy it. The reviewed proposal is a separately versioned opt-in
adapter with the same twelve fields and `confidence: null`, retaining the original
BLD-1 adapter and default legacy path unchanged. **Owner acceptance remains pending.**

`prepare_frankie_forecast` creates only `BOSS_FRANKIE_CATEGORY_FREE_DRAFT_V1` for
review. It preserves supplied metadata and valid ABSTAIN forecasts; absent calibration
does not enter fatal defects. It checks S121 clocks, accounting and target date,
preserves compact/ISO date spelling and rejects DST incompatibility independently of
timestamp quantum. `24:00` is S121's terminal 20:00 sentinel, never ordinary midnight.

`route_frankie_forecast` defaults to the exact legacy callback without importing or
initializing native modules. Enabling currently raises
`LegacyConfidenceCompatibilityError` with the intact draft attached. It does not
pass the draft to BLD-1, label a winner high, or erase a valid forecast into zeros.
The owner decision and subsequent consumer wiring remain required. This is a
standalone disabled-route proof, not deployed integration in `spawn.py`.

## Verification and boundaries

New focused checks: 21 decoder, 17 session/artifact, 7 native-refresh and 9 bridge
tests: 54 synthetic checks. Independent review reproduced and closed optimizer
median drift, snapshot architecture/runtime gaps, expired-target blockage, native
module-setting retry drift, compact-date incompatibility and coarse-quantum DST
acceptance. No required findings remain for the implemented slices.

Final verification at implementation checkpoint `eec0ded1`: broad suite 914 passed,
1 CUDA-only skip; isolated checkpoint suite 11 passed. Total **925 passed, 1 skipped**
across the two processes. The 54 focused checks overlap and must not be added again.
Python compilation and Git whitespace validation passed. This handoff and task-status
update is a descendant documentation-only commit, not a new software implementation.

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests --ignore=research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
python -m pytest research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
git diff --check
```

Protected Frankie, S121, B0/B1 controls, context runner, C15/QSV, raw evidence,
replay and Memory A source files are unchanged. The previous closeout workbook
remains historical evidence and byte-identical, SHA-256
`8862589effeee8ccb745dba6fe97a270921571c5524bd8d1b98df04f03817b23`.

Training, provider/market-data/mechanics runs, held-out/OSS evaluation, serving
downloads and live execution remain parked. No fitted weights, eligible calibration,
timestamp-noise evidence, accuracy or production throughput is claimed. Production
manifests, empirical acceptance, QSV producer, six teacher columns, Granite serving,
experiment orchestration and execution remain open. G15 stays Partial/OPEN and
production B2_GATED remains incomplete. Rollback keeps opt-in paths disconnected;
retain every evidence/forecast ledger and all historical artifacts.
