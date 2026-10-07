# Whole-workflow coverage and one-day inspection — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Read with the latest continuation handoff and
`SPEC-experiment-orchestrator.md` section 0. This maps that **entire workflow**, including
conditional and cross-day substeps; the ten-item module-review list is only a build checklist.
Nothing here establishes a successful E2E, consumer execution, full 99-layer computation,
native learning, measured speedup or a completed workflow.

Applied API and Interface Design: explicit read-only input/output contract, exact day/run
selection, explicit unknown/error dispositions, no change to scientific or runner interfaces.
Existing AWS processing findings in the module reports are reused. AWS plugin reauthentication
is blocked in this session; no new AWS finding, account inspection or execution is claimed.

## Reading the map

Source names without a directory are under `deploy/aws/box/`. `Run.*` means
`frankie_box_experiment.py`; queue-owned days use `frankie_box_frankie_queue.py` (ROOT and classroom queues). Artifact paths are relative to the retained owning output,
unless a step receipt supplies an absolute path. **Retained** and **published** do not mean
**used in computation**. A source-read counter does not prove every retained field entered
a scientific operation. Search output counts are recorded calculations, not acceptance.
A reused result is not a new independent observation.

Every row below is a reviewable workflow piece/substep. Existing reports stay authoritative;
the temporary inspection fills presentation gaps by projecting their real metadata and
pointing to full retained evidence. Unknown or missing evidence remains visible.

