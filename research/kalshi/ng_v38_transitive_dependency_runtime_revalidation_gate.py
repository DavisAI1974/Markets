#!/usr/bin/env python3
"""Revalidate every local Python dependency used by the readiness-v38 plan.

The all-stage runtime gate hashes each configured entrypoint immediately before execution.
An entrypoint can still import mutable repository code, so hashing only the top-level script
leaves a time-of-check/time-of-use seam. This gate statically resolves the transitive local
Python import closure for every configured historical, G15, and G16 stage, hashes those files,
and binds the closure to the recursively validated all-stage runtime receipt.

Only repository code is opened. Corpus and outcome artifacts remain untouched. Non-literal
dynamic imports fail closed because their dependency closure cannot be proven.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_historical_refinement_executor_v34 as executor
import ng_v38_all_stage_runtime_revalidation_gate as prior

SCHEMA = "ng_v38_transitive_dependency_runtime_revalidation_gate.v1"
READY = "V38_TRANSITIVE_LOCAL_PYTHON_DEPENDENCIES_RUNTIME_REVALIDATED_READY"


class V38TransitiveDependencyRuntimeRevalidationError(ValueError):
    """Raised when the local Python dependency closure cannot be proven."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _authority(value: Mapping[str, Any]) -> None:
    for field in (
        "paid_live_data_assumed",
        "corpus_files_opened",
        "outcome_files_opened",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_g16_blind_prior",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise V38TransitiveDependencyRuntimeRevalidationError(
                f"dependency runtime revalidation must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "brokerage contract must remain tastytrade"
        )


def _inside(root: Path, path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"{label} escapes repository root: {resolved}"
        ) from error
    return resolved


def _stage_script(plan: Mapping[str, Any], row: Mapping[str, Any], root: Path) -> Path:
    argv = row.get("argv")
    key = str(row.get("key") or "<unknown>")
    if not isinstance(argv, list) or len(argv) < 2:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"{key}: configured command is missing"
        )
    launcher = Path(str(argv[0])).name.lower()
    if not launcher.startswith("python"):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"{key}: canonical configured stage must use a Python launcher"
        )
    script_token = str(argv[1])
    if script_token.startswith("-") or not script_token.endswith(".py"):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"{key}: canonical Python script path is missing from argv"
        )
    workdir = Path(str(plan.get("working_directory") or ".")).expanduser().resolve(strict=False)
    cwd_value = Path(str(row.get("cwd") or ".")).expanduser()
    cwd = cwd_value if cwd_value.is_absolute() else workdir / cwd_value
    script = Path(script_token).expanduser()
    if not script.is_absolute():
        script = cwd / script
    script = _inside(root, script, label=f"{key} stage script")
    if not script.is_file():
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"{key}: configured stage script is missing: {script}"
        )
    return script


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    observed: set[Path] = set()
    for value in paths:
        resolved = value.expanduser().resolve(strict=False)
        if resolved not in observed:
            observed.add(resolved)
            result.append(resolved)
    return result


def _search_roots(
    plan: Mapping[str, Any], row: Mapping[str, Any], script: Path, repository_root: Path
) -> list[Path]:
    workdir = Path(str(plan.get("working_directory") or ".")).expanduser().resolve(strict=False)
    cwd_value = Path(str(row.get("cwd") or ".")).expanduser()
    cwd = cwd_value if cwd_value.is_absolute() else workdir / cwd_value
    return [
        path
        for path in _dedupe_paths((script.parent, cwd, workdir, repository_root))
        if path == repository_root or repository_root in path.parents
    ]


def _package_initializers(search_root: Path, target: Path) -> list[Path]:
    """Return package __init__.py files executed before target under one search root."""
    try:
        relative = target.relative_to(search_root)
    except ValueError:
        return []
    parts = list(relative.parts)
    if not parts:
        return []
    directory_parts = parts[:-1]
    result: list[Path] = []
    current = search_root
    for part in directory_parts:
        current = current / part
        initializer = current / "__init__.py"
        if initializer.is_file():
            result.append(initializer.resolve(strict=False))
    return result


