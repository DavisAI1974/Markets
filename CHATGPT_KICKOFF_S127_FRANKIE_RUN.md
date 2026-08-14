# ChatGPT Kickoff S127 — Run Frankie from sanctioned g24 state

## Start here

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/burn-hh-12m-s125`

Sanctioned S126 artifact commit: `5d0354b5230c5fe746c639608075e0a3f2a54735`

That commit is the current data/artifact truth for g24. GitHub Actions workflow `S126 Frankie Specialist Parity`, run `31772136525`, completed `success` against that commit.

This document is the S127 takeover note. Treat it plus the current branch state as newer truth than older handoffs when they conflict.

## S126 is CLOSED — do not reopen it

The following work is complete and sanctioned:

- S125 burn/HH work.
- S125 Frankie national-storage-null repair.
- Specialist A-E parity to the current Frankie build, without rewriting their roles.
- M-13 recovery for `storage_consensus`, `weather_forecast_cycle`, and `freeze_risk`.
- S114 `weather_forcing_forecast` recovery from the existing private S3 store.
- Wind and solar verified non-null and served separately on all 10 g24 days.
- Legacy S114 D37 separation metadata normalized to the machine-readable boolean contract without changing wind or solar proxy values.
- Storage-consensus decision-time causality tightened to the actual D-1 20:00 ET reopen wall.
- Hard future value-capture gate installed.
- Canonical `grp24_state.json` re-staged and all 10 `g24_causal_slices/state_*.json` rebuilt.
- The 11 regenerated canonical artifacts committed at `5d0354b...`.
- Committed-artifact CI passed the same S114 and causal-slice gates from Git.

Do not rerun M-13, redesign S114 wind/solar, or regenerate g24 state merely to prove these again unless a later run produces concrete contradictory evidence.

## What the sanctioned committed-artifact gate proves

The committed g24 state/slices satisfy:

- all configured g24 days present;
- `weather_forcing_forecast == PASS`;
- `wind_solar_separate is True`;
- `causal_slices == PASS`;
- `future_capture_stamps == 0`;
- `causal_structure == PASS`;
- specialist A-E parity/blind-wall tests pass;
- protected `spawn.py` and specialist role files are unchanged;
- S114 producer -> decision state -> state health -> restore path remains intact.

The protected historical blind S114 artifact was also verified unchanged during AWS recovery.

## Non-negotiable build rules

Frankie remains the coordinator.

Do NOT change:

- Frankie settings;
- Frankie schema;
- Frankie inputs;
- specialist A-E role definitions;
- `spawn.py`;
- S114 wind/solar methodology;
- the current served data universe merely to add more data points.

The served universe is at the stopping point. Do not invent/build new data points before running Frankie. Give Frankie/specialists the complete causal data universe already served and let the run reveal whether anything is genuinely missing.

Preserve all causal/blind walls. Do not weaken a fail-closed gate to make a run pass.

## Temporary Claude runtime rule

Claude may be used as the temporary model runtime/backend while OpenAI/AWS account constraints are in effect.

Do NOT redesign Frankie around Claude, embed Claude-specific assumptions into the coordinator contract, or change the specialist roles for Claude. Frankie is the framework/coordinator; the model backend is replaceable.

## NEXT TASK — run the current Frankie forecast path on sanctioned g24

Do not start by writing new infrastructure.

First identify the CURRENT canonical launcher/CLI and backend seam from the current tree. Inspect at minimum:

1. `research/kalshi/frankie_s121_curve_restore.py`
2. `research/kalshi/frankie_s118_redo.py`
3. `research/kalshi/frankie_group_forecast_s118.py`
4. `research/kalshi/frankie_backends.py`
5. `research/kalshi/frankie_specialist_parity_s126.py`
6. `research/kalshi/group_config.py`

Also inspect any newer Frankie wrapper/runner in the current tree before choosing a command.

The purpose of that inspection is narrow: determine the exact supported invocation that gives Frankie the sanctioned g24 causal slices, full current brain/data universe, existing A-E specialists, and a temporary Claude backend without bypassing existing runner contracts.

Do not guess the CLI. Do not modify an allow-list or runner guard just because an older runner names only older validation groups; determine whether a newer wrapper already owns g24 first.

Before model invocation, prove the runner will consume:

- `research/kalshi/renders/ng_refine_s95/grp24_state.json`;
- `research/kalshi/renders/ng_refine_s95/g24_causal_slices/state_<DAY>.json`;
- current specialist A-E role files unchanged;
- current full brain / lossless serving path;
- no realized g24 outcome in the blind forecast packets;
- Frankie as coordinator, with deterministic specialist ownership rather than averaging.

Then run the smallest canonical g24 preflight/smoke path available. If it passes, proceed into the real temporary-Claude Frankie run. If it fails, fix only the exact current runner/backend seam that failed; do not reopen S125/S126 data work.

## Current runner facts already established

`frankie_s121_curve_restore.py` installs on top of the S118 redo machinery and installs S126 specialist parity. It exists to preserve/restore the current path-curve contract rather than replace Frankie.

`frankie_s118_redo.py` is current redo orchestration machinery using specialist A-E ownership, per-day causal packets, full brain serving, and outcome exclusion.

`frankie_group_forecast_s118.py` contains a model-backend seam and strong packet/outcome guards, but it is an older validation runner. Inspect its current restrictions before assuming it is the direct g24 launcher.

## AWS status

The private AWS/S3 data-plane work needed for S126 is complete. Do not make another AWS recovery pass before the Frankie run unless the canonical runner itself demonstrates a missing runtime dependency.

ChatGPT does not currently have a credentialed AWS shell in-chat. Claude's credentialed Markets environment can execute exact AWS commands when genuinely required.

Never paste or commit AWS passwords, access keys, secret keys, session tokens, or MFA codes.

## Artifact-format note — non-blocking

The sanctioned `grp24_state.json` and rebuilt slices were written as compact/single-line JSON. The apparent large line-deletion diff at `5d0354b...` was formatting, not data loss: the canonical state grew in bytes and gained the three recovered M-13 blocks per day while preserving all 10 day keys.

Do not reformat these artifacts as part of the Frankie run. If diff readability is worth improving later, fix the writer deterministically in a separate task after the run.

## Read order for S127

1. `CHATGPT_KICKOFF_S127_FRANKIE_RUN.md` — this file, current takeover truth.
2. `S126_M13_RECOVERY_STATUS.md` — provenance and recovery mechanics if needed.
3. `S126_FRANKIE_SPECIALISTS_WEATHER_STATUS.md` — specialist/S114 status if needed.
4. `S125_FRANKIE_STORAGE_FIX.md` only for closed S125 provenance.
5. Current repo tree and current code are authoritative over older handoffs.

## Immediate definition of progress

S127 should end the inspection phase with an exact canonical command and then actually run Frankie on g24. Do not spend another session adding data fields or rebuilding already-closed substrate work.
