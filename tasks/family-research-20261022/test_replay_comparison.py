import unittest
from research_replay_comparison import candidate_inputs


class CandidateClocks(unittest.TestCase):
    def fixture(self):
        emission = dict(group_index=0, input_cursor=8, ts_recv_ns=105_500_000_000)
        records = [dict(emitting_section='candidate', candidate_id='x', polarity=1),
                   dict(emitting_section='episode', candidate_id='x', birth_recv_ns=90_000_000_000,
                        recognized_recv_ns=100_000_000_000, frankie_emission=emission),
                   dict(emitting_section='flow_substrate', second=90, buy_volume=2, sell_volume=0),
                   dict(emitting_section='flow_substrate', second=104, buy_volume=0, sell_volume=3)]
        groups = [dict(group_ordinal=0, close_cursor=8, receive_ns=105_500_000_000)]
        return records, groups

    def test_actual_emission_and_last_closed_second(self):
        records, groups = self.fixture()
        c = candidate_inputs(records, groups)[0]
        self.assertEqual(c['recognition_receive_ns'],105_500_000_000)
        self.assertEqual(c['last_closed_second'],104)
        self.assertEqual(c['last_closed_window']['roll20'],-.2)
        self.assertEqual(c['birth_to_emission_flow_state'],'opposite_direction_at_emission')

    def test_mismatched_group_is_rejected(self):
        records, groups = self.fixture()
        groups[0]['close_cursor'] = 7
        with self.assertRaises(ValueError):candidate_inputs(records, groups)

    def test_missing_candidate_operands_not_fabricated(self):
        records, groups = self.fixture()
        with self.assertRaises(ValueError):candidate_inputs(records[1:], groups)

    def test_finalize_is_retained_without_backdated_group(self):
        records, groups = self.fixture()
        records[1]['frankie_emission'].update(group_index=None,phase='FINALIZE')
        c = candidate_inputs(records, groups)[0]
        self.assertEqual(c['input_disposition'],'finalize_only_no_live_recognition')
        self.assertIsNone(c['recognition_group'])


if __name__ == '__main__':unittest.main()