| Canonical piece / applicable substep | Producer → consumer | Existing review evidence / report | One-day inspection and remaining gap |
|---|---|---|---|
| 0. Plan / authorization scope | Saved plan, run/day admissions → queues/day runner | `plan.json`, per-day/batch step receipts, controller/queue ownership | Print selected plan entry and exact step identities; controller delivery is not stage execution. CCode now owns the admission/save source fixes; the main-recovery agent reviews their integration. |
| 0. Resume / held CPU ownership | Ledger, claim, original attempt and save marker → resumed child | Existing CPU booking, source/attempt pins and saved-child acknowledgments | Review original source/attempt/day/CPU set together, including waiting/refused state; no automatic resume or repair by reporter. |
| 1. Fetch / member selection | Plan manifest/archive members → existing ingest | Fetch step record, ingest manifest and member dispositions | Reuse completed retained day; actual new/missing fetch must be distinguished from retained input. |
| 1. Seal / opening book / partial members | Ingest → ROOT and teacher journal readers | `ingestion-receipt.json`, completion and opening state; journal count/hash and partial/tail members | Project receipt counts/bindings; these establish sealed availability, not complete ROOT/teacher consumption. Do not rescan giant journal for this report. |
| 2. Historical/external day attachment | `frankie_box_day_external.py` → permitted AsOf readers | `day-external-receipt.json`: every input, missing list, output bytes/hash; `day-external.json` | Show missing/deferred series and publication identity; attachment/upload alone does not show as-of use. |
| 2. Causal external reading | `operations/frankie_day_external.py` AsOfReader → ROOT, classroom, search | ROOT `external-computation.json`; teacher external section; search source/clock placements | Distinguish original rows, cutoff/as-of aliases and unplaced/overwritten rows. No invented missing values. |
| 3. ROOT source binding / whole-day legacy pass | `frankie_box_experiment_root.py` → `Session.derive`, retained spools | `source-binding.json`, `calculations-receipt.json`, `work/derive.json` and optional normal digest | Print processes, layer outputs, row counts, producer failures and every not-run process. Full registry union is not proof of full calculation coverage. |
| 3. INPUT/APPLIED / full book / FIFO / F_LAST groups | Existing pinned adapter → frame/price/structure spools → search readers | Derivation layer pins and frame schema; journal/ROOT alignment source tables in search manifest | Trace actual placed fields/ordinals and unplaced dispositions. Positional rows are not persistent lifecycle trajectories. |
| 3. Bedrock/native completed products | Explicit default-off native traversal → selected native ledgers → native search/scientific readers | Native policy and derivation refs; selected native source channels/results | Do not activate the producer to fill report. Disabled means not run; stored native references alone do not prove training or every consumer. |
| 3. Native model learning / representation | Original model/checkpoint + BOSS objective → native learner | Existing evidence-role contracts and retained session/checkpoint identities | No model calls in current experiment ROOT. Target/mask/control/objective and cross-lane checkpoint lineage remain scientific decisions; classroom answers are not native training. |
| 3. Immediate ROOT knowledge | `Run.brain_stage` → next applicable reader | Stage knowledge and brain manifest pins, later learner knowledge input | Publication is shown separately from later consumption. Requires actual downstream documents/inputs, not only brain receipt. |
| 4. JournalTeacherR3/Dipole walk | Sealed journal/book → attachment and governed rows | Teacher `receipt.json`: processed/entity rows, cursor, attachment/rows hashes, caveat | Report exact scope. Whole-day row self-comparison is not independent verification; teacher evidence must exclude private decisions. |
| 4. BOSS preparation / representation supervision | Existing BOSS provider lifecycle, targets/masks/controls → model consumers | `BOSS_MODULE_PERFORMANCE_PLAN_20261007.md`; original native outputs/receipts | Approved provider/queue/hoist work is already source-built. Broader evidence/knowledge target consumers remain unproven; no replacement objective. |
| 4. Teacher external section | External day AsOf material + teacher source → classroom section | Teacher receipt `external_section`, retained source/key/section | Report built/reused/absent/refused and reason; all external columns need consumer accounting. |
| 4. Immediate teacher knowledge | `teacher_knowledge()` → classroom learner knowledge | Stage source/knowledge hashes; classroom delivery fields and learner reader evidence | Distinguish teacher entry published, document read, and applied answering/calculation. |
| 5. Prior-class/cumulative knowledge | Brain/school/previous class → `classroom_v2`, staged learner | `learner-knowledge.json`, previous state, numbered Classroom/Frankie reports | Exact cutoff/available documents and actual learner use; no chronology gate. Currentness and corrected-container work is owned by other agents. |
| 5. TEACH / GUIDED / SOCRATIC / VERIFY | Permitted journal/native/external reader → code answers | Normal reports plus `code-answers.json`, external answers, reader scope | Honour per-mode answer walls; lawful learner journal route is not independent second science. Historical glossary wording is not execution authority. |
| 5. Grade / correction / acknowledgment | Teacher host grading → learner correction response → completion | `post-grade.json`, correction request/response, acknowledgment, completion; normal report | Reuse reports showing each answer/correction and disagreement. Missing response cannot become completion. |
| 5. Novel claims / immediate classroom brain | Learner ledgers → scientific teacher and brain | `novel-findings.json`, `novelty-investigation.json`, `ledgers.json`, normal reports | Claims remain claims until scoped checking; brain entry is not a scientific finding by itself. |
| 6. Data export / exclusions | `frankie_box_experiment_data.py` → both teachers/search | `MANIFEST.json`: included, excluded, missing, unclaimed and byte/hash pins | Print all dispositions; owner-local hard links avoid duplication. Export availability does not establish consumer use. |
| 7. Source channels / causal alignment | journal/native/ROOT/Dipole/external readers → `build_series` | Search manifest `sources`, `notes`, `leakage`, placed channel/ordinal tables | Show real channels and exclusions, not just static plane map. Numeric market values distinct from ID/date grouping labels. |
| 7. Cells / transforms / lag / chance statistic | Complete selected series → `_cell_job` / `couple` | Manifest `cells`, `transforms`, `lags`, `cells_not_counted`; exact coupling parts and rows | Counts remain per pair/cell/day. Report selected transform pairs, unclassified steps, null/opportunity scope. Conditional cell-axis lag remains unsettled. |
| 7. Scientific arithmetic / immediate search knowledge | `review.search_findings` → candidate document / brain | `knowledge-review-<hash>.json`, `knowledge-findings.json`, exact part/ordinal/raw-line bindings | Existing reviewer reads actual part bytes. Reporter references its result, never reruns science or treats beyond-chance count as acceptance. |
| 7. Symbolic nonlinear/multivariable discovery | `odcore/symbolic.py:discover`, `scripts/od_pysr_discover.py` → future lawful workflow call | Existing engine preserved; no experiment call found in Step 3/current source | **Unwired.** Pairwise nonlinear transforms are not symbolic discovery. Feature/target/condition interface must be settled without changing original fitting math. |
| 8. Carried historical / accumulated claims | `scientific_teacher.test`, `teacher_knowledge.teach` → scoped lesson results | Frozen `inputs.json`, full result files, accumulated receipt scope; normal exchange/report | Report scheduled/new/reused/already-tested, late knowledge, counts-only/unresolved and origin evidence separately. Retained reuse is no new computation. |
| 8. Native evidence / historical reproduction | Completed owner-local native evidence and checked reproduction selection → each applicable scientific result | `completed_native_evidence`, per-consumer dispositions, frozen reproduction pins | Typed scientific mapping gaps remain. Historical cost-contaminated conclusions require source/reproduction correction for **both teachers**; no historical run occurred. Memory A/H06–H08 remain retired/not_bound. |
| 9. Today's Frankie findings | Ledgers → standalone scientific operation → lessons/exchange | Batch `lessons` calls, exact frozen operation, `<day>-frankie.json`, claim results | Preserve every claim's identity/scope; future knowledge cannot retroactively change its original answer. Relevant batch receipt is not enough without real result document. |
| 10. Candidate generation | Each checked scoped search row → `candidate_claims_doc` → accumulated checking | Search findings and claim input/provenance, per-claim scientific results | Candidate generation exists. Retest/origin rows/mirrors are not independent confirmation; retain each original scope. |
| 10. Survivor update / availability | Completed cross-day evidence → survivor set → later classroom | Existing consumers / input references; no adopted writer/acceptance rule established | **Open scientific acceptance contract/producer.** Not a per-day blocker invented by reporting. Single-occurrence equality; no same-day circular classroom promotion. |
| 11. Three code seats | Checked lessons + BOSS rows + search → exchange → Frankie reply | Exchange/Frankie view and receipt; normal numbered reports | Exact lesson/search inputs and actual code-generated positions/checks; no receipt-only teacher consumption claim. |
| 11. Granite facilitator / requested owner tests | Retained code seats → pinned runtime → meeting → explicit owner request | `meeting.json`, receipt, runtime evidence; Frankie numbered report | Report completed/refused/unavailable truthfully; Granite is facilitator, never scientific seat. Requested test is not a result. Effective runtime threads/staging remain unverified. |
| 12. School consolidation | Current classroom/lessons/exchange/meeting → school document | School step file/sections/missing/withheld; school index | Reuse unaffected knowledge and explicit corrected successors. Consolidation is not first publication; old embedded meeting cannot masquerade as current. |
| 12. Numbered reports | Retained classroom/exchange/meeting → deterministic report translators | Classroom/Frankie report #N and revisions; Jev same N | Reuse originals; normal report generation retains every recorded field under its own contract. Temporary report does not replace or delete them. |
| 13. Blind material / request/reply / sealed claims | Governed classroom material → CPU Jev → claims | Existing material/client state/request hashes and normal Jev report | CPU runtime/model/allocation/completion choices open. Preserve pending calls and blindness until seal; legacy Pod/material delivery is not completed comparison. |
| 13. Scientific testing / dual delivery | Sealed Jev claims → scientific teacher → Frankie + Jev | Exact scientific operation/results, recovered lesson delivery receipts | Upload recovery is source-built; CPU owner-local seal/result/consumer completion remains open. Replaying delivery never reruns science. |
| 14. Market-only checking / checked successor | Explicit owner request and scientific decision → corrected result → affected consumers | Owner request/decision/result/publication, successor receipt, correction scopes | Retain unaffected knowledge and unresolved conflicts. No auto scientific decision or “latest wins”; correction propagation must reach actual downstream use. |
| 14. Dependent exchange / learner / school | Current correction scope → explicit dependent successor → later original-session learner | Existing correction ledger, exchange successors; current school/learner integration work | Preserve immutable forecast/source/session/request/input and pending feedback. Delivering corrected knowledge is not retrospective forecast replacement/native training. |
| 15. Separate confirmation | Separately defined future design → eventual confirmation | Historical code/drafts only | **Not selected/authorized.** Retained frozen-lag route limitations are not repaired or activated by inspection. |

