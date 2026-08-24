#!/usr/bin/env python3
"""Validated native-context profiles for the uniform two-Frankie build."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import importlib.util
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence


PROFILE_SCHEMA = "FRANKIE_ROLE_CONTEXT_PROFILES_V1_20260824"
ROLE_CONTEXT_BUILD_SCHEMA = "FRANKIE_ROLE_CONTEXT_BUILD_V1_20260824"
CAPABILITY_RECONCILIATION_SCHEMA = "FRANKIE_CAPABILITY_RECONCILIATION_V1_20260824"
CANONICAL_PROFILE_PATH = Path("research/kalshi/FRANKIE_ROLE_CONTEXT_PROFILES_20260824.json")


class RoleContextProfileError(ValueError):
    """The canonical role-profile contract is incomplete or has drifted."""


class FrankieRole(str, Enum):
    REAL_TIME = "REAL_TIME_FRANKIE"
    FORECASTER = "FORECASTER_FRANKIE"


class ActivationState(str, Enum):
    DIRECT = "DIRECT"
    TOOL_ACCESSIBLE = "TOOL_ACCESSIBLE"
    DORMANT = "DORMANT"


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise RoleContextProfileError("role profiles must be deterministic JSON") from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _strict_object(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RoleContextProfileError(f"{field} violates the strict schema")
    return dict(value)


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RoleContextProfileError(f"{field} must be a positive integer")
    return value


def _source_path(repo_root: Path, relative_path: str) -> Path:
    relative = Path(str(relative_path or ""))
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise RoleContextProfileError("static surface source path must be repository-relative")
    root = repo_root.resolve()
    try:
        target = (root / relative).resolve(strict=True)
    except OSError as exc:
        raise RoleContextProfileError(f"static surface source is missing: {relative}") from exc
    if not target.is_relative_to(root) or not target.is_file():
        raise RoleContextProfileError(f"static surface source escapes the repository: {relative}")
    return target


@dataclass(frozen=True)
class StaticSourceIdentity:
    path: str
    sha256: str
    byte_length: int

    def provider_identity(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }


def _load_static_source(
    value: Any,
    *,
    repo_root: Path,
    field: str,
) -> StaticSourceIdentity:
    row = _strict_object(value, {"path", "sha256"}, field)
    path = str(row["path"] or "").strip()
    expected = str(row["sha256"] or "").strip().lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise RoleContextProfileError(f"{field} sha256 is invalid")
    target = _source_path(repo_root, path)
    content = target.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise RoleContextProfileError(f"static surface source hash drift: {path}")
    return StaticSourceIdentity(path=path, sha256=actual, byte_length=len(content))


@dataclass(frozen=True)
class StaticSurfaceBinding:
    surface_id: str
    bundle_schema: str
    canonical_pack: StaticSourceIdentity
    direct_sources: tuple[StaticSourceIdentity, ...]
    tool_reference_sources: tuple[StaticSourceIdentity, ...]
    bundle_hash: str


def _load_static_surface_binding(
    surface_id: str,
    value: Any,
    *,
    repo_root: Path,
) -> StaticSurfaceBinding:
    row = _strict_object(
        value,
        {"bundle_schema", "canonical_pack", "direct_sources", "tool_reference_sources"},
        f"static surface binding {surface_id}",
    )
    bundle_schema = str(row["bundle_schema"] or "").strip()
    if not bundle_schema:
        raise RoleContextProfileError(f"static surface binding {surface_id} needs a schema")
    canonical_pack = _load_static_source(
        row["canonical_pack"], repo_root=repo_root, field=f"{surface_id} canonical pack"
    )
    direct_rows = row["direct_sources"]
    tool_rows = row["tool_reference_sources"]
    if not isinstance(direct_rows, list) or not direct_rows:
        raise RoleContextProfileError(f"{surface_id} direct sources must be a non-empty list")
    if not isinstance(tool_rows, list):
        raise RoleContextProfileError(f"{surface_id} tool references must be a list")
    direct = tuple(
        _load_static_source(
            item,
            repo_root=repo_root,
            field=f"{surface_id} direct source {index}",
        )
        for index, item in enumerate(direct_rows)
    )
    tool = tuple(
        _load_static_source(
            item,
            repo_root=repo_root,
            field=f"{surface_id} tool reference {index}",
        )
        for index, item in enumerate(tool_rows)
    )
    identities = (canonical_pack, *direct, *tool)
    if len({item.path for item in identities}) != len(identities):
        raise RoleContextProfileError(f"{surface_id} static sources must be unique")
    core = {
        "surface_id": surface_id,
        "bundle_schema": bundle_schema,
        "canonical_pack": canonical_pack.provider_identity(),
        "direct_sources": [item.provider_identity() for item in direct],
        "tool_reference_sources": [item.provider_identity() for item in tool],
    }
    return StaticSurfaceBinding(
        surface_id=surface_id,
        bundle_schema=bundle_schema,
        canonical_pack=canonical_pack,
        direct_sources=direct,
        tool_reference_sources=tool,
        bundle_hash=_hash(core),
    )


@dataclass(frozen=True)
class NativeContextBudget:
    direct_min_tokens: int
    direct_target_tokens: int
    tool_expanded_max_tokens: int
    soft_ceiling_tokens: int

    @classmethod
    def from_payload(cls, value: Any) -> "NativeContextBudget":
        row = _strict_object(
            value,
            {
                "direct_min_tokens",
                "direct_target_tokens",
                "tool_expanded_max_tokens",
                "soft_ceiling_tokens",
            },
            "native context budget",
        )
        budget = cls(**{key: _positive_int(item, key) for key, item in row.items()})
        if not (
            budget.direct_min_tokens
            <= budget.direct_target_tokens
            <= budget.tool_expanded_max_tokens
            <= budget.soft_ceiling_tokens
        ):
            raise RoleContextProfileError("native context budget ordering is invalid")
        return budget


@dataclass(frozen=True)
class RoleContextProfile:
    role: FrankieRole
    mission: str
    budget: NativeContextBudget
    direct_token_plan: Mapping[str, int]
    activation: Mapping[str, ActivationState]
    profile_hash: str

    @property
    def direct_surface_ids(self) -> tuple[str, ...]:
        return tuple(key for key, state in self.activation.items() if state is ActivationState.DIRECT)

    @property
    def tool_accessible_surface_ids(self) -> tuple[str, ...]:
        return tuple(
            key for key, state in self.activation.items() if state is ActivationState.TOOL_ACCESSIBLE
        )

    @property
    def dormant_surface_ids(self) -> tuple[str, ...]:
        return tuple(key for key, state in self.activation.items() if state is ActivationState.DORMANT)

    def provider_payload(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "mission": self.mission,
            "budget": {
                "direct_min_tokens": self.budget.direct_min_tokens,
                "direct_target_tokens": self.budget.direct_target_tokens,
                "tool_expanded_max_tokens": self.budget.tool_expanded_max_tokens,
                "soft_ceiling_tokens": self.budget.soft_ceiling_tokens,
            },
            "direct_token_plan": dict(self.direct_token_plan),
            "activation": {key: state.value for key, state in self.activation.items()},
            "profile_hash": self.profile_hash,
        }


@dataclass(frozen=True)
class CanonicalRoleProfiles:
    uniform_superset_build: bool
    native_context_only: bool
    nova_token_optimization: bool
    collaboration_contract: Mapping[str, Any]
    surface_registry: Mapping[str, str]
    static_surface_bindings: Mapping[str, StaticSurfaceBinding]
    roles: Mapping[FrankieRole, RoleContextProfile]
    capability_inventory: Mapping[str, Any]
    dormancy_approvals: Mapping[tuple[FrankieRole, str], Mapping[str, str]]
    source_file_sha256: str
    aggregate_hash: str


def load_role_profiles(
    path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> CanonicalRoleProfiles:
    source = Path(path)
    root_path = Path(repo_root).resolve() if repo_root is not None else source.resolve().parents[2]
    try:
        raw_bytes = source.read_bytes()
        payload = json.loads(raw_bytes)
    except (OSError, TypeError, ValueError) as exc:
        raise RoleContextProfileError("canonical role-profile file cannot be read") from exc
    root = _strict_object(
        payload,
        {
            "schema",
            "uniform_superset_build",
            "native_context_only",
            "nova_token_optimization",
            "collaboration_contract",
            "surface_registry",
            "static_surface_bindings",
            "capability_inventory",
            "dormancy_approvals",
            "roles",
        },
        "role-profile root",
    )
    if root["schema"] != PROFILE_SCHEMA:
        raise RoleContextProfileError("role-profile schema mismatch")
    if root["uniform_superset_build"] is not True or root["native_context_only"] is not True:
        raise RoleContextProfileError("two Frankies must share one native-context superset build")
    if root["nova_token_optimization"] is not False:
        raise RoleContextProfileError("Nova token optimization must remain disabled for this release")
    collaboration = _strict_object(
        root["collaboration_contract"],
        {
            "forecaster_consumes_frozen_rt_state",
            "forecaster_consumes_specialist_packets",
            "forecaster_day_specific_surface",
            "legacy_day_specialists_policy",
            "legacy_spawn_py_mutated",
            "rt_helper_packets_are_forecaster_inputs",
            "rt_helper_scouts_policy",
        },
        "collaboration contract",
    )
    if collaboration != {
        "forecaster_consumes_frozen_rt_state": True,
        "forecaster_consumes_specialist_packets": False,
        "forecaster_day_specific_surface": "day_specific_forecast_context",
        "legacy_day_specialists_policy": "NO_ACTIVE_CALLS_PRESERVED_INSTALLED_TOOL_ACCESSIBLE",
        "legacy_spawn_py_mutated": False,
        "rt_helper_packets_are_forecaster_inputs": False,
        "rt_helper_scouts_policy": "ONE_OPTIONAL_RT_EVIDENCE_SCOUT_NOT_AUTO_CALLED",
    }:
        raise RoleContextProfileError("two-Frankie collaboration contract drift")
    registry = root["surface_registry"]
    if not isinstance(registry, Mapping) or not registry:
        raise RoleContextProfileError("surface registry must be a non-empty object")
    normalized_registry = {
        str(key): str(value).strip() for key, value in sorted(registry.items())
    }
    if any(not key or not value for key, value in normalized_registry.items()):
        raise RoleContextProfileError("surface registry IDs and descriptions must be non-empty")
    static_rows = root["static_surface_bindings"]
    if not isinstance(static_rows, Mapping) or not static_rows:
        raise RoleContextProfileError("static surface bindings must be a non-empty object")
    if not set(static_rows).issubset(normalized_registry):
        raise RoleContextProfileError("static surface binding is not in the surface registry")
    static_bindings = {
        str(surface_id): _load_static_surface_binding(
            str(surface_id), row, repo_root=root_path
        )
        for surface_id, row in sorted(static_rows.items())
    }
    capability_inventory = _strict_object(
        root["capability_inventory"],
        {"bigsuite", "executable_tools"},
        "capability inventory",
    )
    bigsuite = _strict_object(
        capability_inventory["bigsuite"],
        {"registry_source", "minimum_leaf_count", "surface_id"},
        "BigSuite capability inventory",
    )
    if str(bigsuite["surface_id"]) != "full_bigsuite":
        raise RoleContextProfileError("BigSuite inventory must bind full_bigsuite")
    _source_path(root_path, str(bigsuite["registry_source"]))
    _positive_int(bigsuite["minimum_leaf_count"], "BigSuite minimum leaf count")
    executable = _strict_object(
        capability_inventory["executable_tools"],
        {
            "scan_rule",
            "semantic_role_registry_status",
            "default_role_activation",
            "role_overrides",
        },
        "executable capability inventory",
    )
    role_ids = {role.value for role in FrankieRole}
    defaults = _strict_object(
        executable["default_role_activation"],
        role_ids,
        "executable default role activation",
    )
    overrides = _strict_object(
        executable["role_overrides"],
        role_ids,
        "executable role overrides",
    )
    if not str(executable["scan_rule"] or "").strip() or not str(
        executable["semantic_role_registry_status"] or ""
    ).strip():
        raise RoleContextProfileError("executable inventory metadata is incomplete")
    for role_id in sorted(role_ids):
        ActivationState(str(defaults[role_id]))
        if not isinstance(overrides[role_id], Mapping):
            raise RoleContextProfileError("executable role overrides must be objects")
        for state in overrides[role_id].values():
            ActivationState(str(state))
    approval_rows = root["dormancy_approvals"]
    if not isinstance(approval_rows, list):
        raise RoleContextProfileError("dormancy approvals must be a list")
    dormancy_approvals: dict[
        tuple[FrankieRole, str], Mapping[str, str]
    ] = {}
    for index, value in enumerate(approval_rows):
        row = _strict_object(
            value,
            {"role", "item_id", "approved_by", "approved_at_utc", "reason"},
            f"dormancy approval {index}",
        )
        role = FrankieRole(str(row["role"]))
        item_id = str(row["item_id"] or "").strip()
        if not item_id or any(
            not str(row[field] or "").strip()
            for field in ("approved_by", "approved_at_utc", "reason")
        ):
            raise RoleContextProfileError("dormancy approval is incomplete")
        key = (role, item_id)
        if key in dormancy_approvals:
            raise RoleContextProfileError("duplicate dormancy approval")
        dormancy_approvals[key] = MappingProxyType(
            {
                field: str(row[field])
                for field in ("approved_by", "approved_at_utc", "reason")
            }
        )
    role_rows = root["roles"]
    if not isinstance(role_rows, Mapping) or set(role_rows) != {role.value for role in FrankieRole}:
        raise RoleContextProfileError("exactly the Real-Time and Forecaster profiles are required")
    roles: dict[FrankieRole, RoleContextProfile] = {}
    for role in FrankieRole:
        row = _strict_object(
            role_rows[role.value],
            {"mission", "budget", "direct_token_plan", "activation"},
            role.value,
        )
        mission = str(row["mission"] or "").strip()
        if not mission:
            raise RoleContextProfileError(f"{role.value} mission is required")
        activation_row = row["activation"]
        if not isinstance(activation_row, Mapping) or set(activation_row) != set(normalized_registry):
            raise RoleContextProfileError(f"{role.value} must classify every registered surface")
        try:
            activation = {
                key: ActivationState(str(activation_row[key])) for key in sorted(activation_row)
            }
        except ValueError as exc:
            raise RoleContextProfileError(f"{role.value} activation state is invalid") from exc
        budget = NativeContextBudget.from_payload(row["budget"])
        token_plan_row = row["direct_token_plan"]
        direct_ids = {
            key for key, state in activation.items() if state is ActivationState.DIRECT
        }
        if not isinstance(token_plan_row, Mapping) or set(token_plan_row) != direct_ids:
            raise RoleContextProfileError(
                f"{role.value} direct token plan must classify every direct surface exactly"
            )
        token_plan = {
            key: _positive_int(token_plan_row[key], f"{role.value} token plan {key}")
            for key in sorted(token_plan_row)
        }
        if sum(token_plan.values()) != budget.direct_target_tokens:
            raise RoleContextProfileError(
                f"{role.value} direct token plan must sum to the direct target"
            )
        core = {
            "role": role.value,
            "mission": mission,
            "budget": row["budget"],
            "direct_token_plan": token_plan,
            "activation": {key: state.value for key, state in activation.items()},
        }
        roles[role] = RoleContextProfile(
            role=role,
            mission=mission,
            budget=budget,
            direct_token_plan=MappingProxyType(token_plan),
            activation=MappingProxyType(activation),
            profile_hash=_hash(core),
        )
    forecaster = roles[FrankieRole.FORECASTER]
    day_surface = str(collaboration["forecaster_day_specific_surface"])
    if forecaster.activation.get(day_surface) is not ActivationState.DIRECT:
        raise RoleContextProfileError("Forecaster day-specific context must be direct")
    if forecaster.activation.get("frozen_rt_state") is not ActivationState.DIRECT:
        raise RoleContextProfileError("Forecaster must directly consume frozen RT state")
    for surface_id in static_bindings:
        if any(
            profile.activation.get(surface_id) is not ActivationState.DIRECT
            for profile in roles.values()
        ):
            raise RoleContextProfileError(
                f"required static surface must be direct for both roles: {surface_id}"
            )
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    aggregate_hash = _hash(
        {
            "schema": PROFILE_SCHEMA,
            "source_file_sha256": source_hash,
            "collaboration_contract": collaboration,
            "surface_registry": normalized_registry,
            "static_surface_bundle_hashes": {
                key: value.bundle_hash for key, value in static_bindings.items()
            },
            "role_profile_hashes": {role.value: item.profile_hash for role, item in roles.items()},
        }
    )
    return CanonicalRoleProfiles(
        uniform_superset_build=True,
        native_context_only=True,
        nova_token_optimization=False,
        collaboration_contract=MappingProxyType(collaboration),
        surface_registry=MappingProxyType(normalized_registry),
        static_surface_bindings=MappingProxyType(static_bindings),
        roles=MappingProxyType(roles),
        capability_inventory=MappingProxyType(
            {
                "bigsuite": MappingProxyType(dict(bigsuite)),
                "executable_tools": MappingProxyType(
                    {
                        **dict(executable),
                        "default_role_activation": MappingProxyType(dict(defaults)),
                        "role_overrides": MappingProxyType(
                            {
                                key: MappingProxyType(dict(value))
                                for key, value in overrides.items()
                            }
                        ),
                    }
                ),
            }
        ),
        dormancy_approvals=MappingProxyType(dormancy_approvals),
        source_file_sha256=source_hash,
        aggregate_hash=aggregate_hash,
    )


def load_canonical_role_profiles(repo_root: str | Path) -> CanonicalRoleProfiles:
    root = Path(repo_root)
    return load_role_profiles(root / CANONICAL_PROFILE_PATH, repo_root=root)


def _direct_source_payload(repo_root: Path, identity: StaticSourceIdentity) -> dict[str, Any]:
    raw = _source_path(repo_root, identity.path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != identity.sha256 or len(raw) != identity.byte_length:
        raise RoleContextProfileError(f"direct static source changed during build: {identity.path}")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoleContextProfileError(
            f"direct static source is not UTF-8 text: {identity.path}"
        ) from exc
    return {**identity.provider_identity(), "content": content}


def _physical_source_identity(repo_root: Path, relative_path: str) -> StaticSourceIdentity:
    target = _source_path(repo_root, relative_path)
    raw = target.read_bytes()
    return StaticSourceIdentity(
        path=relative_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_length=len(raw),
    )


def _bigsuite_capability_payload(
    repo_root: Path,
    *,
    role: FrankieRole,
    profiles: CanonicalRoleProfiles,
) -> dict[str, Any]:
    config = profiles.capability_inventory["bigsuite"]
    registry_path = str(config["registry_source"])
    registry_source = _source_path(repo_root, registry_path)
    spec = importlib.util.spec_from_file_location(
        "frankie_role_profile_bigsuite_registry", registry_source
    )
    if spec is None or spec.loader is None:
        raise RoleContextProfileError("cannot load the authoritative BigSuite registry")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fields = module.survey()
    if not isinstance(fields, Mapping):
        raise RoleContextProfileError("authoritative BigSuite survey did not return a mapping")
    leaf_ids = tuple(sorted(str(path) for path in fields))
    if len(leaf_ids) != len(set(leaf_ids)):
        raise RoleContextProfileError("authoritative BigSuite registry contains duplicate leaves")
    if len(leaf_ids) < int(config["minimum_leaf_count"]):
        raise RoleContextProfileError(
            f"BigSuite registry regressed below {config['minimum_leaf_count']} leaves"
        )
    state_paths = module.state_files()
    if not isinstance(state_paths, list) or not state_paths:
        raise RoleContextProfileError("BigSuite registry has no physical state sources")
    physical_paths = [registry_path]
    for path in state_paths:
        resolved = Path(path).resolve()
        try:
            relative = str(resolved.relative_to(repo_root))
        except ValueError as exc:
            raise RoleContextProfileError("BigSuite state source escapes the repository") from exc
        physical_paths.append(relative)
    physical_sources = [
        _physical_source_identity(repo_root, path).provider_identity()
        for path in sorted(set(physical_paths))
    ]
    surface_id = str(config["surface_id"])
    activation = profiles.roles[role].activation[surface_id].value
    items = [
        {
            "item_id": f"bigsuite:{path}",
            "path": path,
            "activation": activation,
            "surface_id": surface_id,
        }
        for path in leaf_ids
    ]
    leaf_hash = _hash(leaf_ids)
    core = {
        "registry_source": registry_path,
        "registry_leaf_hash": leaf_hash,
        "leaf_count": len(leaf_ids),
        "block_count": len({path.split(".", 1)[0] for path in leaf_ids}),
        "items": items,
        "physical_sources": physical_sources,
        "unregistered_leaf_count": 0,
        "silently_omitted_leaf_count": 0,
    }
    return {**core, "manifest_hash": _hash(core)}


def _installed_executable_paths(repo_root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for path in repo_root.rglob("*.py"):
        relative_path = path.relative_to(repo_root)
        if (
            ".git" in relative_path.parts
            or "__pycache__" in relative_path.parts
            or "tests" in relative_path.parts
            or path.name.startswith("test_")
            or not path.is_file()
        ):
            continue
        paths.append(str(relative_path))
    return tuple(sorted(set(paths)))


def _executable_capability_payload(
    repo_root: Path,
    *,
    role: FrankieRole,
    profiles: CanonicalRoleProfiles,
) -> dict[str, Any]:
    config = profiles.capability_inventory["executable_tools"]
    paths = _installed_executable_paths(repo_root)
    if not paths:
        raise RoleContextProfileError("installed executable inventory is empty")
    defaults = config["default_role_activation"]
    overrides = config["role_overrides"][role.value]
    missing_overrides = sorted(set(overrides) - set(paths))
    if missing_overrides:
        raise RoleContextProfileError(
            f"executable override paths are not installed: {missing_overrides}"
        )
    items: list[dict[str, Any]] = []
    for path in paths:
        identity = _physical_source_identity(repo_root, path)
        state = ActivationState(str(overrides.get(path, defaults[role.value])))
        item_id = f"executable:{path}"
        approval = profiles.dormancy_approvals.get((role, item_id))
        if state is ActivationState.DORMANT and approval is None:
            raise RoleContextProfileError(
                f"dormant executable lacks explicit approval: {role.value}/{path}"
            )
        items.append(
            {
                "item_id": item_id,
                **identity.provider_identity(),
                "activation": state.value,
                "classification_basis": (
                    "EXPLICIT_ROLE_OVERRIDE"
                    if path in overrides
                    else "PRESERVED_NON_DORMANT_DEFAULT"
                ),
                "approval": None if approval is None else dict(approval),
            }
        )
    core = {
        "scan_rule": config["scan_rule"],
        "semantic_role_registry_status": config["semantic_role_registry_status"],
        "unknown_rt_dormancy_action": "PRESERVE_NON_DORMANT_AND_FLAG",
        "tool_count": len(items),
        "items": items,
        "unregistered_tool_count": 0,
        "silently_omitted_tool_count": 0,
    }
    return {**core, "manifest_hash": _hash(core)}


def _capability_reconciliation_payload(
    repo_root: Path,
    *,
    role: FrankieRole,
    profiles: CanonicalRoleProfiles,
) -> dict[str, Any]:
    core = {
        "schema": CAPABILITY_RECONCILIATION_SCHEMA,
        "role": role.value,
        "bigsuite": _bigsuite_capability_payload(repo_root, role=role, profiles=profiles),
        "executable_tools": _executable_capability_payload(
            repo_root, role=role, profiles=profiles
        ),
    }
    return {**core, "receipt_hash": _hash(core)}


def build_role_context_payload(
    repo_root: str | Path,
    role: FrankieRole,
) -> dict[str, Any]:
    """Build the exact in-request role context; static DIRECT bytes are never sidecars."""
    if not isinstance(role, FrankieRole):
        raise RoleContextProfileError("role context build requires a FrankieRole")
    root = Path(repo_root).resolve()
    profiles = load_canonical_role_profiles(root)
    profile = profiles.roles[role]
    direct_static: dict[str, Any] = {}
    for surface_id, binding in profiles.static_surface_bindings.items():
        if profile.activation[surface_id] is not ActivationState.DIRECT:
            raise RoleContextProfileError(f"static surface is not direct for {role.value}")
        direct_identities: Sequence[StaticSourceIdentity] = (
            binding.canonical_pack,
            *binding.direct_sources,
        )
        direct_static[surface_id] = {
            "bundle_schema": binding.bundle_schema,
            "bundle_hash": binding.bundle_hash,
            "direct_sources": [
                _direct_source_payload(root, identity) for identity in direct_identities
            ],
            "tool_reference_sources": [
                identity.provider_identity() for identity in binding.tool_reference_sources
            ],
        }
    capability_reconciliation = _capability_reconciliation_payload(
        root, role=role, profiles=profiles
    )
    core = {
        "schema": ROLE_CONTEXT_BUILD_SCHEMA,
        "operating_role": role.value,
        "uniform_superset_build_hash": profiles.aggregate_hash,
        "role_profile": profile.provider_payload(),
        "collaboration_contract": dict(profiles.collaboration_contract),
        "direct_static_surfaces": direct_static,
        "capability_reconciliation": capability_reconciliation,
        "native_context_only": True,
        "nova_token_optimization": False,
    }
    return {**core, "role_build_hash": _hash(core)}


__all__ = [
    "ActivationState",
    "CANONICAL_PROFILE_PATH",
    "CanonicalRoleProfiles",
    "FrankieRole",
    "NativeContextBudget",
    "PROFILE_SCHEMA",
    "ROLE_CONTEXT_BUILD_SCHEMA",
    "RoleContextProfile",
    "RoleContextProfileError",
    "StaticSourceIdentity",
    "StaticSurfaceBinding",
    "build_role_context_payload",
    "load_canonical_role_profiles",
    "load_role_profiles",
]
