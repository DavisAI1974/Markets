# SESSION HANDOFF - S119 (2026-08-12)

**Three branches touched, deliberately kept separate. Brain s105.9, 90 plays - UNCHANGED, no merge,
no group scored into the record.**

| branch | final SHA | what it carries |
|---|---|---|
| `chatgpt/agent-frankie-s117` | `d8e8c04` | the shared C2C ledger, blocks C2C-008 .. C2C-018 |
| `claude/kalshi-research-handoff-4l0nt7` | `b19cdcd` | refreshed master data-point list + kitchen-sink render |
| `claude/frankie-temp-s124` | `c27b5be` | the Claude-operated Frankie run: 4 frozen g18 blind days |

Read `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` for the C2C detail (it is append-only
and now 2,753 lines), `CLAUDE_FRANKIE_TEMP_S124_RUN_NOTES.md` and `S124_FRANKIE_ACCOUNT.md` on the
temp branch for the Frankie run.

---

## PART ONE - M-16 IS PHYSICALLY CLOSED, AND THE PAID DATA WAS NEVER AT RISK

**C2C-008 inspection verdict: M-16 was PARTIALLY FIXED, and the fixed half was not on the trunk.**
`databento_backfill.py` is byte-identical across branches, so all three original bugs are live
everywhere: relative `OUT_DIR`/`MBP10_DIR`/`L1_DIR`, `_write_df` with no `out_dir` while both
siblings have one, and a log line printing the requested destination. The guarded wrapper existed
only on chat's branch.

**Two defects found in that guard, both observed executing rather than read off the source.**
`_files_for` dispatched `mbp-10` into the `mbp-1` branch (`"mbp-10".startswith("mbp-1")` is True), so
every depth pull STOPped with data on disk; and in `range` mode the row count was derived from the
destination, making the landing assertion a tautology that could not fire. Chat fixed both; verified
4/4 by running each firing path.

**C2C-009/010: the data was on S3 all along, complete.** Head trades 74 of 74 weekdays of the paid
window; `ng_l1` 326 day files / 742.5 MB covering the full window. The restore reproduced the S3
evidence **byte for byte** - 311 files, 85,835,820 bytes, paid window bytes 15,418,181 identical.
`vol_regime` rebuilt, 311/311 valid, its one gap being Good Friday.

**A correction I had to make to my own C2C-009 stop:** I flagged `ng_l1` as most likely to need the
paid-job re-serve. Wrong - I computed that window inclusively and read `20260806` as missing; the job
record shows `end` is exclusive, so a store ending `20260805` is complete. The vendor record settled
it, not the file listing.

**Two operational findings recorded:** the box's SSM instance role cannot `ListBucket` on the data
bucket, so the documented one-command restore fails under the instance profile alone (it works from
`/etc/markets/*.env`); and sourcing `markets.env` fails under `sh` because a value contains
parentheses.

---

## PART TWO - THE BEDROCK LANE OPENED AND THEN DENIED AT RUNTIME

**A-79's form-and-agreement half is genuinely closed.** Greg submitted the console form; C2C-012
accepted the Opus 5 agreement on the single authorized call and availability went
`NOT_AVAILABLE -> PENDING -> AVAILABLE` in 30 seconds and has held. I deliberately did not invoke at
PENDING - spending a one-shot budget on a half-open gate buys nothing.

**The canary was then denied at the Bedrock runtime:** `anthropic.claude-opus-5 is not available for
this account`. No retry, budget spent. Reported as measurement with no cause proposed, because this
is the exact error-shape family I got wrong three times at S118.

**C2C-013 localised it to BRANCH 3 - a different failure.** One Converse against
`us.anthropic.claude-haiku-4-5-20251001-v1:0`, matched on region and profile shape, returned
`ResourceNotFoundException: Model use case details have not been submitted for this account ... try
again in 15 minutes`. Different exception class, different message. So the probe did not localise
Opus 5; it hit a prior account-level gate. **Control plane and runtime disagree**: the form reads
stored and Opus 5 reads AVAILABLE while the runtime says the details were never submitted. One
repeat of that probe after the window separates propagation lag from a real gate. Not run.

---

## PART THREE - THE OPENAI LANE, AND THE FIRST FORECAST TO PASS VALIDATION

