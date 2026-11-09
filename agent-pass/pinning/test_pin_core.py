import unittest
from pin_core import exact_int, utc_ns, extract_clocks, select_index, layer_fields

class ClockTests(unittest.TestCase):
    def test_nanoseconds_are_not_rounded(self):
        ns=1696206092957453764
        self.assertEqual(exact_int(str(ns)),ns)
        self.assertEqual(utc_ns(ns),"2023-10-02T00:21:32.957453764Z")
    def test_latest_invalid_is_not_replaced_by_older_present(self):
        self.assertEqual(select_index([10,20],20),1)
        self.assertEqual(select_index([10,20],9),-1)
    def test_equal_publications_keep_last_source_order(self):
        self.assertEqual(select_index([10,20,20,30],20),2)
    def test_future_value_is_never_in_asof_context(self):
        self.assertEqual(select_index([10,20,30],29),1)
    def test_durations_are_not_absolute_clocks(self):
        c,_=extract_clocks({"receive_ns":1696206092957453764,"duration_receive_ns":99,"seconds_since_previous":2})
        self.assertEqual([x["field"] for x in c],["receive_ns"])
    def test_horizon_is_relative_to_event_not_session(self):
        r={"day0_epoch_s":1696194000,"t0":3693,"t0_epoch_s":1696197693,
           "info_horizon_local_s":5,"info_horizon_local_s_epoch_s":1696194005}
        c,fix=extract_clocks(r,ccode=True)
        by={x["field"]:x for x in c}
        self.assertEqual(by["info_horizon_local_s_epoch_s"]["ns"],1696197698000000000)
        self.assertEqual(len(fix),1)
    def test_nested_clocks_remain_distinct(self):
        c,_=extract_clocks({"first":{"receive_ns":1696204800000000001},
                           "last":{"receive_ns":1696204800000000002}})
        self.assertEqual(len(c),2)
        self.assertEqual([x["field"] for x in c],["first.receive_ns","last.receive_ns"])
    def test_original_epoch_second_is_label_not_availability(self):
        c,_=extract_clocks({"second":"1696204800"})
        self.assertEqual(c[0]["role"],"second_label")
    def test_missing_recognition_is_not_invented(self):
        c,_=extract_clocks({"birth_second":1696204800,"recognition_ns":None})
        self.assertEqual(len(c),1)
    def test_flow_and_outcome_are_different_layers(self):
        a=layer_fields(["native_buy","later_move","event_ns"])
        self.assertIn("aggressor_and_native_signed_flow",a["native_buy"])
        self.assertIn("later_outcome_reveal",a["later_move"])
        self.assertEqual(a["event_ns"],["clock_event_time"])
if __name__=="__main__":unittest.main()
