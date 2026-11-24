from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from refrag_discovery.paths import MANIFESTS_DIR, SCHEMA_DIR
from refrag_discovery.registry.models import ManifestValidationResult


DEFAULT_MANIFESTS_DIR = MANIFESTS_DIR
DEFAULT_SCHEMA_DIR = SCHEMA_DIR
DEFAULT_OPERATOR_SCHEMA_PATH = SCHEMA_DIR / "operator_manifest.schema.json"
DEFAULT_EVIDENCE_SCHEMA_PATH = SCHEMA_DIR / "evidence_graph.schema.json"

EXECUTION_CLASS_NORMALIZATION = {
    "control": "control_plane",
}

OPERATOR_TYPE_NORMALIZATION = {
    "pipeline": "template",
}

MATURITY_NORMALIZATION = {
    "beta": "candidate",
}

# Type kinds accepted in manifest input/output declarations without a separate
# data-type schema. Anything outside this set is treated as a custom type and
# must resolve to a schema file in SCHEMA_DIR (see load_data_type_registry).
PRIMITIVE_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "integer",
        "float",
        "number",
        "boolean",
        "object",
        "any",
        "uuid",
    }
)

# Filenames in SCHEMA_DIR that are NOT data-type schemas (meta-schemas or
# specialised validators with their own callsite).
NON_DATA_TYPE_SCHEMA_STEMS: frozenset[str] = frozenset(
    {
        "operator_manifest",
    }
)

ARRAY_TYPE_RE = re.compile(r"^array<(.+)>$")
ENUM_TYPE_RE = re.compile(r"^enum\(([^)]+)\)$")
MAP_TYPE_RE = re.compile(r"^map<([^,]+),\s*(.+)>$")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_schema(schema_path: Path) -> dict[str, Any]:
    return load_json(schema_path)


def normalize_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = json.loads(json.dumps(manifest))
    changes: list[str] = []

    execution_class = normalized.get("execution_class")
    if execution_class in EXECUTION_CLASS_NORMALIZATION:
        new_value = EXECUTION_CLASS_NORMALIZATION[execution_class]
        normalized["execution_class"] = new_value
        changes.append(f"execution_class: {execution_class} -> {new_value}")

    operator_type = normalized.get("operator_type")
    if operator_type in OPERATOR_TYPE_NORMALIZATION:
        new_value = OPERATOR_TYPE_NORMALIZATION[operator_type]
        normalized["operator_type"] = new_value
        changes.append(f"operator_type: {operator_type} -> {new_value}")

    maturity = normalized.get("maturity")
    if maturity in MATURITY_NORMALIZATION:
        new_value = MATURITY_NORMALIZATION[maturity]
        normalized["maturity"] = new_value
        changes.append(f"maturity: {maturity} -> {new_value}")

    return normalized, changes


def _format_validation_errors(errors: list[Any]) -> tuple[str, ...]:
    formatted: list[str] = []
    for error in sorted(errors, key=lambda item: list(item.path)):
        dotted = ".".join(str(part) for part in error.path) or "<root>"
        formatted.append(f"{dotted}: {error.message}")
    return tuple(formatted)


def validate_instance(instance: dict[str, Any], schema: dict[str, Any]) -> tuple[str, ...]:
    validator = Draft7Validator(schema)
    return _format_validation_errors(list(validator.iter_errors(instance)))


def _snake_to_camel(stem: str) -> str:
    """spectral_chunk -> SpectralChunk. Filename stem to canonical TypeName."""
    return "".join(part.capitalize() for part in stem.split("_") if part)


def load_data_type_registry(
    schema_dir: Path = DEFAULT_SCHEMA_DIR,
) -> dict[str, dict[str, Any]]:
    """Build {TypeName: schema} from every *.schema.json in schema_dir, except
    meta-schemas listed in NON_DATA_TYPE_SCHEMA_STEMS.

    The canonical TypeName is the CamelCase form of the filename stem (with
    ``.schema`` removed). Each schema may optionally override this by setting an
    ``x-typename`` field.
    """
    registry: dict[str, dict[str, Any]] = {}
    for schema_path in sorted(schema_dir.glob("*.schema.json")):
        stem = schema_path.stem  # e.g. "spectral_chunk.schema" -> stem "spectral_chunk.schema"
        # The .schema.json suffix means Path.stem leaves ".schema" on the end.
        if stem.endswith(".schema"):
            stem = stem[: -len(".schema")]
        if stem in NON_DATA_TYPE_SCHEMA_STEMS:
            continue
        schema = load_json(schema_path)
        type_name = str(schema.get("x-typename") or _snake_to_camel(stem))
        if type_name in registry:
            raise ValueError(
                f"Duplicate data-type schema for {type_name!r} "
                f"({registry[type_name].get('$id', '?')} vs {schema.get('$id', '?')})"
            )
        registry[type_name] = schema
    return registry


