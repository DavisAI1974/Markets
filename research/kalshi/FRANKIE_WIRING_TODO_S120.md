# FRANKIE WIRING TO-DO — S120 (2026-09-02)

**The rule this list serves (Greg, verbatim intent):** Frankie receives every record of every
field for the day being run, delivered exactly as it arrives in real time (F_LAST-closed groups
in `ts_recv_ns` order, visible only when their F_LAST is received, never ahead). He computes the
sixteen calculation-contract sections himself. The runner captures, retains and proves nothing
was dropped. Its calculations are not his evidence.

**How an item gets checked off:** a row in a real run's delivery table that names the layer,
the file or field that carried it, and the receipt hash. Not a test alone, not a sentence in a
handoff, not "the code is there". If the table does not have the row, the box stays open.

**Measured on the Sunday run 33630348943 before this list was written:** 99 registered layers;
78 are inputs to the principal, 75 apply to A-clean; **2 of 75 reached him** (mission, contract).
91 of 99 layers bind their evidence hash to one markdown inventory document, so the pre-call
gate proved the document was unchanged and nothing about delivery.

## The list

- [x] **1. Raw-MBO causal stream to Frankie (55 layers) — BUILT and merged (`80f8b33`); the delivery ROW from a real run is still pending the workflow's first successful fire.** `CausalGroupStream`: one group at a
      time, byte-identical rows, no peeking, lifecycle/legacy rows attached only at or before the
      cutoff, every group through `validate_causal_group_delivery_receipt` (existed, never
      called). Session-side fetch verifies gz length vs S3, plain bytes vs the box's `wc -c`,
      sha256 vs `PLAIN_SHA256SUMS`. *IN PROGRESS (test-engineer persona, own worktree).*
- [x] **2. Frankie computes the sections himself — mission sections 2 and 5 rewritten, spawn says so, result file is not his evidence (`80f8b33`).** Mission section 5 rewritten; the
      spawn prompt says so; `calculation_result.json` is not his evidence and is compared only
      after he files. *IN PROGRESS (same persona).*
- [ ] **3. Frozen learned structure to Frankie (9 layers, DIRECT). The proposal lineage goes in WHOLE; disregard its "do not promote" language (Greg); every lesson carries VERIFIED / UNVERIFIED / REFUTED, Frankie verifies against the stream, only the refuted comes out.** D structures and families,
      dipoles and geometry, pair/triplet recurrence, chains/extensions/reappearances/ancestry,
      phase-1 discoveries and falsifiers, phase-2 findings/timing/POX/negatives, predecessor and
      unresolved-chain state, historical timing as context, and the proposal/index material
      (`NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md` + addendum). Each registry entry rebound
      from the inventory document to its REAL file(s); each named in the spawn; each receipted.
- [ ] **4. Current brain runtime to Frankie (5 layers, DIRECT).** `knowledge/ng_brain.json`
      (s105.9, 90 plays), the S135 construction, doctrine/reasoning/play index, lawful prior
      carry, October outcome-wall enforcement. Same treatment as item 3.
- [ ] **5. Extra-agent carryforward (1 layer) and the binding inputs (manifest, profile, A-clean
      capsule; 3 layers).** Named in the spawn and receipted; the mission and contract already
      are.
- [ ] **6. The layer crosswalk.** For every one of the 99: registry id -> producing field,
      section or file -> delivery evidence in the run. Rendered from each run, not written by
      hand. The pre-call gate's per-layer status is computed from this, never read off the
      policy.
- [ ] **7. The spawn gate.** Refuse to spawn unless all 75 A-clean-applicable inputs carry a
      delivery receipt; refuse an artifact that says NOT_READ on a delivered ledger.
- [ ] **8. His output ledgers: the registry's ten as the FLOOR plus one per contract section (Greg: "ten" is an old number; no historical count is a spec), plus the 9a raw-MBO classification and the knowledge-verification ledger.** State/state-delta movie, reasoning
      movie, probability movie, candidate discoveries, first locks/no locks, negative/sparse/
      inconclusive ledger, knowledge-retrieval receipts, invocation receipts, answer-wall access
      receipts, source/state/manifest/code/run hashes. Defined in the return shape, required by
      the staging gate, rendered by the report. The one real spawn produced none of them.
- [ ] **9. The nine sealed layers stay sealed, proven.** A test on the delivery manifest and the
      emitted prompt that none of the nine ids or their objects reaches the session.
- [ ] **10. Register it.** F-20.. in `OPEN_ITEMS.json` for items 3-9; D81 (the rule) and D82 (the
      inventory-document binding) in the decisions store; renders regenerated.
- [ ] **12. The canonical input list, reviewed and updated.** The pair from 2026-08-24:
      `NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` (15 feeds; the registry's authority)
      and `NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md` (149 paths, sections A-M).
      Every section classified KEEP (knowledge he receives) / CODE (runtime, not knowledge) /
      SUPERSEDED (Sol/API era, four-helper era, D54/D63/D64/D70) / SEALED / OBSOLETE, each path
      with its reason, applied as a DATED addendum to the inventory, never a silent rewrite.
      The registry's knowledge layers rebind to the KEEP files.
- [ ] **11. Sunday, then Monday.** Fetch Sunday's ledgers into the session with the receipt;
      spawn; his report on the calcs and the raw MBO; STOP for the reveal (D68). Then Monday the
      same way.

## Already built and verified this session (not delivery; kept for the record)
4.0 per-second substrate; 4.0b detector coverage; the field census; mission 9a; the
evidence-read gate; the findings report render; F-16/F-17/F-18 joins; 1,406 tests green.
