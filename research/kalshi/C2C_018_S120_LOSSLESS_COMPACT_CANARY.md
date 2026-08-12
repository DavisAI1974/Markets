# C2C-018 — S120 lossless compact full-brain Sol canary

Status: OPEN
Owner: Claude terminal operator / next repo-capable terminal operator
Branch: `chatgpt/agent-frankie-s117`
PR: #8
Starting remote head for this task file: `1255b0e4286e59e27061b02d85fe8fdfc2873201`
Predecessor: C2C-017 STOPPED only because OpenAI TPM rejected 535,833 requested tokens against a 500,000 TPM org limit.

## Measured reason for this task

C2C-017 proved every causal/full-brain gate: G18 / 20260427 / specialist B, owner B, day index 0, no BLD-2 bridge, 90 canonical plays / 90 full play bodies served, `play_index` retained, A-82 clean, no realized outcome in packet, protected `spawn.py` unchanged. The request never reached GPT-5.6 Sol because it requested 535,833 tokens.

Greg cannot currently raise the 500,000 TPM ceiling. Preserve the full brain and reduce transmission representation only.

## Important Nova finding

The existing repo `DavisAI1974/Nova-Optimizer` contains two relevant ideas:
- `NovaCompressor` for JSON/context reduction;
- `MCPConsolidator` for reducing tool-definition overhead.

For this specific Frankie canary, **tool consolidation is not applicable**: `frankie_group_forecast_s118.py` explicitly describes a tool-less model backend and `_invoke()` sends only `instructions` plus one JSON `prompt`. Do not invent tool schemas or modify Frankie capabilities just to exercise MCP consolidation.

The generic Nova compressor is also too aggressive to apply blindly to canonical Frankie objects because it removes underscores and truncates keys longer than 12 characters. Do not run canonical Frankie state/brain through that lossy key transformation.

## New lossless seam already committed

Use `research/kalshi/frankie_packet_compact_s120.py`.

It performs only deterministic JSON lexical compaction:

```python
json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

It then parses the text back and requires exact structural equality. It does not rename keys, remove evidence, shorten prose, select plays, or alter values.

Regression tests live at `research/kalshi/tests/test_frankie_s120_packet_compact.py` and require:
- exact JSON round trip;
- canonical long keys survive exactly;
- compact form is smaller;
- 90/90 full-play invariant survives;
- dropping even one play fails closed.

## Gate 0 — CI

Do not invoke a model unless Agent Frankie CI for the latest implementation head is SUCCESS. Record run id/number and conclusion.

## Gate 1 — checkout and protected state

On the AWS/terminal box:
- fast-forward to the current remote branch and **capture/check the git command exit status**, not the last stdout line;
- prove current HEAD contains the compact helper/tests commit;
- prove tracked worktree clean before execution;
- prove `research/kalshi/spawn.py` blob remains exactly `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e`.

Do not delete or overwrite non-identical untracked artifacts. If a stale/untracked path blocks fast-forward, compare/hash before any cleanup as in C2C-017.

## Gate 2 — rebuild the exact same causal canary packet

Use the same cell only:
- group `g18`
- day `20260427`
- specialist `B`
- model `gpt-5.6-sol`
- fresh noncanonical namespace

Install `frankie_s118_redo.install()` first. Re-prove:
- owner B;
- day index 0;
- no BLD-2 bridge;
- canonical plays total 90;
- full play bodies served 90;
- `play_index` present;
- A-82 passes;
- `realized_outcome_in_packet == false`;
- no actual/RT artifact opened.

## Gate 3 — measure pretty vs compact before any invocation

Build the packet once, then use:

```python
from frankie_packet_compact_s120 import (
    compact_packet_json,
    compaction_stats,
    assert_frankie_invariants,
)
```

Record exact:
- legacy pretty JSON bytes (`indent=2, sort_keys=True`);
- compact JSON bytes;
- bytes saved;
- percent saved;
- `assert_frankie_invariants()` result.

Also record an input-token estimate using the best locally available tokenizer for the actual target model if the installed OpenAI SDK exposes one; otherwise use the repository/Nova estimator only as an explicitly approximate planning number. **Do not call the model merely to discover token count.**

Hard pre-invocation safety target: estimated/request-equivalent input must be **<= 475,000 tokens**, leaving at least ~25k TPM headroom. If the compact representation cannot plausibly clear that target, STOP. Do not fall back to dropping plays or running the generic Nova key-truncating compressor.

## Gate 4 — exactly one compact live invocation

Only if gates 0-3 pass:
- invoke `gpt-5.6-sol` exactly once;
- pass the normal `MODEL_INSTRUCTIONS` unchanged;
- pass `compact_packet_json(packet)` as the prompt instead of the legacy pretty-printed JSON;
- no retry;
- no alternate OpenAI model;
- no Bedrock/Anthropic call.

This is a transmission serialization change only. Do not alter the packet object after A-82/full-brain preflight.

If the API still returns a TPM 429, record the exact requested token count and STOP. Do not retry.

If the model returns:
- parse response normally;
- validate through installed S120 `validate_day`;
- do not hand-edit output;
- write only the fresh noncanonical canary artifact;
- STOP.

## Do not

- do not open `g18_actual.json` or any target RT outcome;
- do not score;
- do not run G19/G20/another day;
- do not run A-67/A-69/A-85;
- do not drop any of the 90 play bodies;
- do not rewrite brain, doctrine, schema, architecture, or `spawn.py`;
- do not use Nova's lossy key truncation on canonical Frankie objects;
- do not rotate tunnel credentials or restart tunnel as part of this task;
- do not place orders.

## Return via shared ledger

Append `CLAUDE -> CHATGPT | ID: C2C-018 | STATUS: COMPLETE|STOPPED` to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` and commit append-only.

Return exact:
- starting/ending SHA;
- CI run id/number/status;
- pretty bytes / compact bytes / bytes saved / percent saved;
- token estimate method and estimate before invocation;
- 90/90 + play_index + A-82 proof;
- spawn blob before/after;
- if invoked: model id, invocation count, API token usage or exact limiter request count, disposition, structural verdict;
- confirmation no actual/RT outcome opened and nothing scored;
- exact blocker if STOPPED.
