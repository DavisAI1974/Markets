# ChatGPT Handoff — S117 Agent Frankie

**Branch:** `chatgpt/agent-frankie-s117`  
**Base:** `chatgpt/novel-edge-lab-s116`  
**Entry point:** `research/kalshi/agent_frankie.py`  
**Date:** 2026-08-06

## Greg's request

Build the hybrid agent discussed with Claude, mix that plan with ChatGPT's trading-agent design,
prepare him for AWS, call the new file `agent_frankie`, and use the old agent spawner as the jumping-off
point without modifying the original.

Greg approved bounded self-improvement: Frankie may learn, propose and test changes, but may not silently
rewrite production code or grant himself execution authority.

## Private Claude-session limitation

The supplied Claude Code URL is login-gated from this build environment:

```text
https://claude.ai/code/session_01XASwGBJCADah3Tb8GssvLJ
```

The exact linked paper titles and URLs could not be retrieved. They were not guessed. Frankie therefore
contains a hard paper-manifest gate at:

```text
research/kalshi/frankie_paper_manifest.json
```

Hybrid paper-grounded evaluation is blocked until the exact paper records are exported and the manifest
is reviewed as `READY`. Deterministic observation is usable before that.

## Original `spawn.py` preserved

`research/kalshi/spawn.py` was not edited.

Frankie verifies the original Git blob before every origin-sensitive action:

```text
2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e
```

`agent_frankie.py legacy ...` delegates directly to the original script after verification. This retains
its lookup-only slots, unresolved-slot stop rule, calendar facts, leakage gates, role-scoped brain views,
bridge dependencies and canonical SOP templates.

## Built architecture

### Deterministic layer

- point-in-time event schema and timezone checks;
- immutable source provenance and content hashes;
- exact/mapped contract-identity gate;
- causal-clock and source-freshness gate;
- payoff-neutral structures require exact payoff identity;
- known-cost state tracked separately;
- registered Novel candidate required;
- all outputs force `execution_enabled=false`.

### Hybrid reasoning layer

Two independent lanes read the same frozen event:

1. causal scientist — mechanism, paper transfer, revision vintage, alternatives and falsifiers;
2. trading mechanics — exact contracts, month/source/clock basis, balance mode, fees, liquidity and legging.

The lanes do not vote or average. A disagreement becomes `HUMAN_REVIEW`; a rejection remains a rejection.
The strongest state is SHADOW.

### AWS worker

- SQS long-poll consumer;
- optional SNS-wrapped event decoding;
- message deletion only after evidence write;
- queue redrive/DLQ handles poison messages and model failures;
- Bedrock Converse primary lane in `us-east-1`;
- optional independent OpenAI Responses critic;
- local append-style evidence plus optional S3 evidence write;
- hardened systemd service and canary-first installer.

### Self-improvement

Frankie can:

- write immutable resolved-outcome sidecars;
- collect recent resolved evidence;
- diagnose one repeated failure pattern;
- propose one bounded change;
- submit the proposal to an independent critic;
- emit a `SANDBOX_ELIGIBLE`, `REVISE` or `REJECT` proposal artifact.

Frankie cannot:

- apply a patch;
- edit or replace `spawn.py`;
- touch credential, authentication, risk or execution files;
- create a Git branch, commit or PR;
- learn from unresolved records;
- change thresholds after seeing a holdout;
- grant execution authority.

At least one cited evidence record must have an immutable resolved-outcome sidecar before an improvement
proposal passes deterministic validation.

## Files added

### Agent

- `research/kalshi/agent_frankie.py`
- `research/kalshi/frankie_core.py`
- `research/kalshi/frankie_backends.py`
- `research/kalshi/frankie_engine.py`
- `research/kalshi/frankie_improve.py`
- `research/kalshi/frankie_reflect.py`
- `research/kalshi/frankie_reflect_runner.py`

### Contracts and grounding

- `research/kalshi/frankie_event_schema.json`
- `research/kalshi/frankie_outcome_schema.json`
- `research/kalshi/frankie_paper_manifest.json`
- `research/kalshi/FRANKIE_ARCHITECTURE_S117.md`

### AWS

- `deploy/aws/markets-frankie.service`
- `deploy/aws/markets-frankie-reflect.service`
- `deploy/aws/markets-frankie-reflect.timer`
- `deploy/aws/install_frankie.sh`
- `deploy/aws/requirements-frankie.txt`
- `deploy/aws/frankie.env.example`
- `deploy/aws/frankie_iam_policy.example.json`
- `deploy/aws/FRANKIE_AWS_SETUP_S117.md`

### Validation

- `research/kalshi/tests/test_agent_frankie.py`
- `.github/workflows/agent_frankie_ci.yml`

## Commands

```bash
cd research/kalshi
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

Nightly bounded reflection uses:

```bash
python frankie_reflect_runner.py --limit 50 --min-resolved 5
```

## Rollout order

1. merge/deploy the Novel Edge Lab dependency;
2. export the exact paper links from the Claude session into the paper manifest;
3. run CI and `agent_frankie.py selftest`;
4. create SQS queue plus DLQ and least-privilege instance policy;
5. install Frankie but keep `FRANKIE_DETERMINISTIC_ONLY=1`;
6. collect deterministic WATCH/REJECT evidence;
7. verify Bedrock and OpenAI one-shot structured results;
8. move to hybrid SHADOW;
9. record resolved outcomes;
10. enable the reflection timer only after at least five resolved records;
11. review every sandbox proposal through the ordinary Git PR process.

## Not built by design

- no venue order API;
- no tastytrade or Kalshi execution credentials;
- no live risk service;
- no browser authority;
- no automatic Git mutation;
- no use of private chat content as uncitable memory;
- no LLM in the hot market-data path.
