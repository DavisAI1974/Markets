import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_coordinator_guard import (  # noqa: E402
    DAYS,
    LETTERS,
    OWNER,
    CoordinatorGuardError,
    build_guard_report,
    validate_guard_report,
)


def entry(day: str, owner: str, *, net: float | None = None) -> dict:
    value = float(net if net is not None else (list(DAYS).index(day) + 1) * (10 if owner in {"A", "C", "E"} else -10))
    return {
        "date": day,
        "expected_magnitude_usd": value,
        "path_p50_curve": [[20, 0], [22, value]],
        "posterior_direction_by_horizon": {"close": "up" if value > 0 else "down"},
        "confidence": 0.6,
        "selection_reason": f"specialist {owner} owns {day}",
        "execution_authority": False,
    }


class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.claims = {letter: [] for letter in LETTERS}
        for day in DAYS:
            self.claims[OWNER[day]].append(entry(day, OWNER[day]))
        self.write_specialists()
        self.refined = self.make_refined()
        self.refined_path = self.root / "grp15_mbo_refined.json"
        self.write_refined()

    def close(self):
        self.temp.cleanup()

    def write_specialists(self):
        for letter in LETTERS:
            (self.root / f"grp15_mbo_specialist_{letter}.json").write_text(
                json.dumps({"specialist": letter, "days": self.claims[letter]}), encoding="utf-8"
            )

    def make_refined(self):
        rows = []
        for day in DAYS:
            source = next(row for row in self.claims[OWNER[day]] if row["date"] == day)
            rows.append({
                "date": day,
                "owner_specialist": OWNER[day],
                "refined_net_usd": source["expected_magnitude_usd"],
                "refined_path_p50": copy.deepcopy(source["path_p50_curve"]),
                "posterior_direction_by_horizon": copy.deepcopy(source["posterior_direction_by_horizon"]),
                "selection_reason": source["selection_reason"],
                "execution_authority": False,
            })
        return {
            "group": 15,
            "method": "five specialists; coordinator SELECTS owner per day; NO averaging",
            "days": rows,
        }

    def write_refined(self):
        self.refined_path.write_text(json.dumps(self.refined), encoding="utf-8")


class CoordinatorGuardTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.close()

    def build(self):
        return build_guard_report(specialist_dir=self.fx.root, refined_path=self.fx.refined_path)

    def test_ready_selection_checks_all_canonical_days(self):
        report = self.build()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual([row["date"] for row in report["checked_days"]], list(DAYS))
        self.assertFalse(report["may_average_specialists"])
        self.assertFalse(report["may_fallback_to_blind_when_owner_missing"])
        validate_guard_report(report)

    def test_wrong_owner_claim_is_rejected(self):
        moved = self.fx.claims["A"].pop(0)
        self.fx.claims["B"].append(moved)
        self.fx.write_specialists()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_duplicate_claim_is_rejected(self):
        self.fx.claims["A"].append(copy.deepcopy(self.fx.claims["A"][0]))
        self.fx.write_specialists()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_missing_owner_claim_is_rejected(self):
        self.fx.claims["A"].pop(0)
        self.fx.write_specialists()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_curve_endpoint_must_equal_selected_magnitude(self):
        self.fx.claims["A"][0]["path_p50_curve"][-1][1] += 5
        self.fx.write_specialists()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_refined_owner_must_match_canonical_owner(self):
        self.fx.refined["days"][0]["owner_specialist"] = "B"
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_refined_net_cannot_be_average_or_fallback(self):
        row = self.fx.refined["days"][0]
        row["refined_net_usd"] = row["refined_net_usd"] / 2
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_refined_path_must_be_selected_verbatim(self):
        self.fx.refined["days"][0]["refined_path_p50"][-1][1] += 1
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_refined_direction_must_be_selected_verbatim(self):
        self.fx.refined["days"][0]["posterior_direction_by_horizon"]["close"] = "flat"
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_method_must_explicitly_forbid_averaging(self):
        self.fx.refined["method"] = "ensemble of five agents"
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_execution_authority_is_forbidden(self):
        self.fx.refined["days"][0]["execution_authority"] = True
        self.fx.write_refined()
        with self.assertRaises(CoordinatorGuardError):
            self.build()

    def test_guard_report_tampering_is_rejected(self):
        report = self.build()
        report["checked_days"][0]["net"] += 1
        with self.assertRaises(CoordinatorGuardError):
            validate_guard_report(report)

    def test_inputs_are_not_mutated(self):
        claims_before = copy.deepcopy(self.fx.claims)
        refined_before = copy.deepcopy(self.fx.refined)
        self.build()
        self.assertEqual(self.fx.claims, claims_before)
        self.assertEqual(self.fx.refined, refined_before)


if __name__ == "__main__":
    unittest.main()
