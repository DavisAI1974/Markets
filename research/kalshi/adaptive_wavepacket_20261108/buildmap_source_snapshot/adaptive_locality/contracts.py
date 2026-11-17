"""Strict, source-bound, historical-only metric calibration and validation."""
from dataclasses import dataclass
import math
from .core import LocalityError, MetricContract, Observation, _digest


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    unit: str
    scale: float
    weight: float

    def __post_init__(self):
        if not self.name or not self.unit:
            raise LocalityError("feature name and unit required")
        if self.name.lower().endswith(("id", "_id", "name", "descriptor")):
            raise LocalityError("identifier cannot be a metric feature")
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise LocalityError("invalid frozen scale")
        if not math.isfinite(self.weight) or self.weight < 0:
            raise LocalityError("invalid frozen weight")


@dataclass(frozen=True)
class Calibration:
    source_identity: str
    schema_identity: str
    training_cutoff: int
    version: str
    features: tuple[FeatureSpec, ...]

    def __post_init__(self):
        if not self.source_identity or not self.schema_identity or not self.version:
            raise LocalityError("calibration identities required")
        if type(self.training_cutoff) is not int:
            raise LocalityError("integer training cutoff required")
        if not self.features or len({f.name for f in self.features}) != len(self.features):
            raise LocalityError("unique calibrated features required")
        if not any(f.weight > 0 for f in self.features):
            raise LocalityError("metric cannot have all zero weights")

    def identity(self) -> str:
        return _digest({"source": self.source_identity, "schema": self.schema_identity,
                        "cutoff": self.training_cutoff, "version": self.version,
                        "features": [f.__dict__ for f in self.features]})

    def metric(self) -> MetricContract:
        return MetricContract(tuple(f.name for f in self.features),
                              tuple(f.scale for f in self.features),
                              tuple(f.weight for f in self.features),
                              self.identity())

    def validate_observation(self, obs: Observation, *, historical: bool = False) -> None:
        if historical and obs.event_clock > self.training_cutoff:
            raise LocalityError("lookahead: training observation after cutoff")
        self.metric().vector(obs)
        for feature in self.features:
            normalized = obs.features[feature.name] / feature.scale
            if not math.isfinite(normalized):
                raise LocalityError("normalized feature overflow; abstain")

    def validate_history(self, observations: list[Observation]) -> None:
        seen = {}
        for obs in observations:
            self.validate_observation(obs, historical=True)
            if obs.event_id in seen and seen[obs.event_id] != obs.identity():
                raise LocalityError("contradictory history identity")
            seen[obs.event_id] = obs.identity()
