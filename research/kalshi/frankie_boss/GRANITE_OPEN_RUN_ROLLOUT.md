# Retained Granite open-run rollout

No deployment or Pod mutation has been performed by this change. The measured
actual request exceeds the model's positional limit; resolve that architecture
gate before any paid start.

## Candidate behavior

The explicit `RUNPOD_GRANITE_LIFETIME_SECONDS=none` mode gives model staging,
startup verification, and healthy backend/proxy supervision no elapsed deadline.
The original positive-integer mode retains its prior bounded behavior.
The proxy cancels its overall request timer only after authenticating and fully
receiving a valid bounded JSON body. Its backend connection has a finite connect
timeout, then no total decode deadline. Socket/connection loss remains ambiguous;
there is no automatic second POST or claim that a provider-lost result is recovered.

The retained model remains exactly thirteen files under `/opt/ml/model`. No
weights, image, Pod identity, persistent mount, or original bootstrap files are
replaced. The versioned bootstrap is separate:

`/opt/ml/additional-model-data-sources/bootstrap-open-run-v1`

## Concrete deployment sequence after admission

1. Export the committed LF files in `granite_runpod_package.FILES` using `git show`
   from the reviewed commit. Call `granite_runpod_package.package` with the new
   versioned directory as `runtime_directory`. Save the new bundle roster,
   bundle SHA256, and source commit. Every changed Python file changes the bundle
   identity; this is a new runtime candidate, never the accepted old hash.
2. Stage those eight small files (seven roster members plus `runpod_bundle.json`)
   under a new digest-scoped private bootstrap prefix. Verify every staged byte.
   Generate fresh narrow download capabilities into memory, never public artifacts.
3. Read the exact retained Pod while EXITED. Validate its ownership, image,
   persistent mount, and original retained receipt. Capture its full original
   environment privately for rollback; it includes credentials and URLs and
   must never be printed or uploaded as a public artifact.
4. Build the new command with
   `granite_runpod_cloud.bootstrap_command(rows, bundle_sha, bucket,
   directory=versioned_directory, open_ended=True)`. The open command removes
   the old total 60-second small-bootstrap download alarm while preserving
   explicit per-connection I/O bounds and every hash/path verification.
5. Patch only the retained Pod's environment, preserving all other values:
   `RUNPOD_GRANITE_LIFETIME_SECONDS` becomes `none`;
   `RUNPOD_BUNDLE_SHA256` becomes the new bundle digest;
   `SUPERVISOR_PROGRAM__APP_COMMAND` becomes the new verified command;
   `RUNPOD_SUPERVISOR_COMMAND_SHA256` becomes its exact UTF-8 SHA256;
   `RP_BOOTSTRAP_URLS` becomes the new exact roster's private URL mapping.
   Read back and compare these exact values without logging secrets.
6. The separate progress-observer workflow starts the retained Pod once, only
   after exact request admission and the local input-admitted witness exist.
   New startup evidence must show `lifetime_seconds:null`, the new bundle and
   command identities, the unchanged thirteen model-file witnesses, and fresh
   authenticated health. No acceptance smoke or repeated inference is required.

## Exact rollback

Use explicit stop-retain and confirm EXITED. Restore the complete privately
captured original environment from step 3, rather than reconstructing it or
merging guessed values. Read back for exact equality. The original bootstrap
directory and model mount were never modified, so restoring that environment
restores the original command, bundle hash, URLs, and bounded lifetime. Leave the
new versioned directory intact as evidence; no recursive deletion is required.
Do not start the old configuration automatically: it has the old runtime budget
and does not satisfy the current user's open-run policy.