def _module_candidates(search_root: Path, module_name: str) -> list[Path]:
    parts = [part for part in module_name.split(".") if part]
    if not parts:
        return []
    stem = search_root.joinpath(*parts)
    file_candidate = stem.with_suffix(".py")
    package_candidate = stem / "__init__.py"
    target: Path | None = None
    if file_candidate.is_file():
        target = file_candidate.resolve(strict=False)
    elif package_candidate.is_file():
        target = package_candidate.resolve(strict=False)
    if target is None:
        return []
    return _dedupe_paths((*_package_initializers(search_root, target), target))


def _resolve_absolute(module_name: str, search_roots: Sequence[Path]) -> list[Path]:
    for search_root in search_roots:
        candidates = _module_candidates(search_root, module_name)
        if candidates:
            return candidates
    return []


def _resolve_relative(
    current_file: Path,
    level: int,
    module_name: str | None,
    repository_root: Path,
) -> list[Path]:
    if level <= 0:
        return []
    base = current_file.parent
    for _ in range(level - 1):
        base = base.parent
    base = _inside(repository_root, base, label=f"relative import base for {current_file}")
    if module_name:
        stem = base.joinpath(*module_name.split("."))
    else:
        stem = base
    candidates: list[Path] = []
    file_candidate = stem.with_suffix(".py")
    package_candidate = stem / "__init__.py"
    if file_candidate.is_file():
        candidates.append(file_candidate.resolve(strict=False))
    elif package_candidate.is_file():
        candidates.append(package_candidate.resolve(strict=False))
    elif module_name is None and (stem / "__init__.py").is_file():
        candidates.append((stem / "__init__.py").resolve(strict=False))
    return _dedupe_paths(candidates)


def _literal_dynamic_imports(tree: ast.AST, source_path: Path) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_dynamic = False
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            is_dynamic = True
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
        ):
            is_dynamic = True
        if not is_dynamic:
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(
            node.args[0].value, str
        ):
            raise V38TransitiveDependencyRuntimeRevalidationError(
                f"non-literal dynamic import cannot be proven: {source_path}:{node.lineno}"
            )
        result.append((node.args[0].value, node.lineno))
    return result


def _imports_for_file(
    source_path: Path,
    search_roots: Sequence[Path],
    repository_root: Path,
) -> tuple[list[Path], set[str]]:
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"cannot parse Python dependency {source_path}: {error}"
        ) from error
    local: list[Path] = []
    external: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_absolute(alias.name, search_roots)
                if resolved:
                    local.extend(resolved)
                else:
                    external.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                resolved = _resolve_relative(
                    source_path, node.level, node.module, repository_root
                )
                if not resolved:
                    raise V38TransitiveDependencyRuntimeRevalidationError(
                        f"unresolved relative import cannot be proven: {source_path}:{node.lineno}"
                    )
                local.extend(resolved)
                base_name = node.module or ""
                base_directory = resolved[-1].parent
                if resolved[-1].name == "__init__.py":
                    base_directory = resolved[-1].parent
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    child = base_directory / alias.name
                    child_file = child.with_suffix(".py")
                    child_package = child / "__init__.py"
                    if child_file.is_file():
                        local.append(child_file.resolve(strict=False))
                    elif child_package.is_file():
                        local.append(child_package.resolve(strict=False))
            else:
                module_name = node.module or ""
                resolved = _resolve_absolute(module_name, search_roots)
                if resolved:
                    local.extend(resolved)
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        child_name = f"{module_name}.{alias.name}" if module_name else alias.name
                        local.extend(_resolve_absolute(child_name, search_roots))
                elif module_name:
                    external.add(module_name)
    for module_name, line in _literal_dynamic_imports(tree, source_path):
        if module_name.startswith("."):
            level = len(module_name) - len(module_name.lstrip("."))
            resolved = _resolve_relative(
                source_path,
                level,
                module_name.lstrip(".") or None,
                repository_root,
            )
            if not resolved:
                raise V38TransitiveDependencyRuntimeRevalidationError(
                    f"unresolved literal dynamic relative import: {source_path}:{line}"
                )
        else:
            resolved = _resolve_absolute(module_name, search_roots)
        if resolved:
            local.extend(resolved)
        else:
            external.add(module_name)
    return _dedupe_paths(local), external


