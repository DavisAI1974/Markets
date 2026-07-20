# AWS PLATFORM S98 - data consolidation + the migration plan + execution-speed analysis

Greg, 2026-07-20: "we don't want data spread everywhere. i want to start the migration to aws where
the platform will live. or a hybrid of that and git. i want you to look at that too for trade
execution speed." This document is that plan. Companion to `research/kalshi/DATA_GATE_S98.md`
(Tier 4 points here) and `deploy/aws/COACH_AGENT_SETUP_S93.md` (the existing box/Bedrock state).

DECISION SUMMARY: HYBRID, formalized - git = CODE + docs + records; S3 = ALL DATA (one bucket, one
taxonomy); local disk = disposable cache; the LIVE LOOP runs in AWS us-east-1 co-region with Kalshi.
This is the standing "git = CODE, S3 = DATA" rule made TRUE - today data also lives on git branches
and in local-only stores, which is the sprawl being ended.

---

## 1. WHERE DATA LIVES TODAY (the honest sprawl inventory, 2026-07-20)

| location | what | status |
|---|---|---|
| S3 `bento-568968024170-us-east-2-an` (us-east-2) | `nymex/` (tape n0/n1/v0, contract_structure, mbp10 year), `weather/mos_asof/`, `weather/nws_hourly/`, `cot/`, `storage_regional/` | CANONICAL for what it holds; verified S97 |
| LOCAL `E:\Markets\data\` | everything above cached + LOCAL-ONLY: `eia_surprise.json`, `nymex_curve/`, `nws_temp/` (gw degree days), soon `kalshi_ng/` (feed L), `storage_consensus/` (feed D) | local-only pieces are UNPROTECTED - a disk loss loses them |
| git trunk `claude/kalshi-s79-kickoff-ij8t9o` | `data/kalshi-bins` (collector pushes, 6h), `data/pyth-ticks` | the git-as-data anti-pattern; accrual state unverified (feed L is auditing the kalshi side) |
| git legacy branches | crypto `data/*-bins`, `data/*-book`, `data/perp-history` | dormant archive, reachable via history |
| git working branches | committed renders, forecast records, brain, MOS index+normals | CORRECT - these are records/docs, they stay in git |

## 2. TARGET ARCHITECTURE

```
git (GitHub)                      S3 one bucket                       AWS compute
--------------                    -------------------------------    -------------------------
code                              nymex/          weather/           us-east-1 LIVE box:
docs + handoffs                   cot/            storage_regional/    - live NYMEX feed in
brain + forecast records          contract_structure/                  - deterministic executor
renders (small, committed)        kalshi/  <- feed L lands here        - Kalshi order path
                                  consensus/      calendar/            - lag telemetry
NO DATA BRANCHES (retired)        options/        manifests            us-east-2 (existing box):
                                  per-prefix manifest.json             - research / batch / pulls
local E:\Markets\data = CACHE, rebuildable from S3 in one command (platform_sync)
```

Rules:
- ONE bucket. Every prefix carries a `manifest.json` (coverage span, writer, updated_at, row/object
  counts) so "what do we have" is a query, not an archaeology session.
- Nothing is data-canonical in git. The two collector workflows are repointed to write S3 directly
  (needs AWS secrets in GitHub Actions - Greg holds secrets, same pattern as the S92 NWS collector
  note); the old data branches are frozen as archive, never deleted.
- Local is cache: `platform_sync.py pull --prefix <p>` materializes any working set; `push` is the
  only door INTO S3 from a session, so provenance stays one-way and auditable.
- MISSING IS EXPLICIT survives the move: manifests name coverage gaps per date, never percentages.

## 3. REGION CALL

- Historical/canonical S3 STAYS in us-east-2 for now. The corpus is small (the S97 push was 148MB;
  the mbp10 year is the only heavy prefix) so moving it is cheap ANY time; what kills the move today
  is churn for zero latency benefit - ANALYTICS reads are not latency-bound, and the live loop must
  not read historical S3 in its hot path anyway (see 4).
- The LIVE LOOP runs in us-east-1: Kalshi's exchange infrastructure runs on AWS US-East (VERIFY at
  build time against Kalshi's current docs before provisioning - recorded assumption, not fact);
  Bedrock access is already us-east-1 (S93); co-region gets order RTT to low single-digit ms.
- Cross-region S3 (us-east-2 data read from us-east-1 box) costs ~$0.02/GB and adds ~10-20ms per
  GET - irrelevant off the hot path, and the hot path holds its state in memory/local disk.
- If/when the platform's daily operation concentrates in us-east-1, migrate the bucket once with a
  sync + manifest verify + old-bucket freeze. One-way door, cheap at this corpus size, not urgent.

## 4. EXECUTION-SPEED ANALYSIS (the point of the whole layout)

THE EDGE'S CLOCK (established, S80/S81 - see DATA_GATE "the standing look-ahead"): the futures ->
Kalshi lag is 7-20 SECONDS on the fastest, most liquid strike, and LONGER on less-liquid strikes;
net-of-fee it cleared on the lagging x >=$0.40-move cell (+91c over fee). The design consequence is
load-bearing and liberating:

**WE NEED SUB-SECOND, NOT SUB-MILLISECOND.** No co-lo, no kernel tuning, no HFT arms race. A plain
us-east-1 instance beats the edge's clock by 1-2 orders of magnitude. Over-engineering here is spend
without return; the real risks are elsewhere (fills, self-impact, decay - below).

Hot-path budget (target, generous vs the 7-20s edge):
| leg | target | note |
|---|---|---|
| NYMEX tick -> box (Databento live GLBX) | < 100ms | vendor feed latency; measure at build |
| detect + decide (deterministic executor) | < 10ms | table lookup against the pre-set playbook |
| Kalshi order submit -> ACK (co-region) | < 50ms | REST/WS; rate-limit tier verified at build |
| END TO END | < 200ms | ~2 orders of magnitude inside the lag |

ARCHITECTURE RULE - THE LLM IS NEVER IN THE HOT PATH. The coach (agent) sets the day's PLAYBOOK
ahead of the session and revises on a cadence (the S87 lifecycle: load by 5PM D-1, recalc AM,
re-check intraday); a DETERMINISTIC executor holds the playbook and fires on triggers in
milliseconds. Agent latency (seconds) never touches an order.

LAG TELEMETRY, NOT RETEST (Greg: the look-ahead is established, ~15 confirmations, never retest):
the live executor LOGS the observed NYMEX-move -> Kalshi-reprice delay and pass-through on EVERY
fire as flight telemetry. That is free continuous measurement of the edge's decay - the lag WILL
compress as Kalshi's MM ecosystem matures, and the telemetry is how we see it happening without
ever re-litigating whether it exists.

Real execution risks (where attention actually belongs, per S81's own cells):
1. FILL REALITY AT THIN STRIKES - the less-liquid strikes lag longest but fill worst; the
   tradeoff cell (lag depth x book depth) is feed M's job to map.
2. SELF-IMPACT - our own order moves a thin Kalshi book; size discipline per strike, measured live.
3. RATE LIMITS / API tier - verify Kalshi's current limits before the executor design freezes.
4. DECAY - the telemetry above; provisional-until-live applies to the lag's SIZE forever.

## 5. MIGRATION STEPS (M-steps; parallel to the data gate, does NOT block G12)

- M1 (GREG, BLOCKS ALL PUSHES): rotate the AWS pair + Databento key (exposed S97).
  STATUS 2026-07-20: AWS pair ROTATED - new key live in `scratchpad/aws.env`, verified via STS
  (user/Claude) + S3 list. The Claude IAM user has no iam:* permissions (correct least-privilege),
  so DEACTIVATING THE OLD KEY IS GREG'S CONSOLE ACTION: IAM -> Users -> Claude -> Security
  credentials -> deactivate the non-AKIAYI6 key; delete after a settling period. DATABENTO key
  ROTATED same day (new key in aws.env, verified: 29 datasets visible, GLBX.MDP3 present) - if the
  OLD Databento key is still active in their portal, deactivate it there (Greg). STILL PENDING: the
  real EIA key. NOTE: both new secrets also transited chat (screenshot / paste - same exposure
  class as S97); for the NEXT rotation, edit scratchpad/aws.env directly and just say it is there;
  zero chat exposure.
- M2: DONE 2026-07-20 - `research/kalshi/platform_sync.py` (list / pull / push with per-prefix
  manifest.json, push is dry-run unless --execute, post-push size verify; selftest PASS).
- M3: DONE 2026-07-20 for the pre-existing local-only stores - pushed + verified with manifests:
  `eia/eia_surprise.json` (0.54 MB), `nymex/nymex_curve/NG_curve.json`, `weather/nws_temp/
  gw_degree_days.json`. Local copies are now officially CACHE. Feed L's `kalshi/` and feed D's
  `consensus/` land via the same door when their builds finish. Bucket at M3 close: cot/ 9 obj
  16.5MB, eia/ 2, nymex/ 892 obj 27.6GB (the MBP-10 year), storage_regional/ 2, weather/ 505 obj
  62MB, deploy/ 6.
- M4: repoint the two live collector workflows (kalshi, pyth) to write S3 (Greg adds the GH
  secrets); freeze the git data branches as archive with a final README commit naming the S3
  successor prefix.
- M5 (post-gate, with the two-coach spec): stand up the us-east-1 live box - Databento live feed
  in, executor skeleton, Kalshi API client, lag telemetry; paper/demo first
  (provisional-until-live).
- M6: the restore ritual becomes one command per session (`platform_sync pull`), and
  `kalshi-session-start` gets updated to use it - the end of "is the data on this machine" as a
  session question.

## 6. WHAT THIS DOES NOT CHANGE

The blind wall, the leakage gate, per-event discipline, renders-printed-before-merge, the walk
protocol - none of this moves. The platform is WHERE things run; the discipline is HOW, and it is
unchanged. The weather forecaster remains Greg's spec, hands off.
