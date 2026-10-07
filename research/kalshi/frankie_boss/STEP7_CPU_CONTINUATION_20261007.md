# Step 7 — owner-local Jev CPU continuation, 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Greg directed completing Step 7 while CCode finishes
Step 8. Jev uses an explicitly chosen worker subset of the SAME held 16-CPU day lane,
sequentially, with no separate host, fourth lane, Pod or new booking. This host policy is
settled; exact runtime/model pins, CPU count and runtime budgets still need supplied values.

Applied using-agent-skills, context-engineering, API and Interface Design and incremental
implementation. Reused the existing AWS CPU-threading/owner-local processing findings in
STEP7_MODULE_REVIEW_20261007.md. AWS reauthentication remains blocked in this session;
no successful new AWS skill/account call is claimed. No measured speedup is claimed.

## Built source boundary

`frankie_box_jev_cpu.py` and its existing-day-child shell wrapper provide an explicit-config
route. They do not provision, install, download a model or discover an external endpoint.
The helper validates the original host, live booking, exact 16 CPUs, source and selected
input hashes before creating its owner continuation. It locks that continuation. A changed
request/source/material/runtime/config requires explicit owner recovery, never replacement.

The blind client is reused, with an opt-in local adapter. Its legacy transport is unchanged.
The CPU route keeps outputs on its owner using the shared durable writer and exact-byte
readback. It pins the classroom's `jev_material` witness and supplies only its governed
attachments (including the experiment directive). A consuming-owner `claims-seal.json`
is written/read back BEFORE the comparison callback can read Frankie's artifacts. Later
scientific claim parsing checks the seal, exact claims/material and original client state.
A model-authored `blind` flag alone is insufficient.

The existing `LlamaServer` is reused ONLY as local CPU process, template/tokenizer and
bounded HTTP transport, never as Granite's meeting or prompt logic. Binary and model bytes
must be explicitly pinned. Runtime workers inherit the approved worker-only CPU subset,
with controlled inference threading; the helper restores its original affinity before
scientific work. Exact template/token counts and response usage govern prompt room; no
characters/3 estimate is used on this route. Completed token counts and replies replay.
Before a new model call the client writes its complete request intent. Unknown/failed
calls retain their exact request and transport evidence and refuse automatic replay.

The scientific stage calls the existing search loader, frozen standalone operation,
scientific test and writer. It tests the explicitly pinned owning-day search. The normal
cross-day accumulated-teacher path remains responsible for later legal retests on other
owners; this helper does not read another lane's giant search parts. A retained completed
result is validated and reused; repairing delivery does not repeat science or inference.
Both deliveries finish before the stage can return done: exact local Jev lesson readback
through his existing lesson reader, and exact Frankie `jev-tested` publication readback.
These are knowledge availability/readback witnesses, not a claim of a new model response
or native learning. The client pins all selected prior local Jev entries/lessons once,
retains older and conflicting knowledge, and does not select by market-date order.

The existing deterministic Jev report renderer has an additive CPU mode. It uses the
already-assigned day report number, local evidence references and CPU wording; it does not
allocate another number or call S3. The final report also references the actual scientific
result and both delivery witnesses. Private comparisons never enter Jev's brain.

## Caller contract (CCode owns Run.jev and main/class recovery)

Call `frankie_box_jev_cpu.sh` through the existing held-day child boundary, setting
`JEV_REQUEST` to an immutable absolute JSON request. Preserve MARKETS_SHA/CODE_ROOT and the
original day marker. Add `jev` to the existing `cores.DAY_RUN_STAGES` so this child uses
`cores run --inside` and inherits exactly the retained 16 CPUs; the helper refuses a wider
or narrower initial affinity. The wrapper checks the staged git commit and starts only the helper.
Missing runtime configuration is **waiting**, never skipped or done.

`JEV_CPU_REQUEST_V1` requires:

- `run`, `day`, `day_role: discovery`, `stamp`, original ROOT/day `attempt`, exact `owner`,
  `host`, `plan_sha256`, `slot_booking`, sorted original `cpus` (16).
- `source: {commit, code_root}`, exact `save_marker`, owner-local absolute `output`,
  Frankie `brain`, Jev `jev_brain`, and existing positive `report_number`.
- `classroom_receipt`, `search`, `runtime`: each `{path, bytes, sha256}`. The classroom
  receipt is the actual classroom producer receipt, not the orchestrator step receipt;
  search is that owning day's `MANIFEST.json`; runtime is the explicit config below.
