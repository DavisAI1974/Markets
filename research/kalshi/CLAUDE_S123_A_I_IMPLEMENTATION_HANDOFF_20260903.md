# Claude handoff — S123 Tasks A–I and legacy repairs

> **S124 correction before any run:** The 44 findings in the historical A_CLEAN artifact are now
> also present unchanged in Frankie's A_MEMORY seed and served as `VERIFIED`. Original ids, content,
> dates and source provenance are preserved; the normal exemplar admission path for future findings
> is unchanged. Future admitted findings enter as `NEW`, meaning recent rather than uncertain. This
> supersedes the exclusion conclusion in “Task I: actual memory-loop contract” and the later
> UNVERIFIED→VERIFIED sentence. The regenerated build-time knowledge block is 128,418 bytes; the
> 15,999-byte number below is the earlier pre-correction fixture measurement. Nothing was dispatched.

Date: 2026-09-03

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Implementation tip before this handoff commit: `58e3e6c3abb2f7a5a8e4956d3b9f3b5711e2ea80`

## Read this first

Tasks A through I are implemented, tested, committed, and pushed. No workflow,
canary, benchmark, Frankie session, feed run, or other run was dispatched. D89
still controls ordering: the run remains last and requires Greg's authorization.
The D61 adapter was preserved byte-for-byte.

The current implementation includes two corrections found after the original A–F
packet: the A_MEMORY checkpoint token fix (H), and rendering the exact gated
knowledge receipt into Frankie's spawn prompt (G). It also implements the
automatic day-over-day findings memory loop (I). The old four-helper October
launch was retired, not deleted; do not recreate its helper topology.

## Tasks A–I

| Task | Commit | What and why | Main files |
|---|---|---|---|
| A | `b7533c57205c1aa8f69bf09ba9d1a667a66bd93d` | Made `emit()` obtain every input receipt, compute the live crosswalk, and call `gate_applicable_inputs` before prompt emission. Refusal preserves all offenders and totals are computed rather than asserted. | `emit_frankie_spawn.py`, `tests/test_emit_frankie_spawn.py`, `tests/test_emit_spawn_gate_s123.py` |
| B | `1ef643a458a5864f1d6da47ff3f59bb56818d336` | Replaced hand-set `DELIVERED` fixtures with an honest producer-built partial fixture. Withholding the computed knowledge receipt now proves refusal. | `tests/test_native_layer_crosswalk.py` |
| C | `441457e0fb2ee42343063be6e3a41dd6777398ac` | Wired `native_staging.KNOWLEDGE_USE_GATE` through an adapter to `validate_staged_knowledge_use`, using the exact receipt, exact model-visible bundle, serialized principal input, and canonical read-back names. Missing or placeholder arguments refuse. | `native_staging.py`, `tests/test_native_staging.py` |
| D | `52bc9bee2679016450e3fdd591d656ca4952b1d9` plus index follow-up `fc314dc952d9b34001d4a8f3703144a2966284d7` | Stamped four frozen F-35 records without rewriting their historical content, registered the stamps, and added a regression test. | four frozen crosswalk/feed Markdown records, `tests/test_s123_frozen_document_stamps.py`, `store/documents.json`, `KALSHI_TRADING.md` |
| E | `574a902b79ef3c9cc539fd151200f585de622619` | Changed bounded scans to say `ABSENT_FROM_SCANNED_PREFIX` with rows/bytes. Only EOF scans may make an unqualified absence claim. | `native_layer_crosswalk.py`, `tests/test_native_layer_crosswalk.py`, `tests/test_native_layer_crosswalk_s122_item4_d.py` |
| F | `722cf6d62a7ca03a94a264c678d42aef2ee0ce88` | Declared the one-day A_MEMORY subject/proof equality as a degenerate self-proof bootstrap instead of manufacturing a receipt. It clears automatically when a distinct receipt exists. This is a one-day bootstrap declaration, not independent evidence; later roster days provide distinct evidence. | `native_layer_crosswalk.py`, `tests/test_knowledge_delivery_receipt.py`, `tests/test_native_layer_crosswalk.py` |
| H | `b896c3f36400ea06ac3fe94a25b41b29bbfba934` | Reproduced the bounded A_MEMORY checkpoint failure, kept the checkpoint contract authoritative, and corrected the writer from `MEMORY` to canonical `MEMORY_ASSISTED`. Unknown modes still raise `CheckpointError`. The arm ID `A_MEMORY` remains a separate vocabulary. | `native_a_arm_launch.py`, `tests/test_native_a_arm_launch.py` |
| G | `58e3e6c3abb2f7a5a8e4956d3b9f3b5711e2ea80` | Rendered knowledge into the spawn prompt from the exact already-loaded receipt object used by gating. This prevents a gated-but-knowledge-blind spawn and keeps emitter schema-free under D82. | `emit_frankie_spawn.py`, `tests/test_emit_frankie_spawn.py`, `tests/test_emit_spawn_gate_s123.py` |
| I | `34331e656a930aa83512de059cf1e963966f6394` | Added the automatic admitted-findings carry: a committed daily findings artifact triggers the ordered rebuild and a direct no-human commit/push; only new stable IDs enter memory; empty days add no memory; vetoes persist but are never served. | `.github/workflows/a_memory_findings_carry_20260903.yml`, `build_a_memory_seed.py`, `native_calculation_runner.py`, `native_knowledge_delivery.py`, `native_staging.py`, `render_frankie_report.py`, `emit_frankie_spawn.py`, `tests/test_a_memory_findings_loop.py` and focused tests |

