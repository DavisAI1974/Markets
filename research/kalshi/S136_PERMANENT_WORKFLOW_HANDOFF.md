# S136 Permanent Date-Driven Workflow Checkpoint / Handoff

Status: COMPLETE

This document is the final workflow-only checkpoint for the permanent Frankie date-driven historical-learning transport. It intentionally does not begin or mix in the next Frankie research/reasoning issue.

## Canonical repository state

- Repository: `DavisAI1974/Markets`
- Branch: `chatgpt/burn-hh-12m-s125`
- Pre-checkpoint validated code HEAD: `2a818c08d62ec2a22d64b95f032773c861b438d2`
- Validation workflow: `S135 Frankie Date Session`
- Successful run: #31
- Run ID: `31968791381`
- Run conclusion: `SUCCESS`
- Validated workflow artifact ID: `9269229547`
- Artifact name: `frankie-s135-date-session`
- Artifact digest: `sha256:51632daf6f073601a98ce64f8ac98788fced2710226bc74d83d92c4a8555791b`

## Final defect fixed

Run #29 exposed a real prior-session identity defect for Monday `20260413`: the older harness tape path could scan backward by calendar day and encounter Sunday `20260412` before Friday `20260410`.

The permanent date driver now owns a fail-closed prior-session boundary:

1. Resolve the requested date window against the exact declared `group_config` session sequence.
2. Build `target_session -> immediately previous resolved trading session` from the declared completed-session anchor plus the resolved session sequence.
3. Stage and prove the exact required prior `n0`, `n1`, and `L1` objects for that map.
4. During date-driven state construction, disable calendar-day fallback and serve only the exact proven prior session.
5. Fail closed if that exact prior tape cannot be read.
6. Post-validate every target row so the served tape identity equals the resolved prior-session identity.

This is not a Monday special case. Weekend and holiday gaps are handled by the resolved actual-session sequence. No trading session is inferred from `target_date - 1 day`.

The repair is scoped to the permanent date-driven workflow. `forecast_harness.py` was not globally rewritten.

## Monday 20260413 proof

For target session `20260413`, the resolved prior-session map is:

- target: `20260413`
- previous actual/resolved trading session: `20260410`

The Run #31 artifact's Monday packet proves:

- `tape_conditions.asof_prior_session = 2026-04-10`
- `tape_conditions.session = 20260410`
- `tape_conditions.source_store = leg:ng_mbo_ngk26`
- `prior_session_resolution.status = PROVEN_RESOLVED_SESSION`
- target = `20260413`
- prior = `20260410`
- calendar `D-1` lookup disabled
- MBO flow present
- L1 book present

Sunday `20260412` is not in the required prior-tape staging set.

`20260412` does appear as the last strictly-prior day in the bounded continuous `n0` history used to rebuild vol conditioning. That is legal historical conditioning and is not used as Monday's previous trading session.

## Targeted S3 / canonical state proof

Run #31 targeted staging passed without a blanket substrate restore or synthetic hydration.

- canonical-state bucket: `bento-568968024170-us-east-2-an`
- staged canonical object count: `348`
- `full_n0_restore = false`
- hydration: `REJECTED_NOT_USED`
- declared contract archive proof: PASS
- exact prior-context `n0/n1/L1` proof: PASS
- exact prior-session identity proof: `PASS_EXACT_RESOLVED_PRIOR_SESSIONS_STAGED`

Real canonical NGWU state was restored from S3, including:

- `data/ngwu/manifest.json`, size `6524`, SHA256 `a2df5990054942dd1f61539d832dda596e7e1c78fdc05c27ea0a3b3e9f38ec8c`
- `data/ngwu/ngwu.json`, size `176780`, SHA256 `f3361400b576966e54049800d1c26f07db193400650a66124069ee2b43c328de`

No fake/blank NGWU object was created.

## Bounded n0 / vol proof

The staging manifest records a bounded strictly-prior continuous `n0` history:

- first selected day: `20260108`
- last selected day: `20260412`
- requested sessions: `80`
- required minimum: `60`
- selected: `80`
- strictly before target-window start: true
- complete continuous `n0` corpus restored: false

Vol regime rebuilt successfully from the staged bounded history:

- path: `data/vol_regime/vol_regime.json`
- size: `785529`
- SHA256: `fd04ea919e208c70bec74df06316fe136905b5a82970e5f85a564a3c849a02e8`

## Preflight proof

Run #31 `preflight.json`:

- status: `PASS`
- run gate: `PASS`
- failed checks: none
- coordinator: Frankie
- runtime stack: `s135.current-frankie.2`
- canonical plays: `90`
- full plays served: `90`
- specialists: A-E
- brain SHA256: `bf473faef4d5a1b8fc68a214616e6c6163f0db1794ac98818a5401225563da57`

All mandatory checks passed, including targeted S3 restore, exact scored-contract mapping, current-full-brain serving, later-learned evidence preservation, A-E/full-universe serving, schema/runtime, dynamic event-driven curve contract, reasoning authority, sequential legal prior, Friday E -> A -> Monday B handoff, target-outcome blocking, and freeze/reveal ordering.

## Current-full-brain target-only wall proof

The actual Run #31 Monday packet records:

- current full Frankie is served for historical learning
- `90/90` canonical plays served
- later-learned historical evidence preserved except evidence attributable to the unrevealed target session
- old broad historical brain cutoff restored: false
- target session `20260413` evidence: `WITHHELD_STRUCTURALLY`
- source-group aggregate touching target: withheld
- target-window redaction/sanitization total: 3

The unrevealed target outcome remains blind. The current brain is not rolled back to the historical forecast date.

## Model transport boundary

Run #31 reached exactly one legal model boundary and emitted exactly one request:

```json
{
  "status": "MODEL_INPUT_REQUIRED",
  "kind": "starter_weekend_bridge",
  "day": "20260413",
  "owner": "A",
  "output_filename": "bridge_A_20260413.json",
  "gid": "gdate"
}
```

The ledger remained incomplete with no frozen/revealed/scored events because the run correctly stopped at that first model boundary.

No Bedrock or new LLM API was added. ChatGPT remains the model transport.

## Scope / protected-contract audit

The workflow repair changed only `research/kalshi/frankie_s135_date_driver.py` before this checkpoint document.

It did not modify:

- `spawn.py`
- `knowledge/ng_brain.json`
- brain schema
- A-E specialist roles
- canonical play universe
- datapoint universe
- prior frozen blind artifacts
- historical target-only outcome wall contract

No hydration or synthetic historical datapoint family was introduced. No guessed futures-roll rule was introduced. No automatic brain teaching was added.

## Remaining workflow defects

None found in the final Run #31 workflow/artifact audit.

The permanent date-driven workflow is checkpointed through the next legal ChatGPT model-input boundary. The next Frankie research/reasoning issue is intentionally not started here.

PERMANENT WORKFLOW WORK IS COMPLETE.