- Optional `prior_brain`: exact owner-local copied prior Jev entry/lesson pins, each with
  `kind: entries|lessons` and optional stable `key`. This admits checked peer-owner material
  without traversing foreign absolute paths or opening Frankie's private answers. It is
  combined with local completed Jev entries/lessons and frozen before the first model call.

Persist this request BEFORE dispatch and reuse it byte-for-byte. Do not mint a new stamp,
attempt, output or config when uncertainty or a changed source refuses continuation.
The saved request plus output `owner.json` preserve the request, source and classroom
session identity; they are never reconstructed from the newest available work.

Runtime schema `JEV_CPU_RUNTIME_V1` requires `engine: llama.cpp-cpu`, binary/model pins,
`model_name`, explicit worker `cpus` inside original `cpus[1:]`, positive integer
`context_size`, `max_output_tokens`, `min_output_tokens`, `token_margin`, `piece_chars`,
`process_seconds`, and explicit `completion: {comparison: required, unparsed: listed}`
or `{comparison: required, unparsed: requires_review}`. `process_seconds` is the absolute
budget of each ephemeral process invocation, not a claimed cumulative lifetime budget.
Model/build/quantization identity and all these values must be real supplied choices; this
source task fabricates no hashes, token counts or CPU allocation.

Exit/receipt semantics:

| Result | Evidence | Parent action |
|---|---|---|
| 0 / done | `JEV_CPU_RECEIPT_V1` in `receipt.json`: original owner, blind seal, frozen scientific result, both deliveries, client/report pins | May satisfy Jev stage only for the exact retained owner/request. |
| 5 / waiting | Complete receipt with pending policy dispositions, or `JEV_CPU_STATUS_V1` status diagnostic with unresolved calls | Keep original owner and dependency pending. No retry of ambiguous calls. |
| 75 / saved | `JEV_CPU_STATUS_V1` in `status.json`, original owner/request, state pin, exact save-marker bytes when present, no unresolved model calls | Compare marker/request/child identity with Step 8's protocol; exit code alone is not acknowledgment. |

A caught stale/invalid invocation does not overwrite a completed result/day receipt.
Stop requests prevent new model phases and later scientific stages; a currently running
call completes under its existing deadline, retaining its reply before saving. A pending
call is waiting/unknown, not saved. No marker is deleted and no booking/claim is released.
CCode must verify the receipt/status and original child identity in his retained save
protocol, and keep Jev waiting until required config/wiring and comparison disposition are
resolved. His caller integration is a separate owned source boundary.

## Remaining concrete setup and verification

Supply pinned CPU runtime/model files (including quantization identity), the worker subset,
context/output/chunk/time budgets and unparsed-response completion policy. No deployment or
runtime verification occurred. The source route is explicit and refuses missing choices;
legacy Qwen3-8B/Pod strings do not supply verified CPU artifacts.

The Granite transport owner supplied `cpu_only=True` launch handling (`--n-gpu-layers 0`)
and rejects configured threads beyond the inherited CPU affinity. This helper explicitly
requests that mode; the shared transport remains owned by Step 6.
CCode must wire Run.jev to this request/child contract and retain the same request on resume.
Cross-day Jev knowledge now uses the existing owner-version brain snapshot transport in
an isolated `jev-peer/<day>-<stamp>/` namespace. Its immutable typed manifest is written LAST
after both exact own-entry and teacher-lesson members; incomplete copies are not published.
`lane_state.snapshot` transports that namespace without adding generic brain entries.
Frankie's existing entry globs do not descend there, so raw Jev claims stay out of his corpus
and teacher seats. The next Jev turn selects typed peer entries across the existing synced
knowledge roots, applies checked corrections, and freezes exact bytes before inference.
Source duplicates across mirrored versions are one publication, never independent evidence.
The caller must execute the normal existing knowledge boundary before Jev and after completed
publication, including a completed publication whose comparison disposition still leaves the
stage waiting; no separate directory share, provider route, scheduler or RPC was added.
One real E2E remains separately authorized after wiring/discussions. Then one-day inspection,
review/adjustments, and three days; thirty days remain a separate decision.

Verification here: direct source/interface review and AST without project imports, plus
`git diff --check`. No tests, models, data/science runs, runtime start, provider operation,
installation, historical rework or AWS execution occurred. No new validators/frameworks.

Independent source review found and closed required classroom comparison evidence and
unparsed-comparison completion gaps. It approved the isolated peer namespace and manifest-last
snapshot delta. Merged peer, explicitly supplied and local brain inputs now deduplicate exact
`(kind, sha256)` copies while preserving different hashes and conflicting knowledge. Publication
to GitHub is performed separately by the coordinating agent; this report alone does not claim it.
