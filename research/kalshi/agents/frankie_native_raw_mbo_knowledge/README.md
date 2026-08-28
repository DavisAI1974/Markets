# Frankie native raw-MBO knowledge base

This directory is the anchor for knowledge promoted from the retained A-arm
native-MBO work. It separates three concerns:

1. **Always-loaded knowledge:** the concise controlling mission/directive and
   the same-arm promoted positive capsule.
2. **Retrieval evidence:** full positive reports remain content-addressed in the
   manifest and available when a task needs their detail.
3. **External bindings:** A-memory's prior lessons package stays outside the
   repository context bundle but is mandatory, arm-routed, and proof-bound.

`KNOWLEDGE_SOURCES_20260828.json` is the editable source-of-truth. The refresh
script generates both promoted capsules and `KNOWLEDGE_MANIFEST_20260828.json`.
Do not hand-edit generated files.

## Refresh and validate

```bash
python research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \
  --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \
  --repo-root . \
  --write

python research/kalshi/frankie_raw_mbo_benchmark/refresh_native_frankie_knowledge.py \
  --spec research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_SOURCES_20260828.json \
  --repo-root . \
  --check
```

## Build a principal context

Use exactly one manifest profile. The builder concatenates only
`always_load` artifacts and emits a receipt that inventories the full retrieval
catalog and required external bindings.

```bash
python research/kalshi/frankie_raw_mbo_benchmark/native_frankie_knowledge_registry.py \
  --manifest research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json \
  --repo-root . \
  --profile RT_A_CLEAN_SECOND_PASS \
  --bundle-out /safe/runtime/RT_A_CLEAN_CONTEXT.md \
  --receipt-out /safe/runtime/RT_A_CLEAN_KNOWLEDGE_RECEIPT.json
```

Available profiles are `RT_A_CLEAN_SECOND_PASS`, `RT_A_MEMORY_SECOND_PASS`,
`FORECASTER_A_CLEAN_REVIEW`, and `FORECASTER_A_MEMORY_REVIEW`.

At the actual model-call seam, the runner must use
`build_model_visible_context()` and `bind_principal_knowledge_use()` from
`native_frankie_knowledge_registry.py`. The first appends a compact hash-bound
retrieval index to the mandatory bundle and verifies external proofs. The second
requires those exact bytes inside the serialized principal input, checks the
response's profile/manifest/bundle bindings and complete `INSPECTED` or
`UNINSPECTED` retrieval inventory, and emits the knowledge-use receipt required
by the first-lock/freeze gate.

## Completeness and non-forgetting gate

A principal model call is ineligible for first lock unless:

- the manifest validates against every registered artifact byte and hash;
- its same-arm/role profile builds without a route violation;
- the exact generated bundle and retrieval index are model-visible;
- the knowledge-use receipt binds the context receipt, bundle, model-visible
  context, serialized principal input, manifest, profile, and retrieval
  dispositions;
- every external binding named by the profile is separately verified;
- the final output includes an inventory of which retrieval artifacts were
  inspected and which remained uninspected; and
- no unregistered file is claimed as retained Frankie knowledge.

The registry deliberately does not claim that a path reference proves model
use. Full reports are not forced into every prompt: they are anchored,
discoverable, and explicitly inventoried, while the concise promoted capsule is
always loaded.

## Adding new retained output

1. Keep only a reviewed positive artifact.
2. Give it a `## Positive knowledge capsule candidates` section when it contains
   material suitable for principal context.
3. Register the source and its exact arm/role/load policy in
   `KNOWLEDGE_SOURCES_20260828.json`.
4. Add or update a capsule source only after deciding that its concise candidate
   section should be promoted.
5. Run the refresh, validation, bundle-isolation tests, and repository tests.
6. Review the generated diff. Promotion occurs through a reviewed commit/PR,
   never by an unreceipted silent rewrite.
