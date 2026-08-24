# Two-Frankie full-suite architecture and October inspection handoff

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies task-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

Date: 2026-08-24  
Protected production branch: `chatgpt/ng-exhaustion-october-sharded-20260824`  
Protected production commit: `a7611133f64064200de48cd2e7839fcea2510d51`  
Isolated review branch: `chatgpt/frankie-october-aws-readonly-20260824`  
Pre-handoff review-branch commit: `cdb205913754bedfc0b3ccd65fe350e3d8bbabab`

## User operating rule

Frankie is not being tricked or tested for sport. The goal is to make Frankie as informed and capable as
possible. State the scientific mission explicitly. Whether target answers are hidden or revealed depends on
the goal and must be agreed with the user before a run.

For the immediate October work, the goal is collaborative retrospective development, not a blind predictive
score. The dipole and other exhaustion-related structures are known minimum phenomena to investigate. Give
Frankie the verified October Step-1 material side by side with the causal October data and label any missing
coverage `UNKNOWN`, never negative.

Before any experiment or provider call, agree with the user on the objective, roles, exact prompt, visible
and withheld data, cutoff/wall, outputs, model and call count, cost, success criteria, stop condition, and any
post-reveal step.

## Complete-suite rule — no silent thinning

Start from the complete existing October ingestion suite. Do not preselect a small packet and silently call it
the suite. Every expected source, field, byte range, model-visible artifact, and runtime input must be present
with a content-addressed receipt or explicitly marked `INPUT_ABSENT` with its reason.

The complete source inventory remains retrievable even when Frankie later chooses that only a subset belongs
in direct context. Frankie—not a helper or packet builder—decides what should be direct, tool-accessible, or
unnecessary. Routing may reduce salience; it may not delete scientific information or conceal omissions.
Lossless Nova minification may reduce representation overhead after selection, but it is not a relevance
filter and may not remove keys, values, plays, evidence, or provenance.

### Uniform superset build and reversible role profiles

Do not create separate shrinking Real-Time and Forecaster codebases. Maintain one immutable superset Frankie
build containing every accepted capability, data connector, schema, tool, model asset, learned artifact, and
source. Role differences are expressed only through small, content-addressed activation profiles.

Every registered item has exactly one explicit role state:

- `DIRECT`: placed in the role's initial model context;
- `TOOL_ACCESSIBLE`: installed, indexed, receipted, and available on demand; or
- `DORMANT`: turned off for that role but still present byte-for-byte in the uniform build and available for
  explicit reactivation without rebuilding, rewriting, or migrating data.

An activation record must include stable item ID, build/source hash, role, state, reason, requester/approver,
timestamp, and profile hash. `DORMANT` is not `ABSENT`. A separate availability receipt must prove that the
underlying item is still installed. `INPUT_ABSENT` is reserved for a genuine missing input and must fail the
expected-coverage gate when the input was required.

During development, start with the complete suite available. Frankie may recommend moving items from
`DIRECT` to `TOOL_ACCESSIBLE` or `DORMANT`, but no helper, packet builder, optimizer, or automatic relevance
rule may make that change silently. Require user approval for capability removal from active use. Re-enabling
an item changes only the activation profile; the runtime/build hash remains the same.

The two Frankies therefore share identical runtime, wrapper, workflow, schemas, source registry, and installed
assets. Their role prompts and activation-profile hashes may differ. Normal monthly rollover still changes only
the month descriptor and frozen knowledge declarations, not the superset build or role machinery.

Focused verification for this mechanism must prove:

- all registered source/build hashes are identical across role profiles;
- inactive items remain installed and hash-valid;
- profile changes cannot delete or rewrite source data;
- reactivation exposes the identical item without a rebuild;
- direct/tool/dormant counts reconcile exactly to the complete registry; and
- no unregistered or silently omitted input reaches either Frankie.

Known current inventory measurements:

