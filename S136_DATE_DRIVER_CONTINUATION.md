# S136 Date-Driver Continuation

Branch: `chatgpt/burn-hh-12m-s125`

Status: **checkpoint only; no Frankie logic changed yet in this continuation.**

This note records the inspection immediately before moving to a new ChatGPT session so the next chat does not redo it.

## Standing constraints

- ChatGPT remains the model handoff for these historical sessions; do **not** wire Bedrock or another model API into the workflow.
- `spawn.py` remains protected and untouched.
- Do not edit Frankie brain/schema, A-E specialist roles, or datapoint universe as part of this runner cleanup.
- Hydration remains rejected.
- Forecast curve is fully event-driven: no fixed forecast clock, no fixed cadence, no minimum/maximum point count, and no filler points.
- A forecast waypoint exists only when Frankie predicts a meaningful market-state transition. Scheduled events may naturally produce exact-time waypoints because the event itself is scheduled.
- Preserve prior frozen S135/S136 artifacts; never overwrite them during a rerun.

## What was inspected

### `research/kalshi/frankie_s135_date_driver.py`

The driver is still a thin adapter over `date_run_session.json`, but the config currently has to supply several pieces of run plumbing explicitly:

- `anchor_date`
- `anchor`
- `anchor_lasthr_dir`
- `pre_leg`
- optional `seam` / `post_leg`
- `eia`
- `basis`
- `namespace`
- `outputs`

The historical cutoff view and Friday E -> A handoff transport are already implemented in the driver and should be preserved.

### `research/kalshi/frankie_s135_date_render.py`

The renderer still plots P25/P50/P75 together and still hardcodes the old Sep-22..Oct-03 final PNG filename. That is presentation/runtime plumbing, not a reason to change Frankie's event-driven curve contract.

## Exact unfinished work

Finish the **permanent date-driven ChatGPT historical-session workflow** so a future run is driven primarily by the requested date window instead of hand-entered run plumbing.

Target behavior:

1. User supplies the historical date window/session request.
2. Runner derives safe run metadata from existing repo truth where it can do so deterministically.
3. If a required contract/anchor/calendar fact is outside proven repo data, fail closed rather than guess or synthesize.
4. Workflow stages exactly one ChatGPT model request at a time.
5. ChatGPT response is frozen before the workflow advances/reveals the target.
6. Preserve the historical cutoff wall and Friday E -> A -> Monday B sequencing.
7. Keep forecast generation fully event-driven; never add a time grid to make the render look denser.
8. Simplify the primary render to the central Frankie event-driven path plus realized path unless uncertainty bands are explicitly requested.
9. Make render/output naming derive from the requested date window rather than `20250922_20251003`.
10. Preserve existing frozen run namespaces and create a new auditable namespace for any rerun.

## Workflow to finish

`.github/workflows/frankie_s135_date_session.yml`

This is the workflow the next chat should continue. The supporting runner is `research/kalshi/frankie_s135_date_driver.py`.

Do not restart architecture work and do not create a new G-numbered group/config. Continue from the current branch state and this checkpoint.