from __future__ import annotations

from types import SimpleNamespace

import ng_corpus_source_identity_attestation as identity


def test_databento_numeric_schema_enum_prefers_semantic_name():
    schema = SimpleNamespace(name="TRADES", value=4)
    assert identity._enum_text(schema) == "trades"
    assert identity._schema_matches(schema, "l1_trades") is True


def test_databento_mbo_numeric_schema_enum_prefers_semantic_name():
    schema = SimpleNamespace(name="MBO", value=0)
    assert identity._enum_text(schema) == "mbo"
    assert identity._schema_matches(schema, "mbo") is True


def test_value_only_enum_like_objects_remain_supported():
    stype = SimpleNamespace(value="RAW_SYMBOL")
    assert identity._enum_text(stype) == "raw-symbol"
