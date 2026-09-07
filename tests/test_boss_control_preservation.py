"""Small synthetic controls for the approved BOSS interface extension.

The two source fixtures are byte-for-byte git blobs from
beb548b86b777dc69bf834950b30cc28000e16ef:
research/kalshi/frankie_boss/{trunk,causal_packet}.py. They are deliberately
frozen, never imported by production, and require no runtime git access.
Input fixtures are the existing test_trunk.cfg/batch and test_causal_prefix
scope/group/ACTIONS_0 fixtures. No training, provider or market-data run occurs.
"""

from dataclasses import asdict
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
BOSS = ROOT / "research" / "kalshi" / "frankie_boss"
PINNED = Path(__file__).parent / "fixtures" / "boss_control_beb548b8"
for path in (ROOT, BOSS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import trunk


def _load(name, path, expected_sha256=None):
    if expected_sha256 is not None:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256, (
            f"pinned beb548b8 source changed: {path.name}"
        )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def historical_trunk():
    return _load(
        "_boss_control_trunk_beb548b8",
        PINNED / "trunk_v1.py",
        "82d2a3ac73cc7d2f7d03d39fd0ef9c96d615f1c611084d702a4a506bbe573c33",
    )


@pytest.fixture(scope="module")
def trunk_fixtures():
    # The existing fixture module seeds torch on import. Keep that side effect
    # local so this preservation test does not alter other tests' RNG state.
    with torch.random.fork_rng(devices=[]):
        return _load("_boss_control_trunk_fixtures", BOSS / "tests" / "test_trunk.py")


@pytest.mark.parametrize("use_qsv", [False, True])
def test_v1_weights_preserve_every_hidden_state_with_masks_omitted(
    historical_trunk, trunk_fixtures, use_qsv
):
    config = trunk_fixtures.cfg(use_qsv=use_qsv)
    inputs = trunk_fixtures.batch(config)
    args = (
        inputs["numeric"], inputs["categorical"], inputs["venue_id"],
        inputs["instrument_id"], inputs["parent"],
        inputs["qsv"] if use_qsv else None,
    )
    with torch.random.fork_rng(devices=[]), torch.no_grad():
        torch.manual_seed(20260907)
        old = historical_trunk.Trunk(
            historical_trunk.TrunkConfig(**asdict(config))
        ).eval()
        current = trunk.Trunk(config).eval()
        compatibility = current.load_state_dict(old.state_dict(), strict=False)
        assert compatibility.unexpected_keys == []
        expected_new_parameters = {
            "encoder.numeric_missing.weight", "encoder.categorical_missing",
        }
        if use_qsv:
            expected_new_parameters.add("encoder.qsv_missing.weight")
        assert set(compatibility.missing_keys) == expected_new_parameters
        expected = old.represent(*args)
        actual = current.represent(*args)
    assert torch.equal(actual, expected), (
        "loading v1 weights with the same config and omitted masks changed "
        f"hidden states (use_qsv={use_qsv})"
    )


def test_control_default_attention_window_remains_128():
    assert trunk.TrunkConfig().window == 128


def test_control_default_qsv_branch_remains_disabled():
    assert trunk.TrunkConfig().use_qsv is False


def test_interface_extension_uses_trunk_v2_schema():
    assert trunk.TRUNK_SCHEMA == "BOSS_TRUNK_V2"


def test_legacy_canonical_bytes_match_v1_for_existing_prefix_fixture(monkeypatch):
    historical_packet = _load(
        "_boss_control_packet_beb548b8",
        PINNED / "causal_packet_v1.py",
        "ea7b7acf43ea2eb03e279acef19b0385dda4a9cd6b3a9e5d53bdab99945e1fc8",
    )
    fixtures = _load(
        "_boss_control_prefix_fixtures", BOSS / "tests" / "test_causal_prefix.py"
    )
    current_canonical = fixtures.cp.canonical_bytes
    comparisons = []

    def checked_canonical(payload):
        current = current_canonical(payload)
        historical = historical_packet.canonical_bytes(payload)
        comparisons.append((current, historical))
        return current

    # Compare every actual serialization used for genesis, actions, prefix
    # and receipt construction, including the action validation calls.
    monkeypatch.setattr(fixtures.cp, "canonical_bytes", checked_canonical)
    chain = fixtures.ProbeGroupPrefixChain(fixtures.scope())
    genesis = chain.prefix_hash
    receipt = chain.advance(fixtures.group(actions=fixtures.ACTIONS_0))
    assert comparisons
    for current, historical in comparisons:
        assert current == historical
    assert (genesis, receipt.prefix_hash, receipt.receipt_hash) == (
        fixtures.KNOWN_GENESIS, fixtures.KNOWN_PREFIX_0, fixtures.KNOWN_RECEIPT_0,
    )
