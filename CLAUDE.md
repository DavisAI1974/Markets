# CLAUDE.md — DavisAI Markets / Kalshi (Updated 2026-07-14, Session 93)

## Agent roles (Greg, 2026-11-23)

Four subagents in `.claude/agents/`. The main session routes work to them:

- **scout (Haiku)** - every locate/search/read-the-docs job: where code lives, what calls what,
  which handoff or runbook covers a topic, what a MANIFEST.json entry says. Returns exact pointers,
  every hit; in extraction mode, source-tagged claim JSON for the graph. Does not interpret results.
- **builder (Sonnet)** - implements a settled plan and runs tests. Shows the diff before writing.
  Stops after the second failure of the same test and hands back.
- **reviewer (Opus)** - called on: a plan touching root/calcs, the tape, causal prefixes,
  leakage, the teacher, Granite or BOSS contracts; any step that failed twice; the final diff
  before it goes to Greg or Codex. Read-only.
- **frankie-performance-auditor (Sonnet)** (Codex, b0e5546; Sonnet and no-AWS edit 2026-11-23) -
  read-only runtime/cost audit of a named Frankie workflow: RunPod Pod, GitHub runner and model
  API token spend. AWS is not available.

Every run of the scout, the builder and the reviewer is audited by the performance auditor, each
run its own row, against the limits written for it before it started. `python3 -m tools.kgraph.auditor_called`
lists the runs no auditor's report has a row for and fails while any is listed; it is run before a
ticket's box is marked and at the close of every session (Greg, 2026-11-24, ticket 03b).
A ticket's box is not marked while a run that worked on that ticket is unaudited (`--ticket NN`). The auditor's
report for each of its runs is kept in git word for word.
The report's first line begins `# Performance auditor run N` and each audited run has its own heading `## Run NNN` at the
start of a line; an auditor's run whose report cannot be read from git at the commit its line names, or is another
run's, fails the command.

The main session does not grep or bulk-read files itself when the scout can. Interpretation of
results stays in the main session and with Greg. Codex review and Greg's merge authority are
unchanged.

## The agent program (built 2026-11-24, twenty-first session; on the session's branch, not on the trunk)

Stages 2 to 8 of the graph adoption plan are built in `tools/` (`exp_dag.py`, `kgraph/`, `ratchet/`,
`swarm/`, `token_test/`); their records are in markets-data `graph/` and `experiments/`. The manual is
`tools/README_AGENT_PROGRAM.md`. A session starts from the graph, not from the handoff pile:
`python3 -m tools.kgraph.context --budget 6000` (add `--task "<the task>"` for the claims about what
the task names). Still on Greg's go, each with its budget: a run of the swarm, a run of the token
test, switching Frankie's input, dispatching a loop, reading the documents not read yet, any paper run.

## FRANKIE / BOSS standing rules (Greg, 2026-09-16) -- MEMORY, read before touching Granite or the native context

- **The Granite 4,096-token context is RETIRED. Remove `4096` from ALL Granite-related code**: the `service_context` /
  `CONTEXT` / `max_model_len` defaults, every `(4096, 131072)` allowlist, the 1,200-output ceiling tied to it, and the
  retained-lifecycle resume gate. The only Granite context is 131,072 with output = remaining context and the
  incomplete-output alert (`IncompleteModelOutput`, `output-incomplete.json`). **DONE 2026-09-17, all 13 files** (record +
  behaviour changes in `research/kalshi/frankie_boss/CLAUDE_RECONCILIATION_20260916.md`). Retired with it, on Greg's
  'no relitigation, no artifacts lying around': the finite-timeout direct Runpod critic (RunpodConfig admits only
  open-ended), the bounded cloud smoke launch controller, and the pinned 4096 smoke admission receipt (deleted).
  Final sweep 2026-09-17: no Granite module or Granite/Sunday test carries the literal any more (byte bounds re-sized,
  refusal tests use other wrong values). The smoke workflow is deleted. Only the NATIVE row context still holds it.
- **The first run's reducer stack and prefixes are the GOLD STANDARD for ingestion (Greg, 2026-09-17)**: 57,027 records
  = 114,054 INPUT/APPLIED entries -> 7,129 gzip blocks of 16 entries (20.9x), verified in 715 s wall on GitHub run
  34962256086 (parent + 3 affinity-bound workers); 19 prefixes (`sunday_20260915_package/FB/actual-prefixes/`), each
  seed = the top T_CTX rows by receive time and cursor, `derivable: true`. Verified 2026-09-17: the prefix builder,
  snapshot, conformance reader, journal reader, stack execution and both Sunday operations scripts on the integrated
  tree are byte-identical to the first run's runtime pin `9a8f3f46`. Never rebuild these; change dates only.
- **The native row context `T_CTX = 4096` is a provisional value** (its own comment says so). Greg has retired the
  4,096-row cycle in prose at least three times; it was never changed in code, so every token projection re-derives it.
  Do NOT quote projections at 4,096 rows. The replacement row count is Greg's modelling call and is still pending.
- **Token figures**: the proven packet is 92,427 input tokens at 3,262 rows (stacked_v1), leaving 38,645 output tokens.
  Shrinking/optimizing the packet is one of the most important jobs. **114,054 is the journal ENTRY count (2 x 57,027
  records, INPUT + APPLIED), not a token count** -- do not let it surface as "114k tokens".
- **Native step thread count is a declared numeric identity**: 8, fixed for the whole run, recorded in the numeric policy.
- Launch is HOLD. No Frankie, Granite, Pod, EC2 or result-bearing action without Greg's explicit go.