## Small temporary reporting interface

Added `deploy/aws/box/frankie_box_workflow_inspection.py`. It is a standalone standard-library
reader. It imports no project modules, writes no files, performs no network/model/science
calls, and changes no queue, brain, checkpoint, curriculum or completion state. No automatic
invocation is wired into the day runner. This avoids a permanent reporting framework and
lets the report run only for the agreed one-day inspection.

Input contract: exact owning-lane `--run-dir` with retained `plan.json`, one exact `--day`
in that plan, and optional repeated `--artifact PIECE=/absolute/path`. PIECE names are
`preflight`, `ingest`, `external`, `root`, `teacher`, `classroom`, `data`, `search`, `carried`,
`findings`, `candidates`, `meeting`, `school`, `jev`, `corrections`, `confirmation`.
Additional JSON artifacts must be metadata/result documents, never giant evidence spools.
Non-JSON inputs are referenced for review, not loaded. Operator-supplied references are
explicitly unverified; passing a path does not attach it to a scientific operation.

The reporter selects only matching run/day control records and compares each step's
`plan_sha256` against the canonical hash of the actual saved plan (the raw plan-file hash is
reported separately). A missing/different plan identity is displayed and its artifact paths
are not followed. Exact `days`, `remote_days`, `waiting`, role, owner and attempt identities
remain visible. Cross-day batches are included
only when they explicitly name that day. It preserves their cross-day scope. It prints all
canonical pieces, distinguishes non-classroom applicability, points out missing records,
opens named local ROOT/teacher/external/export/search/classroom metadata, and reuses normal report
references. Original metadata values are not sampled. Selected processing/disposition fields
are printed; other field names and the exact source path/hash are listed explicitly so their
full contents remain reviewable. Each JSON read has an explicit **8 MiB metadata ceiling**, including operator-supplied
JSON. Oversized inputs are not parsed or truncated: `not-inspected-too-large` and the original
reference remain visible. The read itself is bounded if a file grows after its size check.
This is a reporting budget, never a cap on scientific evidence. Only paths/stage names are
retained when scanning receipts, then each selected document is inspected in turn. Giant
journal, spool, coupling-part and model bytes are not read. Missing artifacts/errors do
not hide other pieces.

