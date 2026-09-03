"""Rebind the registry's knowledge layers from the inventory DOCUMENT to their KEEP FILES.

**The defect (S120, measured).** 91 of the 99 layers in
`frankie_native_raw_mbo_ingestion_layer_registry_20260828.json` named one markdown document,
`NG_EXHAUSTION_FRANKIE_DATA_FEED_INVENTORY_20260824.md`, as their only source path. The
pre-call gate hashed that document, found it unchanged, and stamped every knowledge layer
AVAILABLE. Nothing about what reached Frankie had been measured. The fourteen knowledge
layers - nine `frozen_learned_structure`, five `current_brain_runtime` - are the ones whose
evidence is a file he can read, and none named one.

**What this does.** For each layer in `native_knowledge_delivery.KNOWLEDGE_LAYER_SOURCES`,
`source_paths` becomes the layer's KEEP files (mapped by content, reasons beside the mapping),
`v3_derived` becomes `any("_V3_" in path)` by the validator's own rule, the JSON's
`permitted_v3_source_paths` becomes the module's `ALLOWED_V3_SOURCE_PATHS`, and
`registry_sha256` is RECOMPUTED with `canonical_hash(omit="registry_sha256")` - never edited
by hand. The result must pass `validate_registry`, whose identity-set hash, policy counts and
arm counts do not move: the layer IDENTITIES are unchanged, only what they point at.

**Fail closed.** After the rebind no pre-call input layer may still be bound solely to the
inventory document; if one is, the rebind raises rather than write a registry that would
reproduce the defect for that layer. The file is re-rendered in the committed layout
(groups indented, one entry per line) so the diff is the binding change and nothing else;
`render_registry_json` reproduces the committed file byte-for-byte before any change.

`--check` exits 1 when the committed registry differs from the rebound render; `--write`
writes it. Idempotent: rebinding a rebound registry changes nothing.

**S122 (D86/D88): the `a_memory_overlay` layers bind to the SEED FILE.** The two layers that
carried `external:` paths - the wrong-data run's lessons package and its proof, pinned by hash
with no repository bytes - now bind to `A_MEMORY_SEED_20260902.json` through the same
mechanism (`native_knowledge_delivery.A_MEMORY_SEED_LAYER_SOURCES`), and their descriptions are
rewritten so no entry says "Verified" of a package that was never memory. After this rebind no
pre-call input layer binds an `external:` path; the launcher's `EXTERNAL_SOURCE_IDENTITIES` is
then dead code for the coordinator to retire.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    ALLOWED_V3_SOURCE_PATHS,
    REGISTRY_PATH,
    canonical_hash,
    validate_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    ALL_LAYER_SOURCES,
    KNOWLEDGE_INPUT_POLICIES,
    KnowledgeDeliveryError,
    LayerBinding,
    layers_bound_only_to,
)


def render_registry_json(registry: Mapping[str, Any]) -> str:
    """The committed layout: top-level keys indented two, groups four, entries one per line."""
    out = ["{"]
    keys = list(registry)
    for index, key in enumerate(keys):
        comma = "," if index < len(keys) - 1 else ""
        value = registry[key]
        if key == "permitted_v3_source_paths":
            out.append(f'  "{key}": [')
            for j, item in enumerate(value):
                out.append(f"    {json.dumps(item)}" + ("," if j < len(value) - 1 else ""))
            out.append("  ]" + comma)
        elif key == "groups":
            out.append(f'  "{key}": [')
            for gi, group in enumerate(value):
                out.append("    {")
                group_keys = list(group)
                for k, group_key in enumerate(group_keys):
                    group_comma = "," if k < len(group_keys) - 1 else ""
                    if group_key == "entries":
                        out.append('      "entries": [')
                        entries = group["entries"]
                        for ei, entry in enumerate(entries):
                            out.append(
                                "        " + json.dumps(entry) + ("," if ei < len(entries) - 1 else "")
                            )
                        out.append("      ]" + group_comma)
                    else:
                        out.append(f'      "{group_key}": {json.dumps(group[group_key])}{group_comma}')
                out.append("    }" + ("," if gi < len(value) - 1 else ""))
            out.append("  ]" + comma)
        else:
            out.append(f'  "{key}": {json.dumps(value)}{comma}')
    out.append("}")
    return "\n".join(out) + "\n"


def rebind_knowledge_layers(
    registry: Mapping[str, Any], *, bindings: Sequence[LayerBinding] = ALL_LAYER_SOURCES
) -> dict[str, Any]:
    """Return a rebound copy of `registry`; refuse if any input layer would stay on the document."""
    by_layer = {binding.layer_id: binding for binding in bindings}
    rebound = json.loads(json.dumps(registry))
    seen: set[str] = set()
    for group in rebound["groups"]:
        if group["policy"] not in KNOWLEDGE_INPUT_POLICIES:
            continue
        for entry in group["entries"]:
            binding = by_layer.get(entry["layer_id"])
            if binding is None:
                continue
            seen.add(binding.layer_id)
            entry["source_paths"] = list(binding.paths)
            entry["v3_derived"] = any("_V3_" in path for path in binding.paths)
            if binding.description is not None:
                entry["description"] = binding.description
    missing = sorted(set(by_layer) - seen)
    if missing:
        raise KnowledgeDeliveryError(
            f"bindings name layers the registry does not carry as pre-call inputs: {missing}"
        )
    still_bound = layers_bound_only_to(
        rebound, rebound["source_authority"], policies=KNOWLEDGE_INPUT_POLICIES
    )
    if still_bound:
        raise KnowledgeDeliveryError(
            "knowledge layers still bound only to the inventory document after rebind (D82): "
            f"{still_bound}"
        )
    rebound["permitted_v3_source_paths"] = sorted(ALLOWED_V3_SOURCE_PATHS)
    rebound["registry_sha256"] = canonical_hash(rebound, omit="registry_sha256")
    validate_registry(rebound)
    return rebound


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 if the committed registry is not the rebound render")
    mode.add_argument("--write", action="store_true", help="write the rebound registry in the committed layout")
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    args = parser.parse_args(argv)
    target = Path(args.registry)
    try:
        committed = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSED: cannot read the registry at {target}: {exc}", file=sys.stderr)
        return 1
    try:
        rebound = rebind_knowledge_layers(committed)
    except (KnowledgeDeliveryError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    rendered = render_registry_json(rebound).encode("utf-8")
    if args.write:
        target.write_bytes(rendered)
        print(f"wrote {target} registry_sha256={rebound['registry_sha256']}")
        return 0
    if target.read_bytes() == rendered:
        print(f"PASS  {target} is the rebound registry (registry_sha256={rebound['registry_sha256']})")
        return 0
    print(f"FAIL  {target} differs from the rebound registry; run --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
