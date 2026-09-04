# Frankie BOSS final-candidate research record

Date: 2026-09-04

Status: Architecture decision and implementation-readiness record. This is not a production promotion, model invocation, data purchase, or trading authorization.

Repository: `DavisAI1974/Markets`

Documentation branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

Current Frankie baseline inspected: `bc8c4fd728036cdc7cedf8d1b9427f58853f2e6c`

Recovered BOSS source branch inspected: `codex/frankie-boss-raw-mbo-benchmark-20260828`

Recovered BOSS source tip inspected: `38b37c4323a027b21b5ca65627daf294a1481541`

## Executive decision

The fourth/final design the prior work was pointing toward is recoverable from its component fingerprint even though the repository does not literally label a file `BOSS V4`.

The governing benchmark record names the intended full BOSS arm `B2`:

- the existing native typed BOSS trunk and causal packet boundary;
- ReFRAG-owned QSV/operator registry and governance;
- the controlled OD/dipole auxiliary-teacher experiment;
- whole-representation recurrent reasoning, called `B1` in the benchmark matrix;
- Granite 4.2 8B reasoning assistance added to B1, producing `B2`;
- the existing BLD-1 projection back into Frankie;
- no Nucleus architecture in the executable route.

This is the best match to the user's recollection of native design plus the IBM piece plus ReFRAG and the dipole teacher.

The architecture lock is:

1. Keep current Frankie and A-memory unchanged as the protected baseline.
2. Keep the native BOSS as the market-authoritative, causal, deterministic decision core.
3. Build the missing native recurrent reasoning loop beside the fixed-depth B0 control, never by mutating B0 into the experiment.
4. Retain Granite 4.2 8B, but initially only as a bounded, receipted shadow teacher/critic. It is not allowed to place orders, rewrite memory, supply market facts, or block the live path.
5. Promote Granite into a decision-affecting role only after serializer probes, four-day paired testing, repeatability checks, latency limits, and market-specific ablations pass.
6. Keep the existing dipole teacher as a falsifiable training hypothesis, not as an assumed proven feature.
7. Exclude the separate Nucleus architecture. IBM's recommended `top_p` setting is also called nucleus sampling in machine-learning terminology; that sampling term is unrelated to the excluded Nucleus system.

The complete B2 target is not yet functional. The repository contains B0, the ReFRAG/QSV seam, the dipole harness, serializer, and restart contracts. It does not contain the B1 whole-representation recurrence, a production BOSS input builder on the current Frankie branch, or a Granite invocation/runtime path.

## Documents in this record

| File | Purpose |
|---|---|
| `01_BOSS_FINAL_CANDIDATE_RECOVERY_AND_LOCK.md` | Recovers the exact design, separates built from specified, and fixes the integration boundary. |
| `02_GRANITE_REASONING_LAYER_ASSESSMENT.md` | Independently evaluates Granite 4.2 8B, scores the credible choices, and records the with/without decision. |
| `03_DIPOLE_TEACHER_TEST_AND_PROMOTION_PLAN.md` | Explains what the dipole harness currently does, identifies its blockers, and defines the four-day test and promotion program. |
| `04_LIVE_MBO_VENDOR_AND_COST_ASSESSMENT.md` | Compares DTN IQFeed with direct CME options against Frankie's full-MBO requirements and gives fixed-cost ranges. |
| `05_PERSONAL_AUTOMATED_EXECUTION_AND_LICENSING.md` | Maps personal automated execution through tastytrade and Kalshi to the likely CME non-display categories and safety controls. |
| `06_AWS_SINGLE_USER_GOVERNANCE.md` | Records why an AWS display name such as DavisAI is not by itself dispositive and defines the single-user evidence package. |
| `SOURCE_REGISTER.md` | Lists the official external sources, effective dates, and the claims each source supports. |

## Evidence labels used throughout

- `REPO FACT`: directly supported by committed source, tests, or governing repository documentation.
- `OFFICIAL EXTERNAL FACT`: directly supported by IBM, DTN, CME, AWS, tastytrade, or Kalshi documentation.
- `INFERENCE`: an engineering or licensing interpretation that still needs an experiment or written vendor confirmation.
- `USER DECISION`: a constraint or choice supplied by the user.
- `OPEN GATE`: work that must complete before launch, promotion, purchase, or live-money use.

## Protected boundaries

- Do not rewrite the frozen Sunday run or current A-memory.
- Do not re-run Sunday merely to test BOSS.
- Do not change the causal clock from `ts_recv_ns`.
- Do not collapse native MBO to MBP-10 or top of book as the scientific input.
- Do not modify the fixed-depth B0 baseline to add B1 recurrence.
- Do not duplicate ReFRAG registry/governance inside BOSS.
- Do not let Granite see outcomes, another current arm's output, or answer-bearing Step-1 material before the blind locks.
- Do not let any language model submit directly to a broker or exchange adapter.
- Do not state that DTN, CME, tastytrade, Kalshi, or AWS licensing is cleared until the named written-confirmation gates close.

## What this record does not do

This documentation does not merge the BOSS source branch, change executable code, alter model configuration, call Granite, order a data feed, create broker credentials, submit an order, or open a pull request. It records the decisions and the exact work required for the later brownfield implementation tranche.
