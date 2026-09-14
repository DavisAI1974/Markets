# Claude architecture review request — NOOA, context management, retrieval, and the A-59/A-66 cluster

Date: 2026-09-14
Repository: `DavisAI1974/Markets`
Branch: `codex/boss-full-evidence-20260907`
Baseline when drafted: `7ef8139800bf596940b200887bab03adb5e5dae3`

## Purpose

Architecture review only. Greg will bring Claude's plan back to ChatGPT/Codex for implementation. Do not implement from this memo.

We recovered an older S115 research/architecture cluster, A-59 through A-66, that grew out of NVIDIA NOOA and adjacent context/scaffolding papers. Some ideas were never completed; others have since reappeared under different names in current Frankie/BOSS. The task is to decide what is already built, what is superseded, what should be dropped, and what small pieces are still worth adding to the current architecture.

Do not revive the old A-E day-class specialists. A-62 originally referred to Weekend Seam / Monday / Core Tape / EIA Thursday / Friday-Expiration specialists. The current native forecast path is category-free. Translate any useful principle away from specialist personas into current model/arm/candidate reliability or discard it.

## Research papers

### 1. NVIDIA NOOA — Native Python Object-Oriented Agents

Paper: NVIDIA-labs OO Agents: Native Python Object-Oriented Agents
arXiv: https://arxiv.org/abs/2607.20709

Core idea: the agent is a Python object. Fields are state, methods are actions, docstrings are prompts/instructions, and type annotations are contracts. Methods whose body is `...` may be model-completed while ordinary methods stay deterministic Python. The architectural value is that prompt, state, contract, deterministic behavior, and model boundary live with the same software object rather than being scattered across templates, schemas and orchestration glue.

The pieces that originally mattered to us were:
- typed I/O enforced at emission;
- prompt/instructions live with the machine, reducing orphaned prompt/schema behavior;
- deterministic methods versus model-completed methods are explicit;
- object state is inspectable and governable.

Current overlap: Frankie/BOSS already has strong typed schemas, immutable artifacts, exact model/config/code identities, reversible native input mapping, context/publication receipts, fail-closed boundaries, and explicit deterministic/model separation. The potentially unfinished part is the packaging principle: prompt + state + contract + model-callable operations are still distributed across modules rather than owned by one coherent governed object.

Claude question: should we adopt a NOOA-inspired packaging layer without changing the underlying model architecture, evidence flow, Memory A, or current forecast contract? If yes, define the smallest brownfield form and exact owning seam.

### 2. Sculptor / Active Context Management

Paper: Sculptor: Empowering LLMs with Cognitive Agency via Active Context Management
arXiv: https://arxiv.org/abs/2508.04664

Core idea: context is not an append-only transcript. The agent gets explicit operations for fragmentation, summarize/hide/restore and intelligent search, allowing it to manage a working set while older material remains externally recoverable. The goal is to reduce proactive interference on long-horizon tasks.

Our required adaptation is stricter: **declared offload**. Anything not model-visible must be explicitly receipted and reversible. Nothing may silently disappear and later read as zero, absent, unchanged, or deliberately masked.

Current overlap: complete journal retention, `ContextSessionRunner`, outside-context counts, context receipts, Memory A, 90/90 brain preservation on legacy Frankie, `play_index`, rolling forecast revisions, causal packet history and governed QSV/ReFRAG.

Possible missing piece: intelligent, governed recall of retained knowledge/evidence into the active reasoning context rather than only fixed windows/static serving rules.

Claude question: is a small recall/retrieval layer justified? If so, where should it live, what may it retrieve, what is always retained, and what exact receipt proves what the model did and did not see?

### 3. Context as a Tool

Paper: Context as a Tool: Context Management for Long-Horizon SWE-Agents
arXiv: https://arxiv.org/abs/2512.22087
ACL 2026: https://aclanthology.org/2026.findings-acl.1032/

Relevant principle: separate durable task semantics, condensed long-term memory, and recent high-fidelity working context, while making context management itself an explicit action. This supports the store / index-retrieval / active-serving separation we independently converged on.

### 4. Language Agents as Optimizable Graphs

Paper: Language Agents as Optimizable Graphs
arXiv: https://arxiv.org/abs/2402.16823

Core idea: represent agent systems as computational graphs whose nodes perform operations/LLM calls and whose edges carry information; optimize both node behavior and orchestration/connectivity.

Historical relevance: this sat in the same full-scaffolding literature cluster as A-64 branching refine.

Current overlap: native B0/B1, B1 recurrence/halting, Granite bounded shadow critic, teacher path, controller/consumer boundaries, paired-arm locks and explicit causal/publication receipts. Do not rebuild Frankie as an automatically self-optimizing graph unless a concrete missing capability remains after comparing with B1 + Granite + current candidate selection.

### 5. Gödel Agent

Paper: Gödel Agent: A Self-Referential Agent Framework for Recursive Self-Improvement
arXiv: https://arxiv.org/abs/2410.04444

Core idea: an agent can recursively modify its own logic/behavior under higher-level objectives.

Most of this should probably remain outside Frankie. Frankie deliberately uses bounded proposal-based self-improvement: production code, model identity, Memory A, evidence contracts and authority do not silently rewrite themselves. The useful lesson is that the improvement mechanism itself can be evaluated, not that production Frankie should recursively rewrite itself.

## Historical items to adjudicate

### A-59 — NOOA scaffold / hybrid object

Original intent: agent-as-render-target with typed I/O, prompt living with code/object, explicit state, deterministic methods, and model-completed methods. Later combined conceptually with ACM so NOOA was “what the agent is” and ACM was “what the agent does over time.”

