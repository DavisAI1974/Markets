# Continue Frankie after combined-build documentation closeout

Run using-agent-skills first. Repository: DavisAI1974/Markets.

The owner wants the full final Frankie build completed, including actual Granite
in integrated tests. Close the remaining build work, then rerun Sunday 2021-10-03
first for comparison. Do not start by building another launcher or calculation
wrapper. This task is closing documentation at the owner's request; no new chat
has been created automatically. Resume implementation in the new task, coordinating
with the separate manual Claude Code assignment below. The canceled request to
create frankie-claude.md was intended for someone else; no such file was created.

## Start from these two branches

**BOSS implementation**

- Remote branch: `codex/boss-full-evidence-20260907`.
- Verified pushed software tip: `de27bb26337c8c7a7abccbee475a56725ac39426`.
  Documentation-only closeout commits may follow this software tip; fetch the branch.
- Local: `C:\Users\A\Documents\Codex\2026-09-14\re\work\Markets-initial-build`.
- Local branch: `codex/boss-initial-software-20260914`.
- Reviewed implementation commits: `c51a8020` physical evidence/replay/runtime pins;
  `aa10a464` lossless compact context and expansion bounds; `61b34ee6` execution
  policy/outbox/account frontier/kill; `cc5e6bf1` exact AWS quota/Hosting inventory.
- The user-supplied architecture review request at `3cfbf5c4` is preserved.
- `de27bb26` rejects negative references in native and compact Granite scorers:
  83 context tests passed. No prompt text changed. Parser source identity changes
  honestly with the repaired code; no full BOSS regression was rerun for this fix.

**Existing committed-file agent path**

- Remote/local branch: `codex/frankie-agent-evidence-fixes-20260914`.
- Verified pushed closeout tip: `996d121cb4b8f723c28c5eb61772fed6719c9c14`.
- Local: `C:\Users\A\Documents\Codex\2026-09-14\re\work\Markets-agent-audit`.
- Base: `9006b633829cc2d7d34df269d6645d1ec4ddee54`.
- Implementation commits: `d9e7f809` lossless source capture/immutable sinks;
  `fdabc363` causal sidecar indexing/complete physical witnesses;
  `81d8a24a` actual byte/run-bound delivery, knowledge and completion.
- Final fixture correction: `28237baa`, actual pinned knowledge at the spawn gate.
- Later fixes `f63fd391`, `1d43c158`, `06118451` and closeout `996d121c` supersede
  the earlier Windows/seed baseline failures. Do not rebuild those repairs.

Fetch both tips before work. These are different lineages: the BOSS tree lacks
the existing raw-MBO agent emitter path, and the agent tree lacks frankie_boss.
They are not yet integrated. Inspect/select the necessary modules and contracts;
do not blindly merge the entire historical trees or force-push.
The agent checkout is clean. The BOSS checkout has no uncommitted tracked changes;
its remaining untracked work/ directory contains scratch/runtime artifacts only.

The earlier checkout below retains deferred addendum work and must not be reset,
cleaned, staged wholesale, or overwritten:
`C:\Users\A\Documents\Codex\2026-09-14\b1-s-required-checks-passed-on\work\Markets-forecast-verify`.
The unrelated `E:\Markets` checkout is also outside this work.

## Read current status before older handoffs

In the BOSS tree:

1. `research/kalshi/frankie_boss/CONTINUATION_HANDOFF_20260914.md` and then
   `EVIDENCE_AUDIT_CLOSEOUT_20260914.md` for historical audit details.
2. `tasks/boss-initial-software-plan.md`, `tasks/boss-production-todo.md` and
   `tasks/boss-production-plan.md`.
3. `CLAUDE_REVIEW_FIXES_HANDOFF_20260914.md` and the controller, execution,
   compact-context, SageMaker and proposed live-run specs under frankie_boss.
4. The historical workbook remains reference evidence:
   `research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R3_20260914_Closeout.xlsx`.
5. The new BUILD_MAP_RECONCILIATION_20260914.md,
   TEACHER_MATERIAL_RECONCILIATION_20260914.md and
   AGENT_FILE_INTEGRATION_PLAN_20260914.md under frankie_boss.

The reconciliation covers all 31 component IDs, 26 gates and 13 roadmap rows.
The historical workbook is unchanged (SHA256
8862589effeee8ccb745dba6fe97a270921571c5524bd8d1b98df04f03817b23).
The proposed new combined Excel workbook was interrupted before generation;
the next task should create a derivative rather than overwrite the original.

The audit reused September 7's FULL_EVIDENCE_HANDOFF and superseding
CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING/NATIVE_MAPPING_BUILD_HANDOFF. Keep declared
compute/teacher windows distinct from full raw retention. No silent filtering,
cap, truncation, dropped field, invented missing value or ignored malformed row.

