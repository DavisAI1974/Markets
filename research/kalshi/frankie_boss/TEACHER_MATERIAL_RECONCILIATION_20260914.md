# Teacher archive reconciliation — 2026-09-14

Read-only comparison against Markets-initial-build at f0127bc4. The incoming
documents are evidence/proposals; the owner's new instruction authorizes their
combined reconciliation, not treating every imperative inside them as an
independent production requirement. No archive code, training, inference, provider
call, source edit, or historical workbook edit was performed.

## Archive and evidence scope

The outer extraction contains the byte-distillation memo, research status, and
claude_session_20260914_outputs.zip. I checked nested paths resolve inside
work/teacher-incoming/nested, reject absolute/drive/traversal/symlink entries, and
bounded total declared size before extracting. The nested archive contains five
Markdown documents (architecture ruling, byte memo, native forecast review,
addendum, research status), operator_runs.xlsx, and three histogram PNGs. It does
not contain the scripts or CSVs listed by RESEARCH_STATUS. No archive code ran.

operator_runs.xlsx SHA256:
`d294a7c0761dfaa737efb568d19bb31913b2470542c3d6dc07a38e1fd70340d2`.
It has 15 sheets, 5,409 formula cells, and zero cached Excel error cells. This is
an inspection of saved formulas/caches, not an Excel/LibreOffice recalculation.
Bundled Python read the workbook without saving it; independent calculations
checked the key histogram claims. No image rendering or publication proof is
claimed from the Audit sheet alone.

## Build-map corrections

| Incoming assertion/proposal | Current evidence | Build-map disposition |
| --- | --- | --- |
| Byte memo §4: six C14 targets remain ABLATED | c15_teacher_r3.py implements the six B2/C1 columns; JournalTeacherR3 combines these with thirteen unchanged R2 definitions, with R3 identity/updating/frozen normalization in c15_normalizer_r3.py. SPEC-c15-teacher-r3.md cites accepted equations. | Stale as a software-gap assertion. Mark R3 software built, production selection and empirical acceptance separate. Do not remove the deliberately ablated R2 control. |
| Representation-supervision harness already exists | teacher.py TeacherHead, make_targets, verify_controls, run_experiment; DipoleTarget carries masks/provenance. ContextSessionRunner accepts explicit JournalTeacherR3 and tests restore its exact receipt. | Correct. Reuse it; do not introduce a second teacher framework. Existing plumbing does not prove teacher benefit. |
| Stage 8 C22 serving is unwired | Frozen Granite services and transport-neutral controller exist, including SageMaker native critique and native mapper. Actual staged model/runtime/capacity/integrated inference remain absent. | Split into built service/controller software and unfinished deployment/production integration. Do not rebuild the transport. |
| Stages 9–10 not started | experiment_runner.py supplies locked complete-roster execution and coordinated reveal/scoring software; production roadmap records this explicitly. | Too broad. Software is built; real paired runs, calibration and empirical acceptance remain open. |
| EOT byte-text distillation should become native BOSS capability | Memo itself rejects it: native B1 predicts typed forecast outputs, not autoregressive text bytes. | Keep rejected/research-source note; no EOT component, byte decoder, or input boundary-token change. Paper claims have not been independently verified in this reconciliation. |
| Add D6, D7, C32 Granite representation teacher | Memo explicitly calls these proposed rows and says “opinion and placement only; no implementation requested.” Neither current ARMS nor production target schema implements them. | Record as a deferred, conditional research fork. Do not mark accepted/built, alter the controlled arm roster, or make it a prerequisite for required Granite critique integration. |
| Hidden-state export is part of serving | Current chat/native critique transport returns parsed text; owned container capability is not an implemented/export-verified contract. | Separate future export endpoint/protocol and receipt identity from frozen chat critique. No implied hidden-state access through existing service. |

R3 details that must survive reconciliation: horizons 64/1024 completed groups;
B2 matched fill removal divided by far-side top-three economic removals; C1
size-weighted identity survival and capped original-size retention; explicit
MISSING/INVALID masks; same-group fill reconciliation; no revival on order-ID
reuse; reprice survival; member/session/reset boundaries. Identity and normalized
routes bind implementation code, source prefix, causal cutoff and normalizer
checkpoint. Full-prefix scans remain a throughput limitation. A saved source
binding is not independent authorization of that source.

`context_session.py:111,186–188` makes R3 an explicit attachment. It is not a
silent replacement for the default/control route. The test at
`tests/test_c15_teacher_r3.py:222` uses the actual session and exact restore.

## What the synthetic workbook establishes

- Operators A2:E5 records skew fraction, normality defect and eigenvector
  conditioning as distinct diagnostics. The orthogonal fixture has skew fraction
  0.7359 and near-zero normality defect; the triangular fixture has conditioning
  about 1.60e24. These are synthetic examples, not evidence about recovered OD
  operators.
