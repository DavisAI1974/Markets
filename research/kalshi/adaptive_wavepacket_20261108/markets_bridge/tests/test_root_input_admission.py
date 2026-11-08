import unittest

from ..root_input_admission import audit_inputs, require_market_fields


class RootAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = audit_inputs()

    def test_exact_retained_inventories(self):
        self.assertEqual(len(self.audit["headings"]), 23)
        self.assertEqual(len(self.audit["paths"]), 324)
        self.assertEqual(len(self.audit["columns"]), 10286)
        self.assertEqual(len(self.audit["planes"]), 99)
        self.assertEqual(self.audit["coverage_gate"], "NOT_PASSED")

    def test_roles_distinguish_market_values_and_context(self):
        paths = {row["path"]: row for row in self.audit["paths"]}
        for path in (
            "ts_recv_ns", "input_records[].sequence", "input_records[].dbn_length",
            "native_frame.fifo_priority_reconstructed", "book.top_n",
            "observation.orders[].last_update_recv_ns", "activity.1.missing_reference_count",
        ):
            with self.subTest(path=path):
                self.assertEqual(paths[path]["disposition"], "context")
        self.assertEqual(paths["book.bid_levels_full[].fifo_queue[].priority_age_s"]["disposition"], "held")

    def test_actual_fitted_clock_states_and_encodings_stay_in_context(self):
        columns = self.audit["columns"]
        clocks = [r for r in columns if r["feature"].endswith(".last_update_clock_state")]
        ages = [r for r in columns if r["feature"].endswith(".last_update_age_ns")]
        encodings = [r for r in columns if r["source_path"] == "input_records[].rtype"]
        self.assertEqual((len(clocks), len(ages), len(encodings)), (4844, 4844, 399))
        self.assertTrue(all(r["disposition"] == "context" for r in clocks + encodings))
        self.assertTrue(all(r["disposition"] == "held" for r in ages))

    def test_source_bindings_distinguish_external_attachment_variants(self):
        dependencies = self.audit["dependencies"]
        self.assertEqual(len(dependencies["historic_external_13_bindings"]), 13)
        self.assertEqual(len(dependencies["second_set_component_names"]), 19)
        self.assertEqual(len(dependencies["historic_native_root_carriers"]), 5)
        attachments = dependencies["external_attachment_inventory"]
        self.assertEqual(attachments["20231002"]["status"], "NO_MATCHING_ATTACHMENT_IN_PINNED_INVENTORY")
        self.assertEqual(attachments["20231017"]["source_rows"], 363661)
        self.assertNotEqual(attachments["20231018"]["sha256"],
                            dependencies["historic_october18_external_primary"]["sha256"])

    def test_missing_coverage_and_unknown_names_fail_closed(self):
        for session in ("20231002", "20231003", "20231017", "20231018"):
            for columns in ((), ("root_full.activity.1.event_count",), ("trade_id",),
                            ("ts_recv_ns",), ("pnl",), ("prior_session_answer",)):
                with self.subTest(session=session, columns=columns):
                    with self.assertRaises(ValueError):
                        require_market_fields(session, columns)