- October raw DBN: 26 immutable objects, 535,712,025 compressed bytes.
- Bootstrap predecessor: one object, 33,433,238 bytes.
- Full October causal interval: 2,678,400 seconds.
- Provider-visible base corpus: 109 sources, 4,296,662 bytes.
- Existing initial excerpt fan-in: 215,244 bytes, formed by taking at most the first 2,048 bytes of every base
  source. Treat this as an implementation behavior, not an accepted relevance strategy.
- Current brain: 1,739,115 bytes and 90 plays.
- Provisional corpus: 22 sources and 658,331 bytes; 20 were active before the freeze.
- BigSuite registry: 1,914 served leaf fields across 44 blocks. Every possessed causal field must appear in
  the input manifest and remain retrievable; omissions must be explicit.

The complete frozen catalogue is larger than the 109-source provider-visible subset:

| Physical class | Count | Bytes |
|---|---:|---:|
| Provider-visible base | 109 | 4,296,662 |
| Binding current | 64 | 2,195,947 |
| Current brain | 1 | 1,739,115 |
| Frozen learned knowledge | 41 | 336,358 |
| Extra-agent carryforward | 3 | 25,242 |
| Provisional | 22 | 658,331 |
| Archive/denied | 15 | 135,406 |
| Sealed local | 5 | 68,813 |
| **Local catalogue** | **151** | **5,159,212** |
| External Step-1 descriptors | 13 | actual bytes unresolved except the validated October child described below |
| **Runtime identities** | **164** | unresolved until all external descriptors are bound to bytes |

The 13 Step-1 inventory entries were descriptors rather than proven payload access. Catalogue membership is
not proof that Frankie could read the bytes. Build `RT_FRANKIE_COMPLETE_AVAILABILITY_V1` before any call. For
each of the 164 identities it must record immutable run/commit/prefix/cutoff, authority, source path/object
version, bytes, SHA-256, schema, temporal coverage, row/event counts, timestamps/units/null semantics,
supersession/target relation, role route, omissions, and one physical state:

- `AVAILABLE_VERBATIM`;
- `DESCRIPTOR_ONLY`;
- `INPUT_ABSENT`;
- `WITHHELD_BY_APPROVED_MODE`; or
- `ARCHIVE_ONLY`.

Physical availability and role activation are independent. An item can be `AVAILABLE_VERBATIM` physically
and `DORMANT` for one role. It can never be called available merely because a descriptor names it.

The availability gate must fail closed unless it proves:

1. all 151 local sources and 13 external identities reconcile by class;
2. exactly 109 base identities and their aggregate corpus hash;
3. brain version `s105.9`, exactly 90 unique play IDs, body hashes, and verbatim routes;
4. all 22 provisional identities, including 20 pre-freeze active and two post-global-freeze, without hidden
   12,000-character truncation;
5. at least 1,914 unique sorted S135 paths across at least 44 blocks, every field present, explicit null, or
   `INPUT_ABSENT`;
6. all 27 raw objects by key/version, bytes, and hash, plus a one-second ledger covering all 2,678,400 October
   seconds with explicit no-event/missing states;
7. complete normalized MBO, full-depth/FIFO, per-instrument state, and synchronized curve receipts;
8. actual bytes/hashes/schema/coverage for every Step-1 output that will be shown;
9. recent-cutoff retrieval, not merely storage/catalogue presence; and
10. exact reconciliation of all direct/tool/dormant and availability counts.

### Claimed suite surfaces the old runtime did not actually deliver

