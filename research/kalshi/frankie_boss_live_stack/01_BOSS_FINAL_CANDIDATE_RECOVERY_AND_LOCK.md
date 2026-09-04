# BOSS final-candidate recovery and architecture lock

Date: 2026-09-04

Decision status: Accepted as the engineering target. Not accepted as production-ready.

## Question resolved

The question was whether the fourth and final BOSS concept could be recovered from a fuzzy recollection: a mixture of the native design, an IBM component, ReFRAG, and a dipole teacher, without Nucleus.

The answer is yes, with one naming qualification. The repository does not contain a literal `V4` label for this design. The strongest direct evidence is the accepted eight-arm raw-MBO benchmark matrix, which states:

- `B0`: fixed-depth native BOSS;
- `B1`: BOSS plus whole-representation recurrent reasoning, no Granite;
- `B2`: recurrent BOSS plus Granite 4.2 8B reasoning assistance;
- clean and memory variants for each relevant arm;
- `B2` is the intended full BOSS arm, while B0 and B1 are controls.

The matching record is `research/kalshi/frankie_boss/FRANKIE_RAW_MBO_BENCHMARK_NEXT_CHAT_HANDOFF_20260828.md` on `codex/frankie-boss-raw-mbo-benchmark-20260828` at inspected tip `38b37c4323a027b21b5ca65627daf294a1481541`.

This is therefore a confidence-qualified recovery: component match is high; literal version-number evidence is absent.

## Final target in one sentence

`B2` is the current Frankie design with its memory preserved, connected through the existing BLD-1 seam to a causal native-MBO BOSS whose native recurrent reasoning is market-authoritative, whose QSV/operator surface is governed by ReFRAG, whose dipole geometry is tested as controlled auxiliary supervision, and whose Granite 4.2 8B layer begins as bounded shadow reasoning assistance.

## Component authority and current readiness

| Component | Intended role | Repository evidence | Current status |
|---|---|---|---|
| Current Frankie | Controller, memory user, final public BLD-1 behavior | Active branch and S127 frozen run | Built and proven on Sunday without BOSS |
| A-memory | Existing learned memory package | Frozen principal run and memory contracts | Preserve exactly; do not rewrite |
| Causal packet | Point-in-time audit object, hashes, provenance, defects | `causal_packet.py` | Built |
| Native fixed-depth trunk, B0 | Typed market baseline and control | `trunk.py` | Built; historical tests exist |
| ReFRAG/QSV | Named operator registry, governance, optional QSV stream | `research/refrag/`, `qsv_registry.py`, trunk QSV seam | Built; dormant by default and ablatable |
| Temporal graph | One shared ancestry/venue/instrument branch | `TemporalGraphBranch` | Built; exactly one module; executable code applies it once before the layer loop |
| Gated delta memory | Within-sequence temporal state | `GatedDeltaCell` | Built; resets each forward call; not reasoning depth |
| Dipole teacher | Controlled auxiliary target experiment | `teacher.py` | Harness built; real data contract and credible result absent |
| State serializer | Deterministic typed state to canonical text boundary | `state_serialization.py` | Built; mechanical tests reported |
| Restart/checkpoint contract | Resume large raw-MBO experiments | `benchmark_checkpoint.py`, `mbo_resume_state.py`, raw manifest | Built in source branch; needs current-branch preservation verification |
| Whole-representation recurrence, B1 | Repeated reasoning over the complete representation | Governing inventory and benchmark record | Specified, not implemented |
| Compute halting | Bounds or adapts B1 reasoning depth | Governing inventory | Missing contract and implementation |
| Granite 4.2 8B, B2 | Frozen reasoning assistant/teacher/critic over serialized state | Granite candidate record | Researched and specified, not wired or invoked |
| BLD-1 projector | Maps only four governed learned values into Frankie | `frankie_contract.py` | Built; must stay narrow |
| Broker execution | Tastytrade for futures/options and Kalshi for event contracts | User decision plus official APIs | Platform APIs exist; Frankie adapters and live gates are separate work |

## Important correction: what is and is not already built

It is accurate to say that much of the BOSS foundation and the dipole teacher harness were already built. It is not accurate to say the final B2 system is executable today.

Three missing links prevent that claim:

1. B1 recurrent reasoning does not exist. `GatedDeltaCell` is temporal memory across sequence positions inside one forward call. It is reset on every call and is not a whole-model reasoning loop.
2. Granite is not connected. The serializer exists, but no approved model download, runtime, checkpoint identity, prompt contract, output parser, repeatability policy, or BOSS adapter exists.
3. The dipole teacher lacks the governed real-MBO target builder and real-data validation required to mean what its name implies.

The architecture can be locked now. Production readiness cannot.

