"""A-59: NOOA-style render target over the existing canonical store.

This does NOT replace spawn.py. It proves the structural claim first: an agent object can render the
same canonical prompt bytes from the same store and lookups, while typed writes fail at emission.
"""
from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import spawn


class RenderContractError(RuntimeError):
    pass


def _substitute_known_slots(body: str, slot_map: Mapping[str, tuple[Any, str]]) -> str:
    out = body
    for key, (value, _source) in slot_map.items():
        out = out.replace("{%s}" % key, str(value))
    return out


@dataclass(frozen=True)
class FrankieAgentObject:
    """The agent is an object: explicit state + deterministic render methods.

    Model-completed work is intentionally not implemented here. A-59's first acceptance gate is
    structural equivalence with the current deterministic emitter.
    """

    template: str
    gid: str
    day: str | None = None
    specialist: str | None = None
    directive: str | None = None

    def render_prompt(self) -> str:
        slot_map = spawn.slots(self.gid, self.day, self.specialist)
        if self.directive is not None:
            slot_map["DIRECTIVE"] = (
                self.directive,
                "argument, quoted verbatim per SOP STEP 5.1",
            )
        templates = spawn.templates()
        if self.template not in templates:
            raise RenderContractError(f"unknown template {self.template!r}")
        body = templates[self.template]["body"]
        needed = set(re.findall(r"\{([A-Za-z_0-9]+)\}", body))
        missing = sorted(needed - set(slot_map))
        if missing:
            raise RenderContractError(f"unresolved canonical slots: {missing}")
        return _substitute_known_slots(body, slot_map)


def canonical_spawn_render(
    *, template: str, gid: str, day: str | None = None, specialist: str | None = None,
    directive: str | None = None,
) -> str:
    """Reference render using spawn.py's canonical store and substitution semantics."""
    slot_map = spawn.slots(gid, day, specialist)
    if directive is not None:
        slot_map["DIRECTIVE"] = (directive, "reference input")
    body = spawn.templates()[template]["body"]
    needed = set(re.findall(r"\{([A-Za-z_0-9]+)\}", body))
    missing = sorted(needed - set(slot_map))
    if missing:
        raise RenderContractError(f"reference render unresolved slots: {missing}")
    return _substitute_known_slots(body, slot_map)


def assert_byte_identical(agent: FrankieAgentObject) -> None:
    got = agent.render_prompt().encode("utf-8")
    want = canonical_spawn_render(
        template=agent.template,
        gid=agent.gid,
        day=agent.day,
        specialist=agent.specialist,
        directive=agent.directive,
    ).encode("utf-8")
    if got != want:
        raise RenderContractError(
            f"A-59 render mismatch: Frankie={len(got)} bytes canonical={len(want)} bytes"
        )


@dataclass(frozen=True)
class TypedPosterior:
    group: str
    day: str
    specialist: str
    direction: str
    magnitude: float | int | None
    fired: tuple[str, ...]
    stood_down: tuple[str, ...]
    reasoning: str
    source_hashes: tuple[str, ...]
    execution_enabled: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TypedPosterior":
        required = (
            "group", "day", "specialist", "direction", "fired", "stood_down", "reasoning",
            "source_hashes",
        )
        missing = [key for key in required if key not in raw]
        if missing:
            raise RenderContractError(f"typed posterior missing required field(s): {missing}")
        direction = str(raw["direction"]).upper()
        if direction not in {"UP", "DOWN", "FLAT", "STAND_DOWN"}:
            raise RenderContractError(f"invalid posterior direction: {direction}")
        if raw.get("execution_enabled") is True:
            raise RenderContractError("posterior may not enable execution")
        fired = raw["fired"]
        stood = raw["stood_down"]
        hashes = raw["source_hashes"]
        if not isinstance(fired, (list, tuple)) or not all(isinstance(v, str) for v in fired):
            raise RenderContractError("fired must be a string list")
        if not isinstance(stood, (list, tuple)) or not all(isinstance(v, str) for v in stood):
            raise RenderContractError("stood_down must be a string list")
        if not isinstance(hashes, (list, tuple)) or not hashes or not all(isinstance(v, str) for v in hashes):
            raise RenderContractError("source_hashes must be a non-empty string list")
        return cls(
            group=str(raw["group"]),
            day=str(raw["day"]),
            specialist=str(raw["specialist"]),
            direction=direction,
            magnitude=raw.get("magnitude"),
            fired=tuple(fired),
            stood_down=tuple(stood),
            reasoning=str(raw["reasoning"]),
            source_hashes=tuple(hashes),
            execution_enabled=False,
        )

    def write(self, path: Path) -> None:
        """Malformed output fails here, before a coordinator can consume it."""
        payload = dataclasses.asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
