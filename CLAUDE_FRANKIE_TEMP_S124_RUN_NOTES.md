# S124 CLAUDE-OPERATED FRANKIE — RUN NOTES (partial run, halted by operator)

Branch `claude/frankie-temp-s124`. Takeover contract: `CLAUDE_FRANKIE_TEMP_TAKEOVER_S124.md`.
Starting HEAD `474267bfa0dab11996211867bcddf7c9ea8765db`.

**STATUS: PARTIAL AND DELIBERATELY HALTED.** Greg stopped the run at 4 of 10 g18 blind days and
directed that what landed be preserved. **No score/reveal was run. No refine was run. No actual or RT
outcome was opened at any point.** That ordering is not an accident of the halt — the takeover
forbids scoring until the full blind group is frozen, and the group is not complete.

Everything below is the good and the bad, in the order it happened.

---

## 1. What was verified clean

| check | result |
|---|---|
| branch / HEAD | `claude/frankie-temp-s124` @ `474267b`, matched the required SHA exactly |
| worktree at start | clean, 0 tracked modifications |
| `research/kalshi/spawn.py` blob | `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e` — protected pin, **never modified** |
| adapter tests | `test_frankie_claude_code_temp.py` **6/6 passed** (before and after the one fix below) |
| auth path | **Claude Code CLI subscription**. The wrapper stripped `ANTHROPIC_BASE_URL` from the child env; probe returned `AUTH_OK`. **No Anthropic API key, no Bedrock, no Vertex, no OpenAI.** Model reported by the CLI: `claude-sonnet-5` |
| g18 preflight | `PACKETS_CAUSAL`, 90 canonical / 90 full play bodies served, `play_index` retained, A-82 clean, `realized_outcome_in_packet: false` |

---

## 2. THE BAD, PART ONE — g17 is not a valid blind target, and this is structural

**g17 preflight fails A-82 and it is a correct fail-closed stop. It was not worked around.**

```
STOP - ForecastStop: outcome leak: 'actual_day_move_usd' has no attributable
                     historical date in g17 20260413 packet
```

Traced to the brain, not the state. Play **`structure.accumulation_arm_turn`**, instance:

```
date:        20260422          <- INSIDE g17's own forecast window
group:       g17
source_file: ... + research/kalshi/renders/ng_refine_s95/g17_actual.json
what_the_day_did: "verifies: refined_day_move_usd +130 against actual_day_move_usd +140,
                   dir_hit true ..."
```

The blind wall redacts in-window dates, so the date was stripped; the **realized value `+140`
survived**; A-82 then found an unattributable realized token and failed closed. Exactly as designed.

Clearing it would require editing the brain, weakening A-82, or widening the mask to strip values.
All three are explicitly forbidden by the takeover. **So g17 stops, and it will keep stopping until
someone with authority over the brain decides what to do.**

### The wider measurement, which matters more than the single stop

**20 brain instances carry dates inside the g17/g18 windows — 4 in g17, 16 in g18.**

g18 passes A-82 only because **none of its 16 in-window instances name one of the four literal leak
tokens** (`actual_day_move_usd`, `actual_close`, `actual_net_usd`, `actual_gap_usd`). The guard is a
token tripwire with a 500-char context window, not a semantic check. In-window instances that
narrate an outcome in prose pass straight through.

