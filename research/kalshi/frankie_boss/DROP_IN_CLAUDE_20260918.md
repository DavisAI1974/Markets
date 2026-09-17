# Drop-in for the next chat - Frankie/BOSS, after 2026-09-17 (Claude Code)

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first.

```
git fetch origin claude/first-run-using-agent-skills-bd52fj
git checkout -B claude/first-run-using-agent-skills-bd52fj origin/claude/first-run-using-agent-skills-bd52fj
git log --oneline -1
```
Read, in order: `CLAUDE.md` (top block: FRANKIE / BOSS standing rules), then
`research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260917.md`, then `CLAUDE_RECONCILIATION_20260916.md` in the same directory.

## State in one paragraph

This branch = recovery `34301ac0` + classroom `d152dd82` + review `61c73a2d` reconciled (first tree with all three) +
the Granite 4,096-token context removed from ALL Granite code (131,072 only; output bounded by the context; finite
direct critic, bounded smoke launch and the 4096 smoke receipt retired). The first run's prefixes and reducer stack are
verified byte-identical to runtime pin `9a8f3f46` and are the GOLD STANDARD (57,027 records -> 114,054 entries -> 7,129
blocks, 715 s). Receiver `2ebb8ce8` is a sibling checkout, not merged. Launch is HOLD.

## First business

1. Greg's row count for the native context (`T_CTX` / `context_rows` / `model_context_rows` / prefix-builder guard).
2. The pre-existing test errors listed in the handoff: 8 failures, the 28 `test_granite_coordinator.py` setup errors
   (fixture `max_model_len=3000`, then a second setup problem), the `test_granite_retained_host.py` stall. Identical on
   the untouched tree; not introduced by the 4096 work. Fix the root causes, never skip or deselect to get green.
3. Audit findings 2-8 (see handoff), then the token shrinks 3.1-3.4, then the CPU items.

## Standing orders (Greg)

- 4096 is RETIRED for Granite. Never reintroduce it in code, tests, fixtures or docs. 114,054 is a row count, not tokens.
- The first run's prefixes/reducer stack are the gold standard; for new days change dates only, never rebuild.
- Shrinking/optimizing the packet is one of the most important jobs. 8 threads, fixed. Per-event, never average.
- No Frankie/Granite/Pod/EC2/result-bearing action, no workflow, without Greg's explicit go. Nothing on local disk: git and S3.
