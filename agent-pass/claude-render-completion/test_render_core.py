import unittest, math
from render_core import relative_seconds, lifecycle_markers, display_values, candidate_labels, prebirth_cutoff

class RenderContracts(unittest.TestCase):
    def test_finalize_only_has_explicit_birth_but_no_live_recognition(self):
        row={"input_disposition":"finalize_only_no_live_recognition",
             "original_episode":{"birth_recv_ns":1696366763000000000,"recognized_recv_ns":1696366809000000000},
             "recorded_operands":{"event_second":1696366763,"available_second":1696366809}}
        labels=candidate_labels(row)
        self.assertEqual(labels["birth_second"],1696366763)
        self.assertEqual(labels["available_second"],1696366809)
        self.assertFalse(labels["live_recognition_allowed"])
    def test_disagreeing_birth_clocks_are_not_guessed(self):
        with self.assertRaises(ValueError):
            candidate_labels({"original_episode":{"birth_recv_ns":100000000000},
                              "recorded_operands":{"event_second":101}})
    def test_unavailable_saved_cutoff_uses_labelled_axis_convention(self):
        self.assertEqual(prebirth_cutoff("-1",1697576378),1697576377999999999)
        self.assertEqual(prebirth_cutoff("1697576377999999999",1697576378),1697576377999999999)
    def test_seam_omission_does_not_remove_recognition_permission(self):
        labels=candidate_labels({"birth_second":1696291285,"available_second":1696291335})
        self.assertTrue(labels["live_recognition_allowed"])
    def test_nanosecond_anchor(self):
        self.assertEqual(relative_seconds(1696197693000000000,1696197692999999999),1e-9)
    def test_missing_recognition(self):
        self.assertIsNone(relative_seconds(None,1696197692999999999))
    def test_missing_values_remain_missing(self):
        v=display_values([0,float('nan'),3])
        self.assertTrue(math.isnan(v[1]))
        self.assertEqual(v[0],0)
    def test_elapsed_time_not_row_count(self):
        m=lifecycle_markers([99,100,105,112],[1,1,-1,float('nan')],100,1)
        self.assertEqual(m['first_flip_s'],5)
        self.assertEqual(m['first_empty_s'],12)
    def test_empty_at_birth(self):
        m=lifecycle_markers([100,101],[float('nan'),1],100,1)
        self.assertEqual(m['first_empty_s'],0)
        self.assertIsNone(m['run_onset_s'])
    def test_censored_tail(self):
        m=lifecycle_markers([100,101],[1,1],100,1)
        self.assertTrue(m['tail_unresolved'])
        self.assertIsNone(m['first_flip_s'])
        self.assertEqual(m['window_end_s'],1260)
    def test_cap_does_not_change_marker(self):
        m=lifecycle_markers([100,2100,2200],[1,-1,float('nan')],100,1)
        self.assertEqual(m['first_flip_s'],2000)
        self.assertEqual(m['window_end_s'],1260)
        self.assertTrue(m['window_capped'])
if __name__=='__main__': unittest.main()
