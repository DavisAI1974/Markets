# DROP-IN BOX - S119

Paste this whole box into a FRESH session. It is the starting state, not the record; the record is
`SESSION_HANDOFF_2026-08-10_S118.md`.

---

## 0. FIRST COMMANDS

```bash
git fetch origin claude/kalshi-agents-coordinator-guard-sg0n15
git checkout -B claude/kalshi-agents-coordinator-guard-sg0n15 origin/claude/kalshi-agents-coordinator-guard-sg0n15
git log --oneline -1        # expect: 2b4c8bd or later
```

The harness assigns its own branch. **That branch is never the work.** If `git log` shows a stale
tip you are not on the real work; if the checkout is empty, the fetch above is the fix.

Then read, in order: this box, `SESSION_HANDOFF_2026-08-10_S118.md`, `OPEN_ITEMS.md` (a render - do
not edit it, edit `research/kalshi/OPEN_ITEMS.json`), and `python research/kalshi/plant_status.py`.

---

## 1. YOU ARE NOT WORKING ALONE - THERE IS A SHARED DOC WITH CHATGPT

**This is the thing most likely to be missed, so it is first.**

Greg runs two agents on this project: **you (Claude)** and **ChatGPT**. You do not talk to each
other directly. You communicate through **one committed file**:

```
research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md
   on branch: chatgpt/agent-frankie-s117
```

### How it works

- Chat appends a numbered task block: `## CHATGPT -> CLAUDE | ID: C2C-### | STATUS: OPEN`, with
  `purpose`, `required state`, `exact actions`, **`stop conditions`**, and `return`.
- You execute it and append your result: `## CLAUDE -> CHATGPT | ID: C2C-### | STATUS: COMPLETE`
  (or `STOPPED`), covering everything the block's `return` section asks for.
- Greg relays the commit sha in chat when a new block lands. **Fetch and read the file at that sha -
  do not act on the summary in the message.**
- **Only execute the LATEST UNRESOLVED block.** Do not infer beyond it, do not batch, and do not
  re-run resolved ones.

### The rules that have already been paid for

1. **APPEND. NEVER REGENERATE (D53).** Chat's C2C-007 commit rebuilt this file instead of appending
   and cut it **637 lines -> 35**, standing in a line reading *"[CONTENT PRESERVED THROUGH
   C2C-006]"* - a line that asserts preservation and IS the deletion. Restored at `ffd6556`. It was
   found only because Greg asked whether the notes had been committed.
2. **READ IT BACK FROM THE REMOTE AFTER PUSHING.** `git show origin/<branch>:<path> | wc -l` plus a
   block-heading count. We cannot gate chat's commits; this is the half we control, and it would
   have caught the truncation instantly.
3. **STOP MEANS STOP.** Blocks carry explicit stop conditions (no IAM/billing changes, no tunnel
   recreation, no reboot, no touching Frankie/brain/`spawn.py`, no model calls). When a block cannot
   be completed within them, the correct output is `STATUS: STOPPED` **with the exact evidence** -
   not a workaround. C2C-007 stopped correctly; that is the pattern.
4. **Report what you did NOT prove.** Every result block names the gap (D51). "The host answers a
   real MCP client" is not "ChatGPT called the tool."

### What has run through it so far

| block | outcome |
|---|---|
| C2C-001/002 | complete |
| C2C-003 | STOPPED - Bedrock model access needs an account-level use-case form (A-79) |
| C2C-004 | read-only MCP server built + tunnel established |
| C2C-005 | COMPLETE - durable on the box under systemd (A-88) |
| C2C-006 | COMPLETE - official checksum-verified tunnel-client v0.0.11 |
| C2C-007 | **STOPPED** - Codex cannot consume the tunnel via a plugin; see section 3 |

---

## 2. STATE AT OPEN

- **Brain `s105.9`, 90 plays - UNCHANGED.** No merge, no group run scored into the record.
- **Registry 202 items** (178 open: 26 ESSENTIAL, 45 BIGGEST_WIN, 108 REST), **decisions 53**.
- **Corpus is 200 gradeable days** (A-77), with a per-group basis verdict rather than an assumed one.
- **`plant_status.py` = ALL CLEAR** at close (WARNs only).
- **Markets Terminal is live**: read-only MCP, two tools, on the box as `markets-mcp-tunnel.service`.

