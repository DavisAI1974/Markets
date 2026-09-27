# CCode Next Slice — After Frankie Box Cleanup

Read this only after a genuine cleanup receipt exists.

## Goal for this slice

Verify that the approved cleanup completed, prove the box has usable capacity, confirm the old ROOT process is inactive, and prepare one same-root corrected-runtime resume. Stop after dispatching that single resume and recording its initial receipt.

Do not begin projection publication recovery, digest, downstream staging, principal, classroom, grading, correction or retention in this slice.

## Preconditions

Require all of these actual receipts:

- Cleanup receipt from the committed retirement script.
- Five target files absent.
- Reclaimed allocated bytes and post-cleanup available bytes.
- Retained checkpoint still matches SHA256 `2d61559ca9f5c650cdb22fa9aff29b8f0a366a648983493d435c26a3387943e6`.
- Retained terminal descriptor still matches its recorded SHA256 `3cc7e16ce0cfa3e2c5297d98d860c5231e09c747e5f82c2de698d7f41ed26ab4`.
- `recovery-9defa3169f7d46679491da2b1bfbbce2` is intact.
- PID59092 and process token `099d4eb6-a46d-4b94-a888-f15e55c1ee7e:54118158` are inactive.
- No current process has an open descriptor for any approved target.

If any precondition is missing, stop and report the exact missing receipt.

## Cleanup receipt already completed

Use the completed retirement receipt; do not rerun cleanup:

- Retirement workflow: 36338877506
- SSM command: 4ad6118d-f846-4283-b4da-87678b15a200
- Receipt: /opt/frankie-box/work/retention/superseded-members-dbcbaaf8689f4648822b59748d3d895c/receipt.json
- Exactly five approved files removed.
- Claimed reclaimed: 945,839,562,752 bytes.
- Actual freed: 945,839,427,584 bytes.
- Available bytes after: 945,841,012,736.
- Available bytes before: 1,585,152.
- Current generation recovery-9defa3169f7d46679491da2b1bfbbce2: all three ledgers re-verified intact.
- Retained checkpoint was SHA256-verified before deletion.
- ROOT restarted: no.
- Scientific records replayed: 0.

Treat this as completed cleanup evidence. Do not dispatch the retirement script again.

## Resume identity

Use the existing calculation root:

`/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`

Use the corrected immutable runtime:

- commit `2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a`
- ref `codex/frankie-projection-runtime-2d3e6bb`
- successful staging run `36323776583`
- CODE_ROOT exactly as printed by that staging receipt:
  `/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a-36323776583-1/markets`

Use:

- original authorship receipt and SHA256;
- source-binding SHA256 `99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a`;
- DATA_WORKERS=48;
- RECONSTRUCT_MISSING=0;
- the verified full terminal checkpoint;
- the existing projection plan and valid completed compressed range receipts.

Do not rebuild records, replay ingestion, create a new root, duplicate staging or change the live checkout.

## Dispatch and first verification

Use the existing `frankie_box_run.yml` and committed `frankie_box_monday_calculations.sh` route. Pass the exact values from the verified receipts. Do not invent shell paths or substitute a mutable branch.

Use these exact dispatch values from the prior resume identity:

- `CODE_ROOT=/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a-36323776583-1/markets`
- `OUTPUT_ROOT=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- `AUTHORSHIP=/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4/authorship-receipt.json`
- `AUTHORSHIP_SHA256=ade460dede20a4557b6369ca45f653fdae24a958fd52d1f1e449da53fe8e2ec6`
- `BINDING_SHA256=99440a65fe5ad6fa93fbeebdfda3391d9dfcbf58abb3251661e6f76adea2d90a`
- `DATA_WORKERS=48`
- `RECONSTRUCT_MISSING=0`
- `RESUME_CHECKPOINT=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json`

The existing workflow appends `MARKETS_SHA` from the dispatched commit. Keep the runtime ref immutable and use the existing staged corrected checkout.

Immediately retrieve:

- workflow ID and conclusion;
- SSM command ID/status;
- new PID and process token;
- restored checkpoint identity;
- projection plan hash;
- completed member/lifecycle range counts;
- ordered byte frontier from progress.json;
- compressed archive bytes;
- available filesystem bytes.

A successful startup is not calculation completion. Stop this slice after the single resume has a real startup/checkpoint receipt. Do not dispatch observers repeatedly; use one fresh read when progress meaningfully changes.

## Success condition for this slice

Report:

- cleanup receipt path/hash;
- exact files removed and allocated bytes reclaimed;
- post-cleanup available bytes;
- checkpoint and descriptor hashes;
- proof PID59092 is inactive;
- new resume workflow/SSM/PID identity;
- initial restored checkpoint and projection range receipt;
- remaining pending stages.

If cleanup or resume fails, preserve the actual failure and stop. Do not retry the same blocked route without a changed access or capacity condition.
