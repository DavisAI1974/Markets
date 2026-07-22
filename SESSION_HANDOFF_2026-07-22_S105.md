# SESSION HANDOFF — 2026-07-22, S105 (the BLIND = REFINE-MINUS-PRICE re-architecture + the gold vault)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain: **s102.9, 54 plays** (unchanged this
session — no merges). This session did NOT walk new groups to completion; it STOPPED the walk to fix a
structural problem Greg spotted in the G19 blind render, and the fix turned into a re-architecture of the
blind. Read this in full before touching the agents.

## THE ARC OF THE SESSION
1. **G19 blind ran** (5-specialist sequenced E->A->B, s102.9, full firehose data): 6/10 dir, mean abs err
   751, and I reported "+$2,290 unit P&L, it works." **Greg looked at the render and called it: the red
   blind path sits ~15 cents BELOW the blue actual through the whole covering rally.** The +$2,290 was a
   daily-reset DIRECTIONAL P&L that HID the real failure — as a FORWARD CURVE the blind under-forecast the
   rally magnitude by ~half (integrated peak +2190 / 2.969 vs actual +3610 / 3.136). The scoreboard was
   lying to us. Lesson logged: **grade the forward-curve error, not daily sign.**
2. **Render fix #1 (committed 31e9a2b-era):** the blue actual curve was straight-line-BRIDGING the 51h
   weekend (Fri 05-15 17:00 -> Sun 05-17 20:00) — an S104 "no gap bridges" violation. Added `break_gaps()`
   to both coordinators: insert a NaN break wherever consecutive tape points are >3h apart. Score/data
   unchanged. THIS IS THE ONLY forecast-affecting-nothing cosmetic fix that shipped.
