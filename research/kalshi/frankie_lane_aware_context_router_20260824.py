#!/usr/bin/env python3
"""Two-lane, identity-bound context routing for the blind October experiment.

The router exposes one control and one all-provisional shadow context.  Both
receive the same lossless base corpus.  The combined lane actively receives
every pre-freeze provisional component, while post-evidence components remain
catalogued and receipted but withheld until the two-lane experiment freezes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from frankie_authority_knowledge_plane_20260824 import (
    AuthorityClass,
    KnowledgeAccessDenied,
    KnowledgeCatalogError,
    KnowledgePlane,
    ReadResult,
    RetrievalLane,
    SourceEntry,
)


class ContextVariant(str, Enum):
    S135_CONTROL = "S135_CONTROL"
    FULL_PROVISIONAL_COMBINED = "FULL_PROVISIONAL_COMBINED"


class ComponentAvailability(str, Enum):
    PRE_FREEZE_AUGMENTATION = "PRE_FREEZE_AUGMENTATION"
    POST_GLOBAL_FREEZE_ONLY = "POST_GLOBAL_FREEZE_ONLY"


@dataclass(frozen=True)
class ProvisionalComponent:
    path: str
    label: str
    availability: ComponentAvailability


@dataclass(frozen=True)
class RouteSource:
    source_id: str
    path: str
    sha256: str
    byte_length: int
    authority: AuthorityClass
    component_label: str | None = None
    availability: ComponentAvailability | None = None


@dataclass(frozen=True)
class ContextRoute:
    variant: ContextVariant
    run_id: str
    state_prefix_hash: str
    knowledge_manifest_hash: str
    base_sources: tuple[RouteSource, ...]
    augmentation_sources: tuple[RouteSource, ...]
    withheld_sources: tuple[RouteSource, ...]
    base_corpus_hash: str
    augmentation_hash: str
    route_hash: str
    brain_sha256: str
    complete_source_fallback: bool
    primary_lock_eligible: bool


@dataclass(frozen=True)
class RouteBundle:
    run_id: str
    state_prefix_hash: str
    knowledge_manifest_hash: str
    routes: Mapping[ContextVariant, ContextRoute]
    bundle_hash: str


@dataclass(frozen=True)
class GlobalExperimentFreezeReceipt:
    run_id: str
    state_prefix_hash: str
    knowledge_manifest_hash: str
    bundle_hash: str
    variant_route_hashes: Mapping[ContextVariant, str]
    variant_artifact_hashes: Mapping[ContextVariant, str]
    primary_freeze_receipt_hash: str
    receipt_hash: str


@dataclass(frozen=True)
class RouterReceipt:
    sequence: int
    event: str
    tool: str
    decision: str
    reason: str
    variant: str | None
    run_id: str
    state_prefix_hash: str
    knowledge_manifest_hash: str
    route_hash: str | None
    base_corpus_hash: str | None
    augmentation_hash: str | None
    component_label: str | None
    source_id: str | None
    source_path: str | None
    source_sha256: str | None
    returned_sha256: str | None
    byte_range: tuple[int, int] | None
    underlying_receipt_sequence: int | None
    primary_lock_eligible: bool
    global_freeze_receipt_hash: str | None
    receipt_hash: str


RouterReceiptSink = Callable[[RouterReceipt], None]

_BASE_AUTHORITIES = frozenset(
    {
        AuthorityClass.BINDING_CURRENT,
        AuthorityClass.CURRENT_BRAIN,
        AuthorityClass.FROZEN_LEARNED_KNOWLEDGE,
        AuthorityClass.EXTRA_AGENT_CARRYFORWARD,
    }
)
_REQUIRED_BASE_AUTHORITIES = _BASE_AUTHORITIES
_REQUIRED_FREEZE_ARTIFACTS = frozenset(
    {
        "candidate_discovery",
        "helper_evidence",
        "frankie_reasoning",
        "probability_movie",
        "first_lock",
        "no_lock",
    }
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _source_payload(source: RouteSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "path": source.path,
        "sha256": source.sha256,
        "bytes": source.byte_length,
        "authority": source.authority.value,
        "component_label": source.component_label,
        "availability": source.availability.value if source.availability else None,
    }


class FrankieLaneAwareContextRouter:
    """Build and serve the only permitted control-vs-combined comparison."""

    def __init__(
        self,
        plane: KnowledgePlane,
        components: Sequence[ProvisionalComponent],
        *,
        receipt_sink: RouterReceiptSink | None = None,
    ) -> None:
        self._plane = plane
        self._components = tuple(components)
        self._receipt_sink = receipt_sink
        self._receipts: list[RouterReceipt] = []
        self._global_freeze: GlobalExperimentFreezeReceipt | None = None
        self._validate_components()

    @property
    def receipts(self) -> tuple[RouterReceipt, ...]:
        return tuple(self._receipts)

    def _validate_components(self) -> None:
        labels = [item.label for item in self._components]
        supplied_paths = [item.path for item in self._components]
        invalid_labels = sorted(label for label in labels if not label or label.strip() != label)
        wrong_authority: list[str] = []
        unknown: list[str] = []
        for path in supplied_paths:
            try:
                entry = self._plane.entry(path)
            except KeyError:
                unknown.append(path)
                continue
            if entry.authority is not AuthorityClass.PROVISIONAL_SHADOW:
                wrong_authority.append(path)

        validation_context = self._plane.context(
            run_id="lane-router-component-validation", state_hash=_sha256(b"component-validation")
        )
        shadow_context = self._plane.context(
            run_id=validation_context.run_id,
            state_hash=validation_context.state_hash,
            lane=RetrievalLane.SHADOW,
        )
        catalogued_paths = sorted(
            entry.path
            for entry in self._plane.list_sources(shadow_context)
            if entry.authority is AuthorityClass.PROVISIONAL_SHADOW
        )
        duplicate_paths = sorted({path for path in supplied_paths if supplied_paths.count(path) > 1})
        duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
        missing = sorted(set(catalogued_paths) - set(supplied_paths))
        extra = sorted(set(supplied_paths) - set(catalogued_paths))
        if (
            invalid_labels
            or unknown
            or wrong_authority
            or duplicate_paths
            or duplicate_labels
            or missing
            or extra
        ):
            raise KnowledgeCatalogError(
                "provisional component coverage invalid: "
                f"missing={missing}, extra={extra}, unknown={sorted(unknown)}, "
                f"wrong_authority={sorted(wrong_authority)}, duplicate_paths={duplicate_paths}, "
                f"duplicate_labels={duplicate_labels}, invalid_labels={invalid_labels}"
            )

    def build_routes(self, *, run_id: str, state_prefix_hash: str) -> RouteBundle:
        if not run_id or not _is_sha256(state_prefix_hash):
            raise KnowledgeCatalogError("route requires run id and SHA-256 state prefix hash")
        state_prefix_hash = state_prefix_hash.lower()
        primary_context = self._plane.context(
            run_id=run_id, state_hash=state_prefix_hash, lane=RetrievalLane.PRIMARY
        )
        shadow_context = self._plane.context(
            run_id=run_id, state_hash=state_prefix_hash, lane=RetrievalLane.SHADOW
        )
        primary_entries = tuple(
            entry
            for entry in self._plane.list_sources(primary_context)
            if entry.authority in _BASE_AUTHORITIES
        )
        shadow_visible = self._plane.list_sources(shadow_context)
        shadow_base_entries = tuple(
            entry for entry in shadow_visible if entry.authority in _BASE_AUTHORITIES
        )
        provisional_entries = {
            entry.path: entry
            for entry in shadow_visible
            if entry.authority is AuthorityClass.PROVISIONAL_SHADOW
        }
        primary_identity = [self._entry_identity(entry) for entry in primary_entries]
        shadow_identity = [self._entry_identity(entry) for entry in shadow_base_entries]
        if primary_identity != shadow_identity:
            raise KnowledgeCatalogError("control and combined base corpus identities differ")
        present_authorities = {entry.authority for entry in primary_entries}
        missing_authorities = sorted(
            authority.value for authority in _REQUIRED_BASE_AUTHORITIES - present_authorities
        )
        if missing_authorities:
            raise KnowledgeCatalogError(
                f"complete S135/base source route missing authorities: {missing_authorities}"
            )

        components = {item.path: item for item in self._components}
        if set(provisional_entries) != set(components):
            raise KnowledgeCatalogError("provisional component coverage changed after validation")
        base_sources = tuple(self._route_source(entry) for entry in primary_entries)
        active_sources = tuple(
            self._route_source(provisional_entries[path], components[path])
            for path in sorted(components)
            if components[path].availability is ComponentAvailability.PRE_FREEZE_AUGMENTATION
        )
        withheld_sources = tuple(
            self._route_source(provisional_entries[path], components[path])
            for path in sorted(components)
            if components[path].availability is ComponentAvailability.POST_GLOBAL_FREEZE_ONLY
        )
        brain_sources = [
            item for item in base_sources if item.authority is AuthorityClass.CURRENT_BRAIN
        ]
        if len(brain_sources) != 1:
            raise KnowledgeCatalogError("route requires exactly one CURRENT_BRAIN source")
        base_hash = _sha256(_canonical_bytes([_source_payload(item) for item in base_sources]))
        control = self._make_route(
            variant=ContextVariant.S135_CONTROL,
            run_id=run_id,
            state_prefix_hash=state_prefix_hash,
            base_sources=base_sources,
            augmentation_sources=(),
            withheld_sources=(),
            base_hash=base_hash,
            brain_sha256=brain_sources[0].sha256,
        )
        combined = self._make_route(
            variant=ContextVariant.FULL_PROVISIONAL_COMBINED,
            run_id=run_id,
            state_prefix_hash=state_prefix_hash,
            base_sources=base_sources,
            augmentation_sources=active_sources,
            withheld_sources=withheld_sources,
            base_hash=base_hash,
            brain_sha256=brain_sources[0].sha256,
        )
        routes = MappingProxyType(
            {
                ContextVariant.S135_CONTROL: control,
                ContextVariant.FULL_PROVISIONAL_COMBINED: combined,
            }
        )
        bundle_payload = {
            "run_id": run_id,
            "state_prefix_hash": state_prefix_hash,
            "knowledge_manifest_hash": self._plane.manifest_hash,
            "routes": {variant.value: route.route_hash for variant, route in routes.items()},
        }
        bundle = RouteBundle(
            run_id=run_id,
            state_prefix_hash=state_prefix_hash,
            knowledge_manifest_hash=self._plane.manifest_hash,
            routes=routes,
            bundle_hash=_sha256(_canonical_bytes(bundle_payload)),
        )
        for route in routes.values():
            self._record(bundle, route, "CONTEXT_ROUTE_BUILT", "build_context", "ALLOWED", "IDENTITY_BOUND")
        for source in active_sources:
            self._record(
                bundle,
                combined,
                "PROVISIONAL_COMPONENT_ATTACHED",
                "build_context",
                "ALLOWED",
                "COMBINED_AUGMENTATION_ACTIVE",
                source=source,
            )
        for source in withheld_sources:
            self._record(
                bundle,
                combined,
                "POST_EVIDENCE_COMPONENT_WITHHELD",
                "build_context",
                "DENIED",
                "POST_EVIDENCE_PRE_FREEZE_WITHHELD",
                source=source,
            )
        return bundle

    def _make_route(
        self,
        *,
        variant: ContextVariant,
        run_id: str,
        state_prefix_hash: str,
        base_sources: tuple[RouteSource, ...],
        augmentation_sources: tuple[RouteSource, ...],
        withheld_sources: tuple[RouteSource, ...],
        base_hash: str,
        brain_sha256: str,
    ) -> ContextRoute:
        augmentation_hash = _sha256(
            _canonical_bytes([_source_payload(item) for item in augmentation_sources])
        )
        payload = {
            "variant": variant.value,
            "run_id": run_id,
            "state_prefix_hash": state_prefix_hash,
            "knowledge_manifest_hash": self._plane.manifest_hash,
            "base_corpus_hash": base_hash,
            "augmentation_hash": augmentation_hash,
            "base_sources": [_source_payload(item) for item in base_sources],
            "augmentation_sources": [_source_payload(item) for item in augmentation_sources],
            "withheld_sources": [_source_payload(item) for item in withheld_sources],
            "complete_source_fallback": True,
        }
        return ContextRoute(
            variant=variant,
            run_id=run_id,
            state_prefix_hash=state_prefix_hash,
            knowledge_manifest_hash=self._plane.manifest_hash,
            base_sources=base_sources,
            augmentation_sources=augmentation_sources,
            withheld_sources=withheld_sources,
            base_corpus_hash=base_hash,
            augmentation_hash=augmentation_hash,
            route_hash=_sha256(_canonical_bytes(payload)),
            brain_sha256=brain_sha256,
            complete_source_fallback=True,
            primary_lock_eligible=variant is ContextVariant.S135_CONTROL,
        )

    @staticmethod
    def _route_digest(route: ContextRoute) -> str:
        payload = {
            "variant": route.variant.value,
            "run_id": route.run_id,
            "state_prefix_hash": route.state_prefix_hash,
            "knowledge_manifest_hash": route.knowledge_manifest_hash,
            "base_corpus_hash": route.base_corpus_hash,
            "augmentation_hash": route.augmentation_hash,
            "base_sources": [_source_payload(item) for item in route.base_sources],
            "augmentation_sources": [
                _source_payload(item) for item in route.augmentation_sources
            ],
            "withheld_sources": [_source_payload(item) for item in route.withheld_sources],
            "complete_source_fallback": route.complete_source_fallback,
        }
        return _sha256(_canonical_bytes(payload))

    @staticmethod
    def _entry_identity(entry: SourceEntry) -> tuple[str, str, int, str]:
        return (entry.path, entry.sha256, entry.byte_length, entry.authority.value)

    @staticmethod
    def _route_source(
        entry: SourceEntry, component: ProvisionalComponent | None = None
    ) -> RouteSource:
        return RouteSource(
            source_id=entry.source_id,
            path=entry.path,
            sha256=entry.sha256,
            byte_length=entry.byte_length,
            authority=entry.authority,
            component_label=component.label if component else None,
            availability=component.availability if component else None,
        )

    def read_source(
        self,
        bundle: RouteBundle,
        variant: ContextVariant,
        path: str,
        *,
        start: int = 0,
        end_exclusive: int | None = None,
    ) -> ReadResult:
        route = self._require_bundle_route(bundle, variant)
        try:
            entry = self._plane.entry(path)
        except KeyError:
            self._deny(bundle, route, "read_source", "SOURCE_NOT_IN_ROUTE")
        source = self._source_in_route(route, entry.path)
        sealed = entry.authority is AuthorityClass.SEALED_TARGET_ANSWER
        if sealed:
            reason = (
                "ANSWER_WALL_PRE_GLOBAL_FREEZE"
                if self._global_freeze is None
                else "ANSWER_SOURCE_RECONCILIATION_ONLY"
            )
            self._deny(bundle, route, "read_source", reason, source=self._route_source(entry))
        if entry.authority is AuthorityClass.PROVISIONAL_SHADOW and variant is ContextVariant.S135_CONTROL:
            self._deny(
                bundle,
                route,
                "read_source",
                "PROVISIONAL_EXCLUDED_FROM_CONTROL",
                source=self._route_source(entry),
            )
        if source is None:
            self._deny(bundle, route, "read_source", "SOURCE_NOT_IN_ROUTE", source=self._route_source(entry))
        if (
            source.availability is ComponentAvailability.POST_GLOBAL_FREEZE_ONLY
            and self._global_freeze is None
        ):
            self._deny(
                bundle,
                route,
                "read_source",
                "POST_EVIDENCE_PRE_FREEZE_WITHHELD",
                source=source,
            )
        lane = (
            RetrievalLane.PRIMARY
            if variant is ContextVariant.S135_CONTROL
            else RetrievalLane.SHADOW
        )
        context = self._plane.context(
            run_id=bundle.run_id, state_hash=bundle.state_prefix_hash, lane=lane
        )
        try:
            result = self._plane.read(
                context, path, start=start, end_exclusive=end_exclusive
            )
        except KnowledgeAccessDenied as exc:
            self._record(
                bundle,
                route,
                "SOURCE_READ",
                "read_source",
                "DENIED",
                str(exc),
                source=source,
                underlying_receipt_sequence=self._plane.receipts[-1].sequence,
            )
            raise
        self._record(
            bundle,
            route,
            "SOURCE_READ",
            "read_source",
            "ALLOWED",
            "ROUTED_SOURCE_BYTES",
            source=source,
            returned_sha256=_sha256(result.data),
            byte_range=result.receipt.byte_range,
            underlying_receipt_sequence=result.receipt.sequence,
        )
        return result

    def read_reconciliation(self, bundle: RouteBundle, path: str) -> ReadResult:
        control = self._require_bundle_route(bundle, ContextVariant.S135_CONTROL)
        entry = self._plane.entry(path)
        source = self._route_source(entry)
        if self._global_freeze is None:
            self._deny(
                bundle,
                control,
                "read_reconciliation",
                "ANSWER_WALL_PRE_GLOBAL_FREEZE",
                source=source,
            )
        if entry.authority is not AuthorityClass.SEALED_TARGET_ANSWER:
            self._deny(
                bundle,
                control,
                "read_reconciliation",
                "RECONCILIATION_REQUIRES_SEALED_ANSWER",
                source=source,
            )
        context = self._plane.context(
            run_id=bundle.run_id,
            state_hash=bundle.state_prefix_hash,
            lane=RetrievalLane.POST_FREEZE_RECONCILIATION,
        )
        result = self._plane.read(context, path)
        self._record(
            bundle,
            control,
            "RECONCILIATION_READ",
            "read_reconciliation",
            "ALLOWED",
            "GLOBAL_EXPERIMENT_FROZEN",
            source=source,
            returned_sha256=_sha256(result.data),
            byte_range=result.receipt.byte_range,
            underlying_receipt_sequence=result.receipt.sequence,
        )
        return result

    def freeze_global_experiment(
        self,
        bundle: RouteBundle,
        artifacts_by_variant: Mapping[ContextVariant, Mapping[str, str]],
    ) -> GlobalExperimentFreezeReceipt:
        control = self._require_bundle_route(bundle, ContextVariant.S135_CONTROL)
        self._require_bundle_route(bundle, ContextVariant.FULL_PROVISIONAL_COMBINED)
        supplied = set(artifacts_by_variant)
        expected = set(ContextVariant)
        if supplied != expected:
            raise KnowledgeCatalogError(
                "global freeze requires both experiment variants exactly: "
                f"missing={sorted(item.value for item in expected - supplied)}, "
                f"extra={sorted(str(item) for item in supplied - expected)}"
            )
        normalized: dict[ContextVariant, dict[str, str]] = {}
        for variant in ContextVariant:
            artifacts = artifacts_by_variant[variant]
            missing = sorted(_REQUIRED_FREEZE_ARTIFACTS - artifacts.keys())
            extra = sorted(artifacts.keys() - _REQUIRED_FREEZE_ARTIFACTS)
            invalid = sorted(
                name for name, digest in artifacts.items() if not _is_sha256(str(digest))
            )
            if missing or extra or invalid:
                raise KnowledgeCatalogError(
                    f"incomplete immutable artifacts for {variant.value}: "
                    f"missing={missing}, extra={extra}, invalid={invalid}"
                )
            normalized[variant] = {
                name: str(digest).lower() for name, digest in sorted(artifacts.items())
            }
        artifact_hashes = MappingProxyType(
            {
                variant: _sha256(_canonical_bytes(normalized[variant]))
                for variant in ContextVariant
            }
        )
        route_hashes = MappingProxyType(
            {variant: bundle.routes[variant].route_hash for variant in ContextVariant}
        )
        prefreeze_payload = {
            "run_id": bundle.run_id,
            "state_prefix_hash": bundle.state_prefix_hash,
            "knowledge_manifest_hash": bundle.knowledge_manifest_hash,
            "bundle_hash": bundle.bundle_hash,
            "variant_route_hashes": {k.value: v for k, v in route_hashes.items()},
            "variant_artifact_hashes": {k.value: v for k, v in artifact_hashes.items()},
        }
        candidate_hash = _sha256(_canonical_bytes(prefreeze_payload))
        if self._global_freeze is not None:
            if self._global_freeze.receipt_hash != candidate_hash:
                raise KnowledgeAccessDenied("GLOBAL_EXPERIMENT_FREEZE_IMMUTABLE")
            return self._global_freeze
        primary_context = self._plane.context(
            run_id=bundle.run_id,
            state_hash=bundle.state_prefix_hash,
            lane=RetrievalLane.PRIMARY,
        )
        primary_freeze = self._plane.freeze_primary_outputs(
            primary_context, normalized[ContextVariant.S135_CONTROL]
        )
        receipt = GlobalExperimentFreezeReceipt(
            run_id=bundle.run_id,
            state_prefix_hash=bundle.state_prefix_hash,
            knowledge_manifest_hash=bundle.knowledge_manifest_hash,
            bundle_hash=bundle.bundle_hash,
            variant_route_hashes=route_hashes,
            variant_artifact_hashes=artifact_hashes,
            primary_freeze_receipt_hash=primary_freeze.receipt_hash,
            receipt_hash=candidate_hash,
        )
        self._global_freeze = receipt
        self._record(
            bundle,
            control,
            "GLOBAL_EXPERIMENT_FROZEN",
            "freeze_global_experiment",
            "ALLOWED",
            "BOTH_VARIANTS_COMPLETE_IMMUTABLE",
        )
        return receipt

    def _require_bundle_route(
        self, bundle: RouteBundle, variant: ContextVariant
    ) -> ContextRoute:
        if (
            bundle.knowledge_manifest_hash != self._plane.manifest_hash
            or not bundle.run_id
            or not _is_sha256(bundle.state_prefix_hash)
            or set(bundle.routes) != set(ContextVariant)
        ):
            raise KnowledgeAccessDenied("ROUTE_BUNDLE_IDENTITY_MISMATCH")
        try:
            route = bundle.routes[variant]
        except (KeyError, TypeError) as exc:
            raise KnowledgeAccessDenied("UNSUPPORTED_CONTEXT_VARIANT") from exc
        if (
            route.run_id != bundle.run_id
            or route.state_prefix_hash != bundle.state_prefix_hash
            or route.knowledge_manifest_hash != bundle.knowledge_manifest_hash
            or route.variant is not variant
            or route.route_hash != self._route_digest(route)
        ):
            raise KnowledgeAccessDenied("ROUTE_IDENTITY_MISMATCH")
        bundle_payload = {
            "run_id": bundle.run_id,
            "state_prefix_hash": bundle.state_prefix_hash,
            "knowledge_manifest_hash": bundle.knowledge_manifest_hash,
            "routes": {
                item.value: bundle.routes[item].route_hash for item in ContextVariant
            },
        }
        if bundle.bundle_hash != _sha256(_canonical_bytes(bundle_payload)):
            raise KnowledgeAccessDenied("ROUTE_BUNDLE_IDENTITY_MISMATCH")
        return route

    @staticmethod
    def _source_in_route(route: ContextRoute, path: str) -> RouteSource | None:
        return next(
            (
                source
                for source in (
                    route.base_sources + route.augmentation_sources + route.withheld_sources
                )
                if source.path == path
            ),
            None,
        )

    def _deny(
        self,
        bundle: RouteBundle,
        route: ContextRoute,
        tool: str,
        reason: str,
        *,
        source: RouteSource | None = None,
    ) -> None:
        self._record(
            bundle, route, "ROUTER_ACCESS", tool, "DENIED", reason, source=source
        )
        raise KnowledgeAccessDenied(reason)

    def _record(
        self,
        bundle: RouteBundle,
        route: ContextRoute,
        event: str,
        tool: str,
        decision: str,
        reason: str,
        *,
        source: RouteSource | None = None,
        returned_sha256: str | None = None,
        byte_range: tuple[int, int] | None = None,
        underlying_receipt_sequence: int | None = None,
    ) -> RouterReceipt:
        payload = {
            "sequence": len(self._receipts) + 1,
            "event": event,
            "tool": tool,
            "decision": decision,
            "reason": reason,
            "variant": route.variant.value,
            "run_id": bundle.run_id,
            "state_prefix_hash": bundle.state_prefix_hash,
            "knowledge_manifest_hash": bundle.knowledge_manifest_hash,
            "route_hash": route.route_hash,
            "base_corpus_hash": route.base_corpus_hash,
            "augmentation_hash": route.augmentation_hash,
            "component_label": source.component_label if source else None,
            "source_id": source.source_id if source else None,
            "source_path": source.path if source else None,
            "source_sha256": source.sha256 if source else None,
            "returned_sha256": returned_sha256,
            "byte_range": byte_range,
            "underlying_receipt_sequence": underlying_receipt_sequence,
            "primary_lock_eligible": (
                decision == "ALLOWED"
                and route.variant is ContextVariant.S135_CONTROL
                and (source is None or source.authority is not AuthorityClass.PROVISIONAL_SHADOW)
            ),
            "global_freeze_receipt_hash": (
                self._global_freeze.receipt_hash if self._global_freeze else None
            ),
        }
        receipt = RouterReceipt(**payload, receipt_hash=_sha256(_canonical_bytes(payload)))
        self._receipts.append(receipt)
        if self._receipt_sink is not None:
            self._receipt_sink(receipt)
        return receipt


__all__ = [
    "ComponentAvailability",
    "ContextRoute",
    "ContextVariant",
    "FrankieLaneAwareContextRouter",
    "GlobalExperimentFreezeReceipt",
    "ProvisionalComponent",
    "RouteBundle",
    "RouteSource",
    "RouterReceipt",
]
