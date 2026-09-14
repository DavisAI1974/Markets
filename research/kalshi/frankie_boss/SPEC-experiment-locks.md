# Paired experiment locks

Software increment for the initial production plan, G20/G21/G22. No experiment,
outcome read, fitting or reveal is authorized by constructing these objects.

## Contract

An immutable plan declares the complete arm roster, exact pairing comparisons,
shared source/partition/schedule/scoring/exclusion identities and per-arm model,
initialization, optimizer, batch order, seed, memory, QSV and teacher identities.
Each comparison explicitly lists factors allowed to differ. All other factors
must match. Source, partition, schedule, scoring and exclusions always match.
Every arm participates in a comparison; missing and duplicate arms reject.
These hashes are caller assertions, not proof of actual execution or authentication.

Output freezing takes exact bytes for every declared arm and binds their hashes
to the plan. It never invokes an arm runner or loads outcomes. Reordering input
arms/outputs does not change the resulting lock. Earlier objects remain immutable.

## Acceptance and verification

- Missing, duplicate, unpaired arms and undeclared differences reject.
- All required shared identities and factor identities are explicit SHA-256 values;
  roster, comparisons, factor values and output bytes affect the lock.
- Mutation of caller containers cannot change a frozen plan or output lock.

Run `python -m pytest research/kalshi/frankie_boss/tests/test_experiment_locks.py -q`
with the package directory on PYTHONPATH. Fixtures are synthetic.

## Remaining integration

The lock increment supplies pair/roster/output checks. `experiment_reveal.py`
adds a separate append-only ledger retaining the complete plan and exact output
bytes before a reveal may occur. Every operation verifies the retained trusted
head/count. Explicit authorization is required even for the loader callback.
An intent commits before that callback; a failed or interrupted loader remains
pending and cannot be invoked again after restart. Successful exact outcome bytes
are retained and replayed without reopening the source. Unknown newer journal
terminals require independently coordinated recovery, never automatic adoption.
The ledger is single-writer, not a cross-process scheduler or an exactly-once
external side-effect guarantee. A callback can access data only because its caller
supplied it; these software checks are not credentials or operational permission.

The six synthetic reveal tests verify disabled access, retained replay, uncertain
failure, source mutation, unknown newer terminal, and changed-plan rejection.
Run `tests/test_experiment_reveal.py` alongside the lock test under the same pytest
command. Actual arm execution and scoring remain subsequent integrations.
A hash-shaped scoring identity does not prove that a scoring
protocol is complete; the actual protocol and arm population remain governed inputs.
No production gate or full experiment implementation is completed by this slice.