### The box, and the one thing that will confuse you

`/opt/markets-terminal` on the durable box is currently checked out to
**`chatgpt/agent-frankie-s117` @ `d539c2a`**, not to the claude branch. So `markets_read_file`
serves *chat's tree*: **anything you commit to the claude branch is invisible through the connector
until the box is repointed.** `markets_repo_status` reports branch and HEAD - call it rather than
assuming. The box also hosts **Greg's live dashboard** (`markets-desk.service`, :8091, up 20+ days):
never reboot it, never restart that unit, never touch `/opt/markets-live`.

Deploy/rotation path, idempotent:
`cd /opt/markets-terminal && git pull && bash mcp_server/deploy_box.sh`

---

## 3. WHAT S119 SHOULD DO

**A-85 (ESSENTIAL) is the frontier, and the next step is NOT another forecast run.** S118 measured
that **magnitude carries no information**: sorted by `|actual|`, the smallest-half and largest-half
`|guess|` ranges overlap almost completely in both arms, and withdrawing the sizing instruction moved
the band without changing its discrimination at all. So run **A-85's falsifier**: across the 200-day
corpus, find *any* served quantity that separates large-move days from quiet ones - `vol_regime`,
realized sigma, options-implied move, `|signed_flow|`, forecast run delta. **If one does, this is a
serving gap. If none does, the honest product is a band and `path_p50_curve` should be REMOVED
rather than filled with decoration.** Per event, never pooled - use
`research/kalshi/per_event.py report(...)`, which returns no scalar on purpose.

Then, in rough order: **A-86** (the contract emits 3 of 20 day-level fields and `_validate_day` only
checks `len(curve) >= 2`), **A-70** (merge review of `chatgpt/agent-frankie-s117` - a merge commit
signs for the whole diff, including ~1,500 lines of dashboard code nobody here has read), **A-84**
(the divergence rule lost all three g20 split days and may deserve demotion), **h1** (blocked on
2026-only fundamental stores).

**If chat posts a new C2C block, that takes priority** - it is usually short and it unblocks him.

---

## 4. STANDING RULES THAT BITE

- **ROTATE THE OPENAI KEY.** It was pasted into chat and must be treated as compromised, exactly
  like the AWS pair at S99. Path: rotate -> `python research/kalshi/creds.py --sync-ssm` ->
  `bash mcp_server/deploy_box.sh` on the box. The key travels via SSM SecureString and is written to
  `/etc/markets/tunnel.env` 0600 **by a script running on the box** - never as an SSM command
  argument, because RunShellScript text is retained in command history and CloudTrail.
- **KEYS DO NOT ROTATE DURING THE WALK** - that standing decision covers the AWS and Databento pair,
  not this OpenAI key, which is a fresh exposure.
- **YOU CANNOT AVERAGE (D4/D37).** An R2, a correlation and a fitted slope are all averages. Read
  every event individually; that correction overturned S118's first read of the whole Frankie run.
- **A finding with no registry line does not exist (D30).** Open things go in `OPEN_ITEMS.json` -
  not a new document, not handoff prose.
- **Nothing local (D34), nothing only on a scratchpad (D52).** git = code and records, S3 = data,
  `data/` is disposable.
- **A gate that exists is not a gate that passed (D51).** Name what you did not prove.
- **The failure family this desk keeps paying for: something reports success while doing nothing.**
  S118 alone: a runner serving zero plays while its preflight said `PACKETS_CAUSAL`; a deploy script
  aborting at `EXIT=2` before installing anything, hidden because I piped it to `grep` and read
  grep's status; a curve passing validation because the check only counted list length. **Capture
  exit codes, and observe the fixed path actually execute (NC-3).**

---

## 5. ONE LESSON FROM S118 WORTH CARRYING

One tunnel error drew three confident causes from me in sequence - project mismatch, then billing,
then permissions. **All three were wrong**; the fault was the tunnel itself, and a new one authorized
on the first attempt with the same key, org and binary. Every theory was reasoned from **how the
platform should work rather than from anything measured about that specific tunnel.** The only move
that resolved it was ordering the cheap one-call retest first.

When something external fails, the first question is not "what would explain this" but **"what is the
cheapest thing I can measure that would distinguish the explanations."**
