#!/usr/bin/env python3
"""Causal, missingness-safe immutable state assembler for NG Exhaustion V4.

The assembler consumes observations only when their lawful `available_at` is <= the
requested causal cutoff. It never backward-fills a previously frozen state and never
conflates missingness with numerical zero.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from research.kalshi.ng_exhaustion_v4_mechanics import (
    CausalField,
    Missingness,
    StateMovieRow,
    V4ContractError,
    make_state_row,
    validate_state_movie,
)


class StateAssemblerError(V4ContractError):
    pass


@dataclass(frozen=True)
class FieldPolicy:
    name: str
    source_identity_sha256: str
    stale_after_seconds: float
    carry_allowed: bool = True
    structurally_known_at: float | None = None
    applicable: bool = True

    def validate(self) -> "FieldPolicy":
        if not str(self.name or "").strip():
            raise StateAssemblerError("field policy name must be non-empty")
        if len(str(self.source_identity_sha256)) != 64:
            raise StateAssemblerError("source_identity_sha256 must be SHA-256")
        try:
            stale = float(self.stale_after_seconds)
        except (TypeError, ValueError, OverflowError) as exc:
            raise StateAssemblerError("stale_after_seconds must be finite") from exc
        if not math.isfinite(stale) or stale < 0:
            raise StateAssemblerError("stale_after_seconds must be non-negative finite")
        if self.structurally_known_at is not None:
            known = float(self.structurally_known_at)
            if not math.isfinite(known):
                raise StateAssemblerError("structurally_known_at must be finite")
        return self


@dataclass(frozen=True)
class Observation:
    field_name: str
    value: Any
    ts_event: float
    ts_recv: float
    available_at: float
    source_identity_sha256: str
    observation_id: str

    def validate(self) -> "Observation":
        if not str(self.field_name or "").strip() or not str(self.observation_id or "").strip():
            raise StateAssemblerError("observation field_name/id must be non-empty")
        if len(str(self.source_identity_sha256)) != 64:
            raise StateAssemblerError("observation source identity must be SHA-256")
        event=float(self.ts_event); recv=float(self.ts_recv); avail=float(self.available_at)
        if not all(math.isfinite(x) for x in (event,recv,avail)):
            raise StateAssemblerError("observation clocks must be finite")
        if event > avail or recv > avail:
            raise StateAssemblerError("observation event/receive clock cannot exceed available_at")
        return self


class CausalStateAssembler:
    def __init__(self, policies: Sequence[FieldPolicy], *, transform_sha256: str) -> None:
        if not policies:
            raise StateAssemblerError("at least one field policy is required")
        self.policies={}
        for policy in policies:
            policy.validate()
            if policy.name in self.policies:
                raise StateAssemblerError(f"duplicate field policy {policy.name}")
            self.policies[policy.name]=policy
        if len(str(transform_sha256)) != 64:
            raise StateAssemblerError("transform_sha256 must be SHA-256")
        self.transform_sha256=transform_sha256

    def _lawful_observations(self, *, field_name: str, cutoff: float,
                             observations: Sequence[Observation]) -> list[Observation]:
        out=[]; seen=set()
        for obs in observations:
            obs.validate()
            if obs.field_name != field_name:
                continue
            if obs.observation_id in seen:
                raise StateAssemblerError(f"duplicate observation_id {obs.observation_id}")
            seen.add(obs.observation_id)
            policy=self.policies[field_name]
            if obs.source_identity_sha256 != policy.source_identity_sha256:
                raise StateAssemblerError(f"source identity drift for {field_name}")
            if obs.available_at <= cutoff:
                out.append(obs)
        out.sort(key=lambda o:(o.available_at,o.ts_recv,o.ts_event,o.observation_id))
        return out

    def assemble_fields(self, *, cutoff: float, observations: Sequence[Observation]) -> tuple[CausalField,...]:
        cut=float(cutoff)
        if not math.isfinite(cut):
            raise StateAssemblerError("cutoff must be finite")
        fields=[]
        for name in sorted(self.policies):
            policy=self.policies[name]
            if not policy.applicable:
                fields.append(CausalField(name,Missingness.NOT_APPLICABLE,None,None,None,cut,
                                          policy.source_identity_sha256,None).validate(cutoff=cut))
                continue
            if policy.structurally_known_at is not None and cut < float(policy.structurally_known_at):
                fields.append(CausalField(name,Missingness.STRUCTURALLY_NOT_YET_KNOWN,None,None,None,cut,
                                          policy.source_identity_sha256,None).validate(cutoff=cut))
                continue
            lawful=self._lawful_observations(field_name=name,cutoff=cut,observations=observations)
            if not lawful:
                fields.append(CausalField(name,Missingness.MISSING,None,None,None,cut,
                                          policy.source_identity_sha256,None).validate(cutoff=cut))
                continue
            obs=lawful[-1]
            age=max(0.0,cut-float(obs.available_at))
            if age <= 1e-12:
                status=Missingness.OBSERVED
                age_out=None
            elif not policy.carry_allowed:
                fields.append(CausalField(name,Missingness.MISSING,None,None,None,cut,
                                          policy.source_identity_sha256,None).validate(cutoff=cut))
                continue
            elif age <= float(policy.stale_after_seconds):
                status=Missingness.PAST_CARRY; age_out=age
            else:
                status=Missingness.STALE; age_out=age
            fields.append(CausalField(
                name=name,status=status,value=obs.value,source_ts_event=float(obs.ts_event),
                source_ts_recv=float(obs.ts_recv),feature_available_at=float(obs.available_at),
                source_identity_sha256=policy.source_identity_sha256,age_seconds=age_out,
            ).validate(cutoff=cut))
        return tuple(fields)

    def append_state(self, *, instance_id: str, cutoff: float, event_known_by: float,
                     source_manifest_sha256: str, observations: Sequence[Observation],
                     prior_rows: Sequence[StateMovieRow]=()) -> StateMovieRow:
        cut=float(cutoff)
        if cut < float(event_known_by):
            raise StateAssemblerError("cannot assemble V4 state before event_known_by")
        if prior_rows:
            validate_state_movie(prior_rows)
            if prior_rows[-1].instance_id != instance_id:
                raise StateAssemblerError("prior movie belongs to another instance")
            if cut <= prior_rows[-1].causal_second:
                raise StateAssemblerError("cannot overwrite/backfill an already frozen causal second")
            prior_hash=prior_rows[-1].row_hash
        else:
            prior_hash="0"*64
        fields=self.assemble_fields(cutoff=cut,observations=observations)
        return make_state_row(
            instance_id=instance_id,causal_second=cut,event_known_by=float(event_known_by),fields=fields,
            source_manifest_sha256=source_manifest_sha256,transform_sha256=self.transform_sha256,
            prior_row_hash=prior_hash,
        )