def _resolve_leaf_type(type_str: str) -> tuple[str, str | None]:
    """Strip array<...>/map<...,V>/enum(...) wrappers down to a leaf type.

    Returns (kind, leaf_type_name). kind is one of 'primitive', 'enum', 'custom'.
    leaf_type_name is None for enums (they are inline literals, not a named type).
    """
    candidate = type_str.strip()

    array_match = ARRAY_TYPE_RE.match(candidate)
    if array_match:
        return _resolve_leaf_type(array_match.group(1))

    map_match = MAP_TYPE_RE.match(candidate)
    if map_match:
        # Map values may be a custom type; map keys are always strings by convention.
        return _resolve_leaf_type(map_match.group(2))

    if ENUM_TYPE_RE.match(candidate):
        return ("enum", None)

    if candidate in PRIMITIVE_TYPES:
        return ("primitive", candidate)

    return ("custom", candidate)


def validate_type_references(
    manifest: dict[str, Any],
    type_registry: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    """Walk inputs/outputs and verify every custom type leaf resolves to a
    data-type schema in the registry. Returns dotted-path error strings.
    """
    errors: list[str] = []
    known_types = set(type_registry.keys())
    for role in ("inputs", "outputs"):
        for index, field in enumerate(manifest.get(role, []) or []):
            field_type = str(field.get("type", "")).strip()
            if not field_type:
                continue
            kind, leaf = _resolve_leaf_type(field_type)
            if kind != "custom":
                continue
            if leaf not in known_types:
                field_name = field.get("name", f"#{index}")
                errors.append(
                    f"{role}.{field_name}: unresolved type {leaf!r} "
                    f"(declared as {field_type!r}); no schema/{leaf}.schema.json or equivalent x-typename. "
                    f"Known custom types: {sorted(known_types) or '(none)'}"
                )
    return tuple(errors)


def validate_manifest_file(
    manifest_path: Path,
    schema: dict[str, Any],
    *,
    repair: bool = False,
    type_registry: dict[str, dict[str, Any]] | None = None,
) -> ManifestValidationResult:
    raw_manifest = load_json(manifest_path)
    normalized_manifest, changes = normalize_manifest(raw_manifest)
    errors = list(validate_instance(normalized_manifest, schema))

    if type_registry is not None:
        errors.extend(validate_type_references(normalized_manifest, type_registry))

    errors_tuple = tuple(errors)
    valid = not errors_tuple

    if repair and valid and changes:
        write_json(manifest_path, normalized_manifest)

    return ManifestValidationResult(
        path=manifest_path,
        operator_id=str(normalized_manifest.get("operator_id", manifest_path.stem)),
        valid=valid,
        normalized_manifest=normalized_manifest,
        changes=tuple(changes),
        errors=errors_tuple,
    )


def validate_manifests(
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
    schema_path: Path = DEFAULT_OPERATOR_SCHEMA_PATH,
    *,
    repair: bool = False,
    schema_dir: Path = DEFAULT_SCHEMA_DIR,
) -> list[ManifestValidationResult]:
    schema = load_schema(schema_path)
    type_registry = load_data_type_registry(schema_dir)
    results: list[ManifestValidationResult] = []
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        results.append(
            validate_manifest_file(
                manifest_path,
                schema,
                repair=repair,
                type_registry=type_registry,
            )
        )
    return results


def validate_evidence_graph(
    graph: dict[str, Any],
    schema_path: Path = DEFAULT_EVIDENCE_SCHEMA_PATH,
) -> tuple[str, ...]:
    schema = load_schema(schema_path)
    return validate_instance(graph, schema)
