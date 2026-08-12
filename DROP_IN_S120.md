# DROP-IN BOX - S120

The harness assigns its own branch. That branch is never the work. Stale tip = you're not on the real
work; empty checkout = the fetch below is the fix.

```bash
git fetch origin claude/kalshi-research-handoff-4l0nt7
git checkout -B claude/kalshi-research-handoff-4l0nt7 origin/claude/kalshi-research-handoff-4l0nt7
git log --oneline -1        # expect b19cdcd "Refresh the master data-point list"
```

Then read: this box -> `SESSION_HANDOFF_2026-08-12_S119.md` -> `OPEN_ITEMS.md` (a render - edit
`research/kalshi/OPEN_ITEMS.json`) -> `python research/kalshi/plant_status.py`.

## 1. THREE BRANCHES ARE LIVE. KNOW WHICH IS WHICH.

| branch | SHA | what it is |
|---|---|---|
| `claude/kalshi-research-handoff-4l0nt7` | `b19cdcd` | ours. master data-point list + kitchen-sink render |
| `chatgpt/agent-frankie-s117` | `d8e8c04` | the shared C2C ledger. **APPEND ONLY (D53)** |
| `claude/frankie-temp-s124` | `c27b5be` | the Claude-operated Frankie run, 4 frozen g18 blind days |

**`plant_status.py` will FAIL on the branch check** - it still expects
`claude/kalshi-agents-coordinator-guard-sg0n15`. Cosmetic, a stale expectation, not a line stop.

## 2. THE SHARED LEDGER

`research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md`, 2,753 lines, blocks C2C-001..C2C-018 all
resolved. Chat posts a task file and a block; you execute and append a
`CLAUDE -> CHATGPT | ID | STATUS: COMPLETE|STOPPED` result. **Read the ledger before acting and only
execute the latest unresolved block.** After pushing, **read it back from the remote** - that check is
the one that catches a truncation.

## 3. STATE AT OPEN

Brain **s105.9, 90 plays - unchanged**. Master data list refreshed: **44 blocks, 1,914 served points,
1,222 read by nothing (64%)**. M-16 physically closed - the paid head tape restored byte-for-byte from
S3 and `vol_regime` rebuilt 311/311.

**The first Frankie forecast to clear structural validation end to end** landed at C2C-018 (an
ABSTAIN, which is the point - declining is now representable). Then the S124 takeover ran **4 of 10
g18 blind days at 0.810x zero_change**, where the S118 GPT arms sat at 0.993x/0.999x, with **80% and
91% of the move called on two days**. Four days is not a result. It is the first sign that magnitude
might carry information.

## 4. WHAT S120 SHOULD DO

**Item zero is a decision, not a build: the six remaining g18 days need a FRESH CONTEXT.** The S119
reasoner read the g18 actuals to score the first four, so it is contaminated for 05-01/04/05/06/07/08.
Run them from a clean session or accept the block as a 4-day sample.

Then, roughly in order of what unblocks the most:

1. **Fix the S121 curve contract.** `_session_position` maps hour 20.0 -> 0.0, so a session closing at
   20:00 is inexpressible and `24.0` is out of range. This burned most of the S124 run's spend.
2. **RFN-1 needs a DIRECTIVE.** It is an INPUT per `spawn.py:583`, not a lookup. The refine cannot run
   until a coordinator writes one. Do not invent it (NC-1).
3. **g17 cannot be blind-forecast** while the brain records g17 outcomes against g17 dates. Retire it
   as a validation target or face the brain question.
4. **A-82 is a token tripwire.** 16 in-window g18 instances pass it because they do not name one of
   the four literal tokens. Decide whether that is acceptable before treating any g18 score as clean.
5. **Correct A-86's registry text** - it measures a blind emission against the refine contract.
6. **A-85's falsifier** over the 200-day corpus. Needs no model backend and the data plane is live.

## 5. STANDING RULES THAT BITE

- **YOU CANNOT AVERAGE (D4/D37).** An R2, a correlation and a fitted slope are all averages. Use
  `research/kalshi/per_event.py`.
- **Nothing local (D34), nothing scratchpad-only (D52).** The S124 run lived in a scratchpad clone and
  had to be committed out of it before the container reclaimed it.
- **No registry line = doesn't exist (D30).**
- **Never weaken a fail-closed invariant to make a run pass.** S119 hit three genuine stops (A-82 on
  g17, TPM on the full-brain packet, DIRECTIVE on RFN-1) and none was routed around.
- **Keys do NOT rotate during the walk.**

## 6. THE FAMILY THIS DESK KEEPS PAYING FOR

Something reports success while doing nothing. S119 added three more instances:

- a `git merge --ff-only` printing `Updating 047d4dd..c607e36` as its **last stdout line** while HEAD
  never moved - exit code 1, blocked by an untracked file. On that stale checkout a gate read
  **33 of 90 and failed**, which would have been reported as chat's redesign being broken.
- a wrapper whose **prose** said "do not use tools" while the **flag** still allowed them, so a tool
  call silently consumed the only turn and killed the run at $0.446 a time.
- a token estimate calibrated against a serialization that **was logged but never transmitted**,
  which would have produced a false STOP on a run that in fact fits.

**Capture exit codes. Observe the fixed path execute. Check the basis of any number before you divide
by it.**
