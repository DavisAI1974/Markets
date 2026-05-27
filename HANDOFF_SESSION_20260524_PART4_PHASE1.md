# Handoff — Part 4: Phase 1 build to arch spec v2.1 (2026-05-24/25)

Continues from `HANDOFF_SESSION_20260524_PART3.md`. PART3 said the next chat
should run the control plane against the discoveries we have. This chat
discovered Phase 1 had foundation gaps that blocked that work, and rebuilt
Phase 1 to spec instead. Phase 1.B is fully done. Phase 1.C is partially done
(orchestrator wired; migration of legacy discoveries still pending).

## NEW-CHAT DIRECTIVE — read this first

**Finish Phase 1.C, then verify Phase 1 milestone, then move to Phase 2.**
Authoritative spec: `E:\refrag\docs\architecture_spec_v21.docx` (text dump at
`E:\refrag\_arch_spec_v21_extracted.txt`). Follow it EXACTLY, no shortcuts.
Greg's framing from this chat: *"i want us to follow the pipeline exactly how
it was laid out in architecture doc"* and *"no short cuts."* Don't run the
control plane against discoveries until Phase 1 is closed — the registry
indexes + discoveries layout are direct prerequisites for gap_finder +
cross_domain_transfer_detector.

**Always check before creating new files** — Greg's specific concern: *"or did
you not check refrag folder first to make sure that files didn't already
exist."* Pre-check with `ls` or `Grep` for the proposed name before any
`Write`. See "Lesson learned" section.

## TL;DR

