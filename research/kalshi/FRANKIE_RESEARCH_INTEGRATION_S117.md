# Frankie Research Integration Addendum — S117

Greg explicitly approved incorporating the following additional research into Frankie even if every paper is not confirmed as one of the originally missing Claude-session links.

## Integrated papers and responsibilities

### Self-Improvements in Modern Agentic Systems: A Survey — arXiv:2607.13104

Frankie now treats the operational scaffold as explicit mutable surfaces rather than one opaque prompt. The allowed surfaces are strategy, skills, playbook, reasoning prompt, analog retrieval, research tools, data contracts, test harnesses, the Novel candidate registry, and calibration reports. Safety-kernel, credential, deployment, CI, risk, and execution surfaces are not mutable by Frankie.

### Adaptive Auto-Harness — arXiv:2606.01770

Frankie now has the abstraction needed for a harness tree: every harness candidate carries a `task_route`, so prediction-market, settlement-structure, weather, revision-vintage, options, physical-gas, or future task families can evolve independently instead of forcing one repeatedly rewritten universal harness. Human-steering notes are first-class for regimes where history is inadequate.

No routing weights or fitted classifier are introduced. Route identity is explicit and preregistered.

### Recursive Self-Evolving Agents via Held-Out Selection — arXiv:2606.28374

Each candidate harness carries three compact state layers:

- strategy;
- reusable skills;
- procedural playbook.

A candidate may not become release-eligible unless the held-out split was precommitted. The release gate uses exact per-case pass/fail outcomes rather than a fitted score. Any pass-to-fail regression rejects the candidate, and a candidate must produce at least one fail-to-pass correction to qualify as `SANDBOX_RELEASE_ELIGIBLE`.

### MOSS — arXiv:2605.22794

Frankie now distinguishes text/scaffold changes from source-affecting research-harness changes. Source-affecting candidates are allowed only for bounded research surfaces such as research tools, test harnesses, or analog retrieval, and they require an isolated trial worker before release eligibility.

Frankie still cannot apply source changes himself. Production application remains outside the process and requires a human-reviewed Git release.

### AgentDevel — arXiv:2601.04620

Frankie now uses flip-centered release accounting:

- `PASS_TO_FAIL` — first-class regression; automatic rejection;
- `FAIL_TO_PASS` — verified correction;
- `UNCHANGED_PASS`;
- `UNCHANGED_FAIL`.

The design retains one canonical version line rather than uncontrolled branching populations. Candidate generation and release authority remain separate.

## Code

The implementation lives in:

```text
research/kalshi/frankie_evolution.py
research/kalshi/tests/test_frankie_evolution.py
```

The research manifest is now `READY` with nine reviewed papers. Four are confirmed from Greg's Claude discussion and five are explicitly approved supplemental grounding. The original screenshot search remains open for any additional papers, but it no longer blocks hybrid research operation.

## Release invariant

The evolution layer can produce only:

```text
REJECT
SANDBOX_RELEASE_ELIGIBLE
```

It never produces LIVE, EXECUTE, DEPLOY, or APPLY authority.

A clean candidate requires all of the following simultaneously:

```text
held-out split precommitted
required deterministic tests passed
isolated trial worker when source-affecting
zero PASS_TO_FAIL flips
at least one FAIL_TO_PASS flip
execution_enabled = false
apply_allowed = false
```

No threshold, coefficient, model weight, or post-hoc scoring rule is fitted by this gate.
