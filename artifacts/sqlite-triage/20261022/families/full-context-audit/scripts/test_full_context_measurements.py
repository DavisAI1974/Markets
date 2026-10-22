import unittest
from full_context_measurements import Measurements,native_measurements,second_measurements,state_field_eligible


class FullMeasurementTests(unittest.TestCase):
    def test_counts_do_not_turn_unavailable_values_into_zero(self):
        out=Measurements();out.counts({'a':{'value':0,'state':'MISSING','reason':'NO_FLOW'},'b':{'value':0,'state':'PRESENT','reason':''}},'book')
        self.assertIsNone(out.numeric['book.a.value']);self.assertEqual(out.numeric['book.b.value'],0)
        self.assertEqual(out.categories['book.a.state'],'"MISSING"')

    def test_absolute_clocks_and_ids_blocked_but_duration_counts_allowed(self):
        out=Measurements();out.counts({'anchor_sequence':3,'family_id':'f','event_ns':101,'elapsed_recv_ns':9,'groups_since_anchor':7,'continuity_segment':2},'x')
        self.assertEqual(out.numeric,{'x.elapsed_recv_ns':9.,'x.groups_since_anchor':7.})

    def test_fifo_positions_preserve_order_and_ahead_quantity(self):
        j={'book_full':{'bid_levels_full':[{'order_count':2,'size':5,'fifo_queue':[{'size':2,'volume_ahead':0,'priority_age_s':10.},{'size':3,'volume_ahead':2,'priority_age_s':1.}]}],'ask_levels_full':[]},'raw_actions':[],'frankie_emission':{'ts_recv_ns':100}}
        out=native_measurements(j)
        self.assertEqual(out.numeric['native.book.bid_levels.rank1.fifo_position2.volume_ahead'],2)
        self.assertNotIn('order_id',' '.join(out.numeric))
        j['book_full']['bid_levels_full'][0]['fifo_queue'][1]['volume_ahead']=0
        with self.assertRaises(AssertionError):native_measurements(j)

    def test_identity_and_future_answer_buckets_not_numeric_predictors(self):
        self.assertFalse(state_field_eligible('native.member|family_id'))
        self.assertFalse(state_field_eligible('native.lifecycle:episode|outcome'))
        self.assertFalse(state_field_eligible('root.structures|candidate_family_id'))
        self.assertTrue(state_field_eligible('native.member|fifo_priority_reconstructed'))
        self.assertTrue(state_field_eligible('native.lifecycle:flow_substrate|window_direction'))


if __name__=='__main__':unittest.main()
