# Frankie Hybrid Agent Architecture — S117

**Entry point:** `research/kalshi/agent_frankie.py`  
**Protected origin:** `research/kalshi/spawn.py`  
**AWS posture:** headless worker; deterministic canary first; no execution authority  
**Self-improvement:** evidence-driven proposals only; no automatic code application

## 1. What Frankie is

Frankie combines three existing DavisAI Markets systems without collapsing their boundaries:

1. **The original specialist system** — `spawn.py`, the static specialist files, the role-scoped
   brain views, the calendar/Jidoka gates, and the sequenced E -> A -> B dependency chain.
2. **The forward-curve architecture** — project conditions, reason to behavior, retrieve or
   construct the session shape, re-anchor level, then monitor slope/direction for adjust or scrap.
3. **The Novel trading agent** — exact contract identity, information clocks, cross-market
   probability structures, revision vintages, balance modes, costs, and falsification.

Frankie is not an LLM placed in a hot execution loop. He is a hybrid system:

```text
market/data collectors
        -> deterministic event qualification
        -> independent causal-scientist lane
        -> independent trading-mechanics lane
        -> deterministic adjudication
        -> WATCH_ONLY / SHADOW / REJECT / HUMAN_REVIEW
        -> immutable evidence + resolved outcome sidecar
        -> bounded self-improvement proposal
        -> independent proposal critic
        -> human-reviewed sandbox PR
```

## 2. `spawn.py` remains untouched

Greg required the new file to be called `agent_frankie.py` and the old spawner to remain
unchanged. Frankie does not copy the implementation into a second drifting source.

At every run he computes the actual Git blob identity of `research/kalshi/spawn.py` and requires:

```text
2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e
```

If that identity changes, Frankie stops. The change must be reviewed and the pin deliberately
updated. The command below delegates to the original process after verification:

```bash
python agent_frankie.py legacy emit BLD-1 g23 --day 20260715
```

That retains the original lookup-only slots, calendar facts, leakage checks, role-scoped brain
views, bridge dependencies, immutable SOP templates, and unresolved-slot stop rule.

## 3. Two independent reasoning lanes

### Causal-scientist lane

Owns:

- physical or contractual mechanism;
- causal ordering and point-in-time knowability;
- revision vintage;
- paper-to-market transfer;
- alternative explanations;
- preregistered falsifiers;
- whether evidence is sufficient to continue researching.

It does not decide execution economics.

### Trading-mechanics lane

Owns:

- exact market and instrument identities;
- futures month and options underlying;
- settlement source, field, time, inequality, and fallback;
- source/clock basis;
- balance mode;
- fees, spread, slippage, hedge cost, liquidity, and legging;
- whether a qualified structure belongs in WATCH_ONLY or SHADOW.

It does not infer causality from a price correlation.

### Adjudication

The lanes do not vote and are never averaged.

- any deterministic gate failure -> `REJECT`;
- any lane rejects -> `REJECT`;
- insufficient evidence -> `HUMAN_REVIEW`;
- disagreement on state or balance mode -> `HUMAN_REVIEW`;
- agreement on SHADOW with known costs and complete paper grounding -> `SHADOW`;
- missing costs or incomplete paper manifest caps the result at `WATCH_ONLY`.

Every result contains `execution_enabled=false`.

## 4. Paper grounding

The Claude Code session supplied by Greg is private/login-gated from the build environment:

```text
https://claude.ai/code/session_01XASwGBJCADah3Tb8GssvLJ
```

Therefore the exact linked research papers have not been guessed or reconstructed. They live in:

```text
research/kalshi/frankie_paper_manifest.json
```

Until that manifest has `status: READY` and at least one reviewed paper record, hybrid reasoning
stops by default. Deterministic observation can run, but paper-grounded SHADOW cannot.

Each paper entry must contain:

```json
{
  "id": "stable-id",
  "title": "Exact paper title",
  "url": "Exact URL",
  "claims": ["Specific claim Frankie may rely on"],
  "why_it_matters": "How the claim maps to Frankie's architecture or market mechanism",
  "source_hash": "Optional archived-source hash"
}
```

A model may cite only manifest IDs. Unknown citations fail schema validation.

## 5. Event contract

Input schema:

```text
research/kalshi/frankie_event_schema.json
```

Every event must include:

- `event_id` and registered `candidate_id`;
- `knowable_at` and `observed_at` with time zones;
- immutable source provenance and content hashes;
- contract identity state;
- market state;
- causal-clock and source-freshness state;
- actual cost readiness;
- `execution_enabled=false`.

`PAYOFF_NEUTRAL` candidates require `contract_identity.status=EXACT`. A semantic or mapped
near-match cannot be treated as payoff-neutral.

## 6. AWS runtime

Frankie is designed for the existing durable AWS Markets host or a later ECS/Fargate container.
The first deployment target is the existing EC2/systemd pattern.

```text
EventBridge / collectors
        -> SQS Frankie events queue
        -> markets-frankie.service
        -> local /var/lib/markets/frankie evidence
        -> optional S3 frankie/evidence prefix
        -> CloudWatch/journald
```

The SQS message body is one `frankie_event_schema.json` object. SNS-wrapped messages are accepted.
A message is deleted only after evidence has been written. Invalid messages and backend failures
remain for the queue redrive/DLQ policy.

