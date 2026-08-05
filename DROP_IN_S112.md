# DROP-IN — S112

Paste BOX 1. Read the verdict before continuing. Then paste BOX 2.

---

## BOX 1 — BRANCH

```
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
echo "--------------------------------------------------------------"
echo "branch : $(git rev-parse --abbrev-ref HEAD)"
echo "tip    : $(git log --oneline -1)"
echo "tree   : $(git ls-files | wc -l) files tracked"
echo "expect : S111 close-out (or later)"
test -f research/kalshi/FORECAST_ARCHITECTURE_S111.md \
  && test -f research/kalshi/brain_schema.py \
  && test -f SESSION_HANDOFF_2026-08-05_S111.md \
  && test "$(git rev-parse --abbrev-ref HEAD)" = "$B" \
  && echo "BRANCH OK - safe to paste BOX 2" \
  || echo "BRANCH FAILED - do NOT continue. Re-run this box; if it fails again, say so."
```

---

## BOX 2 — READ ORDER AND STATE

**0. READ ORDER.** `research/kalshi/FORECAST_ARCHITECTURE_S111.md` **FIRST — the target changed in
S111 and everything else is downstream of it.** Then `SESSION_HANDOFF_2026-08-05_S111.md` →
`DECISIONS.md` (D29-D32 are new; D23-D27 were Greg's open calls and D23 is now measured) →
`research/kalshi/agents/RUN_SOP.md` (BINDING) → `CLAUDE.md` header.

Research, as needed, not front-to-back: `GAS_SIGNAL_BRIEFING_S111.md` (horizon + the dimension
budget), `COMPETITIVE_BRIEF_S111.md` (the field), `GAS_OPTIONS_SYNTHESIS_S111.md` (options).

**1. EMPTY TO READY.**
```
pip install --quiet numpy pandas matplotlib boto3 databento
python research/kalshi/verify_gold.py      # MUST print PASS + runtime==gold
python research/kalshi/plant_status.py     # andon board: expect ALL CLEAR
python research/kalshi/brain_schema.py validate   # the work list, made visible in S111
```
Keys and `data/` do not survive a session — expected. A group staged at S108+ runs both rounds with
no data plane. Kalshi keys in `scratchpad/kalshi.env` (prod + demo, both verified 200).

**2. STATE.** Brain **s105.0, 82 plays**, now under `meta.schema = brain-schema-1`. No group run in
S111, no merge. G22 and G23 both complete. **G23 was the last staged block — G24 needs a DATA PULL,
not a re-stage.**

**3. THE TARGET, IN ONE PARAGRAPH.** The product is a **price curve**, not a day-move number. The walk
builds a **library**: each past session with its conditions and the curve it traded. Forecasting
inverts it — project conditions, reason to expected **behaviour**, retrieve a past day whose **shape**
matches, re-anchor level, monitor continuously. The analog renders the forecast; it does not make it.
**Level is the only free parameter; amplitude is a rejection test. The scrap signal is slope, not
level. The adjustment loop is the product.**

**4. TWO MEASUREMENTS THAT CHANGE HOW YOU READ THE SCOREBOARD.**
- The blind **loses to a zero-change forecast in six of seven blocks**, and the 939 → 592 "improvement"
  tracked realized volatility falling 799 → 457. **Never report an error number without a named
  benchmark again.** It is a benchmark, not a verdict — those runs were degraded and ran the
  architecture we are replacing.
- **We cannot measure forecast skill until the system can decline to forecast.** One high-confidence
  day in fifty, and the confidence field does not discriminate. Build NO CALL first.

**5. FIRST WORK, IN ORDER.**
1. **Finish the 82-play audit** (`w8319y7l4` if resumable, otherwise re-run from
   `workflows/scripts/brain-play-audit-d24-*.js`). **Correct the rubric first**: it conflates
   `ASSERTED` with a genuinely novel n=1 finding, which Greg explicitly warned against — *"some
   things won't have past instances because it was the first time we saw them but that doesn't make
   them bad."* `NOVEL_N1` is already in the schema's support enum.
2. `python research/kalshi/brain_schema.py sections --write` (dry-run verified lossless in S111;
   held only because the audit was reading the file).
3. **The backfill Greg asked for**: audit output → instances and corpus state into the brain for the
   **58 plays that carry none**. Additive, proposal + adjudication + backup, incumbents untouched.
4. Wire **zero-change and seasonal-naive** baselines into `blind_score_nonpooled`.
5. **Check the weekly balance is not reading a dead page** — EIA Natural Gas Weekly Update's final
   edition was the week ending **21 Jan 2026**. Minutes of work, live staleness risk, our exact hole
   signature.
6. **Fix the false claim in `condition_audit.py` lines 10-11** — it says `gw_hdd >= 16.4` "never
   discriminates INSIDE a block" while the tool's own output says it splits in 7 of 14. That sentence
   was carried into a commit message and into D28.

**6. GREG'S STANDING CALLS FROM S111.**
- **Nothing we declared dead is actually dead** (D31). A refutation is scoped to the cell and the
  instrument it was measured on. The burn gate is first in line, and the seasonal degree-day weight
  rebuild is the test that decides it.
- **A finding with no home in DECISIONS.md does not exist** (D30). Any memo or audit item marked FIX
  becomes a D-line with a status, or it is not a finding.
- **One store, generated views.** Documents that describe what should happen must not sit apart from
  the machinery that makes it happen. `RUN_SOP.md` has 13 slot placeholders filled by hand — that is
  how NC-1 happened. Curve-building doctrine belongs in the brain (served at spawn); plant policy
  stays in the ledger; both files become renders.

**7. LIVE TRAPS.** MBO book files absent for g21/g22/g23 (book layer stands down). Only NGQ26 staged —
roll attribution unanswerable without NGU26. 0710's tape absent from every g23 slice. `ph_absorb` has
no magnitude term. No `wind_chg_7d`. **125 served quantities are globally constant** — dead feeds at a
scale nobody had counted. `deploy/aws/install-ng-live.sh` pins a stale branch.

**KEYS DO NOT ROTATE DURING THE WALK.** git = code + records, S3 = data, `data/` disposable. No emojis.
