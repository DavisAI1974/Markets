# CHATGPT KICKOFF S119 — MCP + FRANKIE

Purpose: drop-in takeover for a fresh ChatGPT conversation. This is a current-state handoff, not canonical truth. `research/kalshi/OPEN_ITEMS.json` / generated `OPEN_ITEMS.md` remain authoritative for registered work.

## FIRST MESSAGE FOR THE NEW CHAT

Paste exactly:

> Read `CHATGPT_KICKOFF_S119_MCP_FRANKIE.md` on branch `chatgpt/agent-frankie-s117`, then read every file it names as required reading. We are continuing the Markets/Frankie build from the previous ChatGPT session. First check whether the custom `Markets Terminal` plugin/MCP tools are visible in this fresh chat. If visible, test the read-only connection before doing anything else. Do not re-litigate completed Frankie work.

## REQUIRED READING ORDER

1. This file — current S119 transition state.
2. `CHATGPT_KICKOFF_S118_TAKEOVER.md` — original Claude -> ChatGPT ownership transfer and protected build context.
3. `research/kalshi/FRANKIE_BUILD_BRIEF_S115.md` — original Frankie design contract.
4. `research/kalshi/FRANKIE_S115_IMPLEMENTATION.md` — implementation against that contract.
5. `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md` — engineering/AWS architecture handoff.
6. `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` — C2C operational history through the current work.
7. `research/kalshi/OPEN_ITEMS.md` / `OPEN_ITEMS.json` — canonical outstanding-work registry; do not hand-edit generated markdown.
8. Older Claude handoffs only for provenance or a specific subsystem.

## OWNERSHIP / PROTECTED STATE

- ChatGPT owns the Markets/Frankie continuation.
- Working branch remains `chatgpt/agent-frankie-s117`; PR #8 is the established Frankie PR context.
- `research/kalshi/spawn.py` is protected. Do not casually modify or re-architect it.
- Do not redo completed Frankie architecture merely because an older handoff describes it as missing.
- Greg wants to get to paper trading ASAP. Only a small number of group runs are desired to prove the corrected path; do not drift back into endless historical-group work.
- Existing brain/schema/lens work predates Frankie and should be reused as much as possible. Frankie should not start from zero; if evidence shows he can move beyond inherited mechanisms, that is fine.

## FRANKIE CURRENT VALIDATION STATE

The S118 redo work established that the corrected causal packet path reaches the model boundary correctly. The Opus 5 canary packet was G18 / 2026-04-27 / specialist B with 90 canonical plays and 33 selected/served plays, and no realized target outcome in the packet. The failure occurred at Bedrock `Converse`, not packet construction.

C2C-001 and C2C-002 established the AWS blocker precisely:
- IAM authorization: available/authorized.
- Entitlement: available.
- Region: available.
- Agreement availability: `NOT_AVAILABLE`.
- AWS explicitly reported that the Anthropic model-access request form had not been filled out.

C2C-003 attempted the SDK route only after Greg explicitly authorized it. AWS exposes `PutUseCaseForModelAccess(formData: blob)` but rejected plausible payloads as opaque `Invalid form data`; Claude correctly stopped rather than invent owner/legal declarations. The practical route is the Bedrock console form, where Greg can answer the rendered owner fields. After form submission, the hard gate is:

`GetFoundationModelAvailability(modelId="anthropic.claude-opus-5").agreementAvailability.status` MUST move off `NOT_AVAILABLE` before any canary retry.

Do not blindly walk through other Anthropic models. Once the form/agreement gate clears, retry one clean Opus 5 canary. If valid, continue only the minimum G18/G19 validation required, then move toward paper trading unless a real mechanical defect appears.

Known Frankie registered items from the prior work include A-70 merge review; A-80/A-82 fixes supplied/applied in the redo path; A-84 tape-vs-weather rule issue; A-85 magnitude carries no information; A-86 one-point-per-day/length-only gate; A-67 unseen-block architecture test. Re-read current OPEN_ITEMS before acting because statuses may have advanced.

## MARKETS TERMINAL MCP — CURRENT STATE

A custom ChatGPT MCP path named **Markets Terminal** has been built.

Initial C2C-004 proof:
- MCP server was first proven locally outside the repo with two read-only tools.
- Real MCP client successfully performed discovery, repo status, and safe file reads.
- Containment tests independently refused traversal, absolute paths, credential files, deny-listed names, oversized files, binary files, and sibling-prefix directory escapes.
- No general shell or write capability was granted in the initial proof.

A-88 was subsequently completed/closed by Claude. The sustained connector now runs on the durable Markets box rather than depending on the disposable chat/session container. The MCP code was moved into the repository under `mcp_server/`, repo-root resolution was derived from code location rather than hardcoded, and persistence/recovery was proven. C2C-005 completion was recorded in the coordination ledger at commit `2288bfd`; A-88 was reported closed at `46a3f2c`.

