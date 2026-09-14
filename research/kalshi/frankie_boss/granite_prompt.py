"""Fixed, model-neutral C23 prompt over an unchanged SerializedState.

P7 applies to the whole rendered prompt, with no BLD-1 vocabulary exceptions.
This is a lexical answer wall, not a proof of upstream causal provenance; the
caller still owns authorized source selection and chronological separation.
No provider, training, replay, or Frankie integration occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .frankie_contract import BLD1_FIELD_NAMES
from .granite_contract import render_system_text
from .state_serialization import (
    SCHEMA_VERSION, SerializedState, parse_serialized_state, serialize_state,
)

PROMPT_VERSION = 'BOSS_GRANITE_PROMPT_V1'
SYSTEM_TEXT = render_system_text('serialized_v2')


@dataclass(frozen=True)
class GranitePrompt:
    version: str
    system_text: str
    snapshot_text: str
    snapshot_hash: str

    @property
    def system_prompt_hash(self) -> str:
        return hashlib.sha256(self.system_text.encode('utf-8')).hexdigest()

    @property
    def text(self) -> str:
        return (self.system_text + '\nsnapshot_hash: ' + self.snapshot_hash
                + '\nserialized_state:\n' + self.snapshot_text)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def build_prompt(snapshot: SerializedState) -> GranitePrompt:
    """Reject contaminated/noncanonical input; never sanitize or reserialize it."""
    if not isinstance(snapshot, SerializedState):
        raise TypeError('snapshot must be SerializedState')
    if snapshot.schema_version != SCHEMA_VERSION:
        raise ValueError('unsupported snapshot schema_version')
    restored = parse_serialized_state(snapshot.text)
    if serialize_state(restored).text != snapshot.text:
        raise ValueError('snapshot must use the canonical serialize_state text')
    # Inspect decoded strings too so JSON escapes cannot conceal vocabulary.
    source_strings = tuple(_strings(json.loads(snapshot.text)))
    for value in source_strings:
        tokens = set(re.findall(r'[a-z]+', value.lower()))
        if tokens.intersection({'target', 'targets', 'label', 'labels', 'outcome', 'outcomes'}):
            raise ValueError('answer wall: training or outcome vocabulary in state')
    prompt = GranitePrompt(PROMPT_VERSION, SYSTEM_TEXT, snapshot.text, snapshot.hash)
    for value in (prompt.text, *source_strings):
        lowered = value.lower()
        identifiers = set(re.findall(r'[a-z0-9_]+', lowered))
        if any(name in lowered if '_' in name else name in identifiers
               for name in BLD1_FIELD_NAMES):
            raise ValueError('answer wall: prohibited BLD-1 vocabulary')
    return prompt
