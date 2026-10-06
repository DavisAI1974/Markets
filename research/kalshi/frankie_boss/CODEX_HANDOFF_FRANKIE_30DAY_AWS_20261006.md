# Codex Handoff for Frankie 30 Day AWS Workflow 20261006

**Latest checkpoint:** Read `HANDOFF_20261006_CHAT_RESET.md` first. It records the partially built implementation, settled discovery/averaging/single-occurrence decisions, retirement of Pods, and all remaining work. This original planning handoff is retained below; its old unimplemented-session status and Pod fallback wording do not describe the checkpoint. Granite must be settled with Greg before final workflow wiring/E2E.

Build the existing workflow to completion using `research/kalshi/frankie_boss/Frankie_30Day_AWS_Runbook_20261006.md`. Greg wants a working experiment with three lanes, immediate delivery of new legal knowledge, and one real end-to-end day after wiring. Keep the scope to that work.

## Repository and first reads

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-30day-aws-workflow-20261006`
Starting handoff tip: `9d355fac22131a84646a9583c5ea18c1a2ee9589`

Verify the current branch and tip before editing; preserve any subsequent work. Read, in order:

1. `research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md`
2. `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`
3. `.claude/skills/experiment-orchestrator/SKILL.md`
4. `research/kalshi/frankie_boss/Frankie_30Day_AWS_Runbook_20261006.md`.
5. `knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md` and `CLASSROOM_RULES_V3.json`. Locate the JSON by filename if its directory differs.

Use existing inventories, contracts and entry points before adding anything. Repository sources determine exact stage names and commands.

## Decisions to implement

- Three lanes: two held 16-core lanes on the main `r7i.8xlarge`, one on the Linux `r7i.4xlarge`. Reuse the existing 16-core/15-worker CPU ledger, held day slots, FIFO queues, claims and receipts.
- A day stays on its same box and lane from ROOT through completion. Keep its slot between stages and its large ROOT artifacts local.
- Frankie receives new legal knowledge immediately after every knowledge-producing stage, before the next dependent step. Other active lanes consume updates at their next legal boundary. Record consumed knowledge versions and preserve causal/answer-wall restrictions.
- Granite is an active bounded post-class coordinator/facilitator: turn selection, clarification, bookkeeping and requests to code seats for the next test. No critic or self-assessment role.
- Default Granite candidate: 3B `Q4_K_M`. Prefer local/free standard GitHub CPU if adequate, then small AWS CPU. Use 8B only if the real E2E exposes facilitator-quality problems. Paid GPU is a fallback; no standing GPU.
- Preserve Frankie's existing inputs, calculations, planes, adapters, replay and Memory A. Every retained native MBO record and available field must reach computation. No silent dropping, arbitrary truncation, averaging, smoothing or normalization of raw evidence.
- Do not pursue a fourth lane, a new discovery engine, a validator framework, a test farm or broad A/B work.

The old four-at-once ROOT run was GitHub-controlled, not GitHub-computed; the prior context identifies run `36656174396` as dispatching four A100 RunPods. Do not use that run as evidence of free GitHub GPU capacity.

## Remaining work in order

1. Inventory the remote Linux worker's ROOT-only implementation and patch it to the common ROOT-to-finish runner.
2. Add minimal cross-box publish/pull of stage knowledge and small coordination state through existing brain/receipt contracts. Avoid a shared journal filesystem or large ROOT transfers.
3. Complete the existing search surfaces: per-event INPUT fields, cross-transform pairs beyond the two combinations, other cells, conditions, additional targets, Dipole on search-only days and claims.
4. Connect survivor selection, freeze and confirmation in the existing spec's order, including immediate delivery of their new legal knowledge.
5. Wire the small Granite post-class facilitator loop.
6. Connect the three-lane launch path. Update the repository runbook with actual launch, status, resume and stop commands derived from the completed implementation.
7. After wiring and Greg's explicit AWS go, run one real ROOT-to-finish E2E day. Fix actual failures through existing recovery/checkpoint paths.
8. After success and authorization covering launch, run the 30 planned days through existing FIFO and dependency rules, with up to three eligible days concurrent.

## AWS MCP tools available to help

The connected `Aws` MCP advertises these capabilities. Discover their current schemas in the new session; tool availability can differ.

| Tool | Useful building work |
| --- | --- |
| `run_script` | Python with AWS API access through `call_boto3`; inspect EC2, S3, IAM and Systems Manager state and use authorized APIs for the existing workflow. |
| `search_documentation` | AWS API/configuration guidance; search topic `agent_skills` for guided workflow skills. |
| `retrieve_skill` | Load a workflow skill using the exact opaque `skill_name` returned by documentation search. |
| `get_presigned_url` | S3 upload/download URLs when file transfer is required. Keep signed URLs private. |
| `get_tasks` | Poll long-running MCP tasks when a prior call returns a working `task_id`. |
| `list_regions`, `get_regional_availability` | Region discovery and availability checks if needed. |

Full tool names use the current prefix `mcp__codex_apps__aws_aws___`.

Inside `run_script`, the MCP also advertises higher-level helpers:

```python
import aws_mcp
help(aws_mcp)
await aws_mcp.search_functions(
    "Inspect existing EC2 Linux workers and Systems Manager command workflow status"
)
```

Search for relevant existing-instance, remote command, orchestration or S3 helpers as needed. Inspect returned helper documentation before use; do not guess function names or build a new orchestration service merely because a helper exists.

For direct APIs, `call_boto3` takes `service_name`, PascalCase `operation_name`, optional `region_name` and `params`. Return `result = {...}` followed by `result` as the final expression. Inspect the reported `api_calls` before trusting results. Discover resources inside the script and follow List calls with Describe/Get calls when attributes are needed. The MCP execution sandbox has no general network access; it is distinct from the EC2 worker.

Read-only AWS/GitHub investigation is allowed. Complete the authorized build before requesting a launch go. Do not start AWS instances, dispatch compute or launch Frankie without Greg's explicit authorization. Loading a skill or finding a workflow helper does not authorize its launch steps.

## Session status and delivery

This handoff and the new runbook are planning artifacts. This session did not change repository code, inspect the remote worker, start AWS or execute an E2E. The starting branch tip was verified as `9d355fac22131a84646a9583c5ea18c1a2ee9589` before adding these documents. Check the current tip again in the implementation session.

The runbook, this handoff and `DROP_IN_CODEX_FRANKIE_30DAY_AWS_20261006.txt` live under `research/kalshi/frankie_boss/`. Read them directly from this branch; attachments are not required. Update the runbook's operating commands as implementation finishes.

Finish the wiring, record the actual files changed and exact operating commands, and report any remaining blocker plainly. Keep verification to the agreed real E2E and fixes for observed failures.

