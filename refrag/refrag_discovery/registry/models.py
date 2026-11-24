from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ManifestValidationResult:
    path: Path
    operator_id: str
    valid: bool
    normalized_manifest: dict[str, Any]
    changes: tuple[str, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ManifestRecord:
    operator_id: str
    manifest: dict[str, Any]
    path: Path
    search_text: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    execution_class: str
    operator_type: str


@dataclass(frozen=True)
class SearchResult:
    operator_id: str
    operator_name: str
    description: str
    score: float
    execution_class: str
    operator_type: str
    path: Path
