# Native mapping build handoff — 2026-09-07

Branch: `codex/boss-full-evidence-20260907`.
Starting commit: `5e93896dd0dd8238fa3ff2af48a0e086fe42170e`.
Authority: approved `CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING_20260907.md`,
plus Greg's subsequent authorization to resolve its identity/reconstruction gaps.
This supersedes the unresolved mapping status in `FULL_EVIDENCE_HANDOFF_20260907.md`.

## Completed scope

The inspected brownfield inventories, native adapter, serialization contract and
R2/R3 contracts had no complete native encoder registry. The additive
`NativeRegistry` now declares all 14 native MBO fields and the 10 available
adapter fields. Explicit named extensions are supported; undeclared fields halt
the mapping. Nothing is classified as retained-but-not-encoded.

| Evidence | Computation path | Exact preservation |
|---|---|---|
| Timestamps, price, size, sequence, input delta | Sign/high32/low32 float64 views plus byte embeddings | Original values/types retained in reversible byte tensors |
| Action, side, publisher/channel, rtype, flags, clock contract | Registered categorical views plus byte embeddings | Unknown values remain distinct in exact bytes |
| Order and instrument identities | Exact categorical byte embeddings; causal order parent links | No numeric order-ID quantity, lossy float conversion or hash bucket |
| Adapter provenance, source cursor/session, integrity defects | Exact byte embeddings | Types, field names, values and ordering round-trip |
| Explicit extension fields | Exact byte embeddings without byte-length caps | Nested values, bytes, missing/null, signed zero and float bits preserved |
| Every journal record through a cutoff | Verified journal stream and optional full-prefix teacher computation | Prefix/entry/record counts and integrity are checked |
| Current entity context | One sequence token per retained context event; every token receives an evidence score | Exact cursors, packet hashes, registry and tensor bytes are receipted |

The byte lane is a real learned model input. Tests perturb every raw native field,
every adapter field, each semantic column and graph link, early bytes of long
extension fields, and source/defect metadata, and verify changed hidden states.
Inverse reconstruction uses tensors and registry, not journal lookup. Learned
hidden states themselves are not claimed to be lossless.

## Contracts restored and preserved

- Granite output/prompt return to the approved V1 caps and nonempty hypotheses;
  the strict reference/hash rules remain. Exact state serialization stays V2.
- Trunk V2 defaults return to attention window 128 and QSV disabled. Existing
  QSV support remains optional and exactly ablatable. NativeTrunk is opt-in.
- Trunk V1 and canonical-byte source fixtures are pinned to
  `beb548b86b777dc69bf834950b30cc28000e16ef`, with source hashes. Loading its
  weights into V2 preserves bit-identical B0 representations on preservation
  fixtures, including QSV. B1's complete acceptance/regression matrix runs on
  both lineages. `b1_reasoner.py` is unchanged.
- C15R2's 19-column teacher is restored downstream of the complete journal.
  Teacher-only transforms, 64/1024 target windows and the existing 4096-row
  normalizer contract do not modify or cap raw evidence. Six B2/C1 columns
  remain explicitly ABLATED as approved; no claim those features were built.
- Frankie controller, inputs, calculations, planes, original adapters, replay,
  BLD-1 and Memory A are untouched by this continuation. Authoritative book
  reads are additive; no private replacement book is maintained.

## Runnable software boundary

`ContextSessionRunner(NativeTrunk(...).double().eval(), builder,
entity=(publisher_id, instrument_id), teacher=JournalTeacher(...))` supplies
the opt-in journal-to-native-to-B0 path. Wrapping the same NativeTrunk in the
unchanged B1Reasoner supplies B1. `append()` commits the original record before
processing. `run(as_of=..., through_cursor=...)` builds and verifies the declared
causal context. No production market-data invocation is needed for this API.

The provisional `T_CTX=4096` is separate from raw retention. The receipt reports
all prefix rows, other-entity rows, entity rows outside the current context,
exact context cursors and packet hashes. It does not claim that older rows are
model-visible on every decision. With the teacher attached, every prefix record
is processed before context-aligned targets are selected. Other instruments are
processed in their own teacher state. There is no silent source-row exclusion.
The withdrawn FullHistoryRunner raises with migration guidance rather than
silently retaining the rejected full-day replay architecture.

Every context cursor receives its own existing C14 DipoleTarget artifact with
its own receive cutoff, source prefix, normalizer receipt and target hash.
The context receipt binds their ordered attachment hash and teacher identity.
Receive-time regressions stop attachment explicitly. Unknown trade sides,
unreconciled fills, missing references, left-censored order origins and
nonterminal groups have explicit invalid/missing states. Matched fill/cancel
economic removal is counted once. Order ranks come from the authoritative book.

Checkpoint restore reconstructs inputs from the verified journal and compares
trusted input/model hashes, exact tensors and the complete receipt. Weights,
configuration, native/QSV registries, ablation and relevant source code are
bound. Future journal suffixes do not alter earlier cutoff identities. A failed
forward blocks appends and binds both input and model; retrying with changed
weights, context, registry or teacher state fails.

## Focused verification

No broad repository rerun was needed. The relevant synthetic batches passed:

| Batch | Passing checks |
|---|---:|
| Approved Granite parser, prompt, evaluator and precision/output contracts | 195 |
| Pinned V1/V2 B0 and canonical-byte preservation | 6 |
| B1 acceptance/regressions on both trunk lineages | 98 |
| Native encoder, teacher attachment and context session, final focused batch | 49 |
| Existing complete-evidence and history checks | 27 |
| Restored default-QSV seam assertion | 1 |

The 27 existing checks also passed in the earlier combined 73-check invocation;
the final 49-check batch includes three additional targeted cases. Counts are
software checks, not experiments or market-performance evidence. The original
355-check correction batch remains historical evidence, not a new broad rerun.
Read-only native/context and teacher reviews identified retry, clock, fill,
target-cutoff and restart gaps; the focused checks cover their corrections.

Test runtime: the existing scratch pytest/torch dependency paths, with
`research/kalshi/frankie_boss` and repository root on PYTHONPATH. No dependency
installation, Frankie launch, training job, market-data/provider run, Oct 1
mechanics probe, OSS evaluation or deployment was performed.

## Remaining scope limits

The requested mapping and opt-in software integration are built. T_CTX remains
provisional until a separately authorized mechanics probe. Full-prefix journal
verification and teacher reconstruction stream evidence but repeat prefix work
per decision; production MBO throughput and resource bounds are not established.
The event-only native candidate defaults to QSV disabled; explicit ablation is
supported, and an enabled unablated QSV branch without governed inputs fails
instead of inventing data. Existing Frankie planes are preserved, not replaced
by a claim that all external production feeds are wired into this candidate.
Experiment arms, training, live integration and OSS evaluation remain parked.
