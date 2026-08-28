#!/usr/bin/env python3
"""Hash-bound, role-routed knowledge registry for native raw-MBO Frankie runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any, Mapping


SCHEMA = "FRANKIE_NATIVE_RAW_MBO_KNOWLEDGE_MANIFEST_V1"
RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_CONTEXT_RECEIPT_V1"
PRECALL_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_KNOWLEDGE_PRECALL_V1"
USE_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_KNOWLEDGE_USE_V1"
ALLOWED_ARMS = frozenset({"A_CLEAN", "A_MEMORY"})
ALLOWED_ROLES = frozenset({"REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"})
ALLOWED_LOAD_MODES = frozenset({"ALWAYS_LOAD", "RETRIEVAL"})
ALLOWED_KINDS = frozenset({"MARKDOWN", "JSON", "DIRECTORY_PROOF"})
ARTIFACT_KEYS = frozenset(
    {
        "id",
        "path",
        "sha256",
        "bytes",
        "kind",
        "authority",
        "arms",
        "roles",
        "load_mode",
    }
)
PROFILE_KEYS = frozenset(
    {"arm", "role", "always_load", "retrieval_catalog", "external_bindings"}
)
EXTERNAL_KEYS = frozenset(
    {"id", "description", "sha256", "arms", "roles", "required_proof_sha256"}
)


class KnowledgeRegistryError(ValueError):
    """The knowledge registry cannot safely construct a principal context."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Mapping[str, Any], *, omit: str | None = None) -> str:
    body = dict(value)
    if omit is not None:
        body.pop(omit, None)
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise KnowledgeRegistryError(f"{label} must be a lowercase SHA-256")
    return value


