"""Launch the actual Sunday host under the explicit GitHub 16-vCPU Frankie policy.

Use only for a NEW run identity or an explicitly migrated checkpoint identity. The
launcher fails closed unless the host exposes at least 16 logical CPUs. It changes only
execution parallelism: evidence, inputs, model structure, loss, causal ordering and
optimizer semantics remain unchanged.
"""
from research.kalshi.frankie_boss.cpu_runtime import CpuRuntimePolicy, configure_cpu_runtime


def main():
    configure_cpu_runtime(CpuRuntimePolicy(
        workers=16,
        torch_intraop_threads=16,
        torch_interop_threads=1,
        worker_internal_threads=1,
    ))
    from research.kalshi.frankie_boss.operations.run_actual_sunday import main as actual_main
    return actual_main()


if __name__ == "__main__":
    raise SystemExit(main())