Task A's documentation indexing needed two bookkeeping commits: `c00b46e`
first indexed the new test but accidentally collapsed the generated Python index;
`6644d5d` immediately restored the complete index. The final tree is correct.

## Frankie spawn lookup contract — new

This is now an explicit runtime contract, not just an implementation detail:

1. `emit()` resolves the live result identity and every receipt/proof by lookup.
2. It computes the crosswalk and runs the applicable-input gate before rendering.
3. The knowledge renderer receives the exact same already-loaded receipt object
   that the gate inspected—no reload and no second disk read.
4. The emitted prompt contains that renderer's exact block.
5. `emit_frankie_spawn.py` does not restate the knowledge receipt schema, section
   headings, counts, or bytes; those remain owned by the renderer module (D82).

The tests assert object binding, exact rendered inclusion, and continued refusal
when the receipt is absent. The honest fixture prompt grew from 13,092 bytes to
15,999 bytes: +2,907 bytes, or +22.2%. Future served findings are roster-bounded.

## Task C/G coupling result

Before G, the Task C gate passed because staging separately serialized both the
spawn prompt and the exact `KNOWLEDGE_BUNDLE.md`. It was not vacuous: the prompt
alone refused with `serialized principal input lacks exact model-visible context`.
Thus C correctly bound the bundle, while G was still required to put the
receipt-rendered inventory, instructions, and future served findings directly in
Frankie's emitted prompt.

## Task I: actual memory-loop contract

The original premise needed correction before implementation:

- The seed builder was hard-coded to run `33605852433`; it did not yet discover
  all principal runs by rule.
- Its direct file scan bypassed `attach_principal_findings`, and it treated whole
  artifacts rather than finding IDs as the carry unit.
- The historical 44-finding artifact lacks the current admission path's required
  exemplars and has run-local-looking IDs (`F-01`, etc.). It is preserved as the
  historical A_CLEAN day-one artifact; it was not silently admitted to the new
  A_MEMORY loop.

The implemented loop now:

- discovers A_MEMORY findings artifacts under `principal_runs/`;
- derives allowed source days and the bound from
  `raw_mbo_source_manifest.EXPECTED_ROSTER` rather than typing `4`;
- excludes the historical A_CLEAN artifact and refuses unknown arms/days;
- sends every candidate through the shared
  `NativeCalculationRun.admit_principal_findings` admission path;
- requires stable persistent finding IDs and current exemplars/falsifier/
  attribution fields;
- deduplicates exact repeated IDs, but refuses an ID reused with changed content;
- treats `findings: []` as a valid completed day and records compact
  `PRESENT_EMPTY` status while adding no empty finding to memory;