My view: **partially absorbed, still worth evaluating.** Do not adopt NVIDIA's runtime wholesale. The useful remaining piece is likely organizational: one governed Python object owning the agent-facing prompt/instructions, typed state, input/output contract, deterministic helpers, and explicit model-call seam.

### A-62 — specialist priors

Original intent: derive a long-term prior/track record for each old A-E specialist from measured outcomes.

My view: **old mechanism should not return.** The day-class specialists are not the current architecture. Translate only the underlying principle if current reliability diagnostics/comparable-candidate scoring do not already cover it. Candidate replacement concept: governed model/arm/mechanism reliability by state, never persona priors.

### A-63 — retrieval kernel

Original intent: make external brain/memory retrieval selective and task-relevant rather than always serving everything equally. Historically this sat under tools/retrieval and was blocked by the older library-index work.

My view: **potentially useful in translated form.** Everything must remain retained and auditable. Retrieval may rank what enters the active reasoning working set; it must never become destructive compaction or a silent knowledge filter. A receipt must name the available corpus, retrieved identities, omitted identities and reason/policy.

### A-64 — branching refine

Original intent: produce multiple candidate reasoning/refinement branches and select among them instead of one linear chain.

My view: **probably superseded.** B1 recurrence/halting, Granite criticism, current comparable-candidate selection and rolling forecast revisions already cover much of the purpose. Add explicit branching only if Claude identifies a concrete decision-quality capability missing from the current stack.

### A-65 — validated compaction

Original intent: change a served view only after proving on the same state/actual/brain that the compacted view does not damage the decision/posterior. It was a validation discipline as much as a feature.

My view: **keep the method, probably drop the old runtime component.** Current rules are stricter: preserve raw evidence, 90/90 brain where applicable, and exact outside-context accounting. The surviving principle is useful for reducing duplicated prompt/scaffold text or changing serving policy, but never as permission to delete plays, raw MBO, Memory A, or unique knowledge.

### A-66 — ownership / collision contract

Original intent: classify improvements by what organ they mutate so additive mechanisms do not get mistaken for competitors and overlapping writers do not silently fight. Historical split included brain store, derived priors/index, serving policy, tools/retrieval and control logic.

My view: **mostly absorbed.** Current BOSS has explicit component authority, frozen Memory A, separate causal/audit authority, separate native input/teacher/model/critic/controller roles and identity-bound receipts. Preserve the principle as an invariant and only add machinery if a real unresolved writer collision exists.

### D8 brain merge

Original intent: findings do not directly edit `ng_brain.json`; they become proposals, are adjudicated, then enter permanent brain knowledge with provenance.

My view: **the principle survives, old mechanism may be superseded by newer knowledge/Memory governance.** Keep adjudicated promotion, provenance, immutable prior evidence and separation of proposed findings from protected Memory A. Do not reintroduce a second competing memory-write path.

## Current architecture facts Claude should preserve

Treat current repository truth as authoritative, not this memo's historical shorthand. In particular preserve:
- complete native MBO retention and exact native-field computation paths;
- no silent dropping, truncation, averaging/smoothing/normalization of raw evidence;
- B0/B1 controls and native B1 authority;
- Granite as bounded shadow critic under the current B2_GATED design;
- dipole teacher/training boundaries;
- protected Frankie/S121 and BLD-1 boundaries;
- immutable Memory A and clean-vs-memory arm identity;
- causal/answer walls and exact receipts;
- category-free native forecast path and approved 12-field nullable interface;
- immutable rolling revisions and publication consumer checks;
- paired-arm locks, durable paired execution/reveal/scoring and crash recovery;
- no production/provider/training/held-out/live-execution authorization from this review.

## Requested architecture output from Claude

Please return an architecture disposition, not implementation code.

For each of **A-59, A-62, A-63, A-64, A-65 and A-66**, state:
1. what the original mechanism actually was;
2. what current Frankie/BOSS component(s) already cover it;
3. what is still missing, if anything;
4. whether the old item should be **BUILT/translated**, **SUPERSEDED**, or **DROPPED**;
5. if anything remains, the smallest brownfield design and exact owning module/seam;
6. invariants/tests needed to prove it does not change protected Frankie behavior or silently hide evidence;
7. build order and dependencies if more than one piece survives.

Please explicitly decide these two likely survivors:
- NOOA-inspired governed Python-object packaging;
- lossless/governed active retrieval or recall into the reasoning working set.

Also explicitly say whether current reliability diagnostics already make translated A-62 unnecessary, and whether B1 + Granite + comparable-candidate selection already make A-64 unnecessary.

## Final registry closeout requirement

After Greg approves Claude's architecture disposition and ChatGPT/Codex completes the approved implementation, the historical S115 entries must be closed. Do not leave them OPEN indefinitely.

For **A-59, A-62, A-63, A-64, A-65 and A-66**, update `research/kalshi/OPEN_ITEMS.json` to a terminal truth state:
- `DONE` only if the approved capability is actually built and verified; or
- `SUPERSEDED` when the old mechanism is intentionally dropped/replaced because its premise no longer applies or current architecture already covers it.

Do not mark an item DONE merely because its idea appears in prose. Do not leave a rejected idea OPEN. Record the replacement component or governing reason in the entry so future sessions cannot rediscover and rebuild the same historical item.

Where a useful method survives but the old component does not (for example A-65 validated-compaction as a validation discipline rather than a runtime subsystem), close the old item as `SUPERSEDED` and name the current mechanism carrying the surviving principle.
