# Frankie A-Arm Review Findings

Date: 2026-08-29 UTC
Status: **EXTERNAL REVIEW RESPONSE — NOT A CONTRACT — NOT LAUNCH AUTHORITY**
Reviewing: `FRANKIE_A_ARM_INGESTION_REVIEW_PAPER_20260829.md` +
`FRANKIE_A_ARM_GOAL_OVERVIEW_FOR_REVIEW_20260829.md`
Method: every claim checked against the repository at commit `d5b7b51`, not read on its
own terms. Verification commands and counts are inline so each finding is reproducible.

## Verdict

**Does not pass muster yet.** The papers are well-structured and the doctrine is sound,
but four findings are load-bearing and two of them invalidate the experiment as currently
configured:

- **A-clean is not clean.** Its always-loaded capsule contains derived results about the
  held-out discovery days.
- **The arms differ in three ways, not one.** The retrieval catalogs are asymmetric in
  both directions.
- **The execution gate is stale and unwired.** It pins 24 surfaces against the
  registry's 97 concrete layers, in a disjoint vocabulary, and nothing calls it.
- **The boss-only-mutable design is not implementable today.** The model identifier is a
  hard-coded constant enforced in three places.

A fifth finding (3b) corrects §10's scope, four further Required items follow, and one
premise in §5.1 is simply wrong — the fact it asks for is already pinned in the repo.
Positives are recorded at the end, including one criterion the existing code already
meets and one enumeration that is faithful and complete.

**Correction to my own first pass, recorded because the pattern matters:** I initially
read the 93 registry entries pointing at the data-feed inventory as an 89% placeholder
rate. That was an over-claim. 93 is exactly that document's bullet count and the mapping
is faithful 1:1 — including two apparent shortfalls that turned out to be correct
relocations into `sealed_target_timing`. Nothing was dropped there. The defect is the
narrower one the paper already states, plus a missing class. See 3b.

---

## CRITICAL 1 — A-clean is not clean: held-out-day results are delivered at ALWAYS_LOAD

`KNOWLEDGE_MANIFEST_20260828.json` binds `a_clean_promoted_positive_knowledge`
(`A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md`, sha `53a42357…`) as `ALWAYS_LOAD` in profile
`RT_A_CLEAN_SECOND_PASS`. That file is not method guidance. It contains six numbered
findings derived from the held-out discovery interval, delivered before the first F_LAST
cutoff:

| # | Content | Why it is a leak |
|---|---|---|
| 2 | "October 5 is more bid-supported than October 4: mean full-depth imbalance 0.221155 vs 0.121056, mean bid depth +21.847%, bid orders +16.460%, bid levels +8.899%" | A cross-day comparison of both held-out days. Computable only after processing all of both. Delivered at cutoff zero. |
| 3 | "cancel-linked share is stable at 82.652%/82.495% by held-out day" | Per-held-out-day statistics, explicitly labelled as such. |
| 4 | "Same order `786260864394` exhibits `AN -> TFMN -> TFCN` … and a 20,400 ns inter-group gap" | A named order ID with its complete terminal lifecycle, before its F_LAST. |
| 5 | "Exact 21:00 UTC mass-withdrawal groups followed by approximately 2,706-second quiet intervals … October 5's withdrawal is larger and more bid-cancel-heavy" | Session-structure answers plus a cross-day comparison. |

This violates three of the papers' own rules simultaneously: §7.3 ("Future response …
must not leak into earlier calls"), §8 ("later causal evidence or completed outcome at an
earlier cutoff"), and the Goal doc's framing sentence — "once as `A-clean`, with no prior
Frankie memory."

Both capsules are prior-run derived. The experiment as configured is **prior-positive
memory vs. prior-positive-plus-full-chain memory**, not clean vs. memory.

**Remedy — pick one, do not leave it implicit:**