## Native, IBM, ReFRAG, and dipole responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| Native Frankie | Memory retrieval, role coordination, final BLD-1 response and disposition | Raw exchange-book reconstruction or unreceipted model facts |
| Native BOSS | Causal typed state, market representation, recurrent reasoning state, calibrated internal heads | Provider-specific chat orchestration or broker credentials |
| ReFRAG | QSV/operator names, ordering, registry, operator lifecycle/governance | A second Frankie memory or duplicate BOSS head mapping |
| Dipole teacher | Experimental representation targets and their falsification controls | Ground truth by declaration, execution authority, or live inference dependency |
| Granite 4.2 8B | Generic structured reasoning assistance over an explicit serialized snapshot | Market truth, raw-MBO reconstruction, memory mutation, confidence authority, or order submission |
| BLD-1 seam | Four explicitly governed learned values crossing into Frankie | Any additional hidden head, free-form chain of thought, or raw Granite score |

## Current Frankie and the Opus question

The inspected active provider contract does not pin Opus 5. `research/kalshi/frankie_full_stack_runtime_contracts_20260824.py` sets:

`EXPECTED_MODEL = "gpt-5.6-sol"`

The S127 Sunday run is documented as an agent session over committed files rather than an API runner. Searches of the active `agent_frankie.py`, `spawn.py`, runtime adapter, and runtime contract found no executable Opus model selection. Occurrences of Claude or Opus in commit attribution, historical handoffs, or session links are provenance, not runtime calls, and must not be stripped.

The later integration should replace or route only an actual executable provider dependency. It should not delete historical attribution or search-and-replace every mention of a model name.

## Brownfield integration boundary

The user chose to clone the currently running Frankie after the Sunday run and leave memory A as-is. Sunday is now complete and frozen at active branch commit `bc8c4fd728036cdc7cedf8d1b9427f58853f2e6c`.

The safe brownfield sequence for a later implementation tranche is:

1. Resolve the current S128 result self-hash defect and cadence defects on the active lineage without touching the frozen Sunday directory.
2. Create an isolated integration branch from the then-current, verified Frankie head. Record its parent SHA.
3. Compare the BOSS source branch against that parent file by file. Import only additive BOSS/ReFRAG modules and their tests; do not overwrite active Frankie files wholesale.
4. Re-run the current Frankie preservation suite before wiring any new call.
5. Wire B0 behind a new typed adapter at the existing BLD-1 boundary. Keep B0 disabled by default and prove that disabled behavior is byte-identical to the protected baseline.
6. Add B1 beside B0 with shared-weight recurrent reasoning and an explicit state/halting contract. B0 remains unchanged as the control.
7. Add the dipole experiment to training only after its target schema and controls are repaired.
8. Add Granite as a separately switchable B2 shadow lane through the deterministic serializer. It cannot be a hidden dependency of B0 or B1.
9. Add broker adapters only after model evaluation. Broker code receives a signed, bounded order intent from a deterministic risk gate, not free-form model output.
10. Promote one stage at a time: replay, shadow live, paper execution, bounded live execution.

## Four-date scientific partition

The accepted starting roster remains:

| Date | Role | Allowed use |
|---|---|---|
| 2021-10-01 | Warmup/development | Input-builder, serializer, recurrence, and Granite mechanical probes |
| 2021-10-03 | Warmup/development | Independent warmup validation; Sunday principal artifact is never rewritten or rerun merely for this work |
| 2021-10-04 | Held-out blind | Frozen paired evaluation only after all warmup gates pass |
| 2021-10-05 | Held-out blind | Frozen paired evaluation only after all warmup gates pass |

Two held-out days can expose catastrophic mismatch and compare paired behavior. They cannot establish a durable trading edge, a stable learning curve, or production readiness.

## Memory isolation

The `clean` and `memory` arms must use identical code, source data, clocks, model identities, and thresholds. Their only allowed difference is the exact predeclared memory package.

Memory rules:

- Current A-memory remains immutable evidence.
- A BOSS run may read a hash-bound copy or reference; it may not rewrite it in place.
- BOSS findings are written to a new result namespace.
- Granite never writes memory directly.
- No current arm sees another current arm's output before all relevant locks freeze.
- A later promotion process may merge accepted findings only through the existing governed memory mechanism.

## Runtime failover lock

Even after Granite passes research gates, live execution must remain able to operate in `B1_ONLY` or safe-abstain mode when Granite is unavailable, late, malformed, or inconsistent.

The failover decision is deterministic:

| Condition | Required behavior |
|---|---|
| Granite response on time, schema-valid, receipt-valid, and within disagreement policy | Record it; allow the governed fusion policy to consider it only after promotion |
| Granite timeout | Continue B1 or abstain according to predeclared risk policy; never wait without bound |
| Granite schema/hash mismatch | Reject Granite contribution and emit a defect |
| Granite contradicts causal state | Preserve disagreement; native state remains authoritative |
| B1 unavailable or state invalid | Complete safety abstention; Granite cannot substitute for missing market state |

## Acceptance statement

The architecture target is `B2_GATED`: native causal BOSS plus ReFRAG/QSV and a validated dipole training path, with native B1 recurrent reasoning as the required core and Granite 4.2 8B retained as a bounded reasoning assistant. Nucleus is excluded. Granite is initially shadow-only and cannot place orders or become a live dependency until the named gates pass.

This lock preserves the original final design while avoiding the central engineering mistake the brownfield evidence warns about: treating an unfinished experimental seam as if it had already been trained, evaluated, and promoted.
