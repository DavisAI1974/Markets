from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_cognition import CognitiveContractError  # noqa: E402
from frankie_microstructure_p0_baselines import (  # noqa: E402
    BookGuardPolicy,
    FitPolicy,
    ResiliencyPolicy,
    aggregate_causal_ofi_windows,
    build_lag_only_forecast_rows,
    compute_level1_ofi_events,
    fit_matched_resiliency_baselines,
    label_depletion_resiliency_episodes,
    predict_matched_resiliency_baselines,
    score_resiliency_forecasts,
    validate_lag_only_forecast_rows,
)


class FrankieMicrostructureP0BaselineTests(unittest.TestCase):
    @staticmethod
    def guard():
        return BookGuardPolicy(
            max_book_age_seconds=0.5,
            max_interarrival_seconds=2.0,
            tick_size=0.25,
        )

    @staticmethod
    def books():
        # BID shock at t=3 refills at t=5; ASK shock at t=7 does not refill by t=10.
        values = [
            # t, bid, bid size, ask, ask size, trade volume
            (0, 100.00, 10, 100.50, 10, 0),
            (1, 100.00, 12, 100.50, 9, 3),
            (2, 100.00, 11, 100.50, 8, 2),
            (3, 100.00, 4, 100.50, 8, 5),
            (4, 100.00, 7, 100.50, 8, 1),
            (5, 100.00, 9, 100.50, 8, 1),
            (6, 100.00, 9, 100.50, 10, 2),
            (7, 100.00, 9, 100.50, 3, 4),
            (8, 100.00, 9, 100.50, 4, 1),
            (9, 100.00, 9, 100.50, 4, 0),
            (10, 100.00, 9, 100.50, 4, 0),
        ]
        return [
            {
                "stream_id": "NG:20260820",
                "snapshot_id": f"s{index}",
                "sequence": index,
                "observed_timestamp": timestamp,
                "book_timestamp": timestamp - 0.1,
                "bid_price": bid,
                "bid_size": bid_size,
                "ask_price": ask,
                "ask_size": ask_size,
                "trade_volume_since_previous": volume,
            }
            for index, (timestamp, bid, bid_size, ask, ask_size, volume) in enumerate(values)
        ]

    @staticmethod
    def resiliency_policy():
        return ResiliencyPolicy(
            minimum_depletion_fraction=0.5,
            refill_fraction_of_reference_depth=0.8,
            refill_horizon_seconds=3.0,
        )

    def test_cont_level1_ofi_equation_and_sign_are_deterministic(self):
        books = self.books()[:3]
        result = compute_level1_ofi_events(books, self.guard())
        self.assertEqual(result["event_count"], 2)
        # t1: bid +2 and ask +1 => +3. t2: bid -1 and ask +1 => 0.
        self.assertEqual(result["events"][0]["bid_contribution"], 2.0)
        self.assertEqual(result["events"][0]["ask_contribution"], 1.0)
        self.assertEqual(result["events"][0]["ofi"], 3.0)
        self.assertEqual(result["events"][0]["ofi_sign"], 1)
        self.assertEqual(result["events"][1]["ofi"], 0.0)
        self.assertEqual(
            result["receipt_hash"],
            compute_level1_ofi_events(copy.deepcopy(books), self.guard())["receipt_hash"],
        )

    def test_causal_window_aggregates_magnitude_and_sign_without_future_events(self):
        result = compute_level1_ofi_events(self.books()[:5], self.guard())
        aggregate = aggregate_causal_ofi_windows(result, trailing_window_seconds=2.5)
        last = aggregate["aggregates"][-1]
        self.assertEqual(last["as_of_timestamp"], 4.0)
        self.assertEqual(last["source_max_timestamp"], 4.0)
        self.assertEqual(last["event_count"], 3)
        self.assertEqual(
            last["positive_event_count"]
            + last["negative_event_count"]
            + last["zero_event_count"],
            last["event_count"],
        )
        extended = compute_level1_ofi_events(self.books()[:6], self.guard())
        extended_aggregate = aggregate_causal_ofi_windows(
            extended, trailing_window_seconds=2.5
        )
        same_as_of = next(
            row for row in extended_aggregate["aggregates"] if row["as_of_timestamp"] == 4.0
        )
        self.assertEqual(last["aggregate_hash"], same_as_of["aggregate_hash"])

    def test_book_guards_reject_stale_crossed_sequence_and_time_gaps(self):
        stale = self.books()[:3]
        stale[1] = {**stale[1], "book_timestamp": 0.0}
        with self.assertRaises(CognitiveContractError):
            compute_level1_ofi_events(stale, self.guard())

        crossed = self.books()[:3]
        crossed[1] = {**crossed[1], "bid_price": crossed[1]["ask_price"]}
        with self.assertRaises(CognitiveContractError):
            compute_level1_ofi_events(crossed, self.guard())

        sequence_gap = self.books()[:3]
        sequence_gap[1] = {**sequence_gap[1], "sequence": 4}
        with self.assertRaises(CognitiveContractError):
            compute_level1_ofi_events(sequence_gap, self.guard())

        time_gap = self.books()[:3]
        time_gap[1] = {
            **time_gap[1],
            "observed_timestamp": 4.0,
            "book_timestamp": 3.9,
        }
        with self.assertRaises(CognitiveContractError):
            compute_level1_ofi_events(time_gap, self.guard())

    def test_episode_labels_distinguish_refill_nonreplenishment_and_censoring(self):
        result = label_depletion_resiliency_episodes(
            self.books(), self.guard(), self.resiliency_policy()
        )
        by_side = {episode["side"]: episode for episode in result["episodes"]}
        self.assertEqual(by_side["BID"]["onset_timestamp"], 3.0)
        self.assertEqual(by_side["BID"]["status"], "REFILLED")
        self.assertEqual(by_side["BID"]["label_reveal_timestamp"], 5.0)
        self.assertEqual(by_side["BID"]["outcome_label"], 1)
        self.assertEqual(by_side["ASK"]["onset_timestamp"], 7.0)
        self.assertEqual(by_side["ASK"]["status"], "NON_REPLENISHED")
        self.assertEqual(by_side["ASK"]["label_reveal_timestamp"], 10.0)
        self.assertEqual(by_side["ASK"]["outcome_label"], 0)

        censored = label_depletion_resiliency_episodes(
            self.books()[:-2], self.guard(), self.resiliency_policy()
        )
        ask = next(row for row in censored["episodes"] if row["side"] == "ASK")
        self.assertEqual(ask["status"], "CENSORED")
        self.assertIsNone(ask["outcome_label"])
        self.assertIsNone(ask["label_reveal_timestamp"])

    def test_future_refill_changes_label_only_not_onset_or_lag_features(self):
        books = self.books()
        ofi = compute_level1_ofi_events(books, self.guard())
        episodes = label_depletion_resiliency_episodes(
            books, self.guard(), self.resiliency_policy()
        )
        splits = {row["episode_id"]: "TRAIN" for row in episodes["episodes"]}
        features = build_lag_only_forecast_rows(
            ofi, episodes, splits, lookback_seconds=3.0
        )
        original_bid = next(row for row in features["rows"] if row["side"] == "BID")

        changed = copy.deepcopy(books)
        changed[4] = {**changed[4], "bid_size": 5}
        changed[5] = {**changed[5], "bid_size": 5}
        changed[6] = {**changed[6], "bid_size": 5}
        changed_episodes = label_depletion_resiliency_episodes(
            changed, self.guard(), self.resiliency_policy()
        )
        changed_splits = {
            row["episode_id"]: "TRAIN" for row in changed_episodes["episodes"]
        }
        changed_features = build_lag_only_forecast_rows(
            compute_level1_ofi_events(changed, self.guard()),
            changed_episodes,
            changed_splits,
            lookback_seconds=3.0,
        )
        changed_bid = next(row for row in changed_features["rows"] if row["side"] == "BID")
        self.assertEqual(original_bid["onset_observation_hash"], changed_bid["onset_observation_hash"])
        self.assertEqual(original_bid["feature_values"], changed_bid["feature_values"])
        self.assertEqual(original_bid["feature_cutoff_timestamp"], 2.0)
        self.assertEqual(changed_bid["label"], 0)

    def test_lag_contract_rejects_onset_or_future_features(self):
        rows = self._synthetic_rows("TRAIN", 4)
        bad = copy.deepcopy(rows)
        bad[0]["feature_cutoff_timestamp"] = bad[0]["forecast_timestamp"]
        for name in bad[0]["feature_source_timestamps"]:
            bad[0]["feature_source_timestamps"][name] = bad[0]["forecast_timestamp"]
        with self.assertRaises(CognitiveContractError):
            validate_lag_only_forecast_rows(bad, require_resolved_labels=True)

    @staticmethod
    def _synthetic_rows(split: str, count: int, *, offset: int = 0):
        rows = []
        for index in range(offset, offset + count):
            forecast = float(100 + 10 * index)
            label = index % 2
            values = {
                "lag_side_aligned_ofi": 2.0 if label else -2.0,
                "lag_side_aligned_mid_change": 0.5 if label else -0.5,
                "lag_trade_volume": 10.0 if label else 1.0,
                "lag_side_aligned_static_imbalance": 0.4 if label else -0.4,
            }
            rows.append(
                {
                    "case_id": f"case-{index}",
                    "stream_id": "NG",
                    "instrument_day": f"2026-08-{10 + index:02d}",
                    "side": "BID" if index % 2 else "ASK",
                    "split": split,
                    "forecast_timestamp": forecast,
                    "feature_cutoff_timestamp": forecast - 1.0,
                    "feature_values": values,
                    "feature_source_timestamps": {
                        name: forecast - 1.0 for name in values
                    },
                    "label_status": "REFILLED" if label else "NON_REPLENISHED",
                    "label": label,
                    "label_reveal_timestamp": forecast + 5.0,
                    "onset_observation_hash": "a" * 64,
                    "lag_event_ids": [f"event-{index}"],
                }
            )
        return rows

    def test_train_only_fit_has_matched_controls_and_exact_fingerprints(self):
        train = self._synthetic_rows("TRAIN", 8)
        fit = fit_matched_resiliency_baselines(
            train, FitPolicy(iterations=50, learning_rate=0.1)
        )
        self.assertEqual(
            set(fit["models"]),
            {"OFI", "PRICE_ONLY_CONTROL", "VOLUME_ONLY_CONTROL", "STATIC_IMBALANCE_CONTROL"},
        )
        self.assertTrue(fit["matching_contract"]["same_case_ids"])
        self.assertEqual(
            {model["feature_dimension"] for model in fit["models"].values()}, {1}
        )
        self.assertEqual(
            {model["train_rows_hash"] for model in fit["models"].values()},
            {fit["train_rows_hash"]},
        )

        changed = copy.deepcopy(train)
        changed[0]["feature_values"]["lag_trade_volume"] += 1.0
        changed_fit = fit_matched_resiliency_baselines(
            changed, FitPolicy(iterations=50, learning_rate=0.1)
        )
        self.assertNotEqual(fit["train_rows_hash"], changed_fit["train_rows_hash"])

        with self.assertRaises(CognitiveContractError):
            fit_matched_resiliency_baselines(self._synthetic_rows("OOT", 4))

    def test_frozen_predictions_score_complete_matrix_and_exclude_censored(self):
        train = self._synthetic_rows("TRAIN", 8)
        fit = fit_matched_resiliency_baselines(
            train, FitPolicy(iterations=100, learning_rate=0.1)
        )
        evaluation = self._synthetic_rows("OOT", 4, offset=20)
        censored = copy.deepcopy(evaluation[-1])
        censored["case_id"] = "case-censored"
        censored["label_status"] = "CENSORED"
        censored["label"] = None
        censored["label_reveal_timestamp"] = None
        evaluation.append(censored)
        predictions = predict_matched_resiliency_baselines(fit, evaluation)
        self.assertEqual(predictions["prediction_count"], 4 * len(evaluation))
        score = score_resiliency_forecasts(predictions, evaluation)
        self.assertEqual(score["resolved_row_count"], 4)
        self.assertEqual(score["censored_row_count"], 1)
        self.assertEqual(score["claim"], "METRICS_ONLY_NO_PASS_OR_FORWARD_GAIN_CLAIM")
        self.assertEqual(set(score["metrics"]), set(fit["models"]))

        tampered = copy.deepcopy(predictions)
        tampered_core = {
            key: value for key, value in tampered.items() if key != "receipt_hash"
        }
        tampered_core["predictions"] = tampered_core["predictions"][:-1]
        from frankie_cognition import sha256_json

        tampered = {**tampered_core, "receipt_hash": sha256_json(tampered_core)}
        with self.assertRaises(CognitiveContractError):
            score_resiliency_forecasts(tampered, evaluation)

    def test_eval_fit_overlap_is_rejected(self):
        train = self._synthetic_rows("TRAIN", 4)
        fit = fit_matched_resiliency_baselines(train)
        overlap = copy.deepcopy(train)
        for row in overlap:
            row["split"] = "OOT"
        with self.assertRaises(CognitiveContractError):
            predict_matched_resiliency_baselines(fit, overlap)


if __name__ == "__main__":
    unittest.main()
