# Session record 2026-09-16: host restore proven, benchmark measured, compact journal made authoritative, Oct 4-6 block brought in

Branch `ccode/frankie-lawful-recovery-review-20260915`, from `e3864daf` to the tip named in the
drop-in. Everything below is measured on the native host `i-0e90ee6110ef609aa` (r7i.4xlarge,
16 vCPU, 126 GB) unless it says workstation. No Frankie, Granite, Pod or result-bearing cycle ran.

## 1. The restore is real: byte-exact, and it took four attempts to make it so

`E:\Codex\RESTORE_RECEIPT_20260916.json`: bulk 27/27 hash-complete, working tree 161/161 byte-exact
at `050c5056`, git-clean. The set moved at about 84 MB/s inside the region (11.7 GB journal in 140 s;
all 27 bulk objects and six archives in 324 s). Each failure was a distinct defect, each now has a
test or a tool:

| attempt | failed on | cause | fix |
|---|---|---|---|
| 1 | first download, HTTP 403 after a 307 | presigned links signed for the global S3 endpoint; the regional redirect breaks the signed host | `presign_restore_set.py` signs against `s3.us-east-2` and fetches the manifest through its own link, no redirects, before writing the runner |
| 2 | first in-git package file | autocrlf checkout had rewritten 17 of 170 package files to CRLF; 4 others were committed LF against a manifest pinning CRLF bytes. No checkout mode reproduced all 170 | whole package `-text`; the four blobs renormalized to manifest bytes; restore reads package bytes from `git show HEAD:path`; `test_sunday_package_blobs_match_manifest.py` |
| 3 | audit step, `ModuleNotFoundError: torch` | audit modules imported through the package `__init__`, which imports torch; the stock host Python has none by design | both stdlib modules loaded by file path; `test_restore_on_host_needs_no_torch.py` blocks torch and the package and loads them |
| 4 (top-up) | `.git/index` "differs after extraction" | git rewrote the index in place at the same size when the host ran `git diff`; the archive step skipped on size alone | skip only on matching hash |
| proof run | missing 729-byte file | the second lineage link's recovery receipt was read by every host and listed in no manifest | `audit_sunday_referenced_files.py` (walks configuration, lineage, prefix manifest, witnesses; 104 referenced, 102 covered, 2 declared absent, 0 uncovered) and `RESTORATION_MANIFEST_ADDENDUM_20260916.json`; restore and blob test read addenda |

Also found: the restored venv has `include-system-site-packages = true` and on the workstation
torch 2.9.1+cpu and numpy 2.3.5 live in the USER site (AppData\Roaming), so the venv archive never
held them and the workstation's "3.13.7 2.9.1+cpu 2.3.5" answer came from there.
`deploy/aws/frankie_host_python_packages.ps1` installs the exact pins into `C:\Python313`; the host
venv now answers `3.13.7 2.9.1+cpu 2.3.5`. The receiver checkout is a git worktree whose parent
repository is not in the set (`RECEIVER_HEAD` empty); not needed by the benchmark, needed by the
principal path, not fixed.

## 2. The compact journal is authoritative; the raw journals never need to be on a host again

`compact_source.CompactSource`: the sealed 570 MB container pinned physically (sha256, bytes from the
host configuration) and logically (seal == ingestion completion), block table verified as one chain
to the seal at open, `digest_at(ordinal)` by decoding one verified block. `verify_lineage_from_compact`
keeps every lawful closed-lineage check and reads parent tails and rehydration anchors from compact
rows. `operations/run_actual_sunday_compact_source.host_class(actual)` subclasses the caller's own
`ActualHost`, overriding `source_lineage()` and `prefix()` (prefix is the lawful text with one raw
read replaced; a drift-guard test holds it there). Lawful `run_actual_sunday.py` untouched.

Proof on the real data with `source.sqlite` renamed away for the duration:

| | |
|---|---|
| `source()` with lineage verification | 1.8 s (lawful path: hash a 4.4 GB parent that the restore set does not even carry) |
| `prefix()` for all 19 cycles | 10.8 s |
| compact blocks decoded for the whole proof | 23 of 7,095 |
| raw journal present | no; restored afterwards, verified present |

Tests: 6 on synthetic journals (tampered block with and without matching sha column, wrong seal,
wrong physical pin, wrong size, broken chain, wrong parent tail, rewritten child, wrong first-link
witness, out-of-range parent), 4 on the subclass.

## 3. Benchmark: memory-bound, thread-count is a numeric identity, not a speed knob

Direct learner harness through the compact-source host, fresh checkpoint each, scratch clones,
cycle 0's retained feedback, on the restored Sunday tree at `050c5056`:

| substage | 8 threads | 16 threads |
|---|---|---|
| identity stack (source, prefix, fresh checkpoint, feedback) | 15 s | 8 s |
| `_prepare` | 334 s | 311 s |
| causal scan | 101 s | 93 s |
| forward | 15 s | 17 s |
| loss | 22 s | 22 s |
| backward | 37 s | 41 s |
| total | 525 s | 494 s |
| peak private / pagefile / RSS | 23.8 / 31.8 / 28.5 GB | 24.0 / 32.0 / 28.6 GB |
| result hash | `228cfb4b…` | `d74eacd4…` |

