import unittest
from link_io import asof,parent_key
class JoinTests(unittest.TestCase):
    def test_day_and_kind_are_identity(self):
        self.assertNotEqual(parent_key("20231002","same"),parent_key("20231003","same"))
        self.assertNotEqual(parent_key("20231002","same"),parent_key("20231002","same","control1"))
    def test_no_future_and_equal_time(self):
        self.assertEqual(asof([10,20],9),-1)
        self.assertEqual(asof([10,20],20),1)
    def test_tied_publications_keep_last(self):
        self.assertEqual(asof([10,10,20],10),1)
    def test_nanosecond_precision(self):
        t=1696206036000000000
        self.assertEqual(asof([t-1,t],t-1),0)
    def test_invalid_latest_is_not_skipped(self):
        times=[10,20];states=["PRESENT","INVALID"]
        self.assertEqual(states[asof(times,21)],"INVALID")
if __name__=="__main__":unittest.main()
