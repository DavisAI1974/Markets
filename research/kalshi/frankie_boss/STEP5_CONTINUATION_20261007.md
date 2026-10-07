# Step 5 continuation — 2026-10-07

Base: `4e416e1826156f59be562d78ed22e9ca886b6758`, verified on the remote before editing.
SOURCE-BUILT / RUNTIME-UNVERIFIED. Source review, AST without imports and whitespace only.
No tests, additional validators, AWS account actions, data/model runs or historical rework.

## Changed inputs and partial claims

The existing successor request additionally accepts:

| Optional field | Contract |
| --- | --- |
| `affected_claim_ids` | Nonempty ordered subset of original claim IDs; omission retains the whole-lesson retest behavior. |
| `replacement_claims` | Path/bytes/SHA256 of a complete `FRANKIE_SCIENTIFIC_CLAIM_INPUTS_V1` projection. Author and ordered IDs remain identical; claims outside the affected set remain identical. |
| `replacement_search` | Path/bytes/SHA256 of the corrected owner-day `MANIFEST.json`. Intake requires the run's completed search receipt to name that directory. |

Only affected claims reach `scientific_teacher.test`. The complete successor retains all other
claim projections and results exactly. `knowledge_retest.claim_operations` identifies which
claims used the new operation and which retain the original input/result witnesses. This is
not another observation for preserved results. Each subsequent correction retains that chain.

Original input/result/source evidence is immutable. A replacement projection is explicitly
selected input, not a fabricated scientific lesson. A changed owner search may replace its
same-day native evidence reference; the old reference remains listed and in the original result.
The correction publisher still requires the owner's researched decision and exact JSON scopes,
including every changed operation/header field. Partial publication cannot change unaffected
claim content/results even if an overly broad scope was supplied.

API/module review: `teacher_knowledge` owns selection, partition and computation;
`successor_dispatch` owns intake/search receipt binding; `experiment_review` owns complete
operation/claim identity and unchanged-knowledge checks. Existing locks, durable receipts,
held lane and retry paths are reused. AWS Compute guidance is reviewed for existing EC2/SSM
ownership only; no infrastructure action or new service is introduced.

## Standalone teacher operation and scientific-owner intake

The standalone CLI freezes `FRANKIE_STANDALONE_TEACHER_INPUTS_V1` before testing: full claim
projection, original source witness, exact search manifests, reader/binding identities and the
selected reproduction records. Reuse checks that complete operation. Legacy results without
an original input binding refuse rather than receiving invented provenance. `--out-dir`
selects a distinct operation; `--retain-only` retains an unpublished correction candidate.
`publish_standalone_correction` requires both real operation witnesses, affected identities,
the researched decision, exact changed scopes and evidence. Unaffected claims/results cannot
change. The ordinary standalone CLI still tests its supplied full claim collection; it is
not an affected-only standalone scheduler. A separately scoped successor must preserve the
original operation rather than silently reinterpreting its result.

`scientific_teacher.submit_correction_work` is the scientific owner's source interface for
request intake and completed decision submission. The experiment CLI routes through it;
decisions name the actual completed candidate receipt. There is no inferred scientific
acceptance from counts, no automatic conflict adjudication and no fabricated research decision.
The original request/decision contracts and held-lane dispatcher remain authoritative.

## Downstream source integration

The exchange owner has `rebuild_successor`, bound to the original frozen lesson selection,
teacher rows and rules and the exact checked source-correction chains. It uses the existing
exchange computations and preserves order, multiplicity, blind flags and unaffected inputs.
New input, full exchange, learner view and receipt are retained separately. No scientific
retest or model call occurs inside this exchange rebuild. A checked exchange transition
allows only this owner-bound dependency rebuild; original artifacts remain available.

The successor dispatcher retains dependent intent/results alongside the original operation.
Dependency computation uses the existing held-lane child. Recovery must reuse that operation's
receipt, invalidate the old exchange-bound voice result, and await any requested original-session
follow-up before acknowledging completion. Later boundary checks refuse stale frozen child inputs.

An explicit successor request may name `learner_requests`, each containing the original
`session-request.json` and `session-response.json` path/bytes/SHA256 witnesses. These are
bound to their canonical originals and original host/session. Each session receives only
the checked corrections affecting its actual selected knowledge; unaffected targets receive
explicit no-op accounting. Original forecasts, target/source/input/request identities,
pending outcome feedback and native checkpoints remain untouched.

The correction-only host route is `frankie_box_boss_session --stage knowledge_correction`
with the original session/request directory and explicit correction-request path/digest.
The existing actual-response recorder accepts `--turn knowledge_correction` and its request
digest. The response compares each declared previous/corrected scope and retains the full
corrected knowledge under that original session. Host attestation/readback is required;
preparing an outbox request is never counted as its actual response. This is code-level
correction application, **not native training or a new forecast**. The follow-up ledger does
not yet replace the later reading/model consumer's pinned knowledge base; that downstream
consumer connection remains open and must not be described as completed native recovery.

## Verification and remaining work

The checks remain source/interface review, AST parsing without project imports and whitespace
checks. No test suite, validator framework, synthetic exercises, reproduction, model/data runs,
AWS account calls or launch. AWS research covered the existing EC2/SSM lane and owner-local
I/O paths; it did not establish a measured bottleneck or speedup.

Historical rework for both teachers, actual researched correction decisions and runtime
verification remain held for explicit authorization. Standalone affected-only scheduling,
the later native knowledge consumer above, unresolved scientific mappings, general main/class
save recovery and Jev CPU completion are not closed by this source checkpoint. Frankie and
BOSS module/performance expansions have separate plans. Greg approved science-preserving
improvements on 2026-10-07 at 00:37 ET; mathematical choices and runtime remain held.
