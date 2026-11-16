# BuildMap — Competitive Research & Product Strategy Handoff

**Date:** 2026-10-13  
**Status:** Product-direction handoff, not an implementation report.  
**Source:** BuildMap competitor research and follow-up product discussion.

## Audience and positioning

BuildMap focuses on beginner-to-intermediate builders, especially people using coding agents who lack architecture confidence and need help controlling project drift and bloat. The value proposition is: **understand what you are building, see what is actually done, and know what to build next.**

## Competitor research snapshot (2026-10-13)

| Product | Availability and pricing | Audience / strengths | Limitations and review evidence |
| --- | --- | --- | --- |
| [DepsView](https://marketplace.visualstudio.com/items?itemName=depsview.depsview) | VS Code extension; free/MIT; no verified paid tier | Developers and agent-assisted coders; live dependency mapping, impact and circular-import insights | Import/dependency view is not a complete goal-driven build guide; sparse independent complaint evidence |
| [Mellos Mapping](https://github.com/GuangminJu/mellos-mapping) | Open-source/MIT; no verified paid tier | Claude Code/Codex and terminal-based builders; ghost design, dependency layers, evidence-backed progress | CLI/plugin learning curve. Firsthand GitHub issues: [plugin schema](https://github.com/GuangminJu/mellos-mapping/issues/7), [Linux pane](https://github.com/GuangminJu/mellos-mapping/issues/8), [Node/Windows lock](https://github.com/GuangminJu/mellos-mapping/issues/26), [stale docs](https://github.com/GuangminJu/mellos-mapping/issues/27). Reports do not establish current unresolved status. |
| [GitKraken Codemaps](https://gitkraken.com/features/code-dependency-mapping) | In-development/early-access messaging; standalone price and free entitlement unverified | Developers and teams; architecture visualization, interactive tours, onboarding | Direct walkthrough overlap; limited Codemaps-specific independent reviews. CodeSee was acquired by GitKraken. |
| [Swimm](https://swimm.io/) | Available; [pricing](https://swimm.io/pricing) is sales-led/custom and based on code volume | Enterprise teams, legacy modernization, knowledge/documentation | Older G2 reports include imperfect AI answers, noisy PR comments, search and plugin friction. Historical G2 $0/$16/$28 tiers are **not verified current**. [Reviews](https://www.g2.com/products/swimm/reviews) |
| [testdart](https://www.testdart.com/) | [Pricing](https://www.testdart.com/pricing): free one-project manual tier; Standard advertised $49/user/month; Premium custom | Startups, QA and developers; requirements-to-tests, browser execution, test reports | Primarily QA, not architecture; sparse independent complaints. Verify pricing before quoting customers. |

**Research caveat:** These are publicly available findings, not hands-on comparative usability results. Lack of reviews is not evidence of customer satisfaction. Competitors can serve beginners; maps, agent integrations, evidence tracking and tours are not unique inventions.

## Product decisions

1. **Preserve the complete original visual map free.** Do not strip existing free functionality.
2. **Recommended and conversationally endorsed direction:** blend the *current* goal-first walkthrough into the free experience. Keep ordered pieces, plain-English purpose, intended final product/behavior, known evidence, gaps and first unfinished point available for free.
3. **Keep “Keep Your Agent Focused” and basic “Copy task brief” FREE.** The free tier retains drift/bloat findings, relevant files, bounded task scopes and existing manual copy workflow. These are core to the product promise.
4. **Proposed paid tier: BuildMap Guide.** Charge for deeper, ongoing project-specific help that turns map understanding into a guided build-and-review process. This is the agreed strategic direction, **not yet implemented or billed**.

## Free versus Paid boundary

| BuildMap Free | Paid: BuildMap Guide |
| --- | --- |
| Complete visual map, file inventory, search and source/evidence inspection | Everything in Free |
| Current walkthrough and project goals / intended finished experience | Interactive code-level walkthrough: functions, execution/data flow, dependencies explained plainly |
| Planned versus observed/verified states; gaps and drift findings | Guided next-step coaching and deeper implementation planning |
| First unfinished point and basic bounded copyable agent task briefs | Detailed agent instructions with acceptance criteria and change-impact preview |
| Manual refresh, snapshots and existing APIs | Post-agent change review against intended scope, guided verification and evidence explanation |
| “Keep Your Agent Focused” findings | Project continuity across sessions: what changed, what remains and where to resume |

**Differentiation:** Free helps users understand their project. Paid helps them build and finish it correctly. The paid tier should not merely be another tour, a longer description or a copy button.

## Paid flagship: Guided Build Loop

1. **Understand** the goal and current evidence-backed state.
2. **Prepare** a bounded next task, including relevant code, dependencies, constraints and acceptance criteria.
3. **Build** using the user's preferred coding agent; BuildMap need not become a separate coding agent.
4. **Review** the actual changes and recorded evidence; agent assertions are not proof.
5. **Continue** with refreshed state, session continuity and the next unfinished piece.

## Implementation priority (proposal, not authorization)

1. Blend current walkthrough into Free without regressing map/evidence/tasks.
2. Introduce deeper code explanations as the first Paid increment.
3. Add guided task preparation, impact analysis and post-agent review.
4. Add session continuity and guided verification.

Avoid unrelated orchestration, extra validation infrastructure or an in-house coding agent. Preserve distinctions among declared, source-connected, computed, verified and observed-live states. Do not imply a result is proven without evidence.

## Pricing and validation

No BuildMap price or billing basis has been selected. Test affordable individual pricing and billing per project, per builder or subscription with actual users. A useful competitor comparison test is to ask beginner and intermediate builders to identify project goals, next unfinished work, unsupported completion claims and an appropriately bounded agent task in the same repository.

## Repo context and instructions for Work

Repository: [DavisAI1974/BuildMap](https://github.com/DavisAI1974/BuildMap), [PR #1](https://github.com/DavisAI1974/BuildMap/pull/1), branch `feat/buildmap-v1-living-map`.

The existing MVP PR describes both Map and Walkthrough as accessible in preview, with billing/access enforcement deferred; it documents browser restrictions and incomplete browser proof. **Fetch CURRENT HEAD and preserve newer commits** before any future work. Read `NEXT_CHAT_HANDOFF.md`, `README.md`, `BUILD_GAPS.md`, `REVIEW_NOTES.md`, `.buildmap/project.json` and `.buildmap/evidence.json`. Treat repo/tests as source of truth, not this strategy document as implementation proof.

This research/handoff does not authorize deployments, merges, feature implementation or paid-tier claims.