**C2C-014 first attempt: the deployed key had no inference scope.** `models.list` 403 missing
`api.model.read`; `responses.create` 401 missing `api.responses.write`. That is the tunnel runtime
key from C2C-005 - tunnel scopes, not inference. Flagged the trap rather than acting on it:
`/markets/OPENAI_API_KEY` is what Markets Terminal authorizes against, so overwriting it risks
reproducing the S118 `tunnel_use_forbidden` episode. Two parameters is probably the clean answer.

**After Greg replaced the key it ran.** `gpt-5.6-sol` confirmed present (the `gpt-5.6` alias is not
listed). 297,670 input tokens. The model emitted the contract shape correctly - 13 points on the
2-hourly ET clock - and then **ABSTAINED**, so A-86 rejected it as a decorative straight line.
**An abstention and a fake curve both have shape deviation 0.0.** That finding produced chat's
`disposition` field.

**C2C-017: every gate green, 7% too big to send.** 90 canonical / 90 full play bodies served,
`play_index` retained, A-82 clean - then `RateLimitError 429, TPM limit 500000, requested 535833`.

**C2C-018: lossless compaction cleared it and the canary PASSED.** Pretty 2,074,610 -> compact
1,789,638 bytes, 13.74% saved, semantic round-trip equal, 90/90 intact. One invocation, 477,817
input tokens, **disposition ABSTAIN, S120 structural verdict PASS** - the first Frankie forecast to
clear structural validation end to end. Declining is now representable, which is the S111
prerequisite.

**Two disclosures on that pass.** The actual input of 477,817 exceeded the 475,000 safety target by
2,817 (the estimate that authorised the call was 462,255; my estimator ran 3.3% low), so the intended
headroom was not really there. And my first estimate would have caused a **false STOP** because it
calibrated against `json.dumps(packet, sort_keys=True)` - the figure C2C-017 logged as `packet_bytes`
but never transmitted; the sent string was the `indent=2` form.

**A correction chat was right to force.** My "0 of 14 canonical fields" census measured a BLD-1 blind
emission against the **refine** contract in `mbo_refine_shared.md` (its field list sits under Round 2
and mirrors `blind_direction`/`blind_net_usd` as inputs). **A-86's registry text carries the same
conflation and needs correcting there.** The curve half of A-86 survives intact.

---

## PART FOUR - THE MASTER DATA LIST WAS STALE

`data_registry.py build --write` against the live decision-state files:

```
blocks                 36 ->  44
SERVED data points  1,717 -> 1,914
...READ BY NOTHING  1,113 -> 1,222      (64% of the served surface)
HELD not served        68 ->   5
PLANNED                52 -> 124
IDENTIFIED            119 ->   9
```

Eight blocks and ~200 fields had landed since it was last written, so anything answered from that
store was answered off an old surface. `selftest` 11/11 after the write. `model_disagreement` alone
is 464 fields, 380 of them unread.

---

## PART FIVE - THE CLAUDE-OPERATED FRANKIE RUN (S124 takeover)

Executed `CLAUDE_FRANKIE_TEMP_TAKEOVER_S124.md` on `claude/frankie-temp-s124` from HEAD `474267b`.
Auth: **Claude Code CLI subscription** (`ANTHROPIC_BASE_URL` stripped by the wrapper; no API key, no
Bedrock, no Vertex). Adapter tests 6/6. `spawn.py` never modified, blob verified at open and close.

### g17 is not a valid blind target, and that is structural

A-82 fails closed on g17. Brain play `structure.accumulation_arm_turn` carries an instance
**dated 20260422, inside g17's own window**, `group: g17`, sourced from `g17_actual.json`, narrating
`actual_day_move_usd +140`. The blind wall redacts the in-window date; the realized value survives;
A-82 then cannot attribute it. Clearing it means editing the brain, weakening A-82, or widening the
mask - all forbidden.

**Wider measurement: 20 brain instances are dated inside g17/g18 windows - 4 in g17, 16 in g18.**
g18 passes only because none of its 16 names one of the four literal leak tokens. **A-82 is a token
tripwire with a 500-char context window, not a semantic check.** Pre-existing, not introduced here.

