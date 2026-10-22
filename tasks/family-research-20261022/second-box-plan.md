# Second-box plan (planning only; 2026-10-22)

Keep i-035994afa8bdf66a5 and its 96 numerical workers running. The user requires
another runtime estimate before any new machine, snapshots or redistribution.
No second instance, monitor, agent, chat, message or live order is authorized
by this plan. Leave the old Search workflow unchanged.

## Decision and proposed machine

Take the next estimate after 15 minutes from the first verified 96-worker snapshot
at 18:29:26 UTC. The earlier 10-18-hour full-suite estimate mixed admission policies.
Compare remaining parallel work with staging time, spend and the serial finalization tail.

A matching r7i.48xlarge adds 96 physical cores / 192 vCPUs and nominal 1.5 TiB RAM.
AWS Pricing read October 22 gives Linux/shared/us-east-1 compute at $12.7008/hour
extra, $25.4016/hour combined. Extra compute: $76.2048 for 6h or $152.4096 for 12h,
plus EBS/snapshots and less any account discounts. No near-2x guarantee is made.

The Standard regional quota was read as 512 vCPUs; these two boxes need 384.
Other usage and available capacity still need a narrow launch-time check.
Current placement is us-east-1d, subnet-0910ec79d4e5d6017, SSM profile Ssm,
IMDSv2 required. No capacity has been reserved.

## Storage and startup

Current attached volumes are three 2,048-GiB gp3 volumes, all without multi-attach:
vol-0d36715924f03b86c, vol-004b68c077be09cc9, vol-0fbf7bc0991bc8e39.
Never detach or share a live source volume. Before an authorized clone, map exact
mount/device dependencies using bounded metadata and choose only required volumes;
do not automatically duplicate all 6 TiB. Snapshot/stage immutable inputs once,
reuse saved identities, and do not scan/hash databases, reinstall Julia, restore
old archives, re-extract inputs or rebuild the frozen matrix.

Boot a clean SSM-managed OS, not a boot clone that can start copied Search,
trading, collectors or old executors. Mount snapshots/clones as data, establish
the original base/runtime/project paths, reuse frozen bytes, and provide fresh
output/cache paths plus writable depot behavior. Copied in-flight outputs are
not completed receipts. First-read hydration and snapshot time are real overhead.

## Disjoint scheduling

The current executor has no cross-machine ownership protocol; do not simply
launch the existing script on B. Add and test whole-cohort ownership first.
All currently active cohorts stay on A. Assign only wholly unstarted cohorts
to B, balancing remaining heavy fold work rather than raw cohort counts.
These balancing forecasts never become RAM admission limits.

Publish an immutable ownership manifest and retained-result index. A coordinator-only
handoff on A must restrict its future queue BEFORE B dispatches. Preserve every
active PID/start token, wrapper, report, CPU assignment, successful result and failed
attempt. One numerical coordinator per box; no task overlap; their union covers
all 63 declared cohorts and all training-derived model groups.

Keep 96 physical-core slots per box, single numerical threads, unlimited job
memory and live MemAvailable admission with the 64 GiB host floor. No changes to
targets, seeds, epochs, algorithms, rounding, preprocessing membership, exact
as-of clocks/cursors, missingness, ages, scopes, provenance or censoring.

## Completion and rollback

After every mandatory task finishes, gather namespaced receipt-committed outputs
and states. Check unique task/model/sample coverage once, merge once, and run
PCA-12, k-means 3/5 and the original postprocessors once. Preserve contrary,
unfavorable and inconclusive evidence. V3 remains frozen; NOT_PASSED remains;
no independent extra market day or established tradable signal is claimed.

If B cannot start, A keeps running. Reassign only demonstrably unstarted work.
Never replay a shard blindly, restart A, or kill numerical fits for rollback.

Ordered acceptance criteria and dependencies are in second-box-todo.md.
Open facts: refreshed ETA, precise clone volume/layout and storage costs,
available capacity/quota headroom, task weights and measured staging overhead.

