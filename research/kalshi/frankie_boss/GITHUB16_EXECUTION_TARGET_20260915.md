# GitHub 16-vCPU execution target — owner correction

Greg corrected the execution target on 2026-09-15: native Frankie/BOSS should be run from GitHub Actions using the available 16-CPU larger runner, not treated as a 32-CPU Windows-host workload and not tied to the retained RunPod CPU count.

Standing rule for the corrected path:

- RunPod remains the Granite service host.
- Native Frankie/BOSS orchestration and CPU training move to GitHub Actions.
- GitHub runner target: 16 logical CPUs.
- Verified journal validation: up to 16 bounded workers, deterministic ordered parent verification, one internal thread per worker.
- Native PyTorch training: one causally ordered model/optimizer writer, up to 16 intra-op threads, one inter-op thread.
- Preserve every input, calculation, plane, adapter, Memory A artifact, causal cutoff, raw record, hash chain and scientific result semantics.
- Preserve the original failed cycle-00 run unchanged.
- The corrected cycle-00 benchmark is a new run identity from the beginning; never overwrite the old cycle-00 evidence.

Do not infer GitHub runner capacity from RunPod. The workflow must target an actual 16-core GitHub larger-runner label/group and must verify `os.cpu_count() >= 16` at runtime before creating a new checkpoint.