The OpenAI Secure MCP Tunnel exists and is associated with Greg's ChatGPT workspace. The tunnel is named **Markets Terminal**. The tunnel identifier is intentionally not repeated here; obtain it from the OpenAI tunnel record if needed rather than copying identifiers through handoffs.

At the end of the prior chat, the old conversation still could NOT discover `Markets Terminal` as an available plugin/tool even though the tunnel existed and had been saved multiple times. This fresh chat is being created specifically to test whether custom plugin availability is fixed at conversation initialization.

### FIRST ACTION IN THIS NEW CHAT

1. Check whether `Markets Terminal` is visible/connected to this conversation.
2. If visible, discover its tool list.
3. Test read-only access only: repo status, then one harmless safe file read.
4. Test at least one expected containment refusal before expanding permissions.
5. Do NOT assume terminal/write/AWS mutation capability exists merely because the tunnel is connected.
6. Only after the read-only connection is proven should we design a narrowly scoped capability expansion for the work ChatGPT actually needs.

If `Markets Terminal` is still not visible in a fresh chat, diagnose the ChatGPT custom-plugin attachment/discovery step. Do NOT rebuild the tunnel or MCP server first; A-88 says the durable server/tunnel side is already proven.

## MCP COST / TOKEN FOLLOW-UP

A-87 remains the important follow-on after persistence: an always-on connector changes the token-cost problem. Measure real tool bytes first. Preferred reduction order is tool-boundary retrieval, not lossy summarization: ranged reads, index/list/search before whole-file reads, explicit refusal/naming when content is withheld. Any compaction/reduction must preserve the desk's rule that absence announces itself and should ultimately pass A-65-style paired validation before being trusted.

## EVOHARNESS-RL PAPER — DO NOT LOSE THIS

Greg supplied the paper screenshot and explicitly asked that the full paper be pulled and studied:

**EvoHarness-RL: Learning Self-Evolving Runtime Harness for Long-Horizon LLM Agents**
Authors include Xuying Ning et al.; affiliations shown include University of Illinois Urbana-Champaign and Meta AI.
arXiv identifier from the supplied paper image: **arXiv:2608.05446v1**, dated **5 Aug 2026**.

This was intentionally put on the back burner during the AWS/MCP work. The previous ChatGPT session began reviewing the public paper record but DID NOT complete a cover-to-cover methods/ablations review. The new chat must not claim otherwise.

Why it matters to Frankie:
- The paper frames external harness state as Belief, Progress, and Experience (BPE).
- It studies learned policies for when to read/update/consolidate external state rather than treating memory/tool use as a fixed prompt convention.
- It introduces/uses the concepts of harness annealing and harness evolution.
- This is highly relevant to Frankie's existing brain/lens/retention architecture and to A-87 token-boundary retrieval, but it is NOT authority to replace the current architecture or jump straight to RL.

Required follow-up: pull/read the full paper, especially methods, state representation, training objective, ablations, failure modes, and what evidence actually supports the claims. Then map it against Frankie's existing brain/schema/lens/retention and MCP tool-boundary design. Preserve existing architecture unless a measured change passes the project's validation discipline. Paper trading is likely a more useful source of future long-horizon trajectories than burning the unseen historical holdout.

## DO-NOT-REDO / DO-NOT-DO

- Do not redo Frankie architecture already completed in S115-S118.
- Do not let older handoffs override newer registered state.
- Do not modify protected `spawn.py` without explicit reviewed authorization.
- Do not open realized outcomes before the causal forecast artifact is sealed.
- Do not treat a visible Bedrock model/profile as proof of invocation access; the agreement gate is separately measured.
- Do not retry Bedrock Opus 5 until agreement availability clears.
- Do not rebuild Markets Terminal merely because this chat cannot initially see it; first diagnose ChatGPT plugin discovery/attachment.
- Do not expand MCP to unrestricted shell/AWS/IAM access. Add only the minimum reviewed capability needed.
- Do not silently truncate MCP responses. Missing/elided content must announce itself and provide a retrieval path.
- Do not spend many more group runs proving architecture. Greg's direction is a couple of groups at most, then paper trading.

## IMMEDIATE SEQUENCE

A. Fresh-chat Markets Terminal discovery + read-only proof.
B. In parallel, Greg completes the rendered AWS Bedrock Anthropic model-access form if not already done; verify agreement status before retry.
C. One clean Opus 5 canary after the AWS gate clears.
D. Minimum clean G18/G19 validation only if needed.
E. Move toward paper trading ASAP, while preserving causal/immutable blind artifacts.
F. Read and analyze the full EvoHarness-RL paper in parallel; propose no architecture change until the evidence and Frankie mapping are explicit.
G. After MCP is proven, measure A-87 real connector byte/token behavior before building a reducer.

## COORDINATION

Claude and ChatGPT use `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` for operational exchanges. It is an audit/coordination ledger, not canonical truth. Registered work belongs in OPEN_ITEMS through the store discipline.