| Claimed surface | Verified gap at the protected pin |
|---|---|
| Recent causal history | Genesis scan capped at 4,096 records; later October recent history becomes unreachable |
| Complete raw event access | Reduced projection omits publisher/channel, flags, sequence, input delta, and exact cancel/modify priority effects |
| Synchronized multi-contract curve | `_latest_v4_native` is overwritten by the last instrument; no synchronized as-of all-contract/spread/roll map was located |
| Dynamic chain and ancestry | One static opportunity transition is constructed at month start; no evolving predecessor, stopped-chain, negative-context, or lifecycle feed was located |
| Explicit D/dipole/family geometry | Geometry state has price/roll/imbalance/weakening but no explicit dipole, D/family, recurrence, or genuine chain/extension geometry |
| Step-1 revealed view | Descriptors existed, but the runner ended with `answer_revealed=False`; no loader connected actual Step-1 payloads to the typed post-freeze evaluator |
| Complete 90-play brain access | Only the first 2,048 bytes were direct; one play per tool call with a 12-call session made all 90 bodies impractical to reach |
| Complete 109-source access | Listing alone consumes three of 12 calls and reads are 16-KB chunks; storage receipts did not prove provider-read coverage |
| Complete provisional access | Combined pipeline passed only the first 12,000 characters of each active source although originals existed elsewhere |
| Actual S135 October substrate | Validator/schema existed, but the staged October descriptor/payload and source corpus were not located in the repository audit |

These gaps explain the user's concern: the build appeared broad while the effective model interface could be
thin. Do not say “full suite” until the availability and retrieval gates above pass.

## Two Frankies

### Real-Time Frankie

Real-Time Frankie is the central causal operating intelligence, not merely an exhaustion detector. It owns
the authoritative answer to “what is happening now” and derives its broader real-time decisions from that
state. Its responsibilities include:

- current book, flow, price path, curve, contract/session/roll, clocks, and source-integrity truth;
- pressure/absorption, depletion/replenishment, resilience/churn, queue survival/concentration/priority loss,
  spread/depth/liquidity transitions, and other market-mechanics state;
- D, dipole, recurrence, chain, extension, stopped-chain, turn, and novel-structure lifecycles, including
  first seen, ancestry, contradictions, current status, and `NONE_FOUND_YET` searched coverage;
- separation of real movement from roll/stitch artifacts and preservation of raw-contract and adjusted views;
- data-quality and causal-legality policing, explicit uncertainty, and abstention when state is unsafe;
- immutable candidate/contradiction memory tied to exact evidence; and
- a frozen, versioned state export for downstream forecasting.

Real-Time Frankie requested full-suite access, reverse/timestamp-indexed tools, complete raw event fields,
before/after book effects, full FIFO reconstruction, top-20 direct book state, multiscale windows from 1 second
through session/candidate history, curve alignment, exact provenance, relevant exemplars, falsifiers, and
negative cases. Its preliminary salience target is 32–48k direct tokens with tool expansion up to about 96k;
this is a measurement proposal, not authority to remove sources.

### Forecaster Frankie

Forecaster Frankie is a distinct horizon layer. It consumes a frozen/versioned Real-Time state plus the full
BigSuite/curve/weather/fundamentals/history inventory and produces horizon distributions, scenarios,
disconfirmers, calibration/support, and abstention reasons. It does not independently reconstruct a competing
version of current reality.

Proposed one-way cycle for user confirmation:

1. Real-Time Frankie seals `RT_STATE_t` at an exact causal cutoff.
2. Forecaster consumes that state plus slower/forward/historical context and seals an advisory forecast.
3. Real-Time Frankie may consume that frozen forecast once for a later decision surface.
4. A new forecast requires a strictly newer evidence prefix; never feed a same-prefix posterior/action back
   into the forecaster.

Forecaster requested all BigSuite fields indexed and receipted, with selected deterministic panels in direct
context and every source still retrievable. Its preliminary direct-context target is 80–120k tokens with a
soft ceiling near 150k. This is a salience proposal, not authority to drop fields.

## Possible Sol replacements and supporting components

Treat every supplied item as its own system. Do not call it Nucleus, ReFRAG, Operator, Hilbert, RankCore, or
Nova unless that identity is explicit in its own repository/title and verified source. The user expects a
composition of incomplete components, not a single complete winner. Preserve the original repositories and
make any future integration in an isolated copy/branch.

### Candidate identity ledger