1. *Preserve the stated experiment.* Strip the A-clean capsule to arm-invariant method
   rules only. Findings 1 and 6 (the causal rule and the parallel-view rule) qualify;
   2, 3, 4 and 5 do not. Re-hash and re-register. Add a scrub gate the contract enforces
   at seal time: no held-out date string, no order ID, no numeric derived from held-out
   records, in any `ALWAYS_LOAD` artifact.
2. *Preserve the current knowledge.* Rename the arms to what they are
   (`A_PRIOR_POSITIVE` vs `A_PRIOR_FULL_CHAIN`) and rewrite the Goal doc's
   one-paragraph goal and comparison table to state the actual contrast.

Option 1 keeps the science. Option 2 keeps the artifacts. Doing neither ships an
experiment whose headline claim its own manifest contradicts.

## CRITICAL 2 — the arms differ in at least three ways, not one

From `KNOWLEDGE_MANIFEST_20260828.json` `profiles`:

| Profile | Retrieval catalog |
|---|---|
| `RT_A_CLEAN_SECOND_PASS` | `native_positive_discovery_addendum`, `a_clean_positive_family_inventory`, `a_clean_actual_rt_positive_report`, **`a_clean_extraction_opportunities`** |
| `RT_A_MEMORY_SECOND_PASS` | `native_positive_discovery_addendum`, `a_memory_actual_rt_positive_report`, **`a_memory_member_first_positive_findings`**, **`a_memory_member_first_recalculation_receipt`** |

Three uncontrolled differences, in both directions:

1. **A-memory only:** `a_memory_member_first_positive_findings` and
   `a_memory_member_first_recalculation_receipt`. These are *calculation outputs over the
   same four October 2021 files* — not prior-run lessons. No A-clean equivalent exists
   anywhere in the tree (`ls` confirms only `AMEMORY_MEMBER_FIRST_*` artifacts).
2. **A-clean only:** `a_clean_extraction_opportunities` (21,745 B) and
   `a_clean_positive_family_inventory` (8,335 B). No A-memory counterpart.
3. The same asymmetry repeats in the Forecaster profiles.

So A-memory carries extra *calculated evidence*, and A-clean carries extra *derived
findings*. The Goal doc's comparison table asserts everything but memory is "Identical".
It is not. §12's criterion — "A-clean and A-memory differ only in their permanently
sealed arm/profile/memory bindings" — cannot be signed off today.

**Remedy:** define the retrieval catalog by **slot**, not by file. Fix the slot set
(family inventory / RT report / extraction opportunities / recalculation receipt), give
both arms the same slots, and require that any slot one arm cannot fill is **empty in
both**. Reduce to the intersection rather than letting each arm carry whatever happens to
exist. Then the memory package is the only remaining difference, which is the experiment.

## CRITICAL 3 — the execution gate is stale: 24 surfaces against the registry's 97 layers

`corrected_a_arm_execution_gate_20260828.py` defines `SURFACE_IDS` as exactly **24**
entries, and `validate_rt_surface_inventory` hard-fails on
`set(by_id) != SURFACE_IDS`. Seven are in `MANDATORY_NATIVE_RT_SURFACES`.

The corrected A-arm ingestion layer count is **97**, and the two vocabularies are
**completely disjoint** — zero of the 24 gate surface ids matches any registry
`layer_id` or `group_id`. The gate is also wired to nothing: the only references to
`validate_rt_surface_inventory` / `RT_SURFACE_INVENTORY_V1` anywhere in the repo are the
module itself and its own test. No launcher or workflow calls it.

The 24 list is a superseded vocabulary. Its contents confirm this — it contains
`top20_book_and_fifo`, `weather_forward_forcing`, `fundamentals_and_storage`,
`power_stack_and_generation`, `synchronized_curve_and_roll` and `full_bigsuite`: the
October full-stack surface set, including the top-20 book reduction that §6.2 and §8 of
the ingestion paper explicitly replaced with full-depth reconstruction. It is the old
number carried forward in a module nobody re-pointed.

**The reconciliation, which neither paper states:**

