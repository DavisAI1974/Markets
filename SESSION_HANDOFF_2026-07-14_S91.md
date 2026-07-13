# SESSION HANDOFF — S91 (work date 2026-07-13/14) — year-pull rebuilt on a durable observable box; GOLD+SILVER depth-add validated (lag)

Branch: came up on stale S70 tip, rebased onto trunk `claude/kalshi-s79-kickoff-ij8t9o` (push there). All work pushed.

## HEADLINE
1. **JOB 1 (the year data) — root-caused + rebuilt.** The S90 EC2 box had FAILED: only July 2025 on S3, and it was corrupt 1-row stubs (the exact S90 flush-bug signature — Friday/last-day survivors only). The box died blind (30GB disk starvation + zero observability). Fixed the whole approach and it is now running on a **durable, observable box**.
2. **GOLD + SILVER depth-add VALIDATED (free).** Greg's call to expand the futures->Kalshi LAG onto more Kalshi markets: the look-ahead lag is CONFIRMED on both KXGOLDD + KXSILVERD using free Pyth XAU/XAG — same structure as WTI/NG. See `research/kalshi/GOLD_SILVER_LAG_FINDINGS_S91.md`.

## THE YEAR PULL — where it stands (VERIFY FIRST in S92)
- **Durable box `i-08cee7171c0a76a04`** (t3.xlarge, **200GB** gp3, us-east-2) is running the full-year weekly pull to `s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/`. Launched ~2026-07-13 20:07Z; confirmed ALIVE (boot.log "deps OK | code extracted", heartbeat disk=191G, pull.log streaming).
- **OBSERVABILITY (the S90 fix):** the box streams `pull.log` + `heartbeat` (+ `mkt-boot.log`) to **`s3://.../deploy/box-logs/`** every 30s. WATCH IT: `aws s3 cp s3://.../deploy/box-logs/pull.log -`. Heartbeat carries disk-free. The box **auto-stops** (InstanceInitiatedShutdownBehavior=stop) when the pull completes + writes `deploy/box-logs/DONE`.
- **Two box attempts this session:** v1 (`i-0e56896a51243edb2`) FAILED silently — its boot script used the `aws` CLI for the code-download + log-streaming and awscli didn't install, so 0 data + 0 logs, then shutdown. v2 is **boto3-only** (no awscli) with early boot markers -> booted clean. v1 is stopped (kill it in S92).
- **`pull_year_mbp10.py --weekly` (NEW, committed 2a484c5):** week-at-a-time — 53 fresh per-week Databento batch jobs, per-week S3 publish, **marker-based resume** (`nymex_cont/_done/{root}_{ws}.done` written ONLY on a clean upload). Smaller jobs clear Databento's queue faster; finer resume. **The pace-setter is Databento's batch queue**, not our compute (jobs sit `queued` then process).
- **Stub-skip fix (committed 2a484c5):** `_s3_month_present` now treats any month with a sub-5KB stub or <15 days as ABSENT -> re-pulled, never silently skipped (the S90 bug that hid corrupt July).
- **S92 VERIFY:** watch `deploy/box-logs/` until DONE; confirm ~53 weeks x CL+NG markers under `nymex_cont/_done/` and clean daily gz (tens of MB, no stubs) across all 12 months. If the box stopped early, relaunch (boto3 boot script in scratchpad `box_userdata2.sh`) or run in-container: `pull_year_mbp10.py --start 2025-07 --end 2026-07 --weekly --dest s3://.../nymex --scratch /tmp/x` (marker-resume skips done weeks). Cost: fresh weekly year ~= full ~$130 (clean uniform corpus, Greg's preference over reuse).
- **DATABENTO SAMPLE-CODE finding (Greg pushed):** we ALREADY use the canonical `batch.submit_job(split_duration="day")` + `batch.download`. The flush bug was our downstream UTC-re-bin, now fixed. **S92 optimization: store the native `.dbn.zst` day files as-is + decode at READ time** (the S3 reader already decodes on read) -> deletes the decode/flush/re-bin step from the pull and makes the flush-bug class impossible.

## GOLD + SILVER depth-add (VALIDATED — the session's research win)
- **Collectors wired + pushed:** KXGOLDD/KXSILVERD added to `kalshi_collector.py` (books, ed778ac); Pyth XAU/XAG spot feeds added to `pyth_collector.py` (6dd118d). Both live; next 6h cron accrues them.
- **HH Pyth was never bogus:** `Commodities.NGDQ6/USD` exists in Pyth with the EXACT id already in our collector — the S84 "bogus NGDQ6" note was WRONG. HH daily-close feed is correctly configured (settle-matching + oracle-divergence ready).
- **Settlement verified vs Kalshi rules_primary:** KXGOLDD/KXSILVERD settle on the 1-min candle @5PM EDT of **XAU/XAG spot** (USD/t.oz) = Pyth Metal.XAU|XAG/USD. Gold/silver futures = **COMEX GC/SI** (same GLBX/Databento machinery; ~$200 tick tape DEFERRED).
- **Cross-strike (Kalshi-internal):** STRONG on NG (down-triggered ITM/ATM pay +1.6..+3.3c, 51-64% win, 5 days, leakage PASS), WEAK on metals (only deepITM|dn marginally +, low win). Cross-strike is an NG thing.
- **Look-ahead LAG (the real edge) — CONFIRMED both:** `futures_kalshi_lag.py` with FREE Pyth XAU/XAG 1-min bars. Gold 37/60 sig z>=3 futures-lead ({0:20,+1:15}); Silver 26/54 sig z>=3 ({0:18,+1:5}); z up to 15-20. Same as WTI/NG. **1-min = LOWER BOUND** (sub-min lead hides in the lag-0 bucket). Remaining: net-of-fee at SIZE at sub-minute (the size-vs-fee wall) -> free 1-sec Pyth first, paid GC/SI to nail it.

## AGENTS (both delivered, committed)
- **NYMEX-products survey** (`NYMEX_PRODUCTS_SURVEY_S91.md`): NG/CL best fit (own tape); HO finest tick; **CME energy has NO maker rebate** (symmetric fees -> "maker" = spread capture, fill-prob is the binding risk).
- **Kalshi product-ranking** (`KALSHI_PRODUCT_RANKING_S91.md`): #1 = **KXGOLDD** (deeper book than KXWTI, identical settle mechanic, reuses both pipelines) -> this session validated it. Also silver, Brent (CME BZ closes the ICE gap), crypto (deepest book, OD-native but efficient), KXLOW weather.

## EXECUTION / GOING LIVE (Greg S91)
- **No prior execution plan existed.** Kalshi trading API IS the plan; **deferred to LAST** ("sounds easy").
- **Paper-trade first** on Kalshi's **demo** environment (demo.kalshi.co, play money) for a few days before real orders.
- **Can trade FROM KALSHI here** (signed HTTPS to the trading API, proxy allows it) — needs: funded Kalshi account + **API key + RSA private key** + a small execution module (place/cancel/track, bounded risk caps) + a cleared edge. **Cannot trade NYMEX** (data-only env; needs an FCM/broker).

## COLLECTION STATE
- **Running (git branches — TO MIGRATE):** Kalshi books `data/kalshi-bins` + Pyth ticks `data/pyth-ticks`, both 6h crons, fresh.
- **Weather:** `weather/nws_hourly/` COMPLETE on S3 (450 files). NO durable FORWARD collector for NWS hourly (gap).
- **NYMEX-forward workflow FAILS every run** (7/7 today) — not collecting; that's why the manual box pull is needed. Gap to fix.

## OPEN for S92 (priority)
1. **VERIFY the box finished the clean year** (watch deploy/box-logs/ -> DONE; check 53 weeks markers + clean gz all 12 months). Kill the stopped v1 box `i-0e56896a51243edb2`.
2. **ROTATE the AWS + Databento keys** (they're in the box boot config; standing item). AWS key `AKIAYI6JDCBVLKYQGLMH`, DB key `db-3ba8...` — Greg re-pastes fresh, rotate early.
3. **Migrate live data git->S3** (task #9): move kalshi-bins/pyth-ticks to S3 + add `--dest s3://` to the collectors + reroute the workflows (needs AWS secret in GH Actions, OR run collectors on the durable box/Routine). Then stop git data-branch pushes.
4. **Net-of-fee/size validation at SUB-MINUTE.** NG/WTI lag is ALREADY TESTED (S81 existence + S81/S87 provisional
   net-of-toll, CL/NG positive gated) — do NOT re-test it. Open: (a) gold/silver's first net-of-fee-AT-SIZE read
   (lag existence done S91); (b) sub-minute DEEPENING across markets (sharpen the size-vs-fee margin at 1-sec/tick
   on the clean year tape + free 1-sec Pyth) — that is sharpening, not re-testing the lag.
5. **Fix the NYMEX-forward workflow** (needs the DATABENTO GH secret or a Routine). **Wire NWS-hourly forward** collector.
6. **SSM:** Greg added the AmazonSSMManagedInstanceCore role, BUT my IAM user lacks ssm:* actions (can't DescribeInstanceInformation / SendCommand) -> I can't drive SSM. S3-log-streaming is the observability path unless my user gets ssm perms. SSM's real payoff = the durable DAILY box (no on-disk keys).
7. Databento native-zst optimization (store zst, decode at read); Kalshi execution module + demo paper-trade (deferred to last).

## SECRETS (session-pasted, never git): AWS_ACCESS_KEY_ID/SECRET (IAM user Claude, EC2FullAccess, NO iam/ssm), DATABENTO_API_KEY, AWS_DEFAULT_REGION=us-east-2. ROTATE early (in box boot config).

## RULES (unchanged): data RAW / aggregate only on trade side; leakage gate; per-cell never pooled; distributions not means; net-of-fee maker AND taker; exclude settle window; zero synthetic; provisional-until-live; weather forecaster = Greg's spec HANDS OFF; git = CODE, S3 = ALL DATA.