3. **Two code audits run (general-purpose agent, read-only):**
   - **Firehose plumbing audit** — the full MBO+L1 flow (flow_read.py) reaches the state file CLEANLY for
     a well-staged group (G19 proof: all 10 days carry session_signed_flow / phase_signed_flow / l1_book).
     THREE defects, none fired on G19 but all live:
     - **#3 (touched G19):** `flow_read.py` computes `big_print_b_share` SIZE-WEIGHTED, but
       `forecast_harness.py:630` copy list OMITS it, so what lands under that name is the OLD S102
       COUNT-based value. The firehose upgrade to that field is inert; the agents read the weak metric
       under the new name (B's 0518 covering tell fired on 0.507 = the count-based number). Literal
       "poured into the trunk."
     - **#1 (HIGH, silent):** a missing `ng_l1` day drops the whole `l1_book` with NO marker and NO
       download log (`stage_group.py:68-72` discards the `_dl` miss, unlike the leg loop).
     - **#2 (HIGH, silent):** any exception in `flow_read` silently reverts a day to pre-firehose S102
       fields behind a buried `flow_read_error` — a mixed-vintage block with no top-level flag.
   - **Blind/refine PARITY audit — THE ROOT CAUSE of "the firehose made the blind weird":** the blind's
     own directives CONTRADICT each other. `blind_shared.md:44-50` (S105) says "USE the full MBO flow,
     dip_imb_level REPEALED." But ALL FIVE `blind_class_{A..E}.md` still say **"NO MBO / NOT
     dip_imb_level."** The agents get both files -> undefined behavior. We turned the firehose on in the
     shared doc a couple groups ago and NEVER updated the five lenses. (Refine has no such contradiction —
     which is why refine behaves and the blind doesn't.) Plus: `blind_shared.md` still documents the
     RETIRED 3-agent A/B/C averaging panel (not the 5-specialist SELECT machine); the HE24->HE1 handoff
     `--source blind` LEAKS the actual exit state (`group_he24_he1_handoff.py:138` hardcodes actual
     `exit_state` regardless of source — a price mask-leak, and the CLI can't even select blind); and the
     refine render drops the overnight gap (`group_coordinate_refine.py:92` = `gap = 0 if d==seam else 0`,
     both branches 0, a botched port).
   - **The curve regression (Q2):** the blind forecast used to render as ONE continuous curve (S95
     `continuous_rt.py` — one concatenated polyline on the real traded span, NaN only at >3h gaps). The
     S104 "no gap bridges" RENDER RULE (commit b533b0b, carried into the generic coordinators) replaced it
     with a SEPARATE `ax.plot` per day on FIXED clock-hours, which severs EVERY day boundary — including
     weeknights that actually traded through. Both blind and refine are equally segmented in code; the
     blind just LOOKS worse because when the forecast is off, the segments scatter. Fix direction: plot the
     forecast as one polyline with NaN only at real >3h gaps (reuse `break_gaps` on the FORECAST line),
     identically in both coordinators.

## THE DECISION (Greg, decisive, repeated 4x): BLIND = REFINE GOLD, MINUS ONLY THE PRICE CURVE
"Clone refine and take away the price curve and that's the new blind." "Blind wants to be exactly what
refine is." Refine's reasoning is the gold standard (G18 refine r2 err 8, G15 err 72); the blind should
be that same reasoning, blindfolded on price and NOTHING else. Stop maintaining two divergent lens stacks
(that duplication IS how the NO-MBO contradiction crept in).

## WHAT WAS BUILT THIS SESSION (all committed + pushed)
- **`agents/refine_gold_s105/`** — FROZEN byte-identical snapshot of the gold refine stack
  (`mbo_refine_shared.md` + `mbo_specialist_{A..E}.md` + `FROZEN.md`), chmod 0444.
- **`agents/refine_gold_s105/CHECKSUMS.sha256`** — the committed sha256 manifest (the durable wall;
  the container is ephemeral, git is truth).
- **`verify_gold.py`** — the CONCRETE WALLS: (1) HARD wall — recompute every frozen file's sha256 vs the
  manifest; any tamper/missing/extra = `SystemExit`, nothing forecasts; (2) SOFT wall — announce whether
  the LIVE working reasoning still == gold (drift allowed for deliberate experiments, but announced loud).
  `assert_gold_intact()` wired into `stage_group.py` + both coordinators. Tamper detection PROVEN.
- **`agents/blind_mode.md`** — the thin BLIND-MODE wrapper: read AFTER `mbo_specialist_<X>.md`; it
  subtracts EXACTLY ONE thing (the price curve), REPEALS the NO-MBO amputation (blind gets the full flow
  read like refine), frames the blind as the FIRST PASS (no prior to consume, no weight split), same
  output schema so one coordinator scores both. NO separate blind lens set anymore.
- **Render gap-break fix** in both coordinators (`break_gaps()`).
- **THIRD, OFF-SITE COPY (the vault)**: Greg created a dedicated PRIVATE repo **`DavisAI1974/Agent-Davis`**
  and the frozen gold now lives there too (commit `0fd70fc`, branch `main`): `refine_gold_s105/` (the 6
  files + FROZEN.md + CHECKSUMS.sha256 + PROVENANCE.md) + a top-level README. Verified byte-exact on copy,
  chmod 0444. So there are THREE copies in THREE places: (1) working `mbo_*` in Markets, (2) in-repo frozen
  `refine_gold_s105/` (sha256-guarded, halts runs on tamper), (3) off-site private vault Agent-Davis.
  DOCTRINE (Greg): clone FROM the vault for every trading venture, never from a working model; a working
  copy that EARNS promotion becomes a NEW dated snapshot (refine_gold_s106/...), never an overwrite — a
  versioned genome of him. The vault does NOT auto-update (that is the point).

## THE OPEN DECISION THAT GATES EVERYTHING NEXT (Greg said "we talk first — DO NOT JUST START CHANGING")
The gold refine is NOT purely "blind + price" today — it has a SECOND difference: it runs as a POSTERIOR
UPDATE (reads the blind's forecast `grp<N>.json` + emits a blind-vs-MBO weight split). That is an input
the blind doesn't have. So to make "the ONLY difference is the price curve" true, ONE of these must be
chosen — GREG DECIDES THIS FIRST, next session, before any wiring:
- **Option A — true symmetry:** both blind and refine forecast from scratch on the data; refine JUST
  additionally sees the price curve. No reading-the-blind-prior, no weight split. Perfectly clean — price
  is the sole difference. BUT this EVOLVES the refine away from the frozen gold (the gold does the
  posterior update). The running refine would no longer be byte-for-byte the vaulted gold.
- **Option B — preserve the gold refine as-is:** the posterior-update IS part of the frozen "perfection";
  keep it. Accept that refine has one unavoidable extra: it sees the blind's first pass as a prior. The
  DATA difference is still only price; refine just also gets the blind's own guess.
My read: Greg leans A (literally identical reasoning, price the one variable), but A means the live refine
diverges from the vault — so it must be his explicit call. DO NOT assume. `blind_mode.md` currently
encodes the FIRST-PASS framing (compatible with A); if B is chosen, blind_mode + the refine relationship
need a small revision.

## NEXT SESSION — priority order (all gated on the A/B decision above)
1. **Greg decides A vs B.** Then:
2. **Wire the blind to `mbo_specialist_<X>.md` + `blind_mode.md`** (retire — move aside, do not delete —
   `blind_shared.md` + `blind_class_{A..E}.md` + `blind_angle_*`). Unify the coordinator so it scores the
   blind on the SAME `expected_magnitude_usd` / `path_p50_curve` schema refine uses.
3. **Render continuity fix (Q2):** forecast as ONE polyline, NaN only at >3h gaps, both coordinators.
4. **THE VALIDATION RUN (Greg's acceptance test), on G18** (it has BOTH goalposts staged: old blind
   5/10 +$440 AND gold refine err 8): run the new blind twice — (a) price ADDED BACK -> must reproduce
   refine (err ~8) = faithful clone; (b) price MASKED -> the real new blind, compare to old blind 5/10 =
   what un-crippling the flow read buys. Two clean numbers.
5. **Fix the 3 plumbing defects** (#3 big_print_b_share copy-through/rename; #1 log the L1 miss + a per-day
   `firehose_present` flag; #2 surface flow_read_error as a top-level flag).
6. **Then resume the walk**: finish G19 (refine), continue G20+ (staged data-ready), under one-group-at-a-
   time discipline.

## STATE OF THE WALK
- **G19 blind = ON RECORD** (`forecasts/grp19.json`, 6/10, immutable) but built on the CONTRADICTED blind
  stack + the inert big_print_b_share — treat it as SUSPECT, likely to be re-run under the new blind.
- G19 refine NOT run. G17/G18 done+merged (brain s102.9). G20-G23 staged data-ready (group_config).
- Actual G19 ends +1150 (covering rally: 2.75 -> peak 3.136 by 0519 -> 2.865). Seam 0520 (June NGM26 ->
  July NGN26, offset +0.169, correctly voided).

## GUARDRAILS THAT HELD / REINFORCED
- git = code, S3 = data. AWS creds are SECRETS (env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY for
  boto3/platform_sync; scratchpad gitignored). Committer identity noreply@anthropic.com / Claude.
- ONE thing at a time; do not batch changes; talk before changing the blind/refine reasoning.
- P&L (forward-curve error) is the scoreboard, not daily direction hit-rate.