**One-line state:** the futures→Kalshi LAG is the live edge — **NYMEX is the CANARY, Kalshi the delayed
follower.** **git = CODE, S3 = ALL DATA. NEVER pool/average as the final word — each event individually; an
extreme rate is a LEAD, individual numbers pinpoint the WHEN (Greg S92).** **S92 = the NG intraday FORECASTER
program + DIRECTION cracked.** **S93 = the coach agent moved INTO AWS: box `i-08cee...` driveable via SSM,
Bedrock LIVE (us-east-1; opus-4-1/haiku-4-5 via boto3), Claude Code installed — one Claude-Code model-preflight
snag left before the LLM invokes; OpenAI written in as an alternative agent backend. Brain unchanged (s92.1); loop
not yet run on the box. See `SESSION_HANDOFF_2026-07-14_S93.md` + `deploy/aws/COACH_AGENT_SETUP_S93.md`.** Built the full-toolbox per-leg characterizer (`month_characterize` now carries
the exhaustion suite + dipole + turning-point fingerprint + surprise/curve) and ran per-event learn/blind/hunt
passes on 12 warm-season NG days: (1) **NG DIRECTION is callable** — `dip_imb_level` (order-flow imbalance)
sorts a leg's side 7%/93%, monotone, **OOS-validated 100% on strong flow (34/34, 3 unseen days)**; a NOWCAST,
ideal for the Kalshi lag. (2) **Magnitude staircase** ($350 crossing = 92% ride, $500 = 100%) + grind-vs-spike;
book/dipole/exhaustion = noise for SHAPE (magnitude confounds). (3) **Turning point = far-side liquidity
RECRUITMENT, not consumption** (held legs grow the far ladder; reversed tops eat it). (4) Built the **coach
"brain"** `research/kalshi/knowledge/ng_brain.json` (versioned plays) + the self-growing loop (load brain ->
forecast blind -> merge -> refine -> converge -> the agent becomes the COACH calling plays). (5) Year-box:
**every Monday was corrupt** (Tue->Tue weeks -> Monday=last-day + `_flush` 'wb' clobber) — root-caused, FIXED
(`_flush` 'ab' append) + DOW-naming + NG Mondays re-downloaded clean; box at ~Oct. (6) NYMEX-forward workflow
rerouted git->S3, NWS-hourly RT collector built (need Greg's 3 GH secrets).
The loop MACHINERY is BUILT + tested (`coach_replay.py` executable playbook, `forecast_harness.py` helpers,
`FORECASTER_RUNBOOK_S93.md` the operating manual). **NEXT (S93) = RUN THE LOOP (brain -> forecast new group blind
-> overlay -> merge -> refine, walk the year); prove the plays (coach replay; gross, no trade cost); the NYMEX-OPTIONS survey
(Greg: the real trading vehicle for our NG-move edge, very soon); characterize NG Mondays; verify box year +
reconcile + final Monday sweep; add GH secrets; rotate keys.**
Detail: `SESSION_HANDOFF_2026-07-14_S92.md`, `KICKOFF_2026-07-15_S93.md`, `research/kalshi/FORECASTER_RUNBOOK_S93.md`.

**READ THIS FIRST, in order — do NOT read this whole file for detail, it points you at the detail:**
1. The latest `SESSION_HANDOFF_*.md` (highest S-number) — the actual current state.
2. The latest `KICKOFF_*.md` — the priorities for this session.
3. `KALSHI_TRADING.md` — the file index: every Kalshi file, what it does, current vs old.
4. Then `git log --oneline -1` — confirm you are NOT on the stale tip (see Branch discipline).

---

## What this project is

DavisAI Markets. The live product is **Kalshi prediction-market trading** (weather / macro / energy /
electricity event contracts). Crypto (the OD "info-dipole" / order-flow toolkit) was the proving ground
and is now history — the session-by-session record + the earlier OD/physics research lives in
`CLAUDE_ARCHIVE_OD.md` on branch `archive/crypto` (see Archive pointer). The operator toolkit that came out of it
is LIVE and documented below (see "OD toolkit") — it is the engine the Kalshi lag / signal work runs on,
and we regularly reach back into it for pieces.

Team: **Greg Davis** (founder, sets direction, owns the weather forecaster spec) + Claude (engineer).

---

## The trading rules (load-bearing — Greg, S80-S82)

- **TRADE DAY ONLY, NEVER A CLOCK DAY (Greg, 2026-11-16).** A TRADE DAY runs from 18:00 ET the evening before to
  17:00 ET on the named date, so trade day Wednesday is 18:00 ET Tuesday to 17:00 ET Wednesday. The hour from
  17:00 to 18:00 ET (the daily halt) is its own marked stretch and belongs to neither trade day: no trades happen
  in it, but its messages are kept and the order book processes them. The order book is the WEEK, not the day: it
  is seated at the exchange's Sunday start-up and carried straight through to Friday, and the only restart is the
  exchange's own on Sunday. Everything we build, label and analyze is cut on the trade day. Never write a bare "day" or a
  bare date: say "trade day" or "UTC clock day". The UTC clock day (00:00-24:00 UTC) exists only because the
  vendor cuts raw tape files that way; midnight UTC is 20:00 ET (EDT), two hours INTO the trade day. Download
  whichever UTC clock-day files are needed to cover a trade day completely, then shelve (keep, do not use) the
  hours that belong to a different trade day. Carry the order book straight through 00:00 UTC: applying the
  snapshot that opens each raw file restarts every resting order's age at 20:00 ET (found and fixed 2026-11-16;
  carried by `root/book.py`, which never applies a vendor snapshot after the week's start; record in `markets-data`
  `tasks/family-research-20261022/research-union-current/resting-order-age-20261116/`). Any
  exception needs a specific reason, written down next to the thing that differs.

