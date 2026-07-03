# AGENT PLAYBOOK — how the agent fleet earned the ENTRY piece (S58), written down so the
# EXIT piece (and every later piece) reuses the pattern instead of reinventing it. (S59, Greg)

The entry piece was not one analysis — it was a division of labor across specialized agents,
each with a narrow charter, cheap inputs, and a falsification duty. The five-verdict board,
the master venue law, and the false-fire fingerprints all came out of this structure. Reuse it.

## THE ROLES (who did what for ENTRY)

### 1. SCRAP-HEAP MINERS (2 agents, parallel)
- **Input:** S38–S57 session handoffs + a full code sweep. NO market data.
- **Charter:** find every descriptor/idea KILLED in the archive and re-ask: was it killed at
  THIS band, under THIS fee regime, in THIS role (gate vs grade)? Rank what deserves a
  mid-band retest; list what stays dead and why.
- **Output that mattered:** the 4-member stack candidates (divergence reads, clmx_60, ER,
  lean deceleration) + the two standing warnings that shaped every later round — GRADED
  BEATS GATED (every hard binary veto eventually lost) and SCALE-LOCALITY (every
  (band, descriptor) pair revalidates; kills don't transfer across scales — later proven
  AGAIN when the S56 trough-sell narrative died at mid-band).
- **Why it worked:** archive mining is context-heavy but tape-free — perfect agent work; it
  stopped us from re-deriving known-dead ideas AND from honoring stale kills.

### 2. PER-COIN VERDICT AGENTS (5 agents, one per coin, strictly isolated)
- **Input:** the LEG DUMP for their coin only (`_s58_piece1_legdump.py` rows: kind/agree/
  member bits/dive/clmx/ER/fade-vel/lag/hod + gross), both venues (bins + books), plus the
  round context. NOT the raw tape — the dump is small, causal-by-construction, and lets an
  agent slice hundreds of ways cheaply.
- **Charter (each):** verdict for the deploy round (keep/drop/remap), the coin's FALSE-FIRE
  fingerprint (what passes the stack and loses), WINNER marks (what the big legs looked like
  at entry), the fallback worst-print, a per-coin member map, and a books venue-check.
  MANDATORY falsification duty: attack your own coin's apparent lift before endorsing it.
- **Output that mattered:** the FIVE-VERDICT BOARD (SOL lead / BTC conditional / DOGE
  remapped / XRP naive-only / ETH dropped); the XRP agent's decisive self-refutation (its
  "stack lift" was COMPOSITION — vetoed confirms replaced by fallbacks — shown 3 independent
  ways) which set the re-earn rule below; the death-combo anti-print (opposing+climax
  WITHOUT exhausting, 4x-replicated); ETH's drop with a NAMED re-entry test instead of a
  vague kill.
- **Why per-coin isolation:** the per-cell law in agent form. Pooled analysis had already
  produced Simpson-paradox artifacts twice in program history; isolated agents CANNOT
  pool-blur, and their independent convergences become evidence (see #5).

### 3. TARGETED AUDIT AGENTS (spawned on Greg's questions, one question each)
- Example: the ETH TOP-LEGS AUDIT ("are those 2 legs our biggest? can we snipe just
  them?") — verdict: the big legs were 20–48h trend rides, QUIETER than median at entry,
  and their entry print selects LOSERS on the 30d tape → no snipe exists; drop stands.
- **Pattern:** when Greg asks a pointed question mid-round, a dedicated agent answers THAT
  question against the dumps, with the deflationary reading required alongside.

### 4. VERIFICATION AGENTS (venue/fee facts, primary sources only)
- Kraken fee schedule (0bp maker @$10M/30d, ladder, Jul-9 change, state eligibility) and
  CFM perp fees (no rebate anywhere; 4-7bp RT) — verified against PRIMARY sources + API
  cross-checks, recorded in `S57_VENUE_FINDINGS.md` grade. Never from memory or blogs.
- **Why agents:** fee/eligibility errors are program-lethal (Bybit lesson); a dedicated
  verification pass with citations is cheap insurance.

## THE RULES THAT MADE IT WORK (carry verbatim to EXIT)
1. **Leg-slice reads are HYPOTHESES, machines are VERDICTS.** Every agent map was RE-EARNED
   as a machine config against k0/k3 baselines (round 6) because an always-in flip machine
   is path-dependent — composition ate half of every leg-slice promise (SOL +11.5 promised
   → +5.6 delivered; XRP's lift vanished entirely). NEVER deploy a leg-slice read.
2. **Agents get DUMPS, not tapes.** Build the leg dump first (one script, full causal
   descriptor row AT THE DECISION CELL, leakage-gated); agents analyze it. Cheap, fast,
   reproducible, and no agent can accidentally peek ahead.
3. **Falsification duty in the charter.** The XRP agent finding AGAINST its own coin's
   stack was the round's most valuable single result. Ask every agent to kill its own
   finding first; anti-prints (what to AVOID) count as full deliverables.
4. **Books venue-check is part of every verdict.** Bins say instrument; books say deploy.
   The master law (price mechanics port, flow reads don't) came from agents checking both.
5. **CROSS-AGENT CONVERGENCE = evidence.** Independent agents converging (climax
   load-bearing on all coins; fast fade = winner mark; per-kind AND per-venue member sign
   flips; winners invisible to flow reads — 5/5 agents) is how findings graduated to LAW.
   Convergence only means something because the agents were isolated (#2 above).
6. **One round = one defined test; notes file updated EVERY round; mistakes ledger read
   BEFORE building** (S58_ENTRY_NOTES.md pattern — the exit piece starts its own ledger).

## THE EXIT-PIECE TRANSLATION (how to aim the same fleet at Piece 2)
- **The dump changes, the structure doesn't.** Build an EXIT leg dump: for every leg of the
  promoted mid-band machine, the causal state at candidate EXIT moments — lean_close /
  dipole-collapse state (R8), giveback path (peak-favorable → exit), time-in-leg, adverse/
  favorable excursions, climax/ER at the top, hod — plus what the ORACLE exit would have
  taken. The R8 lean-collapse (~123bp/side prize) and the S55-R9 negative coarse-top dive
  wrinkle are the first candidate reads (parked list, S58_ENTRY_NOTES.md).
- **Scrap-heap first:** one mining pass over the archive for every exit/giveback read ever
  killed (lean_exit inert at fine scale ≠ dead at coarse; the trailing-4h-range axis; the
  climax-collapse half-signature) — at THIS band, in the GRADE role.
- **Per-coin exit agents:** same 4 coins (eth stays dropped), same isolation, charter =
  the coin's GIVEBACK fingerprint (which rides die vs run), the premature-exit anti-print,
  a per-coin exit map, books venue-check, falsification duty.
- **Re-earn as machines:** every exit map runs as a machine config (entry held fixed at the
  promoted registry shapes) vs the flip-at-next-confirm baseline, all fee columns incl.
  kr_mk0, per-week stability, then books check. Sandbox-first when anything wires.
- **Verification agents:** none needed unless a new venue/fee fact enters (Jul-9 Kraken
  post-confirm is already queued).
