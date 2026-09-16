# Addendum for Claude — token condensation and avoiding 19-cycle rebuilds

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-lawful-recovery-clean-20260915`

This is intentionally a short architecture addendum. Please answer these two questions, challenge the proposals below, and then collapse this sheet with the existing recovery/review sheet into one combined document.

Scientific constraints stay unchanged: no silent dropping, truncation, averaging, smoothing, normalization, causal leakage, or weakening of Frankie inputs/calculations/planes/Memory A. All retained evidence must still reach computation. The goal is to reduce repeated representation/work, not remove evidence.

## 1. Additional token-condensation opportunities

My current view is that there is still meaningful room beyond the compact/stacked work already done.

### A. Stop re-sending static material every cycle

Split the model packet into:

- one immutable, hash-bound run/day-group header containing schemas, field dictionary, instrument/session metadata, policies, static instructions and other material that does not change across the 19 cycles;
- a per-cycle packet containing only that cycle's causal state/delta plus references to the immutable header hashes.

If the model-serving path supports prefix/KV caching, keep the static prefix resident rather than rebuilding/reprocessing it for every cycle.

### B. Exact delta packets between consecutive cycles

The 19 cycles are cumulative. Cycle N+1 should not need to text-serialize everything cycle N already showed if we can provide:

- prior-state/hash identity;
- every exact new/changed causal record since N;
- any exact state transitions caused by those records;
- a deterministic reconstruction rule that reproduces the same full N+1 state.

This must be lossless delta encoding, not summarization. If reconstruction does not byte/field-match the full packet, reject it.

### C. Replace verbose JSON repetition with a reversible compact grammar

JSON field names, enum strings and repeated object structure are expensive tokens. Define one hash-bound schema/codebook once, then encode rows with short field IDs / positional fields / compact enum IDs.

Example conceptually: transmit the schema once, then rows become compact tuples rather than repeating `ts_recv_ns`, `order_id`, `side`, etc. thousands of times. The decoder must be deterministic and reversible.

### D. Columnar/block serialization for repeated numeric evidence

Where the model-visible transport still serializes row-oriented evidence, consider a compact columnar block format:

- one field dictionary;
- arrays for timestamps/order IDs/prices/sizes/actions/etc.;
- exact validity/presence masks;
- explicit row ordering.

This can materially reduce punctuation/key tokens while preserving every value and exact order.

### E. Exact run-length/dictionary encoding of repeated values

Use lossless RLE/dictionaries for genuinely repeated values such as unchanged metadata, repeated enums, venue/instrument IDs, side/action codes, repeated book attributes, etc. Never coalesce distinct market events; only compress representation.

### F. Content-address exact deterministic intermediate products

Anything expensive that is a pure deterministic function of immutable inputs should be stored once and referenced by hash on later reuse. Candidates include exact context selection, prefix selection, teacher/QSV attachments, static prompt sections, parser outputs and other preparation products.

Important: cache keys must include every input/code/config element that can change the result. A cache hit must be equivalent to recomputation, not an approximation.

### G. Split weight-independent preparation from weight-dependent work

Claude already confirmed context preparation is weight-independent, but the current reuse contract binds it to the live checkpoint hash. I think this is unnecessarily preventing reuse.

Potential redesign after cycle 0 is stable:

- `SOURCE/PREPARATION RECEIPT`: binds source/cutoff/context selection/teacher/QSV/parser/code, but not model weights when the operation truly does not depend on weights;
- `MODEL RECEIPT`: separately binds the model/checkpoint used for forward/training.

That would allow exact cycle N+1 preparation while N trains, and reuse the same prepared source surface across clean reruns that have identical source/preparation identities.

### H. Keep full evidence native; minimize what Granite must tokenize

Granite is the critic/reasoning side, not the authority for native MBO reconstruction. We should be strict about not converting large evidence surfaces to text merely because they exist. Native Frankie should consume the full typed evidence; Granite should receive the smallest exact causal representation required by its contract, with hash references back to the complete native evidence.

Please identify any current Granite packet sections that duplicate information already deterministically represented elsewhere and could be replaced by a compact exact reference/delta without reducing what Granite can reason about.

## 2. Avoid rebuilding the 19 cycles for every new group of days

I think the right answer is to stop treating each day group as a bespoke 19-cycle build and instead create a reusable **day-pack / cycle compiler**.

### A. Separate the 19-cycle template from the day-specific binding

The reusable template should contain things that do not depend on the actual market day:

- number/order of cycles;
- stage graph;
- schedule semantics;
- cutoff policy;
- schemas/contracts;
- static prompt/policy material;
- model/runtime configuration that is intentionally shared.

For a new day/group, generate only a small binding containing:

- source/day hashes;
- actual timestamps;
- through-cursors/F_LAST boundaries;
- source-prefix hashes;
- session/day identifiers;
- per-cycle snapshot/view receipts.

That should turn “build 19 cycles” into “bind this new source to the existing 19-cycle template.”

### B. Build all 19 cutoffs in one source pass

The 19 prefixes are cumulative. Do not independently rescan/rebuild the source 19 times.

Create a single-pass multi-cutoff compiler that streams the source once in causal order and emits the receipts/index entries for all 19 cutoffs as those boundaries are reached.

### C. Prefer virtual immutable prefixes over 19 cumulative SQLite copies

This may be the largest opportunity.

Instead of physically materializing 19 increasingly large prefix databases, keep one immutable compact/full journal plus a cryptographically bound per-cycle prefix index/receipt:

- cutoff/through-cursor;
- prefix record count;
- prefix head hash;
- block range;
- optional final partial-block boundary;
- source journal hash/code identity.

Then a verified prefix reader exposes only blocks/rows <= that cycle's cutoff and refuses all future rows. If this can give the same leakage proof as the current physical snapshots, cycles 1..18 become tiny receipts/views rather than copied databases.

If physical isolation is still required, use content-addressed immutable blocks so cycle N+1 references all prior blocks and adds only new blocks instead of duplicating bytes.

### D. Build reusable source indices once per day

For each new day/day-group, compute and hash once:

- receive-time -> cursor index;
- F_LAST/group boundary index;
- entity/instrument cursor index;
- session/open/close boundaries;
- any exact context-selection index needed by the 19-cycle schedule.

The cycle compiler can then resolve cutoffs without replaying/scanning the complete source for every cycle.

### E. Create a content-addressed `DAY_PACK_V1`

One day-pack should hold or reference:

- immutable source journal/compact blocks;
- source lineage + hashes;
- source indices;
- 19-cycle binding/schedule;
- 19 prefix receipts/views;
- exact context-selection seeds where weight-independent;
- parser/teacher/QSV/code identities;
- restoration manifest.

Build a day-pack once. Clean vs Memory A, boss experiments, reruns and later analysis should reference the same day-pack when their source/preparation identities match.

For multi-day runs, compose existing day-packs by manifest instead of reconstructing each underlying day.

### F. Precompute preparation for all 19 cycles before paid/model work

If preparation is proven weight-independent, produce all 19 exact preparation surfaces ahead of training/model calls and seal them. Then the 19-cycle run spends time on model reasoning/training, not repeated source/context preparation.

This also enables the RunPod/EC2 overlap we discussed: while native cycle N trains, Granite-side work for N+1 can use the already-sealed N+1 preparation receipt.

### G. Reuse a golden initialized native state

If every new day-group begins from the same intended model/teacher/runtime initialization, preserve a hash-bound immutable “golden seed” checkpoint/state bundle. Starting a new group should restore/copy that known seed rather than reconstructing initialization machinery each time.

If the model is supposed to carry learning from one day to the next, then instead preserve the prior day-group's completed checkpoint as the explicit next group's start. Either way, initialization should be a restore operation, not a rebuild.

### H. Keep the native EC2 process warm across adjacent day groups when lawful

Once the first result-bearing path is stable, consider running consecutive day groups in the same pinned EC2 process/host so Python imports, model objects, static schemas, tokenizer/admission assets and immutable codebook/prefix structures remain warm.

Day/run authority still resets explicitly through new run/day bindings and checkpoint rules. This is a latency optimization, not state leakage.

## My priority order

The highest-value ideas to investigate first are:

1. **Virtual/content-addressed prefixes instead of 19 cumulative SQLite copies.**
2. **Single-pass 19-cutoff compiler + reusable `DAY_PACK_V1`.**
3. **Separate weight-independent preparation receipts from checkpoint/model receipts.**
4. **Static-prefix + exact per-cycle delta tokenization for Granite.**
5. **Compact reversible schema/columnar grammar to eliminate repeated JSON keys/tags.**
6. **Golden initialization/checkpoint restore and warm-host reuse across day groups.**

## Questions for Claude

Please review the current code and answer:

1. Which of these token reductions are already partly implemented, and what additional savings remain?
2. Where are we still duplicating the same information in the Granite/principal packet?
3. Can a verified virtual-prefix reader provide the same causal/leakage guarantee as physical prefix SQLite snapshots? If not, what exact invariant prevents it?
4. Can all 19 cutoff receipts/views be generated in one causal source pass?
5. Which current preparation outputs are genuinely weight-independent and safe to content-address/reuse across cycles or reruns?
6. What should the exact cache/day-pack key contain so reuse cannot cross a scientific identity boundary?
7. For a new group of days, what is the irreducible work that truly must be recomputed, versus work we are currently rebuilding only because of orchestration design?
8. Estimate the likely token, I/O, storage and wall-time savings of the top options, and recommend the smallest safe implementation sequence.

Please add your answers directly to this material, then collapse this addendum and the existing recovery/review sheet into one consolidated sheet for Greg.