Three conclusions. (a) 16 threads buys 6 percent, all of it in preparation, which is single-threaded
Python either way; the tensor work is about 75 s of 500 and does not scale with threads. (b) The
step needs 32 GB at 3,262 rows; the sheet's 25-30 GB estimate was right and Sunday's 16 GB box could
never have finished it. Linear in rows that is about 40 GB at 4,096; a 64 GB host is the smallest
that fits, 128 GB is comfortable. (c) **The two thread counts produce different results on
identical inputs** (float64 reductions reorder). The retained Sunday run recorded no thread count;
the EC2 wrapper's numeric policy records it. The 19-cycle run must declare one and never change it.
Recommendation: 8, the host's physical core count and its default.

## 4. Where the hour goes, measured

`operations/profile_journal_drain.py` on the host:

| drain | rows | wall | per row |
|---|---|---|---|
| cycle-0 prefix, raw reader, single thread | 6,524 | 27.9 s | 4.27 ms |
| cycle-1 prefix, compact, single thread | 12,108 | 78.2 s | 6.46 ms |
| cycle-1 prefix, compact, 15 workers | 12,108 | 7.7 s | 0.63 ms |

A full 114k-row drain is therefore about 72 s with 15 workers, and each cycle drains its prefix
about five times (`_prepare` twice, the critic causal scan, the learner causal scan, the checkpoint
export), which is the hour over 19 cycles. `SPEC_PREPARED_SOURCE_ONCE_20260916.md` takes that to one
verified-table open plus about 256 tail blocks per cycle; it is a new native identity and is for
the run after Sunday.

## 5. The Oct 4-6 block: sources in, nothing further

Greg's order, in sequence: one more Sunday by itself first; the block's data plane may be brought
in (sources, then ingestion, schedule, prefixes) but nothing that runs it; everything built for the
one day is reused with only the dates changed; three consecutive sessions so cycles that straddle
the 17:00-18:00 ET halt can be seen.

Staged: `frankie/block_20211004_20211006/sources/` on S3, manifest
`blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json` (hash `eb68cb23…`), four members in replay
order, each copied server-side, re-read and verified, decoded for counts and the 21:00Z halt split:

| member | records | before halt | after halt |
|---|---|---|---|
| 20211003 (the Sunday file) | 57,027 | 245 | 56,782 |
| 20211004 | 1,994,358 | 1,975,176 | 19,182 |
| 20211005 | 2,111,930 | 2,085,682 | 26,248 |
| 20211006 | 2,308,160 | 2,278,747 | 29,413 |

6,471,475 records, 113x the Sunday run. Book depth on Monday peaks at 1,353 resting orders against
Sunday's 823, so per-record bodies grow modestly; the count is what scales. Arithmetic from the
Sunday build that the block design must answer before ingestion starts:

- raw journal at Sunday's 205 KB/record: about 2 TB; not viable. The journal stack converted the
  Sunday raw journal at 80 records/s on 3 workers (36 ms CPU per record); the raw ingestion itself
  ran under 2 records/s, which is 41 days for the block. A DBN-to-compact single pass with the
  builder's per-record cost measured first is the build item.
- cycles at Sunday's cadence (one per ~3k records) would be 2,150 for the block; the cadence for a
  weekday is a decision, not a parameter, and it decides the token bill.
- every Sunday literal in the one-day build (`57027`, `19`, `20211003`) is listed by
  `grep -rn '57027\|!=19\|20211003'`: `run_actual_sunday.py`, `build_remaining_sunday_prefixes.py`,
  `verified_sunday_schedule.py`, `sunday_schedule.py`, `sunday_execution.py`,
  `source_contract_runtime.py`, `selected_source_scope.py`, `seal_final_prelaunch_candidate.py`,
  `run_journal_stack.py`, `parallel_source/verify_snapshot.py`. "Only the dates change" means each
  becomes a manifest field.

## 6. Operations

- PR #10 (idle EC2 guard) merged into `claude/kalshi-s79-kickoff-ij8t9o` at `e975a493`.
- `deploy/aws/ec2_host.py status|start|stop|snapshot|snapshots`: start waits for SSM, stop waits for
  stopped, snapshot takes a point-in-time EBS copy of the data volume (`xvdf`, vol-05c3d967e07b2d61f).
  A stopped instance keeps its volumes; only terminate loses them; the idle guard never terminates.
- Host runtime this session about 1.9 h across five boots, roughly $3.50.
- Known, not fixed: `tests/test_benchmark_checkpoint.py::test_checkpoint_core_has_no_torch_dependency`
  fails when run after `test_native_learner_direct_benchmark.py` in one process and passes alone
  (pre-existing order dependence, reproduced without this session's changes).
