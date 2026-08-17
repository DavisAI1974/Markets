"""Canonical serialization, hashing, identifiers, and UTC clock helpers."""
from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any, Mapping


def to_primitive(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_primitive(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def hash_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_timestamp(value: str | dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value!r}")
    return parsed.astimezone(dt.timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"