| Candidate | Frozen identity/evidence | Potential contribution | Proven limitation |
|---|---|---|---|
| Markets | `DavisAI1974/Markets` at protected pin `a7611133f64064200de48cd2e7839fcea2510d51` | Deterministic OD recurrence, dipole, timing, validation, market adapters, registries, V4 replay/state, Frankie wrappers | Markets fragments are not the complete external ReFRAG or Nucleus engine |
| Nova Optimizer public snapshot | `DavisAI1974/Nova-Optimizer`, `main` at `77aa7eaac492005717992c573da4929e782a801d` | Context/transport utilities | Generic key-shortening compressor is unsafe for canonical Frankie evidence |
| Nova lossless Frankie provenance | User reports commit `1255b0e4286e59e27061b02d85fe8fdfc2873201`, CI #217 passed | Lossless compact JSON for the full 90/90 Frankie packet | Reported commit/run were not reachable from the connected public snapshot; retain as user-supplied provenance until its exact branch/artifact is available |
| Quantum Signal Validator | `DavisAI1974/Quantum-Signal-Validator`, `master` at `82aec5f8b13a70c7ff9afe7c16cd42f76728a77f` | User-confirmed system that found the dipole; alignment, correlation, leading-indicator scaffold | Current tracked tree does not contain the complete historical dipole proof or a complete reasoning system |
| Brain-guided LLM | `pkuxmq/Brain-guided_LLM`, `main` at `f4c6f6b1b737a3885e198185456c7f1241fd2149` | Controlled representation/activation interventions and ablation ideas that may improve salience | Independent research code, not a DavisAI runtime or a named Nucleus/ReFRAG build |
| ReFRAG V2.1 archive | Uploaded manifest archive SHA-256 `bc2df161ee55c3fe3e65e2071ef2ba87d005d46b1a16fe550c341630d121a26a` | Architecture specification, 21 operator manifests, one pipeline manifest, and a partial adapter | Design/manifest bundle, not a runnable clean-clone engine |
| Quantum APIs memo | PDF SHA-256 `70ab4315355ba4ee022129048068630dfeb620f4aa1c2efdc2e6dfd03cf78cbc`; DOCX SHA-256 `1d4792b5a0af9969f79c5ab50497a1f94a013716f7e0dc749bbdca4d6fd50de9` | Async-job, API, and guardrail design ideas | No operator implementation, weights, repository identity, or quantum runtime |
| Operator/Hilbert scaffold | `DavisAI1974/operator_hilbert_seq` at `5bc511c06d3048a510333910588b9a6305532ab2` | Six-file integration sketch | Placeholder operator/embedding/wavelet calculations, missing integration import, heuristic string compression, no weights/tests/runtime; not authoritative |
| Nucleus/RankCore bundle | Intended `collected/nucleus_rankcore_bundle.zip` or later user-supplied source | Intended local structured reasoning engine | Not supplied in the accessible workspace and not inspected; do not reconstruct or choose it from memory |

### Markets fragments that may replace paid helper work

Markets already contains deterministic local pieces that can produce structured evidence without a Sol helper:

- Recurrence and local state: `odcore/operators.py`, `odcore/null_extract.py`,
  `odcore/coupling_scanner.py`, `odcore/incremental.py`, and `odcore/info_dipole.py`.
- Timing: `odcore/leadlag.py`, `odcore/flip_detector.py`, and `odcore/swing_maker.py`.
- Context/provenance: `markets_adapter.py`, `odcore/fingerprint.py`, `operator_registry.py`, and
  `operator_drift_alarm.py`.
- Candidate extension: `odcore/symbolic.py`, `odcore/dipole_predictor.py`, `odcore/stacking.py`, and
  `odcore/validation.py`.

These are reconstructed Markets OD components. They are evidence engines, not final probability/lock
authorities and not a verbatim Nucleus/ReFRAG implementation. Their strongest immediate use is to compute
deterministic, source-linked state and candidate sections locally, leaving semantic synthesis to Frankie.

The Markets V2.1 map is incomplete:

- market analogs exist for spectral chunking/encoding;
- operator query, falsification, chain building, benchmark, lifecycle, and promotion functions are partial;
- the operator decoder is a mean/std stub with no FNO, ensemble, or weights;
- the V2.1 runtime/control operators and `od_spectral_retrieval_pipeline` are absent; and
- no exact V2.1-named implementation exists in the pinned Markets tree.

