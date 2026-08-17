# NG Exhaustion Runway Clock V0 — Large-Batch Proof

Status: PASS. Single deterministic worker is sufficient for V0 at the tested batch size. Permanent Frankie remains untouched.

## Corpus

The batch is the exact frozen blind input artifact, not a reconstructed sample:

- GitHub Actions artifact ID: `9274443976`
- artifact SHA-256: `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`
- blind records: 1711
- Family A: 1616
- Family B: 35
- Family C: 60
- held-out days: 20250717=420, 20250923=446, 20250930=428, 20251001=417
- future price / price-bearing window served: `false`
- blind outcome-wall scan: `PASS`

No post-reveal outcome data is consumed by the benchmark.

## Full-corpus classifier proof

Across all 1616 Family A records:

- A-fast-collapse: 831
- A-persistent: 785
- invalid A windows: 0
- label mismatches against the frozen pre-reveal assignment: 0
- centroid-distance mismatches: 0

This reproduces the frozen 831 / 785 split record-by-record, including the exact stored centroid distances.

## Contract sweep

The harness checks eight elapsed checkpoints per record: `0, 30, 59.999, 60, 300, 900, 1802, 7200` seconds.

- timeline outputs checked: 13688
- pre-60 A pending failures: 0
- confirmed A mismatches: 0
- negative runway failures: 0
- monotonic countdown failures: 0
- future-price-access flags: 0
- A missing-window fail-closed checks: 1616 with 0 failures
- microstructure confidence-only checks: 5133 with 0 cases where seconds changed
- missing event clock fails closed: `true`

The timed sweeps deliberately set microstructure to `unavailable`; no scratch support-to-confidence mapping is promoted into V0.

## Throughput

Environment: Python 3.13.5, 5 logical CPUs reported by the container.

Input/serialization:

- records JSON: 22,104,694 bytes
- parse manifest + records: 411.4 ms

Single process:

- one +60s checkpoint over all 1,711 records: 20.62 ms median (82,994 updates/s)
- eight-checkpoint sweep, 13,688 updates: 121.03 ms median (113,095 updates/s)
- confirmed-A call latency: 11.50 us median, 13.12 us p95, 28.84 us p99

Process pool comparison:

- 2 warm workers: 62.04 ms / 220,620 updates/s
- 4 warm workers: 59.10 ms / 231,607 updates/s
- 2 cold workers: 78.00 ms
- 4 cold workers: 82.94 ms

Parallel compute improves raw batch throughput, but the single-process clock already clears the complete 1,711-record +60 sweep in about 21 ms and the full eight-checkpoint sweep in about 121 ms. JSON parsing alone takes about 411 ms, materially more than the clock computation.

## Worker decision

Do **not** add multiple exhaustion workers now. Use one ordinary deterministic clock worker/service for V0. The measured math is not the bottleneck; input parsing/transport is more expensive in this batch.

If future live instrumentation shows queue backlog or update demand approaching the single-process capacity, a persistent 2-4 process pool is a valid scaling path. That should be a throughput optimization only. Do not create AI exhaustion agents, and do not change the frozen classifier or duration baselines to justify parallelism.

## Boundaries preserved

- classifier retuned: no
- reveal runway baselines retuned: no
- scratch price-curve logic used: no
- microstructure mapping learned/retuned: no
- future price accessed by the clock: no
- permanent Frankie mutated: no
