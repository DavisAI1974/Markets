import unittest
from episode_path_checks import stage_bin, check_path, lawful


class EpisodePathTests(unittest.TestCase):
    def test_stage_bins_are_closed_octaves(self):
        self.assertEqual([stage_bin(k) for k in [0,1,2,3,4,691]],[(0,0),(1,1),(2,3),(2,3),(4,7),(512,1023)])

    def test_zero_flow_does_not_invent_direction_and_reversals_skip_zeros(self):
        stages=[]
        for i,flow in enumerate([2,0,-3,0,4]):
            lo,hi=stage_bin(i)
            stages.append(dict(runway_id='x',stage_index=i,recv_ns=10+i,orientation='FLIP',signed_flow=flow,
                direction='LONG' if flow>0 else 'SHORT' if flow<0 else 'NO_DIRECTION',magnitude=abs(flow),
                bid_depth=4,ask_depth=2,normalized_imbalance=1/3,price_raw=100+i,
                stage_bin=f'STAGE_{lo}_{hi}',stage_bin_first_index=lo,stage_bin_last_index=hi))
        path=dict(runway_id='x',orientation='FLIP',stage_count=5,stages=stages,
             sign_reversals=[dict(stage_index=2,recv_ns=12,from_direction='LONG',to_direction='SHORT'),
                             dict(stage_index=4,recv_ns=14,from_direction='SHORT',to_direction='LONG')],
             sign_reversal_count=2,persisted=False,inflection_recv_ns=12,price_coupling_raw=4)
        self.assertEqual(check_path(path,20)['stage_count'],5)
        path['stages'][1]['direction']='LONG'
        with self.assertRaises(AssertionError):check_path(path,20)

    def test_emission_clock_and_cursor_control_availability(self):
        row=dict(known_by_ns=100,input_cursor=8,instrument_id=1)
        self.assertFalse(lawful(row,99,8,1))
        self.assertFalse(lawful(row,100,7,1))
        self.assertFalse(lawful(row,100,8,2))
        self.assertTrue(lawful(row,100,8,1))


if __name__=='__main__':unittest.main()
