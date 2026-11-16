---
name: repo-conventions
description: House rules for any GitHub or git write on the DavisAI repositories (DavisAI1974/Markets and DavisAI1974/markets-data) - which branch to work on, the stale-tip check, commit message style and [skip ci], what may and may not be committed, and secrets. Use before creating a branch, committing, pushing, opening an issue or PR, or editing files through the GitHub tools on either repository.
---

# DavisAI repository conventions

Two repositories, one owner (`DavisAI1974`). Team: Greg Davis (founder, sets direction) plus
agents (Claude, Codex). The repository's own `CLAUDE.md` and the newest handoff always win over
this file when they disagree - say so rather than picking silently.

## The repositories

| Repository | Holds | Start here |
|---|---|---|
| `DavisAI1974/Markets` | Application and research code, runbooks, workflows, research artifacts | `CLAUDE.md`, then the newest `SESSION_HANDOFF_*.md` / `KICKOFF_*.md`, then `KALSHI_TRADING.md` |
| `DavisAI1974/markets-data` | Market data, tables, workbooks, renders, provenance manifests | `MARKET_DATA_INDEX.md` (default branch `main`) |

Code goes to Markets. Data navigation and published results go to markets-data. The raw NYMEX
tick tape lives in S3, not in either repository.

## Branches (Markets)

- **Trunk: `claude/kalshi-s79-kickoff-ij8t9o`.** The collector workflows check out and push
  relative to it. Fetch and rebase before pushing - the collectors commit too.
- **Stale-tip check, every session, first thing:** `git log --oneline -1`. Harnesses often cut a
  session branch from an old tip (the known bad one is `3c70ff5`, S70). An old tip means you are
  not on the real work.
- **Data branches accrue data, never code:** `data/kalshi-bins`, `data/pyth-ticks`,
  `data/nymex-ticks`, and the older `data/*-book` / `data/*-bins` / `data/*-kraken-book` crypto
  history. Never merge them into the trunk, never open a PR from them, never rebase them.
- **`archive/crypto`** holds the crypto-era files and `CLAUDE_ARCHIVE_OD.md`, moved off the trunk
  2026-11-16. Read from it; do not move its files back.
- The remote has nearly 300 branches from Claude, Codex, ChatGPT and older sessions (`claude/`,
  `codex/`, `chatgpt/`, `ccr-`, `ccode/`, `persona/`). Never delete, rename or prune any of them
  without Greg's word, and never assume one is dead because it looks old.
- **Frankie run branches have no merge base with the trunk.** Do not merge, rebase or "sync" one
  with the trunk. The run branch name comes from the newest drop-in doc, not from this file.
- A session that was assigned its own branch pushes there and nowhere else without Greg's word.
  Do not strand finished work on it - say where it sits.

## Branches (markets-data)

- Default branch `main`. The canonical research branch is named in `MARKET_DATA_INDEX.md` -
  read it there, do not guess.
- Publish substantive data and results there and update the index or its linked manifests in the
  same session.
- `MANIFEST.json` is the original pinned-input catalog: its paths and checksums are immutable.
  New outputs get their own linked manifest.
- Preservation archives are GitHub Releases on markets-data. Never delete a release, a tag or a
  receipt. Local copies are removed only after the remote copy is verified.

## Commit messages

- Form: `type: lower-case subject` or `type(scope): subject` - types in use: `research`, `docs`,
  `data`, `rule`, `fix`, `feat`, `chore`; scopes seen: `rule(markets)`, `chore(claude)`,
  `archive(frankie)`. A new standing rule from Greg lands as `rule(markets): ...` with the rule
  stated in the subject, and goes into `CLAUDE.md` in the same push.
- Append ` [skip ci]` to docs-only, research-artifact and data commits. Several workflows are
  push-triggered and a careless push has billed CI before. During a Frankie run, **every** push
  carries `[skip ci]`.
- The subject says what was preserved or changed and why it matters, not which tool did it.
- No emojis or special symbols in commits, PR text, issues or any pushed document.
- No model identifiers in commits, PR titles or bodies, or code comments.

## What never goes into git

- Secrets: AWS, Databento, Runpod, EIA or Kalshi keys, tokens, presigned URLs. They live in
  GitHub Actions secrets and SSM. If one appears in a diff, an issue or a log excerpt, stop and
  tell Greg - do not push, and do not paste it into a comment.
- The gitignored local stores (`data/kalshi_hist_trades/`, `data/pyth_ticks/`, `data/kalshi/`,
  `data/level_hits_*.json`) and raw tick tape. Re-pullable and too large.
- Synthetic trading data. Not as a fixture, not as a test input, not ever.

## What never gets rewritten

- No force-push to the trunk, a data branch, a run branch or `main`.
- Never delete evidence: receipts, manifests, superseded results, adverse or missing cases.
  Supersede by adding, and mark the old item historical.
- Pinned files named in the Frankie runbook are swapped, never edited.

## Issues and pull requests

- Do not open a PR unless Greg asks for one. The normal flow is commit and push to the working
  branch.
- Use the `pr-and-review` skill for the PR body and for any review.
- Comments posted by an agent end with a line saying so; never post as if you were Greg.
