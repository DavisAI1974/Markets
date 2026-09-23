# Shipping review — digest, host preservation and inactive staging — 2026-09-23

Code candidate: 0b419436a100a3c189c58780c90cec981889c324 on codex/trading-day-readiness-20260922.
Decision: SOURCE_READY_FOR_INACTIVE_STAGING; LIVE_RUNTIME_AND_CYCLE_0_HELD.
The required scoped CI and parallel code, security and test reviews passed. No live dispatch, deployment, native move, ingestion replay, model call or cycle occurred.

## Scope and review

Remote [using-agent-skills](https://github.com/addyosmani/agent-skills/blob/0.6.8/skills/using-agent-skills/SKILL.md),
[shipping-and-launch](https://github.com/addyosmani/agent-skills/blob/0.6.8/skills/shipping-and-launch/SKILL.md)
and [/ship](https://github.com/addyosmani/agent-skills/blob/0.6.8/.claude/commands/ship.md) were applied.
Code, security and test personas reviewed independent portions concurrently. The host implementation author reviewed digest/staging tests, not their own host tests; code/security reviewers and root reviewed host code and behavioral evidence.
A new reviewer could not be created because the desktop thread store reported disk full, so existing agents were reused with explicit scope separation.

The source now:
- Streams pinned calculation-layer JSON through SQLite member/lifecycle/section sources, composes complete exact DIGEST_V6 files, independently inverts tables and hashes before proof, after proof and during assembly. Session.derive uses this path and retains its proof alongside derivation evidence.
- Hashes file witnesses incrementally, reads only the reuse-check header, and streams token-estimate/table inventory. Compatibility APIs remain available.
- Preserves response and whole-cycle state through durable preintents, full manifests, per-move receipts, replay and shared cross-helper locking. All three helpers now refuse unavailable or ambiguous process inventory; the code-bound helper checks both initial work and replay.
- Stages an exact commit in a fresh inactive Linux checkout with pinned transport, retained intents, raw blob/mode checks, no parent-history dependency, and no active-checkout advancement. Git filters, hooks, fsmonitor, metadata redirection and lazy remote object fetches are refused or disabled.
- Routes explicit staging through the already-registered box workflow, with credential-free input validation and a same-commit reusable workflow. No live action is triggered by a push.

The repository term bedrock denotes retained calculation layers. No Amazon Bedrock integration was added.

## Verification

All final-candidate workflows succeeded at 0b419436a100a3c189c58780c90cec981889c324:
- Host contracts: 97 passed; isolated PowerShell preservation behaviors: 102 passed, [run 35819811777](https://github.com/DavisAI1974/Markets/actions/runs/35819811777).
- Inactive staging transport and manual routing: 63 passed, [run 35819811735](https://github.com/DavisAI1974/Markets/actions/runs/35819811735).
- Trading-day/ingest regression: 84 passed; expanded cycle-zero regression: 147 passed, [run 35819811759](https://github.com/DavisAI1974/Markets/actions/runs/35819811759).
These are isolated CI executions, not live ingestion or cycle runs.

Earlier differential/reference and real-producer integration evidence:
- Full digest plus publication boundaries: 35 passed at 1b27af95cd0fa5f53eb182ee5441a57bcbcfda42, [run 35819306452](https://github.com/DavisAI1974/Markets/actions/runs/35819306452). Those digest source/test files are unchanged in the final candidate.
- Real pinned-producer Session derivation and codec suite: 228 passed at fcd5808807c05770b4303d5da1ac00338a66647a, [run 35818616295](https://github.com/DavisAI1974/Markets/actions/runs/35818616295). This predates the publication hash correction; focused publication tests cover that correction.
- Table primitive: 71 passed, [run 35818141198](https://github.com/DavisAI1974/Markets/actions/runs/35818141198).
- Full composer growth: 4,000/40,000 rows; 2,000/20,000 dictionary entries; output 102,992/1,080,999 bytes. Peak RSS 49,627,136/49,627,136 bytes; peak traced Python 1,759,179/2,543,089 bytes. Fixture generation is outside tracing; the complete writer is inside. Legacy/flow inputs are empty in this memory fixture, so it is not an end-to-end Session capacity measurement.

Tests first reproduced missing modules, the post-inverse mutation race, full-file estimate/header reads, Git normalization/config hazards, missing manual route and 12 process-guard failures. Fixes followed observed RED runs. Publication tests cover link failure, directory-sync failure, completion-receipt failure and a concurrent destination; verified scratch and intent remain, and existing output is never overwritten.

No currently open Critical/High/Medium/Low source security finding was reported by the scoped final security review. This is not a live environment certification.

## Remaining deployment gates

1. No dispatch was possible in this session. The GitHub connector exposes no workflow-dispatch mutation. Browser initialization failed with OS error 112 (disk full); the remote-only restriction forbids local cleanup as a workaround.
2. Owner Monday model_context_rows, cutoff rule/roster and the identity/completion of the final workflow task remain unanswered. Do not substitute stale 4096/19-cycle settings. Cycle 0/new run remains HELD.
3. Real Linux inventory, disk capacity and inactive staging receipts are absent. Dependency versions, runtime/module reachability, brain/history, part 4 and Granite priming acknowledgement remain unverified.
4. Native Windows preservation semantics and actual runner inactivity are unverified. The shared helper lock does not prevent a runner from starting after inventory. No native dispatch is authorized by this report, and legacy interrupted name-only plans are retained but not automatically reconciled.
5. Actual Monday preparation, source/context/runtime/seed rebinding (original step 1b), and explicit native transport/dependency closure remain open. Canonical recovery receipts retain original Linux paths and bytes. Copying an archive or rewriting paths is not admission; the current recovery loader opens the original container and compact prefix ancestry checks its full-source digest.
6. project_sections, exact whole-input tokenizer, flow/input arrays and reading/writing retain separate memory boundaries. Streaming the writer does not prove full-runtime capacity. Do not truncate scientific evidence, model output or context to hide a capacity limit.

## Inactive staging route

Use the registered [Frankie box run workflow](https://github.com/DavisAI1974/Markets/actions/workflows/frankie_box_run.yml) at the reviewed branch/tip:
- script: deploy/aws/box/frankie_box_stage_code.sh
- variables: ACTION=inventory
- instance: i-035994afa8bdf66a5
- region: us-east-1
- presign: empty
- github_token_to_ssm: false

After inventory is reviewed, ACTION=stage uses the same route and creates a new inactive checkout and receipts. It does not prepare Monday, move native state, start a runtime or release Cycle 0. Direct dispatch of the new reusable workflow is not assumed registered on the default branch.

GitHub's [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatch) requires default-branch registration for dispatch. A [relative reusable workflow](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows#calling-a-reusable-workflow) runs from the caller's commit.

## Rollback and evidence

Nothing live changed, so no live rollback is required. A failed stage retains its transfer, pack, intent and partial checkout; reconcile it and use a fresh run identifier. Do not delete it or repoint the active checkout. Do not automatically restore moved native evidence or revert to an unsafe helper. Runtime admission requires a separate reviewed configuration and gate decision. Repository integration used GitHub APIs only; all executable tests ran on isolated remote Linux CI. A later explicit user request authorized reading the single local architecture attachment, without editing it or accessing the local repository.
