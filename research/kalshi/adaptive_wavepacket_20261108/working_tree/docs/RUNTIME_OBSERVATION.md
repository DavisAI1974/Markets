# Explicit local runtime observation

This increment finishes the local observer/receipt/inspection path. It does not declare the entire BM-01–BM-12 roadmap finished. See the finalization checklist before release. Billing remains deferred; the final billing increment will use a Stripe stub.

## Collect one bounded Python run

Requires Node 20+ and Python 3.11+. Static mapping remains read-only and never starts the target. Observation is a separate explicit command that **executes the chosen script**, with the project as its working directory. Use small test cases and the appropriate existing Python environment; no target dependency is installed automatically.

Create an Ed25519 collector key, keeping the private file outside mapped projects. The public output and its parent directory must not already conflict with another configuration:

```bash
node src/cli.js --new-collector-key /private/local.pem --collector-public /project/.buildmap/collectors.json --collector-id local
node src/cli.js /project --observe-python main.py --collector-key /private/local.pem --collector-id local --observation-output /project/run.json
```

Optional `--observe-args '["argument"]'`, `--observe-timeout 60000` (milliseconds, 100–3,600,000), and `--python-runtime /path/to/venv/bin/python` select arguments, deadline and interpreter. Default deadline: one minute. The entry must be an inventoried project-relative Python file; the signing key must be outside the project. Output is reserved with exclusive creation **before execution**, so a collision does not launch the target. The target never receives the signing key through its configuration, arguments or environment.

The observer supports normal installed site packages in the chosen isolated interpreter. It adds the project root to the import path and runs the script through `runpy` as `__main__`; this is not a claim of identical launcher/import behavior for every application. Interactive stdin is not forwarded. Collector overhead is included.

## Inspect a receipt

Add its exact project-relative path to the existing analysis document:

```json
{"version":1,"collectedRuns":["run.json"]}
```

Preserve existing product, stage, workload and runtime sections. The scanner reads public trust configuration from `.buildmap/collectors.json`; it does not generate or silently trust keys. Unknown/ambiguous keys, malformed records and signature changes are refused. Source and bounded project-input hashes are checked again when viewing. Stale, partial, failed, source-changing and timed-out records stay visible but cannot justify current reuse comparisons.

**Calculations & risks · Guide** and the piece/mission inspector display verified collector identity, profile entry/exit counts, observed project-filtered call routes, resource metrics, file-open attempts and finite value identities. Nested functions have their own source records. A current source match can navigate to the corresponding declaration. Unsupported/dynamic declarations remain observed but uncatalogued instead of being silently guessed. Recorded observations do not grant free piece/goal completion states.

## Meaning and limits

- Signatures authenticate the configured collector and receipt bytes. This is not hostile-code isolation, result-correctness certification or continuing liveness. The target can affect its own Python process; this is ordinary local observability, not a hardware/remote attestation system.
- Calls are profile entries. Generator/coroutine entries include resumes. Exit events can include exception unwinding; unavailable returns are never treated as equal results. Native internals and subprocesses are outside this collector. Project-filtered ancestry can skip external intervening frames.
- Actual elapsed time, process CPU, normalized CPU, allowed CPU count, observed Python threads and peak process RSS are separate from static estimates. Inclusive function times overlap and must not be summed as whole-run elapsed time. Unavailable platform metrics remain unknown.
- Open events are **attempts**, including failed attempts. They are not successful reads, writes, transferred bytes, cache hits or completed jobs. Outside-project/descriptor attempts are counted as excluded scope, without exposing outside paths.
- Exact built-in arguments/results are digested, not stored raw. Signed zero and floating-point NaN bits remain distinct. Bounded numeric NumPy arrays include dtype, shape, strides and exact bytes. Custom objects, object/structured arrays, oversized values and missing returns remain unknown. No `repr`, pickle, averaging or zero fill is used. Repeated directional input/output identities support review of these finite observations, not general purity or safe caching.
- Source identity is checked before/after the run. Ordinary project-file input reads are hashed before their attempted read and at exit within bounds; input identity is not a proof of complete transitive I/O or race-free capture. Large/unavailable/changing inputs disable comparisons rather than becoming zero/compatible.
- Limits: 10,000 source files, 1 MB/source file, 128 MB source total; 10,000 calculation/route/operation records; 256 value groups per calculation; depth 8 / 1,024 bounded value nodes; 64 KB string/bytes/array values; 1 MB/input file / 4 MB selected input total. Omission/error counts are explicit. Unknown value coverage never becomes an equivalence claim. Receipt output is capped at 16 MB; scanner accepted receipt budget is 32 MB over at most 20 receipts.

## Signed comparisons

Optional `analysis.collectedComparisons` entries name `baselineRunId`, `currentRunId` and an optional `calculation: {path,name}`. Both signatures, complete successful run scope, exact arguments, entry, captured environment and observed project input identities must agree; candidate source/input bindings must be current.

Changed source additionally requires `codeReview: {note,paths,bindings}` naming **every changed source path**, current small receipt bindings and a calculation whose covered finite directional inputs and return identities match. Historical baseline source stays stale for navigation; an explicit current review permits comparison of its authentic historical observations. Missing/unequal/unsupported/nondeterministic values refuse the comparison. Current-minus-baseline metric differences are measured within the stated scope, not a universal speedup or automatic reuse approval.

## Evidence from this increment

Executed tests exercise dynamic/nested calls, directional identities, tamper/key/source/input failures, interruption/timeout preservation, safe output collisions, static-mode non-execution, real three-open-attempt versus one-open-attempt comparison, custom-value refusal, signed zero, bounded NumPy arrays and offline source navigation. Separate recovery tests compare actual resumed calculations and independent/rolling/stateful extensions with full recomputation, including holes, nulls and stale/torn state refusal. Temporary projects, keys, receipts and review artifacts are removed by teardown.

Validation on November 1, 2026: all 167 tests passed on Node 24.22.1 / Python 3.12.14 (NumPy 2.3.5 for optional array coverage). A supported cloud-browser check of a disposable offline export observed the verified collector, current source/input bindings, real resource metrics, three nested calls with repeated directional identities, and navigation to the nested calculation explanation. This was a small integration check; realistic-scale, full accessibility, device/browser and supported-version release checks remain on the finalization checklist. Disposable browser observation material was removed after use. Existing whole-MVP acceptance receipts are not renewed by these tests.