| Component | Count | Source |
|---|---|---|
| Inventory bullet layers (15 sections) | 93 | `NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` |
| + section 10 "four live helper-evidence feeds" (prose, 0 bullets, materialized as entries) | 4 | `helper_role_configuration` |
| **= concrete ingestion layers** | **97** | |
| + arm/control bindings (`binding_common_controls` 4, `a_clean_overlay` 1, `a_memory_overlay` 3) | 8 | |
| **= registry entries** | **105** | registry total, verified |
| `hard_minimum_concrete_layer_count` | 90 | a **floor**, not the actual |

Both numbers in circulation are therefore wrong in the papers' vicinity: **24** is the
superseded gate constant, and **90** is the declared minimum, not the count. The actual
is **97 concrete layers / 105 registry entries**.

**Remedy:** re-point `SURFACE_IDS` at the registry's layer vocabulary (generate it from
the registry rather than restating it, so it cannot drift again), re-derive
`MANDATORY_NATIVE_RT_SURFACES` from the registry's `CAUSAL_STREAM_REQUIRED` policy, and
add a test asserting `SURFACE_IDS == {registry layer_ids}` so the next divergence fails
CI instead of sitting unreferenced. Then wire the gate into the launcher — an unreferenced
gate is not a gate. Both papers should state 97/105/90 explicitly so the contract cannot
inherit either stale number.

## CRITICAL 3b — the registry enumerates layer identities, not underlying bytes

§10 is correct and I initially over-stated it; the precise position matters.

93 of the 105 registry entries carry
`NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md` as their only `source_paths`
entry. That is **not** a lazy placeholder pointing at an unrelated document: 93 is exactly
that inventory's bullet count, and the mapping is faithful 1:1, section by section
(brain 5, frozen 9, carryforward 2, raw DBN 6, lifecycle 9, book/FIFO 8, microstructure 7,
legacy 5, geometry 8, pre-birth 5+1, clocks 7+1, shadow 2, sealed 7, outputs 11). The two
apparent shortfalls are correct relocations, not drops — pre-birth's "later outcome reveal"
and clocks' "onset time, withheld until allowed" both moved into `sealed_target_timing`,
which is where sealed content belongs. Nothing was dropped in that enumeration.

The real defect is the narrower one §10 names: the inventory document **defines** each
layer but does not **enumerate or hash the underlying bytes** for it. So the registry
proves 97 layer identities exist, not that any file content behind them was served.

One class is missing from §10's four-class table, and it covers the majority. The eight
`CAUSAL_GROUP_STREAM` groups — `canonical_raw_dbn_mbo`, `order_lifecycle`,
`full_book_fifo_queue`, `microstructure_mechanics`, `legacy_observable_crosswalk`,
`derived_geometry`, `prebirth_opportunity`, `causal_clocks` (55 entries) — do not describe
*files* at all. They describe **runtime-generated evidence**. Neither of §10's two options
(enumerate-and-hash, or narrow to the document) applies to them. They need a fifth class:

| Class | Meaning |
|---|---|
| `RUNNER_GENERATED` | Evidence computed at replay time, hash-bound at emission, with the producing module and calculation-contract clause named |

**Remedy:** add `RUNNER_GENERATED` to §10, classify the 55 causal-stream entries into it,
and apply §10's existing two options only to the ~38 static entries where a file genuinely
backs the layer.

## CRITICAL 4 — the boss-only-mutable design is not implementable today

Both papers rest on this: §3, "the only post-seal mutable field should be
conceptually equivalent to `{"boss": "gpt-5.6-sol"}` … It may not trigger an adapter,
prompt, tool, calculation, or source-code edit." The Goal doc gives the example
"switching an already-supported model from Sol to Granite."

`research/kalshi/frankie_full_stack_runtime_contracts_20260824.py`:

