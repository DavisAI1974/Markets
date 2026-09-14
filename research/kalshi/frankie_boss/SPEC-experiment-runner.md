# Paired execution and explicit scoring

Add a single-writer execution journal above existing ExperimentPlan, arm/output
locks and RevealLedger. Inputs are exact immutable source, partition, exclusion
and execution-order bytes whose SHA256 values match the plan. Execution order is
a JSON array containing the complete roster once. Each arm supplies exact byte
artifacts for every declared factor except controller_hash, which binds the
runner's Python code identity. A runner receives only its own artifacts and the
shared causal input, never another arm's outputs or outcome material.

Only module-level Python functions with no closure are supported. Callable pins
bind bytecode, qualified name and defining module bytes; all runtime dependencies
and mutable external resources remain explicitly governed outside this narrow
code identity. This is interface isolation, not an OS sandbox or proof a malicious
callback cannot inspect external files or globals.

Persist intent before each runner callback and exact returned bytes afterward.
Successful arms replay from the journal. An incomplete arm intent is uncertain
and cannot auto-repeat. Complete outputs feed existing freeze_outputs and a
separate RevealLedger; partial rosters cannot reveal. Actual reveal still requires
explicit authorization. The existing irreversible pending-reveal behavior remains.

Scoring uses one explicitly pinned pure callback, the same retained exact outcome
bytes and each frozen arm output. It receives declared partition/exclusions but
no metric defaults. Retain every exact score result, including null/negative
results. Score intents/results are durable; uncertain callbacks do not auto-repeat.

Restart requires independent exact execution-journal checkpoint. If the reveal
ledger advances beyond the last durably coordinated reveal checkpoint during a
crash, the caller must provide an independently trusted reveal checkpoint; no
newer journal tail is silently adopted. Both journals remain append-only.
Re-read the retained reveal journal against the exact coordinated checkpoint and
output lock before each scorer starts, before each score result commits, and
before fresh or replayed complete scores return. A foreign append or corruption
cannot be accepted through cached scores; a failed post-callback check leaves
the scorer intent uncertain and cannot auto-repeat. This detects mutations at
those boundaries under the single-writer contract, not arbitrary concurrent
filesystem writes after a completed verification.

Tests use two small actual native BOSS models on one synthetic source fixture,
then a deterministic synthetic scorer/outcome callback. No provider, training,
real market input, held-out read or production scoring claim occurs.