def _closure_for_stage(
    plan: Mapping[str, Any],
    row: Mapping[str, Any],
    repository_root: Path,
) -> tuple[list[str], set[str]]:
    script = _stage_script(plan, row, repository_root)
    roots = _search_roots(plan, row, script, repository_root)
    queue: list[Path] = [script]
    observed: set[Path] = set()
    external: set[str] = set()
    while queue:
        current = _inside(repository_root, queue.pop(0), label="local Python dependency")
        if current in observed:
            continue
        if current.suffix != ".py" or not current.is_file():
            raise V38TransitiveDependencyRuntimeRevalidationError(
                f"local dependency is not a readable Python file: {current}"
            )
        observed.add(current)
        dependencies, ignored = _imports_for_file(current, roots, repository_root)
        external.update(ignored)
        for dependency in dependencies:
            dependency = _inside(repository_root, dependency, label="resolved local import")
            if dependency not in observed:
                queue.append(dependency)
    return sorted(path.relative_to(repository_root).as_posix() for path in observed), external


def _dependency_closure(
    plan: Mapping[str, Any], repository_root: Path
) -> tuple[dict[str, list[str]], dict[str, str], list[str]]:
    try:
        executor.validate_plan(plan)
    except Exception as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"readiness-v38 plan is invalid: {error}"
        ) from error
    rows = list(plan.get("stages") or [])
    if not rows:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "readiness-v38 plan has no configured stages"
        )
    per_stage: dict[str, list[str]] = {}
    all_paths: set[str] = set()
    external: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise V38TransitiveDependencyRuntimeRevalidationError(
                "execution plan stage row must be an object"
            )
        key = str(row.get("key") or "")
        if not key or key in per_stage:
            raise V38TransitiveDependencyRuntimeRevalidationError(
                "execution plan stage keys are missing or duplicated"
            )
        closure, ignored = _closure_for_stage(plan, row, repository_root)
        per_stage[key] = closure
        all_paths.update(closure)
        external.update(ignored)
    hashes = {
        relative: _sha256_file(repository_root / relative)
        for relative in sorted(all_paths)
    }
    return per_stage, hashes, sorted(external)


def _validate_entrypoint_hashes(
    plan: Mapping[str, Any],
    repository_root: Path,
    dependency_hashes: Mapping[str, str],
    prior_receipt: Mapping[str, Any],
) -> None:
    prior_hashes = prior_receipt.get("all_stage_script_sha256")
    if not isinstance(prior_hashes, Mapping):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "all-stage runtime receipt lacks entrypoint hashes"
        )
    rows = list(plan.get("stages") or [])
    expected_keys = [str(row.get("key") or "") for row in rows if isinstance(row, Mapping)]
    if list(prior_hashes) != expected_keys:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "all-stage entrypoint hash order does not match the execution plan"
        )
    for row in rows:
        key = str(row.get("key") or "")
        script = _stage_script(plan, row, repository_root)
        relative = script.relative_to(repository_root).as_posix()
        if dependency_hashes.get(relative) != prior_hashes.get(key):
            raise V38TransitiveDependencyRuntimeRevalidationError(
                f"{key}: dependency closure disagrees with the validated entrypoint hash"
            )


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    all_stage_runtime_receipt: Mapping[str, Any],
    repository_root: Path,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    if not root.is_dir():
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"repository root is missing: {root}"
        )
    try:
        checked_prior = prior.validate_gate(
            all_stage_runtime_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"all-stage runtime revalidation is invalid: {error}"
        ) from error
    per_stage, hashes, external = _dependency_closure(plan, root)
    _validate_entrypoint_hashes(plan, root, hashes, checked_prior)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "repository_root": str(root),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "all_stage_runtime_revalidation_receipt": copy.deepcopy(dict(checked_prior)),
        "all_stage_runtime_revalidation_fingerprint": checked_prior.get("fingerprint"),
        "stage_local_python_dependency_paths": per_stage,
        "stage_local_python_dependency_paths_fingerprint": _fp(per_stage),
        "local_python_dependency_sha256": hashes,
        "local_python_dependency_sha256_fingerprint": _fp(hashes),
        "configured_stage_count": len(per_stage),
        "local_python_dependency_file_count": len(hashes),
        "external_imports_ignored": external,
        "external_imports_ignored_fingerprint": _fp(external),
        "all_entrypoints_in_dependency_closure": True,
        "transitive_local_python_dependencies_rehashed": True,
        "nonliteral_dynamic_imports_forbidden": True,
        "runtime_dependency_revalidation_immediately_before_executor_delegation": True,
        "code_files_only": True,
        "corpus_files_opened": False,
        "outcome_files_opened": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_g16_blind_prior": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "RUN_BRANCH_GUARDED_FIRST_BLOCKING_STAGE",
    }
    result["fingerprint"] = _fp(result)
    validate_gate(
        result,
        plan=plan,
        arm_receipt=arm_receipt,
        repository_root=root,
        verify_runtime=False,
        timeout_seconds=timeout_seconds,
    )
    return result


