# Pod journal boundary and included CPU capacity

Recorded 2026-09-15 from live retained-Pod metadata and frozen code 35982ac7d42b546446038866299c23ca4fc50edc.

## Current actual Sunday data path

The host reads verified source prefixes and prepares the critic request using stacked_v1. Only the admitted JSON model request is sent through jobs_v1 to the Pod. The full market source.sqlite is not sent to, opened by, or interpreted by the current Pod bootstrap. The Pod's jobs.sqlite is a separate durable request/response ledger; it is not the 114,054-entry source journal.

Relevant source:
- operations/run_actual_sunday.py: install_prefix/verified reader, prepared_input, admit_preparation, critic transport.
- granite_runpod_service.py: critique_stacked and exact admitted request transport.
- granite_open_ended_service.py: prompt serialization.
- granite_runpod_jobs.py: durable model jobs and GET-first recovery.
- bootstrap-jobs-final-v3 contains the eight already-reviewed service/bootstrap files; no source-journal reader is part of that bootstrap.

The lossless source-storage and verified-reader reductions therefore run upstream of the current Pod. The model receives the separately reduced stacked_v1 context. Do not decompress the source journal into a model prompt or multiply storage and token ratios.

If journal processing moves onto the Pod, use the same compact format and exact reconstruction checks, bounded ordered workers, single semantic finalization pass, and percentage/backlog probes. Do not introduce a second raw-journal ingestion path.

## Included resources, no capacity purchase

The live Runpod get_pod response for retained Pod jvs75m56w8f73q reports:
- status: EXITED
- GPU: 1 x NVIDIA L40S
- included vCPU count: 32
- reported running compute cost: $1.09/hour

Using CPUs already allocated to this same Pod does not require a larger Pod. The frozen bootstrap contains no application CPU affinity restriction; operating-system allocation at actual start remains authoritative. GPU tensor/data/pipeline parallel settings of 1 are GPU execution topology and do not mean only one CPU is available.

For simultaneous future data work, reserve CPU capacity for the model service and ordered producer before assigning the remaining included CPUs to bounded data workers. Observe actual CPU quotas/affinity and lag before claiming a worker-count speedup. No extra CPU Pod, resize, replacement, Pod start, or price increase was performed for this inspection.

The current GitHub journal job uses its included four CPUs: one ordered parent and three dedicated data workers. Its running worker allocation is unchanged; do not restart completed or advancing journal work to change CPU count.

Pricing reference: https://docs.runpod.io/pods/pricing

## Ownership update

At the user's explicit request, older independent verification run 34958705448 was cancelled and GitHub confirmed completed/cancelled. Combined journal run 34962256086 remains the active migration/conformance execution. Original source completion and retained evidence remain intact. Final Sunday schedule/prefix audit and the actual nineteen-cycle model run remain outstanding.
