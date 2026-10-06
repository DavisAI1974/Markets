# CCode: the Dipole collection combined into one catalog, 2026-10-06

Greg, in chat: "The dipole collection. Anything dipole. And if they're in different places, combined them into 1."
Built by CCode on that word, on branch `ccode/dipole-collection-20261006` cut from `ccr-5fce7de3-xa4hfg` at Codex's
`21df8f1`. Code over committed bytes only: no model, no data run, no scientific judgment, nothing summarized.
SOURCE-BUILT: the catalog and the claims file are reproducible records; no teacher has run on them.

## What was found, and where

The collection Greg remembered was in two places and neither was complete:

| collection | where | size |
|---|---|---|
| the Sept 22 shared catalog (research agents' gathering) and its 2026-09-29 claims build | this branch | 127 sources; 4,806 candidates, 10 claims, 4,799 not_testable |
| the Aug 28 native raw-MBO knowledge base (79-artifact manifest, A-memory seed, positive reports) | branches up to Sept 17 only; 8 of its files were catalog sources read at their revision | absent from this branch |
| everything else that mentions dipole: S36/S37 findings, the OD toolkit, crypto-era dipole scripts and results, the dipole classroom and its reviews, docs, handoffs, workflows | spread over 199 branch tips; 392 paths absent from this branch, 182 paths differing across branches | 1,032 paths, 1,528 versions |

The scientific teacher's launcher already takes a committed `HISTORICAL_CLAIMS_V1-*.json` (`HISTORICAL_CLAIMS`), and the
teacher tests its `claims` list; the BOSS teacher reads none of it (experiment directive only). Of 4,806 candidates,
10 reached computation. That limit is the crosswalk, not the collection, and it is unchanged here.

## What was built

1. `research/kalshi/frankie_boss/operations/build_dipole_combined_catalog.py`: sweeps every non-data origin branch
   tip with `git grep -il dipole`, keeps one entry per distinct (path, blob) with its newest tip as revision and every
   other tip carrying the same bytes under `provenance.also_on`, carries the 127 Sept 22 entries byte-for-byte, lists
   machine data (.jsonl/.csv/.npz/.html, .json over 1 MB) under `data_listed` and this pipeline's own outputs under
   `derived_excluded`, and validates the result with `dipole_shared_knowledge._catalog`. Nothing swept is dropped:
   every version lands in exactly one of the three lists. Reproduction needs the branch tips fetched (depth 1 is
   enough); the branch list and tip commits are recorded under `sweep`.
2. `research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20261006_COMBINED.json` (4.8 MB), schema
   `FRANKIE_SHARED_KNOWLEDGE_CATALOG_V1`, version `20261006-combined-every-dipole-source-v1`, review groups K01-K10
   carried. Counts: 1,538 sources (127 base + 1,411 swept), 46 data listed, 3 derived excluded; 199 branches,
   69,153 sweep rows, 1,528 distinct versions, 68 swept versions identical to a base entry (carried once).
3. `research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json` (52.9 MB raw, 7.6 MB packed):
   built by the EXISTING `frankie_box_historical_claims.build(catalog_path=<combined>, review_path=REVIEW)`, the
   builder unchanged. All 1,538 sources read at their catalog revision (the five base revisions were fetched by commit),
   none unreadable. 82,372 candidates; 10 claims (H01-H10, the existing crosswalk); 82,365 not_testable (81,655 "no
   crosswalk entry", 710 code sources). The old 2.85 MB file stays beside it untouched.

The combined claims file is above GitHub's 50 MB soft warning and well under its hard limit; git stores it packed.

## What it means for the teachers (the open gap, not closed here)

The collection is now in one place and reaches the scientific teacher through the existing launcher by naming the new
file. The crosswalk still puts 10 of 82,372 statements in testable form. The 81,655 "no crosswalk entry" items are
carried with full source identity (path:line, catalog id, source sha256, revision) so both teachers can bind
computations to them; that binding is the remaining work of CCode's task 1 (statuses: stored evidence reassessed /
original calculation awaiting reproduction / repair or reformulation pending or performed / missing inputs open) and
is NOT done by this build. CCode did not rerun, rework or judge any Dipole research.

## Codex (callers outside CCode ownership)

- Point the scientific teacher's caller at the combined file: `HISTORICAL_CLAIMS=research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json` (the launcher's pattern check already admits it).
- Give the BOSS teacher the same input (today it reads only the experiment directive); the exchange's historical seat should cite `catalog_sha256 9dc79ca359e9...` so both teachers' turns name the same collection.
- `frankie_box_principal_inputs.py` still reads the Sept 22 catalog for the principal's 71 artifacts; switching it to the combined catalog is Codex's call (it would widen the principal's retrieval set from 127 to 1,538 sources).

## Checks

py_compile on the builder; the shared-knowledge validator passed on the catalog; JSON parse of both outputs; git diff
--check. No tests, no runs, no model, no AWS, no dispatch. Scratchpad cleared.
