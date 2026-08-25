# Two Frankies — Keyless October 4–5 Prior-Surface Build Control

## Scope

This is the exact two-day discovery run on
`[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)`. Its only market source is the
112,852,940-byte object with SHA-256
`93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90`.
The evidence label is `PRIOR_REDUCED_NON_FULL_MBO_SURFACE`. It is the earlier
aggregated-seconds surface and must never be described as full MBO.

This build does not run a test or canary. It does not read, cancel, rerun, modify,
or wait for the independent full-MBO Step-1 run. Protected production commit
`a7611133f64064200de48cd2e7839fcea2510d51` remains untouched.

## Keyless blind → freeze → refine sequence

The GitHub workflow is a deterministic private packet bridge only. It verifies the
exact source, filters the exact half-open interval, builds the capability and
lawful-knowledge packets, and publishes a private artifact. It does not call a
model. The workflow and packet builder fail if an OpenAI key is present; there is
no OpenAI-key lookup, CLI invocation, SDK call, provider response, or provider cost
receipt.

ChatGPT Work then performs the two principal role calls sequentially using
`gpt-5.6-sol`:

1. `REAL_TIME_FRANKIE`
2. freeze and hash the complete validated RT output
3. inject that immutable output and hash into Forecaster's packet
4. `FORECASTER_FRANKIE`

There are no automatic model helpers, specialists, repair calls, retries, or
fallbacks. RT retains one optional deterministic local evidence scout over the
exact two-day rows; it is not a model and is never auto-called. Forecaster has one
optional knowledge-helper agent available for a single explicit call. It is never
auto-called. If used, it is a conditional third model call, not a third principal
role; its call and response hash must be receipted. No other helper or specialist
is exposed.

## Capability and knowledge preservation

The complete 1,940-leaf, 46-block, 24-surface capability registry is preserved.
Forecaster's registry routes are all `DIRECT` and none are dormant. Registry
identity is separate from value availability: absent reduced-surface values remain
`UNAVAILABLE` or `UNKNOWN`, never false, zero, synthesized, or silently omitted.
RT's expressly approved role-specific dormant routes remain unchanged.

Canonical direct static source bytes are restored to Forecaster's packet rather
than replaced by hashes. The complete lawful source plane is additionally emitted
byte-for-byte in a content-addressed private knowledge bundle. `SERVE` sources and
explicit `SHADOW_ONLY` sources are present; shadow claims remain nonbinding.
`DENY` and `SEALED_UNTIL_PRIMARY_FREEZE` contents are not read or included. The
sealed Step-1 answer wall remains closed.

Forecaster must ingest the complete knowledge inventory and authority map, full
registry, exact two-day context, and complete frozen RT output. Every lawful byte
remains preserved and addressable. Hash-receipted deterministic retrieval selects
model-visible content within the 150,000-token principal ceiling, and the result
must reconcile consulted and uninspected source rosters without treating an
uninspected source as absent. The optional helper may retrieve or reconcile only
those same lawful bytes; it has no independent feed, current-state
authority, forecast ownership, repair authority, or access to Step-1 answers.

## Role missions

### Real-Time Frankie

RT detects and characterizes exhaustion; it does not own the general future market
curve. For every candidate it must build an observed causal runway, keep event,
receive, evidence-availability, and decision/as-of clocks separate, characterize
dipole state and transitions, search open-world correlations and ordered motifs,
and estimate exhaustion-specific pre-birth detectability, lead time, detection
latency, causal age, total duration, and remaining duration. Those narrow
exhaustion projections do not authorize a general price forecast.

This is answer-key-blind retrospective discovery over the complete two-day
surface, not prospective or out-of-sample validation. RT must reconstruct claimed
early signals from explicit causal prefixes and label early-warning, latency,
duration-error, and strategy findings accordingly.

RT directly receives the exact `odcore/info_dipole.py` source. It uses signed
buy-versus-sell imbalance for current direction and opposing flow plus collapse
toward balance for continuation/weakening/reversal/flip risk. Dipole magnitude
alone is not direction, and the provisional direct `cell_signal` map may not be
promoted to fact.

RT also directly receives the exact provisional `frankie_lats_p0_search.py`
bounded-lookahead source. It applies the fixed-budget multi-hypothesis selection,
feedback, reflection, and backpropagation pattern only as `SHADOW_ONLY` reasoning
at the current causal cutoff. It cannot read future outcomes or mutate the first
lock.

After its observed first lock is complete, RT must add provisional trading-strategy
hypotheses as discovery research. Each hypothesis states triggers and clocks,
position logic, entry, hold, exit/reversal, invalidation, horizon, risk, costs/fill
assumptions, unavailable requirements, contradictions, and evidence. It has no
execution authority and may not claim validated profitability from two days. A
strategy preference may not alter the detection lock.

### Forecaster Frankie

Forecaster's main job is the strongest honest forecast it can make. It plots
explicit future points into one continuous time-evolving forecast curve, carrying
conditions, distributions/ranges, catalysts, disconfirmers, confidence,
missingness, separate clocks, and conditional dipole paths. Materially distinct
or multimodal paths remain separate and are never averaged into a false centre.

Forecaster consumes the exact frozen RT output and hash but may not reconstruct or
mutate RT's current-state authority. Farther-future exhaustion correlation search
is secondary and not a success gate. Both roles search beyond known families for
novel fields, depths, mechanisms, nonlinear interactions, causal lags,
clock-to-clock relationships, dipole transitions, recurrence/extension sequences,
and ordered motifs. `NONE_FOUND_IN_SEARCHED_COVERAGE` is lawful.

## Token ceilings

- RT direct input: 48,000 estimated tokens.
- RT cumulative input, including deterministic scout continuations: 96,000.
- RT cumulative accepted output: 12,000 estimated tokens.
- Forecaster principal input: 150,000 estimated tokens, including the full frozen
  RT object and any lawful-knowledge bytes loaded into principal context.
- Forecaster accepted output: 12,000 estimated tokens.
- Optional Forecaster knowledge helper input: 48,000 estimated tokens.
- Optional Forecaster knowledge helper output: 6,000 estimated tokens.

The Work execution surface does not expose provider token metering. Receipts must
say so truthfully. Packet and output byte ceilings use the frozen conservative
0.285-token-per-byte estimator; no provider cost is claimed.

## Launch and cleanup

Implementation, authorization, and transient workflow activation are separate
commits. The one-shot launch commit changes only the workflow to add the guarded
feature-branch push trigger. After its target run registers, the workflow is
immediately restored to this manual-only version in a workflow-only cleanup commit.
No default/production branch is changed.