The vendored build kit still refers to external `E:\refrag` adapters, orchestrator, control-plane storage,
discovery indexes, evidence graphs, lifecycle state, coefficient records, a missing combined-info-flow module,
and a missing schema-v2 gate. The checked-in coefficient index contains 16,484 compact 128-dimensional
signatures, which are evidence/test data rather than model weights. No exact external ReFRAG remote, branch,
or HEAD is recorded.

### How each independent candidate could contribute

- **Quantum Signal Validator:** preserve its historical status as the system that found the dipole. Recover
  the original discovery inputs/outputs when available and use its alignment/correlation/leading-indicator
  outputs as a dedicated, source-linked dipole/signal surface. Do not pretend the current public scaffold
  reproduces the historical discovery until that proof is recovered.
- **ReFRAG V2.1:** use its manifests as interface contracts for operator lifecycle, query, falsification,
  chaining, decoding, and the retrieval pipeline. It can guide wrappers and receipts but cannot replace Sol
  until runtime code, dependencies, state assets, tests, and exact source identity are recovered.
- **Nucleus/RankCore/Operator/Hilbert:** the intended role is local structured recurrence, extension, timing,
  and context processing before Frankie. The known six-file scaffold is explicitly disqualified. Compare
  every later supplied branch/build by exact HEAD, tree, dependencies, weights, entrypoints, wrappers, and
  tests before choosing or rebuilding anything.
- **Brain-guided LLM:** investigate as a shadow salience/representation layer—controlled activation,
  intervention, and ablation—not as market evidence authority. It may help route the complete suite without
  deleting it, but any representation intervention must preserve reversible source pointers and be compared
  on frozen prefixes.
- **Nova lossless path:** use only after the complete canonical packet is frozen. Whitespace compaction or a
  separately reviewed reversible codec must decode to the identical object and preserve all 90 plays,
  evidence, keys, values, indexes, and receipts. Nova reduces representation overhead; it does not decide
  relevance and does not make Nucleus or Frankie smarter. The historical hard gate was at most 475,000
  estimated tokens before one Sol call; if over the gate, stop rather than delete evidence.
- **Quantum APIs memo:** retain only as application/job-control guidance if useful. It is not a quantum
  reasoning engine and supplies no weights or signal logic.

### Replacement architectures still under consideration

1. **Frankie-only with deterministic tools:** eliminate the four paid semantic helpers. Local code maintains
   the complete causal state, candidate registry, recurrence/extension/timing/context evidence, and exact
   retrieval tools. One Real-Time Frankie call occurs only on a deduplicated material state transition. Add a
   narrowly scoped helper later only if traces prove a unique semantic task is missing.
2. **Nucleus local bundle plus Frankie:** after a complete Nucleus build is verified, have it emit four
   separate, source-linked recurrence/extension/timing/context sections locally. Frankie performs one final
   synthesis per lane. This was the original target of two logical Sol invocations per paired prefix instead
   of ten.
3. **Markets OD + ReFRAG-contract hybrid:** use the deterministic Markets components now available, wrap them
   in the ReFRAG V2.1 schemas/receipts where justified, and keep missing operators explicit. This may be a
   nearer-term local evidence bundle while the complete Nucleus/ReFRAG runtime is recovered.
4. **Quantum-signal augmentation:** feed the recovered Quantum Signal Validator dipole/alignment outputs into
   Real-Time Frankie's candidate lifecycle as an independent evidence family, with contradictions and
   falsifiers. It supports the local bundle; it is not a standalone Frankie replacement.
5. **Representation/salience augmentation:** use Brain-guided LLM ideas for reversible routing and Nova for
   lossless encoding after full-suite ingestion. Neither may replace evidence, causal state, or final synthesis.

No option has been accepted. No complete-build winner exists among the currently accessible candidates.

### Sol-call accounting after the two-Frankie split

