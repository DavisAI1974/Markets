import unittest, math
from render_core import relative_seconds, lifecycle_markers, display_values

class RenderContracts(unittest.TestCase):
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
