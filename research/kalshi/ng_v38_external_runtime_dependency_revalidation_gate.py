#!/usr/bin/env python3
"""Revalidate Python, installed distributions, and AWS CLI before readiness-v38 execution.

The transitive dependency gate proves the repository-local Python import closure. External
imports and executables can still drift after plan compilation, changing DBN parsing, S3
materialization, replay behavior, or scoring. This gate fingerprints the active Python runtime,
all files belonging to every installed distribution that supplies a non-stdlib import, and the
AWS CLI executable/version required by the historical-first corpus path.

Only runtime code and package metadata are opened. Corpus and outcome artifacts remain closed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import ng_corpus_executor_plan_compiler_v31 as compiler
import ng_v38_transitive_dependency_runtime_revalidation_gate as dependency_gate

SCHEMA = "ng_v38_external_runtime_dependency_revalidation_gate.v1"
READY = "V38_EXTERNAL_RUNTIME_DEPENDENCIES_REVALIDATED_READY"
DEFAULT_REQUIRED_EXECUTABLES = ("aws",)


class V38ExternalRuntimeDependencyRevalidationError(ValueError):
    """Raised when external runtime dependency provenance is incomplete or stale."""


def _fp(value: Any) -> str:
    return compiler._fp(value)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise V38ExternalRuntimeDependencyRevalidationError(
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
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"external runtime revalidation must keep {field}=false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise V38ExternalRuntimeDependencyRevalidationError(
            "one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise V38ExternalRuntimeDependencyRevalidationError(
            "blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise V38ExternalRuntimeDependencyRevalidationError(
            "CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise V38ExternalRuntimeDependencyRevalidationError(
            "brokerage contract must remain tastytrade"
        )


def _runtime_identity(python_executable: Path | None = None) -> dict[str, Any]:
    executable = (python_executable or Path(sys.executable)).expanduser().resolve(strict=False)
    if not executable.is_file():
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"active Python executable is missing: {executable}"
        )
    return {
        "executable": str(executable),
        "executable_sha256": _sha256_file(executable),
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "cache_tag": getattr(sys.implementation, "cache_tag", None),
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
    }


def _top_level_imports(external_imports: Sequence[Any]) -> list[str]:
    result: set[str] = set()
    for raw in external_imports:
        text = str(raw or "").strip()
        if text:
            result.add(text.split(".", 1)[0])
    return sorted(result)


def _stdlib_names() -> set[str]:
    names = set(getattr(sys, "stdlib_module_names", set()))
    names.update(sys.builtin_module_names)
    names.add("__future__")
    return names


def _distribution_evidence(distribution: Any, requested_name: str) -> dict[str, Any]:
    canonical_name = str(distribution.metadata.get("Name") or requested_name)
    version = str(distribution.version or "")
    files = distribution.files
    if files is None:
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"installed distribution has no file manifest: {canonical_name}"
        )
    hashes: dict[str, dict[str, Any]] = {}
    for raw_path in sorted((str(item) for item in files)):
        located = Path(distribution.locate_file(raw_path)).expanduser().resolve(strict=False)
        if not located.is_file():
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"installed distribution file is missing: {canonical_name}:{raw_path}"
            )
        hashes[raw_path] = {
            "size_bytes": located.stat().st_size,
            "sha256": _sha256_file(located),
        }
    if not hashes:
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"installed distribution file manifest is empty: {canonical_name}"
        )
    return {
        "name": canonical_name,
        "requested_name": requested_name,
        "version": version,
        "file_count": len(hashes),
        "files": hashes,
        "files_fingerprint": _fp(hashes),
    }


def _installed_distribution_evidence(
    external_imports: Sequence[Any],
    *,
    packages_distributions: Callable[[], Mapping[str, Sequence[str]]] = metadata.packages_distributions,
    distribution_loader: Callable[[str], Any] = metadata.distribution,
) -> tuple[list[str], dict[str, list[str]], dict[str, dict[str, Any]]]:
    top_level = _top_level_imports(external_imports)
    third_party = [name for name in top_level if name not in _stdlib_names()]
    mapping = packages_distributions()
    import_to_distributions: dict[str, list[str]] = {}
    required_distributions: set[str] = set()
    for module_name in third_party:
        names = sorted({str(name) for name in mapping.get(module_name, ()) if str(name)})
        if not names:
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"external import has no installed distribution provenance: {module_name}"
            )
        import_to_distributions[module_name] = names
        required_distributions.update(names)
    evidence = {
        name: _distribution_evidence(distribution_loader(name), name)
        for name in sorted(required_distributions)
    }
    return third_party, import_to_distributions, evidence


def _default_version_runner(argv: Sequence[str], timeout_seconds: float) -> Mapping[str, Any]:
    process = subprocess.run(
        list(argv),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def _executable_evidence(
    names: Sequence[str],
    *,
    which: Callable[[str], str | None] = shutil.which,
    version_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_version_runner,
    timeout_seconds: float,
) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for name in names:
        resolved_text = which(name)
        if not resolved_text:
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"required runtime executable is missing: {name}"
            )
        path = Path(resolved_text).expanduser().resolve(strict=False)
        if not path.is_file():
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"required runtime executable is not a file: {name}:{path}"
            )
        probe = dict(version_runner((str(path), "--version"), timeout_seconds))
        if int(probe.get("returncode", 1)) != 0:
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"required runtime executable version probe failed: {name}"
            )
        version_text = str(probe.get("stdout") or probe.get("stderr") or "").strip()
        if not version_text:
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"required runtime executable returned no version text: {name}"
            )
        evidence[name] = {
            "path": str(path),
            "sha256": _sha256_file(path),
            "version_text": version_text,
        }
    return evidence


def build_gate(
    plan: Mapping[str, Any],
    arm_receipt: Mapping[str, Any],
    dependency_runtime_receipt: Mapping[str, Any],
    repository_root: Path,
    *,
    required_executables: Sequence[str] = DEFAULT_REQUIRED_EXECUTABLES,
    python_executable: Path | None = None,
    packages_distributions: Callable[[], Mapping[str, Sequence[str]]] = metadata.packages_distributions,
    distribution_loader: Callable[[str], Any] = metadata.distribution,
    which: Callable[[str], str | None] = shutil.which,
    version_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_version_runner,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=False)
    try:
        checked_dependency = dependency_gate.validate_gate(
            dependency_runtime_receipt,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            verify_runtime=True,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"transitive local dependency receipt is invalid: {error}"
        ) from error
    external_imports = checked_dependency.get("external_imports_ignored")
    if not isinstance(external_imports, list):
        raise V38ExternalRuntimeDependencyRevalidationError(
            "transitive dependency receipt lacks external import evidence"
        )
    third_party, import_mapping, distributions = _installed_distribution_evidence(
        external_imports,
        packages_distributions=packages_distributions,
        distribution_loader=distribution_loader,
    )
    executable_names = tuple(dict.fromkeys(str(name) for name in required_executables if str(name)))
    executables = _executable_evidence(
        executable_names,
        which=which,
        version_runner=version_runner,
        timeout_seconds=timeout_seconds,
    )
    runtime = _runtime_identity(python_executable)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY,
        "repository_root": str(root),
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "dependency_runtime_revalidation_receipt": copy.deepcopy(dict(checked_dependency)),
        "dependency_runtime_revalidation_fingerprint": checked_dependency.get("fingerprint"),
        "python_runtime": runtime,
        "python_runtime_fingerprint": _fp(runtime),
        "third_party_imports": third_party,
        "third_party_imports_fingerprint": _fp(third_party),
        "import_to_distributions": import_mapping,
        "import_to_distributions_fingerprint": _fp(import_mapping),
        "installed_distributions": distributions,
        "installed_distributions_fingerprint": _fp(distributions),
        "required_executables": list(executable_names),
        "required_executables_fingerprint": _fp(list(executable_names)),
        "runtime_executables": executables,
        "runtime_executables_fingerprint": _fp(executables),
        "all_external_imports_mapped_to_installed_distributions": True,
        "all_distribution_files_rehashed": True,
        "python_executable_rehashed": True,
        "aws_cli_rehashed_and_version_probed": "aws" in executable_names,
        "runtime_external_dependency_revalidation_immediately_before_executor_delegation": True,
        "code_and_runtime_files_only": True,
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
        required_executables=executable_names,
        python_executable=python_executable,
        packages_distributions=packages_distributions,
        distribution_loader=distribution_loader,
        which=which,
        version_runner=version_runner,
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
    required_executables: Sequence[str] = DEFAULT_REQUIRED_EXECUTABLES,
    python_executable: Path | None = None,
    packages_distributions: Callable[[], Mapping[str, Sequence[str]]] = metadata.packages_distributions,
    distribution_loader: Callable[[str], Any] = metadata.distribution,
    which: Callable[[str], str | None] = shutil.which,
    version_runner: Callable[[Sequence[str], float], Mapping[str, Any]] = _default_version_runner,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise V38ExternalRuntimeDependencyRevalidationError(
            "external runtime dependency receipt schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked)
    if checked.get("status") != READY:
        raise V38ExternalRuntimeDependencyRevalidationError(
            "external runtime dependency revalidation is not ready"
        )
    for field in (
        "all_external_imports_mapped_to_installed_distributions",
        "all_distribution_files_rehashed",
        "python_executable_rehashed",
        "runtime_external_dependency_revalidation_immediately_before_executor_delegation",
        "code_and_runtime_files_only",
    ):
        if checked.get(field) is not True:
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"mandatory field mismatch: {field}"
            )
    root = (
        repository_root.expanduser().resolve(strict=False)
        if repository_root is not None
        else Path(str(checked.get("repository_root") or "")).expanduser().resolve(strict=False)
    )
    if str(root) != checked.get("repository_root"):
        raise V38ExternalRuntimeDependencyRevalidationError("repository root mismatch")
    embedded = checked.get("dependency_runtime_revalidation_receipt")
    if not isinstance(embedded, Mapping):
        raise V38ExternalRuntimeDependencyRevalidationError(
            "embedded transitive dependency receipt is missing"
        )
    try:
        validated_dependency = dependency_gate.validate_gate(
            embedded,
            plan=plan,
            arm_receipt=arm_receipt,
            repository_root=root,
            verify_runtime=verify_runtime,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        raise V38ExternalRuntimeDependencyRevalidationError(
            f"embedded transitive dependency receipt is invalid: {error}"
        ) from error
    expected_pairs = {
        "execution_plan_fingerprint": plan.get("fingerprint"),
        "pipeline_arm_receipt_fingerprint": arm_receipt.get("fingerprint"),
        "dependency_runtime_revalidation_fingerprint": validated_dependency.get("fingerprint"),
    }
    for field, expected in expected_pairs.items():
        if checked.get(field) != expected:
            raise V38ExternalRuntimeDependencyRevalidationError(f"field mismatch: {field}")
    for field, fingerprint_field in (
        ("python_runtime", "python_runtime_fingerprint"),
        ("third_party_imports", "third_party_imports_fingerprint"),
        ("import_to_distributions", "import_to_distributions_fingerprint"),
        ("installed_distributions", "installed_distributions_fingerprint"),
        ("required_executables", "required_executables_fingerprint"),
        ("runtime_executables", "runtime_executables_fingerprint"),
    ):
        evidence = checked.get(field)
        if checked.get(fingerprint_field) != _fp(evidence):
            raise V38ExternalRuntimeDependencyRevalidationError(
                f"evidence fingerprint mismatch: {field}"
            )
    expected_executables = list(
        dict.fromkeys(str(name) for name in required_executables if str(name))
    )
    if checked.get("required_executables") != expected_executables:
        raise V38ExternalRuntimeDependencyRevalidationError(
            "required runtime executable set mismatch"
        )
    if checked.get("aws_cli_rehashed_and_version_probed") is not ("aws" in expected_executables):
        raise V38ExternalRuntimeDependencyRevalidationError(
            "AWS CLI runtime assertion mismatch"
        )
    if verify_runtime:
        rebuilt = build_gate(
            plan,
            arm_receipt,
            embedded,
            root,
            required_executables=expected_executables,
            python_executable=python_executable,
            packages_distributions=packages_distributions,
            distribution_loader=distribution_loader,
            which=which,
            version_runner=version_runner,
            timeout_seconds=timeout_seconds,
        )
        if checked != rebuilt:
            raise V38ExternalRuntimeDependencyRevalidationError(
                "external runtime dependency receipt differs from current deterministic reconstruction"
            )
    return copy.deepcopy(dict(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--arm-receipt", type=Path, required=True)
    parser.add_argument("--dependency-runtime-revalidation", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--required-executable", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args(argv)
    required = tuple(args.required_executable) or DEFAULT_REQUIRED_EXECUTABLES
    receipt = build_gate(
        _load(args.plan),
        _load(args.arm_receipt),
        _load(args.dependency_runtime_revalidation),
        args.repository_root,
        required_executables=required,
        timeout_seconds=args.timeout_seconds,
    )
    _write(args.out, receipt)
    print(json.dumps({"status": receipt["status"], "fingerprint": receipt["fingerprint"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