Do not silently preserve the old “two calls” claim after adding Forecaster Frankie:

| Topology | Logical Sol calls per paired prefix |
|---|---:|
| Current accepted four helpers + one Frankie in each lane | 10 |
| Local evidence bundle + one Real-Time Frankie in each lane | 2 |
| Local evidence bundle + Real-Time and Forecaster Frankie in each lane | 4 |
| One live, unpaired prefix with Real-Time only | 1 |
| One live, unpaired prefix with Real-Time plus a Forecaster update | 2 |

Tool rounds inside one logical invocation must also be measured. Decide whether a comparison needs both
Frankies in both lanes or only Real-Time Frankie before authorization. Do not call four paid helpers merely
because the accepted production path contains them; conversely, do not remove them from production until a
frozen-prefix trace demonstrates equal or better evidence coverage and decision quality.

### Required comparison before adopting a replacement

After all user-supplied candidates are available, compare exact repositories/branches/HEADs, tracked trees,
dependency manifests, weights/checkpoints/LFS, entrypoints, wrappers, tests/CI, clean-clone runnability, source
receipts, and missing external paths. Then use only one or two immutable frozen prefixes. Preserve identical
inputs, sequential control then combined order, source/omission receipts, and explicit role authority. The
current October retrospective is revealed collaborative development; any later prospective/blinded gate is a
separate user-approved experiment.

## Critical runtime defect to address before a meaningful Real-Time evaluation

The current provider-facing history tools do not provide reliable recent history later in a run:

- `MAX_HISTORY_RECORD_SCAN = 4_096`;
- `MAX_RAW_EVENT_RECORD_SPAN = 120`; and
- `MAX_RAW_EVENTS = 500`.

The history reader scans from causal-sequence zero. At one row per second it cannot reach recent state after
68 minutes 16 seconds. Frankie then sees a current snapshot and aggregates but often cannot retrieve the
immediately preceding temporal sequence needed to establish a dipole, exhaustion, or chain.

The current `ActionEvidence` projection also drops publisher/channel, flags, sequence, input latency, and
modify/cancel before-after effects. Fix or replace these retrieval surfaces before using helper count or model
performance as the explanation for missed structures. The desired tools are timestamp/reverse indexed:
`state_window`, `event_range`, `book_snapshot`, `book_delta`, `curve_snapshot`, and `candidate_history`, with
full source and omission receipts.

The 4,096 limit is in the provider-facing retrieval implementation, not in the retained October source. The
tool currently validates the append-only causal hash chain by reading from sequence zero until the requested
record, with per-record, tool-result, and total-output byte limits. The code does not document a scientific
reason for 4,096; it behaves as a defensive work/output bound around a linear scan. That bound accidentally
became a limit on how far into the past Frankie can reach.

Do **not** solve this by merely replacing 4,096 with 2.7 million. That would make late-month lookups repeatedly
scan and rehash the month from genesis. Replace the access architecture:

1. Retain the complete immutable causal journal and raw MBO indefinitely according to the project's storage
   policy. Summaries and compaction are secondary indexes, never replacements for exact evidence.
2. Build a content-addressed index mapping causal sequence and event/availability timestamp to byte offsets,
   plus candidate/chain IDs to their exact source spans.
3. Add periodic authenticated checkpoints so a query can verify the requested chain segment and its ancestry
   without rescanning from genesis every time.
4. Allow `prior_causal_state` and `prior_causal_delta` to address any sequence not later than the bound causal
   prefix. Remove the fixed history-reach maximum.
5. Add reverse/timestamp windows and paginated cursors. Bound each response's event count and serialized bytes,
   but never bound which lawful historical timestamp can be requested.
6. Keep hot indexes for the active session/month and durable cold indexes for older history. Older exact raw
   evidence must remain retrievable by content hash.
7. Return explicit `next_cursor`, searched coverage, source hashes, checkpoint identity, and omissions so
   Frankie can continue reading until satisfied.
8. Test early-, middle-, and late-month retrieval, including the final October second, and prove exact equality
   with a genesis scan on a small frozen fixture. Use only focused tests after the design is agreed.

