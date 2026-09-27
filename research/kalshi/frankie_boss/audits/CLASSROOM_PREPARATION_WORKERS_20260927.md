# Classroom preparation workers — 2026-09-27

## Implemented source

The user authorized preparing classroom optimizations before its actual Monday run and requested the same helper count and designated CPUs as ROOT. Classroom now has one coordinator on physical CPU1 and fourteen session-lived preparation helper threads on physical CPUs2–15 on the observed box topology. CPU0 remains reserved for I/O. Linux physical-package/core IDs and every native-thread affinity are read back at actual initialization; fewer than sixteen available physical cores refuses initialization. Original coordinator affinity is restored when the session ends.

Only independent source preparation is dispatched. Up to28 tasks are pending and results are joined in original submission order. Model calls, teacher dependencies, component interpretations, grading and correction order retain their existing lanes. These are CPU helpers, not additional GPU inference workers.

The helpers share immutable source bytes within one process. No process pickle or extra shared-memory copy is needed for this classroom path. Source inventories retain per-source SHA256 and exact canonical index lines; task snapshots share immutable bytes and extend ordered indexes only as completed evidence arrives. Replacing a source invalidates its cached index. Source content, exact byte-range retrieval, canonical encoding, request identities and acknowledgements retain the original semantics.

One pinned tokenizer is reused per preparation thread. A file identity/size/mtime/ctime stamp detects changes; a changed file is reread and checked against the existing pin before a tokenizer is constructed from those very bytes. Existing token counting, UTF-8 boundaries, context budget and fallback formula are unchanged. Independent source plans retain their original per-source chunking and are joined before the existing model-call fan-out.

The new helper file is included in classroom cache code witnesses. Source arrays, reading assessments and completed exchanges continue to be appended at the same causal points. No historical section, slot, producer, scientific formula or output budget was removed.

## Actual checks and deployment state

- [x] Static review of the eight changed Python files: ordered joining, per-thread tokenizer state, exact canonical source index encoding, bounded dispatch, cleanup, CPU affinity readback and cache code binding.
- [x] Python3.13 syntax compilation in memory of the exact eight files at candidate4542c96813dcbbb453a7b2313e8357ad295b324f. No imported calculators, scientific tests, canaries, comparison runs or model calls.
- [ ] Inactive immutable checkout staged on the box.
- [ ] Actual classroom initialization receipt at SESSION/work/classroom-preparation-workers.json, including native thread IDs, CPU/core assignments and prepared item counts.
- [ ] Actual classroom throughput and model receipts. No classroom speedup is established yet.

Stage through the existing inactive staging workflow only. Its serial box-run lock may queue behind canonical ROOT; do not pause ROOT or bypass the lock to stage classroom. Start the actual Monday host/principal/classroom sequence only after complete calculation/input receipts. No ROOT checkpoint transition is necessary for these downstream changes because its immutable interpreter is untouched.

## Current ROOT and Granite

Read-only progress workflow36311053493 observed1,440,016/2,032,203records (70.86%), failed=0, PID56833 alive at1790503138.6401565. Three checkpoints saved/read_verified, latestcheckpoint-000002.json. ROOT remains on runtime293113435a8fdf7bd5566f2652e1a1f7a1734c35 and workflow36309059667, unchanged.

Runpod live read at approximately09:59Z reports replacementPod fhiwwlouzyx6l2 RUNNING, NVIDIA L40S, cost1.09/hour. This is a Pod-state read, not a fresh authenticated service-health result. Existing authenticated health/startup evidence remains workflow36304223443; operational migration and priming configuration are already adopted.

Granite's retained five-lesson capsule is available now. Sending it with the first actual Monday stacked_v2 request follows the authorized single-run sequence; it is request context, not persistent model training from a file upload. The existing code verifies historical provenance, projects model-visible helpful lessons and checks the real response knowledge acknowledgement. Actual Monday configuration, prime delivery/acknowledgement, classroom, grades/corrections and retention remain pending. No additional watcher, Pod, priming inference or pinned-bootstrap change was made.

## Remaining evidence

After calculation completion, use one immutable downstream source ref and its matching staged CODE_ROOT for inputs/configuration and the existing manual sequence. Obtain the actual knowledge hash, request/delivery witness and response acknowledgement from that sequence; configuration is not acknowledgement or learning. The GPU service is ready by retained evidence, but no further GPU tuning gain is claimed before measuring the actual workload.

## Inactive staging queued — 2026-09-27 10:01Z

- [x] Reviewed source atomically pushed in a80990d42161c3020c21363137439da7dd6ba527.
- [x] Immutable downstream ref codex/frankie-classroom-runtime-a80990d created at that exact commit.
- [x] One existing staging workflow dispatched: https://github.com/DavisAI1974/Markets/actions/runs/36311196131, ACTION=stage. Observed status=pending at10:01Z, behind ROOT workflow36309059667 on the existing serial lock.
- [ ] Staging success, source-pack witness and CODE_ROOT receipt. Do not dispatch another staging run or pause ROOT for this queue.

The source package includes the already-adopted Granite Pod bindings and retained five-lesson priming configuration. No classroom worker or Granite inference has started from this package.
