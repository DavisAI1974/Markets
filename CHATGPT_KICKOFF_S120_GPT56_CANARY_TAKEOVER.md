# CHATGPT KICKOFF S120 — GPT-5.6 SOL CANARY TAKEOVER

This file is the new-chat starting point for the DavisAI Markets / Frankie build.

## Ownership and branch truth

- Repo: `DavisAI1974/Markets`
- Active branch: `chatgpt/agent-frankie-s117`
- PR: #8 `Build AWS-ready hybrid Agent Frankie`
- PR state at takeover creation: OPEN, DRAFT, unmerged, mergeable.
- Pre-kickoff PR head: `edcddb4397e9ef164d5bce53769eb1c4856b18c6`.
- `research/kalshi/spawn.py` remains protected and must not be modified; canonical protected blob remains `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e`.
- Shared coordination ledger: `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` is canonical for ChatGPT <-> Claude task/result blocks. Append only; never rewrite prior ledger content.

## What is actually complete

### M-16 / data plane

M-16 physical head-tape recovery is closed. The durable S3 head trades corpus was restored byte-for-byte: 311 files / 85,835,820 bytes, with all 74/74 weekdays in the paid 2025-07-22..2025-11-02 window present. No repurchase was required. `vol_regime` rebuilt from the restored tape. `ng_l1` remains intentionally per-group staged and was not silently added to the whole-plane restore policy. The real depth corpus is the MBO family, not `nymex_mbp10`.

### Bedrock / Anthropic

Greg submitted the Anthropic Bedrock use-case form and explicitly authorized acceptance of the Claude Opus 5 agreement. The form is stored and the agreement became AVAILABLE. Runtime invocation nevertheless remained problematic: Opus 5 returned AccessDenied; a later Haiku 4.5 probe returned a different first-use/runtime propagation error. Do not spend more build time chasing Bedrock before the OpenAI path; Bedrock is now secondary/fallback investigation.

### Frankie model backend decision

Greg directed Frankie to use **GPT-5.6 Sol**. Preserve Frankie architecture and swap only the reasoning backend seam. OpenAI credential lives in AWS SSM SecureString `/markets/OPENAI_API_KEY`. Greg replaced the previously restricted key with a key that has inference scope. Never print, log, hash, commit, or paste the secret.

### First live GPT-5.6 Sol canary

Commit `edcddb4397e9ef164d5bce53769eb1c4856b18c6` records the first successful live GPT-5.6 Sol canary and contains the noncanonical canary artifact:

`research/kalshi/forecasts/c2c014_gpt56sol_canary/grp18_B_20260427.json`

Artifact sha256: `f6465c51debb3e9bffd2953bb2296952e0bf9e62b69436937d220287e6ab82de`.

Measured canary facts:

- model id confirmed: `gpt-5.6-sol`
- one invocation, no retry, no alternate model
- input 297,670 tokens; output 3,836 tokens
- cell: `g18 / 20260427 / specialist B`
- owner B confirmed
- day index 0, therefore no BLD-2 bridge and exactly one specialist invocation
- canonical plays: 90
- served/selected plays: 33
- A-82/no-outcome leak wall: PASS
- no actual/RT file opened
- brain serving worked end-to-end: 4 plays fired by name and 16 stood down
- the model independently identified several already-known input defects and rejected a post-cutoff value rather than using it
- no scoring has been performed and no realized outcome has been opened

The live backend is therefore proven. Do **not** classify the canary as an OpenAI/backend failure.

## The current blocker: our own structural contract

The canary was rejected by A-86 because `path_p50_curve` was flat with max shape deviation 0.0. This was not decorative interpolation. GPT-5.6 Sol explicitly ABSTAINED and represented that abstention as the contract-required all-zero 13-point two-hour ET curve. It also set `guessed_net_usd = 0` and confidence low.

This exposes a validator semantic defect: A-86 currently cannot distinguish an honest no-call/abstention from a decorative straight-line nonzero forecast. S111 established that NO CALL / abstention must be representable for measurement.

The intended fix is narrow, not a weakening of the guard:

- explicit ABSTAIN + `guessed_net_usd == 0` + low confidence + zero curve => structurally valid abstention state;
- nonzero forecast/net with straight/flat decorative shape => continue to hard-fail A-86.

Do not simply disable the straight-line guard.

## Separate output-contract defect

The GPT-5.6 Sol response emitted only the narrow legacy-style output set and omitted all 14 canonical day-level fields. The clock/curve contract clearly reached the model, so this must be investigated as prompt/output-adapter/schema enforcement, not hand-waved away.

Before scoring anything, enforce the canonical output contract and add explicit regression coverage so missing required day-level fields fail clearly. Preserve explicit abstention semantics while doing so.

## Immediate next build sequence

1. Read this kickoff file, then the latest sections of `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md`, then the relevant A-86/output-contract implementation and tests.
2. Locate A-86's decorative straight-line guard and the canonical day-level output schema/adapter.
3. Implement the smallest semantic repair that makes a genuine explicit abstention representable while preserving rejection of decorative nonzero straight-line forecasts.
4. Enforce/validate the canonical 14 day-level fields separately; do not conflate this with the abstention exception.
5. Add regression tests at minimum for:
   - explicit zero-net/low-confidence abstention with zero curve => PASS;
   - nonzero net with flat/straight decorative curve => FAIL;
   - missing canonical day-level fields => FAIL with a clear structural-contract error;
   - complete canonical abstention output => PASS.
6. Run local/unit/CI validation with protected `spawn.py` unchanged.
7. Only after code/tests are clean, register the next shared-ledger canary task and run exactly one fresh GPT-5.6 Sol G18 specialist-B canary through the same causal packet. Do not score/open outcomes until structural validation passes.

## Do not redo

- Do not rebuild Frankie architecture.
- Do not redo M-16 recovery/inventory.
- Do not repurchase Databento data.
- Do not reopen Bedrock form/agreement work unless specifically needed later as fallback.
- Do not modify `research/kalshi/spawn.py`.
- Do not change brain/schema serving architecture merely because the first GPT-5.6 canary abstained.
- Do not score the existing canary against realized outcomes.
- Do not run A-67/A-69/A-85 ahead of fixing the structural output contract unless a new measured blocker forces resequencing.

## Infrastructure edge to remember, but keep separate

`markets-mcp-tunnel.service` remained healthy during the SSM OpenAI-key replacement because it reads `/etc/markets/tunnel.env`, which still held the older key at the time of the canary. A future restart/redeploy/token refresh may expose that mismatch if the old key was revoked. Treat this as a separate infrastructure task before deliberately restarting the tunnel; do not mix it into the A-86/schema patch.

## Coordination protocol

Use repo truth first. For ChatGPT <-> Claude operational handoffs, create/read the small C2C task file and append matching task/result blocks to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md`. Greg should not have to courier long task bodies between agents. Preserve the full prior ledger prefix byte-for-byte on every append.