The desired invariant is **unlimited lawful recall reach, bounded response size**. Direct model context remains
finite for attention quality, but Frankie must be able to retrieve any prior causal state or raw event through
tools without silent truncation.

## Verified AWS evidence — no Step-1 rerun

The isolated read-only workflow
`.github/workflows/frankie_october_aws_readonly_probe_20260824.yml` ran at review commit
`cdb205913754bedfc0b3ccd65fe350e3d8bbabab`.

- Workflow run: `32770498473`
- Job: `97569534930`
- Conclusion: `success`
- Raw S3 object count: 26
- Raw S3 total bytes: 535,712,025
- Manifest totals match: true
- Progress receipt key: present, 20,604 bytes
- Progress heartbeat key: present, 2,725 bytes
- Cancelled sharded monolithic-reference receipt/seconds keys: absent, as expected because its archival job
  never ran
- Worker SSM status: `Success`, response code 0
- Frozen `_resumable_segment_receipt` validator: `PASS`
- Existing seconds file: 112,852,940 bytes
- Seconds SHA-256: `93654eb5eaf24be6dc6821f422cdd7fc416e12778dcecd6c97150cbc34004f90`
- Receipt file SHA-256: `80b6cf7199805cf40a0b16b139ee1aa8f705b884acf03856640df4054802f7ab`
- Canonical receipt SHA-256: `4966dac8b25fee7acabf53f880a30155985bd5767ee222381f1188d4eecada3c`
- Heartbeat and worker log: present

The probe retrieved no raw data, seconds, receipt body, heartbeat, or log contents. It made no provider call,
ran no Step-1 science, and launched no October process.

The October monolithic child is therefore validated as complete. The broader three-month finalizer products,
52-week out-of-time folds, crosswalks, populations, classifications, and lineage bundle are not proven
available. Do not describe those broader products as complete. If absent, show that absence to Frankie.

## What the prior bounded run proves

No successful bounded three-month Frankie scientific run exists. All four attempts failed before a provider
response because of infrastructure/configuration faults. The intended prompt asked Frankie to evaluate generic
candidate events and did not explicitly direct it to find exhaustion, D, dipole, chain, or curve structures.
Therefore the earlier “no D” impression is not evidence that Frankie cannot detect them, and it is not a valid
test of context overload.

## Next-chat sequence

1. Read the canonical monthly procedure and this handoff in full.
2. Inspect the isolated review branch and exact read-only probe evidence. Do not modify the protected branch.
3. Build a content-addressed complete-suite input/availability receipt. Fail closed on any silent omission.
4. Present the full inventory and accessible contents to both Frankies. Ask each what it wants direct,
   tool-accessible, and excluded, and why. Preserve everything for retrieval.
5. Agree with the user on the two role contracts, provider model(s), exact prompt(s), call count/cost, and
   whether this first pass is architecture consultation, October retrospective analysis, or both.
6. Retrieve or process AWS data only through an explicitly approved secure path. Do not place private raw
   data or receipt bodies into GitHub artifacts without the user explicitly approving that transfer after the
   destination, size, and retention are stated.
7. Correct the recent-history/raw-event retrieval defect with the smallest reviewed change and focused tests
   before judging Real-Time Frankie.
8. For the revealed October retrospective, show the verified Step-1 seconds/receipt beside the exact causal
   state, book/event windows, curve state, and Frankie's candidate output. Missing broader products stay
   `UNKNOWN`.
9. Do not relaunch October, rerun Step-1, call a provider, alter the accepted four-CPU production path, or run
   broad tests without a new explicit preflight agreement.

## Untouched areas

- Protected branch and commit remain unchanged.
- October attempt 8 remains stopped and unauthorized.
- Accepted four-CPU production implementation remains unchanged.
- No candidate Nucleus/ReFRAG/Quantum/Nova repository was selected, rebuilt, or modified.
- No raw or Step-1 file contents were moved out of AWS.
- No provider/model call was made.