**This is inspection, not a provenance validator.** It hashes the exact metadata it reads;
it does not reverify all referenced giant outputs or infer that a receipt's claim is true.
Search `sources`/placed channels and actual scoped calculation result fields are stronger
recorded evidence than storage inventories, but gaps stay gaps. Full native/claim/model
consumption cannot be established by this projection if the producer did not record it.
The operator reviews exact original results before claiming consumer coverage.

After execution is separately authorized, use the staged source path on the day-owning lane:

```bash
python3 /ABSOLUTE/STAGED/CHECKOUT/deploy/aws/box/frankie_box_workflow_inspection.py \
  --run-dir /ABSOLUTE/RETAINED/RUN \
  --day YYYYMMDD
```

At a pause boundary the same command reports what exists so far. Add exact artifacts the
step metadata does not expose, especially first-run teacher rows, standalone scientific
results, owner recovery records, checked correction consumers and existing numbered reports:

```bash
python3 /ABSOLUTE/STAGED/CHECKOUT/deploy/aws/box/frankie_box_workflow_inspection.py \
  --run-dir /ABSOLUTE/RETAINED/RUN \
  --day YYYYMMDD \
  --artifact teacher=/ABSOLUTE/DAY/TEACHER/receipt.json \
  --artifact carried=/ABSOLUTE/ACCUMULATED/RESULT.json \
  --artifact findings=/ABSOLUTE/SCIENTIFIC/YYYYMMDD-frankie.json \
  --artifact school=/ABSOLUTE/REPORTS/frankie-report-NNNN.md
```

These are placeholders requiring the actual retained paths, not commands run this session.
Do not feed stdout to Frankie, scientific evidence, lesson inputs or a brain writer. No
permanent storage is required. Keep Linux/remote giant evidence on its owning lane; a central
remote receipt can identify the owner, but cannot substitute for its local report/artifacts.
Automatic artifact following is disabled whenever a receipt has `remote_owner`,
`remote_attempt`, `remote_calculations`, or an `owner` other than `main`. Such receipts are
rendered as **foreign-owner-reference-only**, even when their absolute paths also exist on
the current host. Run the inspection against original receipts on the owning lane. There
is no inferred-hostname or path-exists override. Explicit `--artifact` inputs are operator-
selected local references, labelled unverified; they do not adopt a remote receipt's identity.

## Remaining decisions and rollout

1. Settle lawful symbolic features/targets/conditions, conditional lag/null semantics, native
   target/model/checkpoint lineage and survivor acceptance. Do not silently activate a producer
   or substitute pairwise search for symbolic discovery. Repeated references and single-occurrence
   validity are different questions; no new rarity thresholds or output pooling.
2. Finish actual evidence/knowledge consumers and owner-local cross-day coordination; explicit
   remote receipt refusal must not become phantom central consumption. Correct both teachers'
   historical sources/results when authorized, not just their displayed fee columns.
3. Integrate CCode's admission/save/controller work and current corrected learner/school
   work; keep those agents' detailed reports authoritative for source completion. Jev's CPU
   runtime/model/allocation and truthful seal/test/delivery/completion still need resolution.
4. Finish wiring/discussions, then the separately authorized **single E2E**. After it passes,
   inspect **one complete applicable day**, reuse normal reports and the temporary projections
   above, review outputs/surprises with Greg and Frankie, apply agreed adjustments, then run
   **three days** when authorized. Thirty days remain a later separate decision.

Verification for this slice: direct source/interface reading, AST parse without project
imports and `git diff --check` only. The reporter itself was not executed. No tests,
synthetic exercises, imports, installs, historical/data/model/scientific runs, AWS starts or
dispatch. Source-built reporting is not evidence that any stage actually ran.
