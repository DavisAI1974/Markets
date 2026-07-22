# DROP-IN BOX — S106 (start a FRESH session with this)

## 0. Branch + read order (do this first, every session)
```
git fetch origin claude/kalshi-agents-coordinator-guard-1175nr
git checkout -B claude/kalshi-agents-coordinator-guard-1175nr origin/claude/kalshi-agents-coordinator-guard-1175nr
git log --oneline -1     # confirm tip: the S105 gold-vault + blind_mode work (not a stale tip)
python3 research/kalshi/verify_gold.py   # confirm the refine gold vault is intact + whether runtime == gold
```
Read in order: `SESSION_HANDOFF_2026-07-22_S105.md` (this session, IN FULL) -> `research/kalshi/agents/README.md`
(the handbook, updated S105) -> `CLAUDE.md` header.

## 1. THE FIRST THING — Greg decides A vs B (nothing else moves until then)
The blind is being re-architected to be **the refine gold specialist minus ONLY the price curve**
(Greg's decisive call, S105). But the gold refine has a SECOND difference: it's a POSTERIOR UPDATE (reads
the blind's forecast + weights blind-vs-MBO). To make "price is the only difference" true, Greg picks:
- **A — true symmetry**: both forecast from scratch; refine just also sees price. Clean, but EVOLVES
  refine off the frozen gold.
- **B — preserve the gold refine**: keep its posterior-update; accept refine also sees the blind's prior.
DO NOT ASSUME. DO NOT START CHANGING THINGS. Ask Greg, then proceed. (`blind_mode.md` currently encodes
A-compatible first-pass framing.)

## 2. What's already BUILT and PROTECTED (S105 — do not rebuild)
- `agents/refine_gold_s105/` = FROZEN gold refine (chmod 0444) + `CHECKSUMS.sha256`. UNTOUCHABLE.
- `verify_gold.py` = the walls; `assert_gold_intact()` is wired into stage_group + both coordinators
  (a violated vault = SystemExit, nothing forecasts). Runs on every stage/coordinate.
- `agents/blind_mode.md` = the blind = gold-specialist-minus-price wrapper (repeals the NO-MBO amputation).
- Render `break_gaps()` fix (no weekend straight-line bridge) in both coordinators.
- THREE copies of the gold now exist: (1) working `mbo_*`, (2) in-repo frozen `refine_gold_s105/`,
  (3) OFF-SITE PRIVATE VAULT `DavisAI1974/Agent-Davis` (commit 0fd70fc, main). Clone FROM the vault for
  any venture, never from a working model. A working copy that EARNS promotion = a NEW dated snapshot in
  the vault (refine_gold_s106/...), never an overwrite. The vault does not auto-update.

## 3. Then, in order (all gated on step 1)
1. Wire blind spawn -> `mbo_specialist_<X>.md` + `blind_mode.md`; retire (move aside, don't delete)
   `blind_shared.md` + `blind_class_{A..E}.md` + `blind_angle_*`. Unify coordinator schema
   (`expected_magnitude_usd` / `path_p50_curve` for both).
2. Render continuity fix (Q2): forecast as ONE polyline, NaN only at >3h gaps, both coordinators.
3. **VALIDATION on G18** (has old blind 5/10 +$440 AND gold refine err 8 staged): new blind (a) price
   ADDED BACK -> must reproduce refine err ~8 (faithful clone); (b) price MASKED -> real new blind vs old
   blind 5/10. PRINT both renders.
4. Fix 3 plumbing defects: #3 big_print_b_share (copy the size-weighted value through at
   forecast_harness.py:630, or rename to end the count-vs-size collision); #1 log the ng_l1 miss in
   stage_group + add a per-day `firehose_present` flag; #2 surface `flow_read_error` as a top-level flag.
5. Resume walk: re-run G19 blind under the new blind (the on-record grp19.json is SUSPECT — built on the
   contradicted stack + inert big_print_b_share), then G19 refine, then G20+ (staged), one group at a time.

## 4. Standing doctrine (load-bearing — do not relearn the hard way)
- **Data doctrine**: both agents get the KITCHEN SINK; the blind's ONLY mask is the PRICE CURVE. The blind
  gets the FULL non-price MBO+L1 flow read. NO-MBO-in-the-blind is DEAD.
- **Scoreboard = forward-curve error / P&L, NOT daily direction hit-rate** (the +$2,290 that hid a 15c
  curve drift is the cautionary tale).
- One group = two weeks; stage all groups' data ready but RUN one at a time. One thing at a time; talk
  before changing the blind/refine reasoning.
- git = code, S3 = data; AWS creds SECRET (env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY for boto3);
  committer noreply@anthropic.com / Claude; no emojis.