## Exact execution requested by the owner

Frankie is an agent session over committed files. No API or runner performs his
calculations for him. Use the existing sequence:

1. `fetch_frankie_ledgers fetch` with the delivery manifest. It verifies every
   ledger against the box's own digests and writes the delivery receipt.
2. `emit_frankie_spawn --result ... --delivery-receipt ... --ledger-dir ...`.
   Without a knowledge receipt, it builds KNOWLEDGE_BUNDLE.md,
   KNOWLEDGE_RECEIPT.json and the pre-call receipt beside the prompt.
3. Spawn on that emitted prompt and the three ledgers. The runner's
   calculation_result.json is not the agent's evidence. Lifecycle per-section
   rows are runner output, not the agent's own calculations/discoveries.
4. Preserve causal delivery. Exhaust the stream, call drain_withheld and retain
   terminal accounting; never expose terminal-only rows to earlier decisions.
   Final native_staging read-back now requires `--stream-receipt` as well as the
   actual delivery, knowledge, bundle, prompt and output files.
5. Commit and push agent outputs as they land so restarts cannot lose them.
6. Do not supply conclusions or previous findings before the independent run.
   Attribute coordinator inquiry pointers in confidence_basis.

Sunday comparison anchor: A-memory run 33746436209; earlier A-clean run 33630348943.
October 1 and 3 are development roster dates; October 4 and 5 are held-out. This
audit launched no replay, reveal or training. Read the source and frozen memory
provenance before selecting the comparison arm; do not silently change Memory A.

## Current agent verification and Sunday memory identity

The agent branch's committed follow-up records the owner's explicit removal of
the requirement to run every earlier roster day before admitting real later
findings. October 1 remains MISSING; nothing was invented or relabeled. Current
carry retains 44 prior VERIFIED findings and adds 18 Sunday findings as NEW.

Latest committed agent verification: **2,082 passed, zero failures/errors/skips**
in two disjoint batches covering the full legacy-agent test directory. This is
the other task's recorded verification, checked in its committed closeout, not
a new run here. The earlier 2,053/15/11 report is historical. Main BOSS regression
before de27bb26: 1,371 passed, one CUDA-only skip, plus 11 checkpoint tests
separately; the new scorer fix has 83 focused passes. Counts overlap.

Current carry: 244,923 bytes, SHA256
b814bb58f03d506f1643a162ff0ca1e94e17a7f8e90d533d844e86b1995b4f07.
Frozen prior used by Sunday run 33746436209: 166,700 bytes, SHA256
4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a.
Never substitute the refreshed carry containing Sunday's findings into the
historical Sunday comparison. Archive files remain unchanged.

## Remaining build, in order

1. Complete BOSS-to-agent delivery integration while retaining original Frankie,
   S121, B0/B1 controls, replay, Memory A and source evidence.
2. Integrate compact context through mapper/service/controller with explicit new
   identity and exact inverse verification. Codec software is built; it is not
   currently the deployed request route. The 512-row repeated-QSV measurement
   was 95,301 tokens; full arbitrary-QSV/4096-row capacity remains unaccepted.
3. Complete exact model artifact staging/runtime verification and actual Granite
   end-to-end tests. Reuse existing services and controller. The proposed
   SPEC-granite-live-run.md is design material, not a completed harness or a
   requirement to add unrelated wrappers.
4. Complete actual QSV source/mask/mapping policy, trained model/head/decoder and
   empirical calibration bindings, plus production throughput acceptance. Heads,
   bridge and category-free publication software are already built.
5. Complete typed venue adapters, provider fact collection/reconciliation and
   operational execution integration. The tested policy/outbox currently uses
   synthetic caller-attested observations and injected senders.
6. Use the correct frozen prior and rerun Sunday through the actual agent
   path, comparing only after independent outputs are filed. Paired runner/scorer
   software exists; empirical acceptance and held-out reveal do not.
7. Coordinate Claude's narrow contract implementation in parallel, then implement
   the static authority map once the model-seam finding is resolved. Reconcile
   the earlier C3/C4 addendum after initial-sheet work as previously instructed.
   Do not claim documents are implemented merely because they were read.

The compact service/controller slice has a saved SPEC-granite-compact-service.md
only. No route module, service methods, controller changes or tests for that slice
were written before the owner requested this closeout. The agent-file exporter
and receiver are likewise a saved plan only, not an implemented integration.

The forecast contract stays category-free: no low/medium/high labels, no minimum
score cutoff, publish the sole valid or best comparable candidate, update every
registered horizon while preserving absolute targets and revisions. Nullable
confidence is approved. Model changes remain distinct from ordinary new-data
updates. No training, new data purchase/acquisition, held-out reveal or live
order submission is implied by the model integration authorization.

