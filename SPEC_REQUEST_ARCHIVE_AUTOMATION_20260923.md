# Request archive automation — 2026-09-23

The next workflow improvement reuses the existing host-stage-critic-request route. R2's missing-writer diagnosis is outdated: the workflow has inline AES-GCM encryption, but it requires manual invocation, refuses valid replay, and has no durable publication transaction.

## Boundary
Extract a reusable exact-byte archive writer, integrate it into the existing workflow, and expose that workflow as workflow_call with required explicit inputs and receipt outputs. It archives an already minted Granite model request. It does not create a request, infer, start/restart/stop a host/Pod, deliver readiness, or resume Cycle0. Future orchestration will use its verified archive commit as a prerequisite, not infer success from dispatch acceptance.

## Writer contract
write_request_archive(directory, body:bytes, expected_sha256:str, *, key:bytes, key_parameter:str, key_region='us-east-2') returns a stable nonsecret receipt.
Validate exact hash, key32bytes, existing transport namespace and region before writing. Linux directory handles refuse symlink traversal. Parent exists; create-new destination. Persist public intent, ciphertext, then reader-compatible envelope last; flush files/directories. Use fresh AES-GCM96bit nonce, request digest as authenticated associated data. Do not serialize or log plaintext/key.
An existing complete archive is reusable only after authenticating ciphertext, exact plaintext, envelope metadata and retained intent. Preserve all existing bytes. Partial, changed, foreign or linked state refuses without deleting evidence. Existing legacy archives lacking the new intent remain readable by the old reader; migration/reuse requires explicit handling, never invented intent.

## Integration
Validate required workflow inputs before credentials or SSM, use shared concurrency, explicit workflow_call inputs/outputs and same-commit source. Do not use historic day/cycle defaults in callable route. The workflow uses the writer and existing independent reader, stages only the exact archive directory, and no-ops a verified unchanged archive. A code ref race must refuse rather than silently mixing source versions. Persist encrypted artifact evidence even if publication fails.
Existing transport key is read from SSM SecureString. This work creates/rotates no keys. No provider integration changes.

## Verification
Independent tests first: exact-byte/current-reader roundtrip (including large integers), nonce freshness, replay byteidentity, invalid input/key/metadata, tampered ciphertext, partial writes, collisions and linked paths. Run actual embedded workflow Python with fake providers to verify durable helper use and no-op behavior where feasible; parse full YAML for callable contracts and credential boundary.
Remote Linux test-only Actions only. No workflow_dispatch, SSM, live archive, new model request or runtime transition is executed in development.
