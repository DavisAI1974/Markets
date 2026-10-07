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

## Still open at this increment

Downstream exchange/request recovery, standalone scientific operation bindings, and actual
scientific-owner decision integration. Historical rework for both teachers and runtime
verification remain held for explicit authorization. Step 5 is not complete.