## Granite/AWS facts

Granite 4.2 8B is definitely in the final design. Self-hosted AWS is the recorded
route; Bedrock is not required. Existing ShadowService names are historical names
and must not reduce the owner's full integration requirement.

- Private AWS instructions: `C:\Users\A\Downloads\DROP_IN_CODEX.md`.
- Use us-east-1 and its exact frankie-granite42 resource prefix/role/bucket scopes.
- Credentials already exist in GitHub secrets. Never ask for or print AWS keys.
- Last read: workflow 34871775747 attempt 2 saw the role and resolved vLLM; target
  ml.g6e.2xlarge endpoint quota was zero, increase to two pending. Recheck current
  quota/rate before provisioning. No GPU resource or real inference exists yet.
- Candidate image digest:
  `sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.
- Model revision: `ibm-granite/granite-4.2-8b` at
  `f8de16cdcdbc6c779ca517604e050d82cc119e44`.
- Exact model weights have not been downloaded/verified/staged. Tokenizer-only
  diagnostics are not proof of a running model. Quota is not the only unfinished
  software item. Private account IDs/ARNs stay outside Git.

## Claude document status

The original R1-R5/O1-O6 review has implementations or explicit constraints in the
predecessor handoff. The addendum at
`C:\Users\A\Downloads\CLAUDE_REVIEW_ADDENDUM_230c648_2b44b4e_20260914.md`
was read for overlap and remains deferred until initial-sheet completion. C1,
C2's honest interim and C5 overlap newer work; C3/C4 require reconciling preserved
predecessor edits. Do not discard those edits or change historical-read behavior
casually. A returned architecture ruling HAS NOW BEEN RECEIVED, distinct from the
older request at 3cfbf5c4. Supplied inputs are preserved in this packet's references:

- CLAUDE_ARCH_RULING_NOOA_CONTEXT_RETRIEVAL_20260914.md from teacherfiles.zip;
  also preserve the user's separately pasted ruling, rather than assuming the
  two files are byte-identical.
- CODEX_HANDOFF_NOOA_SLICE1_STOP_20260914.md.
- The original native forecast review, addendum, byte-distillation memo and
  RESEARCH_STATUS_20260914.md inside teacherfiles.zip.

The ruling narrows A-59 to contract packaging, A-63 to existing legacy retrieval,
A-65 to a proof method and A-66 to a static authority map. It rejects specialist
priors, standalone tree search, a native knowledge-retrieval layer, runtime
arbitration and a NOOA framework. Proposed non-recency selection and scored-history
publication feedback remain deferred; do not infer them from the combined build.

Slice 1 found protected legacy BLD-1 prompt fields (11) differ from BOSS additive
S120/S121 final fields (12, including disposition). The adapter docstring supports
distinct seams, but the full caller trace and corrected conformance proof remain
Claude's assignment. Do not patch frozen BLD-1 or invent a postprocessor.

The teacher archive is synthetic research material. Its six-column-unbuilt claim
is stale: R3 raw/normalized attachment and controls are already implemented. D0-D5
empirical evidence is still absent. C32/D6/D7 and hidden-state distillation are
conditional later proposals; EOT byte-text conversion is rejected. Hidden-state
export must not become a prerequisite for required Granite critique integration.
The archive lacks the cited research scripts/CSVs; operator_runs.xlsx and PNGs do
not alone establish a reproducible BOSS/OD result. See the teacher reconciliation.

## Claude Code assignment and concurrency

The owner received CLAUDE_CODE_DROP_IN.md for manual paste. It assigns an isolated
branch/worktree from de27bb26 to resolve the 11/12-field finding and implement
byte-preserving contract packaging for ALL THREE Granite prompt variants:
serialized V2, native V1, compact native V1. It requires genuine parser dependency
identity, unchanged prompt bytes, tests and a returned commit/patch for integration.
Claude must preserve de27bb26's reference bounds fix.

The automatic local Claude Code read-only attempt FAILED with HTTP 401 expired
OAuth, zero model usage and no edits. No Claude implementation/result/commit was
received here. Check whether the manual assignment has started or returned before
duplicating its files. Codex owns compact service/controller routing, BOSS-to-agent
file integration, build-map updates and later addendum reconciliation. Prompt and
parser identity helpers overlap those tasks, so integrate isolated commits carefully.

No frankie-claude.md was created. The later 18files.zip mention was part of the
wrong-recipient message and was not opened or incorporated into this build.

Proceed autonomously on authorized implementation and verification. Use parallel
agents for independent bounded slices/review, preserve other checkouts, and commit
reviewed increments. Keep the build map truthful about real integration versus
synthetic test evidence.
