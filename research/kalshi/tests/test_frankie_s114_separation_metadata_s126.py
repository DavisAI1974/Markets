from __future__ import annotations

from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s114_separation_metadata_s126 as sep  # noqa: E402


def _rec(**extra):
    base = {"wind_cf_proxy": 0.25, "solar_irradiance_proxy": 400.0}
    base.update(extra)
    return base


def test_missing_legacy_flag_is_added_only_when_both_separate_proxies_exist():
    store = {"20260720": _rec()}
    out, changed = sep.normalize_store(store, ["20260720"])
    assert changed == ["20260720"]
    assert out["20260720"]["served_separately"] is True
    assert out["20260720"]["wind_cf_proxy"] == store["20260720"]["wind_cf_proxy"]
    assert out["20260720"]["solar_irradiance_proxy"] == store["20260720"]["solar_irradiance_proxy"]
    assert "served_separately" not in store["20260720"]


def test_existing_true_flag_is_preserved_without_change():
    out, changed = sep.normalize_store(
        {"20260720": _rec(served_separately=True)}, ["20260720"]
    )
    assert changed == []
    assert out["20260720"]["served_separately"] is True


@pytest.mark.parametrize("value", [False, None, 0, "true"])
def test_explicit_non_true_flag_fails_closed(value):
    with pytest.raises(sep.SeparationMetadataError, match="explicit served_separately"):
        sep.normalize_store({"20260720": _rec(served_separately=value)}, ["20260720"])


@pytest.mark.parametrize("missing_key", ["wind_cf_proxy", "solar_irradiance_proxy"])
def test_missing_or_null_proxy_cannot_be_relabelled_as_separate(missing_key):
    rec = _rec()
    rec[missing_key] = None
    with pytest.raises(sep.SeparationMetadataError, match=missing_key):
        sep.normalize_store({"20260720": rec}, ["20260720"])


def test_missing_required_day_fails_closed():
    with pytest.raises(sep.SeparationMetadataError, match="forcing record missing"):
        sep.normalize_store({"20260720": _rec()}, ["20260721"])
