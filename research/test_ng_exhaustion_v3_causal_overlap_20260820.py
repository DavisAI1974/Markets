#!/usr/bin/env python3
from __future__ import annotations

import unittest

import numpy as np

import ng_exhaustion_chain_recovery_features_v2_20260819 as v2
import ng_exhaustion_chain_recovery_features_v3_20260819 as v3


class CausalOverlapRegressionTests(unittest.TestCase):
    @staticmethod
    def event(polarity: int = -1):
        return {
            "event_id": "20251102-083177--1",
            "t0_idx": 83177,
            "polarity": polarity,
            "family": "A",
            "pre_family_distances": [],
            "a_frozen_post_state": "A-persistent",
            "seed_state": "persistent_exhaustion",
            "feature": {},
            "dynamic_endpoint": {
                "causal_confirmation_idx": 83263,
                "structural_onset_offset_s": 84,
            },
            "time_context": {},
        }

    @staticmethod
    def cache():
        times = np.arange(83170, 83281, dtype=float)
        prices = 3.0 + (times - times[0]) * 0.001
        return {"times": {"20251102": times}, "prices": {"20251102": prices}}

    def test_exact_failed_overlap_clock_is_valid_at_successor_t0(self):
        case = {"preds": [self.event()], "target": {"t0_idx": 83223}}
        self.assertIsNone(v3.checkpoint(case, "PRIOR", 0))
        self.assertEqual(v3.checkpoint(case, v3.BIRTH_T0_PHASE, 0), (83223, 0))
        self.assertEqual(v3.checkpoint(case, "POST_BIRTH", 1), (83224, 0))

    def test_preconfirm_predecessor_is_raw_unoriented_and_structure_withheld(self):
        negative = v2.event_vector(
            self.event(-1), "20251102", 83223, self.cache(), False, "FULL_CAUSAL", True
        )
        positive = v2.event_vector(
            self.event(+1), "20251102", 83223, self.cache(), False, "FULL_CAUSAL", True
        )
        np.testing.assert_array_equal(negative, positive)
        np.testing.assert_array_equal(negative[:48], np.zeros(48))
        self.assertTrue(np.any(negative[48:] != 0.0))

    def test_structure_and_polarity_appear_only_after_own_confirmation(self):
        before = v2.event_vector(
            self.event(-1), "20251102", 83223, self.cache(), False, "NO_PRICE_CAUSAL", True
        )
        after = v2.event_vector(
            self.event(-1), "20251102", 83263, self.cache(), False, "NO_PRICE_CAUSAL", True
        )
        np.testing.assert_array_equal(before, np.zeros(48))
        self.assertTrue(np.any(after != 0.0))
        self.assertEqual(v2.CAUSAL_OVERLAP_FIX_REVISION, "V3_CAUSAL_OVERLAP_SAFE_20260820")

    def test_all_logged_failure_shapes_are_valid_preconfirmation_states(self):
        logged = (
            ("20251102-083177--1", 83177, 83223, 83263),
            ("20251102-091321-+1", 91321, 91367, 91458),
            ("20251102-103539--1", 103539, 103704, 103739),
            ("20260322-169709-+1", 169709, 169802, 169804),
        )
        for event_id, t0, cutoff, confirm in logged:
            with self.subTest(event_id=event_id):
                event = self.event(-1)
                event["event_id"] = event_id
                event["t0_idx"] = t0
                event["dynamic_endpoint"]["causal_confirmation_idx"] = confirm
                times = np.arange(t0 - 10, confirm + 10, dtype=float)
                cache = {
                    "times": {"week": times},
                    "prices": {"week": 3.0 + (times - times[0]) * 0.001},
                }
                row = v2.event_vector(event, "week", cutoff, cache, False, "NO_PRICE_CAUSAL", True)
                np.testing.assert_array_equal(row, np.zeros(48))


if __name__ == "__main__":
    unittest.main()