- **ONLY THE FOUR TRADE DAYS ENTER A CALCULATION (Greg, 2026-11-16, said several times).** Scope: the ROOT rebuild,
  trade days Oct 2, 3, 17 and 18, 2023. Only ticks inside those four trade days (18:00 ET to 17:00 ET) are used in
  any calculation that feeds research, analysis or trade strategies. Data from outside them (the Sunday start-ups,
  trade day Mon Oct 16, the 17:00 to 18:00 ET stretches, the evening hours after a built trade day) may be used for
  ONE thing: seating the order book so the book on the four trade days is complete. The stretches and the Sunday
  start-up before Oct 2 keep their marked rows; nothing is calculated on them. **Any other use of data from outside
  the four trade days is put to Greg FIRST, before it is built.** Nothing is commingled; anything ever made from the
  warm-up data goes in its own output, apart. Enforced in code: a calculation receives ticks only through the two
  gates of `root/tape.py`, which use the same `calculation_eligible` and pass exactly the same ticks:
  `for_calculations()` hands it the raw tape record, `rows_for_calculations()` hands it the stored row (what a tick
  did to the book is on the row). Calculation modules live in `root/calcs/` and may not read the tape or open a
  stored file themselves (`tests/root/test_tape.py`); the runner proves on every run that the rows gate passed the
  tape gate's positions. The 13 outside data points are the published figures Greg approved in
  `SPEC-outside.md`; no new outside input is added without asking him. Greg, same day: a trade may continue into the
  days beyond the four; nothing is built for that now ("we'll cross that bridge if we come to it"), and when it comes
  up it is put to him first.

