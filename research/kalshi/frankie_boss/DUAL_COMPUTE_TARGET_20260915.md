# Dual-compute target — GitHub 16 CPU + retained RunPod 32 vCPU/L40S

Owner correction, 2026-09-15: this is not an either/or choice.

## Native Frankie/BOSS — GitHub 16 CPU

Run native Frankie/BOSS orchestration and the single causally ordered PyTorch training writer on the GitHub 16-core larger runner.

- 16 verified-journal workers where safe and lossless.
- 16 PyTorch intra-op threads for native CPU math.
- 1 PyTorch inter-op thread.
- 1 nested/internal thread inside each verification worker.
- Preserve model/loss/order/planes/inputs/Memory A and checkpoint semantics.
- New cycle-00 benchmark gets a NEW run identity; original failed cycle 0 is immutable evidence.

## Granite — retained RunPod 32 vCPU + L40S

Keep the retained RunPod as Granite's model-serving host and use its included 32 vCPUs for CPU work owned by the Granite/service boundary.

Safe current responsibilities include:

- Granite service process and durable jobs transport.
- Request parsing/serialization and response handling.
- Tokenizer/model-serving CPU support already owned by the Pod runtime.
- Any Granite-specific preprocessing that can be moved there without changing the native Frankie evidence or optimizer authority.

Potential next optimization, subject to Claude review: move Granite-bound context/request preprocessing and tokenizer admission onto the retained Pod so its 32 vCPUs absorb that work. If journal-derived data is moved to the Pod, use the same exact lossless format, verified reader semantics, bounded workers, causal cutoffs and receipts. No source row/field may be dropped, averaged, normalized, or retained-but-uncounted.

## Do not do

- Do not split one native optimizer step across GitHub and RunPod.
- Do not create concurrent writers to the same Frankie checkpoint/model state.
- Do not infer that 16 + 32 means one 48-thread PyTorch process.
- Do not move ownership of Memory A, native forecast state, or training checkpoints onto Granite.
- Do not restart or resize the retained Pod merely to obtain CPU; its 32 vCPUs are already included.

The machines may work concurrently on different owned phases. Aggregate available CPU capacity is 48 logical CPUs across two hosts, but each host has a distinct authority boundary.
