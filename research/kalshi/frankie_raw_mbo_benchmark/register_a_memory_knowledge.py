"""Register the KEEP set in the knowledge sources spec BY SCRIPT, routed to the arm that runs.

**The gap this closes (S121, measured by a read-only search).** `native_knowledge_delivery.
classify_inventory` derives the KEEP set of the 2026-08-24 source-file inventory - the frozen
54/55-week corpus, the proposal lineage, the V4 contracts and corrections, the V3 carryforward
controls, the brain and the two inventories - and the registry's fourteen knowledge layers were
rebound to those files (D82). But the knowledge MANIFEST, the only thing `build_context_bundle`
and `build_model_visible_context` route to a principal, carried twelve artifacts and NONE of
them was a KEEP file: overlap zero. A layer bound to a real file that no manifest delivers is
delivered to nobody. This script puts every KEEP path into `KNOWLEDGE_SOURCES_20260828.json`
as a RETRIEVAL artifact, and `refresh_native_frankie_knowledge --write` then hashes them into
the manifest.

**Rules (Greg, DROP_IN_S121 item zero; D86).**

- No historical number is a spec: the artifact list is DERIVED from `classify_inventory` and
  the registry at build time. Nothing here says 63.
- The sources file is GENERATED, never hand-typed. The base rows (mission, contract, directive,
  capsules, the positive reports, the retired external binding) stay hand-maintained; every
  row whose id starts with `keep_` is owned by this script and regenerated on every run.
  `--check` exits 1 when the committed spec is not the generated one.
- One arm, and it is `A_MEMORY` (D86). KEEP artifacts route to `A_MEMORY`, both roles; the
  A_CLEAN profiles are left byte-identical as inert records (their removal is a D60 discussion).
- Authority is the authority of the registry group that binds the file. A file two groups bind
  carries both, joined in registry order - nothing is dropped. The two inventories are the
  canonical input list (D82) and read `BINDING_CURRENT`.
- The wrong-data package of run 32851909748-1 is NOT memory (D86): its external binding is
  removed from the A_MEMORY profiles' `external_bindings`. The binding ROW stays in the spec as
  an inert record, because removing it breaks nothing and D60 governs its removal.
- A KEEP path that no pre-call input layer binds is a REFUSAL, not an omission (D60): a file
  in the KEEP set with no layer to deliver it would otherwise be registered under no authority
  and reach him as an orphan.

Run:
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge --check
    python3 -m research.kalshi.frankie_raw_mbo_benchmark.register_a_memory_knowledge --write
then `refresh_native_frankie_knowledge --write` to regenerate the manifest.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_frankie_knowledge_registry import (
    ALLOWED_KINDS,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    FEED_INVENTORY_PATH,
    KEEP,
    KNOWLEDGE_INPUT_POLICIES,
    REPO_ROOT,
    SOURCE_INVENTORY_PATH,
    classify_inventory,
)

ARM = "A_MEMORY"
ROLES = ("REAL_TIME_FRANKIE", "FORECASTER_FRANKIE")
KNOWLEDGE_DIR = "research/kalshi/agents/frankie_native_raw_mbo_knowledge/"
SPEC_PATH = KNOWLEDGE_DIR + "KNOWLEDGE_SOURCES_20260828.json"
KEEP_ID_PREFIX = "keep_"
INVENTORY_AUTHORITY = "BINDING_CURRENT"
KIND_BY_EXTENSION = {"md": "MARKDOWN", "json": "JSON", "py": "PYTHON_SOURCE"}
RETIRED_EXTERNAL_BINDINGS = frozenset({"a_memory_prior_lessons_package"})
"""D86: the prior reduced run's lessons package (MEMBER_MANIFEST_SHA256 b487acfb...) is not
memory. Retired from the A_MEMORY profiles; the row itself stays as an inert record."""


class RegistrationError(ValueError):
    """The sources spec cannot be generated honestly; nothing is written."""


def kind_for_path(path: str) -> str:
    extension = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    kind = KIND_BY_EXTENSION.get(extension)
    if kind is None or kind not in ALLOWED_KINDS:
        raise RegistrationError(
            f"no manifest kind for {path!r} (extension {extension!r}); "
            f"kinds known here: {sorted(KIND_BY_EXTENSION)}"
        )
    return kind


def artifact_id(prefix: str, path: str) -> str:
    """Derived from the whole path so two KEEP files sharing a stem (`.md` and `.json`) differ."""
    return prefix + re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")


def _input_authorities(registry: Mapping[str, Any]) -> dict[str, list[str]]:
    """path -> the authorities of the pre-call input groups binding it, in registry order."""
    out: dict[str, list[str]] = {}
    for group in registry["groups"]:
        if group["policy"] not in KNOWLEDGE_INPUT_POLICIES:
            continue
        for entry in group["entries"]:
            for path in entry["source_paths"]:
                bound = out.setdefault(path, [])
                if group["authority"] not in bound:
                    bound.append(group["authority"])
    return out


def keep_artifacts(registry: Mapping[str, Any], repo_root: Path | str = REPO_ROOT) -> list[dict[str, Any]]:
    """One RETRIEVAL artifact row per KEEP path, in inventory order. Derived, never typed."""
    authorities = _input_authorities(registry)
    rows: list[dict[str, Any]] = []
    for row in classify_inventory(repo_root):
        if row.classification != KEEP or row.path is None:
            continue
        bound = authorities.get(row.path)
        if not bound:
            raise RegistrationError(
                f"no pre-call input layer binds KEEP path {row.path!r}; a KEEP path no layer "
                "delivers is a refusal, not an omission (D60)"
            )
        authority = (
            INVENTORY_AUTHORITY
            if row.path in (FEED_INVENTORY_PATH, SOURCE_INVENTORY_PATH)
            else "+".join(bound)
        )
        rows.append(
            {
                "id": artifact_id(KEEP_ID_PREFIX, row.path),
                "path": row.path,
                "kind": kind_for_path(row.path),
                "authority": authority,
                "arms": [ARM],
                "roles": list(ROLES),
                "load_mode": "RETRIEVAL",
            }
        )
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RegistrationError("derived KEEP artifact ids collide")
    return rows


def register(
    spec: Mapping[str, Any], registry: Mapping[str, Any], repo_root: Path | str = REPO_ROOT
) -> dict[str, Any]:
    """Return the spec with the generated rows regenerated and the memory profiles routed.

    Idempotent: registering a registered spec changes nothing. The hand-maintained base rows
    are untouched; a base row whose path is a KEEP path would make the manifest's unique-path
    rule fail later, so it is refused here by name instead.
    """
    out = json.loads(json.dumps(spec))
    generated = keep_artifacts(registry, repo_root)
    base = [row for row in out["artifacts"] if not row["id"].startswith(KEEP_ID_PREFIX)]
    base_paths = {row["path"] for row in base}
    clash = sorted(row["path"] for row in generated if row["path"] in base_paths)
    if clash:
        raise RegistrationError(
            f"KEEP paths already registered as hand-maintained artifacts (paths must be unique): {clash}"
        )
    out["artifacts"] = base + generated
    generated_ids = [row["id"] for row in generated]
    for profile in out["profiles"].values():
        if profile["arm"] != ARM:
            continue
        catalog = [value for value in profile["retrieval_catalog"] if not value.startswith(KEEP_ID_PREFIX)]
        profile["retrieval_catalog"] = catalog + generated_ids
        profile["external_bindings"] = [
            value for value in profile["external_bindings"] if value not in RETIRED_EXTERNAL_BINDINGS
        ]
    return out


def render_spec(spec: Mapping[str, Any]) -> str:
    """The committed layout: one-space indent, sorted keys, trailing newline."""
    return json.dumps(spec, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 if the committed spec is not the generated one")
    mode.add_argument("--write", action="store_true", help="write the generated spec")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="where the inventory and KEEP files are classified from")
    parser.add_argument("--spec", default=None, help="the sources spec to check or write (default: the committed one under --repo-root)")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    target = Path(args.spec) if args.spec else repo_root / SPEC_PATH
    try:
        committed = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"REFUSED: cannot read the sources spec at {target}: {exc}", file=sys.stderr)
        return 1
    try:
        generated = register(committed, load_registry(), repo_root)
    except (RegistrationError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    rendered = render_spec(generated)
    keep_count = sum(1 for row in generated["artifacts"] if row["id"].startswith(KEEP_ID_PREFIX))
    if args.write:
        target.write_text(rendered, encoding="utf-8")
        print(f"wrote {target}: {keep_count} KEEP artifacts routed to {ARM}; run refresh_native_frankie_knowledge --write")
        return 0
    if target.read_text(encoding="utf-8") == rendered:
        print(f"PASS  {target} is the generated spec ({keep_count} KEEP artifacts routed to {ARM})")
        return 0
    print(f"FAIL  {target} differs from the generated spec; run --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
