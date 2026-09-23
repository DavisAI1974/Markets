# Inactive reviewed source staging — 2026-09-23

Scope: stage code independently of actual Monday modelling inputs. Cycle 0 remains held.
No Amazon Bedrock service is involved. Source staging does not establish runtime readiness.

## Design

The explicit workflow_dispatch action inventory inspects fixed Linux paths, Git metadata,
available disk and service state. It reads installed distribution metadata as text, without
importing repository or package code. It neither opens source SQLite nor reads application
keys, IMDS, SSM parameters or model/provider endpoints. No application files are created.
GitHub/SSM retain their normal audit records. Git commands require a standalone .git directory,
refuse redirected metadata and configuration includes, disable hooks/fsmonitor and external
diff/textconv, and neutralize configured clean/smudge/process filters without executing them.

The stage action produces an exact-commit Git object pack on isolated Linux CI. The pack
contains only the dispatched commit and its reachable tree/blobs; it contains no parent
history, checkout credentials or untracked files. Symlinks, submodules and unsafe tracked
paths are refused. A shallow marker makes the resulting detached checkout self-contained.

The private existing bucket/region and presigned GET-map transport deliver this hash-pinned
pack. Writes use fresh run/attempt names and conditional S3 creation. The box creates only
fresh /opt/frankie-box/code/transfer-COMMIT-RUN and COMMIT-RUN directories. A flushed
create-new transfer intent precedes the download; a flushed staging intent precedes Git
import. Pack hash, object set, target commit, full tree, worktree cleanliness and untracked
absence are checked. Each tracked file's raw Git blob hash and executable mode must match
the tree, even if Git attributes normalize different worktree bytes to a clean diff. Checkout
transformations fail closed and retain their intent. Every checkout file and directory is synced before the completion
receipt binds the intent, pack hash and code root. Partial state remains; retry uses a new
run id. No cleanup, overwrite, service operation or shared-checkout advancement occurs.

The launcher receives the exact reviewed helper bytes through the established literal SSM
assignment mechanism, validates their SHA256 and executes them using python3 -I -S -B.
Inventory therefore needs neither an already-staged helper nor a download/file write.
The runner uses AWS-RunShellScript's commands string list with one multiline command.
The workflow measures serialized runtime parameters before dispatch and refuses more than
48 KiB, reserving 16 KiB below AWS's 64 KiB document limit. Logs contain only the parameter
byte count, never the helper payload or unmasked signed capabilities.
Reference: https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-creating-content.html

The receipt's code_root can be passed as CODE_ROOT to frankie_box_prepare_trading_day.sh.
After owner model_context_rows, cutoff rule/roster and coherent pinned input bindings exist,
preparation can use that checkout and a fresh output root. Source staging does not invoke it.

## Verification

Isolated Linux tests use temporary Git repositories. They verify exact bytes/HEAD, no
ancestor-history objects, no source-checkout movement, dirty/untracked/ignored refusals,
symlink refusal, create-new semantics, retained intent after interruption, inventory
without writes/imports and hash-bound downloads. Adversarial cases cover configured Git
execution hooks/filters, metadata redirection, foreign symlink packs, CRLF normalization,
hidden executable modes, isolated shell bootstrap and the SSM payload budget. No production workflow is automatic:
frankie_code_staging_ci.yml is test-only on scoped pushes; frankie_stage_code.yml accepts
workflow_dispatch and workflow_call only. The already-registered frankie_box_run.yml routes the
exact staging script to that same-commit reusable workflow after credential-free validation of
ACTION=inventory or ACTION=stage, the canonical instance/region, empty presign and token-copy=false.
The generic script route is unchanged except for excluding that exact script. Root reviews and owns commits and dispatch.

## Remaining native boundary

The Linux preparation archive is not a native-host configuration. Current recovery
admission opens the original Linux container and compact prefix admission checks its
full-source digest. Native delivery requires a separate explicit transport/provenance
descriptor, dependency closure and native storage bindings; canonical recovery receipts
remain unchanged. The original step 1b context/code/seed rebinding remains required.
No Windows CI or C:/E: access is introduced. No ingestion/replay, runtime start/stop,
model call, pinned Pod bootstrap change or cycle authorization is part of this slice.
