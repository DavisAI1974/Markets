# DROP-IN FOR CLAUDE — RUN FRANKIE

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

Start from the remote branch tip carrying this file. Read `CLAUDE.md` and
`research/kalshi/DROP_IN_S124.md` before acting.

## Authorization and state

Greg's instruction is now to run Frankie. The implementation, review, mission correction and
handoff are finished. No workflow, canary, benchmark, Frankie session or feed run was dispatched
while preparing this commit.

The earlier complete S124 pytest result was 2,004 passed, 14 warnings and 6,389 subtests. After the
final D99 input-isolation correction, all 289 tests in the six changed modules pass, and the
store/generation, JSON, compilation, diff and D61 gates pass. This scratch runtime lacked pytest
and databento, so no replacement full pytest result was fabricated; separate unittest discovery
executed 1,988 tests without an assertion failure and had three imports blocked by missing
databento.

Preserve the D61 adapter exactly:
`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`, SHA-256
`4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`.

## What Frankie receives and must do

- A_MEMORY starts with the 44 established `F-01`–`F-44` findings, unchanged and served as
  `VERIFIED`, with their historical A_CLEAN provenance. Future admitted findings are `NEW`, where
  NEW means recent rather than unverified. `VETOED` is retained and unserved.
- Frankie computes every current `### 4.x` calculation-contract section himself from the causal
  stream. The exact 18 identities—4.0, 4.0b and 4.1–4.16—are the protected floor; later headings
  grow the set. Empty lawful populations return `NULL_RESULT`; no section is silently omitted.
- The calculations exist to uncover causal market mechanics, relationships, falsifiers and
  possible signals, including whether non-exhaustion behavior connects to exhaustion. They are
  not ledger-filling math exercises.
- Frankie receives and assesses the complete raw/derived MBO surface for the source day, including
  FIFO, full book and dipole. The retention review covers every current causal registry identity:
  47 raw/non-geometry plus 8 derived-geometry layers, and any later additions.
- Elimination requires exactly zero informational value. Even slight credible present or future
  value means KEEP. The rule applies independently to full book and FIFO as whole surfaces and to
  every constituent field, depth, order identity, queue, queue-position fact and derived component.
  Frankie recommends; Greg alone decides whether anything is removed. `KEEP EVERYTHING` is valid.

## Initial four-day input isolation

Reliable day-aligned October 2021 values are not currently available for weather, storage,
COT/positioning, pipeline/LNG, production/demand, grid/nuclear/solar, STEO, options, cash basis,
macro and equivalent non-MBO context. For the initial four one-day runs these families are
`IGNORE_AS_EVIDENCE`. Do not infer, fabricate, backfill, retrieve or use them in calculations,
findings, causal explanations, hypotheses, falsifiers or elimination recommendations.

Their input identities are preserved for later phases and later source days with reliable aligned
values. This is temporary isolation, not deletion and not a zero-value judgment. Native raw MBO,
lawful raw/derived MBO transformations, the binding mission and calculation contract, and all 44
A_MEMORY seed findings remain in scope. Historical external-input mentions in seed findings are
provenance only, not permission to substitute missing contemporaneous data.

## Run sequence — do not combine source days

1. Run the bounded A_MEMORY canary using the workflow's single Sunday source object default. It is
   reduced-MBO slice evidence only and cannot prove a complete daily run.
2. Inspect the canary artifact itself: verdict, failed gates, sections fed, raw actions, lifecycle
   `emitted_at_recv_ns`, crosswalk, knowledge receipt and output-bundle receipt. Stop on any refusal.
3. Run October 1 as the first production day with `mode=full` and exactly
   `glbx-mdp3-20211001.mbo.dbn.zst`. It must traverse that source object's complete manifest record
   count and report `is_complete_source_day=true`.
4. Deliver and inspect the ledgers, spawn Frankie against the receipted prompt and knowledge bundle,
   validate the output bundle, first-lock/freeze Frankie's actual output, and commit its findings
   artifact.
5. Confirm the automatic carry actually fires after the findings commit arrives. GitHub Actions
   cannot create a commit that never arrives from the external ChatGPT Work session; this is the
   one silent first-link failure mode. Do not assume the carry occurred—verify the seed/manifest
   update and service of the admitted findings.
6. Only after October 1 is frozen and promoted, repeat the same complete one-day process for
   October 3, then October 4, then October 5. A later-day artifact is correctly refused while any
   earlier roster-day artifact is `MISSING`; `PRESENT_EMPTY` is a legitimate completed day.
7. Keep D99's non-MBO input isolation active for all four days. Fill those preserved inputs only on
   later source days where reliable aligned values are available.

Never pass multiple source objects to one production run. Never treat a record-bounded canary as
complete-day proof. Report the actual emitted prompt bytes on the first live run; the known 15,999
byte and 128,418 byte figures are pre-run component/fixture measurements, not a live prompt.

## Report back

For every run, report the exact run id, source object, requested and traversed record counts,
`is_complete_source_day`, verdict, failed gates, receipts, prompt bytes, sections present, findings
artifact status, memory carry result and any zero-value-only retention recommendation. Preserve
`CANNOT_JUDGE` where the evidence is insufficient. Do not hide a worse measurement or relax a gate
to obtain green.