- Projection A2:E3 preserves the same true projection cosine (0.3182953), while
  an incorrect orthonormal assumption gives 0.7947852 for the near-collinear
  basis (Gram condition about 1044.25). Any future real-basis calculation must
  explicitly account for the Gram matrix/orthonormalization and rank/conditioning.
  This does not establish that current BOSS code has this defect.
- Diagnostics D44:D61 contains exactly the 18 non-positive entry gaps among
  D2:D61: four exact zeros, minimum -0.6951674, median -0.1211849 and mean
  -0.2099681. Sigma counts are 0/1/6/11 at 0.05/0.15/0.30/0.50. I recomputed
  these from stored raw values and confirmed the last-18 selection equals the
  non-positive predicate for this frozen sheet.
- Plot gap hist D3:I40 has 38 bins over -1.2125 to 2.5875, with a closed final
  upper edge. Independent Python comparisons reproduce all six count series;
  D41:I41 is 18/18/18/60/60/60 and D42:I42 is all zero. No observation is dropped
  by those histogram edges in the supplied workbook.
- Audit B4:C7 reconciles 240 spectra, 480 path, 160 separation and 60 diagnostic
  rows. Audit D4:D7 “rendered points” are hardcoded, and D8:D9 are blank. They
  are not independent runtime proof that an image renderer emitted every point.
- The 18-row histogram uses fixed Diagnostics rows 44–61, explicitly documented
  as sorted by gap sign. If trials are added or sorting changes, the selection,
  formula ranges and audit must be updated together. Do not blindly append trials.
- The status claims about 600-term support monotonicity, OLS equivalence and
  t-statistic separation are not independently reproducible from this archive:
  the cited scripts/per_term/upstream/tstat CSVs are absent. Term scale is a
  separate eight-term/path example; do not treat the status's n_lam=40 relation
  as a universal identity for every workbook sheet.

These findings justify careful research diagnostics and row-count reconciliation.
They do not authorize replacing C15 targets, inventing new masks, declaring dipole
benefit, or claiming byte evidence lacks information that its semantic views have.

## Dependencies and ordered work

1. Finish the already-required integrated native/agent delivery and Granite
   deployment/capacity work with the current architecture ruling respected. The
   architecture memo rejects adding native B1 knowledge retrieval; none of this
   teacher material changes that boundary.
2. For the dipole experiment, choose an explicit R3 production configuration;
   pin actual source/manifest, QSV source/masks/mapping, causal context, checkpoint,
   normalizer, model/head/decoder, forecast scorer, splits, seeds and complete
   control roster. Verify lawful target coverage and production throughput.
   Training/reveal still need their own authorized run scope; this audit ran none.
3. Obtain attributed D0–D5 controlled results before claiming an aligned dipole
   improvement. Existing none/plain_aux/shuffled/random/dipole controls must keep
   exact identities and the plain projection independent of dipole targets.
   Rank using forecast scoring, not incomparable auxiliary/text losses.
4. Required Granite critique integration should proceed independently of the
   speculative export path. The memo's “D0–D5 then stage 8 with export” ordering
   is not a reason to block ordinary hosted critique integration until training.
5. Only if the future research fork is accepted: specify the frozen teacher
   checkpoint/runtime/tokenizer, chosen hidden layers and dimensions, exact
   prompt/event alignment, source cutoff, missing/failure policy, loss weighting,
   target artifact and export-code hashes, and model/training receipt binding.
   A hidden-state vector is not just an unversioned extra scalar column. The
   native event input/output semantics remain unchanged and inference stays
   independent of the export service.
6. D6 tests Granite representation alone against unchanged appropriate controls.
   D7 combines teachers only after separately interpretable D5/D6 evidence. The
   memo also says choose runtime fusion versus distillation after stage 10;
   record this as a conditional decision, not simultaneous mandatory delivery.
7. Real OD diagnostic application needs the actual authorized arrays, basis and
   operator identities plus the missing script/source versions. Synthetic
   examples alone cannot set production targets or thresholds.

The new owner instruction combines the earlier addendum and architecture ruling
with the remaining build. The old “deferred until initial sheet complete” line
must be reconciled by the root against that latest instruction. Teacher work
does not override the architecture stop or authorize an unsupported NOOA runtime.

## Validation

Workbook histogram counts and selected descriptive statistics independently
recomputed as above. Current teacher R3 and teacher-control focused regression:
58 passed, one skipped in 65.70 seconds. An initial invocation named a nonexistent
separate normalizer test file and collected no tests; the corrected run includes
the normalization tests housed in test_c15_teacher_r3.py. No prior workbook or source
module was changed. The external arXiv paper is not independently reviewed here;
all discussion of it is attributed to the supplied byte-distillation memo.