def validate_gate(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    repository_root: Path | None = None,
    verify_runtime: bool = True,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "dependency runtime revalidation schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "dependency runtime revalidation is not ready"
        )
    for field in (
        "all_entrypoints_in_dependency_closure",
        "transitive_local_python_dependencies_rehashed",
        "nonliteral_dynamic_imports_forbidden",
        "runtime_dependency_revalidation_immediately_before_executor_delegation",
        "code_files_only",
    ):
        if checked.get(field) is not True:
            raise V38TransitiveDependencyRuntimeRevalidationError(
                f"mandatory field mismatch: {field}"
            )
    embedded = checked.get("all_stage_runtime_revalidation_receipt")
    if not isinstance(embedded, Mapping):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "embedded all-stage runtime receipt is missing"
        )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(checked.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    if str(root) != checked.get("repository_root"):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "repository root mismatch"
        )
    try:
        checked_prior = prior.validate_gate(
            embedded,
            plan=plan,
            arm_receipt=arm_receipt,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38TransitiveDependencyRuntimeRevalidationError(
            f"embedded all-stage runtime receipt is invalid: {error}"
        ) from error
    if checked.get("all_stage_runtime_revalidation_fingerprint") != checked_prior.get(
        "fingerprint"
    ):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "all-stage runtime revalidation fingerprint mismatch"
        )
    per_stage = checked.get("stage_local_python_dependency_paths")
    hashes = checked.get("local_python_dependency_sha256")
    external = checked.get("external_imports_ignored")
    if not isinstance(per_stage, Mapping) or not isinstance(hashes, Mapping) or not isinstance(
        external, list
    ):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "dependency closure evidence is incomplete"
        )
    if checked.get("configured_stage_count") != len(per_stage):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "configured stage count mismatch"
        )
    if checked.get("local_python_dependency_file_count") != len(hashes):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "local dependency file count mismatch"
        )
    if checked.get("stage_local_python_dependency_paths_fingerprint") != _fp(per_stage):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "per-stage dependency path fingerprint mismatch"
        )
    if checked.get("local_python_dependency_sha256_fingerprint") != _fp(hashes):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "dependency hash fingerprint mismatch"
        )
    if checked.get("external_imports_ignored_fingerprint") != _fp(external):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "external import fingerprint mismatch"
        )
    if checked.get("execution_plan_fingerprint") != plan.get("fingerprint"):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "execution plan fingerprint mismatch"
        )
    if checked.get("pipeline_arm_receipt_fingerprint") != arm_receipt.get("fingerprint"):
        raise V38TransitiveDependencyRuntimeRevalidationError(
            "pipeline arm receipt fingerprint mismatch"
        )
    _validate_entrypoint_hashes(plan, root, hashes, checked_prior)
    if verify_runtime:
        rebuilt = build_gate(
            plan,
            arm_receipt,
            embedded,
            root,
            timeout_seconds=timeout_seconds,
        )
        if checked != rebuilt:
            raise V38TransitiveDependencyRuntimeRevalidationError(
                "dependency runtime revalidation differs from current deterministic reconstruction"
            )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--all-stage-runtime-revalidation", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.all_stage_runtime_revalidation),
        args.repository_root,
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, receipt)
    print(json.dumps({"status": receipt["status"], "fingerprint": receipt["fingerprint"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