def _safe_path(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise KnowledgeRegistryError("artifact path must be a non-empty string")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise KnowledgeRegistryError(f"artifact path escapes repository root: {relative}")
    target = (root / Path(*pure.parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise KnowledgeRegistryError(
            f"artifact path escapes repository root: {relative}"
        ) from exc
    return target


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(row, str) for row in value):
        raise KnowledgeRegistryError(f"{label} must be a string array")
    if len(value) != len(set(value)):
        raise KnowledgeRegistryError(f"{label} contains duplicates")
    return value


def load_and_validate_manifest(path: Path | str, repo_root: Path | str) -> dict[str, Any]:
    manifest_path = Path(path)
    root = Path(repo_root)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeRegistryError(f"cannot read knowledge manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise KnowledgeRegistryError("unsupported knowledge manifest schema")
    if manifest.get("manifest_hash") != canonical_hash(manifest, omit="manifest_hash"):
        raise KnowledgeRegistryError("knowledge manifest hash mismatch")
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise KnowledgeRegistryError("knowledge manifest version is required")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise KnowledgeRegistryError("knowledge manifest has no artifacts")
    by_id: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    for row in artifacts:
        if not isinstance(row, dict) or set(row) != ARTIFACT_KEYS:
            raise KnowledgeRegistryError("knowledge artifact fields are incomplete or unknown")
        artifact_id = row["id"]
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in by_id:
            raise KnowledgeRegistryError("knowledge artifact IDs must be unique strings")
        if row["path"] in seen_paths:
            raise KnowledgeRegistryError("knowledge artifact paths must be unique")
        seen_paths.add(row["path"])
        if row["kind"] not in ALLOWED_KINDS:
            raise KnowledgeRegistryError(f"unsupported artifact kind: {row['kind']}")
        if row["load_mode"] not in ALLOWED_LOAD_MODES:
            raise KnowledgeRegistryError(f"unsupported load mode: {row['load_mode']}")
        if not isinstance(row["authority"], str) or not row["authority"]:
            raise KnowledgeRegistryError("artifact authority is required")
        arms = set(_require_string_list(row["arms"], f"{artifact_id}.arms"))
        roles = set(_require_string_list(row["roles"], f"{artifact_id}.roles"))
        if not arms or not arms <= ALLOWED_ARMS:
            raise KnowledgeRegistryError(f"invalid arms for artifact {artifact_id}")
        if not roles or not roles <= ALLOWED_ROLES:
            raise KnowledgeRegistryError(f"invalid roles for artifact {artifact_id}")
        expected_sha = _require_sha(row["sha256"], f"{artifact_id}.sha256")
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise KnowledgeRegistryError(f"invalid byte count for artifact {artifact_id}")
        target = _safe_path(root, row["path"])
        if not target.is_file():
            raise KnowledgeRegistryError(f"missing required artifact: {row['path']}")
        if target.stat().st_size != row["bytes"]:
            raise KnowledgeRegistryError(f"byte-length drift for artifact {artifact_id}")
        if sha256_file(target) != expected_sha:
            raise KnowledgeRegistryError(f"SHA-256 drift for artifact {artifact_id}")
        by_id[artifact_id] = row

    external_rows = manifest.get("external_bindings")
    if not isinstance(external_rows, list):
        raise KnowledgeRegistryError("external_bindings must be an array")
    external: dict[str, dict[str, Any]] = {}
    for row in external_rows:
        if not isinstance(row, dict) or set(row) != EXTERNAL_KEYS:
            raise KnowledgeRegistryError("external binding fields are incomplete or unknown")
        binding_id = row["id"]
        if not isinstance(binding_id, str) or not binding_id or binding_id in external:
            raise KnowledgeRegistryError("external binding IDs must be unique strings")
        _require_sha(row["sha256"], f"{binding_id}.sha256")
        _require_sha(row["required_proof_sha256"], f"{binding_id}.required_proof_sha256")
        arms = set(_require_string_list(row["arms"], f"{binding_id}.arms"))
        roles = set(_require_string_list(row["roles"], f"{binding_id}.roles"))
        if not arms or not arms <= ALLOWED_ARMS or not roles or not roles <= ALLOWED_ROLES:
            raise KnowledgeRegistryError(f"invalid route for external binding {binding_id}")
        external[binding_id] = row

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise KnowledgeRegistryError("knowledge manifest has no load profiles")
    for profile_id, profile in profiles.items():
        if not isinstance(profile_id, str) or not isinstance(profile, dict) or set(profile) != PROFILE_KEYS:
            raise KnowledgeRegistryError("invalid knowledge profile")
        arm = profile["arm"]
        role = profile["role"]
        if arm not in ALLOWED_ARMS or role not in ALLOWED_ROLES:
            raise KnowledgeRegistryError(f"invalid profile route: {profile_id}")
        always = _require_string_list(profile["always_load"], f"{profile_id}.always_load")
        retrieval = _require_string_list(
            profile["retrieval_catalog"], f"{profile_id}.retrieval_catalog"
        )
        bindings = _require_string_list(
            profile["external_bindings"], f"{profile_id}.external_bindings"
        )
        if set(always) & set(retrieval):
            raise KnowledgeRegistryError(f"profile duplicates load modes: {profile_id}")
        for artifact_id in always + retrieval:
            if artifact_id not in by_id:
                raise KnowledgeRegistryError(f"unknown artifact in profile {profile_id}: {artifact_id}")
            row = by_id[artifact_id]
            if arm not in row["arms"]:
                raise KnowledgeRegistryError(f"arm route violation in profile {profile_id}")
            if role not in row["roles"]:
                raise KnowledgeRegistryError(f"role route violation in profile {profile_id}")
            expected_mode = "ALWAYS_LOAD" if artifact_id in always else "RETRIEVAL"
            if row["load_mode"] != expected_mode:
                raise KnowledgeRegistryError(f"load-mode violation in profile {profile_id}")
        for binding_id in bindings:
            if binding_id not in external:
                raise KnowledgeRegistryError(f"unknown external binding in profile {profile_id}")
            row = external[binding_id]
            if arm not in row["arms"] or role not in row["roles"]:
                raise KnowledgeRegistryError(f"external-binding route violation in {profile_id}")

    for artifact_id, row in by_id.items():
        if row["load_mode"] != "ALWAYS_LOAD":
            continue
        compatible = [
            profile
            for profile in profiles.values()
            if profile["arm"] in row["arms"] and profile["role"] in row["roles"]
        ]
        if not compatible or any(artifact_id not in profile["always_load"] for profile in compatible):
            raise KnowledgeRegistryError(f"unrouted ALWAYS_LOAD artifact: {artifact_id}")
    return manifest


def _inventory(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "path": row["path"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "authority": row["authority"],
    }


def build_context_bundle(
    manifest: Mapping[str, Any], profile_id: str, repo_root: Path | str
) -> tuple[bytes, dict[str, Any]]:
    profiles = manifest["profiles"]
    if profile_id not in profiles:
        raise KnowledgeRegistryError(f"unknown knowledge profile: {profile_id}")
    profile = profiles[profile_id]
    by_id = {row["id"]: row for row in manifest["artifacts"]}
    root = Path(repo_root)
    chunks: list[bytes] = []
    loaded: list[dict[str, Any]] = []
    for artifact_id in profile["always_load"]:
        row = by_id[artifact_id]
        raw = _safe_path(root, row["path"]).read_bytes()
        chunks.extend(
            [
                f"\n===== BEGIN KNOWLEDGE {artifact_id} {row['sha256']} =====\n".encode(),
                raw,
                f"\n===== END KNOWLEDGE {artifact_id} =====\n".encode(),
            ]
        )
        loaded.append(_inventory(row))
    bundle = b"".join(chunks)
    retrieval = [_inventory(by_id[value]) for value in profile["retrieval_catalog"]]
    external_by_id = {row["id"]: row for row in manifest["external_bindings"]}
    external = [external_by_id[value] for value in profile["external_bindings"]]
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "manifest_version": manifest["version"],
        "manifest_hash": manifest["manifest_hash"],
        "profile_id": profile_id,
        "arm": profile["arm"],
        "role": profile["role"],
        "loaded_artifacts": loaded,
        "retrieval_catalog": retrieval,
        "external_bindings": external,
        "context_bundle_sha256": hashlib.sha256(bundle).hexdigest(),
        "context_bundle_bytes": len(bundle),
        "missing_required_artifacts": [],
        "unregistered_required_artifacts": [],
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_hash(receipt, omit="receipt_hash")
    return bundle, receipt


def build_model_visible_context(
    manifest: Mapping[str, Any],
    profile_id: str,
    repo_root: Path | str,
    *,
    external_proofs: Mapping[str, Mapping[str, str]],
) -> tuple[bytes, dict[str, Any]]:
    """Append a compact retrieval index and bind required external proofs."""
    bundle, context_receipt = build_context_bundle(manifest, profile_id, repo_root)
    expected_external = {
        row["id"]: row for row in context_receipt["external_bindings"]
    }
    if set(external_proofs) != set(expected_external):
        raise KnowledgeRegistryError("external-proof inventory mismatch")
    verified_external: list[dict[str, str]] = []
    for binding_id, expected in expected_external.items():
        observed = external_proofs[binding_id]
        if set(observed) != {"sha256", "proof_sha256"}:
            raise KnowledgeRegistryError(f"external-proof fields mismatch: {binding_id}")
        if (
            observed["sha256"] != expected["sha256"]
            or observed["proof_sha256"] != expected["required_proof_sha256"]
        ):
            raise KnowledgeRegistryError(f"external-proof hash mismatch: {binding_id}")
        verified_external.append(
            {
                "id": binding_id,
                "sha256": observed["sha256"],
                "proof_sha256": observed["proof_sha256"],
            }
        )

    retrieval_index = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_RETRIEVAL_INDEX_V1",
        "profile_id": profile_id,
        "manifest_hash": manifest["manifest_hash"],
        "artifacts": context_receipt["retrieval_catalog"],
    }
    index_bytes = canonical_bytes(retrieval_index)
    model_visible_context = b"".join(
        [
            bundle,
            b"\n===== BEGIN HASH-BOUND RETRIEVAL INDEX =====\n",
            index_bytes,
            b"\n===== END HASH-BOUND RETRIEVAL INDEX =====\n",
        ]
    )
    pre_call: dict[str, Any] = {
        "schema": PRECALL_SCHEMA,
        "profile_id": profile_id,
        "arm": context_receipt["arm"],
        "role": context_receipt["role"],
        "manifest_hash": manifest["manifest_hash"],
        "context_receipt": context_receipt,
        "retrieval_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "retrieval_index_bytes": len(index_bytes),
        "model_visible_context_sha256": hashlib.sha256(model_visible_context).hexdigest(),
        "model_visible_context_bytes": len(model_visible_context),
        "verified_external_proofs": verified_external,
        "pre_call_receipt_hash": "",
    }
    pre_call["pre_call_receipt_hash"] = canonical_hash(
        pre_call, omit="pre_call_receipt_hash"
    )
    return model_visible_context, pre_call


def bind_principal_knowledge_use(
    pre_call: Mapping[str, Any],
    *,
    model_visible_context: bytes,
    serialized_principal_input: bytes,
    response_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove exact principal-input inclusion and complete retrieval disposition."""
    if pre_call.get("schema") != PRECALL_SCHEMA or pre_call.get(
        "pre_call_receipt_hash"
    ) != canonical_hash(pre_call, omit="pre_call_receipt_hash"):
        raise KnowledgeRegistryError("principal pre-call receipt mismatch")
    if (
        len(model_visible_context) != pre_call["model_visible_context_bytes"]
        or hashlib.sha256(model_visible_context).hexdigest()
        != pre_call["model_visible_context_sha256"]
    ):
        raise KnowledgeRegistryError("model-visible context hash mismatch")
    if model_visible_context not in serialized_principal_input:
        raise KnowledgeRegistryError(
            "serialized principal input lacks the exact model-visible context"
        )

    context_receipt = pre_call["context_receipt"]
    for field in (
        "profile_id",
        "arm",
        "role",
        "manifest_hash",
        "context_bundle_sha256",
    ):
        expected = (
            context_receipt["context_bundle_sha256"]
            if field == "context_bundle_sha256"
            else pre_call[field]
        )
        if response_binding.get(field) != expected:
            raise KnowledgeRegistryError(f"response binding mismatch: {field}")

    dispositions = response_binding.get("retrieval_dispositions")
    if not isinstance(dispositions, Mapping):
        raise KnowledgeRegistryError("retrieval disposition inventory is required")
    retrieval = context_receipt["retrieval_catalog"]
    expected_ids = {row["id"] for row in retrieval}
    if set(dispositions) != expected_ids:
        raise KnowledgeRegistryError("retrieval disposition inventory is incomplete")
    allowed_dispositions = {"INSPECTED", "UNINSPECTED"}
    if any(value not in allowed_dispositions for value in dispositions.values()):
        raise KnowledgeRegistryError("unsupported retrieval disposition")
    retrieval_inventory = [
        {**row, "disposition": dispositions[row["id"]]} for row in retrieval
    ]

    receipt: dict[str, Any] = {
        "schema": USE_SCHEMA,
        "profile_id": pre_call["profile_id"],
        "arm": pre_call["arm"],
        "role": pre_call["role"],
        "manifest_hash": pre_call["manifest_hash"],
        "context_receipt_hash": context_receipt["receipt_hash"],
        "pre_call_receipt_hash": pre_call["pre_call_receipt_hash"],
        "context_bundle_sha256": context_receipt["context_bundle_sha256"],
        "model_visible_context_sha256": pre_call["model_visible_context_sha256"],
        "model_visible_context_bytes": pre_call["model_visible_context_bytes"],
        "serialized_principal_input_sha256": hashlib.sha256(
            serialized_principal_input
        ).hexdigest(),
        "serialized_principal_input_bytes": len(serialized_principal_input),
        "loaded_artifacts": context_receipt["loaded_artifacts"],
        "retrieval_inventory": retrieval_inventory,
        "verified_external_proofs": pre_call["verified_external_proofs"],
        "missing_retrieval_dispositions": [],
        "knowledge_use_receipt_hash": "",
    }
    receipt["knowledge_use_receipt_hash"] = canonical_hash(
        receipt, omit="knowledge_use_receipt_hash"
    )
    return receipt


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--profile")
    parser.add_argument("--bundle-out", type=Path)
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args()
    manifest = load_and_validate_manifest(args.manifest, args.repo_root)
    if args.profile is None:
        print(json.dumps({"status": "VALID", "manifest_hash": manifest["manifest_hash"]}))
        return
    if args.bundle_out is None or args.receipt_out is None:
        parser.error("--profile requires --bundle-out and --receipt-out")
    bundle, receipt = build_context_bundle(manifest, args.profile, args.repo_root)
    _write_atomic(args.bundle_out, bundle)
    _write_atomic(args.receipt_out, json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n")
    print(json.dumps({"status": "BUNDLED", "profile": args.profile, "receipt_hash": receipt["receipt_hash"]}))


if __name__ == "__main__":
    main()