### What ran: 4 of 10 g18 blind days, then the operator halted

| day | called | actual | \|err\| | called % | direction |
|---|---|---|---|---|---|
| 20260427 Mon B | -730 | +370 | 1,100 | 197% | **wrong sign** |
| 20260428 Tue C | -350 | -440 | 90 | 80% | hit |
| 20260429 Wed C | -400 | -440 | 40 | 91% | hit |
| 20260430 Thu D | +450 | +1,230 | 780 | 37% | hit |

Per event, never pooled. Against `zero_change` these four land at **0.810x**, where the S118
GPT-driven arms sat at 0.993x and 0.999x. **The called-% column is the part worth attention: 80% and
91% on two days is sizing, not the roughly constant band A-85 described.** It is also four days with
one wrong-signed miss large enough to swamp the rest, on an incomplete group, with no refine.

All four are CALLs with **self-chosen intraday structure** - 12 to 18 irregular timestamps. The S121
endogenous-timestamp contract is doing what it was built for.

### Three run defects, one fixed

1. **FIXED (transport only).** `DEFAULT_DISALLOWED_TOOLS` was incomplete - `TodoWrite`/`Task`/`Skill`
   stayed callable, a tool call consumed the single permitted turn, and Claude Code exited
   `error_max_turns` before returning anything. **$0.446 for one dead call.** The guard's prose said
   "do not use tools" while the flag allowed them. `--max-turns` left at 1 so the pinned assertion in
   the adapter test stays true rather than editing a test to make a run pass.
2. **NOT FIXED, and it is a contract gap.** `frankie_s121_curve_restore._session_position` maps hour
   20.0 -> 0.0, so **a session closing at 20:00 cannot be expressed** (fails strict-increase) and
   `24.0` is rejected as out of `[0,24)`. The reasoner reached for both illegal forms repeatedly.
   Main cost driver of the run.
3. **RFN-1 is blocked on a coordinator input.** `template RFN-1 needs slots that did not resolve:
   DIRECTIVE`. `spawn.py:583` states DIRECTIVE is an INPUT, not a lookup. Inventing one would repeat
   NC-1. **It failed before any model call, so nothing was spent.**

### Documents produced on the temp branch

- `CLAUDE_FRANKIE_TEMP_S124_RUN_NOTES.md` - the full run record, good and bad.
- `S124_FRANKIE_ACCOUNT.md` - **the forecaster's own words per day**: the call, the full reasoning,
  every play fired, every play stood down with its stated reason, and everything it said it did not
  have. No averaging anywhere; each day is its own instance (D4/D37).
- `research/kalshi/renders/s124_claude_blind_vs_actual.html` - blind path vs realized tape per day.

### What Frankie asked for, in its own words

The 04-27 account opens by naming its own handicap: *"No inbound bridge from A this run (A did not
spawn), so I own the Monday number unaided."* That is the wrong-signed day, and it is the same
inheritance hole S104 traced 10 of 14 bad Mondays to. Recurring across the four days: **null
`vol_regime`**, **`options_surface` strikes incompatible with the front settle** (the S110 f5 defect
again), an **incomplete storage family**, and **no forward wind/solar expectation**.

Discipline worth noting: on 04-27 it had Friday buy flow (+3,189, big-print share 0.593) and
**explicitly refused to read it as bullish**, citing the play that measures that instrument at
coin-flip for D-1 use, and declined the crowded-short up-gap because `chg_wow` was +13,521. It got the
day wrong without ignoring its brain.

---

## STANDING / OUTSTANDING AT CLOSE

- **ROTATE THE OPENAI KEY** remains open in spirit: the key was replaced for inference, but the
  tunnel/inference parameter split (section three) was flagged and NOT acted on.
- **Reading the g18 actuals contaminates this reasoner for the six remaining g18 days**
  (20260501/04/05/06/07/08). They must be run from a fresh context.
- **A-86's registry text needs correcting** - it measures a blind emission against the refine schema.
- **`grp17_state.json` lives only at the pre-restructure root path.** Deliberately not committed to
  the harness path; a second copy is the duplication hazard. `cp` line is in the run notes.
- Bedrock: one repeat of the Haiku probe separates propagation lag from a real account gate.
- **Keys do NOT rotate during the walk.**
