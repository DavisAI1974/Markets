import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("data_registry_s123", HERE / "data_registry.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class DataRegistryS123Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = mod.build()

    def test_accepted_surface_is_locked_to_live_measurement(self):
        accepted = self.store["accepted_measurement"]
        self.assertEqual(accepted["served"], 1914)
        self.assertEqual(accepted["decision_state_blocks"], 44)
        self.assertEqual(accepted["served_unread"], 1222)

    def test_committed_checkout_cannot_downgrade_accepted_truth(self):
        accepted = self.store["accepted_measurement"]
        if (self.store["n_served"] < accepted["served"] or
                self.store["n_blocks"] < accepted["decision_state_blocks"]):
            self.assertEqual(self.store["measurement_status"], "REGRESSED_LOCAL_SURVEY_DO_NOT_WRITE")
            with self.assertRaises(RuntimeError):
                mod._write_guard(self.store)
        elif (self.store["n_served"] > accepted["served"] or
              self.store["n_blocks"] > accepted["decision_state_blocks"]):
            self.assertEqual(self.store["measurement_status"], "ADVANCED_SURVEY_UPDATE_LOCK_BEFORE_WRITE")
            with self.assertRaises(RuntimeError):
                mod._write_guard(self.store)
        else:
            self.assertEqual(self.store["measurement_status"], "CURRENT_ACCEPTED_SURVEY")
            mod._write_guard(self.store)

    def test_unread_is_not_frankie_access_control(self):
        self.assertIn("does not mean unavailable", self.store["reader_semantics"])
        self.assertTrue(all(row["frankie_access"] == "TARGET_CELL_MANIFEST_DECIDES"
                            for row in self.store["served"]))

    def test_completed_gap_claims_cannot_return(self):
        absent = "\n".join(x["field"] for x in self.store["known_absent"])
        held = "\n".join(x["field"] for x in self.store["held_not_served"])
        self.assertNotIn("forward wind / solar generation forecast", absent)
        self.assertNotIn("zero-change", absent)
        self.assertNotIn("gen_mwh['WAT']", held)
        self.assertFalse(any(x["field"].startswith("GEFS") for x in self.store["identified_not_committed"]))

    def test_implemented_frankie_harnesses_are_not_replanned(self):
        planned = {x["item"] for x in self.store["planned_from_registry"]}
        for item in ("A-42", "A-59", "A-61", "A-62", "A-65", "A-66", "A-67", "A-68", "A-69"):
            self.assertNotIn(item, planned)


if __name__ == "__main__":
    unittest.main()
