# DROP-IN BOX — S106 (start a FRESH session with this)

## 0. Branch + read order (do this first, every session)
```
git fetch origin claude/kalshi-agents-coordinator-guard-1175nr
git checkout -B claude/kalshi-agents-coordinator-guard-1175nr origin/claude/kalshi-agents-coordinator-guard-1175nr
git log --oneline -1     # confirm tip: the S105 gold-vault + one-shared-rule-set work (not a stale tip)
python3 research/kalshi/verify_gold.py   # confirm the refine gold vault is intact + whether runtime == gold
```
Read in order: `SESSION_HANDOFF_2026-07-22_S105.md` (this session, IN FULL) -> `research/kalshi/agents/README.md`
(the handbook, updated S105) -> `CLAUDE.md` header.

## 1. SETTLED (Greg, FINAL, S105) — blind and refine are ONE agent; price is the only difference
The old blind is DELETED and does not exist. The blind IS the 5-specialist engine
(`mbo_specialist_{A..E}.md` + `mbo_refine_shared.md`) run on a PRICE-MASKED state. "Refine" = the SAME
files on a state that includes price. Blind and refine read the IDENTICAL committed rule files, byte-for-
byte - there is NO blind-specific file (the `blind_mode.md` wrapper was deleted too; a separate file could
drift). The one difference (price) lives in the DATA. No A/B question, no validation tests. Build + run.

## 2. What's already BUILT and PROTECTED (S105 — do not rebuild)
- `agents/refine_gold_s105/` = FROZEN gold refine (chmod 0444) + `CHECKSUMS.sha256`. UNTOUCHABLE.
- `verify_gold.py` = the walls; `assert_gold_intact()` is wired into stage_group + both coordinators
  (a violated vault = SystemExit, nothing forecasts). Runs on every stage/coordinate.
- NO blind-specific file: blind = the refine files (`mbo_refine_shared.md` + `mbo_specialist_{A..E}.md`) on a price-masked state.
- Render `break_gaps()` fix (no weekend straight-line bridge) in both coordinators.
- THREE copies of the gold now exist: (1) working `mbo_*`, (2) in-repo frozen `refine_gold_s105/`,
  (3) OFF-SITE PRIVATE VAULT `DavisAI1974/Agent-Davis` (commit 0fd70fc, main). Clone FROM the vault for
  any venture, never from a working model. A working copy that EARNS promotion = a NEW dated snapshot in
  the vault (refine_gold_s106/...), never an overwrite. The vault does not auto-update.

## 3. Then, in order
1. Wire the blind spawn -> the SAME `mbo_specialist_<X>.md` + `mbo_refine_shared.md` on a price-masked state (no blind-specific file exists). Unify
   the coordinator schema so the blind emits the refine `expected_magnitude_usd` / `path_p50_curve` and
   ONE coordinator scores both.
2. Render continuity fix (Q2): forecast as ONE polyline, NaN only at >3h gaps, both coordinators.
3. Fix 3 plumbing defects: #3 big_print_b_share (copy the size-weighted value through at
   forecast_harness.py:630, or rename to end the count-vs-size collision); #1 log the ng_l1 miss in
   stage_group + add a per-day `firehose_present` flag; #2 surface `flow_read_error` as a top-level flag.
4. DATA (Greg S105) - LIVE MBO is the ticket, but the $1,500 Plus bump is NOT how to get it (research
   flipped this): live CME is ALREADY in the Standard plan (~$179; Databento moved live CME into the
   subscription Apr 2025, NYMEX/NG covered). The real gate is the CME EXCHANGE LICENSE - complete
   Databento's CME license questionnaire + pay pass-through CME Globex fees (non-pro = modest;
   pro/firm = higher). We do NOT need more historical (already on S3). GREG TO CHECK IN-ACCOUNT (saves
   ~$1,500/mo): (a) live GLBX.MDP3 entitlement active vs historical-only? (b) CME license questionnaire
   signed? = the live switch. (c) pro vs non-pro. THEN stand up live MBO ingest (NG first) on the
   existing Standard plan; skip Plus. Refs: databento.com/pricing, /blog/real-time-cme.
5. Resume walk: re-run G19 blind under the new blind (the on-record grp19.json is SUSPECT — built on the
   deleted contradicted stack + inert big_print_b_share), then G19 refine, then G20+ (staged), one group
   at a time.

## 4. Standing doctrine (load-bearing — do not relearn the hard way)
- **Data doctrine**: both agents get the KITCHEN SINK; the blind's ONLY mask is the PRICE CURVE. The blind
  gets the FULL non-price MBO+L1 flow read. NO-MBO-in-the-blind is DEAD.
- **Scoreboard = forward-curve error / P&L, NOT daily direction hit-rate** (the +$2,290 that hid a 15c
  curve drift is the cautionary tale).
- One group = two weeks; stage all groups' data ready but RUN one at a time. One thing at a time; talk
  before changing the blind/refine reasoning.
- git = code, S3 = data; AWS creds SECRET (env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY for boto3);
  committer noreply@anthropic.com / Claude; no emojis.
