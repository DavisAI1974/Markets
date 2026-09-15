# Compact journal adoption in Frankie Sunday

The Sunday host now selects a full-evidence compact reader for explicitly identified compact prefix receipts. Existing legacy prefix 00 remains supported. The compact reader uses the faster canonical validator and bounded, ordered processes pinned to available logical CPUs, reserving one CPU for the consumer when possible. A requested budget of 48 is capped to the actual process allocation; it does not purchase or imply 48 CPUs.

The prefix builder accepts an independently pinned compact journal via host_runtime.compact_journal. It copies compressed blocks without rebuilding them, re-encodes only the block crossing a cutoff, and verifies each resulting physical prefix against the original source journal's exact cutoff digest. Original INPUT/APPLIED checks and context seed selection still run. Every original field, including book observations, reaches Frankie. The conformance-only projection is not used.

host_runtime.data_workers selects the requested parallel budget. Existing source, schedule, lineage, native initialization, prepared request, training save points and durable same-job recovery checks remain. Prefix progress and actual reader progress include percent. No inference retry or new source day is introduced.

restore_existing_journal_archive.py restores the already completed Git archive by exact commit and authenticated hashes, using the existing local recipient key. It performs no second journal conversion or source conformance run. New runtime files belong in authorized E staging; the canonical encrypted archive already resides in Git.

Measured evidence remains: full compact journal 569,667,584 bytes versus 11,700,711,424 original snapshot bytes. Reader and storage ratios are not multiplied into an end-to-end prediction. Actual Sunday runtime and sustained real-time readiness are not established by this code change.

Deployment requires the focused new boundary tests, final data/host review, a newly pinned configuration and consistent code/package identities. At publication of this change the actual nineteen-cycle model run has not started.