- **Arch §3.1 directory structure now exists on disk** at `E:\refrag\registry\`.
  - `registry/manifests/` (22 files, moved from top-level `manifests/`)
  - `registry/embeddings/{operator_embeddings.faiss, embedding_metadata.json}` (deterministic hash n-gram, 128-d, python backend until faiss is installed)
  - `registry/capability_index/{capabilities, input_types, output_types, domain_tags}.json`
  - `registry/dependency_graph/{graph.json, topological_order.json}` (bidirectional edges, Kahn topo sort matching arch §6 dep table)
  - `registry/lineage/` (3 state files moved from `artifacts/control_plane/lineage/`; 973 + 47 + 3357 history entries preserved)
- **Data-type schemas wired**: `schema/spectral_chunk.schema.json`, `schema/operator_candidate.schema.json` plus manifest validator type-reference resolution (fails fast on unresolved custom types).
- **Orchestrator writes discoveries per arch §4** (in production / default mode): `discoveries/operator_discoveries/<domain>/<run_id>.json`. Sandboxed scenarios (`OperatorOrchestrator(artifacts_dir=...)`) keep the flat legacy layout to stay under Windows MAX_PATH=260 when nested under pytest tmpdirs.
- **Domain plumbed through 4 callers**: `markets="markets"`, `quantum="quantum"`, `markets_inflight_predictor="markets_inflight"`, `refrag_mcp/server="mcp_external"`. Default = `"unknown"`.
- **3 new tests + 125/125 suite green**: `tests/test_registry_build.py` (19 tests) plus all existing tests pass after the path migration.
- **Arch doc bug logged**: §6 prose "Topological Build Order" is internally inconsistent with §6 dependency table. Manifests match the table; the prose listing is stale. Specifically:
  - `operator_query` per prose: depth 1; per table+manifest: depth 2 (deps on `spectral_chunk_encode`)
  - `operator_chain_builder` per prose: depth 2; per table+manifest: depth 1 (deps only on depth-0 ops)
  - `operator_orchestrator` per prose: depth 3; per table+manifest: depth 4 (deps on `task_meta_learner` at depth 3)
  - `operator_graph_rewriter` per prose: "Depth 4 (build last)"; per manifest: depth 3 AND not the deepest — `cross_domain_transfer_detector` is depth 5, `od_spectral_retrieval_pipeline` template is depth 5.

## What shipped this session

### Phase 1.A — type schemas + validator (DONE)

- `E:\refrag\schema\spectral_chunk.schema.json` — mirrors the `SpectralChunk` dataclass at `adapters/od_refrag_adapter.py:42`.
- `E:\refrag\schema\operator_candidate.schema.json` — mirrors the `OperatorCandidate` dataclass at `adapters/od_refrag_adapter.py:75`.
- `E:\refrag\refrag_discovery\registry\manifest_validator.py` — added `load_data_type_registry()`, `_resolve_leaf_type()` (handles `array<...>`, `map<K,V>`, `enum(...)` wrappers), `validate_type_references()`. Manifests now fail fast if they declare `array<NonExistentType>`.

### Phase 1.B — registry storage per arch §3.1 (DONE)

- `E:\refrag\scripts\build_registry_indexes.py` — derives dep graph + topo order + capability/type/domain inverted indexes from manifests. Idempotent.
- `E:\refrag\scripts\build_registry_embeddings.py` — builds FAISS-or-python-backed manifest embedding index using deterministic hash n-gram (no training, no external model) per Rule 5. Defaults to dim=128.
- `E:\refrag\refrag_discovery\paths.py` — added `REGISTRY_DIR`, `MANIFESTS_DIR`, `EMBEDDINGS_DIR`, `CAPABILITY_INDEX_DIR`, `DEPENDENCY_GRAPH_DIR`, `LINEAGE_DIR`, `DISCOVERIES_DIR`. `MANIFESTS_DIR` now resolves to `registry/manifests/` (was `manifests/`).
- `E:\refrag\refrag_discovery\control_plane\storage.py` — `operator_state_path("lineage", ...)` routes to `registry/lineage/` by default; other kinds stay under `artifacts/control_plane/<kind>/`. Sandboxed callers (`artifacts_dir=...`) still get per-scenario isolation.
- File moves:
  - `manifests/*.json` (22 files) → `registry/manifests/*.json`
  - `artifacts/control_plane/lineage/*.json` (3 files) → `registry/lineage/*.json`
- `E:\refrag\tests\test_registry_build.py` — 19 tests covering the layout, dep graph bidirectionality, topo sort no-forward-refs, type indexes, embeddings round-trip + self-retrieval, lineage routing, idempotent rebuilds.

### Phase 1.C — discoveries storage per arch §4 (PARTIAL)

DONE:
- `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py`:
  - Added `domain: str = "unknown"` kwarg to `execute()`.
  - Production runs write to `discoveries/operator_discoveries/<domain>/<run_id>.json`.
  - Production evidence graphs write to `discoveries/evidence_graphs/<pipeline_id>.json`.
  - Sandboxed runs (`artifacts_dir=...`) keep the flat legacy layout for MAX_PATH safety.
- `E:\refrag\refrag_discovery\runtime\od_spectral_retrieval_pipeline.py` — `execute_pipeline()` now forwards `domain=` to the orchestrator.
- `E:\refrag\adapters\markets_refrag_adapter.py` — `domain="markets"`.
- `E:\refrag\adapters\quantum_refrag_adapter.py` — `domain="quantum"`.
- `E:\refrag\adapters\markets_inflight_predictor.py` — `domain="markets_inflight"` (keeps inference probes partitioned from validated winners per Rule 8).
- `E:\refrag\refrag_mcp\server.py` — accepts `domain` in MCP arguments, defaults to `"mcp_external"`.
- Smoke test: synthetic 200-sample series → `execute_pipeline(domain="markets_smoke")` → file lands at `discoveries/operator_discoveries/markets_smoke/<run_id>.json` with `"domain": "markets_smoke"` in payload. Evidence graph at `discoveries/evidence_graphs/od_spectral_retrieval_pipeline.json`. Nothing leaks to legacy `artifacts/discoveries/`.

PENDING:
1. **Migration script** for 3475 files at `artifacts/discoveries/*.json` into `discoveries/operator_discoveries/<inferred_domain>/<run_id>.json`. Domain inference rules (from earlier sampling):
   - `source_id` contains `BTC|`, `_bybit`, `_coinbase`, `_kraken` → `"markets"`
   - `source_id` contains `spin-boson`, `2_epsilon`, `twobath`, `sb_` → `"quantum"`
   - `source_id` starts with `od_disc_`, `series_a`, `series_b` → `"fixture"`
   - else → `"unknown"`
   - `source_id` lives inside `result.evidence_graph.nodes[].metadata.source_id` (or similar) — walk the discovery payload to extract it.
   - Migration must be REVERSIBLE: keep the legacy `artifacts/discoveries/` until verification passes, then archive (not delete).
2. **`scripts/build_discoveries_index.py`** — scan `discoveries/operator_discoveries/<domain>/*.json` and emit `discoveries/index.json` keyed by `run_id` → `{path, domain, pipeline_id, recorded_at}`. Idempotent rebuild (same pattern as `build_registry_indexes.py`).
3. **Stub subdirs**: `discoveries/cross_domain_transfers/`, `discoveries/pipeline_discoveries/` (empty `.gitkeep` is fine).
4. **Phase 1.C tests** — extend `tests/test_registry_build.py` or new `tests/test_discoveries_layout.py` covering: orchestrator default writes to correct subdir; sandboxed writes to flat legacy; migration script is idempotent; index builder covers all files.
5. **Phase 1 milestone verification** — run the chunk → encode → query → lineage → discovery round-trip end-to-end with `domain="markets"` AND `domain="quantum"`, confirm both files land correctly, confirm `discoveries/index.json` updates.

### Other findings

- **Arch doc §6 prose-vs-table inconsistency** — flagged above. Recommend updating the prose listing to match the table (which matches the manifests). Specifically: `operator_query → depth 2`, `operator_chain_builder → depth 1`, `operator_orchestrator → depth 4`, drop the "depth 4 build last" claim about graph_rewriter (it's depth 3 and not the deepest).
- **Codex/MCP softer than Rule 9 implied** — Greg's clarification this chat: *"codex doesn't have to read the manifests later. that's just a suggestion, not demanded."* Don't over-engineer MCP exposure during Phase 1; the existing `visibility` field on manifests is enough.
- **No git in use** — confirmed again. `git status` shows 119 dirty files; intentional per `feedback_periodic_git_push.md`. Mirror artifacts across dirs (OD KB + Markets KB) instead of relying on git.

## Lesson learned (record for future chats)

I created `scripts/build_registry_indexes.py`, `scripts/build_registry_embeddings.py`, and `tests/test_registry_build.py` without first grep-ing the destination directories to confirm no pre-existing file would be overwritten. mtime evidence after the fact confirmed no collisions (my new files = May 24 today, all surrounding files = March 12), and `Write` would have errored if a name clashed — but Greg correctly called this out as a process gap. Going forward: **always `ls`/`Glob` the destination directory before any `Write` for a new path.** I did pre-check `schema/` and `registry/` subdirs before creating there; the gap was specifically `scripts/` and `tests/`.

## Files of interest

| Path | Role |
|---|---|
| `E:\refrag\docs\architecture_spec_v21.docx` | **THE arch map. Authority for everything.** |
| `E:\refrag\_arch_spec_v21_extracted.txt` | Plain-text dump |
| `E:\refrag\schema\spectral_chunk.schema.json` | NEW — SpectralChunk wire schema |
| `E:\refrag\schema\operator_candidate.schema.json` | NEW — OperatorCandidate wire schema |
| `E:\refrag\refrag_discovery\registry\manifest_validator.py` | UPDATED — type-reference resolution |
| `E:\refrag\refrag_discovery\paths.py` | UPDATED — registry/discoveries paths |
| `E:\refrag\refrag_discovery\control_plane\storage.py` | UPDATED — lineage routing |
| `E:\refrag\refrag_discovery\runtime\operator_orchestrator.py` | UPDATED — discovery domain routing |
| `E:\refrag\refrag_discovery\runtime\od_spectral_retrieval_pipeline.py` | UPDATED — domain kwarg |
| `E:\refrag\scripts\build_registry_indexes.py` | NEW |
| `E:\refrag\scripts\build_registry_embeddings.py` | NEW |
| `E:\refrag\tests\test_registry_build.py` | NEW — 19 tests |
| `E:\refrag\registry\manifests\` | MOVED FROM `E:\refrag\manifests\` |
| `E:\refrag\registry\lineage\` | MOVED FROM `E:\refrag\artifacts\control_plane\lineage\` |
| `E:\refrag\registry\dependency_graph\` | NEW |
| `E:\refrag\registry\capability_index\` | NEW |
| `E:\refrag\registry\embeddings\` | NEW |
| `E:\refrag\adapters\markets_refrag_adapter.py` | UPDATED — `domain="markets"` |
| `E:\refrag\adapters\quantum_refrag_adapter.py` | UPDATED — `domain="quantum"` |
| `E:\refrag\adapters\markets_inflight_predictor.py` | UPDATED — `domain="markets_inflight"` |
| `E:\refrag\refrag_mcp\server.py` | UPDATED — accepts `domain` arg |
| `E:\refrag\artifacts\phase1_audit_report.md` | NEW — Phase 1 gap report |
| `E:\refrag\discoveries\operator_discoveries\markets_smoke\` | smoke-test residue, can be deleted |
| `E:\refrag\artifacts\discoveries\` (3475 files) | LEGACY — awaiting migration |

## Live constraints (carried forward + reinforced)

- **DO** follow the arch doc EXACTLY. No invented knobs, no shortcuts.
- **DO** pre-check destination directories before `Write` for new paths (lesson above).
- **DO** keep sandboxed scenarios (`artifacts_dir=`) on the flat legacy layout — Windows MAX_PATH=260 bites otherwise.
- **DO** treat manifests as authoritative when arch doc prose and table disagree.
- **DO NOT** enable `operator_graph_rewriter` (Phase 6, disabled until then).
- **DO NOT** push to git. Mirror artifacts across dirs instead.
- **DO NOT** appear as #1/#worst long or short on any public leaderboard.
- **DO NOT** invoke `markets_refrag_batched_adapter.py` (neutralized in part 2; will tag domain="unknown" if called).

## End of handoff

Next chat: finish Phase 1.C (migration + index + tests + verification), then audit Phase 2 against arch §8.