- **EVERY CALCULATION IS MADE AT THE TICK, TIMED TO THE NANOSECOND (Greg, 2026-11-18: "Definitely run it on nano
  ticks"; "We've gone over numerous times").** Rows are ticks; nothing is put on a time grid of any size before it
  is calculated on. A span of time a calculation is allowed (the 20 seconds of the exhaustion calculation) is read
  at each tick's own nanosecond. This holds for anything brought over from older work, crypto included: where an
  old step would collapse ticks, say so to Greg and do it at the tick. Code and data made on a time grid are
  deleted, and so is every mention of such a grid as a time ("We don't keep wrong data"). No made-up numbers are
  used in a session, not even to check code: a new calculation is checked on real tape. Before a run, say how
  many trades it will make a line for.

- **BAD OR INCOMPLETE DATA THAT WILL NOT BE USED IS NOT SAVED (Greg, 2026-11-16).** Data that is wrong, or
  incomplete, and will not be used is not kept: not in git, not on a branch, not beside the good data "just in
  case". An output that fails its check is not pushed. When a rebuild replaces something, the old one goes in the
  same change. A session's scratch work stays out of git. This is about which outputs are kept; it does not change
  "we don't drop any data", which is about ticks and rows inside a build. Deleting something already saved still
  goes to Greg first, with what it is and why it exists.

- **TRADE COST IS NOT A MARKET CONDITION (Greg, 2026-11-08).** No fee, slippage, maker or taker offset, fill
  model or any other execution assumption enters ANY research calculation, forecast or output. Research numbers
  are GROSS.

- **NO BITCOIN-ERA RULES. KALSHI RULES START FRESH, FOR KALSHI ONLY (Greg, 2026-11-16).** Every trade rule that
  came over from the crypto work is removed, together with the code that factored it in: fee floors, net-of-cost
  gates, maker and taker fill assumptions, slippage, bps cost thresholds and crypto-venue strategy rules. Do not
  reintroduce any of them, and do not copy one out of old code, an old handoff or the archive. The dead and
  old Kalshi rules went the same way (2026-11-16): net-of-fee at maker and taker, the size-vs-fee wall, the
  spread toll and pooled hit-rate evaluation. Whatever execution or cost rules Kalshi needs will be worked
  out new, from Kalshi itself, and will apply to Kalshi only. None is written yet, so none is assumed. The only things kept from the crypto era are measurement tools: the dipole
  read (imbalance, divergence, exhaustion), the pre-entry look-ahead window and the leakage gate.
  **ONE EXCEPTION, on Greg's explicit word (2026-11-18): the `crypto_ng/` package, named "crypto and ng".** It holds
  the rules and numbers of the crypto exhaustion calculation of 2026-07-07 (the original files stay on Markets
  `75b15fa`), written at the nanosecond, to make the natural gas exhaustion calculation exactly the way the crypto
  one was made ("Bring back the program and just designate it crypto and ng so we know what it is at a later
  date"). Its outputs are for OBSERVATION AND VERIFICATION ONLY and go into the Excel sheet under that name. Its
  fill rule, wait and fee settings apply inside that package and nowhere else; nothing in it may be imported by a
  calculation, a strategy or the Kalshi work, and no winner or loser label is made from it. Do not delete it as a
  violation and do not copy from it.
  AMENDED 2026-11-23 (the next rule but one): the two LINES it makes on the natural gas tape, the dipole and the
  exhaustion, are strategy inputs. "Observation and verification only" still holds for the program's own trades,
  its price and result figures and its fee marks.
  AMENDED AGAIN 2026-11-23 (Greg: "Yes to all four", the second of four points put to him on the paper runner):
  the paper runner (`tasty/paper/` in `DavisAI1974/paper-trading-platform`) may CALL the two line functions `crypto_ng.tick.reads` and
  `crypto_ng.tick.line` exactly as they are, so the live lines are the same formula and not a reinvention. Nothing
  else of the package is imported, and nothing of it is copied. Record: markets-data
  `paper-trading-20261123/RUNNER_PLAN_20261123.md`, point G2.

- **DIPOLE AND EXHAUSTION MEAN THE CRYPTO FORMULAS. DO NOT REINVENT THEM (Greg, 2026-11-23: "We should not be
  reinventing the wheel! The instructions should have been explicit to follow the crypto formulas. That's why we
  brought that part back").** Scope: the ROOT rebuild's renders and outputs. Both are ONE figure, bought minus sold
  over bought plus sold, over the trades received in a span of time, read at the nanosecond:
  the EXHAUSTION line is that figure over the last 20 seconds (crypto: `research/shape_s71/regroup2.py`, Markets
  `75b15fa`; ours: `crypto_ng/tick.py`, stored as `crypto-ng-tick/crypto-ng-tick-line-20s-<trade day>.parquet`);
  the DIPOLE line is that figure over the last 60 seconds (crypto: `_dipole_price_overlay.py` on the same commit,
  `W = 60`; ours: the same line the turn finder reads, stored as `crypto-ng-tick-lean-60s-<trade day>.parquet`).
  The 20 and the 60 seconds are READ FROM THOSE SCRIPTS by Claude, not numbers Greg gave: his word is "exactly like
  they were in crypto", and which crypto picture is "the dipole" is his to confirm.
  "Ticked by nano" means the TIME each read is made at, never a new formula. Any other line called dipole or
  exhaustion is named as what it is, is never drawn in their place, and is put to Greg before it is built.
  Claude's own versions of the twelfth session (the run of trades under way against the run before it; "the
  dipole at the tick", "the exhaustion at the tick") were never approved as a calculation: their programs
  (`root/tick_renders.py`, `root/continuing.py`, `root/four_graphs.py`) and everything stored from them were
  deleted on his word ("Delete anything that you ran your way") and are not to be made again. NO HARD CODED START
  OR STOP for a graph: the crypto pictures' 45 and 60 seconds are not carried; the dipole and the exhaustion start
  and stop where the data says (a hump: the time a line stays on one side of zero).
  THE EXCEL SHEETS take dipole and exhaustion from the crypto calculation only (Greg, 2026-11-23: "make sure your
  new calcs don't end up on the excel sheet. We only want the crypto calc styles as the source of output for
  exhaustion and dipole to put on excel sheets"). No figure of Claude's goes into a sheet under those names or
  beside them. What was left out of the crypto work on his word stays out: winner and loser, the
  average line, the short or long split.

- **THE NATURAL GAS DIPOLE AND EXHAUSTION ARE USED FOR STRATEGY. CRYPTO DATA IS NOT IN OUR ANALYSIS OR ON THE EXCEL
  SHEETS (Greg, 2026-11-23: "The crypto data is not to be in our analysis or on excel sheets. The ng version of
  these absolutely should be used for strategy").** Scope: the ROOT rebuild. The dipole line (60 seconds) and the
  exhaustion line (20 seconds) made on the NATURAL GAS tape with the crypto formulas (stored as
  `crypto-ng-tick-lean-60s-<trade day>.parquet` and `crypto-ng-tick-line-20s-<trade day>.parquet`, and the humps
  of the 20-second line) ARE inputs to the strategy analysis and go into the Excel sheets. They are natural gas
  data: every value in them is made from natural gas trades. CRYPTO DATA is anything measured on a crypto market
  (prices, trades, results, the saved crypto arcs, the values and averages of the crypto pictures): none of it
  enters an analysis, a strategy or a sheet. The crypto work gives the FORMULAS and nothing else. Claude's
  reading, stated to him, his to correct: the crypto and ng PROGRAM'S OWN TRADES (where it gets in and out) are
  made with settings that were tuned coin by coin on crypto results (the turn amount, the 30-second wait, the
  fees), so they, its price and result figures and its fee marks stay observation and verification only and are
  not a strategy input unless he says. The leakage gate still comes before any backtest; both lines read only
  trades already received at each nanosecond.

- **EACH TRADE INDIVIDUALLY, never average.** No pooled hit-rate, no mean signed-bps, no averaged
  coefficient — every aggregate blurs away the per-trade fingerprint that IS the predictive content.
  Characterize the DISTRIBUTION + the per-trade fingerprint; never lead with the mean.
- **Per-cell always, never pool.** Cells = moneyness × side × velocity/lag-class × release (for
  level-hits); regime × city × season × bucket × swing-dir (for weather). A signal that survives on a
  SUBSET of cells is KEPT and used on those cells — partial coverage is not failure. Report "works on
  {X}, not {Y}", never "X failed."
- **The merged signal architecture:** catalyst (release/news) = trigger + coarse size; book imbalance +
  flow + exhaustion = direction + magnitude; herd breadth = continuation, whale = scalp-only.
- **NYMEX is the CANARY; Kalshi is the delayed follower (Greg, S84).** The move happens on NYMEX/ICE
  first and reprices onto Kalshi seconds-to-a-minute later (futures lead, Kalshi never leads). Gather
  NYMEX as the leading signal, measure the lag, fire on Kalshi. Resolution: 1-min is USELESS (NYMEX
  moves fast); 1-sec is the historical floor and STILL undersamples — every 1-sec NYMEX readout is a
  LOWER BOUND, never the full tape. Data reality: Pyth has WTI (historical works) but NO natural gas
  and Brent-historical 404s; NG/Brent need Yahoo/other. See `research/kalshi/NYMEX_CANARY_NOTES_S84.md`.
- **Exclude the settle window** (the daily-settle exclusion / `SETTLE_UTC` guard) from every backtest.
- **Leakage gate before ANY backtest** (`odcore/leakage.py`) — pre-entry context must be invariant to
  future trades. This is mandatory and non-negotiable.
- **Zero synthetic trading data.** Ever.
- **Provisional until live.** A backtest edge is a hypothesis; nothing is "real" until it clears live.
- **Weather = Greg's spec, HANDS OFF.** The forecaster itself is Greg's own work; we only build the
  scoreboard/bridge (`kalshi_score.py`, the `(value,sigma)` bridge) and score PER REGIME vs the baseline.
- **`--events` on `news_coupling_research.py` is a BASENAME** joined onto `--data-dir`, not a path.
- **Keep `KALSHI_TRADING.md` current** — add new files to the top section, move superseded ones down.

---

## Operating discipline (cross-cutting)

- **Falsification-first / Result Discipline.** Every claim needs a falsifiable test. Every result is ONE
  data point — map alternatives (incl. the deflationary reading) before promoting to a claim. Catalog
  MISSES with the same care as hits; a negative that sharpens the program (like the S82 level-hit result)
  is a real deliverable.
- **No tent-widening on outliers.** When something lands outside the pattern, find the specific reason —
  don't loosen the test or wave it off as transient.
- **Incremental validation.** Canary run (short) before any long/compute-heavy run; break long runs into
  chunks with stop gates.
- **git is the source of truth.** Commit + push working code/docs regularly. Large data stays LOCAL /
  gitignored (see Branch & data). Better, stronger, faster, cheaper.
- **No emojis / special symbols** in docs, commits, or anything pushed.

---

## Agent skills (addyosmani/agent-skills, pinned 0.6.8 — Greg, S94)

Installed as a PLUGIN via `.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`),
never vendored: 25 skills, 9 phase commands (`/spec` `/plan` `/build` `/test` `/constraints`
`/review` `/code-simplify` `/ship` `/webperf`), 4 review personas, 7 reference checklists, a
SessionStart hook. `using-agent-skills` is the router. Proven on Codex; Greg: "a world of difference."

- **PRECEDENCE: when a skill is invoked, the SKILL WINS any overlap with this file.** That is
  engineering process — commit sizing and trunk habits (`git-workflow-and-versioning`), TDD,
  review gates, ADRs, spec/plan artifacts. Follow the skill; do not argue it back down to the
  house habit.
- **The research rules are NOT overlaps and are untouched by that**, because no skill speaks to
  them: the leakage gate, per-cell/never-pool, per-trade-never-mean, the settle-window exclusion,
  provisional-until-live, weather = Greg's spec. And a skill asking for a quality bar, a fixture
  or a test is NEVER licence to synthesize market data — zero synthetic trading data still governs.
- Markets is **BROWNFIELD** on the adoption guide's own test (years old, uneven coverage,
  entrenched conventions, high blast radius) so Path B applies: read-and-protect skills first
  (`context-engineering`, `code-review-and-quality`, `debugging-and-error-recovery`,
  `doubt-driven-development`), characterization tests before touching untested code, and the
  full `/spec -> /ship` lifecycle on NEW work only.
- **One router only.** Do not stack a second skill framework (Superpowers, Pocock) as an active
  router — they collide on command names and routing. Borrow individual skills a la carte.

## Branch & data discipline (READ — recurring trap)

- **MARKETS IS CODE ONLY. DATA AND RESULTS GO TO `DavisAI1974/markets-data` (Greg, repeated 2026-11-16).**
  Every data file, table, workbook, CSV/parquet/gz/tar part, render, export, receipt bundle, research result,
  handoff evidence and task output is committed to `markets-data` (index: its `MARKET_DATA_INDEX.md`), never to
  this repo. Raw tick tape goes to S3. Markets holds code, workflows, skills and the short state docs only. It
  reached ~5.9 GB because `artifacts/` and `tasks/` were pushed here (Oct 22 - Nov 7) after Greg said to stop;
  GitHub now warns the repo is near its size quota. `artifacts/` and `tasks/` are gitignored: never `git add -f`
  them. If a script writes output under this repo, point it at a markets-data checkout or S3 instead.

- **The stale-tip trap:** the harness often cuts a fresh session branch from a stale old tip (the known
  bad one is **S70 `3c70ff5`**). ALWAYS run `git log --oneline -1` first. If the tip is old, you are NOT
  on the real work.
- **Canonical trunk = `claude/kalshi-s79-kickoff-ij8t9o`.** The GitHub Actions collectors auto-push data
  commits here, so it is the live rolling branch — develop and push here (pull/rebase first, the
  collectors commit too). Do not strand work on a fresh harness-assigned branch.
- **Durable data accrues on branches, code does not:** `data/kalshi-bins` (live bins + consensus),
  `data/pyth-ticks` (Pyth futures ticks), `data/*-book` / `data/*-bins` (crypto history). Fetch + gunzip
  the relevant branch at session start; VERIFY it actually accrued before trusting it.
- **Local/gitignored data stores:** `data/kalshi_hist_trades/`, `data/pyth_ticks/`, `data/kalshi/`,
  `data/level_hits_*.json`. Too big for git; re-pullable.
- **Workflows (kept, on the trunk):** `.github/workflows/kalshi_collectors_durable.yml` (6h),
  `pyth_collector_durable.yml` (6h). If a run sits `queued` and never executes, it is an account-level
  Actions issue (billing/minutes/runner cap), not the workflow. My token cannot click "Run workflow" —
  Greg dispatches manually.

---

## Where things live (see `KALSHI_TRADING.md` for the full index)

- **`research/kalshi/`** — all Kalshi code: collectors (`kalshi_collector.py`, `kalshi_history.py`,
  `pyth_collector.py`, `consensus_poll.py`), the lag thread (`futures_kalshi_lag.py`,
  `lag_exploit_backtest.py`), the level-hit thread (`level_hit_dataset.py`), release/scoring/weather
  (`release_book_signal.py`, `kalshi_score.py`, `kalshi_weather_forecast.py`), findings `*.md`.
- **`KALSHI_BUILD_SCOPE.md`** — the build scope / thesis.
- **`odcore/`** — the OD toolkit (below).
- **`.claude/agents/`** — subagents with the Skill tool and the aws-mcp skill/doc tools: `aws-skills-guide`
  (plans from the AWS agent skills), `aws-infra-reviewer` (reviews repo AWS code), `aws-operator`
  (read-only account inspection). The Frankie role agents live on `ccr-d2f8f826-iefeah-frankie`.
- **`.claude/skills/`** — session rituals: `kalshi-session-start` (branch/data/accrual checks),
  `kalshi-backtest` (the mandatory evaluation discipline), `kalshi-roll` (Pyth front-month roll).
  GitHub house rules: `repo-conventions` (branches, commits, `[skip ci]`), `actions-operations` (workflow
  map + HOLD on dispatch), `pr-and-review` (PR body + review checklist), and `/actions-health`
  (`.claude/commands/`). These are copies of the skills in `plugins/davisai-github/` (the customized
  GitHub plugin, which only loads locally): edit both together.
- Shared: `news_ingest_rss.py`, `news_coupling_research.py`, `regime_classifier.py`.

---

## OD toolkit (live — we reach back into this; provenance in `CLAUDE_ARCHIVE_OD.md` on branch `archive/crypto`)

The operator tools built in the crypto era (S20–S37) that the Kalshi pipeline runs on, plus the pieces
we periodically pull back out. All portable numpy; validated per-cell.

- **`odcore/leakage.py`** — the MANDATORY pre-backtest leakage gate (catches look-ahead 40/40). Nothing
  gets backtested without passing it.
- **`odcore/leadlag.py`** — raw cross-covariance-over-lag lead-lag + time-slide null (the S19 "right
  tool"; what `futures_kalshi_lag.py` is built on).
- **`odcore/info_dipole.py`** — signed order-flow features + `divergence()`: the 2-factor
  DIVERGENCE (flow opposes price → ~65% reversal) + EXHAUSTION (imbalance collapsing toward 0.5 =
  leader weakening) read. The FILTER in the filter/timing split. Also provisional `cell_signal`/`DEPLOY`
  — **`DEPLOY_VALIDATED=False`, never trade the directional map** (S36 robustness: trend artifacts).
- **`odcore/incremental.py`** — `RollingFlow`, O(1)/tick bit-faithful incremental operator (1.7µs/tick)
  for hot-path use.
- **`odcore/fingerprint.py`** — per-cell fingerprint encoder (verbatim ports of the live micro-feature
  math + chunker recipe; flow features stacked per cell).
- **`odcore/dipole_predictor.py`** — the 128-dim centroid-projection algebraic dipole
  (`build_centroids`/`project`; H_a/H_b = projections on win/lose centroids — centroid-based, NOT bins).
- **`odcore/null_extract.py` / `coupling_scanner.py` / `symbolic.py` (PySR) / `validation.py` /
  `sizing.py` / `stacking.py` / `generators.py`** — coupling discriminator, tautology-killing
  circular-shift null, symbolic regression, walk-forward splits (the cost-charging promotion gate was
  removed 2026-11-16), OD-native sizing, stacking.
- **Crypto data history** (for reaching back): `data/*-bins`, `data/*-book`, `data/*-kraken-book`,
  `data/perp-history` branches — 5 coins × 3 venues 1s bins + L2 books. Collector workflows were
  deleted from the trunk end-S82 (runner hog); the code is recoverable via git history if collection
  ever needs to restart.

The research findings behind these tools are the next section — the dipole research stays LIVE here,
not just in the archive.

---

## Dipole research (standing — the findings, kept live)

The information dipole (davisai.ai/dipole) is our directional/flow tool; Greg: the trend-following /
flow read may be one of our biggest edges, usable across the WHOLE platform — which is why this stays
in the live doc. Full detail: `S36_NETCOST_BACKTEST_FINDINGS.md`, `SESSION_HANDOFF_2026-06-22_S36.md` /
`_S36b` / `_S37`, and `CLAUDE_ARCHIVE_OD.md`, all on branch `archive/crypto`.

- **The core read (S36, 2 factors, stack monotonically):** markets are follow-the-leader (a trend = a
  flow) until the leader exhausts → new leader, usually opposite; the edge is detecting the changeover.
  (1) **DIVERGENCE** — `aligned_flow = imb_level × sign(price_drift)`; strong divergence (≤ −0.20) →
  ~65% reversal, temporally stable, consistent 6/7 cells. (2) **EXHAUSTION** — the dipole COLLAPSING
  toward 0.5 (leader weakening; the MOVE toward balance, NOT the discrete crossing, which is a coin
  flip). Combined: oppose+exhaust 64% reversal > oppose+strengthen 58% > with-trend+exhaust 52% >
  with-trend+strengthen 49% (healthiest trend).
- **Discipline (load-bearing):** the signed flow is NOT a direct direction predictor — apparent
  directional lifts were trend/base-rate artifacts (Simpson's on a trending window) and died under
  window/forward sweep + temporal OOS + detrended targets. `DEPLOY_VALIDATED=False`; never trade the
  directional `cell_signal` map. The DIVERGENCE/FLIP read is the robust edge; static `imb_level` is
  the detector (differential flows are not).
- **The architecture split:** DIPOLE = the FILTER (which turns are real) + fine-resolution
  PRICE-REVERSAL = the TIMING (1-sec enters ~5–6bps off the true turn vs ~9–11 at 1-min).
- **The centroid-dipole lineage (S33–S35):** the real markets dipole is CENTROID-based, not bins —
  H_a/H_b = projections of a trade's 128-dim OD `operator_coefficients` on win/lose centroids; per-cell
  exact coeffs + the distinctive-fingerprint program (`bucket-distinctiveness-is-the-goal`: predict
  winners by their per-cell fingerprint, never by class-separation statistics).
- **Standing meta-rules:** tools are COMPLEMENTARY, not competing — evaluate by STACKING, never
  head-to-head ("even a 5% net edge is huge"). Per-cell always. On Kalshi today the dipole exhaustion
  read is live inside `release_book_signal.py` (direction = book-imbalance sign, magnitude/fade =
  imbalance + dipole exhaustion) and the level-hit context features.

---

## Current state & priorities

Detail is in the latest handoff + kickoff — this is the pointer, not the record.

Recent arc (compressed; full detail in each `SESSION_HANDOFF_*.md`):
- **S93** — the coach agent moved INTO AWS (Greg: the agent must live in his AWS, on the box, not a Claude
  Routine). Cleared the whole access chain (the `Claude` IAM user now has S3+EC2+SSM-full+Bedrock-full + inline
  PassRole; no permissions boundary) and stood the box up as the agent host: instance profile `Ssm` attached ->
  **box `i-08cee...` Online in SSM** (drive via `scratchpad/ssm_run.py`); **Bedrock LIVE in `us-east-1`** (model
  access is per-region — us-east-2 404s; boto3 converse OK for opus-4-1/4-5/4-6 + haiku-4-5); **Node 20 + Claude
  Code 2.1.197 installed on the box**, `/etc/markets/coach.env` wired (Bedrock=us-east-1, S3=us-east-2). ONE SNAG:
  Claude Code 2.1.197's model preflight rejects the Bedrock Opus IDs (boto3 invokes them fine) -> LLM not yet
  invoking. Per Greg, **OpenAI is now an accepted alternative agent backend** (loop is provider-agnostic). Brain
  did NOT advance (s92.1); no group scored/merged. Detail: `SESSION_HANDOFF_2026-07-14_S93.md`,
  `deploy/aws/COACH_AGENT_SETUP_S93.md`, `KICKOFF_2026-07-15_S94.md`.
- **S92** — NG intraday FORECASTER + DIRECTION cracked + the coach BRAIN. Built the full-toolbox per-leg
  characterizer (`month_characterize`: exhaustion suite + dipole + turning-point fingerprint + surprise/curve)
  and ran per-event (NO-pooling) learn/blind/hunt passes on 12 warm-season NG days. (1) **NG DIRECTION callable**
  — `dip_imb_level` order-flow imbalance sorts a leg's side 7%/93%, OOS-validated 100% strong-flow (34/34, 3
  unseen days); a nowcast for the Kalshi lag. (2) **Magnitude staircase** ($350->0.92, $500->1.00) + grind-vs-
  spike; book/dipole/exhaustion NOISE for SHAPE (magnitude confounds). (3) **Turning point = far-side liquidity
  RECRUITMENT, not consumption.** (4) **Coach BRAIN** `knowledge/ng_brain.json` + the self-growing loop (load ->
  forecast blind -> merge -> refine -> converge -> the agent becomes the COACH calling plays). (5) Year-box
  every-Monday-corrupt bug (Tue->Tue weeks + `_flush` 'wb' clobber) root-caused + FIXED ('ab') + DOW-naming + NG
  Mondays re-downloaded clean; box at ~Oct. (6) NYMEX-forward workflow git->S3 + NWS-hourly RT collector (need
  Greg's 3 GH secrets). Detail: `SESSION_HANDOFF_2026-07-14_S92.md`, `KICKOFF_2026-07-15_S93.md`.
- **S91** — YEAR-PULL REBUILT on a durable observable box + GOLD/SILVER depth-add VALIDATED. (1) The S90 box had
  failed (S3 year = corrupt July stubs, blind box); rebuilt: `pull_year --weekly` (per-week Databento jobs +
  marker-resume) + stub-aware resume-skip, on box `i-08cee7171c0a76a04` (200GB) streaming its log to S3 (v1 died
  on an awscli dependency; v2 boto3-only booted clean). (2) Gold/silver LAG confirmed on free Pyth XAU/XAG
  (gold 37/60, silver 26/54 sig, futures-lead, same as WTI/NG; cross-strike is NG-only) — collectors + XAU/XAG
  Pyth feeds wired, HH NGDQ6 feed confirmed correct. (3) Agents: NYMEX-products + Kalshi-ranking (KXGOLDD #1).
  Execution deferred to last (paper-trade Kalshi demo first). Open S92: verify the year landed clean, rotate
  keys, migrate data git→S3, validate the lag at size (gross). Detail: `SESSION_HANDOFF_2026-07-14_S91.md`.
- **S90** — EVERYTHING TO AWS + a critical data-integrity fix. (1) Verifying the first S3 month exposed an
  80% loss: `batch_pull`'s flush gzipped each day BEFORE it was complete, so a later file's boundary rows
  overwrote it (only Fridays/last-day survived) — FIXED (hold latest-2 days unflushed; validated 32.8M/32.8M
  CL-July rows recovered). (2) `pull_year --reuse-done-jobs` + `redecode_job` rebuild corrupt months from
  already-paid Databento jobs FREE. (3) Durable **EC2 box** `i-0017dc36072eaa6c8` (needed EC2FullAccess on
  the `Claude` IAM user; no managed Lightsail-full policy exists) self-configures from S3 + runs the
  recovery+resume. (4) ALL bento data moved git→S3 (`nymex_tape/`+`nymex_mbp10/`); git holds NO bento now.
  (5) S3 tape reader `event_move_baseline.load_cont_day(source="s3")` + raw normalizer (JOB 2 core, wired
  into `month_characterize --source s3`). (6) RAW HOURLY weather ingestion `nws_temp_feed --ingest-hourly`
  → `weather/nws_hourly/` (every field/ob, no roll-up; the daily degree-day store was the same reduction
  mistake). (7) Weather interface spec + trade-distribution math + AWS deploy kit + the daily-cadence trigger
  note. NG dipole quick canary = static-divergence NULL (test exhaustion next). Secrets to ROTATE (Q5).
  Detail: `SESSION_HANDOFF_2026-07-13_S90.md`.
- **S89** — BUILT the durable RAW ingestion + moved the tick corpus to AWS S3. Zero-filter MBP-10 writer
  (removed the last silent row-drop; verified 76 fields/row, all 10 levels). `pull_year_mbp10.py`:
  month-at-a-time batch, gzip-each-day-as-it-lands (`batch_pull(flush_dir=)` bounds local to 1 day),
  `--worktree`/`--scratch`, and **`--dest s3://…` or git**. One-day proof (CL 2026-05-14 = 975k msgs,
  1.3 GB→61 MB gz). Now pulling the full-raw year (CL+NG, 2025-07..2026-07) to bucket
  `bento-568968024170-us-east-2-an` (us-east-2, prefix `nymex/`); split container Jan-Jun 2026 / Greg's
  box Jul-Dec 2025, resumable via bucket list. AWS+Databento keys are session-pasted SECRETS; corpus is
  on S3 now, not git. NEXT = finish/verify + rework scoring to read the raw S3 tape. Detail:
  `SESSION_HANDOFF_2026-07-13_S89.md`, `research/kalshi/AWS_INGEST_SETUP_S89.md`.
- **S83** — meta session: CLAUDE.md audit/split (this lean doc + `CLAUDE_ARCHIVE_OD.md`, dipole
  research + OD toolkit kept live); the three ritual skills (`kalshi-session-start`, `kalshi-backtest`,
  `kalshi-roll`). No research ran; `data/pyth-ticks` still absent at close.
- **S84** — Data reckoning + weather. NYMEX-canary principle set. Found Pyth has NO natgas (bogus `NGDQ6`
  id) → Databento = primary historical (true-tick CL+NG, `databento_backfill.py`). KXNATGASD = daily
  NG-futures market; KXPOWERKWH = monthly macro stat. Weather per-day fingerprint. Killed respawning
  crypto collectors. Detail: `SESSION_HANDOFF_2026-07-15_S84.md`.
- **S86** — Produced the **event-state MODEL** (`EVENT_STATE_DESIGN_S86.md`, Greg's driver model — see
  one-line state) + three leakage-gated builds on the 24 MBP-10 windows (~$0.42), all provisional/n=12/
  Apr-Jul/logged-without-mechanism: (1) MBP-10 depth run-length (push-book one-sidedness vs run length NG
  −0.17 / CL +0.52); (2) EIA seasonal-proxy surprise split (`eia_surprise.py`, 12/12; opposite-signed
  surprise/move NG vs CL); (3) pre-release VOLUME primed/coiled detector (`pre_release_volume`; NG quieter
  pre-release → bigger move, consistent across cells — first build off the model, no external feeds).
  Eyeball-validated (06-17 CL big move = the 2026 Hormuz crisis). NEXT = P3 lag join (needs a Kalshi
  historical pull; gates the $130 full-year MBP-10). Detail: `SESSION_HANDOFF_2026-07-13_S86.md`,
  `DEPTH_RUNLENGTH_FINDINGS_S86.md`, `EVENT_SURPRISE_FINDINGS_S86.md`, `PREVOL_FINDINGS_S86.md`.
- **S85** — Databento LIVE (key set, `pip install databento` 0.81). `event_move_baseline.py` BUILT + run
  on 12 NG + 12 CL real release windows (leakage PASS, `definition`-schema $10/tick): per-contract
  HOLD-TIME map (NG 60s=66% of move front-loaded; CL slower, 60s=27%, longer hold gets the rest — both
  kept). Futures move = the ceiling; lag join next. `databento_backfill.py`
  hardened (defs mode + point-in-time tick store, volume roll `.v.0`, retry/backoff). Schema decision =
  MBP-10 (depth, ~$130/yr both, ~$5 over credit; MBO off). Tape persisted on `data/nymex-ticks`
  (session-start restores it). Detail: `SESSION_HANDOFF_2026-07-12_S85.md`, `EVENT_MOVE_FINDINGS_S85.md`.
- **S88** — RAW-INGESTION correction (Greg, load-bearing): historical data is RAW, keep ALL the info; gates
  ONLY on the trade side. Rewrote the MBP-10 writer to keep everything (every message + all 10 levels, zero
  reduction). Built the data feeds `nws_temp_feed.py` (NWS gas-weighted HDD/CDD+precip) + `forward_curve.py`
  (backwardation/contango). Forecaster scoring scaffolding built (`month_characterize`, `bucket_continuation`,
  coin-style `forecaster_month_pass.workflow.js` — ran end-to-end, fixed a date-format leakage bug) but it
  pre-processes on the ingest side → must be reworked to read the RAW tape. NEXT = the durable raw-ingestion
  workflow. Detail: `SESSION_HANDOFF_2026-07-13_S88.md`, `KICKOFF_2026-07-14_S89.md`.
- **S87** — BUILT P3: `lag_join.py` lag-join engine (release + `--intraday`), NYMEX-driven entry/hold/exit,
  trend-hold dollar trailing stop (its fee, slippage and maker/taker terms were removed 2026-11-16; it now
  reports gross moves only). PROVISIONAL, tiny-n. Designed the intraday
  PATH FORECASTER as a stacked hold-length signal (`FORECAST_AGENT_DESIGN_S87.md` Greg's spec +
  `PATH_FORECAST_RESEARCH_S87.md` cited methods). Databento pull infra (`batch_pull`, `pull_year_mbp10.py`);
  1-yr continuous MBP-10 pull = pay-once to `data/nymex-ticks:nymex_cont/` = the forecaster's analog library
  (2-yr to S3 at go-live). Detail: `SESSION_HANDOFF_2026-07-13_S87.md`.

---

## Archive pointer

The full OD / info-dipole crypto research (S20–S37) and the earlier Information-Layer / four-forces /
gravity-time physics research (S3–S25, the INFO-0xx ledger, capability demos) live VERBATIM in
`CLAUDE_ARCHIVE_OD.md`, which is on branch **`archive/crypto`**. Consult it only if a question reaches back
into the OD toolkit's provenance.

**Crypto files live on branch `archive/crypto` (Greg, 2026-11-16).** That branch is a full snapshot of the
trunk at `676322d`. The crypto-only files were then removed from the trunk and the research branch: the
exchange collectors, the crypto research scripts and their result files, `backend/`, `frontend/`,
`discord_bot/`, `fingerprint_dataset/`, `vendored_build_kit/`, the crypto-era documents and the S20 to S38
kickoffs and handoffs. Kept on the trunk because live code uses them or Greg said so: `odcore/` whole (with
`tests/` and `scripts/`), `research/shape_s71/early_signal.py`, and the news pipeline with
`regime_classifier.py`, `phase1_5_evaluator.py` and `markets_adapter.py`. New crypto work, if any, goes on
that branch, not the trunk.

---

## Keeping this file lean (session-note workflow)

This file stays SHORT and CURRENT. Per session: write full detail to a `SESSION_HANDOFF_*.md`, update the
one-line state + header date/session at the top, fold only the new headline into the "Recent arc" list
(drop the oldest if it grows past ~6 entries), keep `KALSHI_TRADING.md` current, commit + push. Do NOT
paste session detail into this file — that is what the handoffs are for. The failure mode this structure
prevents: a bloated master a cheaper model silently half-ignores.
