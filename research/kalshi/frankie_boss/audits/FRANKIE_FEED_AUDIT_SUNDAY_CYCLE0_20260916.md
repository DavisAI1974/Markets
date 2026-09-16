# Frankie feed audit, Sunday cycle 0 (2026-09-16): what was actually ingested, layer by layer

Greg: "start tracking that down now and seeing what is actually being ingested." Read-only. No
Frankie, Granite, EC2, Pod or result-bearing run. Every number here is computed by Frankie's own
built tools in the frozen receiver checkout (commit `342f5728`) from the retained cycle-0 artifacts
and the delivery on disk; nothing was built, nothing was edited, and the three records beside this
file (`CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.md/.json`,
`SEALED_ABSENCE_PROOF_SUNDAY_CYCLE0_20260916.json`) are the tools' outputs verbatim.

## What "the 99" are

Frankie's ingestion layer registry, `native_ingestion_layer_registry.py` in the receiver package,
validated today: 99 union layers (105 before D64 removed the six helper-architecture layers),
A_CLEAN 96 / A_MEMORY 98 applicable, hard minimum 90, policy split 19 static required / 4 arm
required / 55 causal-stream required / 9 sealed / 2 provisional shadow / 10 append-only outputs,
layer-id set sha `fbb79cde…`, registry content sha `239a1480…`.

## Which run cycle 0 was actually fed

Not the run the last fed render on file documented. `LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md`
(9 of 77 inputs delivered) is for run 33630348943, the A_CLEAN arm, against an older registry
(`d6c72dfe…`; the registry changed twice since: `00c03db4` rebound 14 knowledge layers,
`78836cb4` bound the A-memory seed). The Sunday-15 host fed cycle 0 from run **33746436209**,
the **A_MEMORY** arm (`local_delivery_receipt.json`, fetched 2026-09-04): `calculation_result.json`
(29,089,413 bytes, sha `91e47d0d…`, verdict ACCEPTED, 57,027 records, 43,569 groups), the exact
member ledger (10,756,276,521 bytes plain), the exact lifecycle and runway ledger, the legacy
observable rows; through the receiver's `prepare_boss_attachment` (preparation receipt in the
retained cycle-0 principal directory), plus the knowledge bundle (248,922 bytes, sha `6f9dbb37…`,
the same bytes the session request attached), the frozen Memory A and the 18 preserved sections.

## The crosswalk, re-rendered against that delivery (the fed render for cycle 0)

`native_layer_crosswalk --enforce-gate`, A_MEMORY, with the delivery receipt, the stream receipt
(complete: true, run `frankie-a-memory-rt-33746436209-1`), the knowledge receipt (22 layers) and the
sealed-absence proof produced below. Gate: **passed**. Crosswalk sha `3c1db7e9…`.

| total | value |
|---|---:|
| registered | 99 |
| applicable (A_MEMORY) | 98 |
| inputs applicable | 77 |
| **inputs delivered** | **75** |
| principal-stamped (lock time, Frankie's own output, no ingestion producer by design) | 1 |
| degenerate proof (see below) | 1 |
| sealed proven absent | 9 of 9 |
| provisional shadow, disabled by policy | 2 |
| outputs pending (Frankie's ten append-only ledgers, correctly empty before a run) | 10 |
| carrier claim mismatches | 0 |
| no producer found | 0 |

By group, every market-data layer delivered: canonical raw DBN MBO 6/6, order lifecycle 9/9,
full-book FIFO queue 8/8, microstructure mechanics 7/7, legacy observable crosswalk 5/5, derived
geometry 8/8, prebirth opportunity 5/5, causal clocks 6/7 plus the stamped lock time. Every
knowledge layer delivered through the bundle: binding common controls 4/4, current brain runtime
5/5, frozen learned structure 9/9, corrected extra-agent carry-forward 1/1, A-memory overlay 2/3.

## The leak check

`native_sealed_absence.prove_sealed_absent` over the four surfaces Frankie receives: the cycle-0
prompt (28,303,442 bytes), the knowledge bundle, the knowledge paths and the delivered paths. The
sealed set is derived, never typed: 9 sealed layer ids, 4 section-K paths, 10 Step-1 identifiers,
23 tokens, set sha `2ad04788…`. **All absent, zero hits**, proof receipt `19af6d54…`.

## What is not closed, and whose it is

1. **The sealed-absence scan and the outputs receipt are built but not wired into the host path.**
   Nothing in `run_actual_sunday.py` or the receiver preparation calls `prove_sealed_absent`
   before the request or `native_principal_outputs.bundle_receipt` after the response; both were
   run by hand here. Until they are wired, every crosswalk of a live cycle reads nine sealed layers
   unproven and ten outputs pending, exactly as the 2026-09-03 render did. Wiring, not building.
2. **`a_memory_prior_package_proof` proves itself.** The A-memory seed carries its own per-entry
   hashes and its proof layer binds the same file, so the crosswalk marks it
   DEGENERATE_PROOF_SAME_AS_SUBJECT. It needs an independently produced receipt over the seed.
   Receiver-side; predates today.
3. **The ten append-only output layers are not produced on the BOSS path, by construction.**
   Cycle 0's retained response (14,280 bytes) carries `feedback` (29 timing labels through source
   cursor 6053), one `lessons` entry (the run analysis), the 18 preserved sections cited by hash,
   and the session identity; no output ledger. The BOSS session request instructs Frankie to
   "reuse the preserved Frankie-authored 18-section evidence with its original authorship; do not
   rerun completed calculations", while the registry's `append_only_outputs` group (and D81) has
   him compute every contract section himself as the stream advances and file a ledger per
   section. The two are different output surfaces: the receiver's `OutputBundle` belongs to the
   A-arm real-time path, and the BOSS feedback path never asks for it. So `outputs_pending = 10`
   on every BOSS cycle is a policy fact, not a wiring fault. Which surface the block run should
   fill is Greg's ruling; it is not a fix.
4. The classroom's audit directory and principal artifacts have no entry in `AUTHORITY_MAP.json`.
   Add them with a declared writer before the post-integration audit.
5. **The BOSS working branch carries stale copies of the two canonical inventories.** The canonical
   file list is `research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md` (149
   bullets, sections A-M; the receiver classifies them 63 KEEP / 68 CODE / 5 SEALED / 6 SUPERSEDED /
   7 OBSOLETE) with `NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` as the registry's source
   authority and `KNOWLEDGE_MANIFEST_20260828.json` pinning 76 artifacts by hash. Measured: all 76
   manifest hashes match on the receiver; 61 of the 63 KEEP files are byte-identical between the
   receiver checkout and the working branch modulo CRLF; the two that differ are the inventories
   themselves, and the RECEIVER's are the newer, corrected (D64) versions: the working branch's
   copies (last touched at `a7dd99e7`) still name "the four live D-finding helpers", keep the
   "Four live helper-evidence feeds" section, and omit ten file names the receiver's list carries
   (the role-context profiles, the Step-1 census method and protocols, the chain study contract,
   the Phase-1 discovery script, the Step-1 census scripts, the Step-1 completion gate). Cycle 0
   was fed from the receiver's corrected copies (the knowledge receipt's model-visible bundle,
   248,922 bytes, sha `6f9dbb37…`, is exactly what the session request attached), so the feed was
   right; the hazard is any future render from the working branch. Not touched here.

Nothing in the ingestion path was found dropped, filtered or rerouted. What the crosswalk
measures is exactly what the registry declares Frankie must be fed, and for cycle 0 it was.
