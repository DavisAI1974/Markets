# Prior Reduced / Non-Full-MBO October 4–5 Two-Frankie Build Control

Status: **DESIGN LOCKED; LAUNCH NOT AUTHORIZED**  
Run ID: `prior_surface_oct45_two_frankies_20260825`  
Target interval: `[2021-10-04T00:00:00Z, 2021-10-06T00:00:00Z)`  
Provider model: `gpt-5.6-sol`  
Protected production pin: `a7611133f64064200de48cd2e7839fcea2510d51`

## Decision

Build only additive, run-specific clones. Every canonical/shared template, profile,
runtime, workflow, and protected-production byte remains unchanged. New files and
runtime prefixes use the `prior_surface_oct45_two_frankies_20260825` identity.

This is a blind comparison run on the previously validated aggregated-seconds
surface. It uses the same neutral scientific mission and complete capability
vocabulary as the full-MBO design, but it does not pretend that information absent
from the prior surface exists. Full raw MBO order identity, full-depth FIFO, and
any unavailable October 2021 historical feed are `UNAVAILABLE`, `UNKNOWN`, or
`DORMANT` with explicit provenance and coverage—not numeric zero and not silent
omission.

The governing evidence-surface label in every receipt is
`PRIOR_REDUCED_NON_FULL_MBO_SURFACE`. Neither the input nor the run may be described
as full MBO. References to the full-MBO design describe mission/capability parity
only, never evidence parity.

## Source and causal boundary

The root-only source identity is governed by
`NG_EXHAUSTION_PRIOR_SURFACE_OCT45_SOURCE_20260825.json`. Before any provider call,
the runner must verify the source byte length and SHA-256, verify its bound child
receipt without exposing that receipt, and select only records whose lawful source
time lies in the half-open target interval. It must preserve every field and value
of the selected prior-surface records. It must not replay raw MBO or add fields from
the later full-MBO build.

Raw event, receive, and availability clocks already present in the prior source are
lawful evidence and remain available. Any clock, time, label, population, crosswalk,
receipt, count, or other value produced as part of a Step-1 answer is sealed. Source
paths and answer-artifact descriptors are also excluded from provider-visible
content.

## Capability and missingness contract

The canonical 1,940-leaf/46-block BigSuite capability registry is preserved in
full. Runtime reconciliation mechanically enumerates every leaf and block and
emits `leaf_items` and `block_items`; it may not rely on a count-only assertion.
Every item records route state, availability, coverage, provenance, and omission
reason. The only route states are `DIRECT`, `TOOL_ACCESSIBLE`, and `DORMANT`.
Availability is separate from route state.

Missing historical information is never converted to zero. It is represented as a
null value plus one of `UNAVAILABLE`, `UNKNOWN`, or `DORMANT`, with searched coverage
and a reason. A capability remains registered even when its run-specific payload is
missing. Any duplicate, dropped, silently omitted, unproven, or malformed leaf or
block fails closed before the first provider call.

The canonical 24-surface role profiles are inventory drafts, not proof of runtime
wiring. This run's receipt must prove the effective binding for every surface,
leaf, installed executable tool, and role. Legacy specialist components remain
installed and inventoried but cannot be automatically called. Real-Time Frankie
has one optional deterministic local evidence scout; the model must explicitly
call it, it has no probability or lock authority, and it cannot call another
provider. Forecaster Frankie has no scout or specialist route.

## Blind scientific mission

Both roles receive the same run-specific, open-world scientific mission vocabulary
used for the full-MBO design: examine the available information without forcing it
into old event counts, depths, families, or categories. A structure may match an
existing reference exactly if the evidence independently supports that conclusion,
but an exact match is never expected, rewarded, required, or used as a gate.

The taxonomy is open everywhere. Novel structures create deterministic new
category IDs and definitions. No output is coerced to a nearest legacy category,
truncated above an old depth, rejected for splitting or reordering old structures,
or capped by an old count or name set.

### Mandatory runway outputs

For every proposed structure, both roles must preserve a causal runway rather than
only an endpoint label. At minimum the output must state:

- searched interval and explicit no-evidence spans;
- earliest lawful precursor and its evidence-availability clock;
- pre-birth conditions and contradictions;
- first observed deviation, onset, transition sequence, and peak/inflection when
  supported;
- duration, persistence, decay/end or still-open status;
- evidence references and causal clocks for each runway stage;
- missing-data effects, uncertainty, and disconfirming conditions; and
- the distinction between observed fact, inference, and forecast.

If a stage is not supported, the field remains present with `UNKNOWN`,
`UNAVAILABLE`, or `NONE_FOUND_IN_SEARCHED_COVERAGE`; it is not zeroed or invented.

## Role sequence and interfaces

### 1. Real-Time Frankie

