# November 8 discovery execution

The current three RunPod jobs cover October 2, 3, and 17. Let their existing
inline ingest processes finish. Their waiting shells hand the same jobs to
the updated day runner under the same per-date locks. The producer pass ends
with ROOT and Native, then the existing standalone touch and print export
starts for that date. The teacher and rich second-set pass are out of today's
scope. October 18's historical teacher evidence stays available for research.

Use the produced tables directly. The day runner no longer opens the separate
producer and teacher completion files to audit the handoff. ROOT reuses
ingest's journal witness while its file claim holds. Native seals the fresh
discovery ledgers from closed-writer counts and digests, eliminating a
separate scan of those tables. The pinned executables still use their internal
source, recovery, and completion metadata. The existing ingest, ROOT, and
Native input contracts keep that metadata until their readers are changed.

Fresh ingests launched with the updated runner use deferred conformance.
The runner does not schedule a second conformance job. ROOT still reads its
input records for calculation. Starting both producers while ingest is
writing is a separate change. See the [streaming work](streaming-replay.md).

The RunPod checkout is `6f9178bbb97721c7a71e94bb602ac256db348c87`.
It applies the [producer change](https://github.com/DavisAI1974/Markets/commit/e6db1cb2a3eff9445c31d821455038cf05716d34)
to the previous manifest-bound runtime
`c42a32d776f251985edacad2ddda42a53251099d`.
Use the [discovery and paper-test log](../october-discovery-log.md) for
observations, candidate disposition, and later simulator rules.
