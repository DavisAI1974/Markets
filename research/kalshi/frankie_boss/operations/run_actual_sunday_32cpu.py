"""Launch the actual Sunday host under the explicit 32-vCPU Frankie policy.

Use this entry point for a NEW or explicitly migrated runtime identity. Do not point it
at a retained BossTrainingCheckpoint created under a different torch thread count; the
checkpoint binding is intentionally supposed to reject that silent change.
"""
from research.kalshi.frankie_boss.cpu_runtime import CpuRuntimePolicy, configure_cpu_runtime


def main():
    configure_cpu_runtime(CpuRuntimePolicy(
        workers=32,
        torch_intraop_threads=32,
        torch_interop_threads=1,
        worker_internal_threads=1,
    ))
    from research.kalshi.frankie_boss.operations.run_actual_sunday import main as actual_main
    return actual_main()


if __name__ == "__main__":
    raise SystemExit(main())