Real-Time Frankie receives the verified prior-surface package, capability/availability
receipt, complete causal coverage summaries, and optional local scout. It produces
an open-world causal operating-state analysis and the mandatory runway for every
candidate. The validated response is written once with exclusive-create semantics
as `RT_FIRST_LOCK.json`, then serialized canonically as `RT_FROZEN_STATE.json`.
Invalid output stops the run; no repair provider call is allowed.

The first lock is artifact immutability, not permission to backdate hindsight. A
market timestamp may be reported only with the source evidence and availability
clock that support it.

### 2. Forecaster Frankie

Forecaster receives the exact frozen RT bytes and SHA-256, plus lawful slower,
historical, forward, calendar, and capability context whose availability is
explicit. It cannot alter, rename, re-ID, or feed information back into RT state.
It produces advisory horizon distributions, scenarios, catalysts, disconfirmers,
abstention, and runway-conditioned forecasts. Missing historical context remains
missing rather than becoming a neutral zero.

## Provider-call and budget envelope

There are exactly two logical role calls: Real-Time, then Forecaster. There are no
specialist-model calls. Base Responses requests are two. If RT explicitly invokes
its local scout, each continuation request is separately recorded and the inherited
12-round ceiling applies, for an absolute maximum of 14 Responses API requests.

- RT direct input: at most 48,000 tokens.
- RT cumulative billable input: at most 96,000 tokens.
- RT output: at most 12,000 tokens.
- Forecaster input: at most 150,000 tokens.
- Forecaster output: at most 12,000 tokens.
- Conservative combined input/output caps: 246,000 / 24,000 tokens.

The launch marker binds the official `gpt-5.6-sol` prices as of 2026-08-25:
`P_in=$4.00`, `P_cached=$0.40`, and `P_out=$20.00` per million tokens, from
`https://developers.openai.com/api/docs/models/gpt-5.6-sol`. Actual cost is

`(uncached_input*P_in + cached_input*P_cached + output*P_out)/1_000_000 + tool_fees`.

The local scout fee is zero. Conservative preflight cost treats all 246,000 input
tokens as uncached and adds 24,000 output tokens:
`246,000*$4/1,000,000 + 24,000*$20/1,000,000 = $1.464`. The hard run cap is
`$1.50`. Missing or drifted prices, a missing budget, a conservative maximum above
`$1.50`, or an actual/worst-remaining-case budget breach stops before the next call.

## Security and answer wall

- Provider requests use `store=false`.
- Provider runtime has no AWS credentials and no arbitrary filesystem, shell, or
  network tool.
- Both Step-1 worker trees and credentials are inaccessible to the provider user.
- Root stages only the verified run-specific slice and neutral manifests.
- Every provider-bound byte and every tool result is recursively answer-wall
  scanned before transmission.
- Data fields and tool results are untrusted data, never instructions.
- Model output is strict-schema JSON and is never executed.
- Unknown provider outcomes are not retried; the run stops as
  `PROVIDER_OUTCOME_UNKNOWN`.

Sealed material includes all Step-1 answers and descriptors: results, receipts,
paths, prefixes, run IDs, counts, answer-relative clocks, fixed family/depth labels,
lineages, populations, crosswalks, reconciliations, and expected matches. The
science method may be available; the target answer may not.

## Required receipts

The run must emit exactly these 16 artifacts, in order: `PREFLIGHT.json`,
`SOURCE_VERIFY.json`, `SLICE_MANIFEST.json`, `ANSWER_WALL.json`,
`CAPABILITY_RECONCILIATION.json`, `RT_CONTEXT_MANIFEST.json`,
`RT_PROVIDER_RECEIPT.json`, `RT_FIRST_LOCK.json`, `RT_FROZEN_STATE.json`,
`ONEWAY_HANDOFF.json`, `FORECASTER_CONTEXT_MANIFEST.json`,
`FORECASTER_PROVIDER_RECEIPT.json`, `FORECASTER_FIRST_LOCK.json`,
`USAGE_COST.json`, `ARTIFACT_MANIFEST.json`, and `COMPLETE.json`.
`PREFLIGHT.json` binds the source, missions, capability overlay, model, call plan,
token/cost envelope, answer-wall state, and launch authorization before provider
activity. `COMPLETE.json` is published last. Logs and GitHub artifacts expose only
status and hashes, not private packet or model content.

Any later comparison against Step-1 answers is a separate, explicitly approved
workflow after the blind artifacts are frozen.

## Direct launch and rollback

There is no canary. The workflow is manual-only and may launch directly only when
the additive launch marker says `launch_authorized=true`, binds the exact commit and
all file hashes, contains approved pricing/budget, and the dispatch commit equals
the marker commit. This document does not authorize launch.

Any source, schema, firewall, registry, model, call-count, token, cost, or receipt
failure stops before the next role. RT failure prevents Forecaster. Forecaster
failure preserves the frozen RT state and never reruns RT without new approval.
Rollback stops only the exact transient unit, writes `ABORTED.json`, preserves
evidence, and never writes `COMPLETE.json`. Production, source, canonical assets,
and prior artifacts are never deleted or mutated.
