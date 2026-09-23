# Whole Monday -> next-trading-day forecast

## Authorized objective

Greg authorized the full Monday run, then clarified: "Just do the run days forecast or the next day."
Use the next trading day so the whole Monday can be input without forecasting an already-observed Monday outcome.
This records the chosen interpretation; it is not a launch receipt, measured result, source contract or runtime pin.

- Input trading day: 20211004, 2021-10-03T22:00:00Z through the 2021-10-04T21:00:00Z halt.
- Forecast target trading day: 20211005, the following 18:00 ET to 17:00 ET session under the same declared trading-day policy.
- Forecast issuance: after consuming the verified complete Monday source; use its measured availability clocks.
- No intraday invocation roster, retained-tail row limit, Sunday cutoff or six-hour configuration.
- Every applicable exact reducer remains stacked. No calculation, producer, reading, critic or classroom stage is optional.
- No ingestion restart/replay, infrastructure stop, bootstrap change, evidence deletion, Amazon Bedrock or BOSS output cap.

## Two different kinds of feedback

The Monday classroom examines Monday observations: complete reading, teaching, grading, correction and saved learning.
It must not claim that a next-day forecast is correct using Monday observations.
Forecast-outcome grading and the corresponding native learning require separately verified target-day outcomes.
If those outcomes are unavailable, persist an explicit pending-feedback state and the immutable forecast; do not fabricate labels,
silently skip training, mark the whole cycle complete, or rerun the forecast with future data.

Classroom learning must retain its provenance and cannot change an already-issued forecast or be applied retroactively to Monday.
Frankie's retained knowledge comes from the brain cycle evidence, not the old six-hour Memory A inputs.

## Existing code constraints

- ForecastSession already permits pre-open forecasts, requires a certified prior reference, and rejects future opening/path observations.
- sunday_native_runtime.assemble_request requires a target close strictly after the source availability clock. Keep this check.
- trading_day_schedule currently requires pre-terminal steps and later feedback within its existing source schedule.
- prepare_trading_day and SundayExecution consume that schedule and bind training to its feedback boundary.
- feedback_cycle currently couples principal completion and native learning before its complete receipt.
- frankie_source_mapping currently binds a single member; Monday has two.
- The Granite critic currently admits a single exact selected-context prompt. Whole-day fit is unmeasured.
  Do not shrink the source or present a different reading route as this critic.
- The legacy monday_read job alone does not run native forecasting or classroom and is not the full run.

Changing the target date alone is therefore not a completed launch implementation.
Do not run the rejected author_monday_launch, host_config or cycle0 scripts.

## Implementation and verification scope

Work serially in the approved branch, with atomic commits:
1. Bind the complete recovered Monday source and both members, with measured terminal clocks and certified anchors.
2. Bind an explicit future target session using existing scientific conventions, independently witnessed source/brain inputs,
   and all Monday rows; no copied six-hour runtime configuration.
3. Separate retained forecast/classroom work from pending target-day feedback without weakening causal checks or completion semantics.
4. Verify the exact whole-day Granite route and all reading/calculation/classroom wiring. Physical admission failures remain explicit.
5. Commit/push, stage the exact commit, then start only the complete authorized route. Preserve root/classroom progress probes and
   validate checkpoint reads. Report actual phases, counts and failures, never estimated completion as a measurement.

Source modules remain under research/kalshi/frankie_boss and deploy/aws/box; focused tests accompany the affected code.
Use existing remote pytest workflows; no local C:/E: artifacts, new push automation, canary or comparison run.
For the existing box regression suite, the authoritative full command is the final pytest step in
.github/workflows/frankie_box_codecs_ci.yml. Additive native changes also need their native-focused tests.
No new executable launch command is documented until its real bindings and end-to-end path exist.

Acceptance: every verified Monday record reaches the required calculations and reading routes; the forecast contains no
target-day observations; classroom evidence is complete; absent target outcomes remain pending, not successful learning.
No new runtime changes or measurements are claimed by this document.