AWS Bedrock uses the Boto3 `bedrock-runtime.converse` API. AWS recommends Converse for supported
models because it provides a consistent messages interface:

- https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started-api-ex-python.html

The optional independent OpenAI lane uses the server-side Responses API:

- https://platform.openai.com/docs/quickstart

Neither backend receives tools, shell access, credentials, or an order router.

## 7. Deployment modes

### Phase 0 — deterministic canary

`/etc/markets/frankie.env`:

```bash
FRANKIE_DETERMINISTIC_ONLY=1
FRANKIE_EVIDENCE_ROOT=/var/lib/markets/frankie/evidence
FRANKIE_QUEUE_URL=<SQS URL>
```

Outputs only WATCH_ONLY or REJECT evidence. No LLM call is made.

### Phase 1 — hybrid SHADOW

Only after the paper manifest is READY and both model backends pass one-shot tests:

```bash
FRANKIE_DETERMINISTIC_ONLY=0
FRANKIE_PRIMARY_BACKEND=bedrock
FRANKIE_CRITIC_BACKEND=openai
FRANKIE_BEDROCK_REGION=us-east-1
FRANKIE_BEDROCK_MODEL=<approved model or inference profile>
FRANKIE_OPENAI_MODEL=<approved model>
```

The OpenAI key may use the existing `creds.get()` resolution and SSM fallback. The Bedrock lane
uses the existing AWS credential resolver and instance role pattern.

### Phase 2 — self-improvement proposals

After events resolve, write outcome sidecars:

```bash
python agent_frankie.py record-outcome EVIDENCE.json OUTCOME.json
```

Then propose one bounded improvement:

```bash
python agent_frankie.py improve EVIDENCE_1.json EVIDENCE_2.json
```

A proposal can become `SANDBOX_ELIGIBLE`, but Frankie cannot apply it.

## 8. Self-improvement rules

Frankie may improve:

- candidate registry descriptions and tests;
- reasoning prompts;
- analog retrieval;
- research tools;
- test harnesses;
- data contracts;
- calibration reports.

He may not propose changes to:

- `spawn.py`;
- credentials;
- Kalshi authentication;
- an order or execution router;
- risk gates or a live risk service;
- private-key or environment files.

The production loop is:

```text
observe
-> write immutable decision evidence
-> append immutable resolved outcome
-> diagnose repeated pattern
-> propose one bounded change
-> independent critic
-> sandbox branch and replay/null tests
-> untouched-forward SHADOW
-> human-reviewed PR
-> new version or rejection
```

No evidence or outcome is overwritten. Corrected outcomes must be a new correction record, not an
edit to the original sidecar.

## 9. Commands

```bash
python agent_frankie.py health
python agent_frankie.py verify-origin
python agent_frankie.py observe event.json
python agent_frankie.py evaluate event.json --primary bedrock --critic openai
python agent_frankie.py legacy emit BLD-1 g23 --day 20260715
python agent_frankie.py consume-once --deterministic-only
python agent_frankie.py serve
python agent_frankie.py record-outcome evidence.json outcome.json
python agent_frankie.py improve evidence1.json evidence2.json
python agent_frankie.py selftest
```

## 10. Deliberately not built

- no venue create/amend/cancel endpoint;
- no browser-held credentials;
- no automatic code patching or Git push;
- no automatic threshold fitting;
- no automatic candidate promotion;
- no pooling of NYMEX, Kalshi, options, or future venue ledgers;
- no use of the private Claude session as an uncitable knowledge source;
- no LLM in the market-data hot path.

## 11. S137 pre-V4 cognitive candidate layer

The 2026-08-20 whole-Frankie research pass is represented as ten independent SHADOW experiment
arms, not as one permanent rewrite. These are bounded schemas, validators, and pure helpers; they do
not implement the papers' complete cognitive behavior. `frankie_cognition.py` owns typed evidence
refs, explicit memory classes, reasoning-step and uncertainty validation, append-only invalidation,
declared transitive influence withdrawal, causal memory serving, and working-memory validation.
`frankie_cognitive_candidates.py` contains pure non-executing candidate helpers.
`frankie_cognitive_experiments.py` owns the matched-budget, stratified component gate and registry.

`frankie_s137_cognitive_runtime.py` is the isolated CURRENT FRANKIE adapter. The canonical S135
runtime remains the frozen control; the wrapper attaches exactly one selected candidate to its
packet, requires an evidence-bound candidate trace, delegates the original owner validation, and is
passed explicitly to the existing S135 freeze/reveal/score runner.

The live evaluation lanes now emit an auditable claim graph whose steps cite exact evidence-catalog
ids. The trace is evidence-bound but is not treated as ground truth or authority. Decision evidence
records the cognitive contract, catalog, and independent trace hashes.

`frankie_evolution.py` remains the later release boundary. It now also requires locked evaluators and
permissions, verified rollback, a one-shot aggregate-only release-holdout exposure audit,
untouched-forward completion, minimum evidence support, explicit task/regime/safety/provenance
strata, and zero catastrophic or protected regressions. The external judge canary can revoke grading
authority for order, length, or objective-truth bias, but cannot grant promotion authority.

See `FRANKIE_COGNITIVE_TOP10_IMPLEMENTATION_HANDOFF_20260820.md` and
`FRANKIE_COGNITIVE_TOP10_EXPERIMENT_MANIFEST_20260820.json`. Component tests do not authorize V4 or
permanent Frankie integration.
