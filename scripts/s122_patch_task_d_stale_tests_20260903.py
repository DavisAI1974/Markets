from pathlib import Path

p = Path('research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py')
text = p.read_text(encoding='utf-8')

old = '''    def test_knowledge_layers_bound_to_the_inventory_document_say_so(self):
        for layer_id in ("complete_s105_9_brain", "learned_d_structures_and_families", "october_outcome_wall_enforcement"):
            with self.subTest(layer_id=layer_id):
                self.assertEqual(self.cw[layer_id]["status"], "BOUND_TO_INVENTORY_DOCUMENT")
                self.assertEqual(self.cw[layer_id]["evidence"]["kind"], "INVENTORY_DOCUMENT")
'''
new = '''    def test_rebound_knowledge_layers_are_produced_not_delivered_without_receipts(self):
        for layer_id in ("complete_s105_9_brain", "learned_d_structures_and_families", "october_outcome_wall_enforcement"):
            with self.subTest(layer_id=layer_id):
                self.assertEqual(self.cw[layer_id]["status"], "PRODUCED_NOT_DELIVERED")
                self.assertEqual(self.cw[layer_id]["evidence"]["kind"], "NONE")
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)

old = '''    def test_lock_time_has_no_producer(self):
        self.assertEqual(self.cw["clock_lock_time"]["status"], "NO_PRODUCER_FOUND")
'''
new = '''    def test_lock_time_has_no_ingestion_producer_but_is_principal_stamped(self):
        self.assertEqual(self.cw["clock_lock_time"]["status"], "PRINCIPAL_STAMPED")
        self.assertEqual(LAYER_PRODUCERS["clock_lock_time"]["kind"], "NO_PRODUCER_FOUND")
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)

old = '''        self.assertEqual(self.cw["clock_prospective_discovery_confirmation"]["status"], "RECEIPTED_CARRIER_ABSENT")
        self.assertEqual(self.cw["clock_lock_time"]["status"], "NO_PRODUCER_FOUND")
'''
new = '''        self.assertEqual(self.cw["clock_prospective_discovery_confirmation"]["status"], "RECEIPTED_CARRIER_ABSENT")
        self.assertEqual(self.cw["clock_lock_time"]["status"], "PRINCIPAL_STAMPED")
'''
assert text.count(old) == 1
text = text.replace(old, new, 1)

p.write_text(text, encoding='utf-8')