```
19:  EXPECTED_MODEL = "gpt-5.6-sol"
257:      raise RuntimeContractError(f"helper model must be exactly {EXPECTED_MODEL}")
437:      raise RuntimeContractError(f"provider request model must be exactly {EXPECTED_MODEL}")
482:      raise RuntimeContractError(f"accepted response model must be exactly {EXPECTED_MODEL}")
```

A single-value constant, enforced on the helper model, the request model, and the
accepted response model. The only provider SDK imported anywhere in the Frankie runtime
is `openai` (`frankie_full_stack_runtime_adapter_20260824.py:149`). There is no Granite
route.

So the Goal doc's own worked example — Sol to Granite — requires exactly the source-code
edit both papers forbid. Question 6 ("Which exact boss identifiers … must be supported
before sealing?") is therefore not an open question to answer later; it is a **build
prerequisite**. Until `EXPECTED_MODEL` becomes an allowlist and a provider route exists
per allowed boss, the sealed contract's one mutable field has exactly one legal value,
and §12's final criterion ("The workflow can change bosses without changing any other
file or field") is unmeetable.

**Remedy:** replace `EXPECTED_MODEL` with a frozen `ALLOWED_BOSSES` map of
`boss -> (provider, route, sdk)`, validated at seal time; make an unsupported boss
fail closed at the gate rather than at the constant. Then Q6 reduces to populating the
map, which is a decision rather than a rebuild.

---

## REQUIRED 5 — the prior-memory package SHA-256 does not reproduce

Appendix C states the package SHA-256 is `0a5cddbcd971…`. Rebuilt from the 15 committed
files using the documented recipe (`a_memory_prepare_20260828.py:89`,
`tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner … | gzip -n`):

```
reproduced : e5e4ed33f57c3b04f833299c39152012bf52e37dc5d540b66c609c755a92b17f
claimed    : 0a5cddbcd971a3e6c2cad88a8e5559b0ab0529a31174c882355a61fe9c680b87
```

Swept 45 variants — formats `gnu/ustar/pax/oldgnu/v7` x modes `default/0600/0644` x
`gzip -n/-n6/-n9`. No match. Environment: GNU tar 1.35, gzip 1.12.

Two consequences. `a_memory_prepare_20260828.py` hard-fails at line 93 ("deterministic
prior memory package hash mismatch"), so **A-memory cannot be prepared in this
environment as committed**. And the Goal doc's success criterion — "append-only output
and receipt chains that another reviewer can reproduce and audit" — fails today.

Separately, Appendix C calls `e7d8cbc5…` "its **independent** proof-receipt SHA-256". It
is not independent. It is checked against `memory_receipt["receipt_hash"]`
(`a_memory_prepare_20260828.py:134`) — a canonical hash of a dict the same script builds.
The actual SHA-256 of `REPOSITORY_FREEZE.json` is `dc567f014d9c…`, which appears nowhere
in either paper.

**Remedy:** either pin the packaging toolchain (tar/gzip versions, in the requirements
lock and the workflow) and re-derive the hash in that environment, or replace the tar
digest with a **manifest-of-member-hashes** digest, which is toolchain-independent and
reproducible by any reviewer. Correct the word "independent" or make the binding
genuinely external.

## REQUIRED 6 — §5.1's URI premise is wrong; the answer is already in the repo

§5.1: *"The current repository fixes the names and aggregate manifest hash but does not
contain the external S3 URI for this exact four-object A-arm roster. That URI must be
resolved and frozen before the contract is accepted."* Question 5 repeats the ask.

It is already pinned — in a file the paper itself cites in Appendix E.1 and dismisses as
"packet staging only":

```
s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101/<name>
region us-east-2
```

with per-object byte lengths and SHA-256 (`frankie_a_clean_rt_native_launch_20260828.yml:77-80`):

| Object | Bytes | SHA-256 |
|---|---|---|
| `glbx-mdp3-20211001.mbo.dbn.zst` | 25,628,861 | `e6b4ec01bd9b34d5…` |
| `glbx-mdp3-20211003.mbo.dbn.zst` | 973,355 | `4380bd9ba83a5bad…` |
| `glbx-mdp3-20211004.mbo.dbn.zst` | 34,300,424 | `8ed47cc0a68cf40c…` |
| `glbx-mdp3-20211005.mbo.dbn.zst` | 36,192,430 | `a4a12f9578da7624…` |

Both launch workflows pin byte-identical values (verified by diff). **Close Question 5**
and fix §5.1. This is exactly the failure mode the review was commissioned to catch: a
resolved fact re-opened as a blocker because the file holding it was classified as
historical.

## REQUIRED 7 — §5.1's field list is a breaking schema change, not an addition

`raw_mbo_source_manifest.py` defines `_SOURCE_KEYS` as exactly
`{name, date, role, bytes, sha256, mbo_records}`, and `_validate_manifest` raises on any
unknown key ("unknown or missing source fields"). §5.1 additionally requires external
URI, download receipt, local staged path, and staged-file SHA-256.

Adding four fields changes `manifest_hash`, invalidating `SOURCE_MANIFEST_HASH`
`a98a454e…`, which is pinned in `a_memory_prepare_20260828.py:17` and
`frankie_a_memory_rt_native_launch_20260828.yml:304`. The paper presents this as
"resolve and freeze a URI"; it is a schema migration with two downstream pins.

Also: `source_manifest.json` is not committed anywhere in the repo (`find` returns
nothing) — it is produced at stage time. Both papers refer to it as an existing artifact.
State that it is generated, and say which step generates it.

## REQUIRED 8 — Appendix B.2 is not arm-partitioned

B.2 lists `ACLEAN_*` and `AMEMORY_*` files in one flat list headed "Same-arm registered
retrieval material". Read literally, it authorizes A-clean to retrieve A-memory
artifacts, which §2.4 and §8 forbid. The manifest itself partitions correctly (every
artifact carries an `arms` list), so this is a paper defect, not a code defect — but the
paper is what the contract will be built from. Split into **B.2a — A-clean** and
**B.2b — A-memory**.

## REQUIRED 9 — files present in the A-arm tree with no classification

§12 requires every runtime file to receive exactly one classification. These are in the
A-arm tree and appear in neither paper:

- `research/kalshi/frankie_raw_mbo_benchmark/AMEMORY_MEMBER_FIRST_RECALCULATION_SPEC_20260828.md`
  — the **spec** for the recalculation whose *receipt* is B.2-listed and is a live
  A-memory retrieval artifact. The output is classified; the spec defining it is not.
- `research/kalshi/frankie_raw_mbo_benchmark/FRANKIE_KNOWLEDGE_USE_AND_NONFORGETTING_REVIEW_20260828.md`
- `research/kalshi/agents/frankie_native_raw_mbo_knowledge/README.md` — sits inside the
  knowledge directory covered by `KNOWLEDGE_SOURCES` `managed_globs`. If any retrieval
  tool serves that directory by prefix, this file is served.
- `research/kalshi/frankie_raw_mbo_benchmark/__init__.py`
- **All ten files in `research/kalshi/frankie_raw_mbo_benchmark/tests/`.** Appendix J
  lists verification files from `research/`, `research/kalshi/tests/` and `tests/`, and
  omits every test covering the A-arm modules actually under review — including
  `test_corrected_a_arm_execution_gate.py`, which tests the gate that closes the lock
  bypass. They pass: **60 passed, 2 subtests, 0.85s**.

---

## Answers to the papers' open questions

| Q | Status |
|---|---|
| 1 — underlying knowledge bytes | **Reframed.** See Critical 3: the problem is 93 entries across 14 groups, and 8 of those groups need a `RUNNER_GENERATED` class that §10's four-class table lacks. |
| 2 — provider invocation cadence | **Genuinely open.** Nothing in the mission or the gate fixes it. The registry's `EACH_F_LAST_CUTOFF` is a policy on *evidence availability*, not an invocation schedule. Agreed this blocks building. |
| 3 — four live helpers | **Declared but unsourced.** Inventory section 10 is prose with zero bullets; the registry materializes it as 4 `helper_role_configuration` entries — these are the +4 that take 93 layers to 97. Meanwhile `frankie_full_stack_runtime_contracts_20260824.py:257` already enforces a helper model, so helpers are wired in code and counted in the registry while sourced nowhere. Decide and source. |
| 4 — Forecaster mission | **Open**, and sharpened: the current directive is `first_replay_forecaster_directive`, authority `BINDING_CURRENT_DIRECTIVE`, bound identically to both arms. If a full-rerun directive replaces it, it must replace it in both profiles in the same edit or Critical 2 gains a fourth difference. |
| 5 — exact source URIs | **Answered — close it.** See Required 6. |
| 6 — boss allowlist | **Promoted to a build prerequisite.** See Critical 4. |
| 7 — calculation completion | **Open.** Confirmed: `a_memory_member_first_recalculation_20260828.py` implements member-first recalculation only. FIFO lifecycle, matching, exhaustion runways, dipole, lineage, clustering and response tables have no implementation in the A-arm tree. |
| 8 — shadow components | **Open**, but note `provisional_shadow` already carries 2 registry entries (`s137_cognitive_shadow_runtime`, `hipporag_associative_retrieval`) with real distinct sources, while Appendix I lists 10 shadow files. The registry has already made a partial decision the paper treats as undecided. |
| 9 — final file manifest | Blocked on 1-8. |

## What is already right (do not rebuild these)

- **The lock bypass is genuinely closed.** `validate_principal_execution` and
  `validate_first_lock_and_freeze` require provider identity, requested and served model,
  `principal_invocation_id`, `actual_principal_invocation`, `controller_only` false,
  distinct pre/post checkpoints, and positive reconciling token usage; and they raise
  "controller summary cannot be first-locked" and "principal output was not first-locked".
  §12's lock criterion is met by existing code. Keep this module as-is.
- **Path hygiene is good.** 227 of 252 file paths cited across both papers resolve. The
  25 that do not are bare filenames relative to the prior-memory directory (all 16
  present, exactly as Appendix C describes: 15 tar members + `REPOSITORY_FREEZE.json`),
  the two papers themselves (not yet committed), and one deliberate glob. **Zero `E:/`
  desktop paths** — D34 is satisfied.
- **No duplicate `layer_id` values** across the 105 registry entries, and the
  inventory-to-registry enumeration is complete and faithful — 93 bullets map 1:1, with
  the two sealed items correctly relocated rather than dropped.
- **The exact-vs-averaged separation (§2.3, §6.6) is correctly stated** and matches
  `AMEMORY_MEMBER_FIRST_RECALCULATION_RECEIPT_20260828.json`
  (`completed_native_mbo_records: 5667689`, agreeing with the manifest denominator).
- **The A-arm test suite passes** (60 passed, 2 subtests) — it is just unlisted.

## Recommended order of work

1. Fix Critical 1 and 2 first — they are content and manifest edits, and every later
   decision inherits from them. Nothing else matters if the arms are not comparable.
2. Fix Critical 4 (`ALLOWED_BOSSES`) — it is small, and it is the premise both papers are
   built on.
3. Re-point the gate at the registry vocabulary and wire it in (Critical 3), and add the
   `RUNNER_GENERATED` class to §10 (Critical 3b) — same enumeration problem at two layers,
   fix in one pass. State 97 / 105 / 90 in both papers so neither stale number is
   inherited.
4. Close Required 6 and 7 together (the manifest schema migration carries the URI).
5. Resolve Required 5 (package hash) before any A-memory run; it is a hard stop today.
6. Sweep Required 9 and 10 last — they are bookkeeping, and they are what §12's
   "explicitly enumerated" criteria will be checked against.

Question 2 (cadence) remains the one item that cannot be closed from the repository and
needs a design decision.
