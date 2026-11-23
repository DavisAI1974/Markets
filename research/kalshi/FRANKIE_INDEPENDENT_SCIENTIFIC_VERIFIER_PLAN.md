# Frankie independent scientific verifier — implementation plan

**Status:** PLAN ONLY, not implemented or deployed.  
**Owner/approval:** Greg decides when to authorize implementation or a result-bearing validation run.  
**Location:** DavisAI1974/Markets (code/design only); scientific evidence and result artifacts in DavisAI1974/markets-data, raw tick tape in S3.

## 1. Purpose

Borrow one **specific principle** from proof-checking multi-agent systems: the proposer of a claim must not be its sole verifier. An independent reviewer should challenge the claim, while deterministic checks establish what the evidence actually supports. This is **not** a plan to copy an 86-agent fleet, to train a language model, or to use Lean to declare an empirical market hypothesis proven.

Frankie already has independent reasoning lanes, leakage checks, evidence gates, falsification and review mechanisms on various branches. **First reconcile them.** The target is a thin extension that closes documented gaps, rather than a parallel research framework or an additional decision-making authority.

## 2. Non-negotiable boundaries

- Read current `CLAUDE.md`, `AGENTS.md`, working-branch handoff, and available implementation before design or code. Do not treat open PRs as merged or production-deployed.
- For the current ROOT rebuild, **research/strategy calculations use only trade days 2023-10-02, 2023-10-03, 2023-10-17, 2023-10-18**: 18:00 ET preceding evening through 17:00 ET named date. Outside data is permitted only to seat the continuous weekly order book. The 17:00-18:00 ET halt is retained as context, never used as an extra research day. Any other outside-data use requires Greg's decision before construction.
- Every original observation, distinct family, counterexample, contradiction, unexpected result and abstention survives. A refuted claim is **retained with its refutation**, not dropped. No averaging, truncation, smoothing or pooled headline obscures event/cell distinctions.
- Mandatory point-in-time leakage checks, input lineage, full original event/order identities, chronological order, causal clocks and order-book continuity remain intact. No synthetic trading data, including test fixtures.
- Research is gross only: no fees, slippage, fill models or imported crypto-era trading assumptions. No trading execution authorization or change to existing forecast logic.
- Launch is HOLD; this plan authorizes no Frankie, Granite, EC2, Pod, paid model call, GitHub workflow dispatch, or production run. Do not modify or disturb current sessions, saved checkpoints or sealed evidence.

## 3. Inventory and reuse — required first step

Inspect the **current working branch**, its deployment receipts, and these starting points where actually present:

- `odcore/leakage.py` and current upstream call sites.
- `CLAUDE.md` trading and falsification rules; `.claude/skills/kalshi-backtest/SKILL.md`; `.claude/skills/pr-and-review/SKILL.md`.
- Frankie S115/S117 independent-lane, event identity, typed posterior, narrative-gate, A-67/A-69 and FJ-1 machinery from open PR #8; distinguish implemented source from unexecuted real-data trials.
- The Adaptive Locality scientific controls, independent review, abstention/preservation logic and BuildMap evidence inspector from open PR #12; distinguish reviewed source from merged or running state.
- The canonical input/evidence manifests and continuation index in `DavisAI1974/markets-data`, especially any new ROOT rebuild receipts. Do not rerun already completed checks.

Produce a **reuse/gap matrix** for the requested branch: requirement, existing implementation (file:line + source SHA), tested status, deployment status, genuine missing behavior, and minimal extension. If the required capability already exists and works, **stop: no new agent is justified**.

## 4. Proposed architecture (only for uncovered behavior)

```text
Independent claim proposal
  -> immutable claim registration (exact source and code identities)
  -> deterministic admissibility checks (scope / provenance / causality)
  -> reviewer isolated from proposer's rationale and outcomes as appropriate
  -> counterexample and alternative-explanation plan
  -> authorized, reproducible checks using real historical evidence
  -> evidence-based comparison (no agent vote or score averaging)
  -> verdict with scope, limitations, conflicting evidence, and retained history
  -> human-reviewed disposition / downstream use (separate approval)
```

The deterministic verifier owns admissibility and computed equality; the independent reviewer owns critiques, alternative explanations and falsifiers. Neither reviewer nor model is allowed to rewrite source evidence, invent missing observations, approve a trade, or promote a claim just because several agents agree.

If current Frankie already owns a part of this flow, add a hook to it rather than a second producer, ledger or scheduler. This verifier should sit **after claim formation and before promotion of scientific confidence**, not in a tick-by-tick execution loop.

## 5. Contracts to design before implementation

### Claim registration

Each candidate needs a stable `claim_id` and immutable revision, author/proposer identity, plain-language hypothesis, exact mathematical/market claim, intended scope, per-event/per-cell boundaries, proposed mechanism and alternative explanations, code commit SHA, data-manifest hashes, all source event identifiers, both event/knowledge timestamps, current outcome visibility, and preregistered falsifiers.

Require explicit provenance of derived features and the exact source columns. Keep order IDs as attributes and traceable original orders, not invented scientific grouping conditions. Missing prerequisites produce **INADMISSIBLE_FOR_CHECK / RETAINED**, never silent exclusion.

### Check register

