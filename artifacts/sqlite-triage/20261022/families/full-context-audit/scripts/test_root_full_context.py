import unittest
from root_full_context import root_measurements


class RootContextTests(unittest.TestCase):
    def test_order_update_age_uses_identity_and_exact_known_clock(self):
        order=dict(order_id=7,instrument_id=1,side='B',price_raw=3000000000,size=4,
                   priority_recv_ns=900,priority_sequence=3,last_update_recv_ns=950)
        queue=dict(order_id=7,size=4,volume_ahead=0,priority_age_s=1e-7,
                   priority_recv_ns=900,priority_sequence=3)
        level=dict(price_raw=3000000000,price=3.,size=4,order_count=1,fifo_queue=[queue])
        frame=dict(ts_recv_ns=1000,input_cursor=8,activity={},book=dict(bid_levels_full=[level],ask_levels_full=[]),
                   observation=dict(orders=[order],levels={'B':[dict(price_raw=3000000000,order_ids=[7])],'A':[]}),
                   input_records=[],native_frame=dict(raw_actions=[]))
        native=dict(frankie_emission=dict(ts_recv_ns=1000,input_cursor=8),book_full=dict(bid_levels_full=[level],ask_levels_full=[]),raw_actions=[])
        measured,checks=root_measurements(frame,{},native)
        self.assertEqual(measured.numeric['root_full.book.bid.rank1.fifo_position1.last_update_age_ns'],50.)
        self.assertEqual(checks['order_identity_matches'],1)
        self.assertFalse(any(k.endswith('order_id') for k in measured.numeric))
        frame['observation']['levels']['B'][0]['order_ids']=[99]
        with self.assertRaises(AssertionError):root_measurements(frame,{},native)

    def test_future_order_update_is_retained_as_unavailable(self):
        order=dict(order_id=7,instrument_id=1,side='B',price_raw=1,size=1,
                   priority_recv_ns=900,priority_sequence=3,last_update_recv_ns=1001)
        queue=dict(order_id=7,size=1,volume_ahead=0,priority_age_s=1e-7,priority_recv_ns=900,priority_sequence=3)
        level=dict(price_raw=1,price=1e-9,size=1,order_count=1,fifo_queue=[queue])
        frame=dict(ts_recv_ns=1000,input_cursor=8,activity={},book=dict(bid_levels_full=[level],ask_levels_full=[]),
                   observation=dict(orders=[order],levels={'B':[dict(price_raw=1,order_ids=[7])],'A':[]}),
                   input_records=[],native_frame=dict(raw_actions=[]))
        native=dict(frankie_emission=dict(ts_recv_ns=1000,input_cursor=8),book_full=dict(bid_levels_full=[level],ask_levels_full=[]),raw_actions=[])
        measured,checks=root_measurements(frame,{},native)
        self.assertIsNone(measured.numeric['root_full.book.bid.rank1.fifo_position1.last_update_age_ns'])
        self.assertEqual(checks['future_last_update_clocks'],1)


if __name__=='__main__':unittest.main()