- distinguishes that from a run that never wrote an artifact (`MISSING`);
- stores vetoes by ID in a committed file, keeps the finding present with
  `served: false`, never renders it, and refuses a veto for an unknown ID;
- performs the ordered rebuild
  `build_a_memory_seed -> register_a_memory_knowledge ->`
  `rebind_registry_knowledge_layers -> refresh_native_frankie_knowledge`;
- commits and pushes generated promotion files directly, with no review PR;
- avoids a retrigger loop because promotion outputs are not workflow trigger paths;
- adds a `Day-over-day memory carry` section to the existing post-run report.

Only stream evidence may move a finding from `UNVERIFIED` to `VERIFIED`; prose
quality cannot. No finding is required on a day, so the design creates no pressure
to invent one. Empty findings JSON files do not fill memory; they remain only as
honest run receipts.

External first-link limitation to report, not conceal: GitHub Actions cannot make
an uncommitted ChatGPT Work artifact appear in the repository. The principal's
existing contract to produce one committed findings artifact is the source-tree
link; the automatic carry starts when that commit arrives. The loop cannot verify
that external commit action itself. No live A_MEMORY findings were ingested in
this work, so there was no evidence-based finding to veto and none was guessed.

## H and the run that did not happen

The bounded local reproduction proved that the previously proposed canary would
have failed at checkpoint on H had it been dispatched. Correcting the writer made
the same bounded path reach checkpoint, while an unknown mode still refuses by
name. A sweep of other launcher checkpoint tokens found no additional contract
mismatch. No actual canary or workflow was launched.

## Retired four-helper launch and seven old failure classes

Commit `5fbb071a0015b49666b7f024762a35f5349072c1` retires rather than deletes
`.github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml`.
It has no push trigger and all three jobs are guarded false, retaining the record
without permitting launch. RT and Forecaster continue to call only the already
selected single skill; the four-helper topology was not rebuilt.

That commit fixed the seven stale failure classes exposed by the current tree:

1. Retirement tests now require no push trigger, every job disabled, and marker
   fields `launch_authorized: false` and `stop_requested: true`.
2. The canonical runner assertion follows `"$venv_python"`, not bare `python`.
3. AWS credential assertions scan the build job only and do not falsely match the
   launch job.
4. The requirements-lock parser accepts valid environment markers such as
   `python_version < ...`.
5. The embedded-Python check selects the credential-scope heredoc rather than the
   first unrelated heredoc.
6. Concurrent fixed-worker initial/continuation calls are classified by input
   shape, not fragile odd/even call order; oversized replay may have multiple
   concurrent initials but no continuation and must persist each.
7. The historical recovery lock remains immutable and correctly refuses current
   engine drift instead of being weakened to fit the retired workflow.

## Task B's deliberately unaccounted layers

Without a real run, the honest fixture cannot account for:

- native DBN decoding witness;
- S3 object identity;
- the workflow's `PLAIN_SIZES`;
- the workflow's `PLAIN_SHA256SUMS`.

The principal-outputs receipt is post-spawn and absent by design, not an input
gap. These limitations were named rather than filled with fabricated receipts.

## Verification evidence

- Baseline at exact `a37fc25`, output redirected and exit code read:
  `1983 passed, 14 warnings, 6387 subtests passed in 83.78s`.
- Task I full suite: `1995 passed, 14 warnings, 6389 subtests passed in 80.64s`.
- Task G focused combined suite: `87 passed, 18 subtests`.
- Final code full suite: `1997 passed, 14 warnings, 6389 subtests passed in 92.35s`.
- Store check: four checks passed.
- Documentation index check: passed after deterministic regeneration.
- D61 lock: `LOCKED_OK`; SHA-256 remains
  `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`.
- YAML parse, `py_compile`, and diff checks passed.
- No transient files remain outside ignored `data/`.

## Review boundary

Claude should review this branch and report disagreements. Do not dispatch any
workflow or run until Greg explicitly authorizes it. Do not rewrite the frozen
records, weaken refusal gates, manufacture receipts, reintroduce the retired
helpers, or modify D61.
