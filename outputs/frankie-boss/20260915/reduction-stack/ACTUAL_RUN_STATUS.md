# Actual journal run and progress units

[Actual combined journal run 34962256086](https://github.com/DavisAI1974/Markets/actions/runs/34962256086) was launched from commit 549efa7376438320ede848483d7e5dd1035177ed. The new conversion/CPU affinity integration check passed once. The exact already-uploaded snapshot is being received; no local source or old GitHub job was restarted.

The logical evidence denominator is 114,054 original INPUT/APPLIED entries from 57,027 source records. It is an integrity denominator, not the new physical row count. The running format stores consecutive groups of at most 16 logical entries in 7,129 compressed SQLite blocks. Exact repeated orders are shared inside each block. The physical byte reduction is reported by raw_body_bytes versus compressed_block_bytes.

For the active run, interpret the existing entries probe as logical_entries_verified. Completed compressed blocks are ceil(entries / 16); block progress is 100 * ceil(entries / 16) / 7129. The final block contains six original entries. This is block packaging plus exact order sharing, not removal of source evidence. A percentage of 100 for traversal is followed by terminal conformance and physical-identity checks before status=verified.

The probe label improvement committed after launch applies to subsequent executions only. The running job is preserved at its original exact commit. No rerun or second actual job is requested.

CPU policy: one affinity-bound parent for ordered causal conformance; every other CPU exposed to the hosted runner assigned to an affinity-bound worker. The queue contains at most twice the worker count in-flight blocks. Probe also reports queue age, record rate, flush latency, worker CPU time, original bytes and compressed bytes. These metrics do not by themselves establish sustained real-time readiness.

The model-input stacked_v1 reduction remains configured in the separately frozen Sunday host. The journal workflow does no model inference. Complete journal result files are archived into authenticated encrypted parts committed back to Markets; original local worktree, evidence, retained Pod, and run34958705448 remain preserved.

The owner now requires all new work to go directly to GitHub, without further C/E files. Eight new code/test files, the benchmark report, both exact synthetic databases, and supporting reports were already published in commit7ebf5e9. The newly created checkout was removed from C. The previously authorized npm cache cleanup had already completed when the owner narrowed cleanup scope; it freed1,622,643,291 bytes, after which no further cleanup was performed. C free space was approximately5.05GB.