Each check has `check_id`, deterministic or model-assisted type, method and version, claim revision, input hash, executable/test location when relevant, scope/time boundary, expected observation, actual observation, reproducibility evidence, exceptions, and an independent reviewer identity. Evidence and analysis are different objects.

Support at least:
- Allowed-trade-day scope and continuous-book boundary checks.
- Causal-clock and future-data leakage checks, including the existing gate.
- Byte/hash and row/event identity integrity and no-drop/no-collision checks.
- Mathematical reproduction and suitable null/counterexample checks.
- Per-cell/per-event robustness, disagreements, negative controls and missing-observation accounting.
- Recovery of earlier failed/contradictory results rather than selecting one favored report.

Use machine-checkable proofs only for precisely formalizable **mathematical** propositions where the formalization is itself reviewed. Lean is optional, not a required dependency and not proof of empirical predictability.

### Verdict and evidence retention

Possible statuses: `PROPOSED`, `UNDER_REVIEW`, `SUPPORTED_WITHIN_SCOPE`, `REFUTED_WITH_EVIDENCE`, `INCONCLUSIVE`, `NEEDS_MORE_EVIDENCE`, `BLOCKED_INPUT_SCOPE`, `SUPERSEDED_RETAINED`.

Every verdict links its claim revision, all passing/failing checks, adverse cases, unresolved objections, exact scope, independent reviewer, deterministic evidence, and approval state. A new finding appends; it never overwrites a conflicting finding. A result is not "scientifically proven" merely because checks pass. No aggregate acceptance score, model majority vote or automatic promotion.

## 6. Implementation sequence (no execution yet)

**Phase 0 — gap inventory and architecture decision**
1. Compare current Frankie, scientific controls and BuildMap against section 3; identify owners and no-duplication boundaries.
2. Pick one insertion point for verification and one canonical claim/evidence register. Record which already-existing components remain authoritative.
3. Define a **stop rule**: no new module where existing mechanisms already satisfy the need.

**Phase 1 — schemas and adapters**
1. Define minimal versioned `claim`, `check`, `verdict`, and `adverse_evidence` contracts under the appropriate existing Markets module. Reuse existing field names/IDs where possible.
2. Build read-only adapters to canonical manifests, current leak gate, experiment lineage and existing FJ-1/independent-review records **only if missing**.
3. Keep outcome-bearing records blinded until the independent challenge/falsification plan is registered, when the research design requires a blind comparison.

**Phase 2 — deterministic checks**
1. Build strict provenance, duplicate/identity, temporal eligibility and order-book scope checks.
2. Verify allowed input selection routes through the current ROOT tape boundary; do not invent a second tape reader.
3. Compare computed outputs and event membership against immutable real-data receipts. Mark missing, corrupt, stale or conflicting data; never auto-fix source evidence.

**Phase 3 — independent scientific review**
1. Give the reviewer claim/specification + sealed admissible evidence, without feeding it the proponent's conclusions first.
2. Require at least one competing explanation, at least one falsifier, and the exact observation that would distinguish them.
3. Where calculations are separately authorized, reproduce or challenge with an independent method on the **same permitted inputs**; preserve every disagreement and explain any method mismatch.
4. Do not ask multiple LLMs to vote on correctness; deterministic evidence adjudicates, and unresolved interpretation goes to human review.

**Phase 4 — non-invasive pilot**
1. Select already-registered claims from the permitted four trade days, including accepted, adverse and unresolved cases, without cherry-picking.
2. Conduct a **read-only historical replay of saved results first**; no new expensive calculations without explicit approval.
3. Compare the new checker's findings with existing review. Record **incremental defects found, false alarms, avoided redundant checking, reviewer effort, and added cost/latency**. If no incremental improvement, do not keep the extra specialist.

**Phase 5 — decision and optional integration**
1. Review the measured value, scientific invariants and operational cost with Greg.
2. Only after authorization wire the minimal check at the existing claim-promotion boundary; no new daemon/fleet, automatic deployment or trading authority.
3. Leave an auditable rollback path that disables the checker without altering original evidence or scientific outputs.

## 7. Acceptance criteria

- No forbidden data enters research calculations; out-of-scope records remain preserved for order-book seating only.
- An inadmissible, future-leaking or missing-source claim cannot be labeled supported, while its records are retained.
- A deliberately contradictory **real archived** example is recorded with both sides; neither result is silently deleted or merged.
- Existing independently verified conclusions are not weakened by a new model opinion; unsupported claims remain qualified.
- The verifier identifies at least one meaningful gap not already caught by existing code **or** demonstrates equivalent coverage at lower measured cost; otherwise **do not ship**.
- Exact input/code/receipt identities reproduce for every reported check. No results, per-event observations or original family distinctions disappear.
- No AWS launch, model call, collector dispatch, CI-expensive push, production change, or strategy execution occurs without separately authorized action.

## 8. Deliverables when implementation is approved

1. Reuse/gap matrix with exact source references and an ownership map.
2. Minimal versioned claim/check/verdict schemas and focused adapters.
3. Deterministic checker plus independent-review procedure, where genuinely missing.
4. Real-evidence regression/negative/adverse cases and a before/after value assessment.
5. Short operating instructions and rollback/disable method.

**Current outcome:** This is a design proposal only. Nothing is integrated, dispatched, experimentally validated, or promoted as a new scientific conclusion.
