# Worker transport activation and remaining refinement — 2026-09-27

## Verified activation
- [x] Runtime 68f2311e3071f24fd63b65134b81861b3246400f resumed the one canonical calculation via workflow 36305497169.
- [x] Restored checkpoint cursor 917118; full descriptor read 36306746820 confirms identical legacy/lifecycle/member prefix hashes. Worker startup read 36306608858: 15 processes on CPUs 1–15, auxiliary/evidence V2 policies with exact V1 predecessor lineage. Runtime worker receipt 4002 bytes, SHA256 7e2fcb27ba243d2b65f23318b91c57dca62f2b6a2a3d9a20cc7ba3b0e038a74b.
- [x] First post-activation complete-state descriptor read 36307135617 at 989940 records. Descriptor 10487 bytes SHA256 6489ae5b5d8077c157ac14c5680eee170b169ad413f95b8cc96070c189fe220e; driver 260047663 bytes SHA256 90b0ad37d9f2ad79ee3d85246f36b7f679223466f9055165a842af487b889cd8.
- [x] Latest direct observation 36307200424: at 1790498758.7796805, 1010109/2032203 records (49.71%), failed=0. Same PID56172/token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:52022690.
- [x] Observed interval 924973 at1790497999.9829316 to939411 at1790498120.0344803: 120.265 records/s. This is 1.858 times the earlier 64.74 interval, not a controlled identical-workload benchmark or completion guarantee.

## Remaining measured costs
Existing normal-run profile 36306860732, summarized in36306968197 and36306996610; no second calculation or scientific test.
Profile receipt work/performance/profile-1790498370913806361/profile-receipt.json, 151855 bytes, SHA2569a3797fe0f85f879a3383c907c6eb95ff4f188de40559b40c87447c17019fa36.
15 processes used75.54 CPU-seconds in30seconds; ROOT25.29, census11.15, encoders9.45/9.50, each book worker1.55–1.92.
ROOT sampled active Python leaves: largest dump frame24.07%, auxiliary receive/decode14.52%, connection recv9.21%.
Pooled dump caller attribution: evidence11.78%, census10.87%, book send0.66%; incomplete nonblocking stacks limit interpretation.
More workers alone are not established as the next gain. Combine elimination of repeated member-row freezing with lower-copy evidence return transport; inspect book result handling without altering math/aliasing/order.

## Ledger freeze request
User asks to freeze the ledger number/prefix to avoid rebuilding200+GB, or use workers where copying is necessary.
Filesystem observation36307200424 is ext4 on /dev/nvme0n1p1, mounted /. No copy-on-write reflink shortcut on this filesystem.
Current checkpoints already freeze byte counts and SHA256; resume still copies and re-hashes all prefixes.
Planned, NOT implemented: immutable prefix segments plus a fresh append segment, ordered hash verification at restore without rewriting the prefix, and independent materialization workers to produce the exact regular final ledger expected by existing readers. Retain every old file and tail. Full SHA256 still requires ordered bytes; independent chunk hashes are not a replacement.

- [ ] Implement/review combined refinement. No next runtime transition dispatched.
- [ ] Fresh verified checkpoint, compatible runtime/transport lineage and measured normal continuation required for any next transition.
- [ ] Granite actual priming delivery and acknowledgement. Configuration binding is in f4569cb578af02a79990d660221db352f3ffd793 only.
- [ ] Complete Monday calculations, manual downstream configuration/host/Granite/principal/classroom/grading/correction/retention. Tuesday outcomes pending. Orchestrator PLAN ONLY.