Examples of g18 in-window instances the guard does not see:
`flow.price_free_absorption_proxy` on 20260427 (g18's own first day), 20260429, 20260430, 20260507;
`magnitude.terminal_impact_coefficient_carry` 20260429, 20260506; `direction.absorption_is_reversal`
20260430; `selector.midblock_right_the_ship` 20260505, 20260506.

**This is a caveat on what any g18 score can mean.** It is pre-existing — identical for the S118 and
C2C-018 runs — and was not introduced by this run. It is recorded here because it was measured here.
Nothing was changed in response to it.

---

## 3. Missing g17 state — found in the repo, not fabricated

`research/kalshi/renders/ng_refine_s95/grp17_state.json` did not exist. g17 was the **only** gap in
g6–g24. The file exists at HEAD at the pre-restructure path `renders/ng_refine_s95/grp17_state.json`
(root level, 591,843 bytes).

Before trusting the older tree, its vintage was tested rather than assumed:

```
grp18_state.json   root vs harness tree   IDENTICAL   (sha256 58cb3d3ba9a946ea...)
grp19_state.json   root vs harness tree   DIFFERENT
```

So the root tree is the same vintage for g18 but is **not** uniformly current (g19 was re-staged
later; g17 never was). The g17 state was copied to the harness path byte-identically. **No content
was altered and nothing was fabricated.**

**It is deliberately NOT committed.** Committing it would put a second copy of one artifact in the
repo — the failure shape this project has already paid for. g17 cannot run anyway (section 2). To
reproduce: `cp renders/ng_refine_s95/grp17_state.json research/kalshi/renders/ng_refine_s95/`.

### A trap avoided, worth writing down

`frankie_two_group_run_s118.prepare()` was NOT used to materialize anchors/slices. Two reasons:
its `GROUPS` is still `("g18","g19")`, and its first statement is `runner.ALLOWED_GROUPS = GROUPS`,
which would have **silently rescoped the harness away from the g17/g18 scope this takeover
mandates.** Instead `_materialize_anchor()` and `_build_slices()` were called directly for g17 and
g18, and `ALLOWED_GROUPS` was asserted unchanged at `('g17','g18')` afterwards. Anchors come from
`group_config` declared values (`actual_tape_read: False`); slices come from
`build_causal_slices.py` off the committed state. 10 slices built per group.

---

## 4. THE BAD, PART TWO — three distinct reasoner/transport failures

The blind step failed repeatedly before producing anything. Three separate causes, and only one of
them was a defect I was permitted to fix.

### (a) FIXED — the tool lockdown was incomplete, and it cost real money

```
Claude Code exited 1: stop_reason "tool_use", terminal_reason "max_turns",
errors ["Reached maximum number of turns (1)"]     cost: $0.446 for that one dead call
```

`OPERATOR_GUARD` *tells* the model not to use tools, but `DEFAULT_DISALLOWED_TOOLS` only listed
`Bash,Read,Write,Edit,MultiEdit,Glob,Grep,WebFetch,WebSearch,NotebookEdit`. `TodoWrite`, `Task`,
`Skill` and others remained callable. One tool call consumed the single permitted turn and the run
died before any JSON came back — **prose guidance was doing the work a flag should have been doing.**

Fix applied (the only code change in this run): extend the disallowed set so no tool is callable.
`--max-turns` was left at `1` **specifically so the pinned assertion in
`test_frankie_claude_code_temp.py:114` stays true** — buying extra turns would have meant editing a
test to make a run pass. This is a transport-layer change only: same packet, same brain, same
instructions, same guards. Tests re-run **6/6**.

### (b) NOT FIXED, stochastic — non-chronological curve

```
STOP - ForecastStop: g18 20260427: curve timestamps must be strictly chronological
```

Twice in a row on the same day. The validator was checked before being blamed: `_session_position`
handles the midnight wrap correctly (20→0, 22→2, 0→4). A standalone diagnostic on the same cell then
returned a **valid** 12-point curve with zero non-increasing pairs, so the fault is intermittent
model output, not a broken check. No artifact was written and no actuals were read, so the blind step
was rerun under takeover §5 rather than anything being weakened.

### (c) NOT FIXED, and it is a genuine contract gap — the 20:00 session close is inexpressible

```
STOP - ForecastStop: g18 20260430: curve ET time 24.0 outside [0,24)
```

Measured on `frankie_s121_curve_restore`:

```
hour 20.0  -> session position  0.00
hour 22.0  -> session position  2.00
hour  0.0  -> session position  4.00
hour 19.99 -> session position 23.99
hour 20.0  -> session position  0.00     <- a session CLOSING at 20:00 maps back to 0.0
```

So a full 20:00 → 20:00 session **cannot** close at hour 20.0 (fails strict-increase), and `24.0` is
rejected by the `[0,24)` range check. The only expressible session end is strictly before 20:00.
The reasoner reached for both illegal forms, which is very likely the common root of (b) and (c).

**This was not touched.** Changing it means changing the output contract. It is flagged for whoever
owns S121. It is also the main cost driver: several ~$0.45 calls were spent on it.

---

## 5. What landed — 4 of 10 g18 blind days, frozen and unrevealed

`research/kalshi/forecasts/claude_s124_g17g18_01/`

| artifact | sha256 (first 16) | bytes | disposition | net | gap | conf | curve pts | fired | stood down | defects reported |
|---|---|---|---|---|---|---|---|---|---|---|
| `grp18_B_20260427.json` | `ff73e444b4682f1a` | 6,514 | CALL | **-550** | -180 | low | 12 | 7 | 7 | 6 |
| `grp18_C_20260428.json` | `01ae23f83f9a397d` | 6,359 | CALL | **-300** | -50 | low | 12 | 3 | 11 | 5 |
| `grp18_C_20260429.json` | `01a2926cbd533738` | 7,871 | CALL | **-350** | -50 | low | 14 | 4 | 12 | 5 |
| `grp18_D_20260430.json` | `d3dd502219d65226` | 8,386 | CALL | **+400** | +50 | low | 18 | 5 | 9 | 4 |

Owners match `owner_map` (B, C, C, D). Every day is a **CALL, not an abstention**, every one carries a
real endogenous multi-point curve, and every one is `confidence: low`.

**The good, and it is worth saying plainly:** these are the first Frankie blind artifacts with
genuine self-chosen intraday structure — 12 to 18 points at irregular timestamps, not a fixed grid
and not a straight line through a decided net. The S121 endogenous-timestamp contract is doing what
it was built to do. Note `20260430` produced 18 points and a `+400` call *after* the earlier `24.0`
rejections on that same day, so the contract is satisfiable.

**Missing: 20260501, 20260504, 20260505, 20260506, 20260507, 20260508.**

**Immutability:** hashes above were taken at halt, before any reveal step existed. No score was run,
so no artifact has been touched by post-reveal information.

---

## 6. What was NOT done, and why

- **No score/reveal.** The blind group is incomplete; the takeover forbids scoring before the full
  group is frozen. Running it on 4 of 10 would have burned the causal wall for a partial number.
- **No RFN-1 refine.** The wrapper refuses refine until every blind day of the group exists, and it
  is right to.
- **No g17 anything** beyond preflight (section 2).
- **No new datapoints, no data-surface change, no brain/schema/mask/threshold/ownership change, no
  prompt change, no `spawn.py` change.** The only code change in the entire run is section 4(a).

---

## 7. Honest cost note

Every failed inference still bills. One recorded dead call was **$0.446** with **769,789 cache-read
tokens**; several more were spent on failure modes (b) and (c) before the first artifact landed.
Roughly half the spend in this run bought nothing but the three diagnoses above. That is the real
price of the S121 contract gap and the incomplete tool lockdown, and it is why both are written up
here rather than left as folklore.

---

## 8. Is the cycle clean enough to move forward?

**Not yet — and the blockers are named, not vague.**

What is proven: the existing Frankie framework **can** be driven by Claude on subscription auth with
the full 1,800+ causal surface and the full 90-play brain, producing contract-valid blind artifacts
with real intraday paths, with A-82 and the future-price mask intact and `spawn.py` untouched.

What is not proven: **a complete blind group, a reveal/score, or a refine.** None of those ran.

Three things gate the next attempt:

1. **S121 curve contract** — make the session close expressible, or accept that the reasoner will
   keep failing on it. Owner's call; not mine.
2. **g17** — it cannot be blind-forecast while the brain records g17 outcomes against g17 dates.
   Either g17 is retired as a validation target or the brain question is faced directly.
3. **A-82 is a token tripwire** — 16 in-window g18 instances pass it. Worth knowing before treating
   a g18 score as clean.

None of these is a reason to weaken anything. All three were found by running the system as-is,
which is what the takeover asked for.